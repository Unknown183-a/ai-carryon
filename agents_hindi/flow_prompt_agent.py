from dotenv import load_dotenv
load_dotenv()

def get_llm():
    from langchain_groq import ChatGroq
    try:
        llm = ChatGroq(model="llama-3.3-70b-versatile")
        llm.invoke("hi")
        return llm
    except Exception:
        from langchain_groq import ChatGroq
        return ChatGroq(model="llama3-8b-8192")

def generate_flow_prompts_hindi(topic, script, num_clips=3):
    llm = get_llm()
    prompt = f"""You are a cinematic director writing Google Flow / Veo 3 VIDEO prompts for YouTube Shorts (Hindi tech channel).

Topic (Hindi channel): {topic}
Script (Hindi): {script}

Generate exactly 3 cinematic video prompts. The prompts must be in ENGLISH (Google Flow only accepts English) but the CONTENT should reflect a Hindi tech channel presenter explaining the topic to an Indian audience.

CLIP 1 — VIRAL HOOK (first 8-10 seconds):
- Objective: Grab attention instantly, create curiosity for Hindi-speaking Indian audience
- Character: young Indian male tech presenter, shocked/curious expression, speaking Hindi (mouth moving naturally)
- Camera: handheld UGC close-up, fast punch-in zoom within first 2 seconds, shaky realistic movement
- Lighting: moody cinematic low-key, saffron/orange rim light on face
- Action: he reacts to something surprising about {topic}, leans forward, eyes wide, hands gesturing expressively in Indian style
- Background: dark futuristic studio, glowing orange holographic UI flickering with Hindi text elements

CLIP 2 — FEATURE SHOWCASE (middle 8-10 seconds):
- Objective: Show the key insight or feature, build trust with Indian viewers
- Character: same presenter, confident and explaining expression, natural Hindi speaker body language
- Camera: smooth gimbal medium shot, rack focus from holographic display to his face
- Lighting: dark studio with saffron/orange ambient, holographic screen glow on face
- Action: he gestures at large floating holographic data/visuals about {topic}, explaining in natural Indian presenter style
- Background: holographic elements animate in orange/saffron glow, subtle Indian design motifs

CLIP 3 — CTA CLOSE (final 8-10 seconds):
- Objective: Drive action, emotional payoff for Hindi audience
- Character: same presenter, direct eye contact, knowing confident smile
- Camera: slow push-in, over-the-shoulder then turns to face camera directly
- Lighting: premium soft orange/saffron rim light, warm Indian skin tone lighting
- Action: he looks directly into camera, gestures warmly as if recommending to a friend, natural Indian conversational style
- Background: holographic text in foreground, dark background with subtle saffron/orange glow

CHARACTER SEED (use EXACTLY this in ALL 3 clips):
"26-year-old Indian male, short neat black hair, light stubble, sharp jawline, wearing a dark navy crew-neck t-shirt, slim build, wheatish skin tone, no glasses, natural Hindi speaker expressions and gestures"

CRITICAL: Every clip must describe this EXACT same person. Prompts in English but character is clearly a Hindi content creator for Indian audience.

For each clip write ONE rich paragraph.
Always end each prompt with: "9:16 vertical, 8 seconds, photorealistic, cinematic UGC style, Hindi tech creator, consistent character: 26-year-old Indian male short black hair dark navy t-shirt"

Return EXACTLY:
CLIP 1: <paragraph>
CLIP 2: <paragraph>
CLIP 3: <paragraph>
"""

    response = llm.invoke(prompt).content.strip()

    clips = []
    for line in response.split("\n"):
        line = line.strip()
        if line.upper().startswith("CLIP"):
            parts = line.split(":", 1)
            if len(parts) == 2:
                clips.append(parts[1].strip())

    if len(clips) < 3:
        clips = [
            f"Viral hook — handheld UGC close-up of 26-year-old Indian male, short neat black hair, light stubble, dark navy t-shirt, shocked expression, eyes wide, fast punch-in zoom in first 2 seconds, leans forward revealing secret about {topic}, dark futuristic studio, glowing orange holographic panels flickering, moody saffron rim lighting, 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style, consistent character: 26-year-old Indian male short black hair dark navy t-shirt",
            f"Feature showcase — smooth gimbal medium shot of 26-year-old Indian male, short neat black hair, light stubble, dark navy t-shirt, confident explaining expression, gestures at large glowing orange holographic display showing {topic} visuals, rack focus from display to his face, dark studio saffron ambient lighting, holographic data pulses around him, 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style, consistent character: 26-year-old Indian male short black hair dark navy t-shirt",
            f"CTA close — slow push-in on 26-year-old Indian male, short neat black hair, light stubble, dark navy t-shirt, turns to face camera directly with knowing smile, direct eye contact, holographic text floats in foreground, premium soft orange rim lighting, dark background subtle saffron glow, gestures toward camera, 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style, consistent character: 26-year-old Indian male short black hair dark navy t-shirt"
        ]

    return clips[:3]
