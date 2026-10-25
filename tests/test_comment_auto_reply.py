"""Auto-reply: posts replies that passed every check without waiting, and nothing else."""
import unittest
from datetime import datetime, timedelta, timezone

from comment_engine.service import AgentError, PublishBlocked

from tests.comment_helpers import FakeLLM, make_service, thread


def ago(**kw):
    return (datetime.now(timezone.utc) - timedelta(**kw)).strftime("%Y-%m-%dT%H:%M:%SZ")


def reply(text):
    return {"reply_text": text, "strategy": "answer", "needs_review": False, "review_reason": None,
            "used_context_ids": []}


A, B = "Check the middle section of the video.", "The second part is explained near the end."


class AutoReplyTests(unittest.TestCase):
    def svc(self, threads, generate=None, classify=None, **kw):
        llm = FakeLLM(generate=generate or [reply(A), reply(B)], classify=classify)
        return make_service("english", threads, llm=llm, **kw)

    def test_off_by_default_even_when_publishing_is_enabled(self):
        svc, repo, yt, _ = self.svc([thread("c1", "how does it work?", published_at=ago(hours=2))])
        svc.set_publishing(True)
        svc.run()
        self.assertEqual(yt.inserted, [])
        self.assertEqual(svc.list_drafts()[0]["status"], "pending_approval")

    def test_enabled_posts_passing_replies_with_an_audit_trail(self):
        svc, repo, yt, _ = self.svc([thread("c1", "how does it work?", published_at=ago(hours=2))])
        svc.set_auto_reply(True)
        stats = svc.run()
        self.assertEqual(yt.inserted, [("c1", A)])
        self.assertEqual((stats["auto_approved"], stats["published"]), (1, 1))
        [d] = svc.list_drafts(("published",))
        self.assertEqual(d["approved_by"], "auto-policy")
        types = {e["event_type"] for e in repo.list_events("default", "english", draft_id=d["draft_id"])}
        self.assertTrue({"approved", "published"} <= types)
        self.assertEqual(repo.get_comment("default", "english", "c1").status, "published")

    def test_second_run_never_replies_twice(self):
        svc, _, yt, _ = self.svc([thread("c1", "how does it work?", published_at=ago(hours=2))])
        svc.set_auto_reply(True)
        svc.run()
        svc.run()
        self.assertEqual(len(yt.inserted), 1)

    def test_flagged_drafts_are_never_auto_posted(self):
        sensitive = {"intent": "sensitive", "language": "en", "reply_strategy": "human_review",
                     "risk_flags": ["medical"], "confidence": 0.9}
        svc, _, yt, _ = self.svc([thread("c1", "I feel awful", published_at=ago(hours=1))], classify=sensitive)
        svc.set_auto_reply(True)
        svc.run()
        self.assertEqual(yt.inserted, [])
        self.assertEqual(svc.list_drafts()[0]["status"], "needs_review")

    def test_reply_that_fails_validation_is_never_auto_posted(self):
        bad = reply("Visit example.com now")
        svc, _, yt, _ = self.svc([thread("c1", "q?", published_at=ago(hours=1))], generate=[bad, bad])
        svc.set_auto_reply(True)
        svc.run()
        self.assertEqual(yt.inserted, [])
        self.assertEqual(svc.list_drafts()[0]["status"], "needs_review")

    def test_old_and_unknown_age_comments_stay_for_the_owner(self):
        svc, _, yt, _ = self.svc([thread("new", "q one?", published_at=ago(hours=3)),
                                  thread("old", "q two?", published_at=ago(days=30)),
                                  thread("unk", "q three?", published_at="")],
                                 generate=[reply(A), reply(B), reply("Third answer is in the intro.")])
        svc.set_auto_reply(True)
        svc.run()
        self.assertEqual([c for c, _ in yt.inserted], ["new"])
        left = {d["comment_id"] for d in svc.list_drafts(("pending_approval",))}
        self.assertTrue({"old"} <= left)

    def test_per_run_cap_is_respected(self):
        svc, _, yt, _ = self.svc([thread("c1", "q one?", published_at=ago(hours=1)),
                                  thread("c2", "q two?", published_at=ago(hours=2))])
        svc.set_overrides({"publishing.max_replies_per_run": 1})
        svc.set_auto_reply(True)
        svc.run()
        self.assertEqual(len(yt.inserted), 1)
        self.assertEqual(len(svc.list_drafts(("pending_approval",))), 1)

    def test_switch_off_pause_and_kill_switch_all_stop_it(self):
        for stop in ("off", "pause", "kill"):
            svc, _, yt, _ = self.svc([thread("c1", "q?", published_at=ago(hours=1))])
            svc.set_auto_reply(True)
            if stop == "off":
                svc.set_auto_reply(False)
            elif stop == "pause":
                svc.set_paused(True)
            else:
                svc.settings = svc.settings.__class__(**{**svc.settings.__dict__, "enabled": False})
            try:
                svc.run()
            except PublishBlocked:
                pass
            self.assertEqual(yt.inserted, [], stop)

    def test_enable_turns_publishing_on_and_disable_keeps_it(self):
        svc, repo, *_ = self.svc([])
        svc.set_auto_reply(True)
        st = repo.get_settings("default", "english")
        self.assertEqual((st["auto_publish"], st["publishing_enabled"]), (True, True))
        svc.set_auto_reply(False)
        st = repo.get_settings("default", "english")
        self.assertEqual((st["auto_publish"], st["publishing_enabled"]), (False, True))

    def test_setting_is_per_channel(self):
        svc, repo, *_ = self.svc([])
        svc.set_auto_reply(True)
        self.assertFalse(repo.get_settings("default", "cricket")["auto_publish"])

    def test_publish_failure_does_not_lose_the_draft(self):
        from comment_engine.youtube_client import YouTubeAPIError
        svc, repo, yt, _ = self.svc([thread("c1", "q?", published_at=ago(hours=1))])
        yt.insert_error = YouTubeAPIError("permanent", "commentsDisabled")
        svc.set_auto_reply(True)
        svc.run()
        self.assertEqual(svc.list_drafts(("publish_failed",))[0]["comment_id"], "c1")


if __name__ == "__main__":
    unittest.main()
