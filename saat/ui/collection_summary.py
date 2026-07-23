from dataclasses import dataclass, field

from saat.storage import WatchRecord


@dataclass(frozen=True)
class CollectionSummary:
    total: int
    by_movement_kind: list[tuple[str, int]] = field(default_factory=list)
    value_by_currency: list[tuple[str, float]] = field(default_factory=list)


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
