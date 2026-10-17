"""Settings dialog: edit the user-tunable config (poll rate, font, color, debug).

Dark, card-based layout drawn with the controls in :mod:`mouse_tray.ui.widgets`:
a battery summary card on top, then "Appearance" and "System" cards.

The dialog only knows how to read/write a :class:`Config`; persisting the result
and refreshing the running tray is the caller's job (see ``app._open_settings``).

The font picker lists monospaced faces by default (the indicator wants
fixed-width digits) and previews each one in its own face; the "All fonts"
chip widens it to every installed face. Face names are resolved back to a
``.ttf``/``.otf`` file so PIL can load them. Every font, text-size, outline or
battery-icon change is also offered to the caller for a live tray repaint,
without waiting for OK.
"""

from __future__ import annotations

import os
import winreg
from collections.abc import Callable
from dataclasses import dataclass

import wx
from PIL import ImageFont

from .. import autostart
from ..config import LOW_THRESHOLD, MID_THRESHOLD, TEXT_SIZE_MAX, TEXT_SIZE_MIN, Config
from ..logging_setup import log_exists, open_log
from ..resources import icon_path
from . import widgets as w
from .info import BatteryInfo


@dataclass(frozen=True)
class PreviewHooks:
    """Callbacks the dialog fires so the caller can repaint the tray live.

    Each fires every time its control changes (and on "Reset to defaults");
    ``font`` receives the picked font file, or ``None`` when the selection
    clears. The caller must drop the previews once the dialog returns.
    """

    font: Callable[[str | None], None] | None = None
    size: Callable[[int], None] | None = None
    outline: Callable[[bool], None] | None = None
    battery_icon: Callable[[bool], None] | None = None
    # foreground, mid, low, dynamic_color — all four so the tray matches the
    # pickers without waiting for OK.
    colors: Callable[[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int], bool], None] | None = None


#: While a settings dialog is open, further open requests just raise it.
_open_dialog: wx.Dialog | None = None


def open_settings(
    parent: wx.Window,
    config: Config,
    preview: PreviewHooks | None = None,
    info: BatteryInfo | None = None,
) -> bool:
    """Show the modal settings dialog, centered on screen.

    On OK the edited values are written back onto ``config`` in place and
    ``True`` is returned; on Cancel nothing changes and ``False`` is returned.
    ``preview`` hooks, when given, repaint the tray live as the user edits
    (see :class:`PreviewHooks`); ``info`` feeds the battery card at the top.

    Only one settings dialog is allowed: a second open request raises the
    existing window instead of stacking another.
    """
    global _open_dialog
    if _open_dialog is not None:
        _open_dialog.Raise()
        _open_dialog.RequestUserAttention()
        return False

    w.apply_theme(config.dark_theme)
    dialog = _SettingsDialog(parent, config, preview or PreviewHooks(), info or BatteryInfo(None, "", ""))
    _open_dialog = dialog
    try:
        if dialog.ShowModal() != wx.ID_OK:
            # Live theme toggles changed the module palette; put it back.
            w.apply_theme(config.dark_theme)
            return False
        dialog.apply_to(config)
        w.apply_theme(config.dark_theme)
        return True
    finally:
        _open_dialog = None
        dialog.Destroy()
        # Defer so Destroy finishes before we drop the widgets module.
        wx.CallAfter(_release_after_close)


def _release_after_close() -> None:
    from .memory import release_ui_memory

    release_ui_memory()


