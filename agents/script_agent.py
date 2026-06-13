from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.8
)

def create_script(research_data):

    prompt = f"""
    Create a YouTube Short.

    Duration: 45 seconds

    Style:
    - Fast paced
    - Engaging
    - Fireship style

    Content:

    {research_data}

    Format:

    Hook
    Main Content
    CTA

    Keep it under 120 words.
    """

    response = llm.invoke(prompt)

    return response.content