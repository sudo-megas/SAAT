import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from saat import paths


class PathsTestCase(unittest.TestCase):
    """Every test here runs fully isolated: SAAT_DATA_DIR, XDG_DATA_HOME and
    XDG_CONFIG_HOME are cleared (unless a test sets one itself) and HOME
    points at a throwaway tmp dir, so a mistake here creates a directory in
    scratch space, never in a real ~/.local/share or ~/.config. sys.frozen
    defaults to False (it doesn't normally exist on sys at all) so each test
    opts in to "frozen" explicitly rather than inheriting ambient state."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-paths-test-"))
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

    def _assert_under_tmp(self, path: Path) -> None:
        self.assertTrue(
            str(path).startswith(str(self.tmp)),
            f"{path} escaped the isolated tmp dir {self.tmp}",
        )

    def _freeze(self, exe_dir_name: str = "fakeapp", marker: bool = False) -> Path:
        """Simulates a frozen build whose executable lives at
        <tmp>/<exe_dir_name>/SAAT, optionally with the .installed marker
        beside it. Returns the executable's directory. Each patch is started
        and registered for cleanup individually (never patch.stopall()) so
        it unwinds in step with setUp's own patches instead of yanking them
        out from under its addCleanup(.stop) calls."""
        exe_dir = self.tmp / exe_dir_name
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


class PortableModeUnchangedTests(PathsTestCase):
    def test_from_source_resolves_to_the_repo_root_like_app_dir_did(self) -> None:
        expected = Path(paths.__file__).resolve().parent.parent
        self.assertEqual(paths.data_dir(), expected)
        self.assertEqual(paths.config_dir(), expected)

    def test_frozen_with_no_marker_resolves_beside_the_executable(self) -> None:
        exe_dir = self._freeze(marker=False)
        self.assertEqual(paths.data_dir(), exe_dir)
        self.assertEqual(paths.config_dir(), exe_dir)


class InstalledModeActivationTests(PathsTestCase):
    def test_frozen_and_marker_activates_installed_mode_under_xdg_dirs(self) -> None:
        self._freeze(marker=True)
        xdg_data = self.tmp / "xdg-data"
        xdg_config = self.tmp / "xdg-config"
        os.environ["XDG_DATA_HOME"] = str(xdg_data)
        os.environ["XDG_CONFIG_HOME"] = str(xdg_config)

        self.assertEqual(paths.data_dir(), xdg_data / "saat")
        self.assertEqual(paths.config_dir(), xdg_config / "saat")

    def test_frozen_without_marker_stays_portable(self) -> None:
        exe_dir = self._freeze(marker=False)
        os.environ["XDG_DATA_HOME"] = str(self.tmp / "xdg-data")

        self.assertEqual(paths.data_dir(), exe_dir)

    def test_marker_present_but_not_frozen_stays_portable(self) -> None:
        """The direct test of 'do not invert this': a .installed file sitting
        somewhere must never flip portable mode on by itself."""
        exe_dir = self.tmp / "fakeapp"
        exe_dir.mkdir()
        (exe_dir / paths.INSTALLED_MARKER).touch()
        # sys.frozen stays False (setUp's default) — never patched to True.
        os.environ["XDG_DATA_HOME"] = str(self.tmp / "xdg-data")

        expected = Path(paths.__file__).resolve().parent.parent
        self.assertEqual(paths.data_dir(), expected)


class XdgFallbackDefaultTests(PathsTestCase):
    def test_unset_xdg_vars_fall_back_to_home_relative_defaults(self) -> None:
        self._freeze(marker=True)
        # XDG_DATA_HOME / XDG_CONFIG_HOME already cleared by setUp.
        self.assertEqual(paths.data_dir(), self.home / ".local" / "share" / "saat")
        self.assertEqual(paths.config_dir(), self.home / ".config" / "saat")

    def test_empty_string_xdg_var_is_treated_as_unset_per_xdg_spec(self) -> None:
        self._freeze(marker=True)
        os.environ["XDG_DATA_HOME"] = ""
        self.assertEqual(paths.data_dir(), self.home / ".local" / "share" / "saat")


class SaatDataDirPrecedenceTests(PathsTestCase):
    def test_saat_data_dir_wins_over_installed_mode_and_is_not_split(self) -> None:
        self._freeze(marker=True)
        os.environ["XDG_DATA_HOME"] = str(self.tmp / "xdg-data")
        os.environ["XDG_CONFIG_HOME"] = str(self.tmp / "xdg-config")
        override = self.tmp / "override"
        os.environ["SAAT_DATA_DIR"] = str(override)

        self.assertEqual(paths.data_dir(), override)
        self.assertEqual(paths.config_dir(), override)

    def test_saat_data_dir_wins_over_portable_mode_too(self) -> None:
        override = self.tmp / "override"
        os.environ["SAAT_DATA_DIR"] = str(override)
        self.assertEqual(paths.data_dir(), override)
        self.assertEqual(paths.config_dir(), override)


class FirstRunCreationTests(PathsTestCase):
    def test_data_dir_creates_a_nonexistent_nested_path(self) -> None:
        target = self.tmp / "does" / "not" / "exist" / "yet"
        self.assertFalse(target.exists())
        os.environ["SAAT_DATA_DIR"] = str(target)

        result = paths.data_dir()

        self.assertEqual(result, target)
        self.assertTrue(result.is_dir())
        self._assert_under_tmp(result)

    def test_config_dir_creates_a_nonexistent_installed_mode_path(self) -> None:
        self._freeze(marker=True)
        xdg_config = self.tmp / "xdg-config"
        os.environ["XDG_CONFIG_HOME"] = str(xdg_config)

        result = paths.config_dir()

        self.assertTrue(result.is_dir())
        self._assert_under_tmp(result)


class ResourceDirUnaffectedTests(PathsTestCase):
    def test_saat_data_dir_does_not_affect_resource_dir(self) -> None:
        expected = paths.resource_dir()
        os.environ["SAAT_DATA_DIR"] = str(self.tmp / "override")
        self.assertEqual(paths.resource_dir(), expected)


if __name__ == "__main__":
    unittest.main()
