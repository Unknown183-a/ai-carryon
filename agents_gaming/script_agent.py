# agents_gaming/script_agent.py
from dotenv import load_dotenv
load_dotenv()

# Reuses the same Groq-first/Gemini-fallback invoke helper as the English
# channel — gaming scripts are English, same as agents/script_agent.py.
from agents.model_invoke_agent_english import safe_invoke


def create_gaming_script(clip_summary, structured=None):
    """One-clip hype/commentary script, ~20-35s of speech (roughly 55-90
    words at the pace used in agents/voice_agent.py). Written to sit OVER
    the real Twitch clip footage, not narrate a static image."""
    structured = structured or {}
    game = structured.get("game", "")
    broadcaster = structured.get("broadcaster", "")

    context_line = ""
    if broadcaster:
        context_line = f"This clip is from streamer {broadcaster}"
        if game:
            context_line += f" playing {game}."
        else:
            context_line += "."

    prompt = f"""You are a hype gaming commentator writing a YouTube Shorts voiceover
script that plays OVER a real gameplay clip (the viewer is watching the clip
while you talk, not looking at you).

Clip data:
{clip_summary}
{context_line}

STRICT RULES:
- 20-35 seconds of speech — total word count: 55-90 words
- First line is a HOOK about what's about to happen in the clip ("Watch what
  happens when...", "Nobody expected this...", "This is the play that...")
- Do NOT describe the clip play-by-play like a boring recap — react to it
  like a hype gaming commentator would, short punchy sentences
- Mention the streamer's name and the game naturally, once each
- Last line: a short call to follow for more gaming clips
- Plain text only — no stage directions, no labels like "Hook:", no emojis,
  no hashtags

Return ONLY the script text, nothing else."""

    response = safe_invoke(prompt)
    script = response.content.strip()

    words = script.split()
    for _ in range(2):
        if len(words) >= 55:
            break
        prompt2 = (
            f"This script is only {len(words)} words. Expand it to ~75 words.\n"
            f"Keep the same hook and single-clip focus — do not add a second clip "
            f"or a full recap.\n\nScript:\n{script}"
        )
        script = safe_invoke(prompt2).content.strip()
        words = script.split()

    if len(words) > 90:
        script = " ".join(words[:90])

    return script
