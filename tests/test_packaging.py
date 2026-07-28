"""Packaging invariants that can be checked without dpkg.

The .deb itself is built and lintian-checked in CI (the release workflow's
`deb` job), because dpkg-deb and lintian do not exist on the machine this is
developed on. What *can* be checked anywhere is that the files feeding that
build agree with each other and with the code that reads them at runtime --
which is where packaging bugs actually come from: two copies of a .desktop
entry drifting apart, or a maintainer script quietly growing a line that
deletes a collection.
"""

import re
import stat
import unittest
from pathlib import Path

from saat import autostart

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGING = REPO_ROOT / "packaging"
DESKTOP_FILE = PACKAGING / "saat.desktop"


def _desktop_entries(text: str) -> dict[str, str]:
    entries = {}
    in_section = False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            in_section = line == "[Desktop Entry]"
            continue
        if in_section and "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            entries[key.strip()] = value.strip()
    return entries


class DesktopEntryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entries = _desktop_entries(DESKTOP_FILE.read_text(encoding="utf-8"))

    def test_required_keys_are_present(self) -> None:
        for key in ("Type", "Name", "Exec", "Icon", "Terminal", "Categories"):
            self.assertIn(key, self.entries)
        self.assertEqual(self.entries["Type"], "Application")

    def test_exec_is_the_bare_command_so_one_file_serves_both_installs(self) -> None:
        """install.sh puts the binary on PATH at /usr/local/bin/saat, the
        package at /usr/bin/saat. An absolute Exec would force two different
        .desktop files -- exactly the drift this file exists to prevent."""
        self.assertEqual(self.entries["Exec"], "saat")

    def test_icon_is_a_theme_name_not_a_path(self) -> None:
        """Both installs drop the icon into the hicolor theme, so the entry
        names it rather than pointing at a file inside the bundle."""
        self.assertEqual(self.entries["Icon"], "saat")
        self.assertNotIn("/", self.entries["Icon"])

    def test_categories_is_semicolon_terminated(self) -> None:
        """Required by the desktop-entry spec for list-typed keys, and the
        one thing desktop-file-validate reliably rejects."""
        self.assertTrue(self.entries["Categories"].endswith(";"))


class DesktopEntryIsSharedTests(unittest.TestCase):
    """One source of truth: install.sh and stage-tree.sh must both install
    packaging/saat.desktop, and neither may compose its own."""

    def test_install_sh_installs_the_shared_file(self) -> None:
        text = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn("packaging/saat.desktop", text)

    def test_install_sh_no_longer_writes_its_own_desktop_entry(self) -> None:
        text = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertNotIn("[Desktop Entry]", text)

    def test_stage_tree_installs_the_shared_file(self) -> None:
        text = (PACKAGING / "stage-tree.sh").read_text(encoding="utf-8")
        self.assertIn("packaging/saat.desktop", text)
        self.assertNotIn("[Desktop Entry]", text)

    def test_both_installs_target_the_path_autostart_reads(self) -> None:
        """autostart.py reads the installed launcher entry and re-emits it
        with --autostart appended, rather than composing a second, divergent
        .desktop file. That only works if the packaging actually puts the
        file where autostart.py looks for it."""
        target = str(autostart.INSTALLED_DESKTOP_PATH)
        self.assertEqual(target, "/usr/share/applications/saat.desktop")

        stage = (PACKAGING / "stage-tree.sh").read_text(encoding="utf-8")
        self.assertIn("usr/share/applications/saat.desktop", stage)
        install_sh = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn(target, install_sh)


class AutostartRewriteOfTheSharedEntryTests(unittest.TestCase):
    def test_appending_the_autostart_flag_produces_a_valid_entry(self) -> None:
        rewritten = autostart._with_autostart_flag(
            DESKTOP_FILE.read_text(encoding="utf-8")
        )
        entries = _desktop_entries(rewritten)
        self.assertEqual(entries["Exec"], f"saat {autostart.AUTOSTART_FLAG}")
        # Everything else survives untouched.
        self.assertEqual(entries["Name"], "SAAT")
        self.assertEqual(entries["Icon"], "saat")


class StagedLayoutTests(unittest.TestCase):
    """The FHS paths milestone 23 committed to. Asserted against the script
    that produces them so the layout cannot be quietly changed in one place
    and documented in another."""

    EXPECTED_PATHS = (
        "usr/lib/saat",
        "usr/bin/saat",
        "usr/share/applications/saat.desktop",
        "usr/share/icons/hicolor/256x256/apps/saat.png",
        "usr/share/man/man1/saat.1",
        "usr/share/doc/saat",
    )

    def setUp(self) -> None:
        self.stage = (PACKAGING / "stage-tree.sh").read_text(encoding="utf-8")

    def test_every_expected_path_is_staged(self) -> None:
        for path in self.EXPECTED_PATHS:
            self.assertIn(path, self.stage, f"{path} is not staged")

    def test_the_installed_marker_is_shipped_as_a_file(self) -> None:
        """SPEC.md §2's opt-in marker. Shipped rather than written by
        postinst, so dpkg owns it and removes it on purge."""
        self.assertRegex(self.stage, r"touch .*usr/lib/saat/\.installed")
        from saat import paths

        self.assertEqual(paths.INSTALLED_MARKER, ".installed")

    def test_usr_bin_entry_point_is_a_relative_symlink(self) -> None:
        """Debian policy 10.5: a symlink within one top-level hierarchy is
        relative. /usr/bin -> /usr/lib is within /usr."""
        self.assertRegex(self.stage, r"ln -sfn \.\./lib/saat/SAAT")

    def test_nothing_writable_by_group_or_other_is_staged(self) -> None:
        self.assertIn("find \"$stage_dir\" -type d -exec chmod 0755", self.stage)

    def test_scripts_are_executable(self) -> None:
        for name in ("stage-tree.sh",):
            mode = (PACKAGING / name).stat().st_mode
            self.assertTrue(mode & stat.S_IXUSR, f"packaging/{name} is not executable")


class ManPageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (PACKAGING / "saat.1").read_text(encoding="utf-8")

    def test_has_a_th_header_naming_section_one(self) -> None:
        self.assertRegex(self.text, r'^\.TH SAAT 1 ')

    def test_name_section_matches_the_desktop_entry_comment(self) -> None:
        """lintian checks the NAME line's shape; a human checks that it says
        the same thing the launcher entry does."""
        entries = _desktop_entries(DESKTOP_FILE.read_text(encoding="utf-8"))
        comment = entries["Comment"].lower()
        name_line = re.search(r"\.SH NAME\n(.*?)\n", self.text, re.DOTALL)
        self.assertIsNotNone(name_line)
        self.assertIn(comment, name_line.group(1).lower())

    def test_states_that_removal_keeps_the_collection(self) -> None:
        self.assertIn("does not delete", self.text)


if __name__ == "__main__":
    unittest.main()
