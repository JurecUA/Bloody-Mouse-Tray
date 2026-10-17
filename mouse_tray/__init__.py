"""Bloody SG5 Pro battery and report-rate tray indicator for Windows."""

from .config import VERSION as __version__

__all__ = ["__version__", "run"]


def run() -> None:
    """Launch the tray application.

    Imported lazily so the non-UI modules (storage, drivers, rate helpers) can be
    imported -- and unit-tested -- without wxPython installed.
    """
    from .ui import run as _run

    _run()
