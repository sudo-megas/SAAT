import re
import unittest
from pathlib import Path

from saat import __version__

CHANGELOG_PATH = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
# Two- and three-numeral versions are both valid. Releases up to 1.8.2 were
# three-part; milestone 23 shipped as 2.0, which this pattern rejected --
# the version scheme is the project's to choose, so the guard was widened
# rather than the version padded to 2.0.0 to satisfy a regex.
VERSION_HEADING = re.compile(r"^## \[(\d+\.\d+(?:\.\d+)?)\]", re.MULTILINE)


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
