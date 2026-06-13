# agents/seo_agent.py
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

llm = ChatGroq(model="llama-3.3-70b-versatile")


def generate_seo(topic, script):
    prompt = f"""
    Based on the topic and script below, generate YouTube SEO content.

    Topic: {topic}
    Script: {script}

    Return your response in EXACTLY this format, with no extra text:

    TITLE: <a catchy, click-worthy YouTube title under 60 characters>
    DESCRIPTION: <a 2-3 sentence engaging description>
    HASHTAGS: <10 relevant hashtags, space-separated, each starting with #>
    """

    response = llm.invoke(prompt).content

    title = ""
    description = ""
    hashtags = ""

    for line in response.split("\n"):
        line = line.strip()
        if line.upper().startswith("TITLE:"):
            title = line.split(":", 1)[1].strip()
        elif line.upper().startswith("DESCRIPTION:"):
            description = line.split(":", 1)[1].strip()
        elif line.upper().startswith("HASHTAGS:"):
            hashtags = line.split(":", 1)[1].strip()

    return {
        "title": title,
        "description": description,
        "hashtags": hashtags
    }