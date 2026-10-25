"""Tests for agents/semantic_report.py (pure dashboard helpers). Run: python -m unittest tests.test_semantic_report -v"""
import json
import unittest

from agents import semantic_report as sr


def rep(n=40, lo=0.1, hi=0.5, rho=0.4, passed=True, **kw):
    return {"videos_with_neighbours": n, "min_eval": 30, "gain_ci95": [lo, hi], "spearman": rho, "mean_gain": 0.3,
            "gate_passed": passed, "channel": "english", "evaluated_at": "2026-10-26T03:30:00+00:00", **kw}


class GateStatusTests(unittest.TestCase):
    def test_passed(self):
        state, label, why = sr.gate_status(rep())
        self.assertEqual(state, sr.PASSED)
        self.assertIn("Ready", label)

    def test_never_evaluated_and_no_evidence(self):
        self.assertEqual(sr.gate_status(None)[0], sr.NO_DATA)
        self.assertEqual(sr.gate_status({})[0], sr.NO_DATA)
        s, _, why = sr.gate_status(rep(n=0, note="no video had neighbour evidence at its publish time"))
        self.assertEqual(s, sr.NO_DATA)
        self.assertIn("similar past videos", why)

    def test_too_few_videos_says_how_many(self):
        s, _, why = sr.gate_status(rep(n=12, passed=False))
        self.assertEqual(s, sr.NOT_YET)
        self.assertIn("12 of the 30", why)

    def test_a_good_looking_small_sample_is_never_ready(self):
        self.assertNotEqual(sr.gate_status(rep(n=29, lo=0.5, hi=0.9, rho=0.9))[0], sr.PASSED)

    def test_interval_touching_zero_is_not_enough(self):
        s, _, why = sr.gate_status(rep(lo=-0.05, hi=0.4, passed=False))
        self.assertEqual(s, sr.NOT_YET)
        self.assertIn("-0.05", why)
        self.assertIn("luck", why)

    def test_negative_or_missing_rank_correlation_blocks(self):
        for rho in (-0.1, 0.0, None, float("nan")):
            s, _, why = sr.gate_status(rep(rho=rho, passed=False))
            self.assertEqual(s, sr.NOT_YET, rho)
            self.assertIn("rank correlation", why)

    def test_nan_interval_survives_a_json_round_trip(self):
        r = json.loads(json.dumps(rep(lo=float("nan"), hi=float("nan"), passed=False)))
        s, _, why = sr.gate_status(r)
        self.assertEqual(s, sr.NOT_YET)
        self.assertIn("unknown", why)

    def test_the_flag_is_not_trusted_over_the_numbers(self):
        self.assertNotEqual(sr.gate_status(rep(lo=-1, hi=1, passed=True))[0], sr.PASSED)


class ReportListTests(unittest.TestCase):
    def test_latest_per_channel_and_history_order(self):
        reps = [rep(evaluated_at="2026-10-26T03:30:00+00:00", mean_gain=0.1),
                rep(evaluated_at="2026-11-02T03:30:00+00:00", mean_gain=0.2),
                rep(evaluated_at="2026-10-19T03:30:00+00:00", mean_gain=0.0),
                rep(channel="hindi", evaluated_at="2026-10-26T03:30:00+00:00", n=0)]
        latest = sr.latest_per_channel(reps)
        self.assertEqual(latest["english"]["mean_gain"], 0.2)
        self.assertEqual(set(latest), {"english", "hindi"})
        h = sr.history(reps, "english")
        self.assertEqual([x["mean_gain"] for x in h], [0.0, 0.1, 0.2])        # oldest first, for the chart
        self.assertEqual(sr.history(reps, "gaming"), [])

    def test_summary_row_handles_missing_numbers(self):
        row = sr.summary_row("gaming", None)
        self.assertEqual((row["channel"], row["scored"], row["mean_gain"], row["interval"]), ("Gaming", 0, None, None))
        row = sr.summary_row("english", rep())
        self.assertEqual(row["interval"], "+0.10 to +0.50")
        self.assertEqual(row["channel"], "English")

    def test_table_reasons_are_short_enough_to_fit_a_cell_and_name_the_gap(self):
        cases = [(None, "Not evaluated yet"), (rep(n=0), "No similar past videos yet"),
                 (rep(n=12), "Needs 30, has 12"), (rep(lo=-0.05), "low end -0.05"),
                 (rep(rho=-0.2), "-0.20"), (rep(), "All checks met")]
        for report, expected in cases:
            why = sr.summary_row("english", report)["why"]
            self.assertIn(expected, why)
            self.assertLessEqual(len(why), 45, why)


def d(run, topic, selected=0, scores=None, channel="english", at="2026-10-26T10:00:00+00:00"):
    return {"run_id": run, "topic": topic, "selected": selected, "brain_scores": scores or {}, "channel": channel,
            "decided_at": at, "source": "brains"}


class DecisionSummaryTests(unittest.TestCase):
    def test_empty(self):
        s = sr.decision_summary([])
        self.assertEqual((s["rankings"], s["candidates"], s["latest"]), (0, 0, None))

    def test_counts_and_agreement(self):
        rows = []
        for topic, score in (("a", 0.7), ("b", 0.4)):                     # run 1: shadow prefers a, a was used
            rows.append(d("r1", topic, selected=int(topic == "a"), scores={"sh": {"role": "shadow", "score": score}}))
        for topic, score in (("a", 0.3), ("b", 0.8)):                     # run 2: shadow prefers b, a was used
            rows.append(d("r2", topic, selected=int(topic == "a"), scores={"sh": {"role": "shadow", "score": score}},
                          at="2026-10-26T12:00:00+00:00"))
        for topic in ("a", "b"):                                          # run 3: shadow had no opinion, nothing used
            rows.append(d("r3", topic, scores={"sh": {"role": "shadow", "score": 0.5}}))
        s = sr.decision_summary(rows)
        self.assertEqual((s["rankings"], s["candidates"], s["with_selection"]), (3, 6, 2))
        self.assertEqual((s["with_shadow_opinion"], s["comparable"], s["shadow_agreed"]), (2, 2, 1))
        self.assertEqual(s["latest"], "2026-10-26T12:00:00+00:00")

    def test_non_shadow_scores_are_ignored(self):
        rows = [d("r1", "a", 1, {"p": {"role": "primary", "score": 0.9}}), d("r1", "b", 0, {"p": {"role": "primary", "score": 0.1}})]
        s = sr.decision_summary(rows)
        self.assertEqual((s["with_shadow_opinion"], s["comparable"]), (0, 0))


if __name__ == "__main__":
    unittest.main()
