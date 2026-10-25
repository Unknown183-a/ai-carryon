"""Tests for tools/eval_semantic.py: it must find real signal, reject noise, and never peek at the future.
Run:  python -m unittest tests.test_eval_semantic -v"""
import random
import unittest
from datetime import datetime, timedelta, timezone

from agents import semantic_features as sf
from tools import eval_semantic as ev

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def synth(n, signal, seed=1, hours_between=12):
    """Two topic clusters (A: ~1000 views, B: ~100 views). With signal=False the views ignore the cluster."""
    rng = random.Random(seed)
    items, vecs = [], {}
    for i in range(n):
        cluster = rng.choice("AB")
        text = f"{cluster} topic {i}"
        base = 1000 if cluster == "A" else 100
        views = base * rng.uniform(0.7, 1.4) if signal else rng.choice([100, 1000]) * rng.uniform(0.7, 1.4)
        items.append(sf.HistoryItem(text, START + timedelta(hours=hours_between * i), views))
        vecs[text] = [1.0, 0.05 * rng.random()] if cluster == "A" else [0.05 * rng.random(), 1.0]
    return items, vecs


CFG = sf.SemanticConfig(k=5, min_similarity=0.6, recent_days=14, min_history=3)


class EvalTests(unittest.TestCase):
    def test_finds_real_signal_and_passes_the_gate(self):
        items, vecs = synth(120, signal=True)
        r = ev.evaluate(items, vecs, CFG)
        self.assertTrue(r["gate_passed"], r)
        self.assertGreater(r["mean_gain"], 0)
        self.assertGreater(r["gain_ci95"][0], 0)
        self.assertGreater(r["spearman"], 0.5)
        self.assertLess(r["mae_semantic"], r["mae_baseline"])

    def test_noise_does_not_pass_the_gate(self):
        for seed in range(3):
            items, vecs = synth(120, signal=False, seed=seed)
            self.assertFalse(ev.evaluate(items, vecs, CFG)["gate_passed"], seed)

    def test_a_small_sample_never_passes_even_with_perfect_signal(self):
        items, vecs = synth(25, signal=True)
        r = ev.evaluate(items, vecs, CFG)
        self.assertLess(r["videos_with_neighbours"], ev.MIN_EVAL)
        self.assertFalse(r["gate_passed"])

    def test_no_peeking_later_videos_cannot_change_earlier_rows(self):
        items, vecs = synth(80, signal=True)
        early = ev.evaluate_rows(items[:50], vecs, CFG)
        # the same first 50 videos, plus 30 later ones whose outcomes are absurd
        later = [sf.HistoryItem(i.text, i.published, 10 ** 7) for i in items[50:]]
        mixed = ev.evaluate_rows(items[:50] + later, vecs, CFG)
        self.assertGreater(len(early), 20)
        self.assertEqual(mixed[:len(early)], early)                       # identical, value for value

    def test_a_video_is_never_its_own_neighbour(self):
        item = sf.HistoryItem("only", START + timedelta(days=5), 500.0)
        prior = [sf.HistoryItem(f"p{i}", START + timedelta(days=i), 100.0) for i in range(4)]
        vecs = {"only": [1.0, 0.0], **{f"p{i}": [0.0, 1.0] for i in range(4)}}
        rows = ev.evaluate_rows(prior + [item], vecs, CFG)
        self.assertIsNone(rows[-1]["ratio"])                              # nothing similar EXCEPT itself => no evidence

    def test_empty_and_unknown_history_are_reported_not_crashed(self):
        self.assertEqual(ev.evaluate([], {}, CFG)["videos_with_outcome"], 0)
        items = [sf.HistoryItem("x", START, None), sf.HistoryItem("y", START + timedelta(days=1), None)]
        r = ev.evaluate(items, {"x": [1.0, 0.0], "y": [0.0, 1.0]}, CFG)
        self.assertFalse(r["gate_passed"])

    def test_spearman_and_bootstrap_helpers(self):
        self.assertAlmostEqual(ev.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertAlmostEqual(ev.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)
        self.assertIsNone(ev.spearman([1, 1, 1], [1, 2, 3]))                 # constant input has no rank correlation
        self.assertIsNone(ev.spearman([1, 2], [1, 2]))
        lo, hi = ev.bootstrap_mean_ci([1.0] * 20)
        self.assertEqual((lo, hi), (1.0, 1.0))
        lo, hi = ev.bootstrap_mean_ci([-1.0, 1.0] * 20)
        self.assertLess(lo, 0 < hi)


if __name__ == "__main__":
    unittest.main()
