import unittest
from datetime import date

from saat.models import Movement, Watch
from saat.ui.facets import (
    VALUE_FACETS_BY_KEY,
    days_since_worn,
    is_not_worn_90d,
)
from saat.ui.filtering import NOT_WORN_FACET_KEY, FilterState, passes
from saat.ui.search import fuzzy_match, search_matches


class FuzzyMatchTests(unittest.TestCase):
    def test_empty_query_matches_anything(self) -> None:
        self.assertTrue(fuzzy_match("", "Seiko"))

    def test_exact_substring_matches(self) -> None:
        self.assertTrue(fuzzy_match("seiko", "Seiko"))

    def test_gapped_subsequence_matches(self) -> None:
        self.assertTrue(fuzzy_match("skx", "SKX007"))
        self.assertTrue(fuzzy_match("srb", "SARB033"))

    def test_out_of_order_characters_do_not_match(self) -> None:
        self.assertFalse(fuzzy_match("xsk", "SKX007"))

    def test_characters_not_present_do_not_match(self) -> None:
        self.assertFalse(fuzzy_match("seiq", "Seiko"))

    def test_case_insensitive(self) -> None:
        self.assertTrue(fuzzy_match("SARB", "sarb033"))


class SearchMatchesTests(unittest.TestCase):
    def _watch(self, **kwargs) -> Watch:
        return Watch(brand=kwargs.pop("brand", "Seiko"), model=kwargs.pop("model", "SARB033"), **kwargs)

    def test_matches_brand(self) -> None:
        self.assertTrue(search_matches(self._watch(), "seiko"))

    def test_matches_model(self) -> None:
        self.assertTrue(search_matches(self._watch(), "sarb"))

    def test_matches_reference(self) -> None:
        watch = self._watch(reference="6R15-00A0")
        self.assertTrue(search_matches(watch, "6r15"))

    def test_matches_caliber(self) -> None:
        watch = self._watch(movement=Movement(caliber="6R15"))
        self.assertTrue(search_matches(watch, "6r15"))

    def test_matches_a_tag(self) -> None:
        watch = self._watch(tags=["vintage", "diver"])
        self.assertTrue(search_matches(watch, "diver"))

    def test_query_must_not_match_across_field_boundaries(self) -> None:
        # brand="AB", model="CD" — "ad" is a subsequence of "AB"+"CD" concatenated
        # but must NOT match, since no single field contains it as a subsequence.
        watch = self._watch(brand="AB", model="CD")
        self.assertFalse(search_matches(watch, "ad"))

    def test_no_match_returns_false(self) -> None:
        self.assertFalse(search_matches(self._watch(), "rolex"))

    def test_blank_query_matches_everything(self) -> None:
        self.assertTrue(search_matches(self._watch(), "   "))


class FacetExtractionTests(unittest.TestCase):
    def test_lug_width_formats_with_unit_and_sorts_numerically(self) -> None:
        facet = VALUE_FACETS_BY_KEY["lug_width"]
        watch = Watch(brand="Seiko", model="SARB033")
        watch.case.lug_width_mm = 20
        self.assertEqual(facet.extract(watch), ["20 mm"])
        self.assertEqual(sorted(["22 mm", "8 mm", "20 mm"], key=facet.sort_key), ["8 mm", "20 mm", "22 mm"])

    def test_lug_width_absent_yields_no_values(self) -> None:
        facet = VALUE_FACETS_BY_KEY["lug_width"]
        self.assertEqual(facet.extract(Watch(brand="Seiko", model="SARB033")), [])

    def test_tags_facet_yields_every_tag(self) -> None:
        facet = VALUE_FACETS_BY_KEY["tags"]
        watch = Watch(brand="Seiko", model="SARB033", tags=["vintage", "diver"])
        self.assertEqual(facet.extract(watch), ["vintage", "diver"])

    def test_status_facet_default_owned(self) -> None:
        facet = VALUE_FACETS_BY_KEY["status"]
        self.assertEqual(facet.extract(Watch(brand="Seiko", model="SARB033")), ["Owned"])


