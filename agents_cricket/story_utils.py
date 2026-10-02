# agents_cricket/story_utils.py
"""Cricket V2 Phase 2 — shared helpers: Hindi word counting and a cheap
numbers-must-come-from-the-data guard (spec: "never invent scores/statistics")."""
import re

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def word_count(text):
    return len(text.split())


def numbers_in(text):
    return set(re.findall(r"\d+(?:\.\d+)?", (text or "").translate(_DEVANAGARI_DIGITS)))


def ungrounded_numbers(script, source_text):
    """Numbers the script states that appear nowhere in the match data.
    Only digit tokens are checked (spelled-out numbers are not)."""
    return sorted(numbers_in(script) - numbers_in(source_text), key=float)


def clean_script(text):
    """Strip labels/markdown the LLM sometimes adds around the script."""
    text = re.sub(r"[*#_`>]+", "", text or "")
    text = re.sub(r"^\s*(hook|context|event|payoff|script|स्क्रिप्ट|हुक)\s*[:：-]\s*", "",
                  text, flags=re.I | re.M)
    return " ".join(text.split())
