import random
import unittest
from datetime import date, timedelta
from pathlib import Path

from saat.models import Watch
from saat.storage import WatchRecord
from saat.selection import (
    MODE_RANDOM,
    MODE_WEIGHTED,
    compute_weights,
    pick_one,
    pick_random,
    pick_weighted,
    pick_week,
    week_dates,
)

TODAY = date(2026, 8, 3)  # a Monday


def _record(slug: str, brand: str = "Brand", model: str = "Model", worn: list[date] | None = None, status: str = "Owned") -> WatchRecord:
    return WatchRecord(
        slug=slug, path=Path(f"/nonexistent/{slug}"), watch=Watch(brand=brand, model=model, worn=worn or [], status=status)
    )


class _ArgmaxRand:
    """Deterministic stand-in for random.Random: always resolves a weighted
    choice to the single highest-weighted candidate (first one, on a tie).
    Lets pick_week's carry-across-week downweighting be asserted exactly,
    rather than only sampled statistically."""

    def choices(self, population, weights, k=1):
        best_index = weights.index(max(weights))
        return [population[best_index]] * k


class OwnedOnlyTests(unittest.TestCase):
    """SPEC.md §5.12: the picker only ever draws from Owned watches."""

    def setUp(self) -> None:
        self.records = [
            _record("owned-a", status="Owned"),
            _record("owned-b", status="Owned"),
            _record("wishlist", status="Wishlist"),
            _record("sold", status="Sold"),
            _record("gifted", status="Gifted"),
            _record("incoming", status="Incoming"),
        ]

    def test_pick_random_never_returns_a_non_owned_watch(self) -> None:
        rand = random.Random(1)
        seen = {pick_random(self.records, rand).slug for _ in range(200)}
        self.assertEqual(seen, {"owned-a", "owned-b"})

    def test_pick_weighted_never_returns_a_non_owned_watch(self) -> None:
        rand = random.Random(1)
        seen = {pick_weighted(self.records, rand, today=TODAY).slug for _ in range(200)}
        self.assertEqual(seen, {"owned-a", "owned-b"})

    def test_pick_week_only_uses_owned_watches(self) -> None:
        picks = pick_week(self.records, TODAY, MODE_RANDOM, rand=random.Random(1))
        self.assertTrue(all(record.slug in {"owned-a", "owned-b"} for record in picks.values()))

    def test_no_owned_watches_raises(self) -> None:
        no_owned = [_record("wishlist", status="Wishlist")]
        with self.assertRaises(ValueError):
            pick_random(no_owned)
        with self.assertRaises(ValueError):
            pick_weighted(no_owned)
        with self.assertRaises(ValueError):
            pick_week(no_owned, TODAY, MODE_WEIGHTED)


class PickRandomTests(unittest.TestCase):
    def test_uniform_distribution_over_many_trials(self) -> None:
        records = [_record(f"w{i}") for i in range(5)]
        rand = random.Random(42)
        counts = {r.slug: 0 for r in records}
        trials = 5000
        for _ in range(trials):
            counts[pick_random(records, rand).slug] += 1
        expected = trials / len(records)
        for slug, count in counts.items():
            # Generous tolerance -- this is a sanity check on uniformity,
            # not a statistical proof, and must never flake in CI.
            self.assertGreater(count, expected * 0.7, f"{slug} picked too rarely for a uniform draw")
            self.assertLess(count, expected * 1.3, f"{slug} picked too often for a uniform draw")

    def test_single_owned_watch_is_always_that_watch(self) -> None:
        records = [_record("only")]
        rand = random.Random(7)
        for _ in range(20):
            self.assertEqual(pick_random(records, rand).slug, "only")


class ComputeWeightsTests(unittest.TestCase):
    def test_every_owned_watch_keeps_a_nonzero_weight(self) -> None:
        records = [
            _record("worn-today", worn=[TODAY]),
            _record("worn-recently", worn=[TODAY - timedelta(days=2)]),
            _record("never-worn"),
            _record("worn-in-the-future", worn=[TODAY + timedelta(days=10)]),  # a pre-planned day, SPEC.md §5.5
        ]
        weights = compute_weights(records, today=TODAY)
        for slug, weight in weights.items():
            self.assertGreater(weight, 0.0, f"{slug} has a non-positive weight")

    def test_never_worn_gets_the_maximum_weight(self) -> None:
        records = [_record("never-worn"), _record("worn-long-ago", worn=[TODAY - timedelta(days=365)])]
        weights = compute_weights(records, today=TODAY)
        self.assertEqual(weights["never-worn"], max(weights.values()))
        self.assertGreater(weights["never-worn"], weights["worn-long-ago"])

    def test_most_recently_worn_gets_the_least_weight(self) -> None:
        records = [
            _record("today", worn=[TODAY]),
            _record("ten-days-ago", worn=[TODAY - timedelta(days=10)]),
            _record("never-worn"),
        ]
        weights = compute_weights(records, today=TODAY)
        self.assertLess(weights["today"], weights["ten-days-ago"])
        self.assertLess(weights["ten-days-ago"], weights["never-worn"])

    def test_all_never_worn_are_tied(self) -> None:
        records = [_record("a"), _record("b"), _record("c")]
        weights = compute_weights(records, today=TODAY)
        self.assertEqual(len(set(weights.values())), 1)


