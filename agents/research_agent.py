# agents/research_agent.py
import os
from dotenv import load_dotenv
load_dotenv()

from agents.model_invoke_agent_english import safe_invoke


def research(topic):
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

    response = safe_invoke(prompt, temperature=0.5)
    return response.content