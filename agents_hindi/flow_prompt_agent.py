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
    brands = [
        "Tata", "Apple", "Samsung", "Google", "Microsoft", "Meta", "Tesla",
        "OpenAI", "Anthropic", "Amazon", "Netflix", "Twitter", "Instagram",
        "WhatsApp", "YouTube", "TikTok", "Jio", "Airtel", "Paytm",
        "Flipkart", "Zomato", "Swiggy", "Ola", "Uber", "iPhone", "Android",
        "ChatGPT", "Gemini", "Claude", "BSNL", "HDFC", "SBI", "ICICI"
    ]
    for brand in brands:
        text = re.sub(rf"\b{brand}\b", "ek badi tech company", text, flags=re.IGNORECASE)
    return text


def extract_hindi_facts(script, topic):
    prompt = f"""From this Hindi YouTube Shorts script, extract exactly 2-3 KEY FACTS for on-screen display.
Topic: {topic}
Script: {script}
Rules: SPECIFIC numbers/prices in Hinglish, max 6 words each.
Good: "Battery 40% zyada", "Price sirf Rs 999"
Bad: "Bahut achha", "Better than before"
Return ONLY a Python list: ["fact 1", "fact 2", "fact 3"]"""
    try:
        import json
        response = safe_invoke(prompt).content.strip()
        match = re.search(r'\[.*?\]', response, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return [f"{topic} naya update", "Poora video dekho"]


def generate_flow_prompts_hindi(topic, script, num_clips=3):
    key_facts = extract_hindi_facts(script, topic)
    facts_display = " | ".join(key_facts)
    clean_topic = topic.split("||PATTERN:")[0].strip()

    # Generate Hinglish dialogue
    dialogue_prompt = f"""You are an emotional Hinglish dialogue writer for YouTube Shorts tech content.
Write 3 short natural Hinglish dialogue lines for a Hindi tech presenter.

Topic: {clean_topic}
Key facts: {facts_display}
Script: {script}

Rules:
- Natural Hinglish — mix of Hindi and English, conversational
- Use phrases like "Honestly yaar...", "Sach mein?", "Yeh toh maine expect nahi kiya tha", "Not gonna lie..."
- NO brand names
- SLOW natural pace — emotional pauses
- Each line max 2 sentences

LINE 1 (Hook — shock/curiosity in Hinglish, don't reveal answer):
LINE 2 (Facts — reveal {facts_display} slowly and clearly in Hinglish):
LINE 3 (Payoff — verdict + follow CTA in Hinglish):"""

    dialogue_response = safe_invoke(dialogue_prompt).content.strip()
    lines = {"LINE 1": "", "LINE 2": "", "LINE 3": ""}
    for line in dialogue_response.split("\n"):
        line = line.strip()
        for key in lines:
            if line.upper().startswith(key):
                lines[key] = line.split(":", 1)[-1].strip()

    if not lines["LINE 1"]:
        lines["LINE 1"] = f"Yaar suno, yeh jaankar main khud hairan tha. Honestly, yeh koi nahi bata raha tha."
        lines["LINE 2"] = f"Toh yeh hain asli facts: {facts_display}. Sach mein, yeh sun ke dimaag ghoom gaya mera."
        lines["LINE 3"] = f"Ab tum jaante ho poora sach. Aisa content chahiye toh follow karo — seriously worth it."

    for key in lines:
        lines[key] = sanitize_for_flow(lines[key])

    # PART 1 — VIRAL HOOK
    clip1 = f"""Hyper-realistic cinematic UGC YouTube Shorts — Hindi tech channel.
SCENE OBJECTIVE: Viral hook — instant curiosity, emotional attention within 2 seconds.
CHARACTER: Smart confident Indian tech presenter, modern minimal outfit — fitted dark t-shirt, clean sharp look. Uses avatar image for face consistency.
ACTION: Fast punch-in zoom in first 2 seconds. Presenter looks directly at camera with genuine shocked curious expression. Natural subtle reaction — slight eyebrow raise, leans forward. Says naturally in Hinglish at slow conversational pace with emotional pause: "{lines['LINE 1']}"
CAMERA: Handheld UGC close-up, fast punch-in zoom, slight authentic shake, POV energy.
ENVIRONMENT: Modern premium Indian home studio — dark background, warm amber and blue LED strip lighting, sleek desk with laptop showing tech content, clean books on shelf, indoor plants, feels real and relatable, shallow depth of field, NOT CGI.
LIGHTING: Moody cinematic, warm amber rim light with cool blue fill, natural Indian skin tone.
EMOTION: Genuine surprise, curiosity, authentic — not overacted, real human energy.
SOUND: Subtle whoosh on zoom, warm ambient room tone.
TRANSITION: Seamless cut — presenter mid-sentence continuing to part 2.
9:16 vertical, 8 seconds, photorealistic, hyper-realistic, premium cinematic UGC, real human energy, Indian aesthetic."""

    # PART 2 — FACT REVEAL
    clip2 = f"""Hyper-realistic cinematic UGC YouTube Shorts — CONTINUES DIRECTLY FROM PREVIOUS CLIP.
SCENE OBJECTIVE: Deliver real value — show facts clearly on screen, build trust.
CHARACTER: Same presenter, same outfit, same environment — confident explaining expression, natural Indian hand gestures.
ACTION: Continues speaking naturally from previous clip — NO restart. Says slowly and clearly in Hinglish: "{lines['LINE 2']}". Bold white Hinglish text overlays appear one by one: '{facts_display}' — each at exact moment mentioned, stays 2-3 seconds, large readable font. Presenter points naturally toward text. Slight confident head nod.
CAMERA: Smooth gimbal medium shot, subtle rack focus from text to face.
ENVIRONMENT: Same premium Indian home studio — laptop now shows relevant tech graphics.
LIGHTING: Same warm amber and blue ambient, laptop glow adds depth.
B-ROLL: Quick macro cut to phone/laptop screen showing facts, then back to presenter.
EMOTION: Confident, knowledgeable, like a smart dost explaining something important.
SOUND: Subtle notification sound as each fact text appears.
TRANSITION: Seamless — leading into part 3.
9:16 vertical, 8 seconds, photorealistic, hyper-realistic, premium cinematic UGC, real human energy, Indian aesthetic."""

    # PART 3 — PAYOFF + CTA
    clip3 = f"""Hyper-realistic cinematic UGC YouTube Shorts — CONTINUES DIRECTLY FROM PREVIOUS CLIP.
SCENE OBJECTIVE: Emotional payoff — close loop, drive follow action naturally.
CHARACTER: Same presenter, same outfit — warm knowing smile, direct confident eye contact.
ACTION: Continues from previous clip, delivers final verdict in Hinglish: "{lines['LINE 3']}". Turns slightly more toward camera — direct personal connection with viewer. Subtle approving nod, natural warm smile. Bold text 'FOLLOW KARO' appears at bottom in clean modern font.
CAMERA: Slow cinematic push-in, turns to face camera directly, premium hero feel.
ENVIRONMENT: Same studio — slight warmer tone, feels like intimate conversation.
LIGHTING: Slightly warmer soft rim light, premium cinematic glow.
B-ROLL: Quick hero shot of topic visual, back to presenter for final warm look.
EMOTION: Warm, genuine, trusted dost giving real advice.
SOUND: Subtle satisfying chime on CTA text, warm ambient fade out.
9:16 vertical, 8 seconds, photorealistic, hyper-realistic, premium cinematic UGC, real human energy, Indian aesthetic."""

    return [clip1, clip2, clip3]
