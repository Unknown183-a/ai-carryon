"""Cricket and Gaming keep their own tables; the semantic evaluation must read them, and an empty result must say why.
Run:  python -m unittest tests.test_semantic_channel_sources -v"""
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone

from agents import semantic_features as sf
from agents import semantic_report as sr
from tools import eval_semantic as ev

PUB = datetime(2026, 1, 1, tzinfo=timezone.utc)


def snap(hours, views):
    return {"views": views, "likes": 0, "comments": 0, "timestamp": (PUB + timedelta(hours=hours)).isoformat()}


class FakeChannelDb:
    def __init__(self, grouped):
        self.grouped = grouped

    def get_all_snapshots(self):
        return self.grouped


def install(name, db, err=None):
    mod = types.ModuleType(name)
    mod.db, mod.db_init_error = db, err
    sys.modules[name] = mod


class HistoryRowsTests(unittest.TestCase):
    def tearDown(self):
        for n in ("agents_cricket.database", "agents_gaming.database"):
            sys.modules.pop(n, None)

    def test_gaming_rows_come_from_its_own_tables_and_measure_24h_views(self):
        grouped = {"g1": {"title": "Boss fight", "published": PUB.isoformat(),
                          "snapshots": [snap(1, 500), snap(24, 20000), snap(30, 22000)]}}
        install("agents_gaming.database", FakeChannelDb(grouped))
        hist = sf.build_history(sf.history_rows("gaming"), as_of=PUB + timedelta(days=5))
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0].views_24h, 20000)

    def test_cricket_uses_the_cricket_module(self):
        install("agents_cricket.database", FakeChannelDb({"c1": {"title": "Match", "published": PUB.isoformat(),
                                                                  "snapshots": [snap(24, 50000)]}}))
        self.assertEqual(sf.history_rows("cricket")["videos"][0]["video_id"], "c1")

    def test_unavailable_database_is_an_error_not_empty(self):
        install("agents_gaming.database", None, err="no connection")
        with self.assertRaises(RuntimeError):
            sf.history_rows("gaming")

    def test_other_channels_use_the_shared_db(self):
        class Shared:
            def get_semantic_history_rows(self, channel):
                return {"videos": [], "ab_tests": [], "snapshots": [], "posted": [], "channel": channel}
        self.assertEqual(sf.history_rows("english", Shared())["channel"], "english")

    def test_source_notes(self):
        self.assertIn("view", sf.source_note("horror"))
        self.assertIsNone(sf.source_note("gaming"))


class DiagnosisTests(unittest.TestCase):
    def report(self, grouped):
        install("agents_gaming.database", FakeChannelDb(grouped))
        history = sf.build_history(sf.history_rows("gaming"), as_of=PUB + timedelta(days=30))
        return ev.evaluate(history, {h.text: [1.0, 0.0] for h in history})

    def tearDown(self):
        sys.modules.pop("agents_gaming.database", None)

    def test_no_videos(self):
        self.assertEqual(self.report({})["diagnosis"], "no_videos")

    def test_videos_without_24h_snapshot(self):
        r = self.report({"g": {"title": "x", "published": PUB.isoformat(), "snapshots": [snap(1, 10), snap(80, 99)]}})
        self.assertEqual((r["diagnosis"], r["videos_found"], r["videos_with_24h_views"]), ("no_outcomes", 1, 0))

    def test_too_few_measured(self):
        r = self.report({"g": {"title": "x", "published": PUB.isoformat(), "snapshots": [snap(24, 10)]}})
        self.assertEqual(r["diagnosis"], "few_outcomes")


class ReportWordingTests(unittest.TestCase):
    def test_diagnosis_codes_reach_the_dashboard(self):
        base = {"videos_with_neighbours": 0, "videos_found": 12, "videos_with_24h_views": 0}
        for code in ("no_videos", "no_outcomes", "few_outcomes", "no_neighbours", "source_unavailable"):
            state, _, why = sr.gate_status({**base, "diagnosis": code})
            self.assertEqual(state, sr.NO_DATA)
            self.assertNotIn("at the time it was published", why if code != "no_neighbours" else "")
        self.assertIn("12 videos", sr.gate_status({**base, "diagnosis": "no_outcomes"})[2])

    def test_negative_gain_is_not_called_luck(self):
        rep = {"videos_with_neighbours": 40, "min_eval": 30, "mean_gain": -0.1, "gain_ci95": [-0.3, 0.1], "spearman": 0.2}
        state, _, why = sr.gate_status(rep)
        self.assertEqual(state, sr.NOT_YET)
        self.assertNotIn("luck", why)
        self.assertIn("no closer", why)
        self.assertNotIn("luck", sr.summary_row("english", rep)["why"])

    def test_positive_gain_with_wide_interval_still_luck(self):
        rep = {"videos_with_neighbours": 40, "min_eval": 30, "mean_gain": 0.1, "gain_ci95": [-0.05, 0.25], "spearman": 0.2}
        self.assertIn("luck", sr.gate_status(rep)[2])


if __name__ == "__main__":
    unittest.main()
