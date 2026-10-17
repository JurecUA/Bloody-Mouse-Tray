import unittest

from tests import fakes

hid = fakes.install_hid()

from mouse_tray.drivers import all_drivers, detect_all_drivers  # noqa: E402
from mouse_tray.drivers.vendor.bloody import BloodyDriver  # noqa: E402


def line(subtype, *payload):
    return [0x06, subtype, *payload, *([0] * (8 - 2 - len(payload)))]


class Decode(unittest.TestCase):
    def setUp(self):
        self.drv = BloodyDriver(BloodyDriver.models[0])

    def burst(self, percent, cable, rate=0x04, dpi=0x04):
        return {0x56: line(0x56, percent, cable), 0x81: line(0x81, rate), 0x87: [6, 0x87, 0, 0, 0, 0, 0, dpi]}

    def test_wireless_with_rate_and_dpi(self):
        st = self.drv._decode(self.burst(85, 0))
        self.assertEqual((st.present, st.percent, st.charging, st.full), (True, 85, False, False))
        self.assertEqual((st.polling_hz, st.dpi), (8000, 1600))

    def test_cable_states(self):
        self.assertTrue(self.drv._decode(self.burst(60, 1)).charging)
        full = self.drv._decode(self.burst(100, 1))
        self.assertTrue(full.full and not full.charging)
        # 100% without the cable is NOT "full" at driver level -- the app's level-based tracker covers it
        unplugged = self.drv._decode(self.burst(100, 0))
        self.assertFalse(unplugged.full or unplugged.charging)

    def test_every_documented_rate_code(self):
        want = {0: 1000, 1: 500, 2: 250, 3: 125, 4: 8000, 5: 4000, 6: 2000}
        for code, hz in want.items():
            self.assertEqual(self.drv._decode(self.burst(50, 0, rate=code)).polling_hz, hz)

    def test_unknown_codes_are_none_not_a_guess(self):
        st = self.drv._decode(self.burst(50, 0, rate=0x42, dpi=0x42))
        self.assertEqual((st.polling_hz, st.dpi), (None, None))

    def test_implausible_percent_is_absent(self):
        self.assertFalse(self.drv._decode(self.burst(101, 0)).present)

    def test_battery_only_burst_still_works(self):
        st = self.drv._decode({0x56: line(0x56, 70, 0)})
        self.assertEqual((st.percent, st.polling_hz, st.dpi), (70, None, None))


class Burst(unittest.TestCase):
    def test_lines_in_any_order_plus_noise(self):
        drv = BloodyDriver(BloodyDriver.models[0])
        hid.device.queue = [line(0x87, 0), [0x06, 0x55, 0, 0, 0, 0, 0, 0], line(0x81, 4), line(0x56, 90, 0), [1, 2]]
        hid.device.queue[0][7] = 4
        got = drv._wait_for_burst(hid.device())
        self.assertEqual(set(got), {0x56, 0x81, 0x87})

    def test_no_battery_line_is_none(self):
        drv = BloodyDriver(BloodyDriver.models[0])
        hid.device.queue = [line(0x81, 4)]
        import mouse_tray.drivers.vendor.bloody as mod

        old, mod._READ_TIMEOUT = mod._READ_TIMEOUT, 0.05
        try:
            self.assertIsNone(drv._wait_for_burst(hid.device()))
        finally:
            mod._READ_TIMEOUT = old


def collections(pid, status, command):
    base = {"vendor_id": 0x1956, "product_id": pid}
    return [
        {**base, "usage_page": 0xFF01, "usage": 1, "interface_number": 0, "path": status},
        {**base, "usage_page": 0xFF02, "usage": 1, "interface_number": 2, "path": command},
    ]


