from dotenv import load_dotenv
load_dotenv()

def generate_flow_prompts(topic, script, num_clips=3):
    from langchain_groq import ChatGroq
    llm = ChatGroq(model="llama-3.3-70b-versatile")

    prompt = f"""You are a cinematic video director writing Google Flow / Veo 3 VIDEO prompts for YouTube Shorts.

Topic: {topic}
Script: {script}
Total clips needed: {num_clips}

Each clip = 8-10 seconds, 9:16 vertical format.

For each clip, write a rich cinematic prompt that combines ALL of these elements in one paragraph:
- Scene objective (hook / feature showcase / CTA etc.)
- Character: young Indian male tech presenter, specific emotion and expression
- Character action: what he is physically doing
- Camera movement: e.g. "slow push-in", "handheld UGC shaky", "smooth gimbal orbit", "rack focus", "whip pan", "over-the-shoulder"
- Lighting: e.g. "moody low-light", "golden-hour warm", "dark room blue ambient", "cinematic shallow depth of field"
- Background: dark futuristic studio, glowing cyan/blue holographic UI elements floating
- Motion: describe what moves in the scene (holograms, text, hands, camera)
- End with: "9:16 vertical, 8 seconds, photorealistic, cinematic"

Return EXACTLY this format, nothing else:

CLIP 1: <full cinematic prompt in one paragraph>
CLIP 2: <full cinematic prompt in one paragraph>
CLIP 3: <full cinematic prompt in one paragraph>

Example of a PERFECT prompt:
CLIP 1: Viral hook scene — close-up handheld UGC shot of a young Indian male tech presenter looking directly into the camera with a shocked, disbelieving expression, slow punch-in zoom within first 2 seconds, he raises one eyebrow and slightly shakes his head as if saying "I can't believe this", dark futuristic studio background with glowing blue holographic data panels flickering around him, moody cinematic low-key lighting with a cyan rim light on his face, floating AI text and code symbols drift past the camera in the foreground, 9:16 vertical, 8 seconds, photorealistic, cinematic UGC style.
"""

    response = llm.invoke(prompt).content.strip()

    clips = []
    for line in response.split("\n"):
        line = line.strip()
        if line.upper().startswith("CLIP"):
            parts = line.split(":", 1)
            if len(parts) == 2:
                clips.append(parts[1].strip())

    if len(clips) < num_clips:
        fallbacks = [
            f"Viral hook — close-up handheld UGC shot of a young Indian male tech presenter with a shocked expression looking into camera, slow punch-in zoom, eyebrow raised, dark futuristic studio with glowing blue holographic panels flickering, cyan rim lighting, floating AI code symbols drift past camera, 9:16 vertical, 8 seconds, photorealistic cinematic",
            f"Feature showcase — medium shot of young Indian male tech presenter gesturing confidently at large glowing holographic data screens showing {topic} visuals, smooth gimbal orbit movement, dark studio with cyan UI glow, cinematic shallow depth of field, holograms animate and pulse, 9:16 vertical, 8 seconds, photorealistic cinematic",
            f"CTA closing — over-the-shoulder slow push-in of young Indian male tech presenter turning to face camera with a knowing smile, holographic text floats in foreground, dramatic blue rim lighting, dark futuristic background, rack focus from background to his face, 9:16 vertical, 8 seconds, photorealistic cinematic"
        ]
        clips = fallbacks[:num_clips]

    return clips[:num_clips]
