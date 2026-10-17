import unittest

from mouse_tray.polling import is_new_full_charge, rate_color, rate_label


class RateLabel(unittest.TestCase):
    def test_labels(self):
        got = [rate_label(hz) for hz in (125, 250, 500, 1000, 2000, 4000, 8000)]
        self.assertEqual(got, ["125", "250", "500", "1K", "2K", "4K", "8K"])

    def test_non_round_thousands_keep_decimals(self):
        self.assertEqual(rate_label(1500), "1.5K")


class RateColor(unittest.TestCase):
    def test_every_color_gets_a_dark_outline(self):
        """Luminance above 0.5 means a black outline (ui/icons.py); a white one smeared the 8K."""
        for hz, (r, g, b) in __import__("mouse_tray.config", fromlist=["RATE_COLORS"]).RATE_COLORS.items():
            self.assertGreater((0.299 * r + 0.587 * g + 0.114 * b) / 255, 0.5, hz)

    def test_colors_match_mouse_indicator(self):
        self.assertEqual(rate_color(1000), (255, 255, 255))  # white, outlined by the icon code
        self.assertEqual(rate_color(250), (150, 150, 150))  # gray: not on the mouse
        self.assertEqual(len({rate_color(hz) for hz in (125, 500, 1000, 2000, 4000, 8000)}), 6)

    def test_unknown_rate_is_gray(self):
        self.assertEqual(rate_color(3333), rate_color(250))


class NewFullCharge(unittest.TestCase):
    def test_charged_while_pc_was_off(self):  # last look 40%, now 100%, cable already unplugged
        self.assertTrue(is_new_full_charge(40, 100, True))

    def test_still_full_is_not_new(self):
        self.assertFalse(is_new_full_charge(100, 100, True))

    def test_below_100_is_never_new(self):
        self.assertFalse(is_new_full_charge(50, 99, True))
        self.assertFalse(is_new_full_charge(None, None, False))

    def test_first_run(self):
        self.assertTrue(is_new_full_charge(None, 100, False))  # no date yet: start the timer
        self.assertFalse(is_new_full_charge(None, 100, True))  # keep the stored date


if __name__ == "__main__":
    unittest.main()
