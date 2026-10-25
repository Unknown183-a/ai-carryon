"""
Offline tests for the semantic Brain features: agents/text_encoder.py (pure helpers), agents/semantic_features.py,
the decision log / embedding cache in agents/database.py, and the wiring in brain_client / topic_selection.
No network, no model download (a tiny fake encoder is used), no YouTube, no LLM.
Run:  python -m unittest tests.test_semantic_features -v
"""
import math
import unittest
from datetime import datetime, timedelta, timezone

from tests import comment_helpers as T   # sets up a temp SQLite DB before agents.database loads
from agents import brain_client as bc
from agents import semantic_features as sf
from agents import text_encoder as te
from agents import topic_selection as ts
from agents.database import db

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
VOCAB = ["iphone", "android", "cricket", "gpu", "robot"]


def iso(dt):
    return dt.isoformat()


class FakeEncoder:
    """Bag-of-words over VOCAB: texts sharing words are similar. Counts calls so cache behaviour is observable."""
    model_id, revision, preprocessing_version = "fake-model", "rev1", "v1"

    def __init__(self, revision="rev1", vecs=None):
        self.revision, self.calls, self.vecs = revision, [], vecs

    def encode(self, texts):
        self.calls.append(list(texts))
        if self.vecs is not None:
            return self.vecs(texts)
        return [[1.0 if w in t.split() else 0.0 for w in VOCAB] for t in texts]


_n = [0]


def fresh_channel():
    _n[0] += 1
    return f"test{_n[0]}"


def add_video(channel, vid, title, hours_ago, views_24h=None, topic=None):
    """Seed a published video (and optionally a snapshot ~24h after publish and an A/B test carrying the topic)."""
    vid = f"{channel}-{vid}"                       # video_id is globally unique in the table
    published = NOW - timedelta(hours=hours_ago)
    db.upsert_video(vid, title, iso(published), channel)
    if views_24h is not None:
        db.add_snapshot(vid, views_24h, timestamp=iso(published + timedelta(hours=24)))
    if topic:
        db.log_ab_test(topic, title, "p", 1, [], generated_at=iso(published), channel=channel)
        db.link_ab_test_to_video(title, vid)
    return published


class TextHelpers(unittest.TestCase):
    def test_normalize_is_deterministic_and_preserves_script(self):
        self.assertEqual(te.normalize_text("  Ｉphone\t 16 \n LEAK  "), "iphone 16 leak")   # NFKC + whitespace + case
        hindi = "क्या आपको पता है  भागवत कथा"
        self.assertEqual(te.normalize_text(hindi), "क्या आपको पता है भागवत कथा")
        self.assertEqual(te.normalize_text(te.normalize_text(hindi)), te.normalize_text(hindi))   # idempotent
        self.assertEqual(te.normalize_text(None), "")
        self.assertEqual(len(te.normalize_text("a" * 5000)), te.MAX_TEXT_CHARS)

    def test_hash_and_preprocessing_version(self):
        self.assertEqual(te.text_hash("a"), te.text_hash("a"))
        self.assertNotEqual(te.text_hash("a"), te.text_hash("b"))
        self.assertEqual(te.preprocessing_version(""), "v1")
        self.assertNotEqual(te.preprocessing_version("query: "), te.preprocessing_version("passage: "))
        self.assertTrue(te.preprocessing_version("query: ").startswith("v1+p"))

    def test_loader_is_off_without_config_and_refuses_a_floating_revision(self):
        import os
        from unittest import mock
        logs = []
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BRAIN_TEXT_MODEL_NAME", None)
            self.assertIsNone(te.load_encoder_from_env(log=logs.append))
            os.environ["BRAIN_TEXT_MODEL_NAME"] = "some/model"
            os.environ.pop("BRAIN_TEXT_MODEL_REVISION", None)
            self.assertIsNone(te.load_encoder_from_env(log=logs.append))
        self.assertTrue(any("floating" in m for m in logs))


