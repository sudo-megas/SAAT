import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from saat import autostart, paths

FIXTURE_DESKTOP_CONTENT = """[Desktop Entry]
Type=Application
Name=SAAT
Comment=Catalogue a mechanical-watch collection
Exec=/usr/local/bin/saat
Icon=saat
Terminal=false
Categories=Utility;
"""


class AutostartTestCase(unittest.TestCase):
    """Isolated the same way tests/test_paths.py is: HOME points at a
    throwaway tmp dir and SAAT_DATA_DIR/XDG_* vars are cleared unless a test
    sets one itself, so a mistake here can never touch a real
    ~/.config/autostart."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-autostart-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.home.mkdir()

        env_patch = patch.dict(os.environ, {"HOME": str(self.home)}, clear=False)
        env_patch.start()
        self.addCleanup(env_patch.stop)
        for var in ("SAAT_DATA_DIR", "XDG_DATA_HOME", "XDG_CONFIG_HOME"):
            os.environ.pop(var, None)

        frozen_patch = patch.object(sys, "frozen", False, create=True)
        frozen_patch.start()
        self.addCleanup(frozen_patch.stop)

    def _freeze(self, marker: bool = False) -> Path:
        exe_dir = self.tmp / "fakeapp"
        exe_dir.mkdir(parents=True, exist_ok=True)
        if marker:
            (exe_dir / paths.INSTALLED_MARKER).touch()

        frozen_patch = patch.object(sys, "frozen", True, create=True)
        frozen_patch.start()
        self.addCleanup(frozen_patch.stop)
        executable_patch = patch.object(sys, "executable", str(exe_dir / "SAAT"))
        executable_patch.start()
        self.addCleanup(executable_patch.stop)
        return exe_dir

    def _installed_desktop_fixture(self, content: str = FIXTURE_DESKTOP_CONTENT) -> Path:
        path = self.tmp / "installed-saat.desktop"
        path.write_text(content, encoding="utf-8")
        return path


class AvailabilityTests(AutostartTestCase):
    """SPEC.md milestone 18 §11 / §17's own explicit test requirement:
    autostart must be unavailable in portable mode."""

    def test_unavailable_in_portable_mode(self) -> None:
        self.assertFalse(autostart.is_available())

    def test_available_once_frozen_and_marked_installed(self) -> None:
        self._freeze(marker=True)
        self.assertTrue(autostart.is_available())

    def test_still_unavailable_when_frozen_without_the_installed_marker(self) -> None:
        self._freeze(marker=False)
        self.assertFalse(autostart.is_available())


class AutostartDirResolutionTests(AutostartTestCase):
    def test_defaults_to_home_config_autostart(self) -> None:
        self.assertEqual(autostart.autostart_path(), self.home / ".config" / "autostart" / "saat.desktop")

    def test_honours_xdg_config_home_when_set(self) -> None:
        custom = self.tmp / "custom-xdg"
        os.environ["XDG_CONFIG_HOME"] = str(custom)
        self.assertEqual(autostart.autostart_path(), custom / "autostart" / "saat.desktop")

    def test_empty_xdg_config_home_is_treated_as_unset(self) -> None:
        os.environ["XDG_CONFIG_HOME"] = ""
        self.assertEqual(autostart.autostart_path(), self.home / ".config" / "autostart" / "saat.desktop")

    def test_is_not_namespaced_under_the_apps_own_config_dir(self) -> None:
        """The sanctioned exception SPEC.md §2 rule 2 now names: this is a
        shared directory every autostart app writes into, not saat/'s own
        config_dir()."""
        self.assertNotIn("saat", autostart.autostart_path().parts[:-1])


class EnabledReflectsDiskTests(AutostartTestCase):
    def test_disabled_when_no_entry_exists(self) -> None:
        self.assertFalse(autostart.is_enabled())

    def test_enabled_once_the_file_exists(self) -> None:
        target = autostart.autostart_path()
        target.parent.mkdir(parents=True)
        target.write_text("anything", encoding="utf-8")
        self.assertTrue(autostart.is_enabled())


class EnableTests(AutostartTestCase):
    def test_raises_if_the_installed_desktop_file_is_missing(self) -> None:
        missing = self.tmp / "does-not-exist.desktop"
        with patch.object(autostart, "INSTALLED_DESKTOP_PATH", missing):
            with self.assertRaises(FileNotFoundError):
                autostart.enable()

    def test_writes_the_autostart_entry_with_the_flag_appended_to_exec(self) -> None:
        fixture = self._installed_desktop_fixture()
        with patch.object(autostart, "INSTALLED_DESKTOP_PATH", fixture):
            autostart.enable()

        written = autostart.autostart_path().read_text(encoding="utf-8")
        self.assertIn("Exec=/usr/local/bin/saat --autostart\n", written)

    def test_reuses_every_other_line_verbatim(self) -> None:
        """SPEC.md milestone 18 §12: reuse the file install.sh produces
        rather than composing a second, divergent one -- Name/Comment/Icon/
        Categories must survive untouched."""
        fixture = self._installed_desktop_fixture()
        with patch.object(autostart, "INSTALLED_DESKTOP_PATH", fixture):
            autostart.enable()

        written = autostart.autostart_path().read_text(encoding="utf-8")
        for line in FIXTURE_DESKTOP_CONTENT.splitlines():
            if line.startswith("Exec="):
                continue
            self.assertIn(line, written)

    def test_creates_the_autostart_directory_if_missing(self) -> None:
        fixture = self._installed_desktop_fixture()
        self.assertFalse(autostart.autostart_path().parent.exists())
        with patch.object(autostart, "INSTALLED_DESKTOP_PATH", fixture):
            autostart.enable()
        self.assertTrue(autostart.is_enabled())

    def test_enabling_twice_does_not_double_append_the_flag(self) -> None:
        fixture = self._installed_desktop_fixture()
        with patch.object(autostart, "INSTALLED_DESKTOP_PATH", fixture):
            autostart.enable()
            autostart.enable()

        written = autostart.autostart_path().read_text(encoding="utf-8")
        self.assertEqual(written.count("--autostart"), 1)


class DisableTests(AutostartTestCase):
    def test_removes_an_existing_entry(self) -> None:
        target = autostart.autostart_path()
        target.parent.mkdir(parents=True)
        target.write_text("anything", encoding="utf-8")

        autostart.disable()

        self.assertFalse(target.exists())

    def test_is_a_no_op_when_nothing_exists(self) -> None:
        autostart.disable()
        self.assertFalse(autostart.is_enabled())


if __name__ == "__main__":
    unittest.main()
