"""Start with Windows: one value under the current user's ``Run`` registry key.

The registry is the single source of truth -- nothing about autostart is kept in
the app's own settings file -- so the checkbox always shows what Windows will
really do. The value holds the command line of *this* copy of the program; after
moving the program folder, enabling the option again (OK in the settings with the
box ticked) rewrites it.

``winreg`` is imported inside the functions so the module can be imported (and
tested) on any platform.
"""

from __future__ import annotations

import os
import sys

from .resources import app_dir

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "Bloody Mouse Tray"


def command() -> str:
    """The command line Windows runs at sign-in.

    The exe itself in a frozen build; from source, ``pythonw`` (no console
    window) running ``main.py``. Paths are quoted because they may contain spaces.
    """
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    interpreter = pythonw if os.path.exists(pythonw) else sys.executable
    return f'"{interpreter}" "{os.path.join(app_dir(), "main.py")}"'


def is_enabled() -> bool:
    """Whether the autostart value exists (``False`` anywhere but Windows)."""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _VALUE_NAME)
    except (ImportError, OSError):
        return False
    return True


def set_enabled(enabled: bool) -> None:
    """Add (or refresh) the autostart value, or remove it. Raises ``OSError`` on failure."""
    import winreg

    if enabled:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, command())
        return
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, _VALUE_NAME)
    except FileNotFoundError:
        pass  # already off
