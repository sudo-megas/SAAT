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


class MaintainerScriptDataSafetyTests(unittest.TestCase):
    """The single most important rule in milestone 23: removing or purging
    the package must never delete a collection.

    Checked statically rather than trusted, because the failure mode is
    unrecoverable and silent -- a user types `apt purge saat`, and years of
    hand-entered watches, photographs and wear history are gone. The
    end-to-end proof is in CI (the deb job plants a file under a fake
    ~/.local/share/saat and purges); this is the cheap guard that catches a
    dangerous line the moment it is written, without needing dpkg.

    The rule is absolute. If a future change makes one of these fail, the
    change is wrong -- not the test."""

    SCRIPTS = ("postinst", "prerm", "postrm")

    # Anything that could reach into a user's home. Maintainer scripts run
    # as root and dpkg gives them no reliable notion of "the user", so
    # there is no correct way to use any of these here -- which is why the
    # absence of all of them is the check.
    FORBIDDEN = (
        ".local/share",
        ".config",
        "XDG_DATA_HOME",
        "XDG_CONFIG_HOME",
        "SUDO_USER",
        "getent passwd",
        "/home/",
        "$HOME",
        "~/",
    )

    def _body(self, name: str) -> str:
        """Comment lines stripped: postrm's own comments name these paths
        at length precisely to explain why it must not touch them, and a
        naive substring search over the whole file would flag that."""
        text = (PACKAGING / "debian" / name).read_text(encoding="utf-8")
        return "\n".join(
            line for line in text.splitlines() if not line.lstrip().startswith("#")
        )

    def test_no_maintainer_script_can_reach_into_a_users_home(self) -> None:
        for name in self.SCRIPTS:
            body = self._body(name)
            for needle in self.FORBIDDEN:
                self.assertNotIn(
                    needle,
                    body,
                    f"{name} references {needle!r} -- maintainer scripts must "
                    "never touch user data",
                )

    def test_no_maintainer_script_removes_anything_recursively(self) -> None:
        for name in self.SCRIPTS:
            body = self._body(name)
            self.assertNotIn("rm -r", body, f"{name} contains a recursive remove")
            self.assertNotIn("rm -f", body, f"{name} removes files")
            self.assertNotIn("rmdir", body, f"{name} removes directories")
            self.assertNotIn("shutil.rmtree", body)

    def test_postrm_handles_purge_without_deleting_anything(self) -> None:
        body = self._body("postrm")
        self.assertIn("purge", body, "postrm must handle the purge case explicitly")
        # The only actions it may take are the two cache refreshes.
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith(("update-desktop-database", "gtk-update-icon-cache")):
                continue
            self.assertNotRegex(
                stripped,
                r"(^|[;&|(]\s*)(rm|rmdir|find|shred|unlink)\b",
                f"postrm deletes something: {stripped}",
            )

    def test_every_script_is_executable_and_a_posix_shell_script(self) -> None:
        for name in self.SCRIPTS:
            path = PACKAGING / "debian" / name
            self.assertTrue(path.stat().st_mode & stat.S_IXUSR, f"{name} not executable")
            first = path.read_text(encoding="utf-8").splitlines()[0]
            self.assertEqual(first, "#!/bin/sh")

    def test_every_script_sets_e_and_rejects_unknown_arguments(self) -> None:
        """Debian policy: a maintainer script must fail on an argument it
        does not understand rather than silently doing nothing, and must
        not continue past an error."""
        for name in self.SCRIPTS:
            body = self._body(name)
            self.assertRegex(
                body, r"(?m)^set -e$", f"{name} does not set -e"
            )
            self.assertIn("exit 1", body, f"{name} does not reject unknown arguments")

    def test_desktop_integration_commands_are_guarded(self) -> None:
        """Requirement: neither update-desktop-database nor
        gtk-update-icon-cache is guaranteed present, and neither is worth a
        hard dependency, so both are called only if they exist."""
        for name in ("postinst", "postrm"):
            body = self._body(name)
            for command in ("update-desktop-database", "gtk-update-icon-cache"):
                self.assertIn(f"command -v {command}", body, f"{name}: {command} unguarded")


