# agents/research_agent.py
import os
from dotenv import load_dotenv
load_dotenv()

def get_llm():
    from langchain_groq import ChatGroq
    try:
        llm = ChatGroq(model="llama-3.3-70b-versatile", request_timeout=15)
        safe_invoke("hi")
        return llm
    except Exception:
        return ChatGroq(model="llama-3.1-8b-instant")


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
    t.join(timeout=20)  # Wait max 20 seconds

    if result[0] is not None:
        return result[0]

    # Groq timed out or failed — use Gemini
    print("Groq timeout/fail — falling back to Gemini Flash")
    try:
        gemini = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=_os.getenv("GEMINI_API_KEY")
        )
        return gemini.invoke(prompt)
    except Exception:
        # Last resort — llama-3.1-8b-instant
        return ChatGroq(model="llama-3.1-8b-instant").invoke(prompt)


def research(topic):
    from langchain_groq import ChatGroq
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.5
    )

    prompt = f"""
    Research the following topic:

    {topic}

    Give:

    1. Important facts
    2. Interesting hook
    3. Key points
    4. Latest information

    Keep response concise.
    """

    response = safe_invoke(prompt)
    return response.content