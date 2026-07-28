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


class PickerConfigTests(ConfigTestCase):
    """Milestone 20: the today picker's Random/Weighted toggle."""

    def test_picker_mode_defaults_to_none(self) -> None:
        """None, not a hard-coded default -- the picker itself applies the
        SPEC.md-mandated Weighted default when this comes back empty, the
        same way last_view()/active_scope() leave defaulting to the UI."""
        self.assertIsNone(self._config().picker_mode())

    def test_picker_mode_round_trips(self) -> None:
        config = self._config()
        config.set_picker_mode("weighted")
        config.save()
        self.assertEqual(Config(config.path).picker_mode(), "weighted")


class LanguageConfigTests(ConfigTestCase):
    """Milestone 21: absent means English, never "follow system" -- the app
    never reads QLocale.system()/LANG/LC_ALL to choose a UI language, so an
    absent key must resolve to English at the call site, the same
    None-means-default shape as theme_mode()/picker_mode()."""

    def test_language_defaults_to_none(self) -> None:
        self.assertIsNone(self._config().language())

    def test_language_round_trips(self) -> None:
        config = self._config()
        config.set_language("tr")
        config.save()
        self.assertEqual(Config(config.path).language(), "tr")

    def test_language_is_independent_of_theme_mode(self) -> None:
        config = self._config()
        config.set_theme_mode("light")
        config.set_language("tr")
        config.save()
        reloaded = Config(config.path)
        self.assertEqual(reloaded.theme_mode(), "light")
        self.assertEqual(reloaded.language(), "tr")

    def test_set_language_none_clears_the_key(self) -> None:
        """The language menu's English entry must call set_language(None),
        never set_language("en") -- saat_en.qm is deliberately never built
        (see saat/ui/i18n.py), so writing "en" would make main.py try to
        load a translation file that doesn't exist by design."""
        config = self._config()
        config.set_language("tr")
        config.set_language(None)
        config.save()
        self.assertIsNone(Config(config.path).language())


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
