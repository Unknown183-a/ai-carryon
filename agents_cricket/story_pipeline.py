# agents_cricket/story_pipeline.py
"""
Cricket V2 Phase 2 (steps 7-8): format router -> hook -> story -> retention.

create_story_script() always returns a usable script: any failure, an
ungrounded number, or a bad length falls back to the legacy single-call
create_cricket_script(), so this can never block an upload.

Set CRICKET_V2_STORY=0 to switch back to the legacy script entirely.
"""
import json
import os

from agents_cricket.format_router import FORMATS, route_format
from agents_cricket.hook_agent import generate_hook
from agents_cricket.retention_agent import optimize_retention
from agents_cricket.script_agent import create_cricket_script
from agents_cricket.story_agent import write_story
from agents_cricket.story_utils import ungrounded_numbers, word_count

V2_STORY = os.getenv("CRICKET_V2_STORY", "1") != "0"
FORMATS_KEY = "cricket_recent_formats"
HOOKS_KEY = "cricket_recent_hook_types"
KEEP = 10


def _range(topic_type):
    return (70, 100) if topic_type in ("news", "upcoming") else (90, 120)


def _load(key):
    try:
        from agents_cricket.database import db
        raw = db.get_meta(key)
        return json.loads(raw) if raw else []
    except Exception:
        return []


def record_story_meta(story):
    """Call after a successful upload so cooldowns only count published videos."""
    try:
        from agents_cricket.database import db
        if not story.get("used_v2"):
            return
        for key, val in ((FORMATS_KEY, story["format"]), (HOOKS_KEY, story["hook_type"])):
            db.set_meta(key, json.dumps((_load(key) + [val])[-KEEP:]))
    except Exception as e:
        print(f"Story meta not saved: {e}")


def _legacy(summary, structured, reason):
    print(f"Story V2 fallback -> legacy script ({reason})")
    return {"script": create_cricket_script(summary, standout_player=(structured or {}).get("standout_player")),
            "format": None, "hook_type": None, "hook": None, "used_v2": False}


def create_story_script(topic, summary, structured):
    structured = structured or {}
    if not V2_STORY:
        return _legacy(summary, structured, "disabled")
    try:
        topic_type = structured.get("topic_type") or topic.get("topic_type", "finished")
        lo, hi = _range(topic_type)

        fmt = route_format(topic_type, summary, structured, _load(FORMATS_KEY))
        guidance = FORMATS[fmt]
        hook_type, hook = generate_hook(summary, fmt, guidance, _load(HOOKS_KEY))
        if not hook:
            return _legacy(summary, structured, "no valid hook")
        print(f"Story V2: format={fmt} hook={hook_type}: {hook}")

        feedback, draft = None, None
        for attempt in range(2):
            draft = write_story(summary, structured, fmt, guidance, hook, (lo, hi), feedback)
            bad = ungrounded_numbers(draft, summary)
            if not bad:
                break
            feedback = f"These numbers are not in the data, remove them: {', '.join(bad)}"
            print(f"Story V2: ungrounded numbers {bad} (attempt {attempt + 1})")
            draft = None
        if not draft:
            return _legacy(summary, structured, "numbers not in match data")

        final = draft
        try:
            tightened = optimize_retention(draft, summary, (lo, hi))
            if (not ungrounded_numbers(tightened, summary)
                    and lo * 0.85 <= word_count(tightened) <= hi * 1.1):
                final = tightened
            else:
                print("Story V2: retention pass rejected, keeping draft")
        except Exception as e:
            print(f"Story V2: retention skipped: {e}")

        n = word_count(final)
        if not (lo * 0.7 <= n <= hi * 1.25):
            return _legacy(summary, structured, f"bad length {n} words")
        return {"script": final, "format": fmt, "hook_type": hook_type, "hook": hook, "used_v2": True}
    except Exception as e:
        return _legacy(summary, structured, f"error: {e}")
