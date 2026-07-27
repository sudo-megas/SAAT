import shutil
import tempfile
import unittest
from pathlib import Path

from saat.config import Config


class ConfigTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-config-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _config(self) -> Config:
        return Config(self.tmp / "config.toml")


class TrayConfigTests(ConfigTestCase):
    """SPEC.md milestone 18 §8/§10: close_to_tray and start_minimised default
    OFF -- a user who hasn't opted in must never lose their window -- and
    tray_hint_shown defaults False so the one-time message can still fire."""

    def test_close_to_tray_defaults_false(self) -> None:
        self.assertFalse(self._config().close_to_tray())

    def test_close_to_tray_round_trips(self) -> None:
        config = self._config()
        config.set_close_to_tray(True)
        config.save()
        self.assertTrue(Config(config.path).close_to_tray())

    def test_start_minimised_defaults_false(self) -> None:
        self.assertFalse(self._config().start_minimised())

    def test_start_minimised_round_trips(self) -> None:
        config = self._config()
        config.set_start_minimised(True)
        config.save()
        self.assertTrue(Config(config.path).start_minimised())

    def test_tray_hint_shown_defaults_false(self) -> None:
        self.assertFalse(self._config().tray_hint_shown())

    def test_tray_hint_shown_round_trips(self) -> None:
        config = self._config()
        config.set_tray_hint_shown(True)
        config.save()
        self.assertTrue(Config(config.path).tray_hint_shown())

    def test_tray_settings_are_independent_of_each_other(self) -> None:
        config = self._config()
        config.set_close_to_tray(True)
        config.save()
        reloaded = Config(config.path)
        self.assertTrue(reloaded.close_to_tray())
        self.assertFalse(reloaded.start_minimised())
        self.assertFalse(reloaded.tray_hint_shown())


if __name__ == "__main__":
    unittest.main()
