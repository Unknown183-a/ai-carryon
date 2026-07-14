# agents_cricket/script_agent.py
from dotenv import load_dotenv
load_dotenv()


def safe_invoke(prompt):
    """Same Groq-first, Gemini-fallback pattern as agents/script_agent.py."""
    import threading
    from langchain_groq import ChatGroq
    from langchain_google_genai import ChatGoogleGenerativeAI
    import os as _os

    result = [None]

    def try_groq():
        try:
            llm = ChatGroq(model="llama-3.3-70b-versatile")
            result[0] = llm.invoke(prompt)
        except Exception as e:
            print(f"Groq failed: {e}")

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


def create_cricket_script(match_summary):
    """Analyst-style recap, 80-100 words, matches your Shorts length constraint."""
    prompt = f"""You are a cricket analyst writing a YouTube Shorts recap script.

Match data:
{match_summary}

STRICT RULES:
- Total word count: EXACTLY 80 to 100 words
- First line MUST be a hook — the turning point, a record, or a shocking stat
- Fast-paced, punchy sentences, analyst tone (like a sports recap channel)
- Mention the standout player and the key moment (a collapse, a chase, a record)
- End with "Follow for more cricket recaps"
- Plain text only, NO symbols, NO hashtags, NO stage directions, NO labels like "Hook:"

Return ONLY the script text, nothing else."""

    response = safe_invoke(prompt)
    script = response.content.strip()

    words = script.split()
    for attempt in range(2):
        if len(words) >= 80:
            break
        prompt2 = (
            f"This script is only {len(words)} words. Expand it to EXACTLY 90 words.\n"
            f"Keep the same hook and topic, add specific stats.\n"
            f"Return ONLY the expanded script.\n\nScript:\n{script}"
        )
        script = safe_invoke(prompt2).content.strip()
        words = script.split()

    if len(words) > 100:
        script = " ".join(words[:100])

    return script
