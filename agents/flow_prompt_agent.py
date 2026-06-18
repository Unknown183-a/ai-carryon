from dotenv import load_dotenv
load_dotenv()

def generate_flow_prompts(topic, script, num_clips=3):
    from langchain_groq import ChatGroq
    llm = ChatGroq(model="llama-3.3-70b-versatile")

    prompt = f"""You are a cinematic director writing Google Flow / Veo 3 VIDEO prompts for YouTube Shorts.

Topic: {topic}
Script: {script}

Generate exactly 3 cinematic video prompts following this exact 3-part structure:

CLIP 1 — VIRAL HOOK (first 8-10 seconds):
- Objective: Grab attention instantly, create curiosity
- Character: young Indian male tech presenter, shocked/curious expression
- Camera: handheld UGC close-up, fast punch-in zoom within first 2 seconds, shaky realistic movement
- Lighting: moody cinematic low-key, blue rim light on face
- Action: he reacts to something surprising about the topic, leans forward, eyes wide
- Background: dark futuristic studio, glowing cyan holographic UI flickering

CLIP 2 — FEATURE SHOWCASE (middle 8-10 seconds):
- Objective: Show the key insight or feature, build trust
- Character: same presenter, confident and explaining expression
- Camera: smooth gimbal medium shot, rack focus from holographic display to his face
- Lighting: dark studio with blue ambient, holographic screen glow on face
- Action: he gestures at large floating holographic data/visuals related to the topic
- Background: holographic elements animate and pulse around him

CLIP 3 — CTA CLOSE (final 8-10 seconds):
- Objective: Drive action, emotional payoff
- Character: same presenter, direct eye contact, knowing smile
- Camera: slow push-in, over-the-shoulder then turns to face camera directly
- Lighting: premium soft blue/cyan rim light, slightly warmer tone
- Action: he looks directly into camera, gestures as if recommending to viewer
- Background: holographic text floats in foreground, dark background with subtle glow

For each clip write ONE rich paragraph combining: scene objective, character emotion+action, camera movement, lighting, background, motion elements.
Always end each prompt with: "9:16 vertical, 8 seconds, photorealistic, cinematic UGC style"

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
            f"Viral hook — handheld UGC close-up of young Indian male tech presenter with shocked expression, eyes wide, fast punch-in zoom in first 2 seconds, he leans forward as if revealing a secret about {topic}, dark futuristic studio with glowing cyan holographic panels flickering, moody blue rim lighting, floating code symbols drift past camera, 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style",
            f"Feature showcase — smooth gimbal medium shot of young Indian male tech presenter gesturing confidently at large glowing holographic display showing {topic} visuals, rack focus from display to his face, dark studio with blue ambient lighting, holographic data pulses and animates around him, confident explaining expression, 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style",
            f"CTA close — slow push-in on young Indian male tech presenter turning to face camera directly with a knowing smile, direct eye contact as if recommending to viewer, holographic text floats in foreground, premium soft cyan rim lighting, dark background with subtle glow, he gestures toward camera, 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style"
        ]

    return clips[:3]
