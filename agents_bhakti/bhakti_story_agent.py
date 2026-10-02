# agents_bhakti/bhakti_story_agent.py
"""Hook + Story agent (spec section 4): short-form structure in Devanagari Hindi."""

import re
from agents_bhakti.model_invoke_agent_bhakti import safe_invoke

MIN_WORDS, MAX_WORDS = 70, 95

STRUCTURE = """Structure (about 40 seconds spoken):
1. HOOK (0-3s): one curiosity line, no unnecessary introduction, no misleading claim
2. SETUP (3-10s): who/where
3. CONFLICT / STORY (10-20s): the problem or test
4. DIVINE / EMOTIONAL MOMENT (20-30s): the peak
5. RESOLUTION (30-40s): outcome
6. ENDING (40-45s): calm blessing + short follow CTA (Jai Shri Krishna / Har Har Mahadev / Jai Shri Ram etc. to match the deity)"""


def _devanagari_ratio(text):
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if "\u0900" <= c <= "\u097f") / len(letters)


def generate_story(topic, research, comparison_insights=None, feedback=None):
    """Returns the narration script (plain spoken text, one sentence per line)."""
    competitor = ""
    if comparison_insights and not comparison_insights.get("error"):
        recs = comparison_insights.get("recommendations", [])
        competitor = f"Competitor hint: ideal duration ~{comparison_insights.get('competitor_avg_duration_seconds', 40)}s. {'; '.join(recs[:2])}\n"
    fb = f"\nA previous draft was rejected. Fix this: {feedback}\n" if feedback else ""
    prompt = f"""Write a YouTube Shorts devotional narration in DEVANAGARI HINDI.
Topic: {topic}
Research: {research}
{competitor}{fb}
{STRUCTURE}

Rules:
- Exactly {MIN_WORDS}-{MAX_WORDS} words. Short sentences, max 10 words each, ONE sentence per line.
- Warm, reverent, natural spoken Hindi. No jokes, no clickbait, no disrespect to any deity.
- Emotion should escalate toward the divine moment.
- Do not repeat the same phrase. No labels (Hook:, CTA:), no stage directions, no emojis.
- Only authentic story content from the research; invent nothing.
Return ONLY the narration lines."""
    script = safe_invoke(prompt).content.strip()
    script = re.sub(r"^\s*(?:[-*\d.]+\s*)", "", script, flags=re.MULTILINE)

    for attempt in range(2):
        n = len(script.split())
        if n >= MIN_WORDS:
            break
        script = safe_invoke(
            f"This Hindi devotional narration has only {n} words. Expand it to about 80 words, "
            f"same Devanagari Hindi, same tone, one sentence per line, add one devotional detail. "
            f"Return only the script.\n\n{script}"
        ).content.strip()

    words = script.split()
    if len(words) > MAX_WORDS + 5:
        # trim on a sentence boundary rather than mid-sentence
        kept, count = [], 0
        for line in [l for l in script.splitlines() if l.strip()]:
            c = len(line.split())
            if count + c > MAX_WORDS:
                break
            kept.append(line)
            count += c
        script = "\n".join(kept) or " ".join(words[:MAX_WORDS])
    print(f"[bhakti_story] {len(script.split())} words, devanagari ratio {_devanagari_ratio(script):.2f}")
    return script
