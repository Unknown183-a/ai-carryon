# agents/script_agent.py
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

llm = ChatGroq(model="llama-3.3-70b-versatile")

def create_script(research_data):
    prompt = f"""
    Write a YouTube Shorts script (60-80 words max) based on this research.

    Rules:
    - Sound like a real human talking, NOT a robot
    - Use natural conversational language: "So basically...", "Here's the thing...", "Right?", "And honestly..."
    - Short punchy sentences. Never more than 10 words per sentence.
    - Start with a shocking/curiosity hook in the first 3 seconds
    - NO labels like "Hook:", "CTA:", no timestamps, no quotes
    - End with a quick CTA like "Follow for more"
    - Write ONLY the spoken words, nothing else

    Research: {research_data}

    Example style:
    So this AI tool just changed everything. Seriously. It can write code, debug it, and deploy it — all by itself. No human needed. That's kind of insane, right? And the crazy part? It's completely free. This is LangChain. And if you're not using it yet, you're already behind. Follow for more.
    """

    response = llm.invoke(prompt).content
    return response.strip()
