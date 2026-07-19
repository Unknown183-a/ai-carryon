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


def create_cricket_script(match_summary, standout_player=None):
    """One-moment highlight script, ~30-45 seconds of speech (roughly 75-105
    words at the pace used in voice_agent.py), NOT a full match recap.
    Written in Hindi (Devanagari script) so it matches the Sarvam hi-IN voice."""
    focus_line = (
        f"AAPKO ISI EK PLAYER KE MOMENT PAR FOCUS KARNA HAI: {standout_player}. "
        f"Sirf isi player ke performance/moment ko highlight karein."
    ) if standout_player else ""
    prompt = f"""Aap ek cricket analyst hain jo YouTube Shorts ke liye script likhte hain.
Script poori tarah HINDI mein likhein, Devanagari lipi mein — koi English translation ya
Hinglish nahi.

Match data:
{match_summary}

BAHUT ZAROORI: Pura match recap MAT karein. Sirf ek sabse interesting/shocking
moment ya highlight chunein (jaise ek match-winning over, ek record-breaking
shot, ek dramatic collapse, ya ek standout player ka key moment) aur SIRF
uss ek moment par poori script focus karein.

{focus_line}
SAKHT NIYAM (STRICT RULES):
- Yeh 30-45 second ka audio hona chahiye — kul shabd sankhya: 75 se 105 shabd
- Pehli line ek HOOK honi chahiye us specific moment ke baare mein
- Sirf EK moment par tikey rahein, poora match cover mat karein
- Tez raftar, chhoti-chhoti punchy sentences, sports analyst wala tone
- Us moment se juda standout player ka naam zaroor lein
- Aakhri line: "Aur cricket recaps ke liye follow karein"
- Sirf plain Hindi text, koi symbols nahi, koi hashtags nahi, koi stage directions
  nahi, koi labels jaise "Hook:" nahi

Sirf script text return karein, Devanagari mein, aur kuch nahi."""

    response = safe_invoke(prompt)
    script = response.content.strip()

    words = script.split()
    for attempt in range(2):
        if len(words) >= 75:
            break
        prompt2 = (
            f"Yeh script sirf {len(words)} shabd ka hai. Ise 90 shabd tak badhayein.\n"
            f"Wahi ek moment aur hook rakhein — poora match cover MAT karein.\n"
            f"Poori tarah Hindi (Devanagari) mein likhein.\n"
            f"Sirf expanded script return karein.\n\nScript:\n{script}"
        )
        script = safe_invoke(prompt2).content.strip()
        words = script.split()

    if len(words) > 105:
        script = " ".join(words[:105])

    return script
