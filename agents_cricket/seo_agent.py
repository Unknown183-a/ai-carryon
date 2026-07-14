# agents_cricket/seo_agent.py
from dotenv import load_dotenv
load_dotenv()

from agents_cricket.script_agent import safe_invoke

PATTERNS = [
    "Shocking collapse: 'X's shocking collapse against Y'",
    "Record-breaking: \"Player's record-breaking knock\"",
    "Chase drama: 'The chase that stunned everyone'",
    "Number-led: '3 records broken in one match'",
]


def generate_cricket_seo(match_summary, script):
    import random
    pattern = random.choice(PATTERNS)

    prompt = f"""You are a YouTube SEO expert for a cricket recap Shorts channel.

Match data:
{match_summary}

Script:
{script}

STRICT RULES:
- Title pattern style to use: {pattern}
- Title under 60 characters, must reference the actual teams/players — not generic
- Never start with: Crazy, Insane, Amazing, Unbelievable, Shocking
- Description: 3-4 sentences, original, ends with "Like & Subscribe for daily cricket recaps! 🏏"
- 15 hashtags: mix of broad (#Cricket #Shorts) + team/player specific + trending

Return in EXACTLY this format, no extra text:

TITLE: <title>
DESCRIPTION: <description>
HASHTAGS: <15 hashtags space-separated>
"""
    response = safe_invoke(prompt).content

    title, description, hashtags = "", "", ""
    for line in response.split("\n"):
        line = line.strip()
        if line.upper().startswith("TITLE:"):
            title = line.split(":", 1)[1].strip().strip('"')
        elif line.upper().startswith("DESCRIPTION:"):
            description = line.split(":", 1)[1].strip()
        elif line.upper().startswith("HASHTAGS:"):
            hashtags = line.split(":", 1)[1].strip()

    hashtag_list = [h for h in hashtags.split() if h.startswith("#")]
    return {"title": title, "description": description, "hashtags": hashtag_list}
