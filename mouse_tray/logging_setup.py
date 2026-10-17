"""Centralized logging configuration.

Built for a windowed (``--noconsole``) tray app:

* Writes a **rotating log file** in the ``logs`` folder next to the program
  (the app is portable: nothing is written to ``AppData``) **only while Debug
  logging is on** (the setting or ``MOUSE_TRAY_DEBUG``). Off, no file and no
  folder are created; warnings still go to the console when there is one.
* Adds a console handler **only when a console exists** -- under PyInstaller's
  windowed build ``sys.stderr`` is ``None``, and a plain ``StreamHandler`` would
  raise on every log call.
* With Debug on the level is DEBUG (every read, HID byte dumps); off, WARNING.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from contextlib import suppress
from logging.handlers import RotatingFileHandler

from .resources import app_dir

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 3
_DEBUG_ENV = "MOUSE_TRAY_DEBUG"
_LOG_FILE = "app.log"


def log_dir() -> str:
    """Log folder next to the program (``<app folder>\\logs``)."""
    return os.path.join(app_dir(), "logs")


def log_path() -> str:
    """The current log file (older rotations sit next to it as ``app.log.1``...)."""
    return os.path.join(log_dir(), _LOG_FILE)


def open_log() -> None:
    """Open the log file in whatever the user reads text with; fall back to
    the log folder if the file is missing or has no associated program."""
    try:
        os.startfile(log_path())
    except (AttributeError, OSError):  # non-Windows, no file, no association
        with suppress(AttributeError, OSError):
            os.startfile(log_dir())


def log_exists() -> bool:
    """Whether a log file has been written (it exists only after Debug logging)."""
    return os.path.isfile(log_path())


def _debug_enabled(debug: bool) -> bool:
    if debug:
        return True
    return os.environ.get(_DEBUG_ENV, "").strip().lower() in ("1", "true", "yes", "on")


def _log_thread_exception(args: threading.ExceptHookArgs) -> None:
    """Send an uncaught exception of any thread to the log (file included)."""
    name = args.thread.name if args.thread else "?"
    logging.getLogger("mouse_tray").error(
        "Uncaught exception in thread %s", name, exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
    )


def setup_logging(debug: bool = False) -> str | None:
    """Configure root logging. Returns the log file path, or ``None`` if the
    file handler could not be created.

    Idempotent: existing handlers are cleared so calling it twice does not
    duplicate output.
    """
    verbose = _debug_enabled(debug)
    level = logging.DEBUG if verbose else logging.WARNING
    threading.excepthook = _log_thread_exception
    root = logging.getLogger()
    root.setLevel(level)
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(_FORMAT)

    # Console handler only if a usable stream exists (None under --noconsole).
    stream = sys.stderr or sys.stdout
    if stream is not None:
        console = logging.StreamHandler(stream)
        console.setFormatter(formatter)
        root.addHandler(console)

    # Rotating file handler -- only with Debug on; best effort, never crash the app.
    path: str | None = None
    if not verbose:
        return None
    try:
        os.makedirs(log_dir(), exist_ok=True)
        path = log_path()
        file_handler = RotatingFileHandler(
            path, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT,
            encoding="utf-8", delay=True,
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        path = None

    if path:
        logging.getLogger(__name__).info("Logging to %s (level=%s)", path, logging.getLevelName(level))
    return path
