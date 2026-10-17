"""Application entry point: the wx app, the polling loop and the one state
machine that turns any :class:`BatteryStatus` into a tray icon. Hovering the
icon swaps it for the report rate (see ``_show`` / ``_on_hover``).

This module never imports a driver module, only the registry's
:func:`detect_all_drivers` and the :class:`MouseDriver` contract it returns.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import threading
import time
from contextlib import suppress
from datetime import datetime, timedelta

import wx
from wx.adv import NotificationMessage

from ..battery import BatteryStatus
from ..config import GREEN, LOW_THRESHOLD, MID_THRESHOLD, VERSION, Config
from ..config import config as default_config
from ..i18n import tr
from ..drivers import detect_all_drivers
from ..logging_setup import setup_logging
from ..polling import is_new_full_charge, rate_color, rate_label
from .icons import IconRenderer, tray_icon_size
from .info import BatteryInfo
from .tray import TrayIcon

log = logging.getLogger(__name__)

#: Charge levels cycled through while the mouse is charging.
_ANIMATION_FRAMES = (0, 50, 100)
_ANIMATION_INTERVAL_MS = 500
#: Hover on the tray icon shows the report rate. Windows reports cursor moves
#: over the icon but not the cursor leaving, so a short timer compares the
#: cursor with where the last move event happened.
_HOVER_POLL_MS = 150
_HOVER_LEAVE_PX = 6  # farther than this from the last event position = left
_HOVER_IDLE_S = 10  # still cursor with no events for this long also ends it
_HOVER_REPOLL_S = 3  # at most one extra mouse read per this many seconds of hovering
_NO_MOUSE = "No Mouse Detected"


def format_timedelta(delta: timedelta, language: str = "en") -> str:
    """Format a duration like ``"1 days, 23:59:59"``."""
    days = delta.days
    seconds = int(delta.total_seconds()) - days * 86400
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{days}{tr(' days, ', language)}{hours:02d}:{minutes:02d}:{secs:02d}"


def format_ago(delta: timedelta, language: str = "en") -> str:
    """Short age like ``"3 d ago"``, ``"5 h ago"``, ``"12 min ago"`` (for the settings card)."""
    minutes = max(0, int(delta.total_seconds() // 60))
    if minutes >= 1440:
        return f"{minutes // 1440}{tr(' d ago', language)}"
    if minutes >= 60:
        return f"{minutes // 60}{tr(' h ago', language)}"
    return f"{minutes}{tr(' min ago', language)}" if minutes else tr("just now", language)


def format_settings(status: BatteryStatus) -> str:
    """Sensor settings line like ``"1000 Hz · DPI 1600"``; either part may be missing.

    Empty when the driver reports neither, so the tooltip is unchanged for every
    mouse that does not expose them.
    """
    parts = []
    if status.polling_hz is not None:
        parts.append(f"{status.polling_hz} Hz")
    if status.dpi is not None:
        parts.append(f"DPI {status.dpi}")
    return " \u00b7 ".join(parts)


class TrayApp(wx.Frame):
    """Hidden frame that owns the tray icon, notification and worker thread.

    A frame is needed because ``NotificationMessage`` and the wx main loop
    require a top-level window; it never becomes visible.
    """

    def __init__(self, config: Config):
        super().__init__(None, title=config.display_name)
        self.config = config
        self.icons = IconRenderer(config, tray_icon_size(self))
        log.info("tray icons render at %dpx", self.icons.icon_size)

        # The full-charge timer is per mouse, keyed by its display name. We
        # only know which mouse is connected after detection, so the date is
        # (re)loaded in _sync_mouse whenever the active mouse changes.
        self.full_charge_date: datetime | None = None
        self._current_mouse: str | None = None
        self._was_full = False
        # Level seen at the last look (persisted, so the next launch can tell a
        # charge that happened while the PC was off).
        self._last_percent: int | None = None
        # True while the last cable-connected reading was still below 100%. The
        # firmware reports a bogus 100% for a moment after the cable comes off
        # (confirmed by the upstream maintainer, issue #5), which must not start
        # the full-charge timer.
        self._charging_below_full = False

        # Name of the detected mouse, kept only to log when it appears or goes
        # (worker thread).
        self._detected: str | None = None

        # Last applied snapshot, so a settings live preview (or a settings
        # close) can repaint instantly without waiting for the next poll tick.
        self._last_status: BatteryStatus | None = None
        self._last_name: str | None = None
        #: Live settings preview for "Show battery icon"; unlike the font/size/
        #: outline overrides it lives here, not on the renderer, because the
        #: digits-vs-battery choice is made by _apply_status, not by drawing.
        self._preview_battery_icon: bool | None = None
        #: Live settings preview for charge-level colouring (mid, low, dynamic).
        #: Foreground lives on the icon renderer; these three live here because
        #: _apply_status decides the band colour before drawing.
        self._preview_mid_color: tuple[int, int, int] | None = None
        self._preview_low_color: tuple[int, int, int] | None = None
        self._preview_dynamic_color: bool | None = None

        # Hover: what the tray shows normally (so it can be restored when the
        # cursor leaves) and the bookkeeping that detects the cursor leaving.
        self._normal_icon: wx.Icon | None = None
        self._normal_tooltip = config.display_name
        self._shown: tuple[wx.Icon, str] | None = None
        self._hover_active = False
        self._hover_pos = wx.Point(0, 0)
        self._hover_seen = 0.0
        self._last_hover_poll = 0.0

        self.tray = TrayIcon(
            self,
            on_left_click=self._wake,
            on_hover=self._on_hover,
            on_reset_timer=self._reset_timer,
            on_settings=self._open_settings,
            on_about=self._open_about,
            on_exit=self._exit,
            dark_theme=config.dark_theme,
            language=config.language,
        )
        self.tray.update(self.icons.text_icon(" "), config.display_name)

        self.notification = NotificationMessage(
            title=config.display_name, message=tr("Charged 100%", config.language)
        )
        self.notification.SetFlags(wx.ICON_INFORMATION)
        self.notification.UseTaskBarIcon(self.tray)

        # Charge animation runs on the main thread via a timer.
        self._anim_timer = wx.Timer(self)
        self._anim_index = 0
        self._anim_tooltip = config.display_name
        self.Bind(wx.EVT_TIMER, self._on_anim_tick, self._anim_timer)
        self._hover_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_hover_tick, self._hover_timer)

        # Polling runs on a background thread; it only ever calls back into the
        # UI through wx.CallAfter, so all widget work stays on the main thread.
        self._stop = threading.Event()
        self._wakeup = threading.Event()
        self._worker = threading.Thread(target=self._poll_loop, daemon=True)
        self._worker.start()

    # --- polling thread -----------------------------------------------------

    def _poll_loop(self) -> None:
        while not self._stop.is_set():
            try:
                status, name = self._poll_once()
            except Exception:
                log.exception("Polling failed; will retry")
                status, name = BatteryStatus.absent(), None
            wx.CallAfter(self._apply_status, status, name)

            # Charging is no reason to read faster: the charge animation runs on its
            # own timer, a hover or click re-polls at once, and "full" / "unplugged"
            # may wait for the next regular read. Fast reads are for a mouse that
            # is asleep or missing, to catch it coming back.
            awake = status.present and not status.asleep
            interval = self.config.poll_rate if awake else self.config.fast_poll_rate
            self._wakeup.wait(interval)
            self._wakeup.clear()

    def _poll_once(self) -> tuple[BatteryStatus, str | None]:
        """Detect the mouse and read it (worker thread).

        Detection runs every tick -- it costs one cached bus enumeration -- so a
        mouse plugged in later is found on its own. A detected mouse that does
        not answer (dongle plugged, mouse switched off) reads as "no mouse".
        """
        drivers = detect_all_drivers()
        found = drivers[0].name if drivers else None
        if found != self._detected:
            log.info("Mouse detected: %s", found or "none")
            self._detected = found
        if not drivers:
            return BatteryStatus.absent(), None
        status = drivers[0].read_status()
        if not status.present:
            return BatteryStatus.absent(), None
        return status, drivers[0].name

    def _wake(self) -> None:
        """Trigger an immediate re-poll (e.g. tray clicked to wake a mouse)."""
        self._wakeup.set()

    # --- state machine (main thread) ---------------------------------------

    def _apply_status(self, status: BatteryStatus, name: str | None) -> None:  # noqa: PLR0911
        """Render one status snapshot. The single point that drives the tray.

        The guard-clause chain is the design (see CLAUDE.md): one flat, ordered
        list of states, each rendering and returning. Collapsing it to fit a
        return-count limit would bury the ordering that makes it readable.
        """
        self._last_status, self._last_name = status, name
        self._sync_mouse(name)
        self._track_full_charge(status)

        if not status.present:
            self._stop_animation()
            self._was_full = False
            self._show(self.icons.text_icon("-"), tr(_NO_MOUSE, self.config.language))
            return

        tooltip = self._tooltip(name, status)

        if status.charging:
            self._was_full = False
            self._start_animation(tooltip)
            return

        self._stop_animation()

        if status.full:
            self._show(self.icons.battery_icon(100, GREEN), tooltip)
            if not self._was_full:
                self._was_full = True
                self.notification.Show(timeout=NotificationMessage.Timeout_Auto)
            return

        self._was_full = False

        if status.asleep:
            self._show(self.icons.text_icon("Zzz"), tooltip)
            return

        if status.percent is None:
            # Present and awake but the driver could not read a level. Neither
            # a number nor a fill height is meaningful, so say so.
            self._show(self.icons.text_icon("?"), tooltip)
            return

        if status.percent == 100:
            # 100% but no "full" flag from the driver. The foreground color is
            # what dynamic_color would pick for this band anyway, and green
            # stays reserved for the full state above.
            self._show(self.icons.battery_icon(100), tooltip)
            return

        color = self._charge_color(status.percent) if self._dynamic_color_mode() else None
        if self._battery_icon_mode():
            # The exact number is in the tooltip built above.
            self._show(self.icons.battery_icon(status.percent, color), tooltip)
            return
        self._show(self.icons.text_icon(str(status.percent), color), tooltip)

    def _track_full_charge(self, status: BatteryStatus) -> None:
        """Start the full-charge timer the moment the battery reaches 100%.

        Judged by the charge level against the level seen at the previous look
        (kept across runs), not by the cable: a mouse charged while the PC was
        off is already unplugged when the app starts, yet still shows a jump to
        100%. The moment is then "now" -- the first look after the charge.

        One exception: right after the cable is pulled in the middle of a charge
        the firmware briefly reports 100% (a known quirk), so a 100% without the
        cable that follows a charging reading below 100 is ignored until the
        real level comes back.
        """
        if self._current_mouse is None or status.percent is None:
            return
        from ..storage import save_last_percent

        # `charging` / `full` both mean "on the cable" (see the Bloody driver).
        if status.charging or status.full:
            self._charging_below_full = status.percent < 100
        elif status.percent < 100:
            self._charging_below_full = False  # the real level is back
        elif self._charging_below_full:
            log.debug("Ignoring 100%% right after the cable was removed mid-charge (firmware artifact)")
            return

        previous = self._last_percent
        if is_new_full_charge(previous, status.percent, self.full_charge_date is not None):
            self._record_full_charge()
        if status.percent != previous:
            self._last_percent = status.percent
            save_last_percent(self._current_mouse, status.percent)

    def _sync_mouse(self, name: str | None) -> None:
        """Load the active mouse's own full-charge date when the mouse changes."""
        if name is None or name == self._current_mouse:
            return
        from ..storage import load_full_charge_date, load_last_percent

        self._current_mouse = name
        self.full_charge_date = load_full_charge_date(name)
        self._last_percent = load_last_percent(name)
        self._was_full = False  # don't carry full-state across a mouse switch
        self._charging_below_full = False

    def _battery_icon_mode(self) -> bool:
        """Whether the tray shows a battery glyph instead of digits (preview wins)."""
        if self._preview_battery_icon is not None:
            return self._preview_battery_icon
        return self.config.battery_icon

    def _tooltip(self, name: str | None, status: BatteryStatus) -> str:
        """Mouse name, time since full, rate / DPI -- and the percent in glyph mode only.

        With digits on the icon the percent line would only repeat them, and the
        user does not want it in any state (charging, full, ...). In the battery
        glyph mode the icon shows a fill level and this line is the only place
        the exact number appears, so it stays there.
        """
        lines = [name or tr(_NO_MOUSE, self.config.language)]
        if self._battery_icon_mode() and status.percent is not None:
            lines.append(f"{status.percent}%")
        if self.full_charge_date:
            lines.append(format_timedelta(datetime.now() - self.full_charge_date, self.config.language))
        settings = format_settings(status)
        if settings:
            lines.append(settings)
        return "\n".join(lines)

    # --- hover: report-rate icon --------------------------------------------

    def _show(self, icon: wx.Icon, tooltip: str) -> None:
        """Put ``icon`` on the tray -- or the report-rate icon while hovering.

        Every normal icon goes through here, so the state machine and the charge
        animation need no hover logic: the normal icon is remembered and comes
        back when the cursor leaves.
        """
        self._normal_icon, self._normal_tooltip = icon, tooltip
        if self._hover_active and (rate_icon := self._rate_icon()) is not None:
            if self._shown == (rate_icon, tooltip):
                return  # nothing changed (e.g. an animation tick under the cursor)
            icon = rate_icon
        self._shown = (icon, tooltip)
        self.tray.update(icon, tooltip)

    def _rate_icon(self) -> wx.Icon | None:
        """The report rate as a colored icon, or ``None`` when it is not known."""
        status = self._last_status
        if status is None or not status.present or status.polling_hz is None:
            return None
        try:
            return self.icons.text_icon(rate_label(status.polling_hz), rate_color(status.polling_hz))
        except OSError:  # stale font path: keep the normal icon
            return None

    def _on_hover(self) -> None:
        """The cursor moved over the tray icon (main thread)."""
        self._hover_pos = wx.GetMousePosition()
        self._hover_seen = time.monotonic()
        if self._hover_active:
            return
        self._hover_active = True
        self._hover_timer.Start(_HOVER_POLL_MS)
        self._redraw_normal()
        # The rate is changed with a button on the mouse, so ask for a fresh
        # read -- but at most once per few seconds, never a polling loop.
        if self._hover_seen - self._last_hover_poll > _HOVER_REPOLL_S:
            self._last_hover_poll = self._hover_seen
            self._wake()

    def _on_hover_tick(self, _evt: wx.TimerEvent | None = None) -> None:
        """Decide whether the cursor has left the icon (no event says so)."""
        pos = wx.GetMousePosition()
        away = max(abs(pos.x - self._hover_pos.x), abs(pos.y - self._hover_pos.y)) > _HOVER_LEAVE_PX
        idle = time.monotonic() - self._hover_seen > _HOVER_IDLE_S
        if away or idle:
            self._end_hover()

    def _end_hover(self) -> None:
        if self._hover_timer.IsRunning():
            self._hover_timer.Stop()
        if self._hover_active:
            self._hover_active = False
            self._redraw_normal()

    def _redraw_normal(self) -> None:
        """Repaint the remembered normal icon (or its hover replacement)."""
        if self._normal_icon is not None:
            self._show(self._normal_icon, self._normal_tooltip)

    # --- animation ----------------------------------------------------------

    def _start_animation(self, tooltip: str) -> None:
        self._anim_tooltip = tooltip
        if not self._anim_timer.IsRunning():
            self._anim_index = 0
            self._on_anim_tick()
            self._anim_timer.Start(_ANIMATION_INTERVAL_MS)

    def _stop_animation(self) -> None:
        if self._anim_timer.IsRunning():
            self._anim_timer.Stop()

    def _on_anim_tick(self, _evt: wx.TimerEvent | None = None) -> None:
        level = _ANIMATION_FRAMES[self._anim_index % len(_ANIMATION_FRAMES)]
        self._anim_index += 1
        self._show(self.icons.battery_icon(level), self._anim_tooltip)

    # --- full-charge timer --------------------------------------------------

    def _record_full_charge(self, when: datetime | None = None) -> None:
        if self._current_mouse is None:
            return  # no active mouse to attribute the timer to
        from ..storage import save_full_charge_date

        self.full_charge_date = when or datetime.now().replace(microsecond=0)
        save_full_charge_date(self._current_mouse, self.full_charge_date)
        log.info("Full charge timer for %s set to %s", self._current_mouse, self.full_charge_date)

    def _reset_timer(self) -> None:
        self._record_full_charge()

    # --- settings -----------------------------------------------------------

    def _preview_font(self, font_path: str | None) -> None:
        """Live preview: repaint the tray in a candidate settings font.

        The override lives on the renderer, so poll ticks keep repainting
        through it until the dialog closes (OK applies it for real, Cancel
        clears it) -- the preview never flickers back to the old font.
        """
        self.icons.preview_font = font_path
        if not self._repaint():
            self.icons.preview_font = None  # not renderable: don't poison later ticks

    def _preview_size(self, text_size: int | None) -> None:
        """Live preview: repaint the tray at a candidate settings text size."""
        self.icons.preview_text_size = text_size
        if not self._repaint():
            self.icons.preview_text_size = None

    def _preview_outline(self, text_outline: bool | None) -> None:
        """Live preview: repaint the tray with a candidate outline setting."""
        self.icons.preview_text_outline = text_outline
        if not self._repaint():
            self.icons.preview_text_outline = None

    def _preview_battery_icon_mode(self, battery_icon: bool | None) -> None:
        """Live preview: repaint the tray as digits or a battery glyph."""
        self._preview_battery_icon = battery_icon
        if not self._repaint():
            self._preview_battery_icon = None

    def _preview_colors(
        self,
        foreground: tuple[int, int, int],
        mid: tuple[int, int, int],
        low: tuple[int, int, int],
        dynamic: bool,
    ) -> None:
        """Live preview: repaint the tray with candidate indicator colours."""
        self.icons.preview_foreground_color = foreground
        self._preview_mid_color = mid
        self._preview_low_color = low
        self._preview_dynamic_color = dynamic
        if not self._repaint():
            self.icons.preview_foreground_color = None
            self._preview_mid_color = None
            self._preview_low_color = None
            self._preview_dynamic_color = None

    def _dynamic_color_mode(self) -> bool:
        """Whether charge-level colouring is on (preview wins over config)."""
        if self._preview_dynamic_color is not None:
            return self._preview_dynamic_color
        return self.config.dynamic_color

    def _charge_color(self, percent: int) -> tuple[int, int, int]:
        """Band colour for ``percent``, honouring live colour previews."""
        try:
            level = int(percent)
        except (TypeError, ValueError):
            return self.icons._foreground()
        if level <= LOW_THRESHOLD:
            return self._preview_low_color or self.config.low_color
        if level <= MID_THRESHOLD:
            return self._preview_mid_color or self.config.mid_color
        return self.icons._foreground()

    def _repaint(self) -> bool:
        """Re-render the cached snapshot (preview on/off).

        Returns False when there is nothing cached yet or the font fails to
        load, in which case the old icon is simply kept.
        """
        if self._last_status is None:
            return True
        try:
            self._apply_status(self._last_status, self._last_name)
        except OSError:  # stale registry font path: keep the old icon
            return False
        return True

    def _open_settings(self) -> None:
        from ..storage import save_settings
        from .settings import PreviewHooks, open_settings

        hooks = PreviewHooks(
            font=self._preview_font,
            size=self._preview_size,
            outline=self._preview_outline,
            battery_icon=self._preview_battery_icon_mode,
            colors=self._preview_colors,
        )
        ok = open_settings(self, self.config, hooks, self._battery_info())
        self.icons.preview_font = None
        self.icons.preview_text_size = None
        self.icons.preview_text_outline = None
        self.icons.preview_foreground_color = None
        self._preview_battery_icon = None
        self._preview_mid_color = None
        self._preview_low_color = None
        self._preview_dynamic_color = None
        if not ok:
            self._repaint()  # drop the preview right away
            return

        # self.config is mutated in place, so IconRenderer (which holds the same
        # reference) picks up the new font/color and the worker thread reads the
        # new poll rate on its next iteration. Persist and refresh now.
        from . import widgets as w

        w.apply_theme(self.config.dark_theme)
        self.tray.set_dark_theme(self.config.dark_theme)
        self.tray.set_language(self.config.language)
        save_settings(self.config)
        setup_logging(self.config.debug)
        self._repaint()  # show the applied settings instantly
        self._wake()  # force an immediate re-poll so the icon repaints

    def _battery_info(self) -> BatteryInfo:
        """What the settings dialog's battery card shows, from the last reading."""
        status = self._last_status
        if status is None or not status.present:
            return BatteryInfo(None, tr("No Mouse Detected", self.config.language), "")
        headline = " \u00b7 ".join(part for part in (self._last_name, format_settings(status)) if part)
        if status.charging:
            detail = tr("Charging", self.config.language)
        elif self.full_charge_date:
            detail = tr(
                "Full {age}", self.config.language,
                age=format_ago(datetime.now() - self.full_charge_date, self.config.language),
            )
        else:
            detail = ""
        return BatteryInfo(status.percent, headline, detail)

    def _open_about(self) -> None:
        from .about import open_about

        open_about(self, self.config)

    # --- lifecycle ----------------------------------------------------------

    def _exit(self) -> None:
        self._stop.set()
        self._wakeup.set()
        self._stop_animation()
        self._end_hover()
        self.tray.RemoveIcon()
        self.tray.Destroy()
        self.Destroy()


class _App(wx.App):
    def __init__(self, config: Config):
        self._config = config
        super().__init__(False)

    def OnInit(self) -> bool:  # noqa: N802 (wx override)
        frame = TrayApp(self._config)
        self.SetTopWindow(frame)
        return True


def run(config: Config | None = None) -> None:
    """Launch the tray application."""
    from ..storage import load_settings

    cfg = config or default_config
    load_settings(cfg)  # apply any persisted user settings
    # Theme palette (widgets.py) is applied lazily on first Settings / About /
    # tray-menu open — keeps a pure-tray process from importing the dialog kit.
    setup_logging(cfg.debug)
    log.info("Starting %s %s from %s", cfg.display_name, VERSION, sys.executable)
    with suppress(AttributeError, OSError):  # non-Windows or older Windows
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    app = _App(cfg)
    app.MainLoop()

