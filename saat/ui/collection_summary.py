from dataclasses import dataclass, field
from datetime import date, timedelta

from saat.storage import WatchRecord


@dataclass(frozen=True)
class CollectionSummary:
    total: int
    by_movement_kind: list[tuple[str, int]] = field(default_factory=list)
    value_by_currency: list[tuple[str, float]] = field(default_factory=list)


@dataclass(frozen=True)
class WishlistSummary:
    """SPEC.md §5.12: the Wishlist scope's summary strip, sibling to
    CollectionSummary's §5.10 footer — same plain-figures restraint."""

    total: int
    target_value_by_currency: list[tuple[str, float]] = field(default_factory=list)
    has_any_target_date: bool = False
    due_next_12_months_by_currency: list[tuple[str, float]] = field(default_factory=list)


def compute_wishlist_summary(records: list[WatchRecord], today: date | None = None) -> WishlistSummary:
    """Total target_price by currency, item count, and — only when at least
    one watch has a target_date at all, regardless of whether it falls in
    the window — the subtotal of target_price for watches whose target_date
    falls in the next 12 months. `has_any_target_date` is what the caller
    checks to decide whether to render that line at all, not whether the
    resulting sum happens to be non-empty."""
    today = today if today is not None else date.today()
    horizon = today + timedelta(days=365)
    valid = [r.watch for r in records if r.watch is not None]

    target_value_by_currency: dict[str, float] = {}
    for watch in valid:
        if watch.acquisition.target_price is not None:
            currency = watch.acquisition.currency or "TRY"
            target_value_by_currency[currency] = (
                target_value_by_currency.get(currency, 0) + watch.acquisition.target_price
            )

    has_any_target_date = any(watch.acquisition.target_date is not None for watch in valid)

    due_by_currency: dict[str, float] = {}
    for watch in valid:
        target_date = watch.acquisition.target_date
        if target_date is None or watch.acquisition.target_price is None:
            continue
        if today <= target_date <= horizon:
            currency = watch.acquisition.currency or "TRY"
            due_by_currency[currency] = due_by_currency.get(currency, 0) + watch.acquisition.target_price

    return WishlistSummary(
        total=len(valid),
        target_value_by_currency=sorted(target_value_by_currency.items(), key=lambda pair: pair[0].casefold()),
        has_any_target_date=has_any_target_date,
        due_next_12_months_by_currency=sorted(due_by_currency.items(), key=lambda pair: pair[0].casefold()),
    )


def compute_collection_summary(records: list[WatchRecord]) -> CollectionSummary:
    """SPEC.md §5.10: watch count, split by movement kind, total acquisition
    value by currency — the whole collection, not whatever the sidebar's own
    filters currently narrow it to. Plain figures: watches with no movement
    kind or no price simply don't contribute to those two breakdowns."""
    valid = [r.watch for r in records if r.watch is not None]

    by_kind: dict[str, int] = {}
    for watch in valid:
        if watch.movement.kind:
            by_kind[watch.movement.kind] = by_kind.get(watch.movement.kind, 0) + 1

    value_by_currency: dict[str, float] = {}
    for watch in valid:
        if watch.acquisition.price is not None:
            currency = watch.acquisition.currency or "TRY"
            value_by_currency[currency] = value_by_currency.get(currency, 0) + watch.acquisition.price

    return CollectionSummary(
        total=len(valid),
        by_movement_kind=sorted(by_kind.items(), key=lambda pair: pair[0].casefold()),
        value_by_currency=sorted(value_by_currency.items(), key=lambda pair: pair[0].casefold()),
    )
