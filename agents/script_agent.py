from dotenv import load_dotenv
load_dotenv()

HOOK_TEMPLATES = [
    "Nobody talks about the fact that {topic_angle}...",
    "Most developers get {topic_angle} completely wrong.",
    "In 30 seconds I'll show you {topic_angle} that changes everything.",
    "Everyone says {topic_angle} is the future. They're wrong.",
    "If you use {topic_angle}, stop what you're doing right now.",
]


def get_llm(temperature=0.7):
    from langchain_groq import ChatGroq
    try:
        llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=temperature)
        safe_invoke("hi")
        return llm
    except Exception:
        return ChatGroq(model="llama-3.1-8b-instant", temperature=temperature)


def safe_invoke(prompt):
    import threading
    from langchain_groq import ChatGroq
    from langchain_google_genai import ChatGoogleGenerativeAI
    import os as _os

    result = [None]
    error = [None]

    def try_groq():
        try:
            llm = ChatGroq(model="llama-3.3-70b-versatile")
            result[0] = llm.invoke(prompt)
        except Exception as e:
            error[0] = e

    t = threading.Thread(target=try_groq)
    t.start()
    t.join(timeout=20)

    if result[0] is not None:
        return result[0]

    print("Groq timeout/fail — falling back to Gemini Flash")
    try:
        gemini = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=_os.getenv("GEMINI_API_KEY")
        )
        return gemini.invoke(prompt)
    except Exception:
        return ChatGroq(model="llama-3.1-8b-instant").invoke(prompt)


def score_hook(hook, llm):
    prompt = (
        f"Score this YouTube Shorts opening line for viewer retention (1-10).\n"
        f"A 10 makes people stop scrolling immediately. A 1 is boring.\n"
        f"Hook: '{hook}'\n\n"
        f"Consider: curiosity gap, urgency, specificity, emotional trigger.\n"
        f"Return ONLY a number 1-10, nothing else."
    )
    try:
        result = safe_invoke(prompt).content.strip()
        return int(''.join(filter(str.isdigit, result[:3])) or '5')
    except Exception:
        return 5


def improve_hook(hook, topic, llm):
    import random
    template = random.choice(HOOK_TEMPLATES)
    prompt = (
        f"Rewrite this weak YouTube Shorts hook using this template style:\n"
        f"Template: {template}\n"
        f"Topic: {topic}\n"
        f"Current hook: '{hook}'\n\n"
        f"Rules:\n"
        f"- Maximum 10 words\n"
        f"- Must create immediate curiosity or urgency\n"
        f"- Must be specific to the topic\n"
        f"- No clickbait — must be truthful\n"
        f"Return ONLY the new hook line, nothing else."
    )
    return safe_invoke(prompt).content.strip()


def create_script(research_data, topic=None, comparison_insights=None):
    llm = get_llm(temperature=0.8)

    # Build competitor context if available
    competitor_context = ""
    if comparison_insights and not comparison_insights.get("error"):
        top_title    = comparison_insights.get("top_competitor_title", "")
        avg_views    = comparison_insights.get("competitor_avg_views", 0)
        avg_duration = comparison_insights.get("competitor_avg_duration_seconds", 0)
        recs         = comparison_insights.get("recommendations", [])
        competitor_context = f"""
COMPETITOR INTELLIGENCE (use this to write a better script):
- Top performing video on this topic: "{top_title}"
- Competitor average views: {avg_views:,}
- Competitor average duration: {avg_duration}s — match this length
- Recommendations from analysis: {'; '.join(recs[:2]) if recs else 'None'}
"""

    prompt = f"""Create a YouTube Shorts script based on this research:

{research_data}
{competitor_context}

STRICT RULES:
- Total word count: EXACTLY 80 to 100 words
- Must be 25-35 seconds when spoken aloud
- First line MUST be a hook that stops scrolling — use one of these styles:
  * Shocking fact: "Nobody knows that [specific fact]..."
  * Direct challenge: "Most people get [topic] completely wrong."
  * Urgency: "In 30 seconds you'll understand [topic] better than 99% of people."
  * Contrarian: "Everyone thinks [topic] is [X]. It's actually [Y]."
  * Personal stakes: "If you use [topic], this affects you right now."
- Fast paced, Fireship style — short punchy sentences
- End with "Follow for more AI and tech insights"
- Plain text only, NO symbols, NO hashtags, NO stage directions
- NO labels like "Hook:" or "CTA:" — just spoken words

Return ONLY the script text, nothing else."""

    response = safe_invoke(prompt)
    script = response.content.strip()

    for attempt in range(3):
        words = script.split()
        if len(words) >= 80:
            break
        prompt2 = (
            f"This script is only {len(words)} words. Expand it to EXACTLY 90 words.\n"
            f"Keep the same hook, style, and topic. Add specific facts, numbers, or examples.\n"
            f"Return ONLY the expanded script, no labels, no explanations.\n\n"
            f"Script to expand:\n{script}"
        )
        script = safe_invoke(prompt2).content.strip()
        print(f"Expansion attempt {attempt+1}: {len(script.split())} words")

    words = script.split()
    if len(words) > 100:
        script = " ".join(words[:100])

    first_sentence = script.split('.')[0].strip()
    hook_score = score_hook(first_sentence, llm)
    print(f"Hook score: {hook_score}/10 — '{first_sentence[:60]}...'")

    if hook_score < 7:
        print("Hook too weak — rewriting...")
        topic_hint = topic or research_data[:50]
        new_hook = improve_hook(first_sentence, topic_hint, llm)
        rest_of_script = script[len(first_sentence):].lstrip('. ')
        script = new_hook + ". " + rest_of_script
        new_score = score_hook(new_hook, llm)
        print(f"Improved hook score: {new_score}/10 — '{new_hook}'")

    return script
