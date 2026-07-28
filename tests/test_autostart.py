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
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-autostart-test-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.home.mkdir()

        env_patch = patch.dict(
            os.environ,
            {"HOME": str(self.home), "USERPROFILE": str(self.home)},
            clear=False,
        )
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


class WindowsStartupShortcutTests(AutostartTestCase):
    """Milestone 24 §8: on Windows the autostart entry is a shortcut in the
    per-user Startup folder, not a registry Run key. Tested by patching the
    platform flag rather than skipping, so the logic is verified before
    anyone has a Windows machine to try it on -- and so a later refactor
    cannot quietly break the Windows half while the Linux half stays green.

    What is NOT verified here, and cannot be from Linux: that the .lnk
    PowerShell produces is one Explorer actually honours at login. That is
    in the milestone's manual-verification list, unperformed."""

    def setUp(self) -> None:
        super().setUp()
        windows = patch.object(autostart, "_WINDOWS", True)
        windows.start()
        self.addCleanup(windows.stop)
        paths_windows = patch.object(paths, "_WINDOWS", True)
        paths_windows.start()
        self.addCleanup(paths_windows.stop)

        self.appdata = self.tmp / "AppData" / "Roaming"
        os.environ["APPDATA"] = str(self.appdata)
        os.environ["LOCALAPPDATA"] = str(self.tmp / "AppData" / "Local")
        self.addCleanup(os.environ.pop, "APPDATA", None)
        self.addCleanup(os.environ.pop, "LOCALAPPDATA", None)

        self.startup = (
            self.appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        )

    def test_the_entry_is_a_shortcut_in_the_startup_folder(self) -> None:
        self.assertEqual(autostart.autostart_path(), self.startup / "SAAT.lnk")

    def test_it_is_not_namespaced_under_the_apps_own_config_dir(self) -> None:
        """Same reasoning as the XDG case: the Startup folder is shared
        with every other app that starts at login, and is not this app's
        config directory."""
        self._freeze(marker=True)
        self.assertNotIn(str(paths.config_dir()), str(autostart.autostart_path()))

    def test_unset_appdata_falls_back_to_the_profile(self) -> None:
        os.environ.pop("APPDATA", None)
        self.assertEqual(
            autostart.autostart_path(),
            self.home
            / "AppData"
            / "Roaming"
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
            / "Startup"
            / "SAAT.lnk",
        )

    def test_availability_is_still_gated_on_installed_mode(self) -> None:
        """A portable copy on a USB stick registering itself to start at
        boot is as incoherent on Windows as on Linux."""
        self.assertFalse(autostart.is_available())
        self._freeze(marker=True)
        self.assertTrue(autostart.is_available())

    def test_enabled_reflects_whether_the_shortcut_exists(self) -> None:
        self.assertFalse(autostart.is_enabled())
        self.startup.mkdir(parents=True)
        (self.startup / "SAAT.lnk").write_bytes(b"")
        self.assertTrue(autostart.is_enabled())

    def test_a_user_deleting_the_shortcut_by_hand_disables_it(self) -> None:
        """is_enabled() is a stat(), never a stored flag -- someone who
        clears out their Startup folder in Explorer has disabled autostart,
        and the tray menu must agree with them."""
        self.startup.mkdir(parents=True)
        shortcut = self.startup / "SAAT.lnk"
        shortcut.write_bytes(b"")
        self.assertTrue(autostart.is_enabled())
        shortcut.unlink()
        self.assertFalse(autostart.is_enabled())

    def _fake_powershell(self, returncode: int = 0, create: bool = True):
        calls = {}

        def run(argv, **kwargs):
            calls["argv"] = argv
            calls["env"] = kwargs.get("env", {})
            calls["creationflags"] = kwargs.get("creationflags")
            if create and returncode == 0:
                target = Path(calls["env"]["SAAT_LNK_PATH"])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"fake shortcut")

            class Completed:
                pass

            completed = Completed()
            completed.returncode = returncode
            completed.stdout = ""
            completed.stderr = "" if returncode == 0 else "CreateShortcut failed"
            return completed

        return run, calls

    def test_enable_creates_the_shortcut_via_powershell(self) -> None:
        exe_dir = self._freeze(marker=True)
        run, calls = self._fake_powershell()
        with patch.object(autostart.subprocess, "run", run):
            autostart.enable()

        self.assertTrue(autostart.is_enabled())
        self.assertEqual(calls["argv"][0], "powershell")
        self.assertIn("-NoProfile", calls["argv"])
        self.assertIn("CreateShortcut", calls["argv"][-1])

    def test_paths_are_passed_through_the_environment_not_interpolated(self) -> None:
        """A user's own name sits inside %APPDATA%. A path containing a
        quote, a backtick or a $ must not be able to break the PowerShell
        command or be interpreted by it, so nothing is interpolated into
        the script text."""
        exe_dir = self._freeze(marker=True)
        run, calls = self._fake_powershell()
        with patch.object(autostart.subprocess, "run", run):
            autostart.enable()

        script = calls["argv"][-1]
        self.assertNotIn(str(self.startup), script)
        self.assertNotIn(str(exe_dir), script)
        self.assertEqual(calls["env"]["SAAT_LNK_PATH"], str(self.startup / "SAAT.lnk"))
        self.assertEqual(calls["env"]["SAAT_LNK_TARGET"], str(exe_dir / "SAAT"))

    def test_the_shortcut_carries_the_autostart_flag(self) -> None:
        """should_start_hidden() must be able to tell an autostarted launch
        from a manual one, exactly as the XDG Exec= line does."""
        self._freeze(marker=True)
        run, calls = self._fake_powershell()
        with patch.object(autostart.subprocess, "run", run):
            autostart.enable()

        self.assertEqual(calls["env"]["SAAT_LNK_ARGS"], autostart.AUTOSTART_FLAG)

    def test_no_console_window_flashes_up(self) -> None:
        self._freeze(marker=True)
        run, calls = self._fake_powershell()
        with patch.object(autostart.subprocess, "run", run):
            autostart.enable()
        self.assertEqual(
            calls["creationflags"], getattr(autostart.subprocess, "CREATE_NO_WINDOW", 0)
        )

    def test_a_powershell_failure_is_surfaced_not_swallowed(self) -> None:
        """SPEC.md §2 rule 7. MainWindow shows this in a dialog."""
        self._freeze(marker=True)
        run, _ = self._fake_powershell(returncode=1, create=False)
        with patch.object(autostart.subprocess, "run", run):
            with self.assertRaises(OSError) as caught:
                autostart.enable()
        self.assertIn("CreateShortcut failed", str(caught.exception))

    def test_a_silent_failure_to_produce_the_file_is_also_caught(self) -> None:
        """Exit code 0 but no shortcut on disk still has to be an error --
        otherwise the menu item would report enabled when nothing was."""
        self._freeze(marker=True)
        run, _ = self._fake_powershell(returncode=0, create=False)
        with patch.object(autostart.subprocess, "run", run):
            with self.assertRaises(OSError):
                autostart.enable()

    def test_disable_removes_the_shortcut(self) -> None:
        self.startup.mkdir(parents=True)
        (self.startup / "SAAT.lnk").write_bytes(b"")
        autostart.disable()
        self.assertFalse(autostart.is_enabled())

    def test_disable_is_a_no_op_when_nothing_exists(self) -> None:
        autostart.disable()
        self.assertFalse(autostart.is_enabled())

    def test_no_registry_is_touched_anywhere_in_this_module(self) -> None:
        """Milestone 24 §8 chose the Startup folder over an HKCU Run key on
        purpose, and the DO-NOT list bans writing to the registry beyond
        what Inno Setup needs for its own uninstaller entry."""
        source = Path(autostart.__file__).read_text(encoding="utf-8")
        for forbidden in ("winreg", "HKEY_", "reg add", "Set-ItemProperty"):
            self.assertNotIn(forbidden, source)
