import unittest
from pathlib import Path

from saat.models import Acquisition, Case, Movement, Watch
from saat.storage import WatchRecord
from saat.ui.compare import (
    MAX_COMPARE,
    MIN_COMPARE,
    SEC_PER_MONTH_DIVISOR,
    RowContrast,
    accuracy_axis_bounds,
    build_accuracy_entries,
    build_compare_groups,
    build_dimension_bar_rows,
    build_silhouette_entries,
    dimension_bar_columns,
    should_show_accuracy,
    should_show_silhouette,
    silhouette_profile_entries,
    silhouette_scale,
)
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


class BuildSilhouetteEntriesTests(unittest.TestCase):
    def test_a_watch_with_diameter_is_drawable(self) -> None:
        records = [_record("a", brand="Seiko", model="A", case=Case(diameter_mm=40))]
        entries, missing = build_silhouette_entries(records)
        self.assertEqual(len(entries), 1)
        self.assertEqual(missing, [])
        self.assertEqual(entries[0].diameter_mm, 40)

    def test_a_watch_with_no_diameter_is_missing_not_drawable(self) -> None:
        records = [_record("a", brand="Seiko", model="A", case=Case(lug_to_lug_mm=47))]
        entries, missing = build_silhouette_entries(records)
        self.assertEqual(entries, [])
        self.assertEqual([r.slug for r in missing], ["a"])

    def test_a_broken_record_with_no_watch_is_missing_not_a_crash(self) -> None:
        broken = WatchRecord(slug="broken", path=Path("/nonexistent/broken"), watch=None, load_error="bad toml")
        entries, missing = build_silhouette_entries([broken])
        self.assertEqual(entries, [])
        self.assertEqual(missing, [broken])

    def test_optional_fields_pass_through_when_present_and_none_when_absent(self) -> None:
        records = [_record("a", brand="Seiko", model="A", case=Case(diameter_mm=40))]
        [entry] = build_silhouette_entries(records)[0]
        self.assertIsNone(entry.lug_to_lug_mm)
        self.assertIsNone(entry.thickness_mm)
        self.assertIsNone(entry.lug_width_mm)


class ShouldShowSilhouetteTests(unittest.TestCase):
    def test_hidden_below_two_watches_with_diameter(self) -> None:
        records = [_record("a", brand="Seiko", model="A", case=Case(diameter_mm=40))]
        self.assertFalse(should_show_silhouette(records))

    def test_shown_at_exactly_two(self) -> None:
        records = [
            _record("a", brand="Seiko", model="A", case=Case(diameter_mm=40)),
            _record("b", brand="Casio", model="B", case=Case(diameter_mm=42)),
        ]
        self.assertTrue(should_show_silhouette(records))

    def test_a_watch_missing_diameter_does_not_count_toward_the_threshold(self) -> None:
        records = [
            _record("a", brand="Seiko", model="A", case=Case(diameter_mm=40)),
            _record("b", brand="Casio", model="B"),  # no case data at all
        ]
        self.assertFalse(should_show_silhouette(records))

    def test_shown_with_four_watches(self) -> None:
        records = [_record(s, brand="Seiko", model=s, case=Case(diameter_mm=40)) for s in ("a", "b", "c", "d")]
        self.assertTrue(should_show_silhouette(records))


class SilhouetteProfileEntriesTests(unittest.TestCase):
    def test_only_entries_with_thickness_qualify(self) -> None:
        records = [
            _record("a", brand="Seiko", model="A", case=Case(diameter_mm=40, thickness_mm=12)),
            _record("b", brand="Casio", model="B", case=Case(diameter_mm=42)),  # no thickness
        ]
        entries, _ = build_silhouette_entries(records)
        profile = silhouette_profile_entries(entries)
        self.assertEqual([e.record.slug for e in profile], ["a"])