class ControlFileTests(unittest.TestCase):
    def setUp(self) -> None:
        text = (PACKAGING / "debian" / "control.in").read_text(encoding="utf-8")
        self.fields = {}
        for line in text.splitlines():
            if line and not line.startswith(" ") and ":" in line:
                key, _, value = line.partition(":")
                self.fields[key] = value.strip()
        self.text = text

    def test_required_fields(self) -> None:
        self.assertEqual(self.fields["Package"], "saat")
        self.assertEqual(self.fields["Section"], "utils")
        self.assertEqual(self.fields["Priority"], "optional")
        self.assertEqual(self.fields["Architecture"], "amd64")
        self.assertRegex(self.fields["Maintainer"], r"^.+ <[^@]+@[^>]+>$")

    def test_description_has_a_short_line_and_an_indented_long_part(self) -> None:
        self.assertTrue(self.fields["Description"])
        self.assertFalse(self.fields["Description"].endswith("."))
        long_part = self.text.split("Description:")[1].splitlines()[1:]
        self.assertTrue(long_part, "Description has no long part")
        for line in long_part:
            self.assertTrue(line.startswith(" "), f"unindented long line: {line!r}")

    def test_description_states_the_size_cost_honestly(self) -> None:
        """Requirement 1: the bundled runtime's size is noted in the
        description rather than discovered at install time."""
        description = self.text.split("Description:")[1]
        self.assertIn("MB", description)
        self.assertIn("Qt", description)

    def test_description_states_that_removal_keeps_the_collection(self) -> None:
        description = self.text.split("Description:")[1]
        self.assertIn("never deletes", description)

    def test_depends_is_present_and_minimal(self) -> None:
        """A dependency list this short is the point -- the bundle carries
        Qt and Python itself. The build-time audit proves it is *complete*;
        this pins that it has not quietly grown."""
        depends = [d.strip() for d in self.fields["Depends"].split(",")]
        self.assertIn("libc6 (>= 2.35)", depends)
        # Every entry is a soname the bundle genuinely needs -- most of them
        # Qt's xcb platform plugin, without which the app does not start on
        # an X11 session. audit-bundle.py proves the list is COMPLETE at
        # build time; this pins that it has not grown a system Qt or a
        # system Python behind anyone's back.
        self.assertLessEqual(len(depends), 20, f"Depends has grown: {depends}")
        for entry in depends:
            self.assertNotIn("qt", entry.lower(), "must not depend on system Qt")
            self.assertNotIn("pyside", entry.lower(), "must not depend on system PySide6")
            self.assertNotIn("python3-", entry, "must not depend on a system Python")

    def test_version_is_substituted_not_hardcoded(self) -> None:
        self.assertEqual(self.fields["Version"], "@VERSION@")
        self.assertEqual(self.fields["Installed-Size"], "@INSTALLED_SIZE@")


class CopyrightFileTests(unittest.TestCase):
    """DEP-5, and the file that makes a package bundling Qt, CPython and
    thirty-odd C libraries legally distributable. Its completeness against
    a given build is enforced at build time by audit-bundle.py; what is
    checked here is that it is well-formed and names the licences that must
    be there whatever the build contains."""

    def setUp(self) -> None:
        self.text = (PACKAGING / "debian" / "copyright").read_text(encoding="utf-8")

    def test_declares_the_dep5_format(self) -> None:
        first = self.text.splitlines()[0]
        self.assertEqual(
            first,
            "Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/",
        )

    def test_covers_the_application_as_gpl3_or_later(self) -> None:
        self.assertIn("Files: *", self.text)
        self.assertIn("License: GPL-3+", self.text)

    def test_covers_the_bundled_qt_as_lgpl3(self) -> None:
        self.assertIn("License: LGPL-3", self.text)
        self.assertIn("libQt6*", self.text)

    def test_covers_the_bundled_ubuntu_fonts(self) -> None:
        self.assertIn("UbuntuFontLicence-1.0", self.text)

    def test_covers_the_bundled_python_runtime(self) -> None:
        self.assertIn("PSF-2.0", self.text)

    def test_covers_the_qt_flow_layout_example(self) -> None:
        """saat/ui/flow_layout.py is adapted from Qt's own example and is
        BSD-3-clause, not GPL like the rest of the application."""
        self.assertIn("saat/ui/flow_layout.py", self.text)
        self.assertIn("BSD-3-clause", self.text)

    def test_every_referenced_license_has_a_standalone_paragraph(self) -> None:
        referenced = set()
        for line in self.text.splitlines():
            if line.startswith("License:"):
                value = line.partition(":")[2].strip()
                if not value:
                    continue
                for name in re.split(r"\s+(?:or|and)\s+", value):
                    referenced.add(name.strip())

        # A standalone License paragraph starts its own paragraph -- the
        # line above it is blank. Inside a Files stanza, License: always
        # follows Copyright: or one of its continuation lines directly.
        defined = set()
        lines = self.text.splitlines()
        for index, line in enumerate(lines):
            if not line.startswith("License:"):
                continue
            if index > 0 and lines[index - 1].strip():
                continue
            defined.add(line.partition(":")[2].strip())

        missing = sorted(name for name in referenced if name not in defined)
        self.assertEqual(missing, [], f"licences referenced but never defined: {missing}")

    def test_qt_is_documented_as_dynamically_linked(self) -> None:
        """The LGPL-3's terms for a combined work are satisfied by dynamic
        linking, which is why SAAT.spec is one-folder rather than one-file.
        Saying so is part of complying."""
        self.assertIn("dynamically linked", self.text)


class LintianOverrideTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (PACKAGING / "debian" / "lintian-overrides").read_text(encoding="utf-8")

    def test_every_override_is_justified_by_a_preceding_comment(self) -> None:
        """'Silently ignoring the whole report is not acceptable.' Each
        override, or each block of them, must have a comment above it
        saying why the tag is expected rather than a defect."""
        block_has_comment = False
        for line in self.text.splitlines():
            stripped = line.strip()
            if not stripped:
                block_has_comment = False
                continue
            if stripped.startswith("#"):
                block_has_comment = True
                continue
            self.assertTrue(
                block_has_comment,
                f"override without a justifying comment: {stripped}",
            )

    def test_every_override_names_this_package(self) -> None:
        for line in self.text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                self.assertTrue(
                    stripped.startswith("saat: "),
                    f"override is not scoped to the package: {stripped}",
                )

    def _overridden_tags(self) -> list[str]:
        """The tag names actually silenced -- not the prose above them.
        The justifying comments necessarily discuss postrm, purge and
        removal at length, so scanning the whole file for those words
        flags the explanations rather than the overrides."""
        tags = []
        for line in self.text.splitlines():
            stripped = line.strip()
            if stripped.startswith("saat: "):
                tags.append(stripped[len("saat: "):].split()[0])
        return tags

    def test_nothing_about_data_safety_is_overridden(self) -> None:
        """No lintian tag that would mask a maintainer script deleting
        something may ever be silenced here. maintainer-script-empty is
        deliberately not in this set: an empty prerm is the absence of an
        action, which is the safe direction."""
        dangerous = ("removes", "delete", "rm-", "-rm", "purge", "clobber")
        for tag in self._overridden_tags():
            for needle in dangerous:
                self.assertNotIn(
                    needle, tag, f"override silences a data-safety tag: {tag}"
                )

    def test_no_override_carries_a_context_pattern(self) -> None:
        """Lintian matches an override's context literally against the
        tag's own context string, so `tag *` matches nothing for most tags
        and is reported as mismatched-override. Bare tag names override
        every instance, which is what this package wants for tags that fire
        across two hundred bundled libraries."""
        for line in self.text.splitlines():
            stripped = line.strip()
            if stripped.startswith("saat: "):
                self.assertEqual(
                    len(stripped.split()),
                    2,
                    f"override carries a context pattern: {stripped}",
                )


