from dotenv import load_dotenv
load_dotenv()

def get_llm():
    from langchain_groq import ChatGroq
    return ChatGroq(model="llama-3.3-70b-versatile")

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

def generate_flow_prompts_hindi(topic, script, num_clips=3):
    prompt = f"""You are a cinematic director writing Google Flow / Veo 3 VIDEO prompts for YouTube Shorts (Hindi tech channel).

Topic (Hindi channel): {topic}
Script (Hindi): {script}

Generate exactly 3 cinematic video prompts. The prompts must be in ENGLISH (Google Flow only accepts English) but the CONTENT should reflect a Hindi tech channel presenter explaining the topic to an Indian audience.

CHARACTER SEED (use EXACTLY this in ALL 3 clips):
"26-year-old Indian male, short neat black hair, light stubble, sharp jawline, wearing a dark navy crew-neck t-shirt, slim build, wheatish skin tone, no glasses, natural Hindi speaker expressions and gestures"

CRITICAL — DIALOGUE RULE: Before writing the clips, first write 3 short Hinglish dialogue lines (8-12 words each) that this presenter actually SAYS about the specific topic "{topic}" based on the script. These must be concrete and factual about the topic — NOT generic filler like "isko dekho" or "subscribe karo". Each line should state a real point, fact, or comparison drawn from the script. Then embed each line inside its matching clip using the exact phrase: He says: "<hinglish line>"

CLIP 1 — VIRAL HOOK (first 8-10 seconds):
- Objective: Grab attention instantly with a specific, surprising fact about {topic} — not a vague tease
- Character: same presenter, shocked/curious expression, speaking Hindi (mouth moving naturally)
- Camera: handheld UGC close-up, fast punch-in zoom within first 2 seconds, shaky realistic movement
- Lighting: moody cinematic low-key, saffron/orange rim light on face
- Action: he reacts to the surprising fact, leans forward, eyes wide, hands gesturing expressively in Indian style
- Dialogue: He says: "<hinglish hook line stating the specific surprising fact about {topic}>"
- Background: dark futuristic studio, glowing orange holographic UI flickering with Hindi text elements

CLIP 2 — FEATURE SHOWCASE (middle 8-10 seconds):
- Objective: Explain the actual key insight, comparison, or result about {topic} — name the specific detail, not "the details"
- Character: same presenter, confident and explaining expression, natural Hindi speaker body language
- Camera: smooth gimbal medium shot, rack focus from holographic display to his face
- Lighting: dark studio with saffron/orange ambient, holographic screen glow on face
- Action: he gestures at large floating holographic data/visuals about {topic}
- Dialogue: He says: "<hinglish line stating the concrete comparison/result/fact from the script>"
- Background: holographic elements animate in orange/saffron glow, subtle Indian design motifs

CLIP 3 — CTA CLOSE (final 8-10 seconds):
- Objective: Give a clear takeaway/verdict about {topic}, then invite the viewer to watch/follow — verdict first, generic CTA second
- Character: same presenter, direct eye contact, knowing confident smile
- Camera: slow push-in, over-the-shoulder then turns to face camera directly
- Lighting: premium soft orange/saffron rim light, warm Indian skin tone lighting
- Action: he looks directly into camera, gestures warmly as if recommending to a friend
- Dialogue: He says: "<hinglish line giving the verdict/takeaway about {topic}, optionally + short CTA>"
- Background: holographic text in foreground, dark background with subtle saffron/orange glow

CRITICAL: Every clip must describe this EXACT same person. Prompts in English but character is clearly a Hindi content creator for Indian audience. Each clip MUST contain the He says: "..." dialogue line with real topic-specific content — do not skip it.

For each clip write ONE rich paragraph including the dialogue line.
Always end each prompt with: "9:16 vertical, 8 seconds, photorealistic, cinematic UGC style, Hindi tech creator, consistent character: 26-year-old Indian male short black hair dark navy t-shirt"

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
        clean_topic = topic.split("||PATTERN:")[0].strip()
        clips = [
            f'Viral hook — handheld UGC close-up of 26-year-old Indian male, short neat black hair, light stubble, dark navy t-shirt, shocked expression, eyes wide, fast punch-in zoom in first 2 seconds, leans forward. He says: "Yaar, {clean_topic} ke baare mein yeh fact suna kya?" Dark futuristic studio, glowing orange holographic panels flickering, moody saffron rim lighting, 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style, consistent character: 26-year-old Indian male short black hair dark navy t-shirt',
            f'Feature showcase — smooth gimbal medium shot of 26-year-old Indian male, short neat black hair, light stubble, dark navy t-shirt, confident explaining expression, gestures at large glowing orange holographic display showing {clean_topic} visuals. He says: "Yeh hai {clean_topic} ka sabse important point, dhyan se suno." Rack focus from display to his face, dark studio saffron ambient lighting, holographic data pulses around him, 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style, consistent character: 26-year-old Indian male short black hair dark navy t-shirt',
            f'CTA close — slow push-in on 26-year-old Indian male, short neat black hair, light stubble, dark navy t-shirt, turns to face camera directly with knowing smile, direct eye contact. He says: "Toh {clean_topic} ka pura sach yahi hai — video pasand aaya toh follow karo." Holographic text floats in foreground, premium soft orange rim lighting, dark background subtle saffron glow, 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style, consistent character: 26-year-old Indian male short black hair dark navy t-shirt'
        ]

    return clips[:3]
