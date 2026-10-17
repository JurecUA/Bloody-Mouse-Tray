"""State-machine logic of ui/app.py against stub wx (not real wx -- see README)."""

import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from unittest import mock

from tests import fakes

fakes.install_hid()
fakes.install_wx()

import wx  # noqa: E402  (the stub)

from mouse_tray import storage  # noqa: E402
from mouse_tray.battery import BatteryStatus  # noqa: E402
from mouse_tray.config import Config  # noqa: E402
from mouse_tray.ui import app as app_mod  # noqa: E402

NAME = "Bloody SG5 Pro"


class FakeTray:
    def __init__(self):
        self.updates = []

    def update(self, icon, tooltip):
        self.updates.append((icon, tooltip))


class FakeIcons:
    preview_foreground_color = None

    def _foreground(self):
        return self.preview_foreground_color or (91, 184, 255)

    def text_icon(self, text, color=None):
        return ("text", text, color)

    def battery_icon(self, level, color=None):
        return ("battery", level, color)


def status(percent, hz=1000, **kw):
    return BatteryStatus(present=True, percent=percent, polling_hz=hz, dpi=800, **kw)


class AppLogic(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.object(storage, "app_dir", return_value=tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)

        a = app_mod.TrayApp.__new__(app_mod.TrayApp)
        a.config, a.tray, a.icons = Config(), FakeTray(), FakeIcons()
        a._hover_timer, a._anim_timer = wx.Timer(), wx.Timer()
        a._hover_active, a._hover_pos, a._hover_seen, a._last_hover_poll = False, wx.Point(), 0.0, -100.0
        a._normal_icon, a._normal_tooltip, a._shown = None, "", None
        a._last_status = a._last_name = None
        a._preview_battery_icon = None
        a._preview_mid_color = a._preview_low_color = a._preview_dynamic_color = None
        a._current_mouse, a.full_charge_date, a._was_full, a._last_percent = NAME, None, False, None
        a._charging_below_full = False
        a._wakeup, a.notification = threading.Event(), mock.Mock()
        a._anim_index, a._anim_tooltip = 0, ""
        a._detected = None
        self.app = a
        wx.mouse = wx.Point(100, 100)

    # --- point 1: full-charge timer -------------------------------------------

    def test_charged_while_pc_off_starts_the_timer(self):
        self.app._last_percent = 40  # what the previous run last saw
        self.app._apply_status(status(100), NAME)  # unplugged, 100%: no cable flag
        self.assertIsNotNone(self.app.full_charge_date)
        self.assertLess(datetime.now() - self.app.full_charge_date, timedelta(seconds=5))
        self.assertEqual(storage.load_last_percent(NAME), 100)
        self.assertEqual(storage.load_full_charge_date(NAME), self.app.full_charge_date)

    def test_still_full_keeps_the_old_date(self):
        old = datetime(2026, 10, 1, 8, 0, 0)
        self.app.full_charge_date, self.app._last_percent = old, 100
        self.app._apply_status(status(100), NAME)
        self.assertEqual(self.app.full_charge_date, old)

    def test_discharging_then_recharging_resets(self):
        old = datetime(2026, 10, 1, 8, 0, 0)
        self.app.full_charge_date, self.app._last_percent = old, 100
        self.app._apply_status(status(99), NAME)
        self.assertEqual(self.app.full_charge_date, old)
        self.app._apply_status(status(100, charging=False, full=True), NAME)
        self.assertGreater(self.app.full_charge_date, old)

    def test_bogus_100_after_unplug_mid_charge_is_ignored(self):
        old = datetime(2026, 10, 1, 8, 0, 0)
        self.app.full_charge_date, self.app._last_percent = old, 90
        self.app._apply_status(status(95, charging=True), NAME)  # on the cable
        self.app._apply_status(status(100), NAME)  # cable pulled: firmware says 100 for a while
        self.app._apply_status(status(100), NAME)
        self.assertEqual(self.app.full_charge_date, old)
        self.app._apply_status(status(95), NAME)  # real level is back
        self.assertEqual(self.app.full_charge_date, old)
        self.app._apply_status(status(100, full=True), NAME)  # really charged later
        self.assertGreater(self.app.full_charge_date, old)

    def test_full_on_cable_then_unplug_keeps_the_date(self):
        self.app._last_percent = 99
        self.app._apply_status(status(100, full=True), NAME)
        stamp = self.app.full_charge_date
        self.assertIsNotNone(stamp)
        self.app._apply_status(status(100), NAME)  # unplugged, genuinely full
        self.assertEqual(self.app.full_charge_date, stamp)

    def test_toast_once_per_full_state(self):
        self.app._last_percent = 99
        self.app._apply_status(status(100, full=True), NAME)
        self.app._apply_status(status(100, full=True), NAME)
        self.assertEqual(self.app.notification.Show.call_count, 1)

    # --- settings card text ----------------------------------------------------

    def test_format_ago(self):
        ago = app_mod.format_ago
        self.assertEqual(
            [ago(timedelta(seconds=10)), ago(timedelta(minutes=12)), ago(timedelta(hours=5, minutes=3)),
             ago(timedelta(days=3, hours=2))],
            ["just now", "12 min ago", "5 h ago", "3 d ago"],
        )

    def test_battery_info_for_the_settings_card(self):
        self.assertEqual(self.app._battery_info().percent, None)  # nothing read yet
        self.app.full_charge_date = datetime.now() - timedelta(days=3, hours=2)
        self.app._apply_status(status(70, hz=8000), NAME)
        info = self.app._battery_info()
        self.assertEqual((info.percent, info.detail), (70, "Full 3 d ago"))
        self.assertEqual(info.headline, f"{NAME} \u00b7 8000 Hz \u00b7 DPI 800")
        self.app._apply_status(status(80, charging=True), NAME)
        self.assertEqual(self.app._battery_info().detail, "Charging")

    # --- detection + reading ---------------------------------------------------

    def _driver(self, status_):
        drv = mock.Mock()
        drv.name, drv.read_status.return_value = NAME, status_
        return drv

    def test_poll_once_reads_the_detected_mouse(self):
        drv = self._driver(status(80))
        with mock.patch.object(app_mod, "detect_all_drivers", return_value=[drv]):
            got, name = self.app._poll_once()
        self.assertEqual((got.percent, name), (80, NAME))

    def test_poll_once_without_a_mouse_or_without_an_answer_is_absent(self):
        with mock.patch.object(app_mod, "detect_all_drivers", return_value=[]):
            got, name = self.app._poll_once()
        self.assertEqual((got.present, name), (False, None))
        silent = self._driver(BatteryStatus.absent())  # dongle plugged, mouse switched off
        with mock.patch.object(app_mod, "detect_all_drivers", return_value=[silent]):
            got, name = self.app._poll_once()
        self.assertEqual((got.present, name), (False, None))

    # --- the worker thread must not die --------------------------------------

    def test_poll_loop_survives_an_exception(self):
        calls = []
        applied = []

        def poll_once():
            calls.append(1)
            if len(calls) == 1:
                raise ValueError("boom")
            self.app._stop.set()
            return status(80), NAME

        self.app._stop = threading.Event()
        self.app.config.poll_rate = self.app.config.fast_poll_rate = 0
        self.app._poll_once = poll_once
        with mock.patch.object(app_mod.wx, "CallAfter", lambda fn, *a: applied.append(a)):
            self.app._poll_loop()
        self.assertEqual(len(calls), 2)  # it went on after the failure
        self.assertFalse(applied[0][0].present)
        self.assertTrue(applied[1][0].present)

    def test_charging_is_read_once_per_poll_interval_not_every_second(self):
        waits = []

        class Wakeup:
            def wait(self, seconds):
                waits.append(seconds)
                app._stop.set()

            def clear(self): ...

        app = self.app
        app._stop, app._wakeup = threading.Event(), Wakeup()
        app.config.poll_rate, app.config.fast_poll_rate = 60, 1
        cases = [(status(80, charging=True), 60), (status(100, full=True), 60), (BatteryStatus.absent(), 1),
                 (status(None, asleep=True), 1)]
        for st, want in cases:
            app._stop.clear()
            app._poll_once = lambda st=st: (st, NAME)
            with mock.patch.object(app_mod.wx, "CallAfter", lambda *a: None):
                app._poll_loop()
            self.assertEqual(waits[-1], want, st)

    # --- tooltip -----------------------------------------------------------------

    def test_percent_is_not_in_the_tooltip_in_any_state_with_digits(self):
        cases = (status(80), status(100), status(95, charging=True), status(100, full=True))
        for st in cases:
            self.app._apply_status(st, NAME)
            self.assertNotIn("%", self.app.tray.updates[-1][1], st)
            self.app._on_hover()  # hovering must not bring it back
            self.assertNotIn("%", self.app.tray.updates[-1][1], st)
            self.app._end_hover()
            self.assertNotIn("%", self.app.tray.updates[-1][1], st)
        self.assertIn("1000 Hz", self.app.tray.updates[-1][1])

    def test_battery_glyph_mode_keeps_the_percent(self):
        self.app.config.battery_icon = True
        self.app._apply_status(status(80), NAME)
        self.assertIn("80%", self.app.tray.updates[-1][1])
        self.app._on_hover()
        self.assertIn("80%", self.app.tray.updates[-1][1])

    # --- point 2 / 4: hover icon ---------------------------------------------------

    def test_hover_shows_rate_in_color_then_restores(self):
        self.app._apply_status(status(80, hz=8000), NAME)
        normal = self.app.tray.updates[-1]
        self.assertEqual(normal[0][:2], ("text", "80"))

        self.app._on_hover()
        self.assertEqual(self.app.tray.updates[-1][0], ("text", "8K", (70, 150, 255)))
        self.assertTrue(self.app._hover_timer.running)
        self.assertTrue(self.app._wakeup.is_set())  # one fresh read requested

        wx.mouse = wx.Point(103, 100)  # jitter inside the icon
        self.app._on_hover_tick()
        self.assertTrue(self.app._hover_active)

        wx.mouse = wx.Point(300, 100)  # left
        self.app._on_hover_tick()
        self.assertFalse(self.app._hover_active)
        self.assertFalse(self.app._hover_timer.running)
        self.assertEqual(self.app.tray.updates[-1], normal)

    def test_hover_ends_when_idle_too_long(self):
        self.app._apply_status(status(80), NAME)
        with mock.patch.object(app_mod.time, "monotonic", return_value=1000.0):
            self.app._on_hover()
        with mock.patch.object(app_mod.time, "monotonic", return_value=1011.0):
            self.app._on_hover_tick()
        self.assertFalse(self.app._hover_active)

    def test_no_known_rate_means_no_swap(self):
        self.app._apply_status(status(80, hz=None), NAME)
        before = len(self.app.tray.updates)
        self.app._on_hover()
        self.assertEqual(self.app.tray.updates[-1][0][:2], ("text", "80"))
        self.assertEqual(len(self.app.tray.updates), before + 1)  # only the redraw, same icon

    def test_charge_animation_does_not_fight_the_hover_icon(self):
        self.app._apply_status(status(50, hz=2000, charging=True), NAME)
        self.app._on_hover()
        shown = len(self.app.tray.updates)
        self.app._on_anim_tick()
        self.app._on_anim_tick()
        self.assertEqual(len(self.app.tray.updates), shown)
        self.assertEqual(self.app.tray.updates[-1][0][:2], ("text", "2K"))

    def test_rate_change_while_hovering_is_picked_up(self):
        self.app._apply_status(status(80, hz=1000), NAME)
        self.app._on_hover()
        self.assertEqual(self.app.tray.updates[-1][0], ("text", "1K", (255, 255, 255)))
        self.app._apply_status(status(80, hz=500), NAME)
        self.assertEqual(self.app.tray.updates[-1][0], ("text", "500", (0, 200, 190)))

    def test_mouse_gone_while_hovering_shows_dash(self):
        self.app._apply_status(status(80), NAME)
        self.app._on_hover()
        self.app._apply_status(BatteryStatus.absent(), None)
        self.assertEqual(self.app.tray.updates[-1][0][:2], ("text", "-"))


if __name__ == "__main__":
    unittest.main()
