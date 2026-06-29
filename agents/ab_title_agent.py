"""
agents/ab_title_agent.py — Phase 3: A/B Title Tester

For every video topic, generates 3 title variations using different
psychological patterns, scores each one, and returns the best.

Also logs results to output/title_ab_log.json so we can track
which patterns perform best over time.

Usage:
    from agents.ab_title_agent import get_best_title
    result = get_best_title(topic, script)
    best_title = result["winner"]["title"]
"""

import os
import json
import re
from datetime import datetime, timezone

LOG_FILE = "output/title_ab_log.json"

PATTERNS = {
    "curiosity":   "Start with 'Did You Know', 'Here's Why', or 'The Reason' — spark curiosity gap",
    "urgency":     "Use urgency words: 'This Changes Everything', 'Stop Doing This', 'Act Now'",
    "revelation":  "Reveal a secret: 'Nobody Told You', 'The Hidden Truth', 'They Don't Want You to Know'",
    "number":      "Use a specific number: '5 Reasons', '3 Things', 'Top 7' — numbers stop scrolling",
    "question":    "Ask a direct question: 'Is This the Future?', 'Can AI Really...?', 'What Happens When'",
    "warning":     "Give a warning: 'Warning:', 'Before You Try', 'Don't Make This Mistake'",
    "contrarian":  "Challenge common belief: 'Everyone Is Wrong About', 'Stop Believing This', 'The Opposite Is True'",
    "personal":    "Make it personal: 'This Affects You', 'You Need To Know', 'Your Phone Is Doing This'",
}

SCORING_CRITERIA = """
Score this YouTube Shorts title from 1-10 based on:
1. Curiosity gap (does it make you NEED to watch?) — worth 3 points
2. Specificity (concrete details, not vague) — worth 2 points  
3. Emotional trigger (fear, excitement, surprise, urgency) — worth 2 points
4. Click-worthiness for tech/AI audience — worth 2 points
5. Length (under 60 chars is ideal) — worth 1 point

Return ONLY a number 1-10.
"""


def safe_invoke(prompt):
    import threading
    from langchain_groq import ChatGroq
    import os as _os

    result = [None]
    def try_groq():
        try:
            result[0] = ChatGroq(model="llama-3.3-70b-versatile").invoke(prompt)
        except Exception:
            pass

    t = threading.Thread(target=try_groq)
    t.start()
    t.join(timeout=20)
    if result[0] is not None:
        return result[0]

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        gemini = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=_os.getenv("GEMINI_API_KEY")
        )
        return gemini.invoke(prompt)
    except Exception:
        return ChatGroq(model="llama-3.1-8b-instant").invoke(prompt)


PATTERN_EXAMPLES = {
    "curiosity":  "Did You Know Claude AI Just Replaced This? 🤯",
    "urgency":    "This Claude AI Update Changes Everything Now ⚡",
    "revelation": "Nobody Told You Claude AI Can Do This 🔥",
    "number":     "3 Reasons Claude AI Beats ChatGPT in 2026 🏆",
    "question":   "Can Claude AI Really Beat Every Chatbot? 🤔",
    "warning":    "Warning: Stop Using ChatGPT Before Watching This 🚨",
    "contrarian": "Everyone Is Wrong About Claude AI — Here's Why 💡",
    "personal":   "This Claude AI Update Affects You Right Now 👀",
}

def generate_title_variation(topic, script, pattern_name, pattern_instruction):
    """Generate one title variation using a specific pattern."""
    example = PATTERN_EXAMPLES.get(pattern_name, "")
    prompt = f"""You are a YouTube Shorts title expert for a tech/AI channel.

Topic: {topic}
Pattern: {pattern_name}
Pattern instruction: {pattern_instruction}
Example of this pattern style (adapt to YOUR topic, don't copy): "{example}"

Write ONE title about "{topic}" following the {pattern_name} pattern.
Rules:
- Under 60 characters
- Must mention the actual topic concept
- Follow the pattern STRICTLY — the example shows the style
- Add 1 relevant emoji at the end
- Do NOT just repeat the topic as-is

Return ONLY the title, nothing else."""

    try:
        response = safe_invoke(prompt).content.strip()
        # Clean up
        title = response.strip('"\'').strip()
        # Enforce length
        if len(title) > 70:
            title = title[:67] + "..."
        return title
    except Exception:
        return f"{topic[:50]} 🤖"