class SilhouetteScaleTests(unittest.TestCase):
    def test_scale_fits_the_largest_lug_to_lug_into_the_available_width(self) -> None:
        records = [_record("a", brand="Seiko", model="A", case=Case(diameter_mm=40, lug_to_lug_mm=48))]
        entries, _ = build_silhouette_entries(records)
        self.assertAlmostEqual(silhouette_scale(entries, 240.0), 240.0 / 48)

    def test_scale_falls_back_to_diameter_when_lug_to_lug_is_absent(self) -> None:
        """'the case where only one watch has the relevant [lug-to-lug]
        data' — a watch missing it still draws, sized off its diameter."""
        records = [_record("a", brand="Seiko", model="A", case=Case(diameter_mm=40))]
        entries, _ = build_silhouette_entries(records)
        self.assertAlmostEqual(silhouette_scale(entries, 200.0), 200.0 / 40)

    def test_scale_is_driven_by_the_largest_extent_across_two_watches(self) -> None:
        records = [
            _record("a", brand="Seiko", model="A", case=Case(diameter_mm=36, lug_to_lug_mm=44)),
            _record("b", brand="Casio", model="B", case=Case(diameter_mm=44, lug_to_lug_mm=52)),
        ]
        entries, _ = build_silhouette_entries(records)
        self.assertAlmostEqual(silhouette_scale(entries, 260.0), 260.0 / 52)

    def test_scale_is_driven_by_the_largest_extent_across_four_watches(self) -> None:
        lug_to_lugs = [44, 52, 47, 39]
        records = [
            _record(str(i), brand="Seiko", model=str(i), case=Case(diameter_mm=36, lug_to_lug_mm=l))
            for i, l in enumerate(lug_to_lugs)
        ]
        entries, _ = build_silhouette_entries(records)
        self.assertAlmostEqual(silhouette_scale(entries, 260.0), 260.0 / max(lug_to_lugs))

    def test_one_watch_missing_lug_to_lug_can_still_end_up_the_scale_reference(self) -> None:
        """The other watch has a *larger* lug-to-lug, but this one's own
        diameter fallback is still what it draws to, and must be included
        in the max() even though it's a fallback value, not a real
        lug-to-lug reading."""
        records = [
            _record("a", brand="Seiko", model="A", case=Case(diameter_mm=46)),  # no lug-to-lug: falls back to 46
            _record("b", brand="Casio", model="B", case=Case(diameter_mm=30, lug_to_lug_mm=34)),
        ]
        entries, _ = build_silhouette_entries(records)
        self.assertAlmostEqual(silhouette_scale(entries, 230.0), 230.0 / 46)

    def test_zero_or_negative_available_width_yields_zero_scale(self) -> None:
        records = [_record("a", brand="Seiko", model="A", case=Case(diameter_mm=40))]
        entries, _ = build_silhouette_entries(records)
        self.assertEqual(silhouette_scale(entries, 0.0), 0.0)
        self.assertEqual(silhouette_scale(entries, -10.0), 0.0)

    def test_empty_entries_yields_zero_scale(self) -> None:
        self.assertEqual(silhouette_scale([], 240.0), 0.0)


def _movement_record(slug: str, **kwargs) -> WatchRecord:
    return WatchRecord(slug=slug, path=Path(f"/nonexistent/{slug}"), watch=Watch(brand="B", model=slug, movement=Movement(**kwargs)))


class BuildAccuracyEntriesTests(unittest.TestCase):
    def test_both_endpoints_present_with_no_unit_defaults_to_sec_per_day(self) -> None:
        records = [_movement_record("a", accuracy_min=-10, accuracy_max=20)]
        entries, missing = build_accuracy_entries(records)
        self.assertEqual(missing, [])
        [entry] = entries
        self.assertEqual(entry.original_unit, "sec/day")
        self.assertEqual((entry.min_sec_per_day, entry.max_sec_per_day), (-10, 20))
        self.assertEqual((entry.original_min, entry.original_max), (-10, 20))

    def test_sec_per_month_is_normalised_but_original_is_kept_for_labelling(self) -> None:
        records = [_movement_record("a", accuracy_min=-15, accuracy_max=25, accuracy_unit="sec/month")]
        [entry], _ = build_accuracy_entries(records)
        self.assertAlmostEqual(entry.min_sec_per_day, -15 / SEC_PER_MONTH_DIVISOR)
        self.assertAlmostEqual(entry.max_sec_per_day, 25 / SEC_PER_MONTH_DIVISOR)
        self.assertEqual(entry.original_min, -15)
        self.assertEqual(entry.original_max, 25)
        self.assertEqual(entry.original_unit, "sec/month")

    def test_only_one_endpoint_present_counts_as_missing(self) -> None:
        records = [_movement_record("a", accuracy_min=-10)]  # no accuracy_max
        entries, missing = build_accuracy_entries(records)
        self.assertEqual(entries, [])
        self.assertEqual([r.slug for r in missing], ["a"])

    def test_no_accuracy_data_at_all_counts_as_missing(self) -> None:
        records = [_movement_record("a")]
        entries, missing = build_accuracy_entries(records)
        self.assertEqual(entries, [])
        self.assertEqual([r.slug for r in missing], ["a"])

    def test_a_broken_record_with_no_watch_is_missing_not_a_crash(self) -> None:
        broken = WatchRecord(slug="broken", path=Path("/nonexistent/broken"), watch=None, load_error="bad toml")
        entries, missing = build_accuracy_entries([broken])
        self.assertEqual(entries, [])
        self.assertEqual(missing, [broken])


