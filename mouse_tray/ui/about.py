"""About dialog: what the app is, what it does, and which device it supports.

The USB ids are read from the driver registry, so they are the ones detection
really uses. This module imports ``all_drivers`` only and never a driver module.
Styled with the same Fluent dark/light palette as the settings dialog.
"""

from __future__ import annotations

import wx
import wx.adv

from ..config import DESCRIPTION, HOMEPAGE, VERSION, Config
from ..drivers import all_drivers
from ..resources import icon_path
from . import widgets as w

#: What the app does, shown under the description. Kept in step with the
#: behavior in ``ui/app.py``.
_FEATURES = (
    "Shows the charge in the tray; the tooltip adds the report rate, DPI and the time "
    "since the last full charge.\n"
    "Hover the icon to see the report rate (125 ... 1K ... 8K) in the color of the "
    "mouse's own indicator.\n"
    "Portable: settings and the full-charge date are stored next to the program (a log "
    "only while Debug logging is on); "
    "the only registry entry is the optional \"Start with Windows\" value.\n"
    "Works without Bloody Central running."
)
_ICON_SIZE = 48
_TEXT_WIDTH = 420


def open_about(parent: wx.Window, config: Config) -> None:
    """Show the modal about dialog."""
    w.apply_theme(config.dark_theme)
    dialog = _AboutDialog(parent, config)
    try:
        dialog.ShowModal()
    finally:
        dialog.Destroy()
        wx.CallAfter(_release_after_close)


def _release_after_close() -> None:
    from .memory import release_ui_memory

    release_ui_memory()


def supported_devices() -> list[str]:
    """One line per supported model, with the USB ids it is found under.

    The ids use the form Windows shows as ``VID_1956&PID_3069``, so a line can be
    checked against Device Manager without conversion.
    """
    return [
        f"{m.name}: dongle {m.vid:04X}:{m.pid_wireless:04X}, cable {m.vid:04X}:{m.pid_wired:04X}"
        for driver_cls in all_drivers()
        for m in driver_cls.models
    ]


class _AboutDialog(wx.Dialog):
    def __init__(self, parent: wx.Window, config: Config):
        super().__init__(parent, title=f"About {config.display_name}")
        self.SetIcon(wx.Icon(icon_path("app.ico")))
        self.SetBackgroundColour(w.BG)
        w.use_dark_titlebar(self)

        pad = self.FromDIP(14)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(self._header_card(config), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, pad)
        outer.Add(self._body_card(), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, pad)
        outer.Add(self._footer(), 0, wx.EXPAND | wx.ALL, pad)
        outer.SetMinSize(wx.Size(self.FromDIP(470), -1))
        self.SetSizerAndFit(outer)
        self.SetMinSize(self.GetSize())
        self.CentreOnScreen()
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)

    def _header_card(self, config: Config) -> w.Card:
        card = w.Card(self)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        card.SetSizer(sizer)

        size = self.FromDIP(_ICON_SIZE)
        image = wx.Image(icon_path("app.ico"), wx.BITMAP_TYPE_ICO)
        image.Rescale(size, size, wx.IMAGE_QUALITY_HIGH)
        sizer.Add(wx.StaticBitmap(card, bitmap=wx.Bitmap(image)), 0, wx.ALIGN_TOP | wx.ALL, pad := self.FromDIP(14))

        title = w.text(card, f"{config.display_name} {VERSION}", bold=True)
        font = title.GetFont()
        font.SetPointSize(font.GetPointSize() + 2)
        title.SetFont(font)

        description = w.text(card, DESCRIPTION, muted=True)
        description.Wrap(self.FromDIP(360))

        link = wx.adv.HyperlinkCtrl(card, label="Based on Fan4Metal/mouse_tray (GitHub)", url=HOMEPAGE)
        link.SetBackgroundColour(w.CARD)
        link.SetNormalColour(w.ACCENT)
        link.SetHoverColour(w.ACCENT)
        link.SetVisitedColour(w.ACCENT)

        column = wx.BoxSizer(wx.VERTICAL)
        column.Add(title, 0)
        column.Add(description, 0, wx.TOP, self.FromDIP(6))
        column.Add(link, 0, wx.TOP, self.FromDIP(8))
        sizer.Add(column, 1, wx.EXPAND | wx.TOP | wx.RIGHT | wx.BOTTOM, pad)
        return card

    def _body_card(self) -> w.Card:
        card = w.Card(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        card.SetSizer(sizer)
        pad = self.FromDIP(14)

        features = w.text(card, _FEATURES)
        features.Wrap(self.FromDIP(_TEXT_WIDTH))
        sizer.Add(features, 0, wx.LEFT | wx.RIGHT | wx.TOP, pad)

        devices = supported_devices()
        title = "Supported device:" if len(devices) == 1 else "Supported devices:"
        sizer.Add(w.text(card, title, bold=True), 0, wx.LEFT | wx.RIGHT | wx.TOP, pad)
        for line in devices:
            sizer.Add(w.text(card, line, muted=True, small=True), 0, wx.LEFT | wx.RIGHT | wx.TOP, self.FromDIP(4))
        sizer.AddSpacer(pad)
        return card

    def _footer(self) -> wx.Sizer:
        footer = wx.BoxSizer(wx.HORIZONTAL)
        footer.AddStretchSpacer()
        footer.Add(w.FlatButton(self, "OK", "primary", wx.ID_OK), 0)
        return footer

    def _on_key(self, evt: wx.KeyEvent) -> None:
        if evt.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_OK)
        else:
            evt.Skip()
