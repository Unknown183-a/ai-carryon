# agents_cricket/video_clip_agent.py
"""Cricket-specific Pexels *video* clip fetcher — the moving-B-roll twin of
agents_cricket/image_agent.py's static Pexels chain. Mirrors the same
structured priority order (venue -> team -> generic), minus the player-photo
step (there's no reliable source of real per-player video clips the way
CricAPI's match_squad gives us real photos).

Falls back gracefully per-slot: any failed venue/team/generic search is just
skipped. The caller (scheduler_cricket.py) falls back entirely to
generate_backgrounds() (static images) if too few clips come back overall,
same pattern scheduler_hindi.py / scheduler.py already use.
"""
import os
import random
import requests

from agents.video_clip_agent import search_pexels_video

GENERIC_QUERIES = [
    "cricket stadium crowd",
    "cricket bat ball closeup",
    "cricket player celebration",
    "cricket stadium floodlights",
    "cricket match action",
    "cricket ground aerial",
    "cricket fans stadium",
    "cricket boundary rope",
    "cricket pitch wicket",
    "cricket team huddle",
]


def _download(url, output_path):
    r = requests.get(url, timeout=90, stream=True)
    r.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)


def _try_query(query, output_path, used_urls):
    """Searches Pexels video for `query`, skipping a result already used
    this run (e.g. same team name appearing twice), and downloads it."""
    try:
        url = search_pexels_video(query)
    except Exception as e:
        print(f"Pexels video search failed for '{query}': {e}")
        return False
    if not url or url in used_urls:
        return False
    try:
        _download(url, output_path)
        used_urls.add(url)
        return True
    except Exception as e:
        print(f"Cricket clip download failed for '{query}': {e}")
        return False


def generate_background_clips_cricket(structured=None, num_clips=4):
    """structured: dict from research_agent.get_summary_for_topic — expects
    venue, teams (same shape agents_cricket/image_agent.py already consumes).
    Falls back to fully generic queries if structured is None/empty."""
    folder = "assets/pexels_clips"
    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder):
        os.remove(os.path.join(folder, f))

    structured = structured or {}
    venue = structured.get("venue") or ""
    teams = structured.get("teams") or []

    clip_paths, errors = [], []
    used_urls = set()
    slot = 1

    # 1) Venue-specific stock footage
    if venue and slot <= num_clips:
        output_path = os.path.join(folder, f"{slot}.mp4")
        if _try_query(f"{venue} cricket stadium", output_path, used_urls):
            clip_paths.append(output_path)
            slot += 1
        else:
            errors.append(f"No Pexels video for venue '{venue}'")

    # 2) Team-specific stock footage
    for team in teams:
        if slot > num_clips:
            break
        output_path = os.path.join(folder, f"{slot}.mp4")
        if _try_query(f"{team} cricket team", output_path, used_urls):
            clip_paths.append(output_path)
            slot += 1
        else:
            errors.append(f"No Pexels video for team '{team}'")

    # 3) Generic fallback for any remaining slots — shuffled each run so a
    # news item (venue=None, teams=[]) doesn't always draw the same clips.
    generic_pool = GENERIC_QUERIES[:]
    random.shuffle(generic_pool)
    gi = 0
    while slot <= num_clips and gi < len(generic_pool):
        output_path = os.path.join(folder, f"{slot}.mp4")
        if _try_query(generic_pool[gi], output_path, used_urls):
            clip_paths.append(output_path)
            slot += 1
        gi += 1

    return clip_paths, errors
