# agents_cricket/news_agent.py
"""
Fetches breaking cricket news (retirements, selection drama, records,
controversies) via Google News RSS — free, no API key needed.

Double-filtered for cricket relevance:
1. The RSS query itself is scoped to cricket ("cricket" + a cricket-only
   site restriction via Google News' own topic search).
2. Every returned headline is re-checked against a cricket keyword list
   before being surfaced — Google News RSS occasionally leaks unrelated
   results, so this is a hard gate, not just a nice-to-have.
"""
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"

# Query scoped tightly to cricket news — "when:2d" limits to last 48h so we
# only ever surface genuinely fresh/breaking items, not old recaps.
QUERY = "cricket when:2d"

# Hard relevance gate — a headline must contain at least one of these
# (case-insensitive) to be treated as genuinely cricket-related, since
# Google News RSS can occasionally return loosely-matched results.
CRICKET_KEYWORDS = {
    "cricket", "bcci", "icc", "ipl", "t20", "odi", "test match", "wicket",
    "batsman", "bowler", "all-rounder", "captain", "selector", "wpl",
    "ranji", "world cup", "ashes", "world test championship", "wtc",
    "run out", "century", "retirement", "retires", "debut",
}

# A few high-signal cricketer/team surnames worth boosting relevance for —
# extend this list over time as needed. Not required for a match, just
# used to help sort/prioritize when multiple headlines qualify.
HIGH_SIGNAL_TERMS = {
    "rohit sharma", "virat kohli", "jasprit bumrah", "hardik pandya",
    "rishabh pant", "shubman gill", "team india", "bcci",
}


def _is_cricket_relevant(title, summary=""):
    text = f"{title} {summary}".lower()
    return any(kw in text for kw in CRICKET_KEYWORDS)


def _score_headline(title, summary=""):
    text = f"{title} {summary}".lower()
    score = 0
    for term in HIGH_SIGNAL_TERMS:
        if term in text:
            score += 2
    for kw in CRICKET_KEYWORDS:
        if kw in text:
            score += 1
    return score


def get_breaking_cricket_news(limit=5, max_age_hours=48):
    """Returns a list of dicts: {title, link, published, source, score}.
    Sorted by relevance score (high-signal player/team mentions first),
    then recency. Returns [] on any fetch/parse failure — fails open, same
    pattern as trending_agent."""
    try:
        r = requests.get(
            GOOGLE_NEWS_RSS,
            params={"q": QUERY, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"},
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        r.raise_for_status()
    except Exception as e:
        print(f"Google News RSS fetch failed: {e}")
        return []

    try:
        root = ET.fromstring(r.content)
    except Exception as e:
        print(f"Google News RSS parse failed: {e}")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    items = []

    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date_raw = item.findtext("pubDate") or ""
        source = (item.find("source").text if item.find("source") is not None else "").strip()

        # Google News titles are usually "Headline - Source" — strip the
        # trailing " - Source" for a cleaner title if it duplicates <source>
        clean_title = re.sub(r"\s+-\s+[^-]+$", "", title) if source and title.endswith(source) else title

        if not _is_cricket_relevant(clean_title):
            continue  # hard gate — skip anything not clearly cricket-related

        try:
            pub_dt = datetime.strptime(pub_date_raw, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
        except Exception:
            pub_dt = datetime.now(timezone.utc)  # if unparseable, don't drop it — just can't age-filter precisely

        if pub_dt < cutoff:
            continue

        items.append({
            "title": clean_title,
            "link": link,
            "published": pub_dt.isoformat(),
            "source": source,
            "score": _score_headline(clean_title),
        })

    items.sort(key=lambda x: (x["score"], x["published"]), reverse=True)
    return items[:limit]
