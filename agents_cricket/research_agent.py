# agents_cricket/research_agent.py
"""Fetches the full scorecard for a match, picks the standout performer, and
returns both a text summary (for the script agent) and structured data (for
the image agent)."""
import os
import requests
from dotenv import load_dotenv
load_dotenv()

CRICAPI_KEY = os.getenv("CRICAPI_KEY", "")
BASE_URL = "https://api.cricapi.com/v1"


def _pick_standout(scorecard):
    """Scans all innings for the best batting and bowling performance.
    Returns (name, kind) or (None, None). A big bowling haul (3+ wickets) is
    treated as more of a 'moment' than a good batting score, unless the
    batting score is more clearly than the bowling."""
    best_bat = None   # (runs, name)
    best_bowl = None  # (wickets, name)

    for inning in scorecard:
        for b in inning.get("batting", []):
            try:
                runs = int(b.get("r", 0) or 0)
            except (TypeError, ValueError):
                continue
            name = b.get("batsman", {}).get("name", "")
            if name and (best_bat is None or runs > best_bat[0]):
                best_bat = (runs, name)
        for bo in inning.get("bowling", []):
            try:
                wkts = int(bo.get("w", 0) or 0)
            except (TypeError, ValueError):
                continue
            name = bo.get("bowler", {}).get("name", "")
            if name and (best_bowl is None or wkts > best_bowl[0]):
                best_bowl = (wkts, name)

    if best_bowl and best_bowl[0] >= 3:
        return best_bowl[1], "bowling"
    if best_bat and best_bat[0] >= 40:
        return best_bat[1], "batting"
    if best_bowl:
        return best_bowl[1], "bowling"
    if best_bat:
        return best_bat[1], "batting"
    return None, None


def get_match_summary(match):
    """match: one dict from trending_agent.get_trending_matches().
    Returns (summary_text, structured) or (None, None) on failure.
    structured = {match_id, venue, teams, standout_player, standout_type}"""
    match_id = match.get("id")
    if not match_id or not CRICAPI_KEY:
        return None, None

    try:
        r = requests.get(
            f"{BASE_URL}/match_scorecard",
            params={"apikey": CRICAPI_KEY, "id": match_id},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"CricAPI match_scorecard failed: {e}")
        return None, None

    if data.get("status") != "success":
        return None, None

    d = data.get("data", {})
    scorecard = d.get("scorecard", [])
    venue = d.get("venue", match.get("venue", ""))
    teams = match.get("teams", [])
    standout_player, standout_type = _pick_standout(scorecard)

    lines = [
        f"Match: {d.get('name', match.get('name', ''))}",
        f"Status: {d.get('status', match.get('status', ''))}",
        f"Venue: {venue}",
    ]
    for inning in scorecard:
        inning_name = inning.get("inning", "")
        lines.append(f"\n{inning_name}:")
        batting = inning.get("batting", [])[:3]
        for b in batting:
            lines.append(
                f"  {b.get('batsman', {}).get('name','')} — "
                f"{b.get('r','?')}({b.get('b','?')}) "
                f"{'*' if b.get('dismissal-text','') == '' else ''}"
            )
        bowling = inning.get("bowling", [])[:2]
        for bo in bowling:
            lines.append(
                f"  Bowling: {bo.get('bowler', {}).get('name','')} — "
                f"{bo.get('w','?')}/{bo.get('r','?')} ({bo.get('o','?')} ov)"
            )

    if standout_player:
        lines.append(f"\nStandout performance: {standout_player} ({standout_type})")

    structured = {
        "topic_type": match.get("topic_type", "finished"),
        "match_id": match_id,
        "venue": venue,
        "teams": teams,
        "standout_player": standout_player,
        "standout_type": standout_type,
    }
    return "\n".join(lines), structured


def get_news_summary(item):
    """item: one dict from news_agent.get_breaking_cricket_news(), tagged
    topic_type='news' by get_all_topics(). No scorecard data exists for
    news items — this just formats the headline for script generation."""
    lines = [
        f"Headline: {item.get('title', '')}",
        f"Source: {item.get('source', '')}",
        f"Published: {item.get('published', '')}",
    ]
    structured = {
        "topic_type": "news",
        "match_id": None,
        "venue": None,
        "teams": [],
        "standout_player": None,
        "standout_type": None,
        "headline": item.get("title", ""),
        "link": item.get("link", ""),
    }
    return "\n".join(lines), structured


def get_upcoming_preview(match):
    """match: one dict from trending_agent.get_upcoming_matches(), tagged
    topic_type='upcoming'. No scorecard exists yet since the match hasn't
    started — this uses only the preview data already on hand (teams,
    venue, date) rather than making another CricAPI call."""
    lines = [
        f"Match: {match.get('name', '')}",
        f"Status: {match.get('status', 'Upcoming')}",
        f"Venue: {match.get('venue', '')}",
        f"Date: {match.get('date', '')}",
    ]
    structured = {
        "topic_type": "upcoming",
        "match_id": match.get("id"),
        "venue": match.get("venue", ""),
        "teams": match.get("teams", []),
        "standout_player": None,
        "standout_type": None,
    }
    return "\n".join(lines), structured


def get_summary_for_topic(topic):
    """Single entry point for script_agent.py — branches on topic_type
    (set by trending_agent.get_all_topics()) so callers don't need to know
    which source function produced the topic."""
    topic_type = topic.get("topic_type")
    if topic_type == "news":
        return get_news_summary(topic)
    if topic_type == "upcoming":
        return get_upcoming_preview(topic)
    return get_match_summary(topic)  # "live" or "finished"
