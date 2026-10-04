"""Offline tests for the Universal Hook Engine (no network, no LLM, no Pexels).

    python -m unittest tests.test_hook_engine -v

The render tests use the real ffmpeg (imageio_ffmpeg) on synthetic clips and
are skipped automatically if it or moviepy is unavailable.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

from agents import hook_engine as he
from agents.hook_engine import HookCandidate


class FakeLLM:
    """Stands in for a channel's safe_invoke; returns scripted replies in order."""
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, prompt):
        self.calls.append(prompt)
        r = self.replies.pop(0) if self.replies else "not json"
        if isinstance(r, Exception):
            raise r
        return types.SimpleNamespace(content=r if isinstance(r, str) else json.dumps(r))


def cand(cid, title, dur=5, w=1080, h=1920, query="q"):
    return HookCandidate(clip_id=str(cid), provider="pexels",
                         url=f"https://www.pexels.com/video/{title.replace(' ', '-')}-{cid}/",
                         duration=dur, query=query, title=title, width=w, height=h,
                         files=[{"link": "x", "file_type": "video/mp4", "width": 1080}])


CRICKET_STORY = {"main_topic": "India cricket match", "main_event": "final over comeback",
                 "emotion": "shock", "subject": "Indian cricket team", "location": "",
                 "action": "comeback", "story_type": "sports_story", "target_audience": ""}
CRICKET_INTENT = {"hook_type": "shock", "emotion": "shock", "visual_need": [],
                  "keywords": ["cricket", "india", "comeback", "crowd"], "minimum_relevance": 0.70}