class HistoryTests(unittest.TestCase):
    def test_views_at_24h_uses_closest_snapshot_within_tolerance(self):
        pub = NOW - timedelta(days=3)
        snaps = [{"views": 10, "timestamp": iso(pub + timedelta(hours=3))},
                 {"views": 90, "timestamp": iso(pub + timedelta(hours=23))},
                 {"views": 95, "timestamp": iso(pub + timedelta(hours=26))},
                 {"views": 500, "timestamp": iso(pub + timedelta(hours=60))}]
        self.assertEqual(sf.views_at_24h(pub, snaps), 90.0)
        self.assertIsNone(sf.views_at_24h(pub, snaps[:1] + snaps[3:]))           # nothing near 24h
        self.assertIsNone(sf.views_at_24h(None, snaps))
        self.assertEqual(sf.views_at_24h(pub, [{"views": 7, "timestamp": iso(pub + timedelta(hours=24)).replace("+00:00", "Z")}]), 7.0)

    def test_build_history_prefers_ab_topic_falls_back_and_drops_the_future(self):
        ch = fresh_channel()
        add_video(ch, "v1", "Final title A", 100, views_24h=300, topic="Raw Topic One")
        add_video(ch, "v2", "Only a title", 90, views_24h=50)
        add_video(ch, "v3", "Too recent for an outcome", 5)
        db.upsert_video(f"{ch}-v4", "Published later", iso(NOW + timedelta(hours=3)), ch)    # clock skew / future row
        db.mark_posted("Posted but not tracked", channel=ch, posted_at=iso(NOW - timedelta(hours=2)))
        items = sf.build_history(db.get_semantic_history_rows(ch), as_of=NOW)
        by_text = {i.text: i for i in items}
        self.assertEqual(set(by_text), {"raw topic one", "only a title", "too recent for an outcome",
                                        "posted but not tracked"})
        self.assertEqual(by_text["raw topic one"].views_24h, 300.0)
        self.assertIsNone(by_text["too recent for an outcome"].views_24h)
        self.assertIsNone(by_text["posted but not tracked"].views_24h)
        self.assertEqual([i.published for i in items], sorted((i.published for i in items), reverse=True))

    def test_closed_ab_test_views_are_the_fallback_when_no_snapshot_is_near_24h(self):
        ch = fresh_channel()
        add_video(ch, "v1", "Closed ab test title", 100, topic="Topic")
        test_id = next(t["id"] for t in db.get_ab_tests(1000) if t["winner_title"] == "Closed ab test title")
        db.close_ab_test(test_id, 777, iso(NOW))
        items = sf.build_history(db.get_semantic_history_rows(ch), as_of=NOW)
        self.assertEqual(items[0].views_24h, 777.0)


def H(text, hours_ago, views, vec):
    pub = NOW - timedelta(hours=hours_ago)
    return sf.HistoryItem(text, pub, views), vec