class ShouldShowAccuracyTests(unittest.TestCase):
    def test_hidden_below_two_watches_with_accuracy(self) -> None:
        records = [_movement_record("a", accuracy_min=-10, accuracy_max=20)]
        self.assertFalse(should_show_accuracy(records))

    def test_shown_at_exactly_two(self) -> None:
        records = [
            _movement_record("a", accuracy_min=-10, accuracy_max=20),
            _movement_record("b", accuracy_min=-5, accuracy_max=5),
        ]
        self.assertTrue(should_show_accuracy(records))

    def test_shown_with_four_watches(self) -> None:
        records = [_movement_record(str(i), accuracy_min=-10, accuracy_max=20) for i in range(4)]
        self.assertTrue(should_show_accuracy(records))

    def test_a_watch_missing_accuracy_does_not_count_toward_the_threshold(self) -> None:
        records = [_movement_record("a", accuracy_min=-10, accuracy_max=20), _movement_record("b")]
        self.assertFalse(should_show_accuracy(records))


class AccuracyAxisBoundsTests(unittest.TestCase):
    def test_zero_is_included_even_when_every_watch_sits_on_one_side_of_it(self) -> None:
        records = [_movement_record("a", accuracy_min=5, accuracy_max=20)]
        entries, _ = build_accuracy_entries(records)
        self.assertEqual(accuracy_axis_bounds(entries), (0.0, 20.0))

    def test_zero_is_included_for_an_entirely_negative_range(self) -> None:
        records = [_movement_record("a", accuracy_min=-40, accuracy_max=-10)]
        entries, _ = build_accuracy_entries(records)
        self.assertEqual(accuracy_axis_bounds(entries), (-40.0, 0.0))

    def test_bounds_span_the_widest_range_across_multiple_watches(self) -> None:
        records = [
            _movement_record("a", accuracy_min=-40, accuracy_max=20),
            _movement_record("b", accuracy_min=-2, accuracy_max=2),
        ]
        entries, _ = build_accuracy_entries(records)
        self.assertEqual(accuracy_axis_bounds(entries), (-40.0, 20.0))

    def test_bounds_use_the_normalised_sec_per_day_value_not_the_raw_sec_per_month_one(self) -> None:
        records = [_movement_record("a", accuracy_min=-15, accuracy_max=30, accuracy_unit="sec/month")]
        entries, _ = build_accuracy_entries(records)
        self.assertEqual(accuracy_axis_bounds(entries), (-15 / SEC_PER_MONTH_DIVISOR, 1.0))

    def test_empty_entries_yields_zero_bounds(self) -> None:
        self.assertEqual(accuracy_axis_bounds([]), (0.0, 0.0))


class DimensionBarColumnsTests(unittest.TestCase):
    def test_collection_scope_includes_price_and_excludes_target_price(self) -> None:
        keys = [c.key for c in dimension_bar_columns(is_wishlist=False)]
        self.assertIn("price", keys)
        self.assertNotIn("target_price", keys)

    def test_wishlist_scope_includes_target_price_and_excludes_price(self) -> None:
        keys = [c.key for c in dimension_bar_columns(is_wishlist=True)]
        self.assertIn("target_price", keys)
        self.assertNotIn("price", keys)

    def test_case_geometry_already_covered_by_the_silhouette_is_excluded(self) -> None:
        """SPEC.md §5.4: diameter, lug-to-lug and thickness stay out of the
        bars — the silhouette already covers case geometry."""
        keys = {c.key for c in dimension_bar_columns(is_wishlist=False)}
        self.assertFalse(keys & {"diameter_mm", "lug_to_lug_mm", "thickness_mm"})

    def test_the_named_dimensions_are_all_present(self) -> None:
        keys = {c.key for c in dimension_bar_columns(is_wishlist=False)}
        self.assertEqual(keys, {"weight_g", "water_resistance_m", "power_reserve_hours", "lug_width_mm", "price"})