def score_title(title, topic):
    """Score a title 1-10 for click-through potential."""
    prompt = f"""Topic: {topic}
Title to score: "{title}"

{SCORING_CRITERIA}"""

    try:
        response = safe_invoke(prompt).content.strip()
        # Extract number
        match = re.search(r'\b([1-9]|10)\b', response)
        if match:
            return int(match.group())
    except Exception:
        pass
    return 5


def get_best_title(topic, script, num_variations=3):
    """
    Generate multiple title variations, score them, return the best.

    Returns:
    {
        "winner": {"title": "...", "pattern": "...", "score": 9},
        "variations": [
            {"title": "...", "pattern": "...", "score": 8},
            {"title": "...", "pattern": "...", "score": 7},
            {"title": "...", "pattern": "...", "score": 6},
        ],
        "topic": "...",
        "generated_at": "..."
    }
    """
    import random

    # Pick random patterns for variety
    selected_patterns = random.sample(list(PATTERNS.items()), min(num_variations, len(PATTERNS)))

    variations = []
    for pattern_name, pattern_instruction in selected_patterns:
        title = generate_title_variation(topic, script, pattern_name, pattern_instruction)
        score = score_title(title, topic)
        variations.append({
            "title": title,
            "pattern": pattern_name,
            "score": score,
        })
        print(f"  [{pattern_name}] score={score} — {title}")

    # Sort by score
    variations.sort(key=lambda x: x["score"], reverse=True)
    winner = variations[0]

    result = {
        "winner": winner,
        "variations": variations,
        "topic": topic,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    # Log for learning
    _log_result(result)

    return result


def get_best_pattern_from_history():
    """
    Analyse past A/B results to find which pattern wins most often.
    Returns pattern name with highest average score.
    """
    if not os.path.exists(LOG_FILE):
        return None

    try:
        with open(LOG_FILE, "r") as f:
            logs = json.load(f)

        pattern_scores = {}
        for entry in logs:
            winner = entry.get("winner", {})
            pattern = winner.get("pattern")
            score = winner.get("score", 0)
            if pattern:
                if pattern not in pattern_scores:
                    pattern_scores[pattern] = []
                pattern_scores[pattern].append(score)

        if not pattern_scores:
            return None

        # Average score per pattern
        avg_scores = {
            p: sum(scores) / len(scores)
            for p, scores in pattern_scores.items()
            if len(scores) >= 2  # need at least 2 data points
        }

        if not avg_scores:
            return None

        best = max(avg_scores, key=avg_scores.get)
        print(f"Best pattern from history: {best} (avg score: {avg_scores[best]:.1f})")
        return best

    except Exception as e:
        print(f"History analysis error: {e}")
        return None


def _log_result(result):
    """Append result to SQLite DB and JSON log file."""
    # Write to SQLite (primary)
    try:
        from agents.database import db
        winner = result.get("winner", {})
        db.log_ab_test(
            topic=result.get("topic", ""),
            winner_title=winner.get("title", ""),
            winner_pattern=winner.get("pattern", ""),
            winner_score=winner.get("score", 0),
            all_variations=result.get("variations", []),
            generated_at=result.get("generated_at"),
        )
    except Exception as e:
        print(f"DB log error: {e}")

    # Write to JSON (backup)
    os.makedirs("output", exist_ok=True)
    logs = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                logs = json.load(f)
        except Exception:
            logs = []

    logs.append(result)
    logs = logs[-200:]

    with open(LOG_FILE, "w") as f:
        json.dump(logs, f, indent=2)


if __name__ == "__main__":
    import sys
    topic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Claude AI beats ChatGPT"
    script = "Claude AI just released a new update that changes everything about how we use AI assistants..."

    print(f"\nGenerating title variations for: {topic}\n")
    result = get_best_title(topic, script)

    print(f"\n🏆 Winner: {result['winner']['title']}")
    print(f"   Pattern: {result['winner']['pattern']} | Score: {result['winner']['score']}/10")
    print(f"\nAll variations:")
    for v in result["variations"]:
        print(f"  {'🥇' if v == result['winner'] else '  '} [{v['score']}/10] {v['title']} ({v['pattern']})")
