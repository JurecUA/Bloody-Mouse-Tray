"""Best-effort release of dialog UI memory after Settings / About / tray menu close.

Python rarely returns heap pages to the OS on its own. After the painted dialog
toolkit is no longer referenced we drop those modules from ``sys.modules``, run
a GC pass, and on Windows ask the kernel to trim the process working set so Task
Manager reflects the lighter pure-tray footprint again.

wxPython and PIL stay loaded — the tray icon needs them — so this cannot return
to a few megabytes, only shed the dialog layer.
"""

from __future__ import annotations

import gc
import sys
from contextlib import suppress

#: Modules that exist only for Settings / About / the painted tray menu.
_UI_MODULES = (
    "mouse_tray.ui.settings",
    "mouse_tray.ui.about",
    "mouse_tray.ui.widgets",
)


def release_ui_memory() -> None:
    """Unload dialog modules (if idle) and trim the Windows working set."""
    # Settings keeps a module-global while the modal is open — skip then.
    settings = sys.modules.get("mouse_tray.ui.settings")
    if settings is not None and getattr(settings, "_open_dialog", None) is not None:
        return

    for name in _UI_MODULES:
        sys.modules.pop(name, None)

    gc.collect()
    gc.collect()  # second pass for cyclic wx wrappers

    with suppress(AttributeError, OSError):
        # Empty working set: kernel discards unused pages; they fault back in
        # cheaply when the tray next needs them. Looks like a real drop in RAM.
        kernel = __import__("ctypes").windll.kernel32
        kernel.SetProcessWorkingSetSize(kernel.GetCurrentProcess(), -1, -1)
