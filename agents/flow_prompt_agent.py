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
        "Tata","Apple","Samsung","Google","Microsoft","Meta","Tesla",
        "OpenAI","Anthropic","Amazon","Netflix","Twitter","Instagram",
        "WhatsApp","YouTube","TikTok","Jio","Airtel","Paytm",
        "Flipkart","Zomato","Swiggy","Ola","Uber","Android",
        "ChatGPT","Gemini","Claude","BSNL","HDFC","SBI","ICICI"
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


def parse_dialogue(response_text):
    """Parse LLM dialogue response — handles label+dialogue on same line OR next line."""
    lines_out = {"LINE 1": "", "LINE 2": "", "LINE 3": ""}
    raw_lines = [l.strip() for l in response_text.split("\n") if l.strip()]
    current_key = None

    for line in raw_lines:
        matched_key = None
        for num, key in [("1", "LINE 1"), ("2", "LINE 2"), ("3", "LINE 3")]:
            if re.match(rf"LINE\s*{num}", line, re.IGNORECASE):
                matched_key = key
                break

        if matched_key:
            current_key = matched_key
            # Check if dialogue is on same line after colon
            after_colon = line.split(":", 1)[-1].strip().strip('"\'')
            if len(after_colon) > 10:
                lines_out[current_key] = after_colon
        else:
            # Dialogue is on next line
            if current_key and not lines_out[current_key]:
                cleaned = line.strip('"\'')
                if len(cleaned) > 10:
                    lines_out[current_key] = cleaned
                    current_key = None

    print(f"Parsed dialogue: {lines_out}")
    return lines_out


def generate_flow_prompts(topic, script, num_clips=3):
    key_facts = extract_key_facts(script, topic)
    facts_display = " | ".join(key_facts)

    dialogue_prompt = f"""You are a YouTube Shorts script writer. Write 3 specific dialogue lines for a tech presenter.

Topic: {topic}
Key facts: {facts_display}
Script reference: {script[:300]}

RULES:
- Be SPECIFIC — mention actual topic concept and facts
- Natural slow conversational English
- Max 2 sentences per line
- Never paste topic title word for word at end of sentence

LINE 1 (Hook — shocking specific angle about topic, build curiosity, do not reveal all facts):
LINE 2 (Facts — explain each fact from "{facts_display}" one by one in simple English):
LINE 3 (Verdict — specific conclusion about topic + natural follow CTA):"""

    dialogue_response = safe_invoke(dialogue_prompt).content.strip()
    lines = parse_dialogue(dialogue_response)

    # Fallback only if parsing completely failed
    if not lines["LINE 1"]:
        lines["LINE 1"] = f"Honestly, what just happened with {topic} caught me completely off guard — and most people have no idea."
        lines["LINE 2"] = f"Here is what actually matters: {facts_display}. Not gonna lie, each of these changes things."
        lines["LINE 3"] = f"If you care about tech, {topic} is something you need to pay attention to right now. Follow for more."

    background = (
        "Modern premium home studio — dark background, soft RGB ambient lighting deep blue and purple, "
        "sleek desk with ultrawide monitor showing tech UI, clean minimal aesthetic, "
        "shallow depth of field, real room NOT CGI"
    )
    suffix = "STRICT 9:16 VERTICAL PORTRAIT FORMAT — YouTube Shorts format, tall not wide, phone screen format, 1080x1920 resolution, 8 seconds, photorealistic, hyper-realistic, premium cinematic UGC, NOT CGI, real human energy"

    clip1 = f"""Hyper-realistic cinematic UGC YouTube Shorts.
SCENE OBJECTIVE: Viral hook — instant curiosity, emotional attention within 2 seconds.
CHARACTER: Smart confident tech presenter, modern minimal outfit — fitted dark t-shirt, clean look, sharp style. Uses avatar image for face consistency.
ACTION: Fast punch-in zoom in first 2 seconds. Presenter looks directly at camera with genuine shocked curious expression. Natural subtle reaction — slight eyebrow raise, leans forward. Says naturally at slow conversational pace with emotional pause: "{lines['LINE 1']}"
CAMERA: Handheld UGC close-up, fast punch-in zoom, slight authentic shake, POV energy.
ENVIRONMENT: {background}.
LIGHTING: Moody cinematic low-key, soft blue rim light on face, natural skin tone, premium contrast.
EMOTION: Genuine surprise, curiosity, authentic not overacted.
SOUND: Subtle whoosh on zoom, ambient room tone.
TRANSITION: Seamless cut — presenter mid-sentence continuing to part 2.
{suffix}"""

    clip2 = f"""Hyper-realistic cinematic UGC YouTube Shorts — CONTINUES DIRECTLY FROM PREVIOUS CLIP.
SCENE OBJECTIVE: Deliver real value — show facts clearly on screen, build trust.
CHARACTER: Same presenter, same outfit, same environment — confident explaining expression, natural hand gestures.
ACTION: Continues speaking naturally from previous clip — NO restart. Says slowly and clearly: "{lines['LINE 2']}". Bold white text overlays appear one by one on screen: '{facts_display}' — each at exact moment mentioned, stays 2-3 seconds, large readable font. Presenter points naturally toward text.
CAMERA: Smooth gimbal medium shot, subtle rack focus from text overlay to face.
ENVIRONMENT: {background} — monitor now shows relevant tech graphics.
LIGHTING: Same moody blue ambient, monitor glow adds depth.
B-ROLL: Quick macro cut to screen showing facts, then back to presenter.
EMOTION: Confident, knowledgeable, trustworthy.
SOUND: Subtle notification sound as each fact text appears.
TRANSITION: Seamless — leading into part 3.
{suffix}"""

    clip3 = f"""Hyper-realistic cinematic UGC YouTube Shorts — CONTINUES DIRECTLY FROM PREVIOUS CLIP.
SCENE OBJECTIVE: Emotional payoff — close loop, drive follow action naturally.
CHARACTER: Same presenter, same outfit — warm knowing smile, direct confident eye contact.
ACTION: Continues from previous clip, delivers final verdict: "{lines['LINE 3']}". Turns slightly more toward camera — direct personal connection. Subtle approving nod, natural warm smile. Bold text 'FOLLOW FOR MORE' appears at bottom in clean modern font.
CAMERA: Slow cinematic push-in, turns to face camera directly.
ENVIRONMENT: {background} — slight warmer tone.
LIGHTING: Slightly warmer soft rim light, premium cinematic glow.
EMOTION: Warm, genuine, trusted friend giving real advice.
SOUND: Subtle satisfying chime on CTA text, warm ambient fade.
{suffix}"""

    return [clip1, clip2, clip3]
