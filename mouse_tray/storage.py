"""Portable persistence: one JSON file next to the program.

Everything the app remembers -- user settings, and per mouse the moment of its
last full charge and the last charge level it was seen at --
lives in ``mouse_tray.json`` in the application folder (see
:func:`~mouse_tray.resources.app_dir`). Nothing goes to the Windows registry or
``AppData``, so the folder can be copied to another PC or deleted as a whole.

Writes are atomic (temp file + ``os.replace``) and never raise: a read-only
folder just means settings do not persist, which is logged on every failure.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from contextlib import suppress
from datetime import datetime
from typing import Any

from .config import TEXT_SIZE_MAX, TEXT_SIZE_MIN, Config
from .resources import app_dir

log = logging.getLogger(__name__)

FILE_NAME = "mouse_tray.json"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

#: Guards read-modify-write of the file (saves come from the UI thread today,
#: but the lock keeps that an implementation detail).
_lock = threading.RLock()


def storage_path() -> str:
    """Absolute path of the JSON state file."""
    return os.path.join(app_dir(), FILE_NAME)


def _load() -> dict[str, Any]:
    """The whole stored document; ``{}`` when absent or unreadable.

    An unreadable file is moved aside to ``<name>.corrupt`` so a later save does
    not silently destroy whatever was in it.
    """
    path = storage_path()
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        log.warning("Could not read %s (%s); starting from empty settings", path, exc)
        with suppress(OSError):
            os.replace(path, path + ".corrupt")
        return {}
    return data if isinstance(data, dict) else {}


def _save(data: dict[str, Any]) -> bool:
    path = storage_path()
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except OSError as exc:
        log.warning("Could not write %s: %s", path, exc)
        return False
    return True


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    """``data[name]`` as a dict, created (or repaired) in place."""
    value = data.get(name)
    if not isinstance(value, dict):
        value = {}
        data[name] = value
    return value


def _mouse_entry(data: dict[str, Any], mouse: str) -> dict[str, Any]:
    return _section(_section(data, "mice"), mouse.strip() or "Unknown")


# --- per-mouse state: last full charge, last seen level -----------------------


def save_full_charge_date(mouse: str, when: datetime) -> None:
    """Persist the moment ``mouse`` was last fully charged."""
    with _lock:
        data = _load()
        _mouse_entry(data, mouse)["full_charge"] = when.strftime(_DATE_FORMAT)
        _save(data)


def load_full_charge_date(mouse: str) -> datetime | None:
    """``mouse``'s stored full-charge timestamp, or ``None`` if absent/invalid."""
    with _lock:
        value = _mouse_entry(_load(), mouse).get("full_charge")
    try:
        return datetime.strptime(value, _DATE_FORMAT)
    except (TypeError, ValueError):
        return None


def save_last_percent(mouse: str, percent: int) -> None:
    """Remember the last charge level seen for ``mouse``.

    This is what lets the next launch tell "charged while the PC was off" (the
    level was below 100 when the app last looked, and is 100 now) from "was
    already full".
    """
    with _lock:
        data = _load()
        entry = _mouse_entry(data, mouse)
        if entry.get("last_percent") == percent:
            return
        entry["last_percent"] = int(percent)
        _save(data)


def load_last_percent(mouse: str) -> int | None:
    """Last charge level seen for ``mouse``, or ``None`` if never recorded."""
    with _lock:
        value = _mouse_entry(_load(), mouse).get("last_percent")
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
        return None
    return value


# --- user settings ------------------------------------------------------------


def _color(value: object) -> tuple[int, int, int] | None:
    """A stored ``[r, g, b]`` list as a tuple, or ``None`` if it is not one."""
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    if not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255 for c in value):
        return None
    return (value[0], value[1], value[2])


def save_settings(config: Config) -> None:
    """Persist the user-tunable settings (poll rate, font, size, colors, debug)."""
    with _lock:
        data = _load()
        data["settings"] = {
            "poll_rate": int(config.poll_rate),
            "font": config.font,
            "text_size": int(config.text_size),
            "text_outline": bool(config.text_outline),
            "foreground_color": list(config.foreground_color),
            "dynamic_color": bool(config.dynamic_color),
            "mid_color": list(config.mid_color),
            "low_color": list(config.low_color),
            "battery_icon": bool(config.battery_icon),
            "dark_theme": bool(config.dark_theme),
            "debug": bool(config.debug),
            "language": config.language,
        }
        _save(data)


def load_settings(config: Config) -> None:
    """Apply persisted settings onto ``config`` in place.

    Missing or invalid values are skipped so each field keeps its code default.
    """
    with _lock:
        saved = _load().get("settings")
    if not isinstance(saved, dict):
        return

    poll_rate = saved.get("poll_rate")
    if isinstance(poll_rate, int) and not isinstance(poll_rate, bool) and poll_rate > 0:
        config.poll_rate = poll_rate

    font = saved.get("font")
    if isinstance(font, str) and font:
        config.font = font

    text_size = saved.get("text_size")
    if isinstance(text_size, int) and TEXT_SIZE_MIN <= text_size <= TEXT_SIZE_MAX:
        config.text_size = text_size

    for field in ("text_outline", "dynamic_color", "battery_icon", "dark_theme", "debug"):
        if isinstance(saved.get(field), bool):
            setattr(config, field, saved[field])

    language = saved.get("language")
    if isinstance(language, str) and language in {"en", "ru", "uk"}:
        config.language = language

    for field in ("foreground_color", "mid_color", "low_color"):
        if (parsed := _color(saved.get(field))) is not None:
            setattr(config, field, parsed)

