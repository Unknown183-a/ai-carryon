# agents_gaming/trending_agent.py
"""
Builds the list of candidate clips for this run, mixing two sources per the
decision to combine both:
  1. Specific streamers you follow (TWITCH_FOLLOWED_STREAMERS)
  2. Top clips across trending game categories (TWITCH_TRACKED_GAMES, or the
     live top-games list from Helix if that's empty)

Each candidate is tagged topic_type so downstream agents (research_agent,
clip_finder) don't need to know which source it came from — same pattern as
agents_cricket/trending_agent.py's topic_type tagging.
"""
import os
from datetime import datetime, timedelta, timezone

from agents_gaming.twitch_client import (
    get_users, get_top_games, get_clips,
)

# Comma-separated Twitch usernames, e.g. "shroud,ninja,pokimane"
FOLLOWED_STREAMERS = [
    s.strip() for s in os.getenv("TWITCH_FOLLOWED_STREAMERS", "").split(",") if s.strip()
]

# Comma-separated game names to bias top-games toward, if set. Otherwise we
# just use whatever Helix currently reports as top games (auto-filtered
# below to exclude non-gameplay categories).
TRACKED_GAMES = [
    s.strip() for s in os.getenv("TWITCH_TRACKED_GAMES", "").split(",") if s.strip()
]

# Twitch's "top games" list is ranked by concurrent viewers, not by whether
# something is actually gameplay — "Just Chatting" regularly sits at #1-2
# and would otherwise get picked up here. These get excluded automatically
# so dynamic trending (no TRACKED_GAMES set) stays gaming-only without
# needing a hand-maintained game list. Matched case-insensitively.
NON_GAME_CATEGORIES = {
    "just chatting",
    "special events",
    "music",
    "asmr",
    "talk shows & podcasts",
    "art",
    "sports",
    "food & drink",
    "travel & outdoors",
    "makers & crafting",
    "pools, hot tubs, and beaches",
    "software and game development",
    "retro",
}

CLIP_WINDOW_HOURS = int(os.getenv("TWITCH_CLIP_WINDOW_HOURS", "24"))


def _window():
    now = datetime.now(timezone.utc)
    started = now - timedelta(hours=CLIP_WINDOW_HOURS)
    return started.strftime("%Y-%m-%dT%H:%M:%SZ"), now.strftime("%Y-%m-%dT%H:%M:%SZ")


def get_streamer_clips(limit_per_streamer=5):
    """Top clips from the last CLIP_WINDOW_HOURS for each followed streamer."""
    if not FOLLOWED_STREAMERS:
        return []
    started_at, ended_at = _window()
    users = get_users(FOLLOWED_STREAMERS)
    results = []
    for u in users:
        try:
            clips = get_clips(
                broadcaster_id=u["id"],
                started_at=started_at,
                ended_at=ended_at,
                limit=limit_per_streamer,
            )
        except Exception as e:
            print(f"Clip fetch failed for streamer {u.get('login')}: {e}")
            continue
        for c in clips:
            c["_topic_type"] = "streamer"
            c["_source_streamer"] = u.get("display_name") or u.get("login")
            results.append(c)
    return results


def get_top_game_clips(limit_games=5, limit_per_game=5):
    """Top clips from the last CLIP_WINDOW_HOURS across trending game categories."""
    started_at, ended_at = _window()
    games = []
    if TRACKED_GAMES:
        # Helix has no "get game by name -> clips" shortcut for a batch, so
        # we resolve each tracked game name via the games endpoint indirectly
        # by just using top_games and filtering — simpler and avoids an extra
        # per-game users-style lookup. If nothing matches, fall back to top N.
        top = get_top_games(limit=50)
        wanted = {g.lower() for g in TRACKED_GAMES}
        games = [g for g in top if g.get("name", "").lower() in wanted]
    if not games:
        # Dynamic path: pull a larger pool than we need, then drop non-game
        # categories (Just Chatting etc.) before taking the top N — so the
        # channel stays gaming-only without a hand-maintained game list.
        pool = get_top_games(limit=50)
        games = [g for g in pool if g.get("name", "").lower() not in NON_GAME_CATEGORIES]

    results = []
    for g in games[:limit_games]:
        try:
            clips = get_clips(
                game_id=g["id"],
                started_at=started_at,
                ended_at=ended_at,
                limit=limit_per_game,
            )
        except Exception as e:
            print(f"Clip fetch failed for game {g.get('name')}: {e}")
            continue
        for c in clips:
            c["_topic_type"] = "top_game"
            c["_source_game"] = g.get("name")
            results.append(c)
    return results


def get_all_topics():
    """Single entry point for scheduler_gaming.py. Returns a flat list of
    raw Helix clip dicts (tagged with _topic_type/_source_*), unranked —
    clip_finder.py does the ranking/selection."""
    topics = get_streamer_clips() + get_top_game_clips()
    print(f"Gaming trending: {len(topics)} candidate clips "
          f"({len(FOLLOWED_STREAMERS)} followed streamers, "
          f"{'tracked' if TRACKED_GAMES else 'top'} games)")
    return topics
