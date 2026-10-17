"""Custom-drawn controls for the settings and about dialogs.

Native Windows controls cannot be restyled, so the few the dialog needs are
drawn here with ``wx.GraphicsContext``: toggle switch, slider, flat button,
color swatch, stepper, dropdown (with its popup list), plus the rounded card
and the battery summary card. Each control mimics the wx control it replaces
(same getters and setters, same command event types), so the dialog logic can
keep binding ``wx.EVT_CHECKBOX``, ``wx.EVT_SLIDER`` and ``wx.EVT_COMBOBOX``.

Palette: Fluent Dark by default; call :func:`apply_theme` for light mode.
"""

from __future__ import annotations

import ctypes
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass

import wx

from .info import BatteryInfo


@dataclass(frozen=True)
class _Palette:
    BG: tuple[int, int, int]
    CARD: tuple[int, int, int]
    CARD_LINE: tuple[int, int, int]
    FIELD: tuple[int, int, int]
    FIELD_HOT: tuple[int, int, int]
    FIELD_LINE: tuple[int, int, int]
    TRACK: tuple[int, int, int]
    TEXT: tuple[int, int, int]
    MUTED: tuple[int, int, int]
    ACCENT: tuple[int, int, int]
    ON_ACCENT: tuple[int, int, int]
    OFF: tuple[int, int, int]
    WARN: tuple[int, int, int]
    LOW: tuple[int, int, int]


_DARK = _Palette(
    BG=(32, 32, 32),
    CARD=(43, 43, 43),
    CARD_LINE=(64, 64, 64),
    FIELD=(56, 56, 56),
    FIELD_HOT=(68, 68, 68),
    FIELD_LINE=(76, 76, 76),
    TRACK=(26, 26, 26),
    TEXT=(243, 243, 243),
    MUTED=(163, 163, 163),
    ACCENT=(96, 205, 255),
    ON_ACCENT=(0, 18, 28),
    OFF=(88, 88, 88),
    WARN=(255, 214, 0),
    LOW=(255, 70, 70),
)

_LIGHT = _Palette(
    BG=(243, 243, 243),
    CARD=(255, 255, 255),
    CARD_LINE=(220, 220, 220),
    FIELD=(245, 245, 245),
    FIELD_HOT=(235, 235, 235),
    FIELD_LINE=(200, 200, 200),
    TRACK=(220, 220, 220),
    TEXT=(28, 28, 28),
    MUTED=(110, 110, 110),
    ACCENT=(0, 120, 212),
    ON_ACCENT=(255, 255, 255),
    OFF=(180, 180, 180),
    WARN=(200, 150, 0),
    LOW=(200, 40, 40),
)

# Active palette colours (mutated by apply_theme; drawn controls read these).
BG = wx.Colour(*_DARK.BG)
CARD = wx.Colour(*_DARK.CARD)
CARD_LINE = wx.Colour(*_DARK.CARD_LINE)
FIELD = wx.Colour(*_DARK.FIELD)
FIELD_HOT = wx.Colour(*_DARK.FIELD_HOT)
FIELD_LINE = wx.Colour(*_DARK.FIELD_LINE)
TRACK = wx.Colour(*_DARK.TRACK)
TEXT = wx.Colour(*_DARK.TEXT)
MUTED = wx.Colour(*_DARK.MUTED)
ACCENT = wx.Colour(*_DARK.ACCENT)
ON_ACCENT = wx.Colour(*_DARK.ON_ACCENT)
OFF = wx.Colour(*_DARK.OFF)
WARN = wx.Colour(*_DARK.WARN)
LOW = wx.Colour(*_DARK.LOW)

_dark_active = True

_CARD_RADIUS = 10
#: Context-menu corner radius — smaller than cards so the tray popup does not
#: look pixelated on a 100% DPI taskbar.
_MENU_RADIUS = 4
_ROW_HEIGHT = 26


def apply_theme(dark: bool) -> None:
    """Switch the module palette between Fluent Dark and a light counterpart."""
    global BG, CARD, CARD_LINE, FIELD, FIELD_HOT, FIELD_LINE, TRACK
    global TEXT, MUTED, ACCENT, ON_ACCENT, OFF, WARN, LOW, _dark_active
    palette = _DARK if dark else _LIGHT
    BG = wx.Colour(*palette.BG)
    CARD = wx.Colour(*palette.CARD)
    CARD_LINE = wx.Colour(*palette.CARD_LINE)
    FIELD = wx.Colour(*palette.FIELD)
    FIELD_HOT = wx.Colour(*palette.FIELD_HOT)
    FIELD_LINE = wx.Colour(*palette.FIELD_LINE)
    TRACK = wx.Colour(*palette.TRACK)
    TEXT = wx.Colour(*palette.TEXT)
    MUTED = wx.Colour(*palette.MUTED)
    ACCENT = wx.Colour(*palette.ACCENT)
    ON_ACCENT = wx.Colour(*palette.ON_ACCENT)
    OFF = wx.Colour(*palette.OFF)
    WARN = wx.Colour(*palette.WARN)
    LOW = wx.Colour(*palette.LOW)
    _dark_active = dark


