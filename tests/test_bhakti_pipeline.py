"""Tests for the Bhakti v2 pipeline. External services (LLM, Pexels, Sarvam,
Freesound) are mocked; ffmpeg must be installed. Run: python -m unittest tests.test_bhakti_pipeline"""

import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from agents_bhakti.bhakti_types import Scene, VideoJob
from agents_bhakti import (bhakti_visual_agent as vis, bhakti_scene_agent as scn,
                           bhakti_retention_agent as ret, bhakti_caption_agent as cap,
                           bhakti_voice_agent as voice, bhakti_music_agent as mus,
                           bhakti_qa_agent as qa)

SCRIPT = "\n".join([
    "क्या आप जानते हैं भगवान कृष्ण ने अपने भक्त की कैसे रक्षा की थी?",
    "एक प्राचीन मंदिर में एक गरीब भक्त रोज़ प्रार्थना करता था।",
    "उसके पास कुछ नहीं था, बस अटूट श्रद्धा थी।",
    "एक रात भयंकर तूफ़ान आया और दीपक बुझने लगा।",
    "भक्त ने काँपते हाथों से कृष्ण का नाम पुकारा।",
    "तभी मंदिर में दिव्य प्रकाश फैल गया।",
    "तूफ़ान शांत हो गया और भक्त की आँखों में आँसू थे।",
    "कहते हैं सच्ची भक्ति कभी व्यर्थ नहीं जाती।",
    "जय श्री कृष्ण, ऐसी कहानियों के लिए फॉलो करें।",
])


def _video(vid, w, h, dur, slug):
    return {"id": vid, "duration": dur, "url": f"https://www.pexels.com/video/{slug}-{vid}/",
            "video_files": [{"file_type": "video/mp4", "width": w, "height": h, "link": "x"}]}


class VisualRanking(unittest.TestCase):
    def setUp(self):
        self.sc = Scene(1, "hook", "x", pexels_queries=["Indian temple sunrise"])
        self.sc.start, self.sc.end = 0, 5
        self.vids = [_video(1, 1080, 1920, 8, "indian-temple-sunrise"), _video(2, 720, 1280, 8, "temple"),
                     _video(3, 1920, 1080, 8, "temple"), _video(4, 1080, 1920, 8, "party-night"),
                     _video(5, 480, 854, 8, "temple")]
        self.search = lambda q: self.vids

    def test_best_clip_is_vertical_relevant_hires(self):
        v, _ = vis.select_clip_for_scene(self.sc, set(), set(), self.search)
        self.assertEqual(v["id"], 1)

    def test_rejects_landscape_lowres_and_bad_words(self):
        for bad in (self.vids[2], self.vids[3], self.vids[4]):
            self.assertIsNone(vis.score_candidate(bad, "temple", 0, 5, set(), set()))

    def test_no_repeat_within_video_and_penalise_recent(self):
        v, _ = vis.select_clip_for_scene(self.sc, set(), {"1"}, self.search)
        self.assertEqual(v["id"], 2)
        v, _ = vis.select_clip_for_scene(self.sc, {"1"}, set(), self.search)
        self.assertEqual(v["id"], 2)


class SceneAndStory(unittest.TestCase):
    def test_grouping_covers_all_sentences_in_order(self):
        sents = scn.split_sentences(SCRIPT)
        groups = scn.group_into_scenes(sents)
        self.assertTrue(5 <= len(groups) <= 8)
        self.assertEqual(" ".join(groups), " ".join(sents))

    def test_purpose_arc_starts_hook_ends_ending(self):
        p = scn.assign_purposes(7)
        self.assertEqual((p[0], p[-1]), ("hook", "ending"))
        self.assertIn("divine", p)

    def test_scene_plan_falls_back_without_llm(self):
        with mock.patch.object(scn, "safe_invoke", side_effect=RuntimeError("down")):
            scenes = scn.create_scene_plan(SCRIPT, {"topic": "t", "key_visuals": ["temple", "diya"]})
        self.assertTrue(all(s.pexels_queries for s in scenes))

    def test_retention_flags_english_and_repetition(self):
        self.assertIn("script is not mainly Devanagari Hindi", ret.heuristic_checks("hello world " * 40))
        self.assertEqual(ret.heuristic_checks(SCRIPT), [])