class NeighborTests(unittest.TestCase):
    CFG = sf.SemanticConfig(k=5, min_similarity=0.6, recent_days=14, min_history=3)

    def hist(self):
        # baseline (median of 100, 400, 100) = 100
        return [H("a", 200, 100, [1, 0]), H("b", 190, 400, [0.8, 0.6]), H("c", 180, 100, [0, 1])]

    def test_weighted_geometric_mean_of_neighbour_ratios(self):
        out = sf.neighbor_features({"cand": [1, 0]}, self.hist(), NOW, self.CFG)["cand"]
        # neighbours: a (sim 1.0, ratio 1.0) and b (sim 0.8, ratio 401/101); c (sim 0) is below min_similarity
        expected = math.exp((1.0 * 0.0 + 0.8 * math.log(401 / 101)) / 1.8)
        self.assertEqual(out["neighbor_count"], 2)
        self.assertAlmostEqual(out["neighbor_ratio"], expected, places=3)
        self.assertGreater(out["neighbor_ratio"], 1.0)

    def test_no_neighbour_above_threshold_means_no_ratio_features(self):
        out = sf.neighbor_features({"far": [0.1, -1]}, self.hist(), NOW, self.CFG)
        self.assertNotIn("neighbor_ratio", out.get("far", {}))

    def test_k_limits_the_neighbours(self):
        hist = [H(str(i), 200 + i, 100 + i, [1, 0.01 * i]) for i in range(8)]
        out = sf.neighbor_features({"c": [1, 0]}, hist, NOW, sf.SemanticConfig(k=3, min_similarity=0.5))
        self.assertEqual(out["c"]["neighbor_count"], 3)

    def test_needs_min_history_outcomes_before_any_ratio(self):
        out = sf.neighbor_features({"c": [1, 0]}, self.hist()[:2], NOW, self.CFG)
        self.assertNotIn("neighbor_ratio", out.get("c", {}))

    def test_recent_similarity_only_looks_at_the_recent_window_and_is_clipped(self):
        hist = [H("old", 24 * 30, None, [1, 0]), H("fresh", 24 * 2, None, [0, 1])]
        out = sf.neighbor_features({"c": [1, 0.0001]}, hist, NOW, self.CFG)["c"]
        self.assertLess(out["max_similarity_recent"], 0.01)          # the identical vector is too old to count
        neg = sf.neighbor_features({"c": [0, -1]}, [H("x", 5, None, [0, 1])], NOW, self.CFG)["c"]
        self.assertEqual(neg["max_similarity_recent"], 0.0)          # cosine -1 is clipped to 0, never negative
        self.assertNotIn("neighbor_ratio", neg)

    def test_point_in_time_an_outcome_is_invisible_until_its_window_closed(self):
        hist = self.hist() + [H("d", 10, 100000, [1, 0])]            # published 10h ago: no knowable 24h outcome yet
        with_leak = sf.neighbor_features({"c": [1, 0]}, hist, NOW, self.CFG)["c"]
        without = sf.neighbor_features({"c": [1, 0]}, self.hist(), NOW, self.CFG)["c"]
        self.assertEqual(with_leak["neighbor_ratio"], without["neighbor_ratio"])
        # ...and judged from the past, later videos cannot influence an earlier moment
        early = NOW - timedelta(hours=195)
        out = sf.neighbor_features({"c": [1, 0]}, self.hist(), early, self.CFG)
        self.assertNotIn("neighbor_ratio", out.get("c", {}))

    def test_a_candidate_never_matches_itself_in_the_evaluation_setting(self):
        item, vec = H("target", 50, 900, [1, 0])
        out = sf.neighbor_features({"target": vec}, self.hist() + [(item, vec)], item.published, self.CFG)["target"]
        self.assertNotEqual(out["neighbor_count"], 3)                # its own row is excluded (published == as_of)

    def test_zero_vectors_and_dimension_mismatch(self):
        out = sf.neighbor_features({"z": [0, 0]}, self.hist(), NOW, self.CFG)
        self.assertTrue(all("neighbor_ratio" not in f for f in out.values()))
        with self.assertRaises(ValueError):
            sf.neighbor_features({"c": [1, 0, 0]}, self.hist(), NOW, self.CFG)

    def test_config_from_env_ignores_garbage(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"BRAIN_SEMANTIC_K": "abc", "BRAIN_SEMANTIC_MIN_SIMILARITY": "7",
                                          "BRAIN_SEMANTIC_RECENT_DAYS": "30"}):
            cfg = sf.SemanticConfig.from_env()
        self.assertEqual((cfg.k, cfg.min_similarity, cfg.recent_days), (5, 0.6, 30.0))


class EmbeddingCacheTests(unittest.TestCase):
    def test_second_call_is_served_from_the_cache(self):
        enc = FakeEncoder()
        texts = ["iphone leak", "android news", "iphone leak"]
        first = sf.embed_texts(texts, enc, db)
        self.assertEqual(enc.calls, [["iphone leak", "android news"]])        # deduplicated, normalized
        again = sf.embed_texts(texts + ["gpu launch"], enc, db)
        self.assertEqual(enc.calls[1], ["gpu launch"])                        # only the new text is encoded
        self.assertEqual(again["iphone leak"], first["iphone leak"])

    def test_cache_is_invalidated_by_model_revision_and_preprocessing(self):
        sf.embed_texts(["robot dog"], FakeEncoder(revision="rev1"), db)
        e2 = FakeEncoder(revision="rev2")
        sf.embed_texts(["robot dog"], e2, db)
        self.assertEqual(e2.calls, [["robot dog"]])                           # new revision => fresh vectors
        e3 = FakeEncoder(revision="rev1")
        e3.preprocessing_version = "v1+pabcdef12"
        sf.embed_texts(["robot dog"], e3, db)
        self.assertEqual(e3.calls, [["robot dog"]])

    def test_bad_encoder_output_is_rejected_and_not_cached(self):
        for bad in (lambda t: [[float("nan"), 1.0]] * len(t), lambda t: [[1.0, 0.0]], lambda t: [[1.0], [1.0, 2.0]]):
            enc = FakeEncoder(vecs=bad)
            with self.assertRaises(ValueError):
                sf.embed_texts(["bad one", "bad two"], enc, db)
        self.assertEqual(db.get_cached_embeddings([te.text_hash("bad one")], "fake-model", "rev1", "v1"), {})

    def test_cache_lookup_handles_more_hashes_than_one_chunk(self):
        items = [(te.text_hash(f"t{i}"), [float(i), 1.0]) for i in range(450)]
        db.save_embeddings(items, "big-model", "r", "v1")
        got = db.get_cached_embeddings([h for h, _ in items], "big-model", "r", "v1")
        self.assertEqual(len(got), 450)


