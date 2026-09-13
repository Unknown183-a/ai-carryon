# agents_cricket/ab_title_agent.py
"""
agents_cricket/ab_title_agent.py — Phase 3 for the Cricket Channel

Same idea as agents/ab_title_agent.py and agents_hindi/ab_title_agent.py:
generate several title variations using different psychological patterns,
score each, pick the winner, log every test so pattern win-rates can be
tracked over time.

Cricket-specific differences:
  - Patterns are built around match drama (chase, collapse, record, milestone)
    instead of generic curiosity/urgency framing
  - Titles are written in Hindi/Hinglish, matching agents_cricket/script_agent.py's
    Devanagari script output and the Sarvam hi-IN voice
  - Logs to Firestore via agents_cricket.database (not the SQLite agents.database
    used by English/Hindi), since the whole cricket channel lives in Firestore

Usage:
    from agents_cricket.ab_title_agent import get_best_title_cricket
    result = get_best_title_cricket(match_summary, script, teams=["India", "Australia"])
    winning_title = result["winner"]["title"]
"""

import re
from datetime import datetime, timezone

PATTERNS_CRICKET = {
    "chase_drama":  "Chase/run-chase drama par focus karo: 'Aakhri Over Mein...', 'Last Ball Thriller'",
    "record":       "Record/milestone highlight karo: 'Naya Record Bana Diya', 'History Rach Di'",
    "collapse":     "Shocking collapse/upset par focus: 'Sab Kuch Bikhar Gaya', 'Kisi Ko Yakeen Nahi Hua'",
    "number":       "Number-led: '3 Records Ek Match Mein', 'Sirf 10 Gendon Mein'",
    "player_hero":  "Ek player ko hero banao: '<Player> Ne Akele Jita Diya', 'Yeh Innings Kabhi Nahi Bhoologey'",
    "question":     "Seedha sawal: 'Kya Yeh Best Innings Thi?', 'Kaise Jeeta Yeh Match?'",
    "warning":      "Miss mat karo wala urgency: 'Yeh Dekhe Bina Mat Jaana', 'Abhi Dekho'",
    "contrarian":   "Expectation ko ulta karo: 'Kisi Ne Nahi Socha Tha Yeh Hoga'",
}

PATTERN_EXAMPLES_CRICKET = {
    "chase_drama":  "आखिरी ओवर में हुआ ऐसा ड्रामा 🔥",
    "record":       "विराट ने बना दिया नया रिकॉर्ड 🏆",
    "collapse":     "5 विकेट सिर्फ 10 रनों में सब हैरान 😱",
    "number":       "3 रिकॉर्ड सिर्फ एक मैच में 🏏",
    "player_hero":  "बुमराह ने अकेले जिता दिया मैच 💪",
    "question":     "क्या ये अब तक की सबसे बड़ी पारी थी? 🤔",
    "warning":      "ये कैच देखे बिना मत जाना 🚨",
    "contrarian":   "किसी ने नहीं सोचा था ऐसा होगा 👀",
}


def safe_invoke(prompt):
    """Same Groq-first, Gemini-fallback pattern used across agents_cricket/."""
    import threading
    from langchain_groq import ChatGroq
    import os as _os

    result = [None]

    def try_groq():
        try:
            result[0] = ChatGroq(model="openai/gpt-oss-120b").invoke(prompt)
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
            google_api_key=_os.getenv("GEMINI_API_KEY"),
        )
        return gemini.invoke(prompt)
    except Exception:
        return ChatGroq(model="openai/gpt-oss-20b").invoke(prompt)


def generate_title_variation_cricket(match_label, script, pattern_name, pattern_instruction):
    example = PATTERN_EXAMPLES_CRICKET.get(pattern_name, "")
    prompt = f"""Aap ek cricket YouTube Shorts title expert hain.

Match: {match_label}
Pattern: {pattern_name}
Pattern instruction: {pattern_instruction}
Is style ka example (apna match ke hisaab se adapt karo, copy mat karo): "{example}"

Script (isi moment ke baare mein hai):
{script}

Is match/moment ke liye ek title likho {pattern_name} pattern follow karte hue.
Rules:
- 60 characters se kam, Hindi/Hinglish mein
- Actual team/player ka naam mention hona chahiye — generic mat rakho
- Pattern STRICTLY follow karo
- End mein 1 relevant emoji (🏏🔥😱🏆 jaisa)
- Kabhi shuru mat karo: Crazy, Insane, Amazing, Unbelievable, Shocking se

Sirf title return karo, kuch aur nahi."""

    try:
        response = safe_invoke(prompt).content.strip()
        title = response.strip('"\'').strip()
        if len(title) > 70:
            title = title[:67] + "..."
        return title
    except Exception:
        return f"{match_label[:50]} 🏏"


def score_title_cricket(title, match_label):
    prompt = f"""Match: {match_label}
Title to score: "{title}"

Score this cricket YouTube Shorts title 1-10 based on:
1. Drama/curiosity gap — worth 3 points
2. Specificity (names real teams/players) — worth 2 points
3. Emotional trigger — worth 2 points
4. Click-worthiness for Indian cricket audience — worth 2 points
5. Length (under 60 chars ideal) — worth 1 point

Return ONLY a number 1-10."""

    try:
        response = safe_invoke(prompt).content.strip()
        match = re.search(r'\b([1-9]|10)\b', response)
        if match:
            return int(match.group())
    except Exception:
        pass
    return 5


def get_best_title_cricket(match_summary, script, teams=None, num_variations=3):
    """match_summary: text summary from research_agent.get_summary_for_topic().
    teams: optional list of team names (from structured["teams"]) used to
    build a short match_label for prompting — falls back to the first line
    of match_summary if not given."""
    import random

    match_label = " vs ".join(teams) if teams else match_summary.splitlines()[0][:60]

    selected_patterns = random.sample(list(PATTERNS_CRICKET.items()), min(num_variations, len(PATTERNS_CRICKET)))

    variations = []
    for pattern_name, pattern_instruction in selected_patterns:
        title = generate_title_variation_cricket(match_label, script, pattern_name, pattern_instruction)
        score = score_title_cricket(title, match_label)
        variations.append({"title": title, "pattern": pattern_name, "score": score})
        print(f"  [Cricket/{pattern_name}] score={score} — {title}")

    variations.sort(key=lambda x: x["score"], reverse=True)
    winner = variations[0]

    result = {
        "winner": winner,
        "variations": variations,
        "match_label": match_label,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    _log_result_cricket(result)
    return result


def _log_result_cricket(result):
    """Log to Firestore via agents_cricket.database — kept fully separate
    from English/Hindi's SQLite AB log."""
    try:
        from agents_cricket.database import db
        if db is None:
            return
        winner = result.get("winner", {})
        db.log_ab_test(
            topic=result.get("match_label", ""),
            winner_title=winner.get("title", ""),
            winner_pattern=winner.get("pattern", ""),
            winner_score=winner.get("score", 0),
            all_variations=result.get("variations", []),
            generated_at=result.get("generated_at"),
        )
    except Exception as e:
        print(f"Cricket AB-test Firestore log error: {e}")


if __name__ == "__main__":
    import sys
    label = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "India vs Australia"
    script = "Aakhri over mein Bumrah ne teen wickets le liye aur match palat diya..."

    print(f"\nGenerating cricket title variations for: {label}\n")
    result = get_best_title_cricket(script, script, teams=[label])

    print(f"\n🏆 Winner: {result['winner']['title']}")
    print(f"   Pattern: {result['winner']['pattern']} | Score: {result['winner']['score']}/10")