class WindowsInstallerDataSafetyTests(unittest.TestCase):
    """The Windows half of the rule the .deb's maintainer scripts carry:
    uninstalling must never delete the collection.

    On Windows the guarantee is structural rather than procedural. The
    program installs to %LOCALAPPDATA%\\Programs\\SAAT and the collection
    lives in %LOCALAPPDATA%\\SAAT -- siblings, not parent and child -- so
    Inno's uninstaller, which removes what it installed under {app},
    cannot reach the data even in principle. These tests pin that
    structure, because the way it would be lost is someone "simplifying"
    DefaultDirName."""

    def setUp(self) -> None:
        self.iss = (PACKAGING / "windows" / "saat.iss").read_text(encoding="utf-8")
        self.directives = [
            line.strip()
            for line in self.iss.splitlines()
            if line.strip() and not line.strip().startswith(";")
        ]

    def test_installs_beside_the_collection_never_on_top_of_it(self) -> None:
        self.assertIn(
            r"DefaultDirName={localappdata}\Programs\{#AppName}", self.directives
        )
        # The data directory itself, as paths.py resolves it, must never be
        # the install target.
        for directive in self.directives:
            if directive.startswith("DefaultDirName"):
                self.assertNotEqual(directive, r"DefaultDirName={localappdata}\SAAT")

    def test_there_is_no_uninstalldelete_section(self) -> None:
        """The section that could delete the collection is absent, and its
        absence is the guarantee."""
        self.assertNotIn("[UninstallDelete]", self.directives)

    def test_no_directive_names_the_users_data_directories(self) -> None:
        """Comments explain at length why these must not be touched, so
        only the directives are searched, not the prose."""
        body = "\n".join(self.directives)
        for forbidden in (
            r"{userappdata}\SAAT",
            r"{localappdata}\SAAT;",
            "{userdocs}",
        ):
            self.assertNotIn(forbidden, body)

    def test_it_installs_per_user_and_needs_no_administrator(self) -> None:
        """An unsigned installer asking for administrator rights is
        exactly the shape of the thing people are right to refuse."""
        self.assertIn("PrivilegesRequired=lowest", self.directives)

    def test_it_ships_the_installed_marker(self) -> None:
        """Load-bearing: without it an installed SAAT falls back to
        portable mode and tries to keep the collection inside its own
        Program Files-style directory. See docs/PLATFORM-AUDIT.md."""
        self.assertRegex(self.iss, r'Source: "installed-marker".*DestName: "\.installed"')
        self.assertTrue((PACKAGING / "windows" / "installed-marker").is_file())

    def test_it_registers_an_uninstaller_in_apps_and_features(self) -> None:
        self.assertTrue(
            any(d.startswith("UninstallDisplayName=") for d in self.directives)
        )
        self.assertTrue(
            any(d.startswith("UninstallDisplayIcon=") for d in self.directives)
        )

    def test_it_creates_start_menu_and_optional_desktop_shortcuts(self) -> None:
        self.assertIn("[Icons]", self.directives)
        self.assertTrue(any("{autoprograms}" in d for d in self.directives))
        self.assertTrue(any("{autodesktop}" in d for d in self.directives))
        # Inno directives wrap with a trailing backslash, so the flags of a
        # wrapped entry live on the following line -- joined before
        # searching rather than read one physical line at a time.
        joined = self.iss.replace("\\\n", " ")
        desktop_icon = [
            line for line in joined.splitlines() if "{autodesktop}" in line
        ]
        self.assertTrue(desktop_icon)
        self.assertIn("Tasks: desktopicon", desktop_icon[0])

        # Optional means unchecked by default.
        task = [
            line
            for line in joined.splitlines()
            if line.strip().startswith('Name: "desktopicon"')
        ]
        self.assertTrue(task)
        self.assertIn("unchecked", task[0])

    def test_the_app_id_is_fixed_so_upgrades_are_upgrades(self) -> None:
        """A changing AppId would leave every previous version installed
        alongside the new one, each with its own Apps & Features entry."""
        self.assertRegex(self.iss, r"AppId=\{\{[0-9A-F-]{36}\}")

    def test_it_writes_nothing_to_the_registry_of_its_own(self) -> None:
        """Milestone 24's DO-NOT list: no registry writes beyond what Inno
        Setup needs for its own uninstaller entry."""
        self.assertNotIn("[Registry]", self.directives)

    def test_the_payload_is_the_one_folder_build_never_onefile(self) -> None:
        self.assertRegex(self.iss, r'Source: "\.\.\\\.\.\\dist\\SAAT\\\*"')
        self.assertIn("recursesubdirs", self.iss)


class WindowsSpecTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = (REPO_ROOT / "SAAT.spec").read_text(encoding="utf-8")

    def test_no_console_window_appears_behind_the_app(self) -> None:
        self.assertIn("console=False", self.spec)

    def test_the_ico_is_the_executable_icon(self) -> None:
        self.assertIn("icon='saat/resources/icon/saat.ico'", self.spec)
        self.assertTrue((REPO_ROOT / "saat" / "resources" / "icon" / "saat.ico").is_file())

    def test_it_is_one_folder_on_every_platform(self) -> None:
        """SPEC.md §8 forbids --onefile, and the reasons hold at least as
        strongly on Windows: it re-extracts Qt to %TEMP% on every launch,
        which antivirus scanning makes slower still."""
        self.assertIn("exclude_binaries=True", self.spec)
        self.assertIn("coll = COLLECT(", self.spec)
        # "onefile" appears several times in the comments explaining why it
        # is banned, so only executable lines are searched.
        code = [
            line
            for line in self.spec.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        for line in code:
            self.assertNotIn("onefile", line.lower())

    def test_a_windows_version_resource_is_generated_from_the_version(self) -> None:
        self.assertIn("version=version_resource", self.spec)
        self.assertIn("saat.__version__", self.spec)

    def test_the_version_resource_is_windows_only(self) -> None:
        """Generating it on Linux would write a build artefact nothing
        reads and make the spec platform-dependent in the wrong
        direction."""
        self.assertIn("if sys.platform == 'win32':", self.spec)


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
