import importlib
import os
import unittest
from unittest.mock import patch

from btc_toolkit import colors


class TestColors(unittest.TestCase):
    def tearDown(self):
        importlib.reload(colors)  # restore the real state for other tests

    def _reload(self, tty: bool, env: dict):
        with patch.dict(os.environ, env, clear=False), patch("sys.stdout.isatty", return_value=tty):
            if "NO_COLOR" not in env:
                os.environ.pop("NO_COLOR", None)
            importlib.reload(colors)

    def test_tty_has_color(self):
        self._reload(True, {})
        self.assertEqual(colors.green("x"), "\033[32mx\033[0m")

    def test_no_color_disables(self):
        self._reload(True, {"NO_COLOR": "1"})
        self.assertEqual(colors.green("x"), "x")

    def test_empty_no_color_is_ignored(self):
        self._reload(True, {"NO_COLOR": ""})  # spec: only non-empty values disable
        self.assertEqual(colors.green("x"), "\033[32mx\033[0m")

    def test_pipe_has_no_color(self):
        self._reload(False, {})
        self.assertEqual(colors.green("x"), "x")


if __name__ == "__main__":
    unittest.main()
