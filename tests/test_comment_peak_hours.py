"""The daily comment cycle runs when a channel's viewers are most present, not at a fixed time."""
import io
import json
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from unittest import mock

from comment_engine import cli
from comment_engine.config import Settings
from comment_engine.peak_hours import best_window_center, choose_peak, is_due

from tests.comment_helpers import FakeLLM, make_service, thread

NO_VELOCITY = lambda ch: ([], 0)


def at(hour, day=24, minute=7):
    return datetime(2026, 10, day, hour, minute, tzinfo=timezone.utc)


def velocity_peaking_at(hour, samples=200):
    def provider(ch):
        w = [1.0] * 24
        w[hour] = 50.0
        return w, samples
    return provider


def stamp(hour, n, day="2026-10-20"):
    return [{"comment_id": f"{hour}-{i}-{day}", "published_at": f"{day}T{hour:02d}:15:00Z"} for i in range(n)]


class PeakMathTests(unittest.TestCase):
    def test_picks_centre_of_busiest_three_hours(self):
        w = [0.0] * 24
        w[13], w[14], w[15] = 5, 20, 6
        self.assertEqual(best_window_center(w)[0], 14)

    def test_wraps_around_midnight(self):
        w = [0.0] * 24
        w[23], w[0], w[1] = 10, 12, 9
        self.assertEqual(best_window_center(w)[0], 0)


class ChoosePeakTests(unittest.TestCase):
    def setUp(self):
        self.svc, self.repo, *_ = make_service("english")
        self.t = self.svc.tenant_id

    def test_velocity_preferred_when_enough_samples(self):
        p = choose_peak(self.repo, self.t, "english", velocity_peaking_at(2))
        self.assertEqual((p.hour, p.source), (2, "velocity"))

    def test_falls_back_to_comment_times_then_bootstrap(self):
        self.assertEqual(choose_peak(self.repo, self.t, "english", NO_VELOCITY).source, "bootstrap")
        self.repo.record_activity(self.t, "english", stamp(1, 25) + stamp(2, 30) + stamp(14, 2))
        p = choose_peak(self.repo, self.t, "english", velocity_peaking_at(9, samples=5))   # too few velocity samples
        self.assertEqual((p.source, p.hour), ("comments", 2))

    def test_activity_is_per_channel_and_idempotent(self):
        self.repo.record_activity(self.t, "english", stamp(3, 40))
        self.repo.record_activity(self.t, "english", stamp(3, 40))
        self.assertEqual(self.repo.activity_hour_counts(self.t, "english")[3], 40)
        self.assertEqual(sum(self.repo.activity_hour_counts(self.t, "hindi")), 0)


class DueTests(unittest.TestCase):
    def setUp(self):
        self.svc, self.repo, *_ = make_service("english", channels=("english", "hindi"))
        self.s, self.t = self.svc.settings, self.svc.tenant_id

    def due(self, hour, provider=None, ch="english", **kw):
        return is_due(self.repo, self.s, ch, now=at(hour, **kw), velocity_provider=provider or velocity_peaking_at(13))

    def test_waits_for_peak_then_runs_and_only_once_a_day(self):
        self.assertFalse(self.due(12)[0])
        self.assertTrue(self.due(13)[0])
        self.assertTrue(self.due(17)[0])                       # a delayed cron still runs the same day
        self.svc.run_cycle(now=at(13))
        self.assertEqual(self.due(14)[1], "already ran today")
        self.assertTrue(self.due(13, day=25)[0])               # next day: due again

    def test_peak_follows_the_data_not_a_fixed_clock(self):
        us = self.due(2, velocity_peaking_at(2))
        india = self.due(2, velocity_peaking_at(14))
        self.assertTrue(us[0])
        self.assertFalse(india[0])

    def test_bootstrap_runs_immediately(self):
        due, why, peak = self.due(5, NO_VELOCITY)
        self.assertTrue(due)
        self.assertIsNone(peak.hour)

    def test_disabled_paused_and_unlisted_channels_never_due(self):
        s_off = Settings(**{**self.s.__dict__, "enabled": False})
        self.assertFalse(is_due(self.repo, s_off, "english", now=at(13))[0])
        self.assertFalse(is_due(self.repo, self.s, "cricket", now=at(13))[0])
        self.svc.set_paused(True)
        self.assertEqual(self.due(13)[1], "channel is paused")

    def test_failed_cycle_retries_but_gives_up_after_three(self):
        self.svc.run = mock.Mock(side_effect=RuntimeError("boom"))
        for _ in range(3):
            self.assertTrue(self.due(13)[0])
            with self.assertRaises(RuntimeError):
                self.svc.run_cycle(now=at(13))
        self.assertIn("gave up", self.due(14)[1])
        self.assertEqual(self.repo.last_run_day(self.t, "english"), None)

    def test_aborted_cycle_is_retried_not_marked_done(self):
        self.svc.run = mock.Mock(return_value={"aborted": "abort:auth"})
        self.svc.run_cycle(now=at(13))
        self.assertIsNone(self.repo.last_run_day(self.t, "english"))
        self.assertEqual(self.repo.attempts_today(self.t, "english", "2026-10-24"), 1)


class SyncAndPlanTests(unittest.TestCase):
    def test_sync_records_activity_for_all_viewer_comments_even_answered_ones(self):
        svc, repo, *_ = make_service("english", [
            thread("a", "new q", published_at="2026-10-20T03:10:00Z"),
            thread("b", "already answered", own_replied=True, published_at="2026-10-20T03:40:00Z"),
            thread("m", "mine", is_own=True, published_at="2026-10-20T09:00:00Z")])
        svc.sync()
        counts = repo.activity_hour_counts(svc.tenant_id, "english", days=3650)
        self.assertEqual((counts[3], counts[9]), (2, 0))          # viewers only, replied-to ones included

    def test_plan_prints_json_list_of_due_channels_last(self):
        svc, repo, *_ = make_service("english", channels=("english", "hindi", "cricket"))
        svc.run_cycle(now=datetime.now(timezone.utc))              # english already done today
        env = {"COMMENT_AGENT_ENABLED": "true", "COMMENT_AGENT_CHANNELS": "english,hindi,cricket"}
        out = io.StringIO()
        with mock.patch.dict("os.environ", env), mock.patch("comment_engine.repository.Repository",
                                                           return_value=repo), \
                mock.patch("comment_engine.peak_hours.velocity_profile", NO_VELOCITY), redirect_stdout(out):
            cli.main(["plan"])
        last = out.getvalue().strip().splitlines()[-1]
        self.assertEqual(sorted(json.loads(last)), ["cricket", "hindi"])

    def test_plan_is_empty_when_disabled(self):
        out = io.StringIO()
        with mock.patch.dict("os.environ", {"COMMENT_AGENT_ENABLED": "false"}), redirect_stdout(out):
            cli.main(["plan"])
        self.assertEqual(out.getvalue().strip().splitlines()[-1], "[]")


if __name__ == "__main__":
    unittest.main()
