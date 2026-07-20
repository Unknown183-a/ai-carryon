# agents_cricket/trending_agent.py
"""
Pulls recently finished + live cricket matches from CricAPI (cricketdata.org).
Free tier: 100 hits/day, so call sparingly.

Two data sources are combined:
1. `currentMatches` — broad feed, catches most finished/live matches
   (IPL, WPL, domestic, etc.) but does NOT reliably surface every top-tier
   international tour (e.g. "India tour of England" didn't show up here
   even while a match was live).
2. Marquee series lookup (`series` + `series_info`) — explicitly searches
   for active "India tour of <opponent>" series and pulls that series'
   match list directly, to catch tours that (1) misses.

Restricted to Indian cricket: matches involving the India national team,
or India-based domestic/league tournaments (IPL, WPL, Ranji, etc.).

CACHING: marquee series list is cached 24h, each series' match list is
cached 15min — both via cricket_db meta — to stay within CricAPI's
100-hits/day free tier given /trigger fires every ~20 min.

NOTE: CricAPI sometimes omits `matchType` for certain fixtures (e.g. youth/
unofficial matches). We fall back to inferring the format from the match
name (looks for "test", "odi", "t20") rather than dropping the match.
"""
import os
import json
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()

CRICAPI_KEY = os.getenv("CRICAPI_KEY", "")
CRICAPI_KEY_2 = os.getenv("CRICAPI_KEY_2", "")

def _cricapi_keys():
    """Yields available CricAPI keys in fallback order."""
    for k in (CRICAPI_KEY, CRICAPI_KEY_2):
        if k:
            yield k
BASE_URL = "https://api.cricapi.com/v1"

ALLOWED_MATCH_TYPES = {"t20", "odi", "test"}

# Excludes youth/unofficial fixtures (e.g. "India U19", "unofficial Test")
# which technically pass the India + format filters but aren't the senior
# international/domestic content this channel is meant to cover.
EXCLUDED_KEYWORDS = {"u19", "u-19", "under-19", "unofficial", "youth"}


def _is_excluded(m):
    name = (m.get("name") or "").lower()
    teams = " ".join(m.get("teams", []) or []).lower()
    return any(kw in name or kw in teams for kw in EXCLUDED_KEYWORDS)

INDIA_KEYWORDS = {
    "india", "ipl", "wpl", "ranji", "syed mushtaq", "duleep", "irani", "vijay hazare"
}

# Higher-profile opponents get priority when picking among multiple eligible
# matches, and define which "India tour of X" series we actively look for.
MARQUEE_OPPONENTS = {"england", "australia", "pakistan", "south africa", "new zealand"}

SERIES_CACHE_TTL_SECONDS = 24 * 60 * 60   # series list changes rarely
MATCHLIST_CACHE_TTL_SECONDS = 15 * 60     # live status needs to stay fresh


def _get_cricket_db():
    try:
        from agents_cricket.database import db as cricket_db
        return cricket_db
    except Exception:
        return None


def is_indian_match(m):
    """True if the match involves the India national team or an India-based
    domestic/league tournament."""
    teams = " ".join(m.get("teams", []) or []).lower()
    series = (m.get("name") or "").lower()
    return "india" in teams or any(k in series for k in INDIA_KEYWORDS)


def _resolve_match_type(m):
    """Returns a normalized match type (t20/odi/test), falling back to
    inferring it from the match name if CricAPI didn't populate matchType."""
    match_type = (m.get("matchType") or "").lower()
    if match_type in ALLOWED_MATCH_TYPES:
        return match_type

    name = (m.get("name") or "").lower()
    if "test" in name:
        return "test"
    if "odi" in name or "one day" in name:
        return "odi"
    if "t20" in name:
        return "t20"
    return ""


def _is_marquee(m):
    teams = " ".join(m.get("teams", []) or []).lower()
    name = (m.get("name") or "").lower()
    return ("india" in teams or "india" in name) and any(
        opp in teams or opp in name for opp in MARQUEE_OPPONENTS
    )