def _font_files() -> dict[str, str]:
    """Map a lowercased font face name to its absolute font file (Windows).

    Built from the per-machine and per-user font registry keys. The regular
    weight of a family wins because its value name (e.g. ``"Consolas
    (TrueType)"``) strips to the bare face name, while ``"Consolas Bold"`` does
    not collide with it.
    """
    fonts_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    result: dict[str, str] = {}
    roots = (
        (winreg.HKEY_LOCAL_MACHINE, R"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
        (winreg.HKEY_CURRENT_USER, R"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
    )
    for hive, path in roots:
        try:
            key = winreg.OpenKey(hive, path)
        except OSError:
            continue
        with key:
            index = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, index)
                except OSError:
                    break
                index += 1
                if not value:
                    continue
                face = name.split(" (")[0].strip().lower()
                file = value if os.path.isabs(value) else os.path.join(fonts_dir, value)
                result.setdefault(face, file)
    return result


def _collect_faces() -> tuple[list[str], set[str], dict[str, str], dict[str, str]]:
    """Every installed face plus the lookups the picker and previews need.

    Returns the sorted face list, the lowercased monospaced faces, and the
    face-to-file / file-to-face maps (built from :func:`_font_files`).
    """
    file_map = _font_files()
    all_faces = sorted(
        face
        for face in wx.FontEnumerator.GetFacenames()
        if not face.startswith("@") and face.lower() in file_map
    )
    mono_faces = {
        face.lower()
        for face in wx.FontEnumerator.GetFacenames(fixedWidthOnly=True)
        if not face.startswith("@")
    }
    face_to_path = {face: file_map[face.lower()] for face in all_faces}
    path_to_face = {
        os.path.basename(path).lower(): face for face, path in face_to_path.items()
    }
    return all_faces, mono_faces, face_to_path, path_to_face


def _rgb(picker: w.Swatch) -> tuple[int, int, int]:
    colour = picker.GetColour()
    if not colour.IsOk():
        return (128, 128, 128)
    return (colour.Red(), colour.Green(), colour.Blue())


class _SettingsDialog(wx.Dialog):
    def __init__(self, parent: wx.Window, config: Config, preview: PreviewHooks, info: BatteryInfo):
        super().__init__(parent, title=f"{config.display_name} settings")
        self.SetIcon(wx.Icon(icon_path("app.ico")))
        self.SetBackgroundColour(w.BG)
        w.use_dark_titlebar(self)
        self._preview = preview
        self._all_faces, self._mono_faces, self._face_to_path, self._path_to_face = _collect_faces()

        pad = self.FromDIP(14)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(w.BatteryCard(self, info), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, pad)
        outer.Add(self._build_appearance(config), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, pad)
        outer.Add(self._build_system(config), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, pad)
        outer.Add(self._build_footer(), 0, wx.EXPAND | wx.ALL, pad)
        outer.SetMinSize(wx.Size(self.FromDIP(470), -1))
        self.SetSizerAndFit(outer)
        self.SetMinSize(self.GetSize())
        self.CentreOnScreen()

        self._restore_font_selection(config)
        # Hide after fitting: the dialog keeps the width of the shown state, so
        # toggling the switch never resizes the window under the cursor.
        self._update_bands()
        # Validate the chosen font before the OK button closes the dialog.
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)

    # --- building blocks ----------------------------------------------------

    def _card(self, title: str) -> tuple[w.Card, wx.BoxSizer]:
        """A rounded card with its title row; rows go into the returned sizer."""
        card = w.Card(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        card.SetSizer(sizer)
        sizer.Add(w.text(card, title, bold=True), 0, wx.ALL, self.FromDIP(14))
        return card, sizer

    def _row(
        self,
        card: w.Card,
        sizer: wx.BoxSizer,
        title: str,
        sub: str,
        *controls: wx.Window | wx.Sizer,
        tip: str | None = None,
    ) -> None:
        """One settings row: title and muted caption on the left, controls right."""
        left = wx.BoxSizer(wx.VERTICAL)
        title_text = w.text(card, title)
        left.Add(title_text, 0)
        if sub:
            left.Add(w.text(card, sub, muted=True, small=True), 0)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(left, 1, wx.ALIGN_CENTER_VERTICAL)
        for control in controls:
            row.Add(control, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, self.FromDIP(10))
        if tip:
            title_text.SetToolTip(tip)
            for control in controls:
                if isinstance(control, wx.Window):
                    control.SetToolTip(tip)
        sizer.Add(row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, self.FromDIP(14))

    def _toggle_row(  # noqa: PLR0913, PLR0917 -- one row = card, sizer, caption pair, value, tooltip
        self, card: w.Card, sizer: wx.BoxSizer, title: str, sub: str, value: bool, tip: str | None = None
    ) -> w.Toggle:
        toggle = w.Toggle(card, value)
        self._row(card, sizer, title, sub, toggle, tip=tip)
        return toggle

    def _build_appearance(self, config: Config) -> w.Card:
        card, sizer = self._card("Appearance")
        # Order: theme → indicator style → outline → charge colours → size → font.
        self._dark_theme = self._toggle_row(
            card, sizer, "Dark theme", "Settings and About dialogs", config.dark_theme,
            "Dark Fluent look for the settings and about windows.\n"
            "Turn off for a light palette. Switches this dialog live;\n"
            "saved when you press OK.",
        )
        self._dark_theme.Bind(wx.EVT_CHECKBOX, self._on_dark_theme)
        self._battery_icon = self._toggle_row(
            card, sizer, "Battery icon", "Glyph instead of digits", config.battery_icon,
            "Draw a battery filled to the charge level instead of\n"
            "the percent digits. The exact number moves to the\n"
            "tray tooltip.",
        )
        self._battery_icon.Bind(wx.EVT_CHECKBOX, self._on_battery_icon)
        self._text_outline = self._toggle_row(
            card, sizer, "Text outline", "Keeps digits readable", config.text_outline,
            "Draw a contrasting outline around the tray digits and\n"
            "the report-rate icon. Keeps them readable on a same-colored taskbar.",
        )
        self._text_outline.Bind(wx.EVT_CHECKBOX, self._on_outline)
        self._dynamic_color = self._toggle_row(
            card, sizer, "Color by charge level", "Yellow and red when low", config.dynamic_color,
            "Color the battery percent by charge: the font color\n"
            f"above {MID_THRESHOLD}%, then the two colors picked next to it\n"
            f"at \u2264 {MID_THRESHOLD}% and \u2264 {LOW_THRESHOLD}%.",
        )
        self._dynamic_color.Bind(wx.EVT_CHECKBOX, self._on_dynamic_color)

        self._color = w.Swatch(card, wx.Colour(*config.foreground_color), on_changed=self._emit_color_preview)
        self._mid_color = w.Swatch(card, wx.Colour(*config.mid_color), on_changed=self._emit_color_preview)
        self._low_color = w.Swatch(card, wx.Colour(*config.low_color), on_changed=self._emit_color_preview)
        # The low-band swatches sit next to the font color -- it is the color of
        # the top band -- and only show up while "Color by charge level" is on.
        self._band_widgets: list[wx.Window] = [self._mid_color, self._low_color]
        self._row(
            card, sizer, "Colors", f"Normal, \u2264 {MID_THRESHOLD}%, \u2264 {LOW_THRESHOLD}%",
            self._color, self._mid_color, self._low_color,
        )

        size_value = min(TEXT_SIZE_MAX, max(TEXT_SIZE_MIN, config.text_size))
        self._size = w.Slider(card, TEXT_SIZE_MIN, TEXT_SIZE_MAX, size_value)
        self._size_label = w.text(card, f"{size_value}%")
        # Reserve the widest value's width so the row never jumps (measured in
        # the label's own font, so it survives DPI scaling).
        self._size_label.SetMinSize(wx.Size(self._size_label.GetTextExtent(f"{TEXT_SIZE_MAX}%").width, -1))
        self._size.Bind(wx.EVT_SLIDER, self._on_size_changed)
        self._row(
            card, sizer, "Text size", "Digits in the tray icon", self._size, self._size_label,
            tip="Scale the tray digits.\n100% fills the icon; lower values shrink.",
        )

        self._font = w.Dropdown(card, list(self._all_faces), width=self.FromDIP(150))
        self._font.Bind(wx.EVT_COMBOBOX, self._on_font_selected)
        self._all_fonts = w.Chip(card, "All fonts", False)
        self._all_fonts.SetToolTip(
            "List every installed font, not just monospaced ones.\n"
            "The digits are measured in the chosen face, so any font fits."
        )
        self._all_fonts.Bind(wx.EVT_CHECKBOX, self._on_all_fonts)
        self._font_caption = w.text(card, "Monospaced", muted=True, small=True)
        font_left = wx.BoxSizer(wx.VERTICAL)
        font_left.Add(w.text(card, "Font"), 0)
        font_left.Add(self._font_caption, 0)
        font_row = wx.BoxSizer(wx.HORIZONTAL)
        font_row.Add(font_left, 1, wx.ALIGN_CENTER_VERTICAL)
        font_row.Add(self._font, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, self.FromDIP(10))
        font_row.Add(self._all_fonts, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, self.FromDIP(6))
        sizer.Add(font_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, self.FromDIP(14))
        return card

    def _build_system(self, config: Config) -> w.Card:
        card, sizer = self._card("System")
        # Not part of Config: Windows' own Run entry is the source of truth. The
        # reset button leaves it alone -- it is not a look-and-feel default.
        self._autostart_was = autostart.is_enabled()
        self._autostart = self._toggle_row(
            card, sizer, "Start with Windows", "Run at sign-in", self._autostart_was,
            "Run the program when you sign in to Windows. Stored as a Run value\n"
            "for the current user that points at this copy of the program;\n"
            "press OK with the switch on after moving the folder to refresh it.",
        )
        self._poll = w.Stepper(card, int(config.poll_rate))
        self._row(card, sizer, "Poll interval", "Seconds between reads", self._poll)
        self._debug = self._toggle_row(
            card, sizer, "Debug logging", "Write logs/app.log next to the program", config.debug,
            "Off by default: no log file is written at all.\n"
            "Turn it on, press OK, and attach the file when reporting a problem.",
        )
        return card

    def _build_footer(self) -> wx.Sizer:
        reset = w.FlatButton(self, "Defaults")
        reset.Bind(wx.EVT_BUTTON, self._on_reset)
        show_log = w.FlatButton(self, "Open log")
        show_log.SetToolTip("Open logs/app.log (exists only after Debug logging was on).")
        show_log.Bind(wx.EVT_BUTTON, self._on_open_log)
        footer = wx.BoxSizer(wx.HORIZONTAL)
        footer.Add(reset, 0)
        footer.Add(show_log, 0, wx.LEFT, self.FromDIP(8))
        footer.AddStretchSpacer()
        footer.Add(w.FlatButton(self, "Cancel", button_id=wx.ID_CANCEL), 0)
        footer.Add(w.FlatButton(self, "OK", "primary", wx.ID_OK), 0, wx.LEFT, self.FromDIP(8))
        return footer

    # --- font list ----------------------------------------------------------

    def _restore_font_selection(self, config: Config) -> None:
        """Show the saved font, widening the list for a proportional face."""
        current_face = self._path_to_face.get(os.path.basename(config.font).lower())
        self._all_fonts.SetValue(bool(current_face) and current_face.lower() not in self._mono_faces)
        self._populate_faces()
        self._select_font(config.font)

    def _select_font(self, font: str) -> None:
        face = self._path_to_face.get(os.path.basename(font).lower())
        if face:
            self._font.SetStringSelection(face)

    def _populate_faces(self) -> None:
        """Fill the picker with all faces or just the monospaced ones."""
        show_all = self._all_fonts.GetValue()
        faces = (
            list(self._all_faces)
            if show_all
            else [face for face in self._all_faces if face.lower() in self._mono_faces]
        )
        keep = self._font.GetStringSelection()
        self._font.set_faces(faces)
        if keep in faces:
            self._font.SetStringSelection(keep)
        else:
            self._font.clear_selection()  # the old pick is not in this list
        self._font_caption.SetLabel("All fonts" if show_all else "Monospaced")

    def _update_bands(self) -> None:
        """Show the low-band swatches only while "Color by charge level" is on."""
        show = self._dynamic_color.GetValue()
        for widget in self._band_widgets:
            widget.Show(show)
        # Relayout the dialog (and the appearance card that owns the swatches)
        # so the row expands/collapses without leaving empty gaps or overlapping.
        self.Layout()
        self.Refresh()

    # --- events -------------------------------------------------------------

    def _on_font_selected(self, evt: wx.CommandEvent) -> None:
        self._emit_font_preview()
        evt.Skip()

    def _emit_font_preview(self) -> None:
        """Offer the current font pick to the live tray preview, if any."""
        if self._preview.font is None:
            return
        face = self._font.GetStringSelection()
        path = self._face_to_path.get(face) if face else None
        if path is not None:
            try:
                ImageFont.truetype(path, 16)
            except OSError:
                path = None  # uninstalled mid-dialog; fall back to the current font
        self._preview.font(path)

    def _on_all_fonts(self, evt: wx.CommandEvent) -> None:
        self._populate_faces()
        self._emit_font_preview()  # the selection may have cleared
        evt.Skip()

    def _on_size_changed(self, evt: wx.CommandEvent) -> None:
        self._size_label.SetLabel(f"{self._size.GetValue()}%")
        self._emit_size_preview()
        evt.Skip()

    def _emit_size_preview(self) -> None:
        """Offer the current size pick to the live tray preview, if any."""
        if self._preview.size is not None:
            self._preview.size(self._size.GetValue())

    def _on_outline(self, evt: wx.CommandEvent) -> None:
        self._emit_outline_preview()
        evt.Skip()

    def _emit_outline_preview(self) -> None:
        """Offer the current outline pick to the live tray preview, if any."""
        if self._preview.outline is not None:
            self._preview.outline(self._text_outline.GetValue())

    def _on_battery_icon(self, evt: wx.CommandEvent) -> None:
        self._emit_battery_icon_preview()
        evt.Skip()

    def _emit_battery_icon_preview(self) -> None:
        """Offer the current battery-icon pick to the live tray preview, if any."""
        if self._preview.battery_icon is not None:
            self._preview.battery_icon(self._battery_icon.GetValue())

    def _on_dynamic_color(self, evt: wx.CommandEvent) -> None:
        self._update_bands()
        self._emit_color_preview()
        evt.Skip()

    def _on_dark_theme(self, evt: wx.CommandEvent) -> None:
        """Switch the open dialog to the picked palette immediately."""
        w.apply_theme(self._dark_theme.GetValue())
        w.refresh_theme(self)
        evt.Skip()

    def _emit_color_preview(self) -> None:
        """Offer the current color pickers to the live tray preview, if any."""
        if self._preview.colors is None:
            return
        self._preview.colors(
            _rgb(self._color),
            _rgb(self._mid_color),
            _rgb(self._low_color),
            self._dynamic_color.GetValue(),
        )

    def _on_open_log(self, _evt: wx.CommandEvent) -> None:
        if log_exists():
            open_log()
            return
        wx.MessageBox(
            "There is no log yet: it is written only while Debug logging is on.\n"
            "Turn it on, press OK and use the program for a while.",
            "Open log",
            wx.OK | wx.ICON_INFORMATION,
            self,
        )

    def _on_key(self, evt: wx.KeyEvent) -> None:
        if evt.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        else:
            evt.Skip()

    def _on_reset(self, _evt: wx.CommandEvent) -> None:
        defaults = Config()
        self._poll.SetValue(defaults.poll_rate)
        self._all_fonts.SetValue(False)
        self._populate_faces()
        self._select_font(defaults.font)
        self._emit_font_preview()
        self._size.SetValue(defaults.text_size)
        self._size_label.SetLabel(f"{defaults.text_size}%")
        self._emit_size_preview()
        self._text_outline.SetValue(defaults.text_outline)
        self._emit_outline_preview()
        self._color.SetColour(wx.Colour(*defaults.foreground_color))
        self._mid_color.SetColour(wx.Colour(*defaults.mid_color))
        self._low_color.SetColour(wx.Colour(*defaults.low_color))
        self._dynamic_color.SetValue(defaults.dynamic_color)
        self._update_bands()
        self._emit_color_preview()
        self._dark_theme.SetValue(defaults.dark_theme)
        w.apply_theme(defaults.dark_theme)
        w.refresh_theme(self)
        self._battery_icon.SetValue(defaults.battery_icon)
        self._emit_battery_icon_preview()
        self._debug.SetValue(defaults.debug)

    def _on_ok(self, evt: wx.CommandEvent) -> None:
        face = self._font.GetStringSelection()
        if face:
            try:
                ImageFont.truetype(self._face_to_path[face], 16)
            except OSError:
                wx.MessageBox(
                    f"Could not load font {face!r}.\nPlease choose another.",
                    "Invalid font",
                    wx.OK | wx.ICON_ERROR,
                    self,
                )
                return  # keep the dialog open so the user can fix it
        if not self._apply_autostart():
            return
        evt.Skip()  # let the standard OK handler close the dialog

    def _apply_autostart(self) -> bool:
        """Write the autostart choice to the registry; ``False`` keeps the dialog open."""
        wanted = self._autostart.GetValue()
        if not wanted and not self._autostart_was:
            return True  # off and was off: nothing to touch
        try:
            autostart.set_enabled(wanted)  # on: also refreshes a stale path
        except OSError as exc:
            wx.MessageBox(
                f"Could not change the autostart setting:\n{exc}",
                "Start with Windows",
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return False
        return True

    # --- result -------------------------------------------------------------

    def apply_to(self, config: Config) -> None:
        config.poll_rate = self._poll.GetValue()
        face = self._font.GetStringSelection()
        if face:
            config.font = self._face_to_path[face]
        config.text_size = self._size.GetValue()
        config.text_outline = self._text_outline.GetValue()
        config.foreground_color = _rgb(self._color)
        config.mid_color = _rgb(self._mid_color)
        config.low_color = _rgb(self._low_color)
        config.dynamic_color = self._dynamic_color.GetValue()
        config.battery_icon = self._battery_icon.GetValue()
        config.dark_theme = self._dark_theme.GetValue()
        config.debug = self._debug.GetValue()