class EndToEndFeatureTests(unittest.TestCase):
    def setUp(self):
        self.ch = fresh_channel()
        for i, (title, views) in enumerate([("iphone camera test", 100), ("iphone battery test", 900),
                                            ("cricket final recap", 100), ("android gpu leak", 100),
                                            ("cricket batting tips", 100)]):
            add_video(self.ch, f"v{i}", title, 24 * (30 - i), views_24h=views)
        add_video(self.ch, "recent", "robot dog unveiled", 30)                    # recent, outcome not known yet
        self.cands = [{"title": "iphone launch review"}, {"title": "robot dog update"}, {"title": "unseen topic"}]

    def test_features_for_candidates_with_evidence_only(self):
        feats = sf.semantic_features(self.cands, self.ch, db=db, encoder=FakeEncoder(), now=NOW,
                                     cfg=sf.SemanticConfig(min_similarity=0.4))
        self.assertEqual(feats["iphone launch review"]["neighbor_count"], 2)      # the two iphone videos
        self.assertGreater(feats["iphone launch review"]["neighbor_ratio"], 1.0)  # one of them did 9x the median
        self.assertEqual(feats["robot dog update"]["max_similarity_recent"], 1.0)  # same vocabulary as a recent video
        self.assertNotIn("neighbor_ratio", feats["robot dog update"])             # its twin has no outcome yet
        self.assertEqual(feats["unseen topic"], {"max_similarity_recent": 0.0})   # checked: not a repeat, no neighbours

    def test_other_channels_are_never_used(self):
        other = fresh_channel()
        feats = sf.semantic_features(self.cands, other, db=db, encoder=FakeEncoder(), now=NOW)
        self.assertEqual(feats, {})

    def test_fail_open_when_off_or_broken(self):
        logs = []
        self.assertEqual(sf.semantic_features(self.cands, self.ch, db=db, encoder=None, now=NOW), {}
                         if sf.default_encoder() is None else None) if sf.default_encoder() is None else None

        class Boom(FakeEncoder):
            def encode(self, texts):
                raise RuntimeError("model exploded")
        self.assertEqual(sf.semantic_features(self.cands, self.ch, db=db, encoder=Boom(), now=NOW, log=logs.append), {})
        self.assertTrue(any("RuntimeError" in m for m in logs))


class DecisionLogTests(unittest.TestCase):
    def test_log_select_and_read_back(self):
        ch = fresh_channel()
        rows = [{"topic": "a", "features": {"neighbor_ratio": 1.5}, "brain_scores": {"b1": {"role": "shadow", "score": 0.6}},
                 "aggregate_score": 0.02, "rank": 1, "source": "brains", "execution_id": "e1", "policy_version": "rrf-v1"},
                {"topic": "b", "features": {}, "brain_scores": {}, "aggregate_score": 0.01, "rank": 2,
                 "source": "brains", "execution_id": "e1", "policy_version": "rrf-v1"}]
        db.log_topic_decision("run-1", ch, rows)
        self.assertTrue(db.mark_topic_selected("run-1", "b"))
        self.assertFalse(db.mark_topic_selected("run-1", "nope"))
        got = {r["topic"]: r for r in db.get_topic_decisions(ch)}
        self.assertEqual((got["a"]["selected"], got["b"]["selected"]), (0, 1))
        self.assertEqual(got["a"]["features"], {"neighbor_ratio": 1.5})
        self.assertEqual(got["a"]["brain_scores"]["b1"]["role"], "shadow")
        self.assertEqual(db.get_topic_decisions(fresh_channel()), [])


# ---------------------------------------------------------------------------------------------------------
# brain_client + topic_selection wiring
# ---------------------------------------------------------------------------------------------------------
CH = "11111111-1111-4111-8111-111111111111"
WS = "22222222-2222-4222-8222-222222222222"
EXEC = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
PRIMARY = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SHADOW = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
VER = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def body_with_shadow():
    rec = lambda cid, s, r=(): {"candidate_id": cid, "score": s, "confidence": 0.5, "reason_codes": list(r)}
    return {"execution_id": EXEC, "source": "brains", "policy_version": "rrf-v1",
            "ranked": [{"candidate_id": "t1", "aggregate_score": 0.0164}, {"candidate_id": "t0", "aggregate_score": 0.0159}],
            "brains": [
                {"brain_id": PRIMARY, "brain_version_id": VER, "role": "primary", "status": "ok",
                 "recommendations": [rec("t0", 0.3), rec("t1", 0.4)]},
                {"brain_id": SHADOW, "brain_version_id": VER, "role": "shadow", "status": "ok",
                 "recommendations": [rec("t0", 0.5, ["no_neighbors"]), rec("t1", 0.66, ["neighbors_strong"])]}]}


