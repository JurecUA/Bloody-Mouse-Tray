import sys
import unittest
from unittest import mock

from tests import fakes

winreg = fakes.install_winreg()

from mouse_tray import autostart  # noqa: E402


class Autostart(unittest.TestCase):
    def setUp(self):
        winreg.values.clear()

    def test_off_by_default(self):
        self.assertFalse(autostart.is_enabled())

    def test_enable_writes_the_quoted_exe_path_and_disable_removes_it(self):
        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(sys, "executable", r"C:\Program Files\Bloody\mouse_tray.exe"):
            autostart.set_enabled(True)
        self.assertTrue(autostart.is_enabled())
        self.assertEqual(list(winreg.values.values()), [r'"C:\Program Files\Bloody\mouse_tray.exe"'])
        autostart.set_enabled(False)
        self.assertFalse(autostart.is_enabled())

    def test_enabling_again_refreshes_a_stale_path(self):
        winreg.values["Bloody Mouse Tray"] = r'"D:\old\mouse_tray.exe"'
        with mock.patch.object(sys, "frozen", True, create=True), mock.patch.object(sys, "executable", r"E:\new\mouse_tray.exe"):
            autostart.set_enabled(True)
        self.assertEqual(winreg.values["Bloody Mouse Tray"], r'"E:\new\mouse_tray.exe"')

    def test_disabling_when_already_off_is_fine(self):
        autostart.set_enabled(False)
        self.assertFalse(autostart.is_enabled())

    def test_from_source_runs_main_py_with_both_paths_quoted(self):
        with mock.patch.object(sys, "frozen", False, create=True):
            cmd = autostart.command()
        self.assertTrue(cmd.startswith('"') and cmd.endswith('main.py"'), cmd)
        self.assertEqual(cmd.count('"'), 4)


if __name__ == "__main__":
    unittest.main()
