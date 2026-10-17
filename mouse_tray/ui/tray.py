"""The system-tray icon; its context menu is :class:`~mouse_tray.ui.widgets.TrayMenu`."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import wx
from wx.adv import TaskBarIcon
from ..i18n import tr


class TrayIcon(TaskBarIcon):
    """Thin wrapper around ``TaskBarIcon`` that forwards events to callbacks.

    Keeping the UI widget free of app logic means the state machine in
    :mod:`mouse_tray.ui.app` owns all behavior; this class only draws the menu.

    ``widgets`` (settings controls + themed menu) is imported only on the first
    right-click so a pure-tray process does not pay for the dialog toolkit.
    """

    def __init__(  # noqa: PLR0913 -- one keyword-only callback per menu action
        self,
        parent: wx.Window,
        *,
        on_left_click: Callable[[], None],
        on_hover: Callable[[], None],
        on_reset_timer: Callable[[], None],
        on_settings: Callable[[], None],
        on_about: Callable[[], None],
        on_exit: Callable[[], None],
        dark_theme: bool = True,
        language: str = "en",
    ):
        super().__init__()
        self._parent = parent
        self._menu: Any = None
        self._dark_theme = dark_theme
        self._language = language
        self._on_left_click = on_left_click
        self._on_hover = on_hover
        self._on_reset_timer = on_reset_timer
        self._on_settings = on_settings
        self._on_about = on_about
        self._on_exit = on_exit
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, lambda _evt: self._on_left_click())
        # Windows sends a move message for every mouse move over the icon and
        # nothing when the cursor leaves; the app detects the "leave" itself.
        self.Bind(wx.adv.EVT_TASKBAR_MOVE, lambda _evt: self._on_hover())
        # Handled here (not skipped), so the native menu never opens.
        self.Bind(wx.adv.EVT_TASKBAR_RIGHT_UP, lambda _evt: self._show_menu())

    def set_dark_theme(self, dark: bool) -> None:
        """Keep the tray menu palette in sync with the settings choice."""
        self._dark_theme = dark

    def set_language(self, language: str) -> None:
        self._language = language

    def _show_menu(self) -> None:
        """Open the themed context menu at the cursor (one at a time)."""
        # Deferred: widgets.py is only needed for the painted menu / dialogs.
        from . import widgets as w

        w.apply_theme(self._dark_theme)
        if self._menu is not None:
            try:
                if self._menu.IsShown():
                    return
            except RuntimeError:  # the closed menu was already destroyed
                pass
            self._menu = None
        self._menu = w.TrayMenu(
            self._parent,
            [
                (tr("Reset timer", self._language), self._on_reset_timer),
                (tr("Settings...", self._language), self._on_settings),
                (tr("About...", self._language), self._on_about),
                None,
                (tr("Exit", self._language), self._on_exit),
            ],
            on_closed=self._menu_closed,
        )
        self._menu.show_at(wx.GetMousePosition())

    def _menu_closed(self) -> None:
        self._menu = None
        # Menu Destroy is itself deferred; trim after that lands.
        wx.CallAfter(self._release_ui)

    @staticmethod
    def _release_ui() -> None:
        from .memory import release_ui_memory

        release_ui_memory()

    def update(self, icon: wx.Icon, tooltip: str) -> None:
        """Set the tray icon and hover tooltip (safe to call from any thread)."""
        wx.CallAfter(self.SetIcon, icon, tooltip)

