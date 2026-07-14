# agents_cricket/research_agent.py
"""Fetches the full scorecard for a match and turns it into a compact text
summary the script agent can write a recap from."""
import os
import requests
from dotenv import load_dotenv
load_dotenv()

CRICAPI_KEY = os.getenv("CRICAPI_KEY", "")
BASE_URL = "https://api.cricapi.com/v1"


def get_match_summary(match):
    """match: one dict from trending_agent.get_finished_matches().
    Returns a plain-text summary string, or None if the scorecard can't be fetched."""
    match_id = match.get("id")
    if not match_id or not CRICAPI_KEY:
        return None

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
        return None

    if data.get("status") != "success":
        return None

    d = data.get("data", {})
    lines = [
        f"Match: {d.get('name', match.get('name', ''))}",
        f"Status: {d.get('status', match.get('status', ''))}",
        f"Venue: {d.get('venue', match.get('venue', ''))}",
    ]

    # Innings-level scores
    for inning in d.get("scorecard", []):
        inning_name = inning.get("inning", "")
        lines.append(f"\n{inning_name}:")
        batting = inning.get("batting", [])[:3]  # top 3 batters
        for b in batting:
            lines.append(
                f"  {b.get('batsman', {}).get('name','')} — "
                f"{b.get('r','?')}({b.get('b','?')}) "
                f"{'*' if b.get('dismissal-text','') == '' else ''}"
            )
        bowling = inning.get("bowling", [])[:2]  # top 2 bowlers
        for bo in bowling:
            lines.append(
                f"  Bowling: {bo.get('bowler', {}).get('name','')} — "
                f"{bo.get('w','?')}/{bo.get('r','?')} ({bo.get('o','?')} ov)"
            )

    return "\n".join(lines)