class Resp:
    status_code = 200

    def __init__(self, body):
        self._b = body

    def json(self):
        return self._b


class ClientCaptureTests(unittest.TestCase):
    def setUp(self):
        import os
        from unittest import mock
        self.p = mock.patch.dict(os.environ, {"BRAIN_ENGINE_URL": "http://engine.test", "BRAIN_WORKSPACE_ID": WS,
                                              "BRAIN_CHANNEL_ID_ENGLISH": CH})
        self.p.start()
        os.environ.pop("BRAIN_ENABLED", None)

    def tearDown(self):
        self.p.stop()

    def test_clean_features_accepts_the_semantic_keys_and_drops_bad_values(self):
        ok = bc.clean_features({"neighbor_ratio": 1.8, "neighbor_count": 4.0, "max_similarity_recent": 0.93,
                                "text": "never forwarded"})
        self.assertEqual(ok, {"neighbor_ratio": 1.8, "neighbor_count": 4, "max_similarity_recent": 0.93})
        self.assertIsInstance(ok["neighbor_count"], int)
        for bad in ({"neighbor_ratio": -0.1}, {"max_similarity_recent": 1.2}, {"neighbor_ratio": float("nan")},
                    {"neighbor_count": True}, {"max_similarity_recent": "0.5"}):
            self.assertEqual(bc.clean_features(bad), {}, bad)

    def test_semantic_features_are_sent_to_the_engine(self):
        sent = {}

        def post(url, json=None, headers=None, timeout=None):
            sent.update(json)
            return Resp(body_with_shadow())
        bc.rank_topics(["alpha", "beta"], "english", post=post,
                       features={"alpha": {"neighbor_ratio": 2.0, "neighbor_count": 5, "max_similarity_recent": 0.4}})
        self.assertEqual(sent["candidates"][0]["features"],
                         {"neighbor_ratio": 2.0, "neighbor_count": 5, "max_similarity_recent": 0.4})
        self.assertNotIn("features", sent["candidates"][1])

    def test_per_brain_scores_and_aggregate_are_captured_by_topic(self):
        r = bc.rank_topics(["alpha", "beta"], "english", post=lambda *a, **k: Resp(body_with_shadow()))
        self.assertTrue(r.applied and r.ordered == ["beta", "alpha"])
        shadow = next(b for b in r.brain_scores if b["role"] == "shadow")
        self.assertEqual(shadow["scores"], {"alpha": 0.5, "beta": 0.66})
        self.assertEqual(shadow["reasons"]["beta"], ["neighbors_strong"])
        self.assertEqual(r.aggregate, {"beta": 0.0164, "alpha": 0.0159})
        rows = {x["topic"]: x for x in r.to_decision_rows(["alpha", "beta"], {"beta": {"neighbor_count": 4}})}
        self.assertEqual(rows["beta"]["rank"], 1)
        self.assertEqual(rows["alpha"]["rank"], 2)
        self.assertEqual(rows["beta"]["features"], {"neighbor_count": 4})
        self.assertEqual(rows["beta"]["brain_scores"][SHADOW]["role"], "shadow")
        self.assertEqual(rows["beta"]["brain_scores"][SHADOW]["score"], 0.66)
        self.assertNotIn("brain_scores", r.to_log_dict())             # the BRAIN_LOG line keeps its original shape

    def test_unavailable_engine_still_produces_loggable_rows_without_scores(self):
        def boom(*a, **k):
            raise RuntimeError("down")
        r = bc.rank_topics(["alpha", "beta"], "english", post=boom)
        rows = r.to_decision_rows(["alpha", "beta"])
        self.assertEqual([x["source"] for x in rows], ["engine_unavailable"] * 2)
        self.assertTrue(all(x["brain_scores"] == {} and x["rank"] is None for x in rows))


