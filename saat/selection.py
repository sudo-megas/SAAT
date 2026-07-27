"""Milestone 20: watch-selection logic for the today picker and the week
planner. Pure — no Qt, no I/O, no event loop. See SPEC.md §5.5.

Both modes draw from wear.owned_watches() only: SPEC.md §5.12 excludes
Wishlist, Incoming, Sold and Gifted watches from anything wear-related, the
same choke point Stats mode and the calendar already read through.
"""

import random
from datetime import date, timedelta

from saat.storage import WatchRecord
from saat.ui.wear_stats import last_worn
from saat.wear import owned_watches

MODE_RANDOM = "random"
MODE_WEIGHTED = "weighted"

# A never-worn watch's weight is set this far above whatever the most-
# neglected *real* value in the batch is, rather than a fixed always-huge
# constant. A collection-relative bonus keeps "never worn is favoured" true
# without making a recently-worn watch's chance so small it stops feeling
# like "never zero" in practice — SPEC.md milestone 20 step 3 wants a
# gentle curve specifically so the result never feels rigged.
_NEVER_WORN_BONUS = 30.0


def _weights_from_last_worn(last_worn_by_slug: dict[str, date | None], reference: date) -> dict[str, float]:
    """Shared weighting core for compute_weights() and the weighted week
    roll (which recomputes this against a different reference day per
    iteration as picks accumulate — see pick_week). Weight is linear in
    days-since `reference` — a gentle curve, not a hard cutoff — floored at
    0 days-since rather than going negative, which a pre-planned future
    wear date (SPEC.md §5.5: "Every day is editable, past or future") could
    otherwise produce. Every result is >= 1.0: never zero."""
    since_by_slug = {
        slug: (None if when is None else max(0.0, float((reference - when).days)))
        for slug, when in last_worn_by_slug.items()
    }
    real_values = [v for v in since_by_slug.values() if v is not None]
    never_worn_weight = max(real_values, default=0.0) + _NEVER_WORN_BONUS
    return {slug: (never_worn_weight if since is None else since + 1.0) for slug, since in since_by_slug.items()}


def compute_weights(watches: list[WatchRecord], today: date | None = None) -> dict[str, float]:
    """slug -> weight for weighted mode. Never-worn always gets the maximum
    (see _weights_from_last_worn); the least-recently-worn watch gets the
    least, but never zero."""
    today = today if today is not None else date.today()
    return _weights_from_last_worn({r.slug: last_worn(r.watch) for r in watches}, today)


def pick_random(records: list[WatchRecord], rand: random.Random | None = None) -> WatchRecord:
    """Uniform over owned watches — a true dN. Raises ValueError with no
    owned watches; callers check emptiness before presenting the picker
    (SPEC.md milestone 20 step 11) rather than relying on this exception."""
    watches = owned_watches(records)
    if not watches:
        raise ValueError("no owned watches to pick from")
    rand = rand if rand is not None else random.Random()
    return rand.choice(watches)


def pick_weighted(
    records: list[WatchRecord], rand: random.Random | None = None, today: date | None = None
) -> WatchRecord:
    """Favours watches worn least recently — see compute_weights() for the
    curve. Raises ValueError with no owned watches; see pick_random()."""
    watches = owned_watches(records)
    if not watches:
        raise ValueError("no owned watches to pick from")
    rand = rand if rand is not None else random.Random()
    weights = compute_weights(watches, today)
    return rand.choices(watches, weights=[weights[r.slug] for r in watches], k=1)[0]


def pick_one(
    records: list[WatchRecord], mode: str, rand: random.Random | None = None, today: date | None = None
) -> WatchRecord:
    """Dispatches to pick_random()/pick_weighted() by mode string."""
    if mode == MODE_WEIGHTED:
        return pick_weighted(records, rand, today)
    if mode == MODE_RANDOM:
        return pick_random(records, rand)
    raise ValueError(f"unknown picker mode: {mode!r}")


def week_dates(week_start: date) -> list[date]:
    """The seven dates Monday..Sunday of week_start's week. week_start need
    not itself be a Monday — normalised here the same way month_grid.py's
    month_grid_days() normalises to whole weeks (SPEC.md §5.5: weeks start
    Monday)."""
    monday = week_start - timedelta(days=week_start.weekday())
    return [monday + timedelta(days=i) for i in range(7)]


def pick_week(
    records: list[WatchRecord],
    week_start: date,
    mode: str,
    rand: random.Random | None = None,
    today: date | None = None,
) -> dict[date, WatchRecord]:
    """One pick per day, Monday..Sunday of week_start's week. SPEC.md
    milestone 20 step 5: repeats are allowed by default (a <=7-watch
    collection cannot fill a week otherwise), but with more than seven owned
    watches, picks prefer distinct watches — a hard guarantee in random mode
    (sampling without replacement), a strong-but-never-absolute preference
    in weighted mode, since hard-excluding an already-picked watch on a
    later day would zero out its chance and break the same never-zero-
    weight invariant compute_weights() promises everywhere else.

    Returns picks for all seven days unconditionally — this function has no
    opinion on which days are empty, already logged, or in the past. That
    filtering belongs to the caller (the week planner in calendar_view.py),
    which decides which of these seven proposals to actually offer or
    write. Raises ValueError with no owned watches; see pick_random()."""
    watches = owned_watches(records)
    if not watches:
        raise ValueError("no owned watches to pick from")
    rand = rand if rand is not None else random.Random()
    days = week_dates(week_start)

    if mode == MODE_RANDOM:
        chosen = rand.sample(watches, k=7) if len(watches) >= 7 else [rand.choice(watches) for _ in days]
        return dict(zip(days, chosen))

    if mode == MODE_WEIGHTED:
        # A working copy of "when was this watch last worn", updated as the
        # week fills in via _weights_from_last_worn (same core compute_weights
        # uses), so a watch picked for Monday reads as freshly-worn when
        # Tuesday's weights are computed — carrying the bias across the week
        # (step 16) without ever hard-excluding it.
        last_worn_by_slug: dict[str, date | None] = {r.slug: last_worn(r.watch) for r in watches}
        picks: dict[date, WatchRecord] = {}
        for day in days:
            weights = _weights_from_last_worn(last_worn_by_slug, day)
            chosen = rand.choices(watches, weights=[weights[r.slug] for r in watches], k=1)[0]
            picks[day] = chosen
            last_worn_by_slug[chosen.slug] = day
        return picks

    raise ValueError(f"unknown picker mode: {mode!r}")