def is_dark_theme() -> bool:
    """Whether the active palette is the dark one."""
    return _dark_active


def use_dark_titlebar(window: wx.Window, dark: bool | None = None) -> None:
    """Ask Windows 10/11 for a dark (or light) title bar; skipped where unsupported."""
    try:
        value = ctypes.c_int(1 if (is_dark_theme() if dark is None else dark) else 0)
        for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (20; 19 on early builds)
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                window.GetHandle(), attribute, ctypes.byref(value), ctypes.sizeof(value)
            )
            if result == 0:
                break
    except (AttributeError, OSError):
        pass


def text(
    parent: wx.Window, label: str, *, muted: bool = False, small: bool = False, bold: bool = False
) -> wx.StaticText:
    """A static text in the dialog's colors, on the card background."""
    item = wx.StaticText(parent, label=label)
    item.SetBackgroundColour(CARD)
    item.SetForegroundColour(MUTED if muted else TEXT)
    # Stash role so refresh_theme can recolour without rebuilding the dialog.
    item._theme_role = "muted" if muted else "text"  # type: ignore[attr-defined]
    font = item.GetFont()
    if small:
        font = font.Smaller()
    if bold:
        font = font.Bold()
    item.SetFont(font)
    return item


def refresh_theme(window: wx.Window) -> None:
    """Re-apply the active palette to an open dialog and all of its children.

    Painted controls read the module colours on every paint; StaticText and
    panel backgrounds are updated here. Call after :func:`apply_theme`.
    """
    if isinstance(window, wx.TopLevelWindow):
        window.SetBackgroundColour(BG)
        use_dark_titlebar(window)
    elif isinstance(window, wx.Panel) and not isinstance(window, _Painted):
        # Cards and plain panels sit on BG; their face is CARD.
        window.SetBackgroundColour(CARD)

    if isinstance(window, wx.StaticText):
        role = getattr(window, "_theme_role", "text")
        window.SetBackgroundColour(CARD)
        window.SetForegroundColour(MUTED if role == "muted" else TEXT)
    else:
        # HyperlinkCtrl lives in wx.adv; avoid a hard import dependency here.
        with suppress(AttributeError, TypeError):
            if window.__class__.__name__ == "HyperlinkCtrl":
                window.SetBackgroundColour(CARD)
                window.SetNormalColour(ACCENT)
                window.SetHoverColour(ACCENT)
                window.SetVisitedColour(ACCENT)

    for child in window.GetChildren():
        refresh_theme(child)
    window.Refresh()


def _thin_pen(gc: wx.GraphicsContext, colour: wx.Colour, width: float) -> wx.GraphicsPen:
    """A pen with a fractional width (``wx.Pen`` only takes whole numbers)."""
    return gc.CreatePen(wx.GraphicsPenInfo(colour, width))


def _emit(control: wx.Control, event_type: int, value: int = 0, string: str = "") -> None:
    """Send a command event of ``event_type`` from ``control`` up the window chain."""
    event = wx.CommandEvent(event_type, control.GetId())
    event.SetEventObject(control)
    event.SetInt(int(value))
    event.SetString(string)
    control.GetEventHandler().ProcessEvent(event)


class _Painted(wx.Control):
    """Base: a control that paints itself with a GraphicsContext and tracks hover/focus."""

    def __init__(self, parent: wx.Window, size: tuple[int, int], *, on_dialog_bg: bool = False):
        super().__init__(parent, style=wx.BORDER_NONE)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        # Clear with the live palette each paint — a frozen Colour captured at
        # import time would stay dark after apply_theme switches to light.
        self._on_dialog_bg = on_dialog_bg
        self._hover = False
        self.SetInitialSize(self.FromDIP(wx.Size(*size)))
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_ENTER_WINDOW, lambda _e: self._set_hover(True))
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda _e: self._set_hover(False))
        self.Bind(wx.EVT_SET_FOCUS, lambda _e: self.Refresh())
        self.Bind(wx.EVT_KILL_FOCUS, lambda _e: self.Refresh())

    def _set_hover(self, hover: bool) -> None:
        self._hover = hover
        self.Refresh()

    def _on_paint(self, _evt: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(BG if self._on_dialog_bg else CARD))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        if gc is not None:
            width, height = self.GetClientSize()
            self.draw(gc, width, height)

    def draw(self, gc: wx.GraphicsContext, width: int, height: int) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    def _focus_ring(self, gc: wx.GraphicsContext, width: int, height: int, radius: float) -> None:
        if self.HasFocus():
            gc.SetPen(wx.Pen(ACCENT, 1))
            gc.SetBrush(wx.TRANSPARENT_BRUSH)
            gc.DrawRoundedRectangle(0.5, 0.5, width - 1, height - 1, radius)

    def _draw_text(  # noqa: PLR0913, PLR0917 -- a drawing helper, every argument is a coordinate or style
        self, gc: wx.GraphicsContext, label: str, x: float, width: float, height: float,
        colour: wx.Colour = TEXT, font: wx.Font | None = None, align: str = "left",
    ) -> None:
        gc.SetFont(font or self.GetFont(), colour)
        extent = gc.GetTextExtent(label)
        text_w, text_h = extent[0], extent[1]
        left = x if align == "left" else x + (width - text_w) / 2
        gc.DrawText(label, left, (height - text_h) / 2)


