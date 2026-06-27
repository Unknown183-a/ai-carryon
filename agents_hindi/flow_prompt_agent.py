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


def extract_hindi_facts(script, topic):
    """Extract 2-3 concrete facts from script for on-screen display."""
    prompt = f"""From this Hindi YouTube Shorts script, extract exactly 2-3 KEY FACTS to show on screen.

Topic: {topic}
Script: {script}

Rules:
- SPECIFIC: numbers, prices, percentages, names
- Short: max 6 words each
- In Hinglish (mix of Hindi + English)

Good: "Battery 40% zyada", "Price sirf ₹999", "Speed 2x faster"
Bad: "Bahut achha hai", "Improved performance"

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
    return [f"{topic} — naya update", "Poora video dekho"]


def generate_flow_prompts_hindi(topic, script, num_clips=3):
    key_facts = extract_hindi_facts(script, topic)
    facts_display = " | ".join(key_facts)
    clean_topic = topic.split("||PATTERN:")[0].strip()

    prompt = f"""You are a cinematic director creating a 3-part CONTINUOUS story for a Hindi YouTube Shorts channel.

Topic: {clean_topic}
Script (Hindi): {script}
Key facts to show on screen in Clip 2: {facts_display}

CRITICAL: These 3 clips are ONE continuous video. The presenter speaks CONTINUOUSLY — each clip picks up EXACTLY where the previous one ended. No random restarts. One unbroken conversation split into 3 parts.

CHARACTER (SAME in ALL 3 clips — never change):
"26-year-old Indian male, short neat black hair, light stubble, sharp jawline, dark navy crew-neck t-shirt, slim build, wheatish skin tone, no glasses, natural Hindi speaker expressions"

CLIP 1 — HOOK (opens the story, creates curiosity):
- Presenter starts speaking directly to camera with shocked/curious expression
- He OPENS A LOOP in Hinglish — teases the topic without revealing the answer yet
- Example: "Yaar suno, {clean_topic} ke baare mein ek baat hai jo koi nahi batata..."
- He does NOT give facts yet — ends mid-sentence to pull viewer into Clip 2
- Camera: handheld UGC close-up, fast punch-in zoom first 2 seconds, shaky realistic
- Lighting: moody saffron/orange rim light, dark futuristic studio
- Ends with "...aur yeh sun ke tumhara dimaag ghoom jayega"
- 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style

CLIP 2 — FACT REVEAL (continues directly from Clip 1):
- Presenter CONTINUES speaking — picks up exactly where Clip 1 ended, no restart
- He reveals the actual facts in Hinglish: bold readable glowing text "{facts_display}" appears on holographic display one by one as he points and explains
- Viewer can READ the facts on screen as floating text cards
- Camera: smooth gimbal medium shot, rack focus from holographic display to face
- Lighting: dark studio saffron/orange ambient, holographic glow on face
- Ends with "...aur sabse mast part toh abhi baaki hai"
- 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style

CLIP 3 — PAYOFF + CTA (closes the loop, drives follow):
- Presenter CONTINUES from Clip 2 — delivers final surprising fact or verdict
- CLOSES THE LOOP from Clip 1 — fully answers what was teased
- Looks directly into camera: "Toh yahi hai {clean_topic} ka sach. Aisa content chahiye toh follow karo."
- Camera: slow push-in, turns directly to camera with knowing smile
- Lighting: premium soft saffron rim light, warm tone
- Holographic text "FOLLOW KARO" floats in foreground
- 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style

Write each clip as ONE rich paragraph in English (Google Flow only accepts English).
Always end each with: "9:16 vertical, 8 seconds, photorealistic, cinematic UGC style, Hindi tech creator, consistent character: 26-year-old Indian male short black hair dark navy t-shirt"

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
            f"Hook — handheld UGC close-up of 26-year-old Indian male short black hair dark navy t-shirt, shocked curious expression, fast punch-in zoom first 2 seconds, looks directly at camera and says in Hinglish 'Yaar suno, {clean_topic} ke baare mein ek baat hai jo koi nahi batata...' opens loop does not reveal answer yet ends mid-sentence, dark futuristic studio orange holographic panels moody saffron rim light, 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style, Hindi tech creator, consistent character: 26-year-old Indian male short black hair dark navy t-shirt",
            f"Fact reveal — smooth gimbal medium shot of same 26-year-old Indian male short black hair dark navy t-shirt, continues speaking directly from clip 1 no restart, points at large holographic display showing bold readable glowing Hinglish text '{facts_display}' appearing one by one as floating text cards he explains each fact, rack focus display to face, dark studio saffron ambient holographic glow, ends with 'aur sabse mast part toh abhi baaki hai', 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style, Hindi tech creator, consistent character: 26-year-old Indian male short black hair dark navy t-shirt",
            f"Payoff CTA — slow push-in on same 26-year-old Indian male short black hair dark navy t-shirt, continues from clip 2 delivers final verdict about {clean_topic} closes loop from clip 1, turns directly to camera knowing smile says 'Toh yahi hai {clean_topic} ka sach. Aisa content chahiye toh follow karo', holographic text FOLLOW KARO floats foreground, premium soft saffron rim light warm tone dark background, 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style, Hindi tech creator, consistent character: 26-year-old Indian male short black hair dark navy t-shirt"
        ]

    return clips[:3]
