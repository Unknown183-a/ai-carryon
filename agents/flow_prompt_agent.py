from dotenv import load_dotenv
load_dotenv()
import re

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


def sanitize_for_flow(text):
    """Remove brand/real entity names that violate Flow policies."""
    brands = [
        "Tata", "Apple", "Samsung", "Google", "Microsoft", "Meta", "Tesla",
        "OpenAI", "Anthropic", "Amazon", "Netflix", "Twitter", "Instagram",
        "WhatsApp", "YouTube", "TikTok", "Jio", "Airtel", "Paytm",
        "Flipkart", "Zomato", "Swiggy", "Ola", "Uber", "iPhone", "Android",
        "ChatGPT", "Gemini", "Claude", "BSNL", "HDFC", "SBI", "ICICI"
    ]
    for brand in brands:
        text = re.sub(rf"\b{brand}\b", "a major tech company", text, flags=re.IGNORECASE)
    return text


def extract_key_facts(script, topic):
    prompt = f"""From this YouTube Shorts script, extract exactly 2-3 KEY FACTS for on-screen display.
Topic: {topic}
Script: {script}
Rules: SPECIFIC numbers/prices/dates, max 6 words each.
Good: "Battery 40% bigger", "Price drops $100"
Bad: "Much improved", "Better than before"
Return ONLY a Python list: ["fact 1", "fact 2", "fact 3"]"""
    try:
        import json
        response = safe_invoke(prompt).content.strip()
        match = re.search(r'\[.*?\]', response, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return [f"{topic} key update", "Watch till end"]


def generate_flow_prompts(topic, script, num_clips=3):
    key_facts = extract_key_facts(script, topic)
    facts_display = " | ".join(key_facts)

    # Generate dialogue for each part
    dialogue_prompt = f"""You are a YouTube Shorts script writer. Write SPECIFIC topic-based dialogue.

Topic: {topic}
Key facts: {facts_display}
Script reference: {script[:300]}

CRITICAL RULES:
- Every line MUST mention the actual topic or specific facts — NO generic filler
- BAD LINE 1: "Wait, this actually surprised me" — TOO VAGUE, REJECTED
- GOOD LINE 1: "Honestly, {topic} just changed something that most people completely missed — and it actually matters"
- BAD LINE 2: "Here are the facts" — TOO VAGUE, REJECTED
- GOOD LINE 2: "So here is what {topic} actually means: {facts_display.split('|')[0].strip() if facts_display else 'first fact'}. Not gonna lie, this one caught me off guard."
- BAD LINE 3: "Now you know the real story" — TOO VAGUE, REJECTED
- GOOD LINE 3: "If you are not paying attention to {topic} right now, you are missing something important. Follow for more content like this."

Write exactly 3 lines. Each MUST contain topic name or specific fact. Natural slow conversational pace.

LINE 1 (Hook — name the topic, ONE shocking specific angle, build curiosity without revealing all):
LINE 2 (Facts — name topic + explain each fact from "{facts_display}" one by one in simple clear English):
LINE 3 (Verdict — specific conclusion about topic + warm natural follow CTA):"""

    dialogue_response = safe_invoke(dialogue_prompt).content.strip()
    lines = {"LINE 1": "", "LINE 2": "", "LINE 3": ""}
    for line in dialogue_response.split("\n"):
        line = line.strip()
        for key in lines:
            if line.upper().startswith(key):
                lines[key] = line.split(":", 1)[-1].strip()

    if not lines["LINE 1"]:
        lines["LINE 1"] = f"Wait... this actually surprised me. Nobody is talking about what just happened in tech."
        lines["LINE 2"] = f"Honestly, here are the facts: {facts_display}. Not gonna lie, this changes everything."
        lines["LINE 3"] = f"This is seriously worth knowing. Follow for more content like this."

    # Do NOT sanitize dialogue — keep topic specific
    # Sanitization only applies to character/scene descriptions below

    # PART 1 — VIRAL HOOK
    clip1 = f"""Hyper-realistic cinematic UGC YouTube Shorts. 
SCENE OBJECTIVE: Viral hook — instant curiosity, emotional attention within 2 seconds.
CHARACTER: Smart confident tech presenter, modern minimal outfit — fitted dark t-shirt, clean look, sharp style. Uses avatar image for face consistency.
ACTION: Fast punch-in zoom in first 2 seconds. Presenter looks directly at camera with genuine shocked curious expression. Natural subtle reaction — slight eyebrow raise, leans forward. Says naturally at slow conversational pace with emotional pause: "{lines['LINE 1']}"
CAMERA: Handheld UGC close-up, fast punch-in zoom, slight authentic shake, POV energy.
ENVIRONMENT: Modern premium home studio — dark background, soft RGB ambient lighting in deep blue and purple, sleek desk setup with ultrawide monitor showing tech UI, clean minimal aesthetic, shallow depth of field, feels real not CGI.
LIGHTING: Moody cinematic low-key, soft blue rim light on face, natural skin tone, premium contrast.
EMOTION: Genuine surprise, curiosity, authentic not overacted.
SOUND: Subtle whoosh on zoom, ambient room tone.
TRANSITION: Seamless cut to next clip — presenter mid-sentence.
9:16 vertical, 8 seconds, photorealistic, hyper-realistic, premium cinematic UGC, NOT CGI, NOT AI generated looking, real human energy."""

    # PART 2 — FACT REVEAL
    clip2 = f"""Hyper-realistic cinematic UGC YouTube Shorts — CONTINUES DIRECTLY FROM PREVIOUS CLIP.
SCENE OBJECTIVE: Deliver actual value — show real facts clearly on screen, build trust.
CHARACTER: Same presenter, same outfit, same environment — confident explaining expression, natural hand gestures.
ACTION: Continues speaking naturally from previous clip — NO restart. Says slowly and clearly: "{lines['LINE 2']}". As he speaks, bold white text overlays appear one by one on screen: '{facts_display}' — each fact appears at exact moment he mentions it, stays 2-3 seconds, large readable font. Presenter points naturally toward text. Slight head nod for emphasis.
CAMERA: Smooth gimbal medium shot, subtle rack focus from text overlay to face, dynamic but stable.
ENVIRONMENT: Same premium home studio — ultrawide monitor now shows relevant tech graphics/data visualizations glowing behind him.
LIGHTING: Same moody blue ambient, monitor glow adds cinematic depth.
B-ROLL: Quick macro cut to tech device/screen showing the facts visually, then back to presenter.
EMOTION: Confident, knowledgeable, trustworthy — like a smart friend explaining.
SOUND: Subtle notification sound as each text fact appears.
TRANSITION: Seamless — presenter mid-thought leading into part 3.
9:16 vertical, 8 seconds, photorealistic, hyper-realistic, premium cinematic UGC, real human energy."""

    # PART 3 — PAYOFF + CTA
    clip3 = f"""Hyper-realistic cinematic UGC YouTube Shorts — CONTINUES DIRECTLY FROM PREVIOUS CLIP.
SCENE OBJECTIVE: Emotional payoff — close the loop, drive follow action naturally.
CHARACTER: Same presenter, same outfit — warm knowing smile, direct confident eye contact.
ACTION: Continues from previous clip, delivers final verdict naturally: "{lines['LINE 3']}". Turns slightly more toward camera — feels like talking directly to viewer. Subtle approving nod. Natural slight smile. Bold text 'FOLLOW FOR MORE' appears at bottom of screen in clean modern font.
CAMERA: Slow cinematic push-in, over-shoulder then turns to face camera directly, premium feel.
ENVIRONMENT: Same studio — slight warmer tone shift, premium hero shot feel.
LIGHTING: Slightly warmer soft rim light, cinematic premium glow.
B-ROLL: Quick hero shot of topic visual, then back to presenter for final look.
EMOTION: Warm, confident, genuine — like a trusted friend giving real advice.
SOUND: Subtle satisfying chime on CTA text appearance, warm ambient fade.
TRANSITION: Clean end frame with presenter smiling at camera.
9:16 vertical, 8 seconds, photorealistic, hyper-realistic, premium cinematic UGC, real human energy."""

    return [clip1, clip2, clip3]
