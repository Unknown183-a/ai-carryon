# agents_gaming/script_quality_agent.py
"""
Gaming V2 Phase 5 — a script is only good enough to voice if hook strength,
naturalness, originality, accuracy and moment relevance are ALL above the
threshold (spec: > 7). Otherwise the caller regenerates it with this agent's
feedback; a weak script is never uploaded just because generation succeeded.

Two layers:
  1. Deterministic checks (no LLM): invented numbers cap accuracy, repeated
     AI phrases cap naturalness, near-duplicate of a recent script caps
     originality. These cannot be talked around by a lenient judge.
  2. LLM judge: scores the five dimensions plus pacing / payoff / repetition
     / AI-pattern notes.

If the judge call itself fails (provider outage, unparsable reply) the script
is flagged `unjudged` and does NOT pass (fail closed) — an unreviewed script
is never published; the scheduler just skips this cycle and the next cron run
tries again. GAMING_ALLOW_UNJUDGED=1 restores the old fail-open behaviour.
"""
import difflib
import os

from agents_gaming.commentary_agent import grounding_text
from agents_gaming.v2_utils import (
    clamp, extract_json, repeated_ai_phrases, ungrounded_numbers,
)

# Spec Phase 5: every score must be > 7. Env-tunable (e.g. 6.5 while tuning).
MIN_SCORE = float(os.getenv("GAMING_SCRIPT_MIN_SCORE", "7"))
SCORE_KEYS = ("hook", "naturalness", "originality", "accuracy", "moment_relevance")
SIMILARITY_LIMIT = 0.6
# The judge must score on ONE scale. The router's Groq budget runs out mid-run
# and silently hands later calls to Gemini, which scores far harsher — so the
# same script could pass or fail depending on call order. Pin the judge to
# Gemini (set GAMING_JUDGE_PROVIDER=router to use the normal router again).
JUDGE_PROVIDER = os.getenv("GAMING_JUDGE_PROVIDER", "gemini").lower()
# The router's shared Gemini timeout (15s) is too short for a thinking model
# reading a long judging prompt: three timeouts in a row trip the circuit
# breaker and kill Gemini for the whole run. The judge gets its own budget.
JUDGE_TIMEOUT_SECONDS = int(os.getenv("GAMING_JUDGE_TIMEOUT_SECONDS", "45"))
# If the judge can't produce scores (outage / unparsable reply) the script is
# UNJUDGED. Default: do not publish it. Set GAMING_ALLOW_UNJUDGED=1 to opt out.
ALLOW_UNJUDGED = os.getenv("GAMING_ALLOW_UNJUDGED", "0") == "1"
JUDGE_PARSE_RETRIES = 1


def _invoke_judge(prompt):
    import agents.model_invoke_agent_english as llm
    if JUDGE_PROVIDER == "gemini" and not llm._provider_dead("gemini"):
        print("[gaming judge] Trying Gemini")
        resp, err = llm._run_with_timeout(lambda: llm._get_gemini().invoke(prompt), JUDGE_TIMEOUT_SECONDS)
        llm._record_outcome("gemini", resp is not None)
        if resp is not None:
            return llm._normalize_response(resp)
        print(f"[gaming judge] Gemini failed: {err} — falling back to the router")
    return llm.safe_invoke(prompt)


def _similarity(script, recent_scripts):
    best = 0.0
    for r in recent_scripts or []:
        best = max(best, difflib.SequenceMatcher(None, script.lower(), r.lower()).ratio())
    return best


def _judge_prompt(script, moment, hook, summary):
    return f"""You are a strict editor for a gaming YouTube Shorts channel. Judge this voiceover
script, which plays over real gameplay.

Moment analysis (ground truth):
Game: {moment.get('game', '')} | Type: {moment.get('moment_type', '')}
What happened: {moment.get('what_happened', '')}
Setup: {moment.get('setup', '')} | Payoff: {moment.get('payoff', '')}
Clip data:
{summary}

Script:
\"\"\"
{script}
\"\"\"

Score 1-10 (be harsh; 8+ means a human creator could have said it):
- hook: does the first line stop a scroll without giving the payoff away?
- naturalness: sounds like a person talking, not an AI announcer (varied rhythm, no cliches)
- originality: a specific angle on THIS moment, not a generic hype template
- accuracy: every claim is supported by the moment analysis / clip data
- moment_relevance: it is about what actually happens in the clip
Also list concrete problems (pacing, weak payoff, repetition, AI-sounding lines).

Reply with ONLY this JSON:
{{"hook": 0, "naturalness": 0, "originality": 0, "accuracy": 0, "moment_relevance": 0,
  "issues": ["..."], "fix": "one sentence telling the writer what to change"}}"""


def evaluate_script(script, moment, hook=None, summary="", recent_scripts=None):
    """Returns {'passed': bool, 'scores': {...}, 'issues': [...], 'feedback': str,
    'judge_skipped': bool}."""
    scores = {k: None for k in SCORE_KEYS}
    issues, fix = [], ""
    judge_skipped = False

    try:
        data = {}
        for _ in range(1 + JUDGE_PARSE_RETRIES):          # retry only an unparsable reply
            raw = _invoke_judge(_judge_prompt(script, moment, hook, summary)).content
            data = extract_json(raw) or {}
            for k in SCORE_KEYS:
                scores[k] = clamp(data.get(k), 1, 10, default=None)
            if any(v is not None for v in scores.values()):
                break
        if all(v is None for v in scores.values()):
            judge_skipped = True
        issues = [str(i) for i in data.get("issues", [])] if isinstance(data.get("issues"), list) else []
        fix = str(data.get("fix", "")).strip()
    except Exception as e:
        print(f"Script quality: judge unavailable ({e}) — deterministic checks only")
        judge_skipped = True

    # Deterministic layer — caps the judge's scores.
    bad_nums = ungrounded_numbers(script, grounding_text(moment, summary, hook))
    if bad_nums:
        scores["accuracy"] = min(scores["accuracy"] if scores["accuracy"] is not None else 10, 4)
        issues.append("states numbers not in the clip data: " + ", ".join(bad_nums))
    rep = repeated_ai_phrases(script, recent_scripts)
    if rep:
        scores["naturalness"] = min(scores["naturalness"] if scores["naturalness"] is not None else 10, 5)
        issues.append("overused AI-sounding phrases: " + ", ".join(rep))
    sim = _similarity(script, recent_scripts)
    if sim >= SIMILARITY_LIMIT:
        scores["originality"] = min(scores["originality"] if scores["originality"] is not None else 10, 4)
        issues.append(f"too similar to a recent script ({sim:.0%})")

    # Unscored dimensions (judge skipped) pass; scored ones must be > MIN_SCORE.
    failing = [k for k, v in scores.items() if v is not None and not v > MIN_SCORE]
    passed = not failing
    if judge_skipped and not ALLOW_UNJUDGED:
        # Never publish a script nobody reviewed just because the reviewer was down.
        passed = False
        issues.append("quality judge unavailable — script was not reviewed")
    feedback = fix or ("; ".join(issues) if issues else "")
    if failing and not feedback:
        feedback = "raise: " + ", ".join(failing)

    return {
        "passed": passed,
        "scores": scores,
        "failing": failing,
        "issues": issues,
        "feedback": feedback,
        "judge_skipped": judge_skipped,
        "unjudged": judge_skipped,
    }
