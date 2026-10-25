"""When should a channel's daily comment cycle run? When its viewers are most present.

Signals, best first (all UTC hours, per channel):
  1. velocity  - the repo's own view tracking: average views gained per hour of day.
  2. comments  - when this channel's viewers actually post comments (recorded on every sync).
  3. bootstrap - no data yet: run at the next opportunity, which also starts collecting data.
Nothing here is a fixed clock time.
"""
import importlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .config import MAX_RUN_ATTEMPTS_PER_DAY

MIN_VELOCITY_SAMPLES = 30
MIN_COMMENT_SAMPLES = 30
LOOKBACK_DAYS = 60

_VELOCITY_FUNCS = {
    "hindi": ("agents_hindi.velocity_agent", "get_peak_hours_hindi"),
    "cricket": ("agents_cricket.velocity_agent", "get_peak_hours_cricket"),
    "gaming": ("agents_gaming.velocity_agent", "get_peak_hours_gaming"),
    "bhakti": ("agents_bhakti.velocity_agent", "get_peak_hours_bhakti"),
}


@dataclass
class PeakDecision:
    hour: Optional[int]      # UTC hour 0-23, None while bootstrapping
    source: str              # velocity | comments | bootstrap
    samples: int = 0
    share: float = 0.0       # share of activity inside the chosen 3-hour window

    def describe(self):
        if self.hour is None:
            return "no viewer-activity data yet (bootstrap: runs at the next opportunity)"
        ist_minutes = (self.hour * 60 + 330) % 1440
        return (f"peak viewer hour {self.hour:02d}:00 UTC = {ist_minutes // 60:02d}:{ist_minutes % 60:02d} IST "
                f"(from {self.source}, {self.samples} samples, {self.share:.0%} of activity in the 3-hour window)")


def velocity_profile(channel_id):
    """(weights[24], samples) from the repo's view-velocity tracking; ([], 0) if unavailable."""
    try:
        if channel_id == "english":
            from agents.database import db
            raw = db.get_peak_hours(channel="english")
        elif channel_id in _VELOCITY_FUNCS:
            mod, fn = _VELOCITY_FUNCS[channel_id]
            raw = getattr(importlib.import_module(mod), fn)()
        else:
            return [], 0
        weights, samples = [0.0] * 24, 0
        for h, v in (raw or {}).items():
            h = int(h)
            if not 0 <= h <= 23:
                continue
            if isinstance(v, dict):
                n = int(v.get("sample_count", 0) or 0)
                weights[h] = float(v.get("avg_velocity", 0) or 0) if n >= 2 else 0.0
                samples += n
            else:
                weights[h] = float(v or 0)
                samples += 1
        return weights, samples
    except Exception:
        return [], 0


def best_window_center(weights):
    """Centre hour of the best 3-hour window (circular, so 23-00-01 works).
    Ties go to the busiest single hour, then the earliest."""
    sm = [weights[(h - 1) % 24] + weights[h] + weights[(h + 1) % 24] for h in range(24)]
    best = max(range(24), key=lambda h: (sm[h], weights[h], -h))
    total = sum(weights)
    return best, (sm[best] / total if total else 0.0)


def choose_peak(repo, tenant_id, channel_id, velocity_provider=velocity_profile):
    weights, samples = velocity_provider(channel_id)
    if samples >= MIN_VELOCITY_SAMPLES and sum(weights) > 0:
        hour, share = best_window_center(weights)
        return PeakDecision(hour, "velocity", samples, share)
    counts = repo.activity_hour_counts(tenant_id, channel_id, LOOKBACK_DAYS)
    if sum(counts) >= MIN_COMMENT_SAMPLES:
        hour, share = best_window_center([float(c) for c in counts])
        return PeakDecision(hour, "comments", sum(counts), share)
    return PeakDecision(None, "bootstrap", sum(counts), 0.0)


def is_due(repo, settings, channel_id, now=None, velocity_provider=velocity_profile):
    """Decide whether the channel's once-a-day cycle should run now.
    Returns (due: bool, reason: str, PeakDecision | None)."""
    now = now or datetime.now(timezone.utc)
    t = settings.tenant_id
    if not settings.enabled:
        return False, "comment agent disabled (COMMENT_AGENT_ENABLED)", None
    if channel_id not in settings.channels:
        return False, "channel not in COMMENT_AGENT_CHANNELS", None
    if repo.get_settings(t, channel_id)["paused"]:
        return False, "channel is paused", None
    day = now.date().isoformat()
    if repo.last_run_day(t, channel_id) == day:
        return False, "already ran today", None
    if repo.attempts_today(t, channel_id, day) >= MAX_RUN_ATTEMPTS_PER_DAY:
        return False, f"gave up after {MAX_RUN_ATTEMPTS_PER_DAY} failed attempts today", None
    peak = choose_peak(repo, t, channel_id, velocity_provider)
    if peak.hour is None:
        return True, "bootstrap: no activity data yet", peak
    if now.hour >= peak.hour:
        return True, f"peak hour {peak.hour:02d}:00 UTC reached", peak
    return False, f"waiting for peak hour {peak.hour:02d}:00 UTC", peak