_current_matches_cache = None
_current_matches_cache_at = None
CURRENT_MATCHES_CACHE_TTL_SECONDS = 300  # 5 min — shared across get_live_matches/get_finished_matches


def _fetch_current_matches():
    global _current_matches_cache, _current_matches_cache_at

    if _current_matches_cache_at is not None:
        elapsed = (datetime.now(timezone.utc) - _current_matches_cache_at).total_seconds()
        if elapsed < CURRENT_MATCHES_CACHE_TTL_SECONDS:
            return _current_matches_cache

    keys = list(_cricapi_keys())
    if not keys:
        print("No CricAPI keys set — skipping trending fetch")
        return []

    last_reason = None
    for key in keys:
        try:
            r = requests.get(
                f"{BASE_URL}/currentMatches",
                params={"apikey": key, "offset": 0},
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"CricAPI currentMatches failed: {e}")
            continue

        if data.get("status") != "success":
            last_reason = data.get("reason") or data.get("status")
            print(f"CricAPI returned non-success ({key[:8]}...): {last_reason}")
            continue

        result = data.get("data", [])
        _current_matches_cache = result
        _current_matches_cache_at = datetime.now(timezone.utc)
        return result

    print(f"All CricAPI keys exhausted/failed — last reason: {last_reason}")
    return []


def _search_marquee_series():
    """Finds currently-active 'India tour of <opponent>' series. Cached 24h
    via cricket_db to conserve API quota."""
    cricket_db = _get_cricket_db()
    cache_key, ts_key = "marquee_series_cache", "marquee_series_cache_at"

    if cricket_db:
        try:
            cached_at = cricket_db.get_meta(ts_key)
            if cached_at:
                elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(cached_at)).total_seconds()
                if elapsed < SERIES_CACHE_TTL_SECONDS:
                    cached = cricket_db.get_meta(cache_key)
                    if cached:
                        return json.loads(cached)
        except Exception:
            pass

    if not CRICAPI_KEY:
        return []

    try:
        r = requests.get(
            f"{BASE_URL}/series",
            params={"apikey": CRICAPI_KEY, "search": "India tour of"},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"CricAPI series search failed: {e}")
        return []

    if data.get("status") != "success":
        return []

    today = datetime.now(timezone.utc).date()
    active = []
    for s in data.get("data", []):
        name = (s.get("name") or "").lower()
        if not any(opp in name for opp in MARQUEE_OPPONENTS):
            continue
        try:
            start_date = datetime.fromisoformat(s.get("startDate")).date()
        except Exception:
            continue
        # endDate often omits the year (e.g. "Jul 19") — assume same year as start
        try:
            end_date = datetime.strptime(f"{s.get('endDate')} {start_date.year}", "%b %d %Y").date()
        except Exception:
            end_date = start_date
        if start_date <= today <= end_date:
            active.append(s)

    if cricket_db:
        try:
            cricket_db.set_meta(cache_key, json.dumps(active))
            cricket_db.set_meta(ts_key, datetime.now(timezone.utc).isoformat())
        except Exception:
            pass

    return active


