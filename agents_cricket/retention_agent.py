# agents_cricket/retention_agent.py
"""Cricket V2 Phase 2 (step 8c) — retention agent: tightens the draft without
adding facts. The caller keeps the original draft if this output is unusable."""
from agents_cricket.script_agent import safe_invoke
from agents_cricket.story_utils import clean_script


def optimize_retention(story, summary, word_range):
    lo, hi = word_range
    prompt = f"""Edit this Hindi cricket Short script for viewer retention.

Script:
{story}

Match data (do not add anything that is not here):
{summary}

Do:
- keep the first sentence (the hook) EXACTLY as it is
- remove repeated information, empty transitions, generic statements and unimportant numbers
- increase curiosity and keep the story moving; strengthen the final payoff line
- keep it {lo} to {hi} words, Hindi (Devanagari), same facts

Do not add new facts or numbers. Return only the edited script."""
    return clean_script(safe_invoke(prompt).content)
