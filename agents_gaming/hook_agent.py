# agents_gaming/hook_agent.py
"""
Gaming V2 Phase 3 — generate five hooks (one per type), score them, keep the
strongest. One LLM call proposes + self-scores; local rules then veto
anything greeting-like, too long, AI-cliche, or containing an invented number.
"""
from agents_gaming.v2_utils import (
    clamp, extract_json, find_ai_phrases, ungrounded_numbers, word_count,
)

HOOK_TYPES = {
    "CURIOSITY": "makes the viewer need to know what happens (a question, a gap)",
    "SHOCK": "states the unbelievable fact of the moment bluntly",
    "STORY": "drops the viewer into the situation like the first line of a story",
    "REACTION": "voices the disbelief a viewer would feel watching it",
    "CHALLENGE": "dares the viewer to spot/predict/keep up with something",
}
MIN_WORDS, MAX_WORDS = 3, 14
_BAD_START = ("hey", "hi ", "hello", "welcome", "what's up", "whats up", "guys", "today")


def _grounding_text(moment, summary):
    m = moment or {}
    return " ".join([
        summary or "",
        str(m.get("game", "")), str(m.get("what_happened", "")), str(m.get("setup", "")),
        str(m.get("payoff", "")), str(m.get("reaction", "")),
    ])


def _valid(text, grounding):
    if not text or not (MIN_WORDS <= word_count(text) <= MAX_WORDS):
        return False
    if text.lower().startswith(_BAD_START):
        return False
    if find_ai_phrases(text):
        return False
    return not ungrounded_numbers(text, grounding)


def _build_prompt(moment, summary):
    types = "\n".join(f"- {k}: {v}" for k, v in HOOK_TYPES.items())
    return f"""You write the first 2 seconds of a gaming YouTube Short — the line that
stops the scroll. The viewer watches real gameplay while you speak.

Moment analysis (the ONLY source of facts):
Game: {moment.get('game', '')}
Type: {moment.get('moment_type', '')}
What happened: {moment.get('what_happened', '')}
Setup: {moment.get('setup', '')}
Payoff: {moment.get('payoff', '')}
Reaction: {moment.get('reaction', '')}

Clip data:
{summary}

Write exactly 5 hooks, ONE of each type:
{types}

Rules:
- {MIN_WORDS}-{MAX_WORDS} words each, one sentence, spoken like a creator, not an announcer
- Tease the payoff, never give it away; no greetings; no "you won't believe", "watch what happens",
  "nobody expected", "insane moment", "absolutely incredible", "let's take a look"
- Use ONLY facts/numbers present above; write numbers as digits
- Score each 1-10 for scroll-stopping power (be harsh; most hooks are 5-7)

Reply with ONLY this JSON:
{{"hooks": [{{"type": "CURIOSITY", "text": "...", "score": 7}}, ...]}}"""


def generate_hooks(moment, summary, recent_hook_types=None):
    """Returns {'text','type','score','candidates'} for the best valid hook, or
    None if the LLM is unavailable / nothing valid came back (caller then lets
    the commentary agent open on its own)."""
    from agents.model_invoke_agent_english import safe_invoke

    grounding = _grounding_text(moment, summary)
    try:
        raw = safe_invoke(_build_prompt(moment, summary)).content
    except Exception as e:
        print(f"Hook agent: LLM failed: {e}")
        return None

    data = extract_json(raw) or {}
    recent = list(recent_hook_types or [])[-1:]
    candidates = []
    for h in data.get("hooks", []) if isinstance(data.get("hooks"), list) else []:
        if not isinstance(h, dict):
            continue
        htype = str(h.get("type", "")).strip().upper()
        text = str(h.get("text", "")).strip().strip('"\u201c\u201d')
        if htype not in HOOK_TYPES or not _valid(text, grounding):
            continue
        score = clamp(h.get("score"), 1, 10, default=5)
        if htype in recent:
            score -= 0.5  # light nudge away from repeating the last hook type
        candidates.append({"type": htype, "text": text, "score": round(score, 2)})

    if not candidates:
        print("Hook agent: no valid hook candidates")
        return None
    candidates.sort(key=lambda c: c["score"], reverse=True)
    best = candidates[0]
    return {"text": best["text"], "type": best["type"], "score": best["score"],
            "candidates": candidates}
