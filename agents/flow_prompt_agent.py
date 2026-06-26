from dotenv import load_dotenv
load_dotenv()

def safe_invoke(prompt):
    import threading
    from langchain_groq import ChatGroq
    from langchain_google_genai import ChatGoogleGenerativeAI
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
        gemini = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=_os.getenv("GEMINI_API_KEY"))
        return gemini.invoke(prompt)
    except Exception:
        return ChatGroq(model="llama-3.1-8b-instant").invoke(prompt)


def extract_key_facts(script, topic):
    """Extract 2-3 concrete facts/numbers from the script for on-screen display."""
    prompt = f"""From this YouTube Shorts script, extract exactly 2-3 KEY FACTS that should appear as text on screen.

Topic: {topic}
Script: {script}

Rules:
- Must be SPECIFIC: numbers, percentages, prices, dates, names
- NOT vague: never "huge improvement" or "much better"
- Short: max 6 words each
- These will appear as floating text in the video

Examples of GOOD facts:
- "Battery: 40% bigger"
- "Price drops $100"  
- "0.5s faster autofocus"
- "Available Sept 2026"

Examples of BAD facts:
- "Much improved performance"
- "Better than before"
- "Amazing new features"

Return ONLY a Python list of 2-3 strings, nothing else:
["fact 1", "fact 2", "fact 3"]
"""
    try:
        response = safe_invoke(prompt).content.strip()
        import re, json
        match = re.search(r'\[.*?\]', response, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return [f"{topic} key update", "Watch till end"]


def generate_flow_prompts(topic, script, num_clips=3):
    # Extract real facts to show on screen
    key_facts = extract_key_facts(script, topic)
    facts_display = " | ".join(key_facts)

    prompt = f"""You are a cinematic director writing Google Flow / Veo 3 VIDEO prompts for YouTube Shorts.

Topic: {topic}
Script: {script}
Key facts to show ON SCREEN in Clip 2: {facts_display}

Generate exactly 3 cinematic video prompts:

CLIP 1 — VIRAL HOOK (first 8-10 seconds):
- Objective: Grab attention instantly, create curiosity
- Character: young Indian male tech presenter, shocked/curious expression
- Camera: handheld UGC close-up, fast punch-in zoom within first 2 seconds, shaky realistic movement
- Lighting: moody cinematic low-key, blue rim light on face
- Action: he reacts to something surprising about {topic}, leans forward, eyes wide, mouth slightly open
- Background: dark futuristic studio, glowing cyan holographic UI flickering

CLIP 2 — FACT REVEAL (middle 8-10 seconds):
- Objective: DELIVER THE ACTUAL INFORMATION — show real facts on screen, not just vibes
- Character: same presenter, confident explaining expression
- Camera: smooth gimbal medium shot, rack focus from holographic display to his face
- Lighting: dark studio with blue ambient, holographic screen glow on face
- Action: he points at large floating holographic text showing EXACTLY these facts: "{facts_display}" — each fact appears as bold glowing text on screen one by one as he explains
- Background: holographic data cards with the actual text "{facts_display}" floating and animating around him
- CRITICAL: The facts "{facts_display}" must be READABLE TEXT visible on the holographic display, not abstract visuals

CLIP 3 — CTA CLOSE (final 8-10 seconds):
- Objective: Drive follow/like action, emotional payoff
- Character: same presenter, direct eye contact, knowing smile
- Camera: slow push-in, turns to face camera directly
- Lighting: premium soft blue/cyan rim light, slightly warmer tone
- Action: he looks directly into camera, points at viewer, says "follow for more" gesture
- Background: holographic text "FOLLOW FOR MORE" floats in foreground, dark background with subtle glow

CHARACTER SEED (use EXACTLY this in ALL 3 clips):
"26-year-old Indian male, short neat black hair, light stubble, sharp jawline, dark navy crew-neck t-shirt, slim build, natural skin tone, no glasses"

For each clip write ONE rich paragraph. Always end with:
"9:16 vertical, 8 seconds, photorealistic, cinematic UGC style, consistent character: 26-year-old Indian male short black hair dark navy t-shirt"

Return EXACTLY:
CLIP 1: <paragraph>
CLIP 2: <paragraph>
CLIP 3: <paragraph>
"""

    response = safe_invoke(prompt).content.strip()

    clips = []
    for line in response.split("\n"):
        line = line.strip()
        if line.upper().startswith("CLIP"):
            parts = line.split(":", 1)
            if len(parts) == 2:
                clips.append(parts[1].strip())

    if len(clips) < 3:
        clips = [
            f"Viral hook — handheld UGC close-up of 26-year-old Indian male, short neat black hair, light stubble, dark navy t-shirt, shocked expression revealing surprising fact about {topic}, fast punch-in zoom first 2 seconds, dark futuristic studio cyan holographic panels, moody blue rim lighting, 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style, consistent character: 26-year-old Indian male short black hair dark navy t-shirt",
            f"Fact reveal — smooth gimbal medium shot of 26-year-old Indian male, short neat black hair, light stubble, dark navy t-shirt, points at large holographic display showing bold readable glowing text '{facts_display}', each fact appears one by one as floating text cards, confident explaining expression, rack focus display to face, dark studio blue ambient, 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style, consistent character: 26-year-old Indian male short black hair dark navy t-shirt",
            f"CTA close — slow push-in on 26-year-old Indian male, short neat black hair, light stubble, dark navy t-shirt, turns directly to camera with knowing smile, points at viewer, holographic text FOLLOW FOR MORE floats foreground, premium cyan rim light dark background, 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style, consistent character: 26-year-old Indian male short black hair dark navy t-shirt"
        ]

    return clips[:3]
