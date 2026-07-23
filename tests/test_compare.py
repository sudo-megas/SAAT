import unittest
from pathlib import Path

from saat.models import Case, Movement, Watch
from saat.storage import WatchRecord
from saat.ui.compare import MAX_COMPARE, MIN_COMPARE, RowContrast, build_compare_groups
from saat.ui.columns import GROUP_ORDER


def _record(slug: str, **kwargs) -> WatchRecord:
    return WatchRecord(slug=slug, path=Path(f"/nonexistent/{slug}"), watch=Watch(**kwargs))


def _row(groups, group_title: str, label: str):
    group = next((g for g in groups if g.title == group_title), None)
    if group is None:
        return None
    return next((r for r in group.rows if r.label == label), None)


class BuildCompareGroupsTests(unittest.TestCase):
    def test_a_row_where_every_watch_agrees_is_dimmed(self) -> None:
        records = [_record("a", brand="Seiko", model="X"), _record("b", brand="Seiko", model="Y")]
        row = _row(build_compare_groups(records), "Identity", "Brand")
        self.assertEqual(row.contrast, RowContrast.DIMMED)
        self.assertEqual(row.values, ["Seiko", "Seiko"])

    def test_a_row_where_watches_differ_is_full_contrast(self) -> None:
        records = [_record("a", brand="Seiko", model="X"), _record("b", brand="Casio", model="Y")]
        row = _row(build_compare_groups(records), "Identity", "Brand")
        self.assertEqual(row.contrast, RowContrast.DIFFERS)

    def test_a_row_absent_for_every_watch_is_dropped_entirely(self) -> None:
        records = [_record("a", brand="Seiko", model="X"), _record("b", brand="Casio", model="Y")]
        row = _row(build_compare_groups(records), "Identity", "Reference")  # neither set a reference
        self.assertIsNone(row)

    def test_a_row_present_for_only_some_watches_is_full_contrast_not_dimmed(self) -> None:
        records = [_record("a", brand="Seiko", model="X", reference="SARB033"), _record("b", brand="Casio", model="Y")]
        row = _row(build_compare_groups(records), "Identity", "Reference")
        self.assertIsNotNone(row)
        self.assertEqual(row.contrast, RowContrast.DIFFERS)
        self.assertEqual(row.values, ["SARB033", "—"])

    def test_works_with_four_watches(self) -> None:
        records = [_record(s, brand="Seiko", model=s) for s in ("a", "b", "c", "d")]
        row = _row(build_compare_groups(records), "Identity", "Brand")
        self.assertEqual(row.values, ["Seiko", "Seiko", "Seiko", "Seiko"])
        self.assertEqual(row.contrast, RowContrast.DIMMED)

    def test_a_group_with_no_surviving_rows_does_not_appear(self) -> None:
        records = [_record("a", brand="Seiko", model="X"), _record("b", brand="Casio", model="Y")]  # no dial fields set
        groups = build_compare_groups(records)
        self.assertNotIn("Dial", [g.title for g in groups])

    def test_group_order_matches_group_order_and_skips_empty_ones(self) -> None:
        records = [
            _record("a", brand="Seiko", model="X", case=Case(diameter_mm=38)),
            _record("b", brand="Casio", model="Y", case=Case(diameter_mm=40)),
        ]
        titles = [g.title for g in build_compare_groups(records)]
        self.assertEqual(titles, [g for g in GROUP_ORDER if g in ("Identity", "Case")])

    def test_the_derived_least_worn_column_never_appears(self) -> None:
        """least_worn's group is "Derived", deliberately excluded from
        GROUP_ORDER — it's a sort key, not a comparable attribute."""
        records = [_record("a", brand="Seiko", model="X"), _record("b", brand="Casio", model="Y")]
        row = _row(build_compare_groups(records), "Derived", "Least Worn")
        self.assertIsNone(row)
        self.assertNotIn("Derived", [g.title for g in build_compare_groups(records)])

    def test_numeric_columns_are_flagged_even_when_one_watch_is_missing_the_value(self) -> None:
        records = [
            _record("a", brand="Seiko", model="X", case=Case(diameter_mm=38)),
            _record("b", brand="Casio", model="Y"),  # no diameter set
        ]
        row = _row(build_compare_groups(records), "Case", "Diameter")
        self.assertTrue(row.numeric)

    def test_text_columns_are_not_flagged_numeric(self) -> None:
        records = [_record("a", brand="Seiko", model="X"), _record("b", brand="Casio", model="Y")]
        row = _row(build_compare_groups(records), "Identity", "Brand")
        self.assertFalse(row.numeric)

    def test_movement_kind_row_reflects_each_watchs_own_value(self) -> None:
        records = [
            _record("a", brand="Seiko", model="X", movement=Movement(kind="Automatic")),
            _record("b", brand="Casio", model="Y", movement=Movement(kind="Quartz")),
        ]
        row = _row(build_compare_groups(records), "Movement", "Movement")
        self.assertEqual(row.values, ["Automatic", "Quartz"])
        self.assertEqual(row.contrast, RowContrast.DIFFERS)


class CompareLimitsTests(unittest.TestCase):
    def test_min_and_max_match_spec(self) -> None:
        """SPEC.md §5.4: 'Select two to four watches.'"""
        self.assertEqual(MIN_COMPARE, 2)
        self.assertEqual(MAX_COMPARE, 4)


if __name__ == "__main__":
    unittest.main()
