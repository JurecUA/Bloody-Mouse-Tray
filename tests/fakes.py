"""Minimal stand-ins for ``hid`` and ``wx`` so the logic runs without a display or a mouse.

They stub only what the modules under test touch; they do NOT prove anything
about the real wxPython/hidapi behavior (see README: what is verified where).
"""

from __future__ import annotations

import sys
import types


def install_hid(devices: list[dict] | None = None) -> types.ModuleType:
    """The shared ``hid`` stub (one per process: the app modules import it once)."""
    existing = sys.modules.get("hid")
    if existing is not None and hasattr(existing, "_devices"):
        return existing
    mod = types.ModuleType("hid")
    mod._devices = devices or []
    mod.enumerate = lambda vid=0, pid=0: list(mod._devices)

    class device:  # noqa: N801 -- mirrors hidapi's class name
        queue: list[list[int]] = []
        #: Answers per status-channel path; a path listed here ignores ``queue``.
        by_path: dict[bytes, list[list[int]]] = {}
        opened: list[bytes] = []

        def open_path(self, path):
            self.path = path
            device.opened.append(path)

        def close(self): ...
        def send_feature_report(self, data): ...
        def read(self, n, timeout_ms=0):
            queue = device.by_path.get(getattr(self, "path", None), device.queue)
            return queue.pop(0) if queue else []

    mod.device = device
    sys.modules["hid"] = mod
    return mod


def install_winreg() -> types.ModuleType:
    """An in-memory ``winreg`` with the handful of calls the autostart code makes."""
    mod = types.ModuleType("winreg")
    mod.HKEY_CURRENT_USER, mod.KEY_SET_VALUE, mod.REG_SZ = 1, 2, 1
    mod.values = {}

    class Key:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def need(name):
        if name not in mod.values:
            raise FileNotFoundError(name)

    mod.OpenKey = lambda root, path, reserved=0, access=0: Key()
    mod.CreateKey = lambda root, path: Key()
    mod.SetValueEx = lambda key, name, reserved, kind, data: mod.values.__setitem__(name, data)
    mod.QueryValueEx = lambda key, name: (need(name), (mod.values[name], 1))[1]
    mod.DeleteValue = lambda key, name: (need(name), mod.values.pop(name))
    sys.modules["winreg"] = mod
    return mod


def install_wx() -> None:
    wx = types.ModuleType("wx")
    adv = types.ModuleType("wx.adv")
    svg = types.ModuleType("wx.svg")

    class Frame:
        def __init__(self, *a, **k): ...

    class Point:
        def __init__(self, x=0, y=0):
            self.x, self.y = x, y

    class Timer:
        def __init__(self, *a, **k):
            self.running = False

        def Start(self, ms):
            self.running = True

        def Stop(self):
            self.running = False

        def IsRunning(self):
            return self.running

    for name in ("App", "Icon", "Size", "Bitmap", "Dialog", "TimerEvent", "Window", "ListCtrl", "Menu"):
        setattr(wx, name, type(name, (), {"__init__": lambda self, *a, **k: None}))
    wx.Frame, wx.Point, wx.Timer = Frame, Point, Timer
    wx.EVT_TIMER = object()
    wx.ICON_INFORMATION = 0
    wx.mouse = Point(0, 0)
    wx.GetMousePosition = lambda: wx.mouse
    wx.CallAfter = lambda fn, *a, **k: fn(*a, **k)
    adv.TaskBarIcon = type("TaskBarIcon", (), {"__init__": lambda self: None})
    adv.NotificationMessage = type("NotificationMessage", (), {"Timeout_Auto": -1})
    adv.EVT_TASKBAR_LEFT_DOWN = adv.EVT_TASKBAR_MOVE = object()
    wx.adv, wx.svg = adv, svg

    def unknown(name: str):
        """Any other wx name the modules touch at import time becomes an inert class."""
        item = type(name, (), {"__init__": lambda self, *a, **k: None})
        setattr(wx, name, item)
        return item

    wx.__getattr__ = unknown
    sys.modules.update({"wx": wx, "wx.adv": adv, "wx.svg": svg})
