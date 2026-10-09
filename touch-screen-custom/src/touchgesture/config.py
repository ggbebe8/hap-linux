"""Strict YAML validation; invalid configuration never enables actions."""
from copy import deepcopy
from difflib import get_close_matches
from importlib.resources import files
from math import isfinite
from pathlib import Path
import os
import shlex
import yaml


class ConfigError(ValueError):
    pass


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node):
    result = {}
    for k, v in node.value:
        key = loader.construct_object(k)
        if not isinstance(key, str) or key in result:
            raise ConfigError(f"invalid or duplicate YAML key: {key!r}")
        result[key] = loader.construct_object(v)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def default_path():
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home()/".config"))/"touchgesture/config.yaml"


def mapping(value, allowed, where):
    if not isinstance(value, dict):
        raise ConfigError(f"{where}: expected mapping")
    extra = value.keys() - set(allowed)
    if extra:
        raise ConfigError(f"{where}: unknown fields {sorted(extra)}")


def number(value, where, minimum=0, strict=True):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not isfinite(value):
        raise ConfigError(f"{where}: expected finite number")
    if value < minimum or (strict and value == minimum):
        raise ConfigError(f"{where}: must be {'greater than' if strict else 'at least'} {minimum}")


def key_code(name):
    from evdev import ecodes
    if not isinstance(name, str):
        raise ConfigError("keys must be strings")
    aliases = {"CTRL": "LEFTCTRL", "CONTROL": "LEFTCTRL", "SHIFT": "LEFTSHIFT", "ALT": "LEFTALT", "SUPER": "LEFTMETA", "META": "LEFTMETA", "ENTER": "ENTER", "ESC": "ESC"}
    name = name.upper()
    full = name if name.startswith("KEY_") else "KEY_" + aliases.get(name, name)
    code = getattr(ecodes, full, None)
    if not isinstance(code, int) or full in {"KEY_RESERVED", "KEY_MAX", "KEY_CNT"}:
        raise ConfigError(f"unknown key: {name}")
    return code


def load_config(path=None):
    defaults = yaml.load(files("touchgesture").joinpath("default.yaml").read_text(), Loader=UniqueLoader)
    source = Path(path) if path else default_path()
    try:
        data = yaml.load(source.read_text(), Loader=UniqueLoader) if source.exists() or path else {}
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"{source}: {exc}") from exc
    mapping(data, defaults, "config")
    cfg = deepcopy(defaults)
    for section in ("device", "recognition"):
        if section in data:
            allowed = set(defaults[section]) | ({"path", "name_contains", "display_connector"} if section == "device" else set())
            mapping(data[section], allowed, section)
            cfg[section].update(data[section])
    for field in ("dry_run", "preview", "preview_backend", "gestures"):
        if field in data:
            cfg[field] = data[field]
    if type(cfg["dry_run"]) is not bool:
        raise ConfigError("dry_run must be true or false")
    if type(cfg["preview"]) is not bool:
        raise ConfigError("preview must be true or false")
    if cfg["preview_backend"] not in ("overlay", "notification"):
        raise ConfigError("preview_backend must be overlay or notification")
    dev, rec = cfg["device"], cfg["recognition"]
    for key in ("auto_detect", "swap_axes", "invert_x", "invert_y"):
        if type(dev[key]) is not bool:
            raise ConfigError(f"device.{key}: expected boolean")
    for key in ("path", "name_contains", "display_connector"):
        if key in dev and (not isinstance(dev[key], str) or not dev[key].strip()):
            raise ConfigError(f"device.{key}: expected nonempty string")
    if not dev["auto_detect"] and not dev.get("path") and not dev.get("name_contains"):
        raise ConfigError("device: auto_detect=false requires path or name_contains")
    if str(dev["rotation"]) not in ("auto", "0", "90", "180", "270"):
        raise ConfigError("device.rotation must be auto, 0, 90, 180 or 270")
    for key in ("screen_width", "screen_height"):
        number(dev[key], f"device.{key}")
    if rec["distance_mode"] not in ("pixels", "normalized"):
        raise ConfigError("distance_mode must be pixels or normalized")
    # Normalized thresholds have useful defaults when not explicitly specified.
    if rec["distance_mode"] == "normalized":
        for key, value in {"min_point_distance": .005, "simplify_epsilon": .015, "min_segment_distance": .08, "min_total_distance": .18}.items():
            if key not in data.get("recognition", {}):
                rec[key] = value
    for key, value in rec.items():
        if key != "distance_mode":
            number(value, f"recognition.{key}")
    if rec["dominance_ratio"] <= 1:
        raise ConfigError("dominance_ratio must exceed 1")
    if not 0 < rec["corner_min_angle_deg"] <= rec["corner_max_angle_deg"] < 180:
        raise ConfigError("corner angles must satisfy 0 < min <= max < 180")
    if rec["simplify_epsilon"] >= rec["min_segment_distance"]:
        raise ConfigError("simplify_epsilon must be below min_segment_distance")
    if not isinstance(cfg["gestures"], list) or not cfg["gestures"]:
        raise ConfigError("gestures must be a nonempty list")
    names, sequences = set(), set()
    for g in cfg["gestures"]:
        mapping(g, ("name", "sequence", "action", "fingers", "label"), "gesture")
        if not isinstance(g.get("name"), str) or not g["name"].strip() or g["name"] in names:
            raise ConfigError("gesture name must be nonempty and unique")
        if "label" in g and (not isinstance(g["label"], str) or not g["label"].strip()):
            raise ConfigError("gesture.label must be a nonempty string")
        fingers = g.get("fingers", 1)
        if type(fingers) is not int or fingers not in (1, 2):
            raise ConfigError("gesture.fingers must be 1 or 2")
        names.add(g["name"])
        seq = g.get("sequence")
        if not isinstance(seq, list) or not seq:
            raise ConfigError(f"{g['name']}: sequence must be a nonempty list")
        for d in seq:
            if not isinstance(d, str) or d not in ("UP", "DOWN", "LEFT", "RIGHT"):
                suggestion = get_close_matches(str(d), ["UP", "DOWN", "LEFT", "RIGHT"], n=1)
                raise ConfigError(f"{g['name']}: unknown direction {d!r}; suggestion: {suggestion}")
        if (fingers, tuple(seq)) in sequences or any(a == b for a, b in zip(seq, seq[1:])):
            raise ConfigError(f"{g['name']}: duplicate sequence or consecutive identical directions")
        sequences.add((fingers, tuple(seq)))
        a = g.get("action")
        mapping(a, ("type", "keys", "command"), f"{g['name']}.action")
        if a.get("type") == "key":
            if "command" in a or not isinstance(a.get("keys"), list) or not a["keys"]:
                raise ConfigError("key action requires keys and no command")
            codes = [key_code(k) for k in a["keys"]]
            if len(codes) != len(set(codes)):
                raise ConfigError("duplicate keys in action")
        elif a.get("type") == "command":
            cmd = a.get("command")
            if "keys" in a or not isinstance(cmd, str) or not cmd.strip():
                raise ConfigError("command action requires command string and no keys")
            try:
                if not shlex.split(cmd):
                    raise ValueError("empty command")
            except ValueError as exc:
                raise ConfigError(f"invalid command: {exc}") from exc
        else:
            raise ConfigError("action.type must be key or command")
    return cfg
