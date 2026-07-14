# agents_cricket/trending_agent.py
"""
Pulls recently finished cricket matches from CricAPI (cricketdata.org).
Free tier: 100 hits/day, so call sparingly — once per /trigger, not in a loop.
"""
import os
import requests
from dotenv import load_dotenv
load_dotenv()

CRICAPI_KEY = os.getenv("CRICAPI_KEY", "")
BASE_URL = "https://api.cricapi.com/v1"

ALLOWED_MATCH_TYPES = {"t20", "odi", "test"}


def get_finished_matches(limit=5):
    """Returns recently finished matches, most recent first. Fails open (empty list) on error."""
    if not CRICAPI_KEY:
        print("CRICAPI_KEY not set — skipping trending fetch")
        return []

    try:
        r = requests.get(
            f"{BASE_URL}/currentMatches",
            params={"apikey": CRICAPI_KEY, "offset": 0},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"CricAPI currentMatches failed: {e}")
        return []

    if data.get("status") != "success":
        print(f"CricAPI returned non-success: {data.get('status')}")
        return []

    matches = []
    for m in data.get("data", []):
        status_text = (m.get("status") or "").lower()
        match_type = (m.get("matchType") or "").lower()
        is_finished = any(kw in status_text for kw in ["won", "match tied", "match drawn", "no result"])
        if not is_finished or match_type not in ALLOWED_MATCH_TYPES:
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
    return matches[:limit]
