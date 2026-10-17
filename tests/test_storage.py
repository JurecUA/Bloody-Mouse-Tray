import json
import os
import tempfile
import unittest
from datetime import datetime
from unittest import mock

from mouse_tray import storage
from mouse_tray.config import Config


class StorageTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        patcher = mock.patch.object(storage, "app_dir", return_value=self.dir.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.dir.cleanup)

    def test_file_is_next_to_the_program(self):
        storage.save_last_percent("M", 50)
        self.assertTrue(os.path.isfile(os.path.join(self.dir.name, "mouse_tray.json")))

    def test_full_charge_and_last_percent_roundtrip(self):
        when = datetime(2026, 10, 14, 12, 30, 5)
        storage.save_full_charge_date("Bloody SG5 Pro", when)
        storage.save_last_percent("Bloody SG5 Pro", 87)
        self.assertEqual(storage.load_full_charge_date("Bloody SG5 Pro"), when)
        self.assertEqual(storage.load_last_percent("Bloody SG5 Pro"), 87)
        self.assertIsNone(storage.load_full_charge_date("Other"))

    def test_settings_roundtrip_and_invalid_values_are_skipped(self):
        cfg = Config(poll_rate=30, battery_icon=True, foreground_color=(1, 2, 3))
        storage.save_settings(cfg)
        loaded = Config()
        storage.load_settings(loaded)
        self.assertEqual((loaded.poll_rate, loaded.battery_icon, loaded.foreground_color), (30, True, (1, 2, 3)))

        path = os.path.join(self.dir.name, "mouse_tray.json")
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        data["settings"].update(poll_rate=-5, text_size=9999, foreground_color=[1, 2])
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        fresh = Config()
        storage.load_settings(fresh)
        self.assertEqual((fresh.poll_rate, fresh.text_size, fresh.foreground_color),
                         (Config().poll_rate, Config().text_size, Config().foreground_color))

    def test_corrupt_file_is_set_aside_not_overwritten_silently(self):
        path = os.path.join(self.dir.name, "mouse_tray.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        self.assertIsNone(storage.load_full_charge_date("M"))
        self.assertTrue(os.path.exists(path + ".corrupt"))

    def test_unwritable_folder_does_not_raise(self):
        missing = os.path.join(self.dir.name, "missing", "dir")
        with mock.patch.object(storage, "app_dir", return_value=missing):
            storage.save_last_percent("M", 50)  # must just log
            self.assertIsNone(storage.load_last_percent("M"))

    def test_no_registry_dependency(self):
        with open(storage.__file__, encoding="utf-8") as handle:
            self.assertNotIn("winreg", handle.read())


if __name__ == "__main__":
    unittest.main()
