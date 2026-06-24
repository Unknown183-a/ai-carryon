# agents/research_agent.py
import os
from dotenv import load_dotenv
load_dotenv()

def get_llm():
    from langchain_groq import ChatGroq
    try:
        llm = ChatGroq(model="llama-3.3-70b-versatile")
        llm.invoke("hi")
        return llm
    except Exception:
        return ChatGroq(model="llama3-8b-8192")


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

    response = llm.invoke(prompt)
    return response.content