class PickWeightedTests(unittest.TestCase):
    def test_neglected_watch_is_favoured_but_never_certain(self) -> None:
        """SPEC.md milestone 20 step 3: a gentle curve, not a hard cutoff --
        the recently-worn watch must still turn up occasionally."""
        records = [_record("neglected"), _record("worn-today", worn=[TODAY])]
        rand = random.Random(3)
        counts = {"neglected": 0, "worn-today": 0}
        for _ in range(2000):
            counts[pick_weighted(records, rand, today=TODAY).slug] += 1
        self.assertGreater(counts["neglected"], counts["worn-today"])
        self.assertGreater(counts["worn-today"], 0, "the recently-worn watch should never be truly excluded")

    def test_pick_one_dispatches_by_mode(self) -> None:
        records = [_record("only")]
        self.assertEqual(pick_one(records, MODE_RANDOM, random.Random(1)).slug, "only")
        self.assertEqual(pick_one(records, MODE_WEIGHTED, random.Random(1), today=TODAY).slug, "only")
        with self.assertRaises(ValueError):
            pick_one(records, "bogus-mode")


class WeekDatesTests(unittest.TestCase):
    def test_returns_seven_consecutive_days_starting_monday(self) -> None:
        for anchor in (TODAY, TODAY + timedelta(days=3), TODAY + timedelta(days=6)):
            days = week_dates(anchor)
            self.assertEqual(len(days), 7)
            self.assertEqual(days[0].weekday(), 0)
            for previous, current in zip(days, days[1:]):
                self.assertEqual((current - previous).days, 1)

    def test_normalises_a_midweek_anchor_to_that_week_s_monday(self) -> None:
        wednesday = TODAY + timedelta(days=2)
        self.assertEqual(week_dates(wednesday), week_dates(TODAY))


class PickWeekTests(unittest.TestCase):
    def test_fills_exactly_seven_days(self) -> None:
        records = [_record(f"w{i}") for i in range(3)]
        picks = pick_week(records, TODAY, MODE_RANDOM, rand=random.Random(1))
        self.assertEqual(set(picks.keys()), set(week_dates(TODAY)))

    def test_random_mode_prefers_distinct_picks_with_more_than_seven_owned(self) -> None:
        records = [_record(f"w{i}") for i in range(10)]
        for seed in range(10):
            picks = pick_week(records, TODAY, MODE_RANDOM, rand=random.Random(seed))
            self.assertEqual(len(set(r.slug for r in picks.values())), 7, f"seed {seed} produced a repeat")

    def test_random_mode_allows_repeats_with_seven_or_fewer_owned(self) -> None:
        records = [_record(f"w{i}") for i in range(3)]
        picks = pick_week(records, TODAY, MODE_RANDOM, rand=random.Random(1))
        self.assertEqual(len(picks), 7)
        self.assertTrue(all(record.slug in {"w0", "w1", "w2"} for record in picks.values()))

    def test_weighted_mode_carries_bias_across_the_week(self) -> None:
        """SPEC.md milestone 20 step 16, made deterministic with a fake
        argmax random source: three never-worn watches start tied, so the
        first day goes to whichever is first; having just been picked, that
        watch's weight drops below the other two for the very next day."""
        records = [_record("a"), _record("b"), _record("c")]
        picks = pick_week(records, TODAY, MODE_WEIGHTED, rand=_ArgmaxRand(), today=TODAY)
        days = week_dates(TODAY)
        self.assertEqual(picks[days[0]].slug, "a")
        self.assertNotEqual(picks[days[1]].slug, "a")
        self.assertNotEqual(picks[days[2]].slug, picks[days[1]].slug)

    def test_weighted_mode_never_zero_across_a_full_week_roll(self) -> None:
        """Even the watch that gets picked (and therefore downweighted)
        keeps a nonzero chance on every subsequent day -- this would raise
        in random.choices() if any weight ever reached zero or went
        negative, so a clean run is itself the assertion."""
        records = [_record(f"w{i}") for i in range(4)]
        for seed in range(30):
            pick_week(records, TODAY, MODE_WEIGHTED, rand=random.Random(seed), today=TODAY)

    def test_week_roll_does_not_crash_with_a_single_owned_watch(self) -> None:
        records = [_record("only")]
        picks = pick_week(records, TODAY, MODE_WEIGHTED, rand=random.Random(1), today=TODAY)
        self.assertTrue(all(record.slug == "only" for record in picks.values()))


if __name__ == "__main__":
    unittest.main()
