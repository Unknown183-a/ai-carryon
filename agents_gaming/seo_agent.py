# agents_gaming/seo_agent.py
from dotenv import load_dotenv
load_dotenv()

from agents.model_invoke_agent_english import safe_invoke

PATTERN_PROMPTS = {
    "reaction": "Frame it around reaction/disbelief: 'You Won't Believe', 'No Way He Did This'",
    "clutch": "Frame it as a clutch/skill moment: 'Insane Clutch', 'Clean Play'",
    "funny": "Frame it as a funny/fail moment: 'This Went Wrong Fast', 'Instant Regret'",
    "record": "Frame it as a milestone/record moment: 'New Record', 'First Time Ever'",
    "question": "Ask a question: 'How Is This Legal?', 'Did You See This?'",
}


def generate_seo(structured, script, use_pattern=None):
    game = structured.get("game", "")
    broadcaster = structured.get("broadcaster", "")
    pattern_instruction = PATTERN_PROMPTS.get(
        use_pattern,
        "Use a punchy gaming-clip title style — avoid generic words like 'Amazing' or 'Crazy' alone"
    )

    prompt = f"""Write YouTube Shorts metadata for a gaming highlight clip video.

Streamer: {broadcaster}
Game: {game}
Script (voiceover over the clip):
{script}

{pattern_instruction}

Return exactly three lines, nothing else:
TITLE: <under 60 characters, no emojis, must include the game or streamer name>
DESCRIPTION: <1-2 sentences, plain text>
HASHTAGS: <5-8 space-separated hashtags, gaming + game-specific + streamer if relevant>"""

    response = safe_invoke(prompt)
    text = response.content.strip()

    title, description, hashtags = "", "", []
    for line in text.splitlines():
        line = line.strip()
        if line.upper().startswith("TITLE:"):
            title = line.split(":", 1)[1].strip()
        elif line.upper().startswith("DESCRIPTION:"):
            description = line.split(":", 1)[1].strip()
        elif line.upper().startswith("HASHTAGS:"):
            hashtags = line.split(":", 1)[1].strip().split()

    if not title:
        title = f"{broadcaster} — {game} Highlight".strip(" —")[:60]
    if not hashtags:
        hashtags = ["#Gaming", "#Shorts", "#Clips"]
        if game:
            hashtags.append("#" + game.replace(" ", ""))

    return title, description, hashtags
