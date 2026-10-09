"""Action mapping is independent from recognition and input collection."""
import logging
import shlex
import subprocess
import time
from typing import Protocol
from evdev import UInput, ecodes as e
from .config import key_code

log = logging.getLogger(__name__)


class KeyBackend(Protocol):
    def send(self, keys: list[str]) -> None: ...
    def close(self) -> None: ...


class UInputExecutor:
    def __init__(self, keys):
        # udev identifies a full keyboard using key codes 1..31.
        codes = sorted(set(range(1, 32)) | {key_code(k) for k in keys})
        self.device = UInput({e.EV_KEY: codes}, name="touchgesture keyboard")
        # Allow the compositor to discover the persistent virtual keyboard.
        time.sleep(0.5)

    def send(self, keys):
        pressed = []
        try:
            for key in keys:
                code = key_code(key)
                self.device.write(e.EV_KEY, code, 1)
                pressed.append(code)
            self.device.syn()
            time.sleep(0.02)
        finally:
            for code in reversed(pressed):
                self.device.write(e.EV_KEY, code, 0)
            self.device.syn()

    def close(self):
        self.device.close()


class ActionExecutor:
    def __init__(self, gestures, dry_run=True, backend=None):
        self.dry_run = dry_run
        self.children = []
        self.backend = backend
        keys = [k for g in gestures if g["action"]["type"] == "key" for k in g["action"]["keys"]]
        if not dry_run and keys and backend is None:
            self.backend = UInputExecutor(keys)

    def execute(self, gesture):
        action = gesture["action"]
        description = "+".join(action["keys"]) if action["type"] == "key" else action["command"]
        log.info("Matched: %s | Action: %s%s", gesture["name"], description, " | DRY RUN — action skipped" if self.dry_run else "")
        if self.dry_run:
            return
        self.children = [p for p in self.children if p.poll() is None]
        if action["type"] == "key":
            self.backend.send(action["keys"])
        elif len(self.children) >= 8:
            log.warning("Command skipped: 8 commands are still running")
        else:
            try:
                self.children.append(subprocess.Popen(shlex.split(action["command"]), stdin=subprocess.DEVNULL, start_new_session=True))
            except OSError as exc:
                log.error("Cannot run command: %s", exc)

    def close(self):
        if self.backend:
            self.backend.close()
        for child in self.children:
            child.poll()
