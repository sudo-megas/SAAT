import unittest
from pathlib import Path

from saat.models import Case, Strap, Watch
from saat.storage import WatchRecord
from saat.ui.strap_compat import compatible_straps


def _record(slug: str, watch: Watch | None) -> WatchRecord:
    return WatchRecord(slug=slug, path=Path(f"/nonexistent/{slug}"), watch=watch)


def _watch(lug_width_mm: int | None, straps: list[Strap] | None = None, status: str = "Owned") -> Watch:
    return Watch(brand="Seiko", model="SARB033", case=Case(lug_width_mm=lug_width_mm), straps=straps or [], status=status)


class CompatibleStrapsTests(unittest.TestCase):
    def test_target_with_no_lug_width_has_nothing_to_match(self) -> None:
        target = _record("target", _watch(None))
        other = _record("other", _watch(20, [Strap(material="Leather", width_mm=20)]))
        self.assertEqual(compatible_straps(target, [target, other]), [])

    def test_a_strap_with_an_explicit_matching_width_is_found(self) -> None:
        target = _record("target", _watch(20))
        other = _record("other", _watch(22, [Strap(material="Leather", width_mm=20)]))
        matches = compatible_straps(target, [target, other])
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].record.slug, "other")
        self.assertEqual(matches[0].strap.material, "Leather")

    def test_a_strap_with_no_width_falls_back_to_its_owners_lug_width(self) -> None:
        """SPEC.md §4: width_mm 'defaults to case.lug_width_mm'."""
        target = _record("target", _watch(20))
        other = _record("other", _watch(20, [Strap(material="NATO", width_mm=None)]))
        matches = compatible_straps(target, [target, other])
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].strap.material, "NATO")

    def test_a_non_matching_width_is_excluded(self) -> None:
        target = _record("target", _watch(20))
        other = _record("other", _watch(22, [Strap(material="Leather", width_mm=22)]))
        self.assertEqual(compatible_straps(target, [target, other]), [])

    def test_the_targets_own_straps_are_excluded_even_if_they_match(self) -> None:
        target = _record("target", _watch(20, [Strap(material="Leather", width_mm=20)]))
        self.assertEqual(compatible_straps(target, [target]), [])

    def test_a_broken_record_among_the_others_is_skipped_safely(self) -> None:
        target = _record("target", _watch(20))
        broken = _record("broken", None)
        matches = compatible_straps(target, [target, broken])
        self.assertEqual(matches, [])

    def test_multiple_matches_across_multiple_watches_are_all_included(self) -> None:
        target = _record("target", _watch(20))
        other1 = _record("other1", _watch(20, [Strap(material="Leather", width_mm=20)]))
        other2 = _record("other2", _watch(20, [Strap(material="NATO", width_mm=20), Strap(material="Rubber", width_mm=22)]))
        matches = compatible_straps(target, [target, other1, other2])
        self.assertEqual({(m.record.slug, m.strap.material) for m in matches}, {("other1", "Leather"), ("other2", "NATO")})

    def test_a_non_owned_target_has_nothing_to_swap(self) -> None:
        """SPEC.md §5.12: swapping only makes sense between watches
        physically on hand — a Wishlist watch isn't owned yet."""
        target = _record("target", _watch(20, status="Wishlist"))
        other = _record("other", _watch(20, [Strap(material="Leather", width_mm=20)]))
        self.assertEqual(compatible_straps(target, [target, other]), [])

    def test_a_non_owned_candidates_straps_are_not_offered(self) -> None:
        target = _record("target", _watch(20))
        wishlist_other = _record("other", _watch(20, [Strap(material="Leather", width_mm=20)], status="Wishlist"))
        self.assertEqual(compatible_straps(target, [target, wishlist_other]), [])


if __name__ == "__main__":
    unittest.main()
