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
    from langchain_groq import ChatGroq
    try:
        return get_llm().invoke(prompt)
    except Exception as e:
        if "503" in str(e) or "capacity" in str(e) or "overloaded" in str(e) or "timeout" in str(e).lower():
            print("Groq overloaded, trying llama-3.1-8b-instant...")
            try:
                return ChatGroq(model="llama-3.1-8b-instant").invoke(prompt)
            except Exception:
                print("Falling back to Gemini...")
                from langchain_google_genai import ChatGoogleGenerativeAI
                import os as _os
                gemini = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=_os.getenv("GEMINI_API_KEY"))
                return gemini.invoke(prompt)
        raise e


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