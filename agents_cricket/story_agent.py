# agents_cricket/story_agent.py
"""Cricket V2 Phase 2 (step 8b) — story agent. Writes the Hindi script as
Hook -> Context -> Event -> Explanation -> Payoff from verified match data."""
from agents_cricket.script_agent import safe_invoke
from agents_cricket.story_utils import clean_script


def write_story(summary, structured, fmt, fmt_guidance, hook, word_range, feedback=None):
    lo, hi = word_range
    player = (structured or {}).get("standout_player")
    player_line = f"- Standout player in the data: {player}\n" if player else ""
    fb = f"\nFIX THIS FROM THE LAST ATTEMPT: {feedback}\n" if feedback else ""
    prompt = f"""You are a cricket storyteller writing a voice-over for a YouTube Short.
Write the whole script in HINDI, Devanagari script (player and team names may stay as in the data).

Format: {fmt} — {fmt_guidance}

Match data (the ONLY source of facts):
{summary}

The script MUST begin with exactly this hook, unchanged: "{hook}"

Structure (flow naturally, no labels):
hook -> one-line context -> the key event -> why it happened / why it mattered -> payoff (what it changed)
{player_line}
RULES:
- {lo} to {hi} words total
- Do not invent facts, scores, quotes, dates or records. Use only numbers present in the data, written as digits (0-9).
- If the data is thin, write a shorter script rather than padding or guessing
- No generic intro, no greeting, no "like/subscribe", no stage directions, no hashtags, no labels
- Every sentence must move the story forward; short punchy sentences, confident analyst tone
- End on the payoff, not on a call to action
{fb}
Return only the script text."""
    return clean_script(safe_invoke(prompt).content)