def _get_marquee_series_matches():
    """For each active marquee series, returns matches that have started
    (live or finished). Each series' match list is cached 15min via
    cricket_db to conserve API quota."""
    cricket_db = _get_cricket_db()
    series_list = _search_marquee_series()
    if not series_list:
        return []

    results = []
    for s in series_list:
        series_id = s.get("id")
        if not series_id:
            continue

        cache_key, ts_key = f"series_matches_{series_id}", f"series_matches_{series_id}_at"
        match_list = None

        if cricket_db:
            try:
                cached_at = cricket_db.get_meta(ts_key)
                if cached_at:
                    elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(cached_at)).total_seconds()
                    if elapsed < MATCHLIST_CACHE_TTL_SECONDS:
                        cached = cricket_db.get_meta(cache_key)
                        if cached:
                            match_list = json.loads(cached)
            except Exception:
                pass

        if match_list is None:
            try:
                r = requests.get(
                    f"{BASE_URL}/series_info",
                    params={"apikey": CRICAPI_KEY, "id": series_id},
                    timeout=20,
                )
                r.raise_for_status()
                info = r.json()
            except Exception as e:
                print(f"CricAPI series_info failed for {series_id}: {e}")
                continue
            if info.get("status") != "success":
                continue
            match_list = info.get("data", {}).get("matchList", [])
            if cricket_db:
                try:
                    cricket_db.set_meta(cache_key, json.dumps(match_list))
                    cricket_db.set_meta(ts_key, datetime.now(timezone.utc).isoformat())
                except Exception:
                    pass

        for m in match_list:
            if not m.get("matchStarted", False):
                continue  # hasn't started yet
            match_type = _resolve_match_type(m)
            if match_type not in ALLOWED_MATCH_TYPES:
                continue
            status_text = (m.get("status") or "").lower()
            is_finished = m.get("matchEnded", False) or any(
                kw in status_text for kw in ["won", "match tied", "match drawn", "no result"]
            )
            # CricAPI's matchStarted flag can lag behind reality near tip-off —
            # if the status text still says "starts at", treat it as not
            # actually live yet regardless of what matchStarted claims.
            not_actually_started = "starts at" in status_text
            if not_actually_started:
                continue  # get_upcoming_matches() will pick this one up instead
            if _is_excluded(m):
                continue
            results.append({
                "id": m.get("id"),
                "name": m.get("name", ""),
                "matchType": match_type,
                "teams": m.get("teams", []) or [],
                "status": m.get("status", ""),
                "date": m.get("date", ""),
                "venue": m.get("venue", ""),
                "_live": not is_finished,
            })
    return results


def get_finished_matches(limit=5):
    """Returns recently finished Indian-cricket matches (currentMatches feed
    only), most recent first, marquee matchups sorted first."""
    raw = _fetch_current_matches()

    matches = []
    for m in raw:
        status_text = (m.get("status") or "").lower()
        match_type = _resolve_match_type(m)
        is_finished = any(kw in status_text for kw in ["won", "match tied", "match drawn", "no result"])
        if not is_finished or match_type not in ALLOWED_MATCH_TYPES:
            continue
        if not is_indian_match(m) or _is_excluded(m):
            continue
        matches.append({
            "id": m.get("id"),
            "name": m.get("name", ""),
            "matchType": match_type,
            "teams": m.get("teams", []),
            "status": m.get("status", ""),
            "date": m.get("date", ""),
            "venue": m.get("venue", ""),
        })

    matches.sort(key=_is_marquee, reverse=True)
    return matches[:limit]


def get_live_matches(limit=5):
    """Returns Indian-cricket matches currently in progress (currentMatches
    feed only), marquee matchups first."""
    raw = _fetch_current_matches()

    matches = []
    for m in raw:
        match_type = _resolve_match_type(m)
        started = m.get("matchStarted", False)
        ended = m.get("matchEnded", False)
        if not started or ended or match_type not in ALLOWED_MATCH_TYPES:
            continue
        if not is_indian_match(m) or _is_excluded(m):
            continue
        matches.append({
            "id": m.get("id"),
            "name": m.get("name", ""),
            "matchType": match_type,
            "teams": m.get("teams", []),
            "status": m.get("status", ""),
            "date": m.get("date", ""),
            "venue": m.get("venue", ""),
        })

    matches.sort(key=_is_marquee, reverse=True)
    return matches[:limit]


