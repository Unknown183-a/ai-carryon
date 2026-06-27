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
    prompt = f"""From this YouTube Shorts script, extract exactly 2-3 KEY FACTS for on-screen display.
Topic: {topic}
Script: {script}
Rules: SPECIFIC numbers/prices/dates, max 6 words each.
Good: "Battery 40% bigger", "Price drops $100"
Bad: "Much improved", "Better than before"
Return ONLY a Python list: ["fact 1", "fact 2", "fact 3"]"""
    try:
        import re, json
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

    # Step 1: Write one continuous presenter monologue, then split into 3 parts
    monologue_prompt = f"""You are a YouTube Shorts presenter. Write ONE continuous spoken monologue about this topic.
The monologue will be split into 3 video clips — so write it as one unbroken speech.

Topic: {topic}
Key facts to include: {facts_display}
Research: {script}

Rules:
- Total: exactly 3 sentences per part, 9 sentences total
- Part 1 (Hook): Open with shocking question or fact. Do NOT answer yet. End with "...and here's what nobody tells you"
- Part 2 (Facts): Continue directly. Reveal the actual facts: {facts_display}. End with "...but the best part?"
- Part 3 (Payoff): Deliver the final punchline. Close the loop. End with "Follow for more like this."
- Natural spoken English, fast punchy sentences
- No labels, no "Part 1:", just the continuous speech

Return EXACTLY this format:
PART1: <3 sentences — hook>
PART2: <3 sentences — facts, continues from part1>
PART3: <3 sentences — payoff, closes loop>"""

    monologue_response = safe_invoke(monologue_prompt).content.strip()

    parts = {"PART1": "", "PART2": "", "PART3": ""}
    for line in monologue_response.split("\n"):
        line = line.strip()
        for key in parts:
            if line.upper().startswith(key + ":"):
                parts[key] = line.split(":", 1)[1].strip()

    # Fallback if parsing fails
    if not parts["PART1"]:
        parts["PART1"] = f"Did you know {topic} just changed everything? Nobody is talking about this. And here's what nobody tells you..."
        parts["PART2"] = f"Here are the facts: {facts_display}. This is exactly what makes it different. But the best part?"
        parts["PART3"] = f"This is why everyone is switching right now. Now you know the real story. Follow for more like this."

    # Step 2: Wrap each part in cinematic scene description
    character = "26-year-old Indian male, short neat black hair, light stubble, sharp jawline, dark navy crew-neck t-shirt, slim build, natural skin tone, no glasses"
    suffix = "9:16 vertical, 8 seconds, photorealistic, cinematic UGC style, consistent character: 26-year-old Indian male short black hair dark navy t-shirt"

    clip1 = (
        f"Handheld UGC close-up of {character}, shocked curious expression, fast punch-in zoom first 2 seconds, "
        f"looks directly at camera and speaks: \"{parts['PART1']}\" — leans forward eyes wide does not reveal answer yet, "
        f"dark futuristic studio cyan holographic panels moody blue rim light flickering. {suffix}"
    )

    clip2 = (
        f"Smooth gimbal medium shot of {character}, confident explaining expression, "
        f"CONTINUES speaking directly from previous clip without any restart: \"{parts['PART2']}\" — "
        f"points at large holographic display showing bold readable glowing text '{facts_display}' "
        f"appearing one by one as floating text cards as he explains each, "
        f"rack focus from display to face, dark studio blue ambient holographic glow. {suffix}"
    )

    clip3 = (
        f"Slow push-in on {character}, knowing smile, "
        f"CONTINUES speaking directly from previous clip: \"{parts['PART3']}\" — "
        f"turns directly to camera delivers final punchline closes the loop, "
        f"holographic text 'FOLLOW FOR MORE' floats in foreground, "
        f"premium soft cyan rim light dark background subtle glow. {suffix}"
    )

    return [clip1, clip2, clip3]
