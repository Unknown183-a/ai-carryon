# agents_hindi/flow_prompt_agent.py
from dotenv import load_dotenv
load_dotenv()

def generate_flow_prompts_hindi(topic, script, num_clips=3):
    from langchain_groq import ChatGroq
    llm = ChatGroq(model="llama-3.3-70b-versatile")

    prompt = f"""You are an expert at writing Google Flow / Veo 3 video generation prompts.

Topic (Hindi channel): {topic}
Script: {script}

Generate exactly {num_clips} short video clip prompts for this Hindi tech channel.
Each clip will be 8 seconds, 9:16 vertical format for YouTube Shorts.

Rules:
- Each prompt must describe a VISUAL SCENE only (no dialogue, no text overlays)
- Must feature a young Indian male tech presenter on camera
- Dark futuristic background with glowing orange/saffron holographic UI elements (use orange/saffron instead of blue to differentiate Hindi channel visually)
- Cinematic lighting, professional look
- Each clip should show a slightly different scene/angle/action
- Prompts should visually match the script topic
- Add at end: "9:16 vertical, 8 seconds, photorealistic, cinematic UGC style, consistent character: 26-year-old Indian male short black hair dark navy t-shirt"

Return EXACTLY this format, nothing else:

CLIP 1: <prompt here>
CLIP 2: <prompt here>
CLIP 3: <prompt here>
"""

    response = llm.invoke(prompt).content.strip()

    clips = []
    for line in response.split("\n"):
        line = line.strip()
        if line.upper().startswith("CLIP"):
            parts = line.split(":", 1)
            if len(parts) == 2:
                clips.append(parts[1].strip())

    if not clips:
        clips = [
            f"Young Indian male tech presenter talking to camera about {topic}, dark futuristic background, glowing orange holographic UI elements, cinematic 9:16 vertical, 8 seconds",
            f"Close up of Indian male tech presenter gesturing at orange holographic data screens showing {topic}, dark studio lighting, cinematic vertical video",
            f"Young Indian male tech presenter standing confidently, AI graphics floating around him related to {topic}, futuristic dark background with saffron glow"
        ]

    return clips[:num_clips]