class SelectionWiringTests(unittest.TestCase):
    CANDS = [{"title": "alpha", "age_days": 1.0}, {"title": "beta", "age_days": 2.0}, {"title": "gamma", "age_days": 3.0}]

    def setUp(self):
        import os
        from unittest import mock
        self.p = mock.patch.dict(os.environ, {"BRAIN_ENGINE_URL": "http://engine.test", "BRAIN_WORKSPACE_ID": WS,
                                              "BRAIN_CHANNEL_ID_ENGLISH": CH})
        self.p.start()
        os.environ.pop("BRAIN_ENABLED", None)
        self.logged, self.selected, self.used, self.rank_features = [], [], [], {}

    def tearDown(self):
        self.p.stop()

    def rank(self, topics, channel, features=None):
        self.rank_features = features
        body = body_with_shadow()
        ids = {f"t{i}": t for i, t in enumerate(topics)}
        return bc._interpret(body, ids, len(topics))

    def call(self, **kw):
        defaults = dict(get_candidates=lambda region: list(self.CANDS), get_requests=lambda: [],
                        check_saturation=lambda t: {"proceed": True, "opportunity_score": 1, "reason": "ok"},
                        mark_used=self.used.append, rank=self.rank, log=lambda m: None,
                        log_decision=lambda run, ch, rows: self.logged.append((run, ch, rows)),
                        mark_selected=lambda run, t: self.selected.append((run, t)))
        defaults.update(kw)
        return ts.brain_ranked_topic("english", **defaults)

    def test_semantic_features_are_merged_and_the_decision_is_logged_and_selected(self):
        sem = lambda cands, channel: {"alpha": {"neighbor_ratio": 1.7, "neighbor_count": 4}}
        topic = self.call(compute_semantic=sem)
        self.assertEqual(topic, "beta")                                           # engine ordered t1 (= beta) first
        self.assertEqual(self.rank_features["alpha"]["neighbor_ratio"], 1.7)
        self.assertEqual(self.rank_features["alpha"]["days_since_trend"], 1.0)    # merged with the demand features
        (run, ch, rows), = self.logged
        self.assertEqual(ch, "english")
        self.assertEqual({r["topic"] for r in rows}, {"alpha", "beta", "gamma"})  # ALL candidates, not just the pick
        alpha = next(r for r in rows if r["topic"] == "alpha")
        self.assertEqual(alpha["features"]["neighbor_count"], 4)
        self.assertEqual(self.selected, [(run, "beta")])
        self.assertEqual(self.used, ["beta"])

    def test_decision_is_logged_even_when_the_brain_is_not_applied(self):
        def flat(topics, channel, features=None):
            b = body_with_shadow()
            b["ranked"] = [{"candidate_id": "t0", "aggregate_score": 0.0}, {"candidate_id": "t1", "aggregate_score": 0.0}]
            return bc._interpret(b, {f"t{i}": t for i, t in enumerate(topics)}, len(topics))
        self.assertIsNone(self.call(rank=flat))                                   # no signal => existing selection
        self.assertEqual(len(self.logged), 1)
        self.assertEqual(self.selected, [])
        shadow_scores = [r["brain_scores"][SHADOW]["score"] for r in self.logged[0][2] if SHADOW in r["brain_scores"]]
        self.assertTrue(shadow_scores)                                            # the shadow Brain's view is kept

    def test_failures_in_semantic_or_logging_never_change_the_choice(self):
        def boom(*a, **k):
            raise RuntimeError("nope")
        topic = self.call(compute_semantic=boom, log_decision=boom, mark_selected=boom)
        self.assertEqual(topic, "beta")

    def test_semantic_is_skipped_when_not_enabled_and_no_work_happens(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"BRAIN_SEMANTIC_ENABLED": ""}):
            self.assertEqual(self.call(), "beta")
        self.assertNotIn("neighbor_ratio", str(self.rank_features))

    def test_nothing_is_logged_when_the_brain_feature_is_off(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"BRAIN_ENABLED": "0"}):
            self.assertIsNone(self.call(get_candidates=lambda r: 1 / 0))          # not even called
        self.assertEqual(self.logged, [])

    def test_the_real_database_receives_the_rows_by_default(self):
        ch_name = "english"
        before = len(db.get_topic_decisions(ch_name))
        ts.brain_ranked_topic("english", get_candidates=lambda r: list(self.CANDS), get_requests=lambda: [],
                              check_saturation=lambda t: {"proceed": True, "opportunity_score": 1, "reason": "ok"},
                              mark_used=lambda t: None, rank=self.rank, log=lambda m: None)
        rows = db.get_topic_decisions(ch_name)
        self.assertEqual(len(rows), before + 3)
        self.assertEqual(sum(r["selected"] for r in rows[:3]), 1)


if __name__ == "__main__":
    unittest.main()
