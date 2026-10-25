"""Loads the real dashboard page (pages/semantic_brain.py) with Streamlit's headless AppTest against the temp test
database: it must render without an exception, show the right state per channel, and never show a stack trace when
the database fails. Skipped automatically if streamlit is not installed.
Run:  python -m unittest tests.test_semantic_dashboard_page -v"""
import os
import unittest
from datetime import datetime, timezone
from unittest import mock

from tests import comment_helpers as T   # sets up a temp SQLite DB before agents.database loads
from agents.database import db

try:
    from streamlit.testing.v1 import AppTest
    import streamlit as st
except ImportError:   # pragma: no cover
    AppTest = None

PAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pages", "semantic_brain.py")


def report(n, lo, hi, rho, **kw):
    return {"outcome": "views24h-v1", "videos_with_outcome": n + 2, "videos_with_neighbours": n, "min_eval": 30,
            "mae_baseline": 0.9, "mae_semantic": 0.8, "mean_gain": 0.1, "gain_ci95": [lo, hi], "spearman": rho,
            "gate_passed": False, "model_id": "m", "revision": "abcdef123456", **kw}


def texts(elements):
    return [e.value for e in elements]


@unittest.skipIf(AppTest is None, "streamlit not installed")
class PageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        now = datetime.now(timezone.utc).isoformat()
        db.save_semantic_eval("gaming", report(14, 0.0, 0.3, 0.2), now)            # too few videos
        db.save_semantic_eval("bhakti", report(40, -0.1, 0.3, 0.2), now)           # enough videos, interval crosses 0
        db.save_semantic_eval("horror", report(40, 0.05, 0.5, 0.3, gate_passed=True), now)   # passes
        db.save_semantic_eval("cricket", {"outcome": "views24h-v1", "videos_with_outcome": 2,
                                          "videos_with_neighbours": 0, "min_eval": 30, "gate_passed": False,
                                          "note": "no video had neighbour evidence at its publish time"}, now)

    def setUp(self):
        st.cache_data.clear()

    def run_page(self):
        at = AppTest.from_file(PAGE, default_timeout=30).run()
        self.assertEqual([str(e.value) for e in at.exception], [])
        return at

    def select(self, at, channel):
        at.selectbox[0].set_value(channel).run()
        self.assertEqual([str(e.value) for e in at.exception], [])
        return at

    def test_renders_and_the_overview_lists_every_channel(self):
        at = self.run_page()
        table = at.dataframe[0].value
        self.assertEqual(list(table["Channel"]), ["English", "Hindi", "Cricket", "Finance", "Gaming", "Horror", "Bhakti"])
        by = dict(zip(table["Channel"], table["Status"]))
        self.assertIn("Ready to consider", by["Horror"])
        self.assertIn("Not yet", by["Gaming"])
        self.assertIn("No data yet", by["Cricket"])
        self.assertIn("No data yet", by["Finance"])            # never evaluated
        why = dict(zip(table["Channel"], table["What is missing"]))
        self.assertEqual(why["Gaming"], "Needs 30, has 14")
        self.assertIn("could be luck", why["Bhakti"])
        self.assertTrue(all(len(w) <= 45 for w in why.values()))
        self.assertNotIn("None", " ".join(map(str, table.values.flatten())))   # missing values show a dash

    def test_channel_detail_banners_say_what_is_missing(self):
        at = self.run_page()
        self.select(at, "gaming")
        self.assertTrue(any("Only 14 of the 30" in t for t in texts(at.warning)))
        self.select(at, "bhakti")
        self.assertTrue(any("could still be luck" in t for t in texts(at.warning)))
        self.select(at, "horror")
        self.assertTrue(any(t.startswith("Ready to consider") for t in texts(at.success)))
        self.select(at, "cricket")
        self.assertTrue(any("No data yet" in t for t in texts(at.info)))

    def test_a_database_failure_shows_a_safe_message_not_a_stack_trace(self):
        with mock.patch.object(db, "get_semantic_eval_reports", side_effect=RuntimeError("password=hunter2 host=x")):
            at = AppTest.from_file(PAGE, default_timeout=30).run()
        self.assertEqual(len(at.exception), 0)
        shown = " ".join(texts(at.error))
        self.assertIn("Could not read the database", shown)
        self.assertNotIn("hunter2", shown)


if __name__ == "__main__":
    unittest.main()
