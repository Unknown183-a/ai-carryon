from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.5
)

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

    response = llm.invoke(prompt)

    return response.content