def _acquisition_record(slug: str, price=None, target_price=None) -> WatchRecord:
    return WatchRecord(
        slug=slug, path=Path(f"/nonexistent/{slug}"),
        watch=Watch(brand="B", model=slug, acquisition=Acquisition(price=price, target_price=target_price, currency="USD")),
    )


class BuildDimensionBarRowsTests(unittest.TestCase):
    def test_a_row_appears_only_when_at_least_two_watches_have_the_value(self) -> None:
        records = [_record("a", brand="B", model="a", case=Case(weight_g=120))]
        self.assertEqual(build_dimension_bar_rows(records), [])

    def test_a_row_appears_at_exactly_two(self) -> None:
        records = [
            _record("a", brand="B", model="a", case=Case(weight_g=120)),
            _record("b", brand="B", model="b", case=Case(weight_g=90)),
        ]
        rows = build_dimension_bar_rows(records)
        self.assertEqual([r.label for r in rows], ["Weight"])

    def test_a_watch_with_no_value_gets_an_em_dash_slot_not_a_dropped_column(self) -> None:
        records = [
            _record("a", brand="B", model="a", case=Case(weight_g=120)),
            _record("b", brand="B", model="b", case=Case(weight_g=90)),
            _record("c", brand="B", model="c"),  # no weight at all
        ]
        [row] = build_dimension_bar_rows(records)
        self.assertEqual(len(row.values), 3)
        missing_value = next(v for v in row.values if v.record.slug == "c")
        self.assertIsNone(missing_value.magnitude)
        self.assertEqual(missing_value.text, "—")

    def test_unit_hint_gives_a_cleaner_label_than_the_tables_own_formatter(self) -> None:
        """water_resistance's table formatter appends a "(N bar)"
        parenthetical — noise at the end of a bar. The unit-hint label
        should just be the plain figure and unit."""
        records = [
            _record("a", brand="B", model="a", case=Case(water_resistance_m=200)),
            _record("b", brand="B", model="b", case=Case(water_resistance_m=100)),
        ]
        [row] = build_dimension_bar_rows(records)
        texts = {v.record.slug: v.text for v in row.values}
        self.assertEqual(texts["a"], "200 m")
        self.assertEqual(texts["b"], "100 m")

    def test_price_row_falls_back_to_the_tables_currency_aware_formatter(self) -> None:
        records = [_acquisition_record("a", price=1200), _acquisition_record("b", price=900)]
        [row] = build_dimension_bar_rows(records, is_wishlist=False)
        self.assertEqual(row.label, "Price")
        texts = {v.record.slug: v.text for v in row.values}
        self.assertEqual(texts["a"], "1,200.00 USD")

    def test_wishlist_scope_uses_target_price_instead_of_price(self) -> None:
        records = [_acquisition_record("a", target_price=1200), _acquisition_record("b", target_price=900)]
        [row] = build_dimension_bar_rows(records, is_wishlist=True)
        self.assertEqual(row.label, "Target Price")

    def test_max_magnitude_ignores_missing_values(self) -> None:
        records = [
            _record("a", brand="B", model="a", case=Case(weight_g=120)),
            _record("b", brand="B", model="b", case=Case(weight_g=90)),
            _record("c", brand="B", model="c"),
        ]
        [row] = build_dimension_bar_rows(records)
        self.assertEqual(row.max_magnitude, 120)

    def test_works_with_two_three_and_four_watches(self) -> None:
        for count in (2, 3, 4):
            records = [_record(str(i), brand="B", model=str(i), case=Case(weight_g=100 + i)) for i in range(count)]
            with self.subTest(count=count):
                [row] = build_dimension_bar_rows(records)
                self.assertEqual(len(row.values), count)


if __name__ == "__main__":
    unittest.main()
