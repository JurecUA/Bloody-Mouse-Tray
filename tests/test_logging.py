import logging
import os
import tempfile
import unittest
from unittest import mock

from mouse_tray import logging_setup


class LogOnlyWithDebug(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        patcher = mock.patch.object(logging_setup, "app_dir", return_value=self.dir.name)
        patcher.start()
        env = mock.patch.dict(os.environ, {"MOUSE_TRAY_DEBUG": ""})
        env.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(env.stop)
        self.addCleanup(self.dir.cleanup)
        self.addCleanup(self._reset_root)

    @staticmethod
    def _reset_root():
        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)
            handler.close()

    def test_debug_off_writes_no_file_and_creates_no_folder(self):
        self.assertIsNone(logging_setup.setup_logging(False))
        logging.getLogger("mouse_tray.test").info("a routine poll line")
        logging.getLogger("mouse_tray.test").warning("a warning")
        self._reset_root()
        self.assertFalse(os.path.exists(os.path.join(self.dir.name, "logs")))
        self.assertFalse(logging_setup.log_exists())

    def test_debug_on_writes_the_file(self):
        path = logging_setup.setup_logging(True)
        logging.getLogger("mouse_tray.test").info("a routine poll line")
        self._reset_root()
        self.assertEqual(path, logging_setup.log_path())
        self.assertTrue(logging_setup.log_exists())
        with open(path, encoding="utf-8") as handle:
            self.assertIn("a routine poll line", handle.read())

    def test_env_variable_also_turns_the_file_on(self):
        with mock.patch.dict(os.environ, {"MOUSE_TRAY_DEBUG": "1"}):
            self.assertIsNotNone(logging_setup.setup_logging(False))


if __name__ == "__main__":
    unittest.main()