def get_trending_matches(limit=5):
    """Marquee series matches first (e.g. today's India vs England match,
    live or just-finished — found via direct series lookup since the
    generic currentMatches feed doesn't reliably surface these), then live
    matches from the generic feed, then finished matches from the generic
    feed. Marquee live matches are prioritized above everything else."""
    marquee = _get_marquee_series_matches()
    marquee_live = [m for m in marquee if m.get("_live")]
    marquee_finished = [m for m in marquee if not m.get("_live")]

    live = get_live_matches(limit=limit)
    finished = get_finished_matches(limit=limit)

    seen = set()
    combined = []
    for m in marquee_live + live + marquee_finished + finished:
        if m["id"] in seen:
            continue
        seen.add(m["id"])
        combined.append(m)

    return combined[:limit]


def get_upcoming_matches(limit=5):
    """Marquee series matches that haven't started yet (previews/build-up
    content — e.g. 'India vs England 3rd T20 preview, Sunday'). Draws from
    the same cached marquee series match lists used elsewhere in this
    module, just inverting the matchStarted filter."""
    series_list = _search_marquee_series()
    if not series_list:
        return []

    cricket_db = _get_cricket_db()
    results = []

    for s in series_list:
        series_id = s.get("id")
        if not series_id:
            continue
        cache_key = f"series_matches_{series_id}"
        match_list = None
        if cricket_db:
            try:
                cached = cricket_db.get_meta(cache_key)
                if cached:
                    match_list = json.loads(cached)
            except Exception:
                pass
        if match_list is None:
            continue  # rely on _get_marquee_series_matches() having run first to populate cache

        for m in match_list:
            if m.get("matchStarted", False):
                continue  # only want matches that haven't started
            match_type = _resolve_match_type(m)
            if match_type not in ALLOWED_MATCH_TYPES:
                continue
            results.append({
                "id": m.get("id"),
                "name": m.get("name", ""),
                "matchType": match_type,
                "teams": m.get("teams", []) or [],
                "status": m.get("status", "") or "Upcoming",
                "date": m.get("date", ""),
                "venue": m.get("venue", ""),
            })

    results.sort(key=_is_marquee, reverse=True)
    return results[:limit]


def get_all_topics(limit=8):
    """Merges all four content types into one prioritized list, each item
    tagged with topic_type so research_agent.py knows how to handle it.

    Priority order: breaking news > live matches > upcoming matches >
    recently finished matches. Marquee (India vs top-tier opponent) matches
    are already prioritized within the live/finished groups by their
    respective source functions."""
    from agents_cricket.news_agent import get_breaking_cricket_news

    news = get_breaking_cricket_news(limit=3)
    marquee = _get_marquee_series_matches()
    marquee_live = [m for m in marquee if m.get("_live")]
    marquee_finished = [m for m in marquee if not m.get("_live")]
    live = get_live_matches(limit=limit)
    upcoming = get_upcoming_matches(limit=3)
    finished = get_finished_matches(limit=limit)

    seen_ids = set()
    topics = []

    import hashlib
    import re
    for n in news:
        # News items have no natural id (unlike matches) — derive a stable
        # one from the normalized title so the same story dedupes even
        # when the link differs across sources/scrapes.
        _norm_title = re.sub(r"[^\w\s]", "", n.get("title", "").lower())
        _norm_title = re.sub(r"\s+", " ", _norm_title).strip()
        news_id = "news_" + hashlib.md5(_norm_title.encode()).hexdigest()[:16]
        topics.append({**n, "id": news_id, "topic_type": "news"})

    for group in (marquee_live, live):
        for m in group:
            if m["id"] in seen_ids:
                continue
            seen_ids.add(m["id"])
            topics.append({**m, "topic_type": "live"})

    for m in upcoming:
        if m["id"] in seen_ids:
            continue
        seen_ids.add(m["id"])
        topics.append({**m, "topic_type": "upcoming"})

    for group in (marquee_finished, finished):
        for m in group:
            if m["id"] in seen_ids:
                continue
            seen_ids.add(m["id"])
            topics.append({**m, "topic_type": "finished"})

    return topics[:limit]
