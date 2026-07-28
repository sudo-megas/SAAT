"""Invariants that exist because SAAT runs on more than one platform.

Every one of these is enforced on EVERY platform, not conditionally on the
one that needs it, and that is the point rather than an implementation
convenience: a collection is a folder of plain files that gets copied
between machines, put on a USB stick, and synced. A rule applied only on
Windows produces collections Linux can create and Windows cannot open,
which is the same bug from the other end.

So these tests do not skip on Linux. They assert the Linux behaviour is
already the portable one.
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tomlkit

from saat import atomic, paths, storage
from saat.models import Watch


class WindowsInstalledPathsTests(unittest.TestCase):
    """%LOCALAPPDATA%\\SAAT and %APPDATA%\\SAAT, reached by patching the
    platform flag rather than by skipping — the resolution logic is
    testable anywhere, and the point is that it is correct before anyone
    has a Windows machine to try it on."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-winpaths-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.home.mkdir()

        env = patch.dict(
            os.environ,
            {"HOME": str(self.home), "USERPROFILE": str(self.home)},
            clear=False,
        )
        env.start()
        self.addCleanup(env.stop)
        # USERPROFILE is deliberately NOT cleared here -- it was just set to
        # the isolated home above, and Path.home() reads it on Windows.
        for var in (
            "SAAT_DATA_DIR", "XDG_DATA_HOME", "XDG_CONFIG_HOME",
            "LOCALAPPDATA", "APPDATA",
        ):
            os.environ.pop(var, None)

        windows = patch.object(paths, "_WINDOWS", True)
        windows.start()
        self.addCleanup(windows.stop)

    def _freeze_installed(self) -> Path:
        exe_dir = self.tmp / "Programs" / "SAAT"
        exe_dir.mkdir(parents=True)
        (exe_dir / paths.INSTALLED_MARKER).touch()
        frozen = patch.object(sys, "frozen", True, create=True)
        frozen.start()
        self.addCleanup(frozen.stop)
        executable = patch.object(sys, "executable", str(exe_dir / "SAAT.exe"))
        executable.start()
        self.addCleanup(executable.stop)
        return exe_dir

    def test_installed_mode_uses_localappdata_for_data(self) -> None:
        self._freeze_installed()
        local = self.tmp / "AppData" / "Local"
        os.environ["LOCALAPPDATA"] = str(local)
        os.environ["APPDATA"] = str(self.tmp / "AppData" / "Roaming")

        self.assertEqual(paths.data_dir(), local / "SAAT")

    def test_installed_mode_uses_appdata_for_config(self) -> None:
        self._freeze_installed()
        roaming = self.tmp / "AppData" / "Roaming"
        os.environ["LOCALAPPDATA"] = str(self.tmp / "AppData" / "Local")
        os.environ["APPDATA"] = str(roaming)

        self.assertEqual(paths.config_dir(), roaming / "SAAT")

    def test_data_and_config_are_different_directories(self) -> None:
        """The split is the whole reason for using two Windows variables:
        a collection with its photographs belongs to the machine, settings
        follow the profile."""
        self._freeze_installed()
        os.environ["LOCALAPPDATA"] = str(self.tmp / "AppData" / "Local")
        os.environ["APPDATA"] = str(self.tmp / "AppData" / "Roaming")

        self.assertNotEqual(paths.data_dir(), paths.config_dir())

    def test_unset_variables_fall_back_to_the_profile_not_to_c_users(self) -> None:
        """A profile is not always on C:, and a redirected or domain
        profile routinely is not."""
        self._freeze_installed()
        # LOCALAPPDATA / APPDATA already cleared in setUp.
        self.assertEqual(
            paths.data_dir(), self.home / "AppData" / "Local" / "SAAT"
        )
        self.assertEqual(
            paths.config_dir(), self.home / "AppData" / "Roaming" / "SAAT"
        )

    def test_empty_variable_is_treated_as_unset(self) -> None:
        self._freeze_installed()
        os.environ["LOCALAPPDATA"] = ""
        self.assertEqual(
            paths.data_dir(), self.home / "AppData" / "Local" / "SAAT"
        )

    def test_saat_data_dir_still_overrides_everything(self) -> None:
        self._freeze_installed()
        os.environ["LOCALAPPDATA"] = str(self.tmp / "AppData" / "Local")
        override = self.tmp / "override"
        os.environ["SAAT_DATA_DIR"] = str(override)

        self.assertEqual(paths.data_dir(), override)
        self.assertEqual(paths.config_dir(), override)

    def test_portable_mode_is_unchanged_on_windows(self) -> None:
        """Portable means beside the executable, on every platform. A
        portable copy on a USB stick must behave identically whichever
        machine it is plugged into."""
        exe_dir = self.tmp / "PortableSAAT"
        exe_dir.mkdir()
        frozen = patch.object(sys, "frozen", True, create=True)
        frozen.start()
        self.addCleanup(frozen.stop)
        executable = patch.object(sys, "executable", str(exe_dir / "SAAT.exe"))
        executable.start()
        self.addCleanup(executable.stop)
        os.environ["LOCALAPPDATA"] = str(self.tmp / "AppData" / "Local")

        self.assertEqual(paths.data_dir(), exe_dir)
        self.assertEqual(paths.config_dir(), exe_dir)

    def test_marker_is_still_required_on_windows(self) -> None:
        """The marker opts IN; portable never opts OUT. %LOCALAPPDATA%
        existing must never be enough on its own."""
        exe_dir = self.tmp / "PortableSAAT"
        exe_dir.mkdir()
        frozen = patch.object(sys, "frozen", True, create=True)
        frozen.start()
        self.addCleanup(frozen.stop)
        executable = patch.object(sys, "executable", str(exe_dir / "SAAT.exe"))
        executable.start()
        self.addCleanup(executable.stop)
        os.environ["LOCALAPPDATA"] = str(self.tmp / "AppData" / "Local")

        self.assertFalse(paths.is_installed())
        self.assertEqual(paths.data_dir(), exe_dir)