class Toggle(_Painted):
    """On/off switch (replaces ``wx.CheckBox``; emits ``wx.EVT_CHECKBOX``)."""

    def __init__(self, parent: wx.Window, value: bool = False):
        super().__init__(parent, (42, 22))
        self._value = value
        # LEFT_DCLICK too: a second click within the system double-click interval
        # arrives as DCLICK instead of DOWN, so rapid toggles would otherwise miss.
        self.Bind(wx.EVT_LEFT_DOWN, lambda _e: self._toggle())
        self.Bind(wx.EVT_LEFT_DCLICK, lambda _e: self._toggle())
        self.Bind(wx.EVT_KEY_DOWN, self._on_key)

    def GetValue(self) -> bool:  # noqa: N802 (wx-style API)
        return self._value

    def SetValue(self, value: bool) -> None:  # noqa: N802
        self._value = bool(value)
        self.Refresh()

    def _toggle(self) -> None:
        self.SetFocus()
        self._value = not self._value
        self.Refresh()
        _emit(self, wx.wxEVT_CHECKBOX, int(self._value))

    def _on_key(self, evt: wx.KeyEvent) -> None:
        if evt.GetKeyCode() == wx.WXK_SPACE:
            self._toggle()
        else:
            evt.Skip()

    def draw(self, gc: wx.GraphicsContext, width: int, height: int) -> None:
        # Leave a 1px transparent margin so the rounded track does not clip
        # against the control edge (black corners on a light card).
        track = ACCENT if self._value else (FIELD_HOT if self._hover else OFF)
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.SetBrush(wx.Brush(track))
        gc.DrawRoundedRectangle(1, 1, width - 2, height - 2, (height - 2) / 2)
        knob = height - 8
        left = width - 4 - knob if self._value else 4
        # On: accent-contrast knob; off: white on both themes (reads on dark and light tracks).
        knob_fill = ON_ACCENT if self._value else wx.Colour(255, 255, 255)
        gc.SetBrush(wx.Brush(knob_fill))
        gc.DrawEllipse(left, 4, knob, knob)


class Slider(_Painted):
    """Horizontal slider (replaces ``wx.Slider``; emits ``wx.EVT_SLIDER``)."""

    def __init__(self, parent: wx.Window, minimum: int, maximum: int, value: int, width: int = 150):
        super().__init__(parent, (width, 22))
        self._min, self._max = minimum, maximum
        self._value = min(maximum, max(minimum, value))
        self._dragging = False
        self.Bind(wx.EVT_LEFT_DOWN, self._on_down)
        self.Bind(wx.EVT_LEFT_UP, self._on_up)
        self.Bind(wx.EVT_MOTION, self._on_move)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, lambda _e: self._end_drag())
        self.Bind(wx.EVT_KEY_DOWN, self._on_key)

    def GetValue(self) -> int:  # noqa: N802
        return self._value

    def SetValue(self, value: int) -> None:  # noqa: N802
        self._value = min(self._max, max(self._min, int(value)))
        self.Refresh()

    def _set_from_x(self, x: int) -> None:
        pad = self.FromDIP(8)
        span = max(1, self.GetClientSize().width - 2 * pad)
        ratio = min(1.0, max(0.0, (x - pad) / span))
        self._change(round(self._min + ratio * (self._max - self._min)))

    def _change(self, value: int) -> None:
        value = min(self._max, max(self._min, value))
        if value != self._value:
            self._value = value
            self.Refresh()
            _emit(self, wx.wxEVT_SLIDER, value)

    def _on_down(self, evt: wx.MouseEvent) -> None:
        self.SetFocus()
        self._dragging = True
        if not self.HasCapture():
            self.CaptureMouse()
        self._set_from_x(evt.GetX())

    def _on_move(self, evt: wx.MouseEvent) -> None:
        if self._dragging and evt.LeftIsDown():
            self._set_from_x(evt.GetX())

    def _on_up(self, _evt: wx.MouseEvent) -> None:
        self._end_drag()

    def _end_drag(self) -> None:
        self._dragging = False
        if self.HasCapture():
            self.ReleaseMouse()

    def _on_key(self, evt: wx.KeyEvent) -> None:
        steps = {
            wx.WXK_LEFT: -1, wx.WXK_DOWN: -1, wx.WXK_RIGHT: 1, wx.WXK_UP: 1,
            wx.WXK_PAGEDOWN: -10, wx.WXK_PAGEUP: 10,
        }
        step = steps.get(evt.GetKeyCode())
        if step is None:
            evt.Skip()
        else:
            self._change(self._value + step)

    def draw(self, gc: wx.GraphicsContext, width: int, height: int) -> None:
        pad = self.FromDIP(8)
        span = width - 2 * pad
        ratio = (self._value - self._min) / max(1, self._max - self._min)
        mid, track = height / 2, self.FromDIP(4)
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.SetBrush(wx.Brush(OFF))
        gc.DrawRoundedRectangle(pad, mid - track / 2, span, track, track / 2)
        gc.SetBrush(wx.Brush(ACCENT))
        gc.DrawRoundedRectangle(pad, mid - track / 2, span * ratio, track, track / 2)
        thumb = self.FromDIP(16)
        gc.SetBrush(wx.Brush(ACCENT))
        gc.DrawEllipse(pad + span * ratio - thumb / 2, mid - thumb / 2, thumb, thumb)
        self._focus_ring(gc, width, height, 6)