# ── helpers ───────────────────────────────────────────────────────────────
class TestUtilities(unittest.TestCase):
    def test_slug_title(self):
        self.assertEqual(he.slug_title("https://www.pexels.com/video/a-wifi-router-3045678/"), "a wifi router")
        self.assertEqual(he.slug_title("garbage"), "")

    def test_norm01_accepts_all_scales(self):
        self.assertEqual(he._norm01(0.9), 0.9)
        self.assertAlmostEqual(he._norm01(9), 0.9)
        self.assertAlmostEqual(he._norm01(85), 0.85)
        self.assertEqual(he._norm01("junk", 0.4), 0.4)
        self.assertEqual(he._norm01(-3), 0.0)

    def test_extract_json_handles_fences_and_noise(self):
        self.assertEqual(he._extract_json('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(he._extract_json('Sure! [{"i": 0}] hope that helps'), [{"i": 0}])
        self.assertIsNone(he._extract_json("no json here"))

    def test_weights_sum_to_one_and_formula(self):
        self.assertAlmostEqual(sum(he.WEIGHTS.values()), 1.0)
        c = cand(1, "x")
        c.relevance_score, c.visual_score, c.curiosity_score = 1.0, 0.0, 0.0
        c.emotional_score = c.continuity_score = 0.0
        self.assertAlmostEqual(he.final_score(c), 0.40)
        c.relevance_score = c.visual_score = c.curiosity_score = 1.0
        c.emotional_score = c.continuity_score = 1.0
        self.assertAlmostEqual(he.final_score(c), 1.0)

    def test_hook_duration_follows_spec(self):
        self.assertTrue(0.8 <= he.hook_duration("action", 10) <= 1.5)
        self.assertTrue(1.5 <= he.hook_duration("curiosity", 10) <= 2.5)
        self.assertTrue(2.0 <= he.hook_duration("mystery", 10) <= 3.0)
        self.assertEqual(he.hook_duration("mystery", 1.0), 1.0)      # never longer than the clip
        self.assertGreaterEqual(he.hook_duration("action", 0.2), 0.8)  # floor


# ── queries ───────────────────────────────────────────────────────────────
class TestQueries(unittest.TestCase):
    def test_pads_to_at_least_three_and_caps_at_five(self):
        prof = he.CHANNEL_PROFILES["cricket"]
        q = he.build_queries(["cricket crowd"], CRICKET_INTENT, prof)
        self.assertGreaterEqual(len(q), 3)
        q = he.build_queries([f"cricket idea {i}" for i in range(9)], CRICKET_INTENT, prof)
        self.assertEqual(len(q), 5)

    def test_cleans_and_dedupes(self):
        prof = he.CHANNEL_PROFILES["english"]
        q = he.build_queries(["AI Robot!!", "ai robot", "The   Robot  arm, close-up shot of parts"],
                             {"keywords": ["robot"]}, prof)
        self.assertEqual(q[0], "ai robot")
        self.assertEqual(q.count("ai robot"), 1)
        self.assertTrue(all(len(x.split()) <= 4 for x in q))

    def test_bhakti_blocks_dramatic_and_deity_terms(self):
        prof = he.CHANNEL_PROFILES["bhakti"]
        q = he.build_queries(["dramatic temple fire", "shocked crowd", "ganesh idol statue",
                              "diya flame close up", "temple bells", "aarti lamp"],
                             {"keywords": ["temple"]}, prof)
        for bad in ("dramatic", "shocked", "idol", "statue", "fire"):
            self.assertFalse(any(bad in x for x in q), f"{bad} leaked into {q}")
        self.assertIn("diya flame close up", q)

    def test_cricket_blocks_other_sports(self):
        q = he.build_queries(["football player celebration", "cricket player celebration"],
                             CRICKET_INTENT, he.CHANNEL_PROFILES["cricket"])
        self.assertNotIn("football player celebration", q)

    def test_expand_queries_are_new_and_on_topic(self):
        prof = he.CHANNEL_PROFILES["cricket"]
        used = ["virat kohli diving catch", "cricket player reaction", "cricket stadium crowd"]
        ex = he.expand_queries(used, {"keywords": ["virat", "kohli", "catch"], "hook_type": "shock"}, prof)
        self.assertTrue(ex)
        self.assertFalse(set(ex) & set(used))
        self.assertTrue(all("shock" not in x for x in ex))


# ── planner ───────────────────────────────────────────────────────────────
class TestPlanner(unittest.TestCase):
    def test_llm_plan_is_parsed(self):
        llm = FakeLLM({"story": CRICKET_STORY,
                       "intent": {"hook_type": "shock", "emotion": "shock",
                                  "visual_need": ["crowd reaction"], "keywords": ["cricket", "crowd"]},
                       "queries": ["dramatic cricket reaction", "cricket crowd shocked",
                                   "intense cricket moment"]})
        story, intent, queries = he.generate_story_and_intent("India comeback", "script", "cricket", llm)
        self.assertEqual(story["main_event"], "final over comeback")
        self.assertEqual(intent["hook_type"], "shock")
        self.assertEqual(intent["minimum_relevance"], 0.70)
        self.assertGreaterEqual(len(queries), 3)
        self.assertEqual(len(llm.calls), 1)                 # ONE call for story + intent + queries

    def test_garbage_llm_falls_back_to_heuristic_plan(self):
        story, intent, queries = he.generate_story_and_intent(
            "India vs Australia T20", "s", "cricket", FakeLLM("totally not json"))
        self.assertGreaterEqual(len(queries), 3)
        self.assertIn("cricket", " ".join(queries))

    def test_no_llm_at_all_still_plans(self):
        _, intent, queries = he.generate_story_and_intent("Quantum chips", "s", "english", None)
        self.assertGreaterEqual(len(queries), 3)
        self.assertIn(intent["hook_type"], he.HOOK_TYPES)

    def test_bhakti_cannot_get_a_shock_hook(self):
        llm = FakeLLM({"story": {}, "intent": {"hook_type": "shock", "keywords": ["diwali"]},
                       "queries": ["diwali diya", "diya flame", "rangoli colors"]})
        _, intent, _ = he.generate_story_and_intent("Diwali puja", "s", "bhakti", llm)
        self.assertIn(intent["hook_type"], ("emotional", "mystery", "curiosity"))

    def test_text_hook_hint_is_respected_when_llm_is_absent(self):
        _, intent, _ = he.generate_story_and_intent("Match", "s", "cricket", None, hint_hook_type="mystery")
        self.assertEqual(intent["hook_type"], "mystery")


# ── scoring and the 70% gate ──────────────────────────────────────────────
class TestScoring(unittest.TestCase):
    def test_spec_example_a_b_pass_c_rejected(self):
        """Spec §10: celebrating Indian player 91%, stadium crowd 78%, football 21%."""
        a = cand(1, "indian cricket player celebrating with team")
        b = cand(2, "cricket stadium crowd cheering")
        c = cand(3, "football player celebration on pitch")
        llm = FakeLLM([
            {"i": 0, "relevance": 0.91, "visual": 0.9, "curiosity": 0.8, "emotional": 0.8, "continuity": 0.9},
            {"i": 1, "relevance": 0.80, "visual": 0.8, "curiosity": 0.6, "emotional": 0.7, "continuity": 0.8},
            {"i": 2, "relevance": 0.21, "visual": 0.9, "curiosity": 0.7, "emotional": 0.8, "continuity": 0.2},
        ])
        he.score_candidates([a, b, c], CRICKET_STORY, CRICKET_INTENT, llm)
        self.assertGreaterEqual(a.relevance_score, 0.70)
        self.assertGreaterEqual(b.relevance_score, 0.70)
        self.assertLess(c.relevance_score, 0.70)
        self.assertEqual(a.scorer, "llm")

    def test_llm_cannot_pass_a_title_with_no_topical_overlap_unless_very_sure(self):
        """No shared word + a lukewarm 0.85 must NOT clear 70%: 0.75*0.85 = 0.64."""
        c = cand(1, "man staring at wall in dark room")
        he.score_candidates([c], CRICKET_STORY, CRICKET_INTENT,
                            FakeLLM([{"i": 0, "relevance": 0.85, "visual": 1, "curiosity": 1,
                                      "emotional": 1, "continuity": 1}]))
        self.assertLess(c.relevance_score, 0.70)

    def test_llm_outage_uses_strict_lexical_scoring(self):
        good = cand(1, "cricket stadium crowd")       # 'cricket' + 'crowd' -> 2 hits
        weak = cand(2, "stadium lights at night")     # 0 hits
        he.score_candidates([good, weak], CRICKET_STORY, CRICKET_INTENT, FakeLLM(RuntimeError("down")))
        self.assertEqual(good.scorer, "lexical")
        self.assertGreaterEqual(good.relevance_score, 0.70)
        self.assertLess(weak.relevance_score, 0.70)

    def test_style_words_do_not_count_as_topical_overlap(self):
        terms = he.topical_terms({"main_topic": "kohli catch"}, {"keywords": ["dramatic", "intense", "reaction"]})
        self.assertNotIn("dramatic", terms)
        self.assertNotIn("reaction", terms)
        self.assertEqual(he.lexical_relevance("dramatic intense reaction moment", terms), 0.0)

    def test_partial_llm_reply_leaves_missing_rows_on_lexical(self):
        a, b = cand(1, "cricket crowd"), cand(2, "cricket stadium")
        he.score_candidates([a, b], CRICKET_STORY, CRICKET_INTENT,
                            FakeLLM([{"i": 0, "relevance": 0.9, "visual": 0.9, "curiosity": 0.9,
                                      "emotional": 0.9, "continuity": 0.9}]))
        self.assertEqual((a.scorer, b.scorer), ("llm", "lexical"))

    def test_ranking_uses_more_than_relevance(self):
        hi_rel_dull = cand(1, "cricket crowd")
        lo_rel_vivid = cand(2, "cricket crowd erupting")
        llm = FakeLLM([
            {"i": 0, "relevance": 0.90, "visual": 0.2, "curiosity": 0.2, "emotional": 0.2, "continuity": 0.9},
            {"i": 1, "relevance": 0.80, "visual": 1.0, "curiosity": 1.0, "emotional": 1.0, "continuity": 0.9},
        ])
        he.score_candidates([hi_rel_dull, lo_rel_vivid], CRICKET_STORY, CRICKET_INTENT, llm)
        self.assertGreater(lo_rel_vivid.final_score, hi_rel_dull.final_score)


# ── duplicate memory ──────────────────────────────────────────────────────
class MetaStore:
    def __init__(self):
        self.d = {}
    def get(self, k):
        return self.d.get(k)
    def set(self, k, v):
        self.d[k] = v


class TestHistory(unittest.TestCase):
    def hook(self, cid="111"):
        return {"provider": "pexels", "clip_id": cid, "query": "q", "hook_type": "shock",
                "relevance": 0.9, "visual_score": 0.8, "curiosity_score": 0.7, "final_score": 0.85,
                "duration": 2.0, "selection_reason": "r"}

    def test_recent_clip_rejected_and_old_clip_penalised(self):
        m = MetaStore()
        he.record_usage(self.hook("111"), "t", "english", m.get, m.set, "vid1")
        hist = he.load_history("english", m.get)
        self.assertEqual(hist["clips"]["111"]["usage_count"], 1)
        self.assertEqual(he.apply_history([cand(111, "a")], hist), [])         # inside cooldown

        hist["clips"]["111"]["used_at"] = "2020-01-01T00:00:00+00:00"           # long ago
        c = cand(111, "a")
        c.final_score = 0.80
        kept = he.apply_history([c], hist)
        self.assertEqual(len(kept), 1)
        self.assertAlmostEqual(kept[0].final_score, 0.75)
        self.assertEqual(he.apply_history([cand(222, "b")], hist)[0].clip_id, "222")

    def test_channels_are_isolated(self):
        m = MetaStore()
        he.record_usage(self.hook("111"), "t", "cricket", m.get, m.set)
        self.assertEqual(he.apply_history([cand(111, "a")], he.load_history("cricket", m.get)), [])
        self.assertEqual(len(he.apply_history([cand(111, "a")], he.load_history("hindi", m.get))), 1)

    def test_gameplay_hooks_are_logged_but_never_blocklisted(self):
        m = MetaStore()
        h = dict(self.hook("tw1"), provider="gameplay")
        he.record_usage(h, "t", "gaming", m.get, m.set, "vid")
        hist = he.load_history("gaming", m.get)
        self.assertEqual(hist["clips"], {})
        self.assertEqual(len(hist["log"]), 1)

    def test_memory_is_bounded_and_failures_never_raise(self):
        m = MetaStore()
        for i in range(he.MAX_REMEMBERED_CLIPS + 25):
            he.record_usage(self.hook(str(i)), "t", "english", m.get, m.set)
        hist = he.load_history("english", m.get)
        self.assertLessEqual(len(hist["clips"]), he.MAX_REMEMBERED_CLIPS)
        self.assertLessEqual(len(hist["log"]), he.MAX_LOG_ENTRIES)

        def boom(*_):
            raise RuntimeError("db down")
        he.record_usage(self.hook(), "t", "english", boom, boom)           # must not raise
        self.assertEqual(he.load_history("english", boom), {"clips": {}, "log": []})


# ── quality control ───────────────────────────────────────────────────────
class TestQuality(unittest.TestCase):
    def setUp(self):
        self.f = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        self.f.write(b"x" * 20_000)
        self.f.close()
        self.addCleanup(os.remove, self.f.name)

    def hook(self, **kw):
        h = {"relevance": 0.8, "duration": 2.0, "path": self.f.name, "width": 1080, "height": 1920}
        h.update(kw)
        return h

    def test_passes_when_everything_is_fine(self):
        self.assertEqual(he.quality_check(self.hook()), (True, "ok"))

    def test_rejections(self):
        self.assertFalse(he.quality_check(self.hook(relevance=0.69))[0])
        self.assertFalse(he.quality_check(self.hook(duration=5.0))[0])
        self.assertFalse(he.quality_check(self.hook(duration=0.3))[0])
        self.assertFalse(he.quality_check(self.hook(path="/nope.mp4"))[0])
        self.assertFalse(he.quality_check(self.hook(width=320, height=480))[0])
        self.assertFalse(he.quality_check(None)[0])


# ── select_hook end to end (fakes for search/download/LLM) ────────────────
def fake_download(_cand, path):
    with open(path, "wb") as f:
        f.write(b"x" * 20_000)


def make_search(pool):
    def search(queries, **kw):
        return [{"id": c.clip_id, "width": c.width, "height": c.height, "duration": c.duration,
                 "url": c.url, "files": c.files, "query": queries[0]} for c in pool]
    return search


def plan_reply(hook_type="shock"):
    return {"story": CRICKET_STORY, "intent": {"hook_type": hook_type, "keywords": ["cricket", "crowd"]},
            "queries": ["cricket crowd shocked", "cricket player reaction", "cricket stadium crowd"]}


class TestSelectHook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.meta = MetaStore()

    def run_select(self, pool, llm, **kw):
        return he.select_hook("India comeback", "script", "cricket", invoke=llm,
                              meta_get=self.meta.get, meta_set=self.meta.set,
                              search_fn=make_search(pool), download_fn=fake_download,
                              out_dir=self.tmp, **kw)

    def test_selects_best_eligible_hook(self):
        pool = [cand(1, "cricket crowd cheering"), cand(2, "football goal celebration"),
                cand(3, "cricket stadium crowd")] + [cand(10 + i, f"cricket crowd view {i}") for i in range(4)]
        rows = [{"i": 0, "relevance": 0.9, "visual": 0.9, "curiosity": 0.9, "emotional": 0.9, "continuity": 0.9},
                {"i": 1, "relevance": 0.1, "visual": 1.0, "curiosity": 1.0, "emotional": 1.0, "continuity": 0.1},
                {"i": 2, "relevance": 0.8, "visual": 0.5, "curiosity": 0.5, "emotional": 0.5, "continuity": 0.8}]
        rows += [{"i": 3 + k, "relevance": 0.5, "visual": 0.5, "curiosity": 0.5, "emotional": 0.5,
                  "continuity": 0.5} for k in range(4)]
        hook = self.run_select(pool, FakeLLM(plan_reply(), rows))
        self.assertIsNotNone(hook)
        self.assertEqual(hook["clip_id"], "1")
        self.assertGreaterEqual(hook["relevance"], 0.70)
        self.assertTrue(os.path.exists(hook["path"]))
        self.assertTrue(0.8 <= hook["duration"] <= 3.0)
        json.dumps(hook)                                    # checkpoint-serialisable

    def test_returns_none_when_nothing_reaches_70_percent(self):
        pool = [cand(i, f"football match {i}") for i in range(7)]
        rows = [{"i": i, "relevance": 0.3, "visual": 1, "curiosity": 1, "emotional": 1, "continuity": 1}
                for i in range(7)]
        self.assertIsNone(self.run_select(pool, FakeLLM(plan_reply(), rows)))

    def test_works_with_no_llm_and_never_forces_an_unrelated_clip(self):
        unrelated = [cand(i, f"cooking pasta in kitchen {i}") for i in range(7)]
        self.assertIsNone(self.run_select(unrelated, None))
        related = [cand(1, "cricket stadium crowd")] + [cand(20 + i, f"pasta {i}") for i in range(6)]
        hook = self.run_select(related, None)
        self.assertEqual(hook["clip_id"], "1")
        self.assertEqual(hook["scorer"], "lexical")

    def test_recently_used_clip_is_skipped_for_the_next_best(self):
        # no-LLM mode needs 2 topical words per title ('cricket' + 'stadium' via the channel anchors)
        pool = [cand(1, "cricket stadium lights"), cand(2, "cricket stadium crowd")] + \
               [cand(10 + i, f"pasta {i}") for i in range(5)]
        first = self.run_select(pool, None)
        he.record_usage(first, "t", "cricket", self.meta.get, self.meta.set, "v")
        second = self.run_select(pool, None)
        self.assertNotEqual(first["clip_id"], second["clip_id"])

    def test_thin_pool_triggers_one_expansion_round(self):
        calls = []

        def search(queries, **kw):
            calls.append(list(queries))
            return make_search([cand(1, "cricket stadium crowd")])(queries) if len(calls) > 1 else []
        hook = he.select_hook("India comeback", "s", "cricket", invoke=None, search_fn=search,
                              download_fn=fake_download, out_dir=self.tmp)
        self.assertEqual(len(calls), 2)
        self.assertFalse(set(calls[0]) & set(calls[1]))
        self.assertIsNotNone(hook)

    def test_never_raises(self):
        def boom(*a, **k):
            raise RuntimeError("pexels down")
        self.assertIsNone(he.select_hook("t", "s", "english", invoke=FakeLLM(RuntimeError("x")),
                                         search_fn=boom, download_fn=fake_download, out_dir=self.tmp))
        self.assertIsNone(he.select_hook(None, None, "nonexistent-channel", search_fn=boom, out_dir=self.tmp))

    def test_download_failure_tries_next_then_gives_up(self):
        pool = [cand(1, "cricket stadium crowd"), cand(2, "cricket crowd cheering")] + \
               [cand(10 + i, f"pasta {i}") for i in range(5)]

        def bad_download(_c, _p):
            raise IOError("net")
        self.assertIsNone(he.select_hook("India comeback", "s", "cricket", invoke=None,
                                         search_fn=make_search(pool), download_fn=bad_download,
                                         out_dir=self.tmp))

    def test_kill_switches(self):
        pool = [cand(1, "cricket stadium crowd")] * 1
        with mock.patch.dict(os.environ, {"HOOK_ENGINE": "0"}):
            self.assertIsNone(self.run_select(pool, None))
        with mock.patch.dict(os.environ, {"HOOK_ENGINE_CRICKET": "0"}):
            self.assertIsNone(self.run_select(pool, None))
            self.assertFalse(he.hook_enabled("cricket"))
            self.assertTrue(he.hook_enabled("english"))


# ── the shared Pexels client extension ────────────────────────────────────
class TestPexelsExtension(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # agents.video_clip_agent imports the LLM-backed image agent at module level
        sys.modules.setdefault("agents.image_agent", types.SimpleNamespace(generate_image_prompts=lambda *a: []))
        from agents import video_clip_agent
        cls.vca = video_clip_agent

    def raw(self, cid, dur, w=1080, h=1920):
        return {"id": cid, "width": w, "height": h, "duration": dur,
                "url": f"https://www.pexels.com/video/clip-{cid}/", "video_files": []}

    def test_search_videos_normalises_and_survives_errors(self):
        resp = mock.Mock()
        resp.json.return_value = {"videos": [self.raw(1, 4)]}
        with mock.patch.dict(os.environ, {"PEXELS_API_KEY": "k"}), \
                mock.patch.object(self.vca.requests, "get", return_value=resp) as g:
            out = self.vca.search_videos("cricket crowd")
        self.assertEqual(out[0]["id"], 1)
        self.assertEqual(g.call_args.kwargs["params"]["orientation"], "portrait")
        self.assertEqual(g.call_args.kwargs["headers"], {"Authorization": "k"})
        with mock.patch.dict(os.environ, {"PEXELS_API_KEY": "k"}), \
                mock.patch.object(self.vca.requests, "get", side_effect=IOError("x")):
            self.assertEqual(self.vca.search_videos("q"), [])
        with mock.patch.dict(os.environ, {"PEXELS_API_KEY": ""}):
            self.assertEqual(self.vca.search_videos("q"), [])

    def test_search_hook_videos_dedupes_filters_duration_and_caps(self):
        def fake(q, per_page=10, orientation="portrait", size=None):
            return {"a": [self.vca_c(1, 4), self.vca_c(2, 0.5), self.vca_c(3, 30)],
                    "b": [self.vca_c(1, 4), self.vca_c(4, 6), self.vca_c(5, 9)]}[q]
        self.vca_c = lambda cid, d: {"id": cid, "duration": d, "width": 1, "height": 2,
                                     "url": "", "files": [], "query": ""}
        with mock.patch.object(self.vca, "search_videos", side_effect=fake):
            out = self.vca.search_hook_videos(["a", "b"], duration_min=1, duration_max=10)
            self.assertEqual([c["id"] for c in out], [1, 4, 5])      # dup, too-short, too-long removed
            out = self.vca.search_hook_videos(["a", "b"], max_total=2)
            self.assertEqual(len(out), 2)
            out = self.vca.search_hook_videos(["a", "b"], exclude_ids=[4])
            self.assertNotIn(4, [c["id"] for c in out])


# ── gaming cold open ──────────────────────────────────────────────────────
class TestGameplayHook(unittest.TestCase):
    def setUp(self):
        from agents_gaming import gameplay_hook as gh
        self.gh = gh
        self.f = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        self.f.write(b"x")
        self.f.close()
        self.addCleanup(os.remove, self.f.name)
        self.moment = {"source": "vision", "intensity": 8, "key_timestamp": 12.0,
                       "moment_type": "CLUTCH", "what_happened": "1v4 clutch"}
        p = mock.patch.object(gh, "_probe", return_value=20.0)
        p.start()
        self.addCleanup(p.stop)

    def test_cuts_the_peak_from_the_real_gameplay(self):
        h = self.gh.select_gameplay_hook(self.f.name, self.moment, {"id": "c1", "title": "T"})
        self.assertEqual(h["provider"], "gameplay")
        self.assertEqual(h["relevance"], 1.0)
        self.assertEqual(h["path"], self.f.name)
        self.assertTrue(0.8 <= h["duration"] <= 1.5)                    # action moment -> fast cut
        self.assertLess(h["start"], 12.0)                               # peak lands inside the cut
        self.assertGreater(h["start"] + h["duration"], 12.0)
        self.assertLessEqual(h["start"] + h["duration"], 20.0)

    def test_no_hook_when_peak_time_is_unreliable_or_boring_or_already_first(self):
        g = self.gh.select_gameplay_hook
        self.assertIsNone(g(self.f.name, dict(self.moment, source="text"), {}))
        self.assertIsNone(g(self.f.name, dict(self.moment, source="heuristic"), {}))
        self.assertIsNone(g(self.f.name, dict(self.moment, intensity=4), {}))
        self.assertIsNone(g(self.f.name, dict(self.moment, key_timestamp=1.5), {}))
        self.assertIsNone(g("/missing.mp4", self.moment, {}))
        self.assertIsNone(g(self.f.name, None, {}))

    def test_cut_never_runs_past_the_end(self):
        h = self.gh.select_gameplay_hook(self.f.name, dict(self.moment, key_timestamp=19.9), {"id": "c"})
        self.assertLessEqual(h["start"] + h["duration"], 20.0 + 0.01)

    def test_kill_switch(self):
        with mock.patch.dict(os.environ, {"HOOK_ENGINE_GAMING": "0"}):
            self.assertIsNone(self.gh.select_gameplay_hook(self.f.name, self.moment, {}))


# ── real ffmpeg renders ───────────────────────────────────────────────────
def _ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _duration(path, ff):
    r = subprocess.run([ff, "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def _mean_rgb(video, t, ff):
    from PIL import Image
    out = tempfile.mktemp(suffix=".png")
    subprocess.run([ff, "-y", "-ss", str(t), "-i", video, "-frames:v", "1", out],
                   capture_output=True)
    img = Image.open(out).convert("RGB").resize((8, 8))
    px = list(img.getdata())
    os.remove(out)
    return tuple(sum(p[i] for p in px) / len(px) for i in range(3))


def _color_clip(ff, path, color, seconds, size="540x960"):
    subprocess.run([ff, "-y", "-f", "lavfi", "-i", f"color=c={color}:s={size}:d={seconds}:r=30",
                    "-pix_fmt", "yuv420p", path], capture_output=True, check=True)


@unittest.skipUnless(_ffmpeg(), "ffmpeg not available")
class TestRenderers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ff = _ffmpeg()
        cls.dir = tempfile.mkdtemp()
        cls.cwd = os.getcwd()
        os.chdir(cls.dir)                       # renderers write to ./output and read ./assets
        os.makedirs("assets/pexels_clips")
        os.makedirs("output")
        for i, col in enumerate(("blue", "green", "blue", "green"), 1):
            _color_clip(cls.ff, f"assets/pexels_clips/{i}.mp4", col, 8)
        _color_clip(cls.ff, "assets/hook.mp4", "red", 5)
        subprocess.run([cls.ff, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=12",
                        "output/voice.mp3"], capture_output=True, check=True)
        cls.hook = {"provider": "pexels", "path": "assets/hook.mp4", "start": 0.0, "duration": 2.0,
                    "hook_type": "curiosity", "selection_reason": "test"}

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.cwd)

    def test_prepare_hook_segment_math(self):
        from agents import hook_render as hr
        seg, hd, per = hr.prepare_hook_segment(self.ff, None, 20.0, 4, 540, 960)
        self.assertEqual((seg, hd, per), (None, 0.0, 5.0))              # == original behaviour
        seg, hd, per = hr.prepare_hook_segment(self.ff, self.hook, 20.0, 4, 540, 960,
                                               out_path="output/h.mp4")
        self.assertEqual(hd, 2.0)
        self.assertAlmostEqual(per, 4.5)                                # (20-2)/4
        self.assertAlmostEqual(_duration("output/h.mp4", self.ff), 2.0, delta=0.15)
        bad = dict(self.hook, path="assets/missing.mp4")
        self.assertEqual(hr.prepare_hook_segment(self.ff, bad, 20.0, 4, 540, 960)[0], None)

    def test_hook_is_capped_at_a_quarter_of_the_video(self):
        from agents import hook_render as hr
        _, hd, _ = hr.prepare_hook_segment(self.ff, dict(self.hook, duration=3.0), 4.0, 2, 540, 960,
                                           out_path="output/h2.mp4")
        self.assertAlmostEqual(hd, 1.0)

    def _render_shared(self, hook):
        try:
            from agents import video_agent
        except Exception as e:
            self.skipTest(f"agents.video_agent not importable here: {e}")
        with mock.patch.object(video_agent, "get_audio_duration", return_value=12.0), \
                mock.patch.object(video_agent, "get_ffmpeg", return_value=self.ff):
            return video_agent._create_video_from_pexels_clips(
                sorted(os.path.join("assets/pexels_clips", f) for f in os.listdir("assets/pexels_clips")),
                "output/voice.mp3", "output/none.srt", hook=hook)

    def test_shared_renderer_opens_on_hook_and_keeps_total_length(self):
        base = self._render_shared(None)
        base_dur = _duration(base, self.ff)
        r, g, b = _mean_rgb(base, 0.5, self.ff)
        self.assertGreater(b, r + 30, "baseline should open on a blue clip")

        out = self._render_shared(self.hook)
        dur = _duration(out, self.ff)
        self.assertAlmostEqual(dur, base_dur, delta=0.3)                # length unchanged -> voice/captions in sync
        r, g, b = _mean_rgb(out, 0.5, self.ff)
        self.assertGreater(r, b + 60, f"first frame should be the red hook, got {(r, g, b)}")
        r, g, b = _mean_rgb(out, 3.5, self.ff)
        self.assertLess(r, 90, f"after the hook the story clips resume, got {(r, g, b)}")

    def test_unusable_hook_falls_back_to_normal_render(self):
        a = _duration(self._render_shared(None), self.ff)
        b = _duration(self._render_shared({"path": "/missing", "duration": 2}), self.ff)  # unusable hook
        self.assertAlmostEqual(a, b, delta=0.1)

    def test_bhakti_narrated_background_with_hook(self):
        try:
            from agents_bhakti import narrated_video_agent as nv
        except Exception as e:
            self.skipTest(f"bhakti renderer not importable here: {e}")
        clips = sorted(os.path.join("assets/pexels_clips", f) for f in os.listdir("assets/pexels_clips"))
        bg = nv._build_background(self.ff, clips, 12.0, hook=self.hook)
        self.assertAlmostEqual(_duration(bg, self.ff), 12.0, delta=0.3)
        r, g, b = _mean_rgb(bg, 0.5, self.ff)
        self.assertGreater(r, b + 60)
        bg2 = nv._build_background(self.ff, clips, 12.0)
        r, g, b = _mean_rgb(bg2, 0.5, self.ff)
        self.assertLess(r, 90)

    def test_gameplay_hook_cuts_from_the_middle_of_the_clip(self):
        """A 2-colour 'gameplay' file: blue 0-5s, red 5-10s. A cut at 6s must render red."""
        from agents import hook_render as hr
        _color_clip(self.ff, "assets/g1.mp4", "blue", 5)
        _color_clip(self.ff, "assets/g2.mp4", "red", 5)
        with open("assets/g.txt", "w") as f:
            f.write("file 'g1.mp4'\nfile 'g2.mp4'\n")
        subprocess.run([self.ff, "-y", "-f", "concat", "-safe", "0", "-i", "assets/g.txt",
                        "-c", "copy", "assets/game.mp4"], capture_output=True, check=True)
        hook = {"provider": "gameplay", "path": "assets/game.mp4", "start": 6.0, "duration": 1.5}
        seg = hr.render_hook_segment(self.ff, hook, "output/g.mp4", 540, 960)
        self.assertIsNotNone(seg)
        self.assertAlmostEqual(_duration(seg, self.ff), 1.5, delta=0.15)
        r, g, b = _mean_rgb(seg, 0.5, self.ff)
        self.assertGreater(r, b + 60)


if __name__ == "__main__":
    unittest.main()