class CaseInsensitiveSlugTests(unittest.TestCase):
    """Two slugs differing only by case are two folders on ext4 and one on
    NTFS. Generated slugs are lowercased so they cannot collide by case on
    their own — the exposure is hand-authored folders, which SPEC.md §3
    explicitly supports."""

    def test_a_hand_authored_uppercase_folder_is_seen_as_taken(self) -> None:
        slug = storage.unique_slug("Seiko", "SKX007", {"Seiko-SKX007"})
        self.assertNotEqual(slug.casefold(), "seiko-skx007")
        self.assertEqual(slug, "seiko-skx007-2")

    def test_mixed_case_existing_names_are_all_considered(self) -> None:
        existing = {"seiko-skx007", "SEIKO-SKX007-2", "Seiko-Skx007-3"}
        slug = storage.unique_slug("Seiko", "SKX007", existing)
        self.assertEqual(slug, "seiko-skx007-4")

    def test_exact_case_collision_still_works_as_before(self) -> None:
        self.assertEqual(
            storage.unique_slug("Seiko", "SKX007", {"seiko-skx007"}),
            "seiko-skx007-2",
        )

    def test_no_collision_returns_the_plain_slug(self) -> None:
        self.assertEqual(storage.unique_slug("Seiko", "SKX007", set()), "seiko-skx007")

    def test_create_watch_does_not_reuse_a_case_variant_folder(self) -> None:
        """The end-to-end version: a collection carrying a hand-made
        `Seiko-SKX007` must not have a new watch written into it."""
        tmp = Path(tempfile.mkdtemp(prefix="saat-case-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        watches = tmp / "watches"
        (watches / "Seiko-SKX007").mkdir(parents=True)
        (watches / "Seiko-SKX007" / "watch.toml").write_text(
            'brand = "Seiko"\nmodel = "SKX007"\n', encoding="utf-8"
        )

        record = storage.create_watch(
            watches, tmp / "backups", Watch(brand="Seiko", model="SKX007")
        )

        self.assertNotEqual(record.path.name.casefold(), "seiko-skx007")
        self.assertTrue((watches / "Seiko-SKX007" / "watch.toml").exists())


class ReservedAndIllegalFilenameTests(unittest.TestCase):
    """Windows forbids nine characters in a filename and reserves the DOS
    device names as whole components. A brand or model producing one must
    not produce an unwritable folder."""

    def test_every_forbidden_character_is_removed(self) -> None:
        for character in '<>:"/\\|?*':
            slug = storage.slugify(f"Bad{character}Brand", "Model")
            self.assertNotIn(character, slug, f"{character!r} survived slugify")

    def test_reserved_device_names_are_suffixed(self) -> None:
        for reserved in ("con", "prn", "aux", "nul", "com1", "com9", "lpt1", "lpt9"):
            slug = storage.slugify(reserved, "")
            self.assertNotEqual(
                slug, reserved, f"{reserved} is an unwritable folder name on Windows"
            )
            self.assertTrue(slug.startswith(reserved))

    def test_reserved_names_are_matched_case_insensitively(self) -> None:
        """slugify lowercases first, so CON and Con reach the check as
        `con` — asserted rather than assumed, since the check is a set
        membership on the lowercased form."""
        for spelling in ("CON", "Con", "cOn"):
            self.assertNotEqual(storage.slugify(spelling, ""), "con")

    def test_a_reserved_name_with_a_real_model_is_untouched(self) -> None:
        """`con` is only reserved as the entire component. `con-divers` is
        a perfectly good folder."""
        self.assertEqual(storage.slugify("Con", "Divers"), "con-divers")

    def test_names_that_are_entirely_invalid_fall_back(self) -> None:
        self.assertEqual(storage.slugify("???", "***"), "watch")

    def test_trailing_dots_and_spaces_cannot_survive(self) -> None:
        """Windows silently strips both, so a folder created as `seiko.`
        would be opened as `seiko` and the two would alias."""
        for name in ("Seiko.", "Seiko ", "Seiko...", "Seiko . . "):
            slug = storage.slugify(name, "SKX")
            self.assertFalse(slug.endswith((".", " ", "-")))

    def test_a_very_long_name_is_capped(self) -> None:
        slug = storage.slugify("Brand " * 40, "Model " * 40)
        self.assertLessEqual(len(slug), storage._SLUG_MAX_LENGTH)
        self.assertFalse(slug.endswith("-"))

    def test_capping_can_collide_and_unique_slug_resolves_it(self) -> None:
        long_brand = "Seiko Prospex Marinemaster Professional Diver " * 3
        first = storage.unique_slug(long_brand, "300m", set())
        second = storage.unique_slug(long_brand, "300m", {first})
        self.assertNotEqual(first, second)


class AtomicReplaceRetryTests(unittest.TestCase):
    """os.replace over a destination another process holds open raises
    PermissionError on Windows. Antivirus scanners and the search indexer
    do exactly that, for milliseconds, unpredictably, right after a file is
    written."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-atomic-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.target = self.tmp / "watch.toml"
        self.tmp_file = self.tmp / "watch.toml.tmp"

    def test_a_transiently_locked_destination_succeeds_after_retrying(self) -> None:
        real_replace = os.replace
        calls = {"n": 0}

        def flaky(src, dst):
            calls["n"] += 1
            if calls["n"] < 3:
                raise PermissionError(13, "The process cannot access the file")
            return real_replace(src, dst)

        with patch.object(atomic.os, "replace", flaky):
            atomic.write_atomic(self.target, "brand = 'Seiko'\n")

        self.assertEqual(calls["n"], 3)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "brand = 'Seiko'\n")
        self.assertFalse(self.tmp_file.exists())

    def test_a_permanently_locked_destination_surfaces_the_error(self) -> None:
        """SPEC.md §2 rule 7: never silently swallow. Retrying is not
        swallowing — the error still arrives, just later."""
        def always_locked(src, dst):
            raise PermissionError(13, "The process cannot access the file")

        with patch.object(atomic.os, "replace", always_locked):
            with self.assertRaises(PermissionError):
                atomic.write_atomic(self.target, "brand = 'Seiko'\n")

    def test_no_tmp_file_is_left_behind_when_the_replace_never_succeeds(self) -> None:
        def always_locked(src, dst):
            raise PermissionError(13, "locked")

        with patch.object(atomic.os, "replace", always_locked):
            with self.assertRaises(PermissionError):
                atomic.write_atomic(self.target, "brand = 'Seiko'\n")

        self.assertFalse(
            self.tmp_file.exists(),
            "an orphaned .tmp in a watch folder looks like corruption",
        )

    def test_no_tmp_file_is_left_behind_when_the_write_itself_fails(self) -> None:
        with patch.object(atomic.os, "fsync", side_effect=OSError("disk gone")):
            with self.assertRaises(OSError):
                atomic.write_atomic(self.target, "brand = 'Seiko'\n")

        self.assertFalse(self.tmp_file.exists())

    def test_it_gives_up_after_a_bounded_number_of_attempts(self) -> None:
        calls = {"n": 0}

        def always_locked(src, dst):
            calls["n"] += 1
            raise PermissionError(13, "locked")

        with patch.object(atomic.os, "replace", always_locked):
            with self.assertRaises(PermissionError):
                atomic.write_atomic(self.target, "x = 1\n")

        self.assertEqual(calls["n"], atomic.REPLACE_ATTEMPTS)

    def test_an_unrelated_oserror_is_not_retried(self) -> None:
        """Only the Windows sharing violation is worth waiting out. A full
        disk should fail immediately, not 300 ms later."""
        calls = {"n": 0}

        def no_space(src, dst):
            calls["n"] += 1
            raise OSError(28, "No space left on device")

        with patch.object(atomic.os, "replace", no_space):
            with self.assertRaises(OSError):
                atomic.write_atomic(self.target, "x = 1\n")

        self.assertEqual(calls["n"], 1)

    def test_the_happy_path_replaces_exactly_once(self) -> None:
        atomic.write_atomic(self.target, "a = 1\n")
        atomic.write_atomic(self.target, "a = 2\n")
        self.assertEqual(self.target.read_text(encoding="utf-8"), "a = 2\n")
        self.assertFalse(self.tmp_file.exists())


class CrossPlatformCollectionTests(unittest.TestCase):
    """A collection written on one platform must load on the other. The
    storage format is plain UTF-8 TOML, so the only thing that genuinely
    differs is line endings."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-crossplat-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.watches = self.tmp / "watches"
        self.watches.mkdir()

    def _write(self, slug: str, text: str) -> None:
        folder = self.watches / slug
        folder.mkdir()
        # newline="" so the exact bytes given are what lands on disk,
        # rather than Python translating them for the host platform.
        with open(folder / "watch.toml", "w", encoding="utf-8", newline="") as handle:
            handle.write(text)

    def test_a_crlf_watch_toml_loads(self) -> None:
        """What a Windows text editor produces after someone hand-edits a
        note in their collection."""
        self._write("seiko-skx007", 'brand = "Seiko"\r\nmodel = "SKX007"\r\n')

        records = storage.load_collection(self.watches)

        self.assertEqual(len(records), 1)
        self.assertIsNone(records[0].load_error)
        self.assertEqual(records[0].watch.brand, "Seiko")

    def test_an_lf_watch_toml_loads(self) -> None:
        self._write("seiko-skx009", 'brand = "Seiko"\nmodel = "SKX009"\n')

        records = storage.load_collection(self.watches)

        self.assertEqual(len(records), 1)
        self.assertIsNone(records[0].load_error)

    def test_crlf_comments_survive_a_round_trip(self) -> None:
        """SPEC.md §3: a hand-written comment must still be there after the
        app saves the file. That promise cannot be conditional on which
        platform typed the comment."""
        self._write(
            "seiko-skx007",
            'brand = "Seiko"\r\nmodel = "SKX007"\r\n'
            "# accuracy not published by the manufacturer\r\n",
        )

        record = storage.load_collection(self.watches)[0]
        record.watch.reference = "SKX007J1"
        storage.save_watch(self.tmp / "backups", record, backup=False)

        saved = (self.watches / "seiko-skx007" / "watch.toml").read_text(
            encoding="utf-8"
        )
        self.assertIn("accuracy not published by the manufacturer", saved)
        self.assertIn("SKX007J1", saved)

    def test_a_saved_file_is_valid_toml_whatever_it_was_written_with(self) -> None:
        self._write("a-watch", 'brand = "A"\r\nmodel = "B"\r\n')
        record = storage.load_collection(self.watches)[0]
        storage.save_watch(self.tmp / "backups", record, backup=False)

        text = (self.watches / "a-watch" / "watch.toml").read_text(encoding="utf-8")
        parsed = tomlkit.parse(text)
        self.assertEqual(parsed["brand"], "A")


if __name__ == "__main__":
    unittest.main()