class FlatButton(_Painted):
    """Flat rounded button (replaces ``wx.Button``; emits ``wx.EVT_BUTTON``).

    ``variant``: ``"normal"``, ``"primary"`` (accent fill) or ``"ghost"`` (text only).
    """

    def __init__(self, parent: wx.Window, label: str, variant: str = "normal", button_id: int = wx.ID_ANY):
        super().__init__(parent, (60, 32), on_dialog_bg=True)
        if button_id != wx.ID_ANY:  # ID_OK / ID_CANCEL make the dialog's own handlers fire
            self.SetId(button_id)
        self._label, self._variant, self._pressed = label, variant, False
        text_w = self.GetTextExtent(label).width
        extra = 70 if variant == "primary" else 32
        self.SetInitialSize(wx.Size(text_w + self.FromDIP(extra), self.FromDIP(32)))
        self.Bind(wx.EVT_LEFT_DOWN, self._on_down)
        self.Bind(wx.EVT_LEFT_UP, self._on_up)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, lambda _e: self._release())
        self.Bind(wx.EVT_KEY_DOWN, self._on_key)

    def _release(self) -> None:
        self._pressed = False
        self.Refresh()

    def _on_down(self, _evt: wx.MouseEvent) -> None:
        self.SetFocus()
        self._pressed = True
        self.CaptureMouse()
        self.Refresh()

    def _on_up(self, evt: wx.MouseEvent) -> None:
        if self.HasCapture():
            self.ReleaseMouse()
        inside = self.GetClientRect().Contains(evt.GetPosition())
        was_pressed, self._pressed = self._pressed, False
        self.Refresh()
        if was_pressed and inside:
            _emit(self, wx.wxEVT_BUTTON)

    def _on_key(self, evt: wx.KeyEvent) -> None:
        if evt.GetKeyCode() in (wx.WXK_SPACE, wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            _emit(self, wx.wxEVT_BUTTON)
        else:
            evt.Skip()

    def draw(self, gc: wx.GraphicsContext, width: int, height: int) -> None:
        gc.SetPen(wx.TRANSPARENT_PEN)
        text_colour = TEXT
        if self._variant == "primary":
            gc.SetBrush(wx.Brush(ACCENT))
            text_colour = ON_ACCENT
        elif self._variant == "ghost":
            gc.SetBrush(wx.Brush(FIELD if self._hover else BG))
            text_colour = TEXT if self._hover else MUTED
        else:
            gc.SetPen(wx.Pen(FIELD_LINE, 1))
            gc.SetBrush(wx.Brush(FIELD_HOT if self._hover else FIELD))
        gc.DrawRoundedRectangle(0.5, 0.5, width - 1, height - 1, 6)
        font = self.GetFont().Bold() if self._variant == "primary" else self.GetFont()
        self._draw_text(gc, self._label, 0, width, height, text_colour, font, "center")
        self._focus_ring(gc, width, height, 6)


class Chip(_Painted):
    """Small toggle button (emits ``wx.EVT_CHECKBOX``)."""

    def __init__(self, parent: wx.Window, label: str, value: bool = False):
        super().__init__(parent, (60, 28))
        self._label, self._value = label, value
        self.SetInitialSize(wx.Size(self.GetTextExtent(label).width + self.FromDIP(22), self.FromDIP(28)))
        self.Bind(wx.EVT_LEFT_DOWN, lambda _e: self._toggle())
        self.Bind(wx.EVT_LEFT_DCLICK, lambda _e: self._toggle())
        self.Bind(wx.EVT_KEY_DOWN, self._on_key)

    def GetValue(self) -> bool:  # noqa: N802
        return self._value

    def SetValue(self, value: bool) -> None:  # noqa: N802
        self._value = bool(value)
        self.Refresh()

    def _toggle(self) -> None:
        self.SetFocus()
        self._value = not self._value
        self.Refresh()
        _emit(self, wx.wxEVT_CHECKBOX, int(self._value))

    def _on_key(self, evt: wx.KeyEvent) -> None:
        if evt.GetKeyCode() == wx.WXK_SPACE:
            self._toggle()
        else:
            evt.Skip()

    def draw(self, gc: wx.GraphicsContext, width: int, height: int) -> None:
        gc.SetPen(wx.Pen(ACCENT if self._value else FIELD_LINE, 1))
        gc.SetBrush(wx.Brush(FIELD_HOT if self._hover else FIELD))
        gc.DrawRoundedRectangle(0.5, 0.5, width - 1, height - 1, 6)
        font = self.GetFont().Smaller()
        self._draw_text(gc, self._label, 0, width, height, ACCENT if self._value else MUTED, font, "center")
        self._focus_ring(gc, width, height, 6)


class Swatch(_Painted):
    """A color chip that opens the color dialog (replaces ``wx.ColourPickerCtrl``)."""

    def __init__(self, parent: wx.Window, colour: wx.Colour, on_changed: Callable[[], None] | None = None):
        super().__init__(parent, (28, 22))
        self._colour = self._opaque(colour)
        self._on_changed = on_changed
        self.Bind(wx.EVT_LEFT_DOWN, lambda _e: self._pick())
        self.Bind(wx.EVT_LEFT_DCLICK, lambda _e: self._pick())
        self.Bind(wx.EVT_KEY_DOWN, self._on_key)

    @staticmethod
    def _opaque(colour: wx.Colour) -> wx.Colour:
        """Force an opaque RGB colour (native ColourDialog can return alpha=0)."""
        if not colour.IsOk():
            return wx.Colour(128, 128, 128)
        return wx.Colour(colour.Red(), colour.Green(), colour.Blue())

    def GetColour(self) -> wx.Colour:  # noqa: N802
        return self._colour

    def SetColour(self, colour: wx.Colour) -> None:  # noqa: N802
        self._colour = self._opaque(colour)
        self.Refresh()

    def _pick(self) -> None:
        self.SetFocus()
        data = wx.ColourData()
        data.SetChooseFull(True)
        data.SetColour(self._colour)
        # Parent the native dialog to None: a custom-painted dark dialog as
        # parent makes ColourDialog crash on some wxPython / Windows builds
        # (especially once the extra mid/low swatches are shown and focused).
        dialog = wx.ColourDialog(None, data)
        try:
            if dialog.ShowModal() == wx.ID_OK:
                self.SetColour(dialog.GetColourData().GetColour())
                if self._on_changed is not None:
                    self._on_changed()
        finally:
            dialog.Destroy()

    def _on_key(self, evt: wx.KeyEvent) -> None:
        if evt.GetKeyCode() in (wx.WXK_SPACE, wx.WXK_RETURN):
            self._pick()
        else:
            evt.Skip()

    def draw(self, gc: wx.GraphicsContext, width: int, height: int) -> None:
        gc.SetPen(wx.Pen(ACCENT if self._hover else FIELD_LINE, 1))
        gc.SetBrush(wx.Brush(self._colour))
        gc.DrawRoundedRectangle(0.5, 0.5, width - 1, height - 1, 5)
        self._focus_ring(gc, width, height, 5)


class Stepper(_Painted):
    """``-  60 s  +`` over a ladder of values (used for the poll interval)."""

    LADDER = (1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1800, 3600)

    def __init__(self, parent: wx.Window, value: int):
        super().__init__(parent, (120, 28))
        self._value = int(value)
        # LEFT_DCLICK: rapid clicks within the system double-click interval land
        # as DCLICK, not a second DOWN — without this the step is skipped.
        self.Bind(wx.EVT_LEFT_DOWN, self._on_down)
        self.Bind(wx.EVT_LEFT_DCLICK, self._on_down)
        self.Bind(wx.EVT_KEY_DOWN, self._on_key)

    def GetValue(self) -> int:  # noqa: N802
        return self._value

    def SetValue(self, value: int) -> None:  # noqa: N802
        self._value = int(value)
        self.Refresh()

    def _step(self, direction: int) -> None:
        """Move to the next ladder value above/below the current one."""
        if direction > 0:
            self._value = next((v for v in self.LADDER if v > self._value), self.LADDER[-1])
        else:
            self._value = next((v for v in reversed(self.LADDER) if v < self._value), self.LADDER[0])
        self.Refresh()

    def _on_down(self, evt: wx.MouseEvent) -> None:
        self.SetFocus()
        width = self.GetClientSize().width
        if evt.GetX() < width / 3:
            self._step(-1)
        elif evt.GetX() > width * 2 / 3:
            self._step(1)

    def _on_key(self, evt: wx.KeyEvent) -> None:
        code = evt.GetKeyCode()
        if code in (wx.WXK_LEFT, wx.WXK_DOWN):
            self._step(-1)
        elif code in (wx.WXK_RIGHT, wx.WXK_UP):
            self._step(1)
        else:
            evt.Skip()

    def draw(self, gc: wx.GraphicsContext, width: int, height: int) -> None:
        gc.SetPen(wx.Pen(FIELD_LINE, 1))
        gc.SetBrush(wx.Brush(FIELD))
        gc.DrawRoundedRectangle(0.5, 0.5, width - 1, height - 1, 6)
        third = width / 3
        self._draw_text(gc, "\u2212", 0, third, height, MUTED, align="center")
        self._draw_text(gc, "+", width - third, third, height, MUTED, align="center")
        self._draw_text(gc, f"{self._value} s", third, third, height, TEXT, align="center")
        self._focus_ring(gc, width, height, 6)


class _ItemList(wx.VListBox):
    """The dropdown's list; each item is drawn in the face it names."""

    def __init__(self, parent: wx.Window, items: list[str], item_font: Callable[[str], wx.Font]):
        super().__init__(parent, style=wx.BORDER_NONE)
        self._items, self._item_font = items, item_font
        self.SetItemCount(len(items))

    def OnMeasureItem(self, _n: int) -> int:  # noqa: N802 (wx override)
        return self.FromDIP(_ROW_HEIGHT)

    def OnDrawBackground(self, dc: wx.DC, rect: wx.Rect, n: int) -> None:  # noqa: N802
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(FIELD_HOT if self.IsSelected(n) else FIELD))
        dc.DrawRectangle(rect)

    def OnDrawItem(self, dc: wx.DC, rect: wx.Rect, n: int) -> None:  # noqa: N802
        dc.SetFont(self._item_font(self._items[n]))
        dc.SetTextForeground(ACCENT if self.IsSelected(n) else TEXT)
        dc.DrawText(self._items[n], rect.x + 10, rect.y + (rect.height - dc.GetCharHeight()) // 2)


class _Popup(wx.PopupTransientWindow):
    def __init__(  # noqa: PLR0913, PLR0917 -- all six describe one popup list
        self, parent: wx.Window, items: list[str], selected: int, width: int,
        on_pick: Callable[[str], None], item_font: Callable[[str], wx.Font],
    ):
        super().__init__(parent, wx.BORDER_SIMPLE)
        self.SetBackgroundColour(FIELD)
        self._on_pick = on_pick
        self._list = _ItemList(self, items, item_font)
        rows = max(1, min(len(items), 8))
        height = rows * self.FromDIP(_ROW_HEIGHT)
        self.SetClientSize(wx.Size(width, height))
        self._list.SetSize(wx.Size(width, height))
        if 0 <= selected < len(items):
            self._list.SetSelection(selected)
            self._list.ScrollToRow(max(0, selected - 3))
        self._list.Bind(wx.EVT_LISTBOX, self._on_select)

    def _on_select(self, evt: wx.CommandEvent) -> None:
        index = evt.GetSelection()
        if index != wx.NOT_FOUND:
            self._on_pick(self._list._items[index])
        self.Dismiss()

    def OnDismiss(self) -> None:  # noqa: N802 (wx override)
        wx.CallAfter(self.Destroy)


class Dropdown(_Painted):
    """Read-only dropdown (replaces the owner-drawn combo; emits ``wx.EVT_COMBOBOX``)."""

    def __init__(self, parent: wx.Window, items: list[str], width: int = 160, preview_faces: bool = True):
        super().__init__(parent, (width, 28))
        self._items, self._selected = list(items), ""
        self._preview_faces = preview_faces
        self.Bind(wx.EVT_LEFT_DOWN, lambda _e: self._open())
        self.Bind(wx.EVT_LEFT_DCLICK, lambda _e: self._open())
        self.Bind(wx.EVT_KEY_DOWN, self._on_key)

    def set_faces(self, faces: list[str]) -> None:
        self._items = list(faces)
        self.Refresh()

    def GetStringSelection(self) -> str:  # noqa: N802
        return self._selected

    def clear_selection(self) -> None:
        self._selected = ""
        self.Refresh()

    def SetStringSelection(self, value: str) -> bool:  # noqa: N802
        if value in self._items:
            self._selected = value
            self.Refresh()
            return True
        return False

    def _font_for(self, face: str) -> wx.Font:
        base = self.GetFont()
        if not self._preview_faces:
            return base
        return wx.Font(
            base.GetPointSize() + 1, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL,
            faceName=face,
        )

    def _open(self) -> None:
        self.SetFocus()
        if not self._items:
            return
        index = self._items.index(self._selected) if self._selected in self._items else -1
        popup = _Popup(self.GetTopLevelParent(), self._items, index, self.GetSize().width + self.FromDIP(40),
                       self._pick, self._font_for)
        popup.Position(self.ClientToScreen((0, self.GetSize().height + 2)), (0, 0))
        popup.Popup()

    def _on_key(self, evt: wx.KeyEvent) -> None:
        if evt.GetKeyCode() in (wx.WXK_SPACE, wx.WXK_RETURN, wx.WXK_DOWN):
            self._open()
        else:
            evt.Skip()

    def _pick(self, face: str) -> None:
        self._selected = face
        self.Refresh()
        _emit(self, wx.wxEVT_COMBOBOX, 0, face)

    def draw(self, gc: wx.GraphicsContext, width: int, height: int) -> None:
        gc.SetPen(wx.Pen(FIELD_LINE, 1))
        gc.SetBrush(wx.Brush(FIELD_HOT if self._hover else FIELD))
        gc.DrawRoundedRectangle(0.5, 0.5, width - 1, height - 1, 6)
        pad = self.FromDIP(10)
        gc.Clip(pad, 0, width - 2 * pad - self.FromDIP(16), height)
        shown_font = self._font_for(self._selected) if self._selected else None
        self._draw_text(gc, self._selected, pad, width, height, TEXT, shown_font)
        gc.ResetClip()
        x, y = width - self.FromDIP(16), height / 2  # chevron
        gc.SetPen(_thin_pen(gc, MUTED, 1.5))
        path = gc.CreatePath()
        path.MoveToPoint(x - 4, y - 2)
        path.AddLineToPoint(x, y + 2)
        path.AddLineToPoint(x + 4, y - 2)
        gc.StrokePath(path)
        self._focus_ring(gc, width, height, 6)


class Card(wx.Panel):
    """A rounded panel; rows are added to its sizer by the dialog."""

    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetBackgroundColour(CARD)
        self.Bind(wx.EVT_PAINT, self._on_paint)

    def _on_paint(self, _evt: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(BG))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        width, height = self.GetClientSize()
        gc.SetPen(wx.Pen(CARD_LINE, 1))
        gc.SetBrush(wx.Brush(CARD))
        gc.DrawRoundedRectangle(0.5, 0.5, width - 1, height - 1, self.FromDIP(_CARD_RADIUS))


class BatteryCard(_Painted):
    """Top card: charge bar with percent, a mouse glyph and two info lines."""

    def __init__(self, parent: wx.Window, info: BatteryInfo):
        super().__init__(parent, (400, 96), on_dialog_bg=True)
        self._info = info

    def draw(self, gc: wx.GraphicsContext, width: int, height: int) -> None:
        pad = self.FromDIP(14)
        gc.SetPen(wx.Pen(CARD_LINE, 1))
        gc.SetBrush(wx.Brush(CARD))
        gc.DrawRoundedRectangle(0.5, 0.5, width - 1, height - 1, self.FromDIP(_CARD_RADIUS))
        base = self.GetFont()
        gc.SetFont(base.Bold(), TEXT)
        gc.DrawText("Battery", pad, self.FromDIP(10))

        percent = self._info.percent
        bar_y, bar_h = self.FromDIP(40), self.FromDIP(8)
        right = width - pad - self.FromDIP(18)  # room for the mouse glyph
        pct_w = self.FromDIP(54)
        bar_w = right - pct_w - pad
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.SetBrush(wx.Brush(TRACK))
        gc.DrawRoundedRectangle(pad, bar_y, bar_w, bar_h, bar_h / 2)
        if percent is not None:
            fill = LOW if percent <= 20 else WARN if percent <= 50 else ACCENT
            gc.SetBrush(wx.Brush(fill))
            gc.DrawRoundedRectangle(pad, bar_y, max(bar_h, bar_w * percent / 100), bar_h, bar_h / 2)
        gc.SetFont(base.Scaled(1.35).Bold(), TEXT)
        label = "--%" if percent is None else f"{percent}%"
        extent = gc.GetTextExtent(label)
        gc.DrawText(label, right - extent[0], bar_y + bar_h / 2 - extent[1] / 2)

        # mouse glyph
        gx, gy = right + self.FromDIP(6), bar_y + bar_h / 2 - self.FromDIP(9)
        gw, gh = self.FromDIP(11), self.FromDIP(18)
        gc.SetPen(_thin_pen(gc, MUTED, 1.5))
        gc.SetBrush(wx.TRANSPARENT_BRUSH)
        gc.DrawRoundedRectangle(gx, gy, gw, gh, gw / 2)
        gc.StrokeLine(gx + gw / 2, gy, gx + gw / 2, gy + gh * 0.4)

        gc.SetFont(base.Smaller(), MUTED)
        gc.DrawText(self._info.headline, pad, self.FromDIP(62))
        if self._info.detail:
            extent = gc.GetTextExtent(self._info.detail)
            gc.DrawText(self._info.detail, width - pad - extent[0], self.FromDIP(62))


class TrayMenu(wx.PopupTransientWindow):
    """The tray icon's context menu: a dark, rounded popup replacing ``wx.Menu``.

    ``entries`` is a list of ``(label, callback)``; ``None`` is a separator. A
    click closes the menu and then runs the callback. Outside clicks close it
    too (the popup captures the mouse; a short timer backs that up, because a
    tray app has no active window and Windows does not always deliver the
    outside click).
    """

    WIDTH = 224

    def __init__(
        self,
        parent: wx.Window,
        entries: list[tuple[str, Callable[[], None]] | None],
        on_closed: Callable[[], None] | None = None,
    ):
        # FRAME_SHAPED is required by SetShape (wx asserts without it).
        super().__init__(parent, wx.BORDER_NONE | wx.FRAME_SHAPED)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self._entries = entries
        self._on_closed = on_closed
        self._closed = False
        self._hot = -1
        pad, row, sep = self.FromDIP(6), self.FromDIP(34), self.FromDIP(11)
        self._rects: list[wx.Rect] = []
        y = pad
        width = self.FromDIP(self.WIDTH)
        for entry in entries:
            height = sep if entry is None else row
            self._rects.append(wx.Rect(pad, y, width - 2 * pad, height))
            y += height
        self.SetClientSize(wx.Size(width, y + pad))
        self._round_corners()
        self._timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_timer, self._timer)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_MOTION, self._on_motion)
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda _e: self._set_hot(-1))
        self.Bind(wx.EVT_LEFT_UP, self._on_click)
        self.Bind(wx.EVT_KEY_DOWN, self._on_key)

    def _round_corners(self) -> None:
        try:
            width, height = self.GetClientSize()
            path = wx.GraphicsRenderer.GetDefaultRenderer().CreatePath()
            path.AddRoundedRectangle(0, 0, width, height, self.FromDIP(_MENU_RADIUS))
            self.SetShape(path)
        except (AttributeError, NotImplementedError, AssertionError):
            pass  # square corners are fine (wx reports a refused shape as an assertion)

    def show_at(self, cursor: wx.Point) -> None:
        """Open with the menu's bottom-right corner at the cursor, kept on screen."""
        size = self.GetSize()
        area = wx.Display(max(0, wx.Display.GetFromPoint(cursor))).GetClientArea()
        x = min(max(area.x, cursor.x - size.width), area.right - size.width)
        y = min(max(area.y, cursor.y - size.height - self.FromDIP(6)), area.bottom - size.height)
        self.SetPosition(wx.Point(x, y))
        self.Popup()
        self._timer.Start(60)
        # Lets Windows route the outside click / Esc to this window.
        with suppress(AttributeError, OSError):
            ctypes.windll.user32.SetForegroundWindow(self.GetHandle())

    def _set_hot(self, index: int) -> None:
        if index != self._hot:
            self._hot = index
            self.Refresh()

    def _index_at(self, point: wx.Point) -> int:
        for index, (entry, rect) in enumerate(zip(self._entries, self._rects, strict=True)):
            if entry is not None and rect.Contains(point):
                return index
        return -1

    def _on_motion(self, evt: wx.MouseEvent) -> None:
        self._set_hot(self._index_at(evt.GetPosition()))

    def _on_click(self, evt: wx.MouseEvent) -> None:
        index = self._index_at(evt.GetPosition())
        entry = self._entries[index] if index >= 0 else None
        if entry is None:
            return
        self.Dismiss()
        wx.CallAfter(entry[1])

    def _on_key(self, evt: wx.KeyEvent) -> None:
        if evt.GetKeyCode() == wx.WXK_ESCAPE:
            self.Dismiss()
        else:
            evt.Skip()

    def _on_timer(self, _evt: wx.TimerEvent) -> None:
        state = wx.GetMouseState()
        pressed = state.LeftIsDown() or state.RightIsDown()
        if pressed and not self.GetScreenRect().Contains(state.GetPosition()):
            self.Dismiss()

    def OnDismiss(self) -> None:  # noqa: N802 (wx override)
        if self._closed:  # Dismiss can arrive twice (click + mouse capture)
            return
        self._closed = True
        self._timer.Stop()
        if self._on_closed is not None:
            self._on_closed()
        wx.CallAfter(self.Destroy)

    def _on_paint(self, _evt: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(BG))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        width, height = self.GetClientSize()
        radius = self.FromDIP(_MENU_RADIUS)
        gc.SetPen(wx.Pen(CARD_LINE, 1))
        gc.SetBrush(wx.Brush(CARD))
        gc.DrawRoundedRectangle(0.5, 0.5, width - 1, height - 1, radius)
        gc.SetFont(self.GetFont(), TEXT)
        for index, (entry, rect) in enumerate(zip(self._entries, self._rects, strict=True)):
            if entry is None:
                y = rect.y + rect.height / 2
                gc.SetPen(wx.Pen(CARD_LINE, 1))
                gc.StrokeLine(self.FromDIP(12), y, width - self.FromDIP(12), y)
                continue
            if index == self._hot:
                gc.SetPen(wx.TRANSPARENT_PEN)
                gc.SetBrush(wx.Brush(FIELD_HOT))
                gc.DrawRoundedRectangle(rect.x, rect.y, rect.width, rect.height, radius)
            extent = gc.GetTextExtent(entry[0])
            gc.SetFont(self.GetFont(), TEXT)
            gc.DrawText(entry[0], rect.x + self.FromDIP(12), rect.y + (rect.height - extent[1]) / 2)
