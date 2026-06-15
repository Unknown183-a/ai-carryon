# agents_hindi/seo_agent.py
from langchain_groq import ChatGroq
from dotenv import load_dotenv
import json, re

load_dotenv()

llm = ChatGroq(model="llama-3.3-70b-versatile")

def generate_seo(topic, script):
    prompt = f"""
    Is YouTube Shorts video ke liye Hindi SEO content banao.

    Topic: {topic}
    Script: {script[:300]}

    Ye JSON format mein return karo:
    {{
        "title": "Catchy Hindi title (max 60 chars, Hindi mein)",
        "description": "Hindi description (150 words, keywords include karo)",
        "hashtags": ["hindi", "technology", "facts", "shorts", "viral"]
    }}

    Rules:
    - Title pure Hindi ya Hinglish mein ho
    - Title curiosity jagaye - "kya aap jaante hain", "ye sun ke hairan ho jaoge" jaisa
    - Description mein Hindi keywords use karo
    - 10-15 hashtags do — mix of Hindi + English tech hashtags
    - Sirf JSON return karo, kuch aur nahi
    """

    response = llm.invoke(prompt).content.strip()
    response = re.sub(r'^```json\n?', '', response)
    response = re.sub(r'^```\n?', '', response)
    response = re.sub(r'\n?```$', '', response)

    try:
        return json.loads(response)
    except:
        return {
            "title": f"{topic} - Hindi Facts",
            "description": f"{topic} ke baare mein amazing facts. {script[:100]}",
            "hashtags": ["hindi", "technology", "facts", "shorts", "viral", "india"]
        }
