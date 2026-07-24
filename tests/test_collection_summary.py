import unittest
from datetime import date
from pathlib import Path

from saat.models import Acquisition, Movement, Watch
from saat.storage import WatchRecord
from saat.ui.collection_summary import compute_collection_summary, compute_wishlist_summary


def _record(slug: str, watch: Watch | None, load_error: str | None = None) -> WatchRecord:
    return WatchRecord(slug=slug, path=Path(f"/nonexistent/{slug}"), watch=watch, load_error=load_error)


def _watch(kind: str | None = None, price: float | None = None, currency: str | None = None) -> Watch:
    return Watch(
        brand="Seiko",
        model="SARB033",
        movement=Movement(kind=kind),
        acquisition=Acquisition(price=price, currency=currency),
    )


def _wishlist_watch(
    target_price: float | None = None, target_date: date | None = None, currency: str | None = None
) -> Watch:
    return Watch(
        brand="Seiko",
        model="SARB033",
        status="Wishlist",
        acquisition=Acquisition(target_price=target_price, target_date=target_date, currency=currency),
    )


class CollectionSummaryTests(unittest.TestCase):
    def test_empty_collection(self) -> None:
        summary = compute_collection_summary([])
        self.assertEqual(summary.total, 0)
        self.assertEqual(summary.by_movement_kind, [])
        self.assertEqual(summary.value_by_currency, [])

    def test_broken_records_are_excluded_from_the_total(self) -> None:
        records = [_record("good", _watch()), _record("broken", None, load_error="bad toml")]
        summary = compute_collection_summary(records)
        self.assertEqual(summary.total, 1)

    def test_movement_kind_counts_are_split_and_sorted(self) -> None:
        records = [
            _record("a", _watch(kind="Quartz")),
            _record("b", _watch(kind="Automatic")),
            _record("c", _watch(kind="Automatic")),
        ]
        summary = compute_collection_summary(records)
        self.assertEqual(summary.by_movement_kind, [("Automatic", 2), ("Quartz", 1)])

    def test_a_watch_with_no_movement_kind_still_counts_toward_the_total_but_not_the_split(self) -> None:
        records = [_record("a", _watch(kind=None))]
        summary = compute_collection_summary(records)
        self.assertEqual(summary.total, 1)
        self.assertEqual(summary.by_movement_kind, [])

    def test_acquisition_value_is_summed_per_currency(self) -> None:
        records = [
            _record("a", _watch(price=1000, currency="TRY")),
            _record("b", _watch(price=500, currency="TRY")),
            _record("c", _watch(price=200, currency="USD")),
        ]
        summary = compute_collection_summary(records)
        self.assertEqual(summary.value_by_currency, [("TRY", 1500), ("USD", 200)])

    def test_a_watch_with_a_price_but_no_currency_defaults_to_try(self) -> None:
        """SPEC.md §4: acquisition.currency defaults to TRY."""
        records = [_record("a", _watch(price=100, currency=None))]
        summary = compute_collection_summary(records)
        self.assertEqual(summary.value_by_currency, [("TRY", 100)])

    def test_a_watch_with_no_price_does_not_contribute_to_value_by_currency(self) -> None:
        records = [_record("a", _watch(price=None))]
        summary = compute_collection_summary(records)
        self.assertEqual(summary.value_by_currency, [])

    def test_currencies_sort_alphabetically(self) -> None:
        records = [
            _record("a", _watch(price=1, currency="USD")),
            _record("b", _watch(price=1, currency="EUR")),
            _record("c", _watch(price=1, currency="AUD")),
        ]
        summary = compute_collection_summary(records)
        self.assertEqual([c for c, _ in summary.value_by_currency], ["AUD", "EUR", "USD"])


class WishlistSummaryTests(unittest.TestCase):
    def test_empty_collection(self) -> None:
        summary = compute_wishlist_summary([])
        self.assertEqual(summary.total, 0)
        self.assertEqual(summary.target_value_by_currency, [])
        self.assertFalse(summary.has_any_target_date)
        self.assertEqual(summary.due_next_12_months_by_currency, [])

    def test_target_value_summed_per_currency(self) -> None:
        records = [
            _record("a", _wishlist_watch(target_price=1000, currency="TRY")),
            _record("b", _wishlist_watch(target_price=500, currency="TRY")),
            _record("c", _wishlist_watch(target_price=200, currency="USD")),
        ]
        summary = compute_wishlist_summary(records)
        self.assertEqual(summary.target_value_by_currency, [("TRY", 1500), ("USD", 200)])

    def test_a_watch_with_target_price_but_no_currency_defaults_to_try(self) -> None:
        records = [_record("a", _wishlist_watch(target_price=100, currency=None))]
        summary = compute_wishlist_summary(records)
        self.assertEqual(summary.target_value_by_currency, [("TRY", 100)])

    def test_a_watch_with_no_target_price_does_not_contribute(self) -> None:
        records = [_record("a", _wishlist_watch(target_price=None))]
        summary = compute_wishlist_summary(records)
        self.assertEqual(summary.target_value_by_currency, [])

    def test_has_any_target_date_false_when_none_set(self) -> None:
        records = [_record("a", _wishlist_watch(target_price=100))]
        summary = compute_wishlist_summary(records)
        self.assertFalse(summary.has_any_target_date)
        self.assertEqual(summary.due_next_12_months_by_currency, [])

    def test_has_any_target_date_true_even_if_nothing_falls_in_the_window(self) -> None:
        """SPEC.md §5.12: the line is gated on *any* target_date existing,
        not on the windowed subtotal being non-empty."""
        far_future = date(2030, 1, 1)
        records = [_record("a", _wishlist_watch(target_price=100, target_date=far_future, currency="TRY"))]
        summary = compute_wishlist_summary(records, today=date(2026, 1, 1))
        self.assertTrue(summary.has_any_target_date)
        self.assertEqual(summary.due_next_12_months_by_currency, [])

    def test_due_next_12_months_includes_only_dates_within_the_window(self) -> None:
        today = date(2026, 1, 1)
        soon = _record("a", _wishlist_watch(target_price=500, target_date=date(2026, 6, 1), currency="TRY"))
        later = _record("b", _wishlist_watch(target_price=300, target_date=date(2027, 6, 1), currency="TRY"))
        summary = compute_wishlist_summary([soon, later], today=today)
        self.assertEqual(summary.due_next_12_months_by_currency, [("TRY", 500)])

    def test_broken_records_are_excluded(self) -> None:
        records = [_record("good", _wishlist_watch(target_price=100)), _record("broken", None, load_error="bad toml")]
        summary = compute_wishlist_summary(records)
        self.assertEqual(summary.total, 1)


if __name__ == "__main__":
    unittest.main()