class WearDerivedTests(unittest.TestCase):
    def test_never_worn_has_no_days_since(self) -> None:
        self.assertIsNone(days_since_worn(Watch(brand="Seiko", model="SARB033")))

    def test_days_since_worn_counts_from_most_recent_entry(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033", worn=[date(2026, 1, 1), date(2026, 6, 1)])
        self.assertEqual(days_since_worn(watch, today=date(2026, 6, 11)), 10)

    def test_never_worn_counts_as_not_worn_in_90_days(self) -> None:
        self.assertTrue(is_not_worn_90d(Watch(brand="Seiko", model="SARB033")))

    def test_worn_exactly_90_days_ago_counts_as_not_worn(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033", worn=[date(2026, 1, 1)])
        self.assertTrue(is_not_worn_90d(watch, today=date(2026, 4, 1)))

    def test_worn_yesterday_does_not_count_as_not_worn(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033", worn=[date(2026, 6, 10)])
        self.assertFalse(is_not_worn_90d(watch, today=date(2026, 6, 11)))


class PassesPredicateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.diver = Watch(brand="Seiko", model="SKX007", style="Diver")
        self.dress = Watch(brand="Seiko", model="Presage", style="Dress")

    def test_no_active_filters_passes_everything(self) -> None:
        state = FilterState()
        self.assertTrue(passes(self.diver, state))
        self.assertTrue(passes(self.dress, state))

    def test_selected_facet_value_excludes_non_matching_watches(self) -> None:
        state = FilterState(active_values={"style": {"Diver"}})
        self.assertTrue(passes(self.diver, state))
        self.assertFalse(passes(self.dress, state))

    def test_multiple_selected_values_in_one_facet_are_ORed(self) -> None:
        state = FilterState(active_values={"style": {"Diver", "Dress"}})
        self.assertTrue(passes(self.diver, state))
        self.assertTrue(passes(self.dress, state))

    def test_different_facets_are_ANDed(self) -> None:
        state = FilterState(active_values={"style": {"Diver"}, "status": {"Sold"}})
        self.assertFalse(passes(self.diver, state))  # status is Owned by default, not Sold

    def test_skip_excludes_that_facet_from_evaluation(self) -> None:
        state = FilterState(active_values={"style": {"Dress"}})
        self.assertFalse(passes(self.diver, state))
        self.assertTrue(passes(self.diver, state, skip="style"))

    def test_not_worn_only_filters_recently_worn_watches(self) -> None:
        worn_today = Watch(brand="Seiko", model="SARB033", worn=[date(2026, 6, 11)])
        state = FilterState(not_worn_only=True)
        self.assertFalse(passes(worn_today, state, today=date(2026, 6, 11)))
        self.assertTrue(passes(self.diver, state, today=date(2026, 6, 11)))  # never worn

    def test_skip_not_worn_facet_key_ignores_not_worn_only(self) -> None:
        worn_today = Watch(brand="Seiko", model="SARB033", worn=[date(2026, 6, 11)])
        state = FilterState(not_worn_only=True)
        self.assertTrue(passes(worn_today, state, skip=NOT_WORN_FACET_KEY, today=date(2026, 6, 11)))

    def test_search_query_combines_with_facets(self) -> None:
        state = FilterState(active_values={"style": {"Diver"}}, query="skx")
        self.assertTrue(passes(self.diver, state))
        state_no_match = FilterState(active_values={"style": {"Diver"}}, query="presage")
        self.assertFalse(passes(self.diver, state_no_match))


class FilterStateTests(unittest.TestCase):
    def test_is_active_false_when_nothing_set(self) -> None:
        self.assertFalse(FilterState().is_active())

    def test_is_active_true_for_query(self) -> None:
        self.assertTrue(FilterState(query="seiko").is_active())

    def test_is_active_true_for_not_worn_only(self) -> None:
        self.assertTrue(FilterState(not_worn_only=True).is_active())

    def test_is_active_true_for_a_selected_facet_value(self) -> None:
        self.assertTrue(FilterState(active_values={"style": {"Diver"}}).is_active())

    def test_is_active_false_for_a_facet_key_with_an_empty_set(self) -> None:
        self.assertFalse(FilterState(active_values={"style": set()}).is_active())


if __name__ == "__main__":
    unittest.main()