class CaptionsAndVoice(unittest.TestCase):
    def test_phrases_are_short(self):
        for p in cap.split_phrases("एक प्राचीन मंदिर में एक गरीब भक्त रोज़ प्रार्थना करता था।"):
            self.assertLessEqual(len(p), cap.MAX_WORDS + 1)

    def test_caption_events_do_not_overlap_and_follow_scene_windows(self):
        scenes = [Scene(1, "hook", "क्या आप जानते हैं, भगवान कौन हैं।"), Scene(2, "ending", "जय श्री कृष्ण।")]
        segs = [{"scene_id": 1, "start": 0.0, "end": 3.0}, {"scene_id": 2, "start": 3.5, "end": 5.0}]
        ev = cap.build_caption_events(scenes, segs, lead=1.0)
        for a, b in zip(ev, ev[1:]):
            self.assertLessEqual(a[1], b[0] + 1e-6)
        self.assertGreaterEqual(ev[-1][0], 4.5)   # scene 2 starts at lead + 3.5

    def test_tts_text_prep(self):
        self.assertEqual(voice.prepare_tts_text("श्रीकृष्ण ने 3 बार कहा"), "श्री कृष्ण ने तीन बार कहा।")

    def test_music_timeline_peaks_at_divine(self):
        scenes = [Scene(1, "hook", ""), Scene(2, "divine", ""), Scene(3, "ending", "")]
        for i, s in enumerate(scenes):
            s.start, s.end = i * 3, (i + 1) * 3
        gains = [g for _, _, g in mus.music_timeline(scenes)]
        self.assertEqual(max(gains), gains[1])


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg required")
class EndToEnd(unittest.TestCase):
    """Mocked services, real ffmpeg: story -> scenes -> voice -> clips -> mix -> render -> QA."""

    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.mkdtemp()
        os.chdir(self.tmp)
        os.makedirs("src")
        for i in range(10):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                            f"testsrc2=s=720x1280:r=30:d=6", "-pix_fmt", "yuv420p", f"src/c{i}.mp4"], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=300:d=60",
                        "src/music.mp3"], check=True)
        os.environ["BHAKTI_PRESET"] = "ultrafast"

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_full_video_build(self):
        import importlib
        from agents_bhakti import (bhakti_pipeline as pipe, bhakti_video_agent as vid,
                                   bhakti_music_agent as m, bhakti_sfx_agent as sfx)
        importlib.reload(vid)

        def fake_llm(prompt, *a, **k):
            r = mock.Mock()
            if "DEVANAGARI" in prompt:
                r.content = SCRIPT
            elif "Rate this" in prompt:
                r.content = '{"hook_score":8,"story_score":8,"emotional_score":8,"visual_score":8,"ending_score":8,"feedback":""}'
            elif "Research this devotional topic" in prompt:
                r.content = ('{"topic":"t","deity":"Krishna","main_event":"protects devotee","emotion":"devotion",'
                             '"setting":"ancient temple","key_visuals":["temple","diya","storm","divine light"]}')
            else:
                r.content = "not json"     # scene planner -> deterministic fallback plan
            return r

        def fake_tts(text, out, d):
            n = max(len(text.split()), 1)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                            f"sine=f=180:d={n * 0.3}", "-af", "adelay=250|250,apad=pad_dur=0.3", out], check=True)

        vids = [_video(100 + i, 1080, 1920, 6, f"indian-temple-{i}") for i in range(10)]
        def fake_download(video, path):
            shutil.copy(f"src/c{int(video['id']) - 100}.mp4", path)

        with mock.patch("agents_bhakti.bhakti_research_agent.safe_invoke", fake_llm), \
             mock.patch("agents_bhakti.bhakti_story_agent.safe_invoke", fake_llm), \
             mock.patch("agents_bhakti.bhakti_retention_agent.safe_invoke", fake_llm), \
             mock.patch("agents_bhakti.bhakti_scene_agent.safe_invoke", fake_llm), \
             mock.patch.object(voice, "synthesize_scene", lambda t, o, d, tts_fn=None: fake_tts(t, o, d)), \
             mock.patch.object(vis, "search_candidates", lambda q, per_page=15: vids), \
             mock.patch.object(vis, "download_clip", fake_download), \
             mock.patch.object(vis, "_used_ids", lambda: []), \
             mock.patch.object(vis, "_save_used_ids", lambda ids: None), \
             mock.patch.object(m.music_agent, "get_background_music",
                               lambda *a, **k: {"path": "src/music.mp3", "license": "Creative Commons 0",
                                                "name": "t", "author": "a", "url": ""}), \
             mock.patch.object(sfx, "_fetch", lambda name: None):
            job = pipe.build_story_job("कृष्ण और भक्त", log=lambda *_: None)
            self.assertGreaterEqual(len(job.scenes), 5)
            job = pipe.build_video(job, log=lambda *_: None)

        self.assertTrue(os.path.exists(job.final_video))
        self.assertTrue(job.qa["approved"], job.qa)
        ids = [s.clip_id for s in job.scenes]
        self.assertEqual(len(ids), len(set(ids)))        # no repeated clips
        info = qa.probe(job.final_video)
        self.assertEqual((info["width"], info["height"]), ("1080", "1920"))


if __name__ == "__main__":
    unittest.main()
