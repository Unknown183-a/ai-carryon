# agents_gaming/clip_scorer.py
"""
Gaming V2 Phase 1 — pick the most interesting + highest-potential clip, not
just the most viewed one.

    Final = 25% viral velocity + 20% engagement + 20% moment quality
          + 15% freshness      + 10% game popularity + 10% streamer relevance

Every component is on a 0-10 scale, so the final score is 0-10.

Helix clips only expose view_count / duration / created_at / game_id (no
likes or comments), so two components are honest proxies:
  - engagement      = view-count percentile in today's pool + duration fit
  - game_popularity = how much total view volume that game has in the pool

moment_quality has two modes. Before the vision pass it is a cheap title
heuristic (capped at 7 so it can't beat a real analysis); once
moment_analyzer has run on a clip, the analysed intensity replaces it.
"""
import math
import os
from datetime import datetime, timezone

WEIGHTS = {
    "viral_velocity": 0.25,
    "engagement": 0.20,
    "moment_quality": 0.20,
    "freshness": 0.15,
    "game_popularity": 0.10,
    "streamer_relevance": 0.10,
}

FRESHNESS_HALF_LIFE_HOURS = float(os.getenv("GAMING_FRESHNESS_HALF_LIFE_HOURS", "24"))
IDEAL_DURATION = (12.0, 35.0)  # seconds — fits a Short without cutting the payoff

_MOMENT_KEYWORDS = (
    "clutch", "1hp", "1 hp", "one hp", "ace", "insane", "no way", "how", "world record",
    "record", "first", "fail", "rage", "ruined", "lucky", "luck", "impossible", "1v", "wipe",
    "trolled", "troll", "unreal", "survives", "survived", "destroyed", "won", "lost",
)


def _parse_ts(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _age_hours(clip, now):
    dt = _parse_ts(clip.get("created_at"))
    if not dt:
        return 24.0  # unknown age -> treat as a day old, neither fresh nor stale
    return max((now - dt).total_seconds() / 3600.0, 0.25)


def _pct_rank(value, population):
    """Percentile of value within population, scaled 0-10."""
    if not population:
        return 5.0
    below = sum(1 for v in population if v < value)
    equal = sum(1 for v in population if v == value)
    return 10.0 * (below + 0.5 * equal) / len(population)


def _duration_fit(duration):
    lo, hi = IDEAL_DURATION
    if duration is None or duration <= 0:
        return 5.0
    if lo <= duration <= hi:
        return 10.0
    if duration < lo:
        return max(0.0, 10.0 * duration / lo)
    return max(0.0, 10.0 - (duration - hi) * 0.5)  # long clips lose ~0.5/sec


def heuristic_moment_quality(clip):
    """Cheap pre-analysis guess from the clip title. Capped at 7."""
    title = (clip.get("title") or "").lower()
    hits = sum(1 for k in _MOMENT_KEYWORDS if k in title)
    letters = [c for c in clip.get("title") or "" if c.isalpha()]
    caps = (sum(1 for c in letters if c.isupper()) / len(letters)) if letters else 0
    bang = 0.5 if ("!" in title or "?" in title) else 0.0
    return min(7.0, 3.5 + hits * 1.2 + (0.8 if caps > 0.5 else 0.0) + bang)


def moment_quality_from_analysis(moment):
    """Analysed score 0-10: intensity dominates, best of the vibe scores
    (funny / clutch) adds the rest."""
    if not moment:
        return None
    intensity = float(moment.get("intensity", 5))
    vibe = max(float(moment.get("funny_score", 0)), float(moment.get("clutch_score", 0)))
    return min(10.0, 0.7 * intensity + 0.3 * vibe)


def _pool_stats(clips, now):
    vph = {}
    views = []
    game_views = {}
    for c in clips:
        v = float(c.get("view_count", 0) or 0)
        vph[id(c)] = v / _age_hours(c, now)
        views.append(v)
        gid = c.get("game_id") or c.get("_source_game") or ""
        game_views[gid] = game_views.get(gid, 0.0) + v
    return {
        "vph_all": list(vph.values()),
        "vph": vph,
        "views_all": views,
        "game_views": game_views,
        "game_views_all": list(game_views.values()),
    }


def score_clip(clip, stats, now, moment=None, followed=None):
    """Returns (final_score_0_10, parts_dict). `stats` comes from _pool_stats."""
    followed = {f.lower() for f in (followed or [])}
    views = float(clip.get("view_count", 0) or 0)
    gid = clip.get("game_id") or clip.get("_source_game") or ""

    viral_velocity = _pct_rank(stats["vph"][id(clip)], stats["vph_all"])
    engagement = 0.6 * _pct_rank(views, stats["views_all"]) + 0.4 * _duration_fit(clip.get("duration"))
    analysed = moment_quality_from_analysis(moment)
    moment_quality = analysed if analysed is not None else heuristic_moment_quality(clip)
    freshness = 10.0 * math.pow(0.5, _age_hours(clip, now) / FRESHNESS_HALF_LIFE_HOURS)
    game_popularity = _pct_rank(stats["game_views"].get(gid, 0.0), stats["game_views_all"])
    is_followed = (clip.get("_topic_type") == "streamer"
                   or (clip.get("broadcaster_name") or "").lower() in followed)
    streamer_relevance = 10.0 if is_followed else 4.0

    parts = {
        "viral_velocity": viral_velocity,
        "engagement": engagement,
        "moment_quality": moment_quality,
        "freshness": freshness,
        "game_popularity": game_popularity,
        "streamer_relevance": streamer_relevance,
    }
    final = sum(parts[k] * w for k, w in WEIGHTS.items())
    parts = {k: round(v, 2) for k, v in parts.items()}
    parts["moment_analysed"] = analysed is not None
    return round(final, 3), parts


def rank_clips_v2(clips, already_posted_ids=(), rejected_ids=(), moments=None,
                  followed=None, now=None, limit=None):
    """Score and sort unposted clips, best first. Tags each returned clip with
    `_score` and `_score_parts`. `moments` maps clip_id -> moment analysis."""
    now = now or datetime.now(timezone.utc)
    skip = set(already_posted_ids) | set(rejected_ids)
    pool = [c for c in clips if c.get("id") not in skip]
    if not pool:
        return []
    stats = _pool_stats(pool, now)
    moments = moments or {}
    scored = []
    for c in pool:
        final, parts = score_clip(c, stats, now, moment=moments.get(c.get("id")), followed=followed)
        c["_score"] = final
        c["_score_parts"] = parts
        scored.append(c)
    scored.sort(key=lambda c: c["_score"], reverse=True)
    return scored[:limit] if limit else scored
