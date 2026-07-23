import re
import unittest
from pathlib import Path

from saat import __version__

CHANGELOG_PATH = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
VERSION_HEADING = re.compile(r"^## \[(\d+\.\d+\.\d+)\]", re.MULTILINE)


class VersionMatchesChangelogTests(unittest.TestCase):
    """Guards against exactly what happened after milestone 12: a milestone
    that ships real behavior changes but forgets to bump __version__. The
    most recent CHANGELOG.md heading and saat.__version__ must always
    agree — enforced by this test, not remembered by whoever's writing the
    commit, the same as every other invariant in this project."""

    def test_version_matches_most_recent_changelog_heading(self) -> None:
        text = CHANGELOG_PATH.read_text(encoding="utf-8")
        match = VERSION_HEADING.search(text)
        self.assertIsNotNone(match, "no '## [x.y.z]' heading found in CHANGELOG.md")
        self.assertEqual(__version__, match.group(1))


if __name__ == "__main__":
    unittest.main()
