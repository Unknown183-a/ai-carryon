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

    # Step 1: Write one continuous monologue split into 3 parts
    monologue_prompt = f"""You are a YouTube Shorts presenter. Write ONE continuous spoken monologue about this topic.
Split into 3 parts — written as one unbroken natural conversation.

Topic: {topic}
Key facts: {facts_display}
Research: {script}

Rules:
- Part 1 (Hook): Shocking opening, do NOT answer yet, end with "...and here's what nobody tells you"
- Part 2 (Facts): Continue directly, reveal facts: {facts_display}, speak slowly and clearly, end with "...but the best part?"
- Part 3 (Payoff): Final punchline, close the loop, end with "Follow for more like this."
- Natural conversational pace — NOT rushed, speak like a real person explaining to a friend
- Short punchy sentences with natural pauses between them

Return EXACTLY:
PART1: <3 sentences>
PART2: <3 sentences — slow clear explanation of facts>
PART3: <3 sentences>"""

    monologue_response = safe_invoke(monologue_prompt).content.strip()

    parts = {"PART1": "", "PART2": "", "PART3": ""}
    for line in monologue_response.split("\n"):
        line = line.strip()
        for key in parts:
            if line.upper().startswith(key + ":"):
                parts[key] = line.split(":", 1)[1].strip()

    if not parts["PART1"]:
        parts["PART1"] = f"Did you know {topic} just changed everything? Nobody is talking about this. And here's what nobody tells you..."
        parts["PART2"] = f"Here are the facts: {facts_display}. Each one matters more than you think. But the best part?"
        parts["PART3"] = f"This is why everyone is switching right now. Now you know the real story. Follow for more like this."

    # Step 2: Build cinematic prompts around YOUR avatar
    # Background: realistic home studio / tech setup — not AI generated looking
    background = (
        "realistic home studio background, dark walls, soft RGB LED strip lighting in blue and purple, "
        "a desk with a monitor showing tech graphics, bookshelf with books, "
        "shallow depth of field, cinematic look, real room not CGI"
    )

    suffix = "9:16 vertical, 8 seconds, photorealistic, cinematic, natural lighting, real environment, NOT CGI, NOT generated looking"

    clip1 = (
        f"Avatar presenter, shocked curious expression, looks directly at camera, "
        f"speaks naturally at SLOW conversational pace with clear pauses between sentences: \"{parts['PART1']}\" "
        f"leans forward slightly, eyes wide, natural hand gesture, "
        f"{background}, fast punch-in zoom in first 2 seconds. {suffix}"
    )

    clip2 = (
        f"Avatar presenter, confident calm expression, continues speaking directly from previous clip at SLOW clear pace: \"{parts['PART2']}\" "
        f"Bold readable text overlays appear on screen one by one showing: '{facts_display}' "
        f"each fact appears as large white bold caption text at the exact moment he mentions it, "
        f"text stays on screen for 2-3 seconds before next fact appears, "
        f"presenter points toward the text naturally, "
        f"{background}, smooth gimbal medium shot. {suffix}"
    )

    clip3 = (
        f"Avatar presenter, warm knowing smile, continues speaking from previous clip at natural relaxed pace: \"{parts['PART3']}\" "
        f"turns slightly more toward camera for direct eye contact, "
        f"bold text 'FOLLOW FOR MORE' appears at bottom of screen, "
        f"subtle approving nod at the end, "
        f"{background}, slow push-in shot. {suffix}"
    )

    return [clip1, clip2, clip3]
