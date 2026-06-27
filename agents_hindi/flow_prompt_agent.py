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


def extract_hindi_facts(script, topic):
    prompt = f"""From this Hindi YouTube Shorts script, extract exactly 2-3 KEY FACTS for on-screen display.
Topic: {topic}
Script: {script}
Rules: SPECIFIC numbers/prices in Hinglish, max 6 words each.
Good: "Battery 40% zyada", "Price sirf Rs 999"
Bad: "Bahut achha", "Better than before"
Return ONLY a Python list: ["fact 1", "fact 2", "fact 3"]"""
    try:
        import re, json
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

    # Step 1: Write one continuous Hinglish monologue
    monologue_prompt = f"""You are a Hindi YouTube Shorts presenter. Write ONE continuous Hinglish monologue.
Split into 3 parts — one unbroken natural conversation.

Topic: {clean_topic}
Key facts: {facts_display}
Script: {script}

Rules:
- Part 1 (Hook): Shocking Hinglish opening, do NOT answer yet, end with "...aur yeh sun ke dimaag ghoom jayega"
- Part 2 (Facts): Continue directly, reveal facts slowly and clearly: {facts_display}, end with "...aur sabse mast part?"
- Part 3 (Payoff): Final verdict, close the loop, end with "Aisa content chahiye toh follow karo."
- Natural conversational pace — SLOW and clear, like explaining to a friend, NOT rushed
- Short sentences with natural pauses

Return EXACTLY:
PART1: <3 Hinglish sentences>
PART2: <3 Hinglish sentences — slow clear facts>
PART3: <3 Hinglish sentences>"""

    monologue_response = safe_invoke(monologue_prompt).content.strip()

    parts = {"PART1": "", "PART2": "", "PART3": ""}
    for line in monologue_response.split("\n"):
        line = line.strip()
        for key in parts:
            if line.upper().startswith(key + ":"):
                parts[key] = line.split(":", 1)[1].strip()

    if not parts["PART1"]:
        parts["PART1"] = f"Yaar suno, {clean_topic} ke baare mein ek baat hai jo koi nahi batata. Sach mein yeh jaankar hairan ho jaoge. Aur yeh sun ke dimaag ghoom jayega..."
        parts["PART2"] = f"Toh yeh hain asli facts: {facts_display}. Yahi cheez isse baaki sab se alag banati hai. Aur sabse mast part?"
        parts["PART3"] = f"Isliye aajkal sablog iske baare mein baat kar rahe hain. Ab tum jaante ho {clean_topic} ka poora sach. Aisa content chahiye toh follow karo."

    # Realistic background for Hindi channel
    background = (
        "realistic Indian home studio background, warm lighting, soft LED strip lights, "
        "a desk with laptop showing tech content, plants in background, "
        "shallow depth of field, cinematic feel, real room not CGI, warm Indian home aesthetic"
    )

    suffix = "9:16 vertical, 8 seconds, photorealistic, cinematic, natural lighting, real environment, NOT CGI, NOT generated looking"

    clip1 = (
        f"Avatar presenter, shocked curious expression, looks directly at camera, "
        f"speaks Hinglish at SLOW natural conversational pace with clear pauses: \"{parts['PART1']}\" "
        f"leans forward slightly eyes wide natural expressive Indian hand gestures, "
        f"{background}, fast punch-in zoom first 2 seconds. {suffix}"
    )

    clip2 = (
        f"Avatar presenter, confident calm expression, continues speaking from previous clip at SLOW clear pace: \"{parts['PART2']}\" "
        f"Bold readable Hinglish text overlays appear on screen one by one: '{facts_display}' "
        f"each fact appears as large white bold caption at exact moment he mentions it, "
        f"text stays 2-3 seconds before next appears, "
        f"presenter points toward text naturally with Indian hand gesture, "
        f"{background}, smooth gimbal medium shot. {suffix}"
    )

    clip3 = (
        f"Avatar presenter, warm confident smile, continues from previous clip at relaxed natural pace: \"{parts['PART3']}\" "
        f"turns slightly more toward camera direct eye contact, "
        f"bold text 'FOLLOW KARO' appears at bottom of screen, "
        f"subtle approving nod at end, "
        f"{background}, slow push-in shot. {suffix}"
    )

    return [clip1, clip2, clip3]
