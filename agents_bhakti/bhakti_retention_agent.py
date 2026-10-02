# agents_bhakti/bhakti_retention_agent.py
"""Retention agent (spec section 5): heuristic checks + LLM scoring."""

import json
import os
import re

from agents_bhakti.model_invoke_agent_bhakti import safe_invoke
from agents_bhakti.bhakti_story_agent import _devanagari_ratio

THRESHOLD = float(os.environ.get("BHAKTI_RETENTION_THRESHOLD", "7"))
SCORE_KEYS = ["hook_score", "story_score", "emotional_score", "visual_score", "ending_score"]


def heuristic_checks(script):
    lines = [l.strip() for l in script.splitlines() if l.strip()]
    words = script.split()
    problems = []
    if len(words) < 60 or len(words) > 105:
        problems.append(f"length {len(words)} words (target 70-95)")
    if lines and len(lines[0].split()) > 16:
        problems.append("hook line too long")
    long_sents = [l for l in lines if len(l.split()) > 14]
    if long_sents:
        problems.append("some sentences exceed 14 words")
    # repetition: any 3-word phrase appearing more than once
    tri = [" ".join(words[i:i + 3]) for i in range(len(words) - 2)]
    if len(tri) != len(set(tri)):
        problems.append("repeated phrases")
    if _devanagari_ratio(script) < 0.6:
        problems.append("script is not mainly Devanagari Hindi")
    if re.search(r"(?i)\b(hook|cta)\s*:", script):
        problems.append("contains labels")
    return problems


def evaluate_retention(script, research=None):
    problems = heuristic_checks(script)
    result = {k: 7 for k in SCORE_KEYS}
    try:
        prompt = f"""Rate this Hindi devotional Shorts narration 1-10 for each key.
Return ONLY JSON: {{"hook_score":n,"story_score":n,"emotional_score":n,"visual_score":n,"ending_score":n,"feedback":"one sentence on the biggest fix"}}
Criteria: strong first 2-3 seconds; no unnecessary intro; story keeps progressing; emotional escalation;
good visual opportunities; no repetition; strong ending; right length.

{script}"""
        raw = safe_invoke(prompt, temperature=0.2).content
        data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        for k in SCORE_KEYS:
            result[k] = float(data.get(k, 7))
        result["feedback"] = data.get("feedback", "")
    except Exception as e:
        print(f"[bhakti_retention] LLM scoring skipped: {e}")
        result["feedback"] = ""
    avg = sum(result[k] for k in SCORE_KEYS) / len(SCORE_KEYS)
    result["average"] = round(avg, 2)
    result["problems"] = problems
    result["approved"] = avg >= THRESHOLD and not problems
    if problems:
        result["feedback"] = (result.get("feedback", "") + " Problems: " + "; ".join(problems)).strip()
    return result
