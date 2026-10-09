import argparse
from copy import deepcopy
import logging
import os
import signal
import sys
from .actions import ActionExecutor
from .display import DisplayMonitor
from .notification import NotificationPreview
from .overlay import OverlayPreview
from .preview import GesturePreview
from evdev import ecodes as e
from .config import ConfigError, default_path, load_config
from .input import TwoFingerRecorder, describe, devices, initialize_recorder, select_device
from .recognition import match, recognize
from .rotation import StrokeOrientation

log = logging.getLogger(__name__)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Passive touchscreen gesture daemon")
    parser.add_argument("--config", help=f"YAML path (default: {default_path()})")
    parser.add_argument("--rotation", choices=["auto", "0", "90", "180", "270"], help="Display orientation (default: config, auto)")
    parser.add_argument("--no-preview", action="store_true", help="Disable gesture preview UI")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Only log; never open uinput or execute commands")
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--check-config", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO, format="%(levelname)s: %(message)s")
    dev = executor = display = preview = None
    old_handler = None
    try:
        if args.list_devices:
            opened = devices()
            try:
                for item in opened:
                    print(describe(item))
                if not opened:
                    print("No accessible input devices. Check /dev/input and permissions.")
            finally:
                for item in opened:
                    item.close()
            return 0 if opened else 1
        cfg = load_config(args.config)
        if args.rotation is not None:
            cfg["device"]["rotation"] = args.rotation
        if args.check_config:
            print(f"Config OK: {len(cfg['gestures'])} gestures; dry_run={cfg['dry_run']}")
            return 0
        dev = select_device(cfg["device"])
        # Request monotonic timestamps where the installed evdev exposes it.
        import time
        if hasattr(dev, "set_clockid"):
            dev.set_clockid(time.CLOCK_MONOTONIC)
        if str(cfg['device']['rotation']) == 'auto':
            display = DisplayMonitor()
        reader = display.read if display is not None else None
        orientation = StrokeOrientation(cfg, reader)
        orientation.current()  # Diagnose missing GNOME session before creating a keyboard.
        input_cfg = deepcopy(cfg)
        input_cfg["recognition"]["distance_mode"] = "normalized"
        recorder = initialize_recorder(dev, input_cfg)
        two_finger = TwoFingerRecorder(recorder)
        two_orientation = StrokeOrientation(cfg, reader)
        executor = ActionExecutor(cfg["gestures"], cfg["dry_run"] or args.dry_run)
        if cfg["preview"] and not args.no_preview:
            ui = OverlayPreview() if cfg["preview_backend"] == "overlay" else NotificationPreview()
            preview = GesturePreview(cfg, ui, executor.dry_run)
            if display is not None:
                display.on_change = preview.hide
        log.info("touchgesture started | Session: %s", os.environ.get("XDG_SESSION_TYPE", "unknown"))
        log.info("Device: %s | Loaded gestures: %d | dry_run=%s", describe(dev), len(cfg["gestures"]), executor.dry_run)
        def stop(signum, frame):
            raise KeyboardInterrupt
        old_handler = signal.signal(signal.SIGTERM, stop)
        # No EVIOCGRAB: events continue reaching GNOME and applications.
        for event in dev.read_loop():
            had_points = bool(recorder.points)
            had_two_points = bool(two_finger.tracks)
            stroke = recorder.feed(event)
            pair = two_finger.feed(event)
            if not had_two_points and two_finger.tracks:
                two_orientation.begin()
            if not had_points and recorder.points:
                orientation.begin()
            if preview and event.type == e.EV_SYN and event.code == e.SYN_REPORT:
                preview.update(event.timestamp(), recorder, two_finger, orientation, two_orientation)
            fingers = 1
            if pair is not None:
                fingers = 2
                combined = two_orientation.finish(pair[0] + pair[1])
                if combined is None:
                    continue
                first = recognize(combined[:len(pair[0])], cfg["recognition"])
                second = recognize(combined[len(pair[0]):], cfg["recognition"])
                if first.reason or second.reason or first.sequence != second.sequence:
                    log.debug("Two-finger gesture rejected: %s / %s", first, second)
                    continue
                result = first
            elif stroke is not None:
                stroke = orientation.finish(stroke)
                if stroke is None:
                    continue
                result = recognize(stroke, cfg["recognition"])
            else:
                continue
            log.debug("Detected path: %s | %s", " -> ".join(result.sequence) or "UNKNOWN", result.reason or "valid")
            for i, (a, b) in enumerate(zip(result.points, result.points[1:]), 1):
                log.debug("Segment %d: dx=%.4f dy=%.4f direction=%s", i, b.x-a.x, b.y-a.y, result.sequence[i-1])
            gesture = match(result, cfg["gestures"], fingers=fingers)
            if gesture:
                log.info("Gesture: %s | fingers=%d", " -> ".join(result.sequence), fingers)
                executor.execute(gesture)
        raise RuntimeError("Input device stream ended")
    except KeyboardInterrupt:
        log.info("touchgesture stopped")
        return 0
    except (ConfigError, OSError, RuntimeError) as exc:
        log.error("%s", exc)
        if isinstance(exc, PermissionError):
            log.error("Grant access to the selected touchscreen and (only for key actions) /dev/uinput; see README.")
        return 1
    finally:
        if old_handler is not None:
            signal.signal(signal.SIGTERM, old_handler)
        if display:
            display.on_change = None
            display.close()
        if preview:
            preview.close()
        if executor:
            executor.close()
        if dev:
            dev.close()


if __name__ == "__main__":
    sys.exit(main())
