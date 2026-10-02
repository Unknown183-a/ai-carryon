# agents_cricket/hook_agent.py
"""Cricket V2 Phase 2 (step 8a) — hook agent. One LLM call proposes 3 hooks of
different types; the first valid one whose type is not the last-used type wins."""
import re

from agents_cricket.script_agent import safe_invoke
from agents_cricket.story_utils import clean_script, ungrounded_numbers, word_count

HOOK_TYPES = {
    "STAT_HOOK": "a striking number from the data",
    "TACTICAL_HOOK": "a tactical detail most viewers missed",
    "MYSTERY_HOOK": "a question the viewer must stay to get answered",
    "EMOTIONAL_HOOK": "the emotion of the moment (silence, shock, joy)",
    "RECORD_HOOK": "a record or rarity — ONLY if the data supports it",
}
_BAD_START = ("नमस्कार", "नमस्ते", "दोस्तों", "दोस्त", "स्वागत", "hello", "welcome", "hi ")
MAX_HOOK_WORDS = 14


def _valid(hook, summary):
    if not hook or word_count(hook) > MAX_HOOK_WORDS or word_count(hook) < 3:
        return False
    if hook.strip().lower().startswith(_BAD_START):
        return False
    return not ungrounded_numbers(hook, summary)


def generate_hook(summary, fmt, fmt_guidance, recent_hook_types=None):
    """Returns (hook_type, hook_text) or (None, None)."""
    recent = list(recent_hook_types or [])[-1:]
    types = "\n".join(f"- {k}: {v}" for k, v in HOOK_TYPES.items())
    prompt = f"""You write the first 2 seconds of a Hindi cricket YouTube Short.
Format: {fmt} — {fmt_guidance}

Match data (the ONLY source of facts):
{summary}

Write 3 different hook lines, each of a DIFFERENT type from this list:
{types}

Rules:
- Hindi in Devanagari script; player/team names may stay as they are in the data
- Each hook is 4 to {MAX_HOOK_WORDS} words, one sentence, creates curiosity or shock
- Never greet ("नमस्कार", "दोस्तों", "welcome"); never start with filler
- Use ONLY facts and numbers present in the data; write numbers as digits (0-9)
- If the data does not support a type (e.g. no record), skip that type

Output exactly 3 lines, nothing else, in the form:
TYPE | hook text"""
    try:
        raw = safe_invoke(prompt).content
    except Exception as e:
        print(f"Hook agent failed: {e}")
        return None, None

    options = []
    for line in raw.splitlines():
        m = re.match(r"\s*([A-Z_]+)\s*\|\s*(.+)", line)
        if m and m.group(1) in HOOK_TYPES:
            hook = clean_script(m.group(2)).strip('"“”')
            if _valid(hook, summary):
                options.append((m.group(1), hook))
    for t, h in options:
        if t not in recent:
            return t, h
    return options[0] if options else (None, None)
