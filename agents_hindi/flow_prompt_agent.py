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
Good: "Battery 40% zyada", "Price sirf ₹999"
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

    # Step 1: Write one continuous Hinglish monologue, split into 3 parts
    monologue_prompt = f"""You are a Hindi YouTube Shorts presenter. Write ONE continuous Hinglish monologue about this topic.
The monologue will be split into 3 video clips — write it as one unbroken speech.

Topic: {clean_topic}
Key facts to include: {facts_display}
Script: {script}

Rules:
- Total: exactly 3 sentences per part, 9 sentences total
- Hinglish (Hindi + English mix), natural conversational tone
- Part 1 (Hook): Open with shocking Hinglish question. Do NOT answer yet. End with "...aur yeh sun ke dimaag ghoom jayega"
- Part 2 (Facts): Continue directly from Part 1. Reveal facts: {facts_display}. End with "...aur sabse mast part?"
- Part 3 (Payoff): Deliver final punchline. Close the loop. End with "Aisa content chahiye toh follow karo."
- No labels, just continuous speech

Return EXACTLY:
PART1: <3 Hinglish sentences — hook>
PART2: <3 Hinglish sentences — facts, continues from part1>
PART3: <3 Hinglish sentences — payoff, closes loop>"""

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

    character = "26-year-old Indian male, short neat black hair, light stubble, sharp jawline, dark navy crew-neck t-shirt, slim build, wheatish skin tone, no glasses, natural Hindi speaker expressions"
    suffix = "9:16 vertical, 8 seconds, photorealistic, cinematic UGC style, Hindi tech creator, consistent character: 26-year-old Indian male short black hair dark navy t-shirt"

    clip1 = (
        f"Handheld UGC close-up of {character}, shocked curious expression, fast punch-in zoom first 2 seconds, "
        f"looks directly at camera speaking Hinglish: \"{parts['PART1']}\" — leans forward eyes wide hands gesturing expressively does not reveal answer yet, "
        f"dark futuristic studio saffron orange holographic panels moody warm rim light flickering. {suffix}"
    )

    clip2 = (
        f"Smooth gimbal medium shot of {character}, confident explaining expression, "
        f"CONTINUES speaking directly from previous clip no restart: \"{parts['PART2']}\" — "
        f"points at large holographic display showing bold readable glowing Hinglish text '{facts_display}' "
        f"appearing one by one as floating text cards as he explains each fact, "
        f"rack focus from display to face, dark studio saffron orange ambient holographic glow. {suffix}"
    )

    clip3 = (
        f"Slow push-in on {character}, knowing confident smile, "
        f"CONTINUES speaking directly from previous clip: \"{parts['PART3']}\" — "
        f"turns directly to camera delivers final verdict closes the loop started in clip 1, "
        f"holographic text 'FOLLOW KARO' floats in foreground, "
        f"premium soft saffron rim light warm tone dark background. {suffix}"
    )

    return [clip1, clip2, clip3]
