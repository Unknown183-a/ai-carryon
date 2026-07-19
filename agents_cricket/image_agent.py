# agents_cricket/image_agent.py
"""Match/topic-specific backgrounds. Priority order per image depends on
topic_type (set by trending_agent.get_all_topics(), passed through in
structured by research_agent.py):

- "live" / "finished" (real matches, have a match_id):
    1. Standout player's real photo, via CricAPI match_squad
    2. Venue-specific Pexels stock
    3. Team-specific Pexels stock
    4. Generic cricket stock (last resort)

- "news" / "upcoming" (no match_id, or match hasn't happened yet):
    No reliable real player photo source exists for these — CricAPI's
    standalone players search endpoint returns names but no playerImg
    (confirmed empirically, not just per their docs). So these skip
    straight to venue/team/generic, same fallback chain minus step 1.

CricAPI's "no photo available" placeholder is icon512.png — detected and
skipped rather than downloaded as a useless generic icon.
"""
import os
import requests
from dotenv import load_dotenv
load_dotenv()

CRICAPI_KEY = os.getenv("CRICAPI_KEY", "")
PEXELS_KEY = os.getenv("PEXELS_API_KEY", "")
BASE_URL = "https://api.cricapi.com/v1"
PLACEHOLDER_MARKER = "icon512.png"

GENERIC_QUERIES = [
    "cricket stadium crowd",
    "cricket bat ball closeup",
    "cricket player celebration",
    "cricket stadium floodlights",
]

# topic_types where a match_id exists and match_squad can be queried
PLAYER_PHOTO_ELIGIBLE = {"live", "finished"}


def _fetch_squad_photo(match_id, player_name):
    """Looks up player_name in the match's squad list, returns a real photo
    URL, or None if not found / only the placeholder is available."""
    if not match_id or not player_name or not CRICAPI_KEY:
        return None
    try:
        r = requests.get(
            f"{BASE_URL}/match_squad",
            params={"apikey": CRICAPI_KEY, "id": match_id},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"match_squad fetch failed: {e}")
        return None

    if data.get("status") != "success":
        return None

    target = player_name.strip().lower()
    for team in data.get("data", []):
        for p in team.get("players", []):
            name = (p.get("name") or "").strip().lower()
            if name == target or target in name or name in target:
                img = p.get("playerImg", "")
                if img and PLACEHOLDER_MARKER not in img:
                    return img
                return None
    return None


def _download(url, output_path):
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    with open(output_path, "wb") as f:
        f.write(r.content)


def _pexels_search(query, output_path):
    if not PEXELS_KEY:
        return False
    try:
        headers = {"Authorization": PEXELS_KEY}
        params = {"query": query, "orientation": "portrait", "size": "large", "per_page": 1}
        r = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if data.get("photos"):
            img_url = data["photos"][0]["src"]["large2x"]
            _download(img_url, output_path)
            return True
    except Exception as e:
        print(f"Pexels search failed for '{query}': {e}")
    return False


def generate_backgrounds(match_summary=None, num_images=4, structured=None):
    """structured: dict from research_agent.get_summary_for_topic — expects
    topic_type, match_id, venue, teams, standout_player. Falls back to fully
    generic behavior if structured is None (keeps old callers working)."""
    folder = "assets/backgrounds"
    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder):
        os.remove(os.path.join(folder, f))

    image_paths, errors = [], []
    slot = 1

    structured = structured or {}
    topic_type = structured.get("topic_type", "finished")
    match_id = structured.get("match_id")
    venue = structured.get("venue") or ""
    teams = structured.get("teams") or []
    standout_player = structured.get("standout_player")

    # 1) Standout player's real photo — only for live/finished matches,
    #    where a real match_id exists to query match_squad against.
    if topic_type in PLAYER_PHOTO_ELIGIBLE and standout_player and slot <= num_images:
        photo_url = _fetch_squad_photo(match_id, standout_player)
        if photo_url:
            output_path = os.path.join(folder, f"{slot}.jpg")
            try:
                _download(photo_url, output_path)
                image_paths.append(output_path)
                slot += 1
            except Exception as e:
                errors.append(f"Player photo download failed: {e}")
        else:
            errors.append(f"No real photo found for '{standout_player}' — using fallback")
    elif topic_type not in PLAYER_PHOTO_ELIGIBLE:
        errors.append(f"topic_type='{topic_type}' has no match to query for a real player photo — using fallback")

    # 2) Venue-specific stock
    if venue and slot <= num_images:
        output_path = os.path.join(folder, f"{slot}.jpg")
        if _pexels_search(f"{venue} cricket stadium", output_path):
            image_paths.append(output_path)
            slot += 1
        else:
            errors.append(f"No Pexels result for venue '{venue}'")

    # 3) Team-specific stock
    for team in teams:
        if slot > num_images:
            break
        output_path = os.path.join(folder, f"{slot}.jpg")
        if _pexels_search(f"{team} cricket team", output_path):
            image_paths.append(output_path)
            slot += 1
        else:
            errors.append(f"No Pexels result for team '{team}'")

    # 4) Generic fallback for any remaining slots
    gi = 0
    while slot <= num_images and gi < len(GENERIC_QUERIES):
        output_path = os.path.join(folder, f"{slot}.jpg")
        if _pexels_search(GENERIC_QUERIES[gi], output_path):
            image_paths.append(output_path)
            slot += 1
        gi += 1

    return image_paths, errors
