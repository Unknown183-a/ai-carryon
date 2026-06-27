from dotenv import load_dotenv
load_dotenv()

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
        gemini = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=_os.getenv("GEMINI_API_KEY"))
        return gemini.invoke(prompt)
    except Exception:
        return ChatGroq(model="llama-3.1-8b-instant").invoke(prompt)


def extract_key_facts(script, topic):
    """Extract 2-3 concrete facts/numbers from the script."""
    prompt = f"""From this YouTube Shorts script, extract exactly 2-3 KEY FACTS for on-screen display.

Topic: {topic}
Script: {script}

Rules:
- SPECIFIC: numbers, percentages, prices, dates
- Short: max 6 words each
- These appear as floating text in the video

Good examples: "Battery: 40% bigger", "Price drops $100", "Available Sept 2026"
Bad examples: "Much improved", "Better than before"

Return ONLY a Python list:
["fact 1", "fact 2", "fact 3"]
"""
    try:
        import re, json
        response = safe_invoke(prompt).content.strip()
        match = re.search(r'\[.*?\]', response, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return [f"{topic} — key update", "Watch till end"]


def generate_flow_prompts(topic, script, num_clips=3):
    key_facts = extract_key_facts(script, topic)
    facts_display = " | ".join(key_facts)

    # First extract the narrative arc from the script
    prompt = f"""You are a cinematic director creating a 3-part continuous story for YouTube Shorts.

Topic: {topic}
Script: {script}
Key facts to show on screen in Clip 2: {facts_display}

IMPORTANT: These 3 clips are ONE continuous video. The presenter speaks CONTINUOUSLY across all 3 clips like one unbroken conversation. Each clip picks up exactly where the previous one left off.

CHARACTER (SAME in ALL 3 clips — never change):
"26-year-old Indian male, short neat black hair, light stubble, sharp jawline, dark navy crew-neck t-shirt, slim build, natural skin tone, no glasses"

CLIP 1 — HOOK (opens the story, creates curiosity):
- Presenter starts speaking directly to camera with shocking/curious expression
- He OPENS A LOOP — raises a question or teases what's coming: "Did you know {topic} just changed everything? Here's what nobody is telling you..."
- He does NOT answer yet — leaves viewer wanting more
- Camera: handheld UGC close-up, fast punch-in zoom in first 2 seconds
- Lighting: moody blue rim light, dark futuristic studio
- Ends mid-sentence or with "and here's the thing..."
- 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style

CLIP 2 — FACT REVEAL (continues directly from Clip 1, delivers the answer):
- Presenter CONTINUES speaking as if no cut happened — picks up exactly where Clip 1 ended
- He reveals the actual facts: bold readable glowing text "{facts_display}" appears on holographic display one by one as he points and explains each
- He gestures at the floating text cards showing "{facts_display}" — viewer can READ the facts
- Camera: smooth gimbal medium shot, rack focus from display to face
- Lighting: dark studio blue ambient, holographic glow on face
- Ends with "and that's not even the best part..."
- 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style

CLIP 3 — PAYOFF + CTA (closes the loop, drives action):
- Presenter CONTINUES from Clip 2 — delivers the final punchline or most surprising fact
- CLOSES THE LOOP started in Clip 1 — answers the original question fully
- Looks directly into camera: "Now you know why everyone is talking about this. Follow for more."
- Camera: slow push-in, turns directly to face camera
- Lighting: premium soft cyan rim light, slightly warmer
- Holographic text "FOLLOW FOR MORE" floats in foreground
- 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style

Write each clip as ONE rich paragraph describing the full cinematic scene.
Always end each with: "9:16 vertical, 8 seconds, photorealistic, cinematic UGC style, consistent character: 26-year-old Indian male short black hair dark navy t-shirt"

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
            f"Hook — handheld UGC close-up of 26-year-old Indian male short black hair dark navy t-shirt, shocked curious expression, fast punch-in zoom first 2 seconds, looks directly at camera and says 'Did you know {topic} just changed everything? Here is what nobody is telling you...' — opens loop does not answer yet, dark futuristic studio cyan holographic panels moody blue rim light, 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style, consistent character: 26-year-old Indian male short black hair dark navy t-shirt",
            f"Fact reveal — smooth gimbal medium shot of same 26-year-old Indian male short black hair dark navy t-shirt, continues speaking directly from clip 1 as if no cut, points at large holographic display showing bold readable glowing text '{facts_display}' appearing one by one as floating text cards, explains each fact confidently, rack focus from display to face, dark studio blue ambient holographic glow, ends with 'and that is not even the best part', 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style, consistent character: 26-year-old Indian male short black hair dark navy t-shirt",
            f"Payoff CTA — slow push-in on same 26-year-old Indian male short black hair dark navy t-shirt, continues from clip 2 delivering final punchline about {topic}, closes the loop from clip 1, turns directly to camera with knowing smile 'Now you know why everyone is talking about this. Follow for more', holographic text FOLLOW FOR MORE floats foreground, premium cyan rim light dark background, 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style, consistent character: 26-year-old Indian male short black hair dark navy t-shirt"
        ]

    return clips[:3]