class Links(unittest.TestCase):
    """Cable and dongle together: the user's log showed the mouse lost (dongle answers 255)."""

    WIRED_STATUS, DONGLE_STATUS = b"wired-status", b"dongle-status"

    def setUp(self):
        import mouse_tray.drivers.bus as bus
        import mouse_tray.drivers.vendor.bloody as mod

        self.bus, self.mod = bus, mod
        self.old_timeout, mod._READ_TIMEOUT = mod._READ_TIMEOUT, 0.05
        self.addCleanup(setattr, mod, "_READ_TIMEOUT", self.old_timeout)
        self.addCleanup(setattr, hid.device, "by_path", {})
        self.addCleanup(setattr, hid, "_devices", [])
        bus._snapshot = None
        self.drv = BloodyDriver(BloodyDriver.models[0])

    def plug(self, wired: bool, dongle: bool, wired_answer=None, dongle_answer=None):
        hid._devices = []
        if wired:
            hid._devices += collections(0x3144, self.WIRED_STATUS, b"wired-command")
        if dongle:
            hid._devices += collections(0x3069, self.DONGLE_STATUS, b"dongle-command")
        hid.device.by_path = {self.WIRED_STATUS: list(wired_answer or []), self.DONGLE_STATUS: list(dongle_answer or [])}
        hid.device.opened = []
        self.bus._snapshot = None

    def test_cable_and_dongle_the_cable_answers(self):
        self.plug(True, True,
                  wired_answer=[line(0x56, 100, 1), line(0x81, 3), [6, 0x87, 0, 0, 0, 0, 0, 2]],
                  dongle_answer=[line(0x56, 255, 1)])
        st = self.drv.read_status()
        self.assertEqual((st.present, st.percent, st.full, st.polling_hz, st.dpi), (True, 100, True, 125, 1000))
        self.assertNotIn(self.DONGLE_STATUS, hid.device.opened)  # no need to ask the dongle

    def test_dongle_saying_255_is_not_a_reading(self):
        self.plug(False, True, dongle_answer=[line(0x56, 255, 1)])
        self.assertFalse(self.drv.read_status().present)

    def test_silent_cable_falls_back_to_the_dongle(self):
        self.plug(True, True, dongle_answer=[line(0x56, 80, 0), line(0x81, 0), [6, 0x87, 0, 0, 0, 0, 0, 2]])
        st = self.drv.read_status()
        self.assertEqual((st.percent, st.polling_hz, st.charging), (80, 1000, False))

    def test_on_the_cable_but_nobody_answers_means_charging_not_gone(self):
        self.plug(True, True, dongle_answer=[line(0x56, 255, 1)])
        st = self.drv.read_status()
        self.assertEqual((st.present, st.percent, st.charging), (True, None, True))

    def test_dongle_alone_wireless(self):
        self.plug(False, True, dongle_answer=[line(0x56, 85, 0), line(0x81, 1), [6, 0x87, 0, 0, 0, 0, 0, 2]])
        st = self.drv.read_status()
        self.assertEqual((st.percent, st.polling_hz, st.charging), (85, 500, False))

    def test_cable_alone(self):
        self.plug(True, False, wired_answer=[line(0x56, 100, 1), line(0x81, 0), [6, 0x87, 0, 0, 0, 0, 0, 2]])
        self.assertEqual(self.drv.read_status().polling_hz, 1000)

    def test_a_crashing_link_does_not_hide_the_other(self):
        self.plug(True, True, dongle_answer=[line(0x56, 70, 0)])
        original = self.drv._read_burst

        def flaky(pid):
            if pid == 0x3144:
                raise ValueError("boom")
            return original(pid)

        self.drv._read_burst = flaky
        self.assertEqual(self.drv.read_status().percent, 70)

    def test_nothing_plugged(self):
        self.plug(False, False)
        self.assertFalse(self.drv.read_status().present)


class Registry(unittest.TestCase):
    def test_only_bloody_is_registered(self):
        self.assertEqual([d.__name__ for d in all_drivers()], ["BloodyDriver"])

    def test_detection_follows_the_bus(self):
        import mouse_tray.drivers.bus as bus

        hid._devices = []
        bus._snapshot = None
        self.assertEqual(detect_all_drivers(), [])
        hid._devices = [{"vendor_id": 0x1956, "product_id": 0x3069, "usage_page": 0xFF01, "usage": 1,
                         "interface_number": 0, "path": b"p"}]
        bus._snapshot = None
        found = detect_all_drivers()
        self.assertEqual([d.name for d in found], ["Bloody SG5 Pro"])
        hid._devices = []
        bus._snapshot = None
        self.assertEqual(detect_all_drivers(), [])  # unplug is noticed


if __name__ == "__main__":
    unittest.main()
