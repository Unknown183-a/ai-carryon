# agents_hindi/seo_agent.py
from langchain_groq import ChatGroq
from dotenv import load_dotenv
import json, re

load_dotenv()

llm = ChatGroq(model="llama-3.3-70b-versatile")

def generate_seo(topic, script, competitor_data=None):
    # Build competitor context if available
    competitor_context = ""
    if competitor_data:
        competitor_context = f"""
    Competitor inspiration (sirf reference ke liye, copy mat karo):
    - Channel: {competitor_data.get('channel', '')}
    - Unka title: {competitor_data.get('title', '')}
    - Unke tags: {', '.join(competitor_data.get('tags', []))}
    - Unka description: {competitor_data.get('description', '')}

    In se INSPIRATION lo but APNA ORIGINAL content banao.
    Same words mat use karo — sirf topic aur angle ka idea lo.
    """

    prompt = f"""
    Is YouTube Shorts video ke liye Hindi SEO content banao.

    Topic: {topic}
    Script: {script[:300]}
    {competitor_context}

    Rules:
    - Title pure Hindi ya Hinglish mein ho (max 60 chars)
    - Title curiosity jagaye — "ye sun ke hairan ho jaoge", "kya aap jaante hain" jaisa
    - Description 100-150 words, Hindi mein, keywords include karo
    - 15 hashtags do — Hindi + English tech mix
    - Competitor ke exact words COPY mat karo — apna style rakho
    - Copyright claim se bachne ke liye original phrasing use karo

    Ye EXACT JSON format mein return karo, kuch aur nahi:
    {{
        "title": "your hindi title here",
        "description": "your hindi description here",
        "hashtags": ["tag1", "tag2", "tag3"]
    }}
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
            "hashtags": ["hindi", "technology", "facts", "shorts", "viral",
                        "india", "tech", "trending", "ai", "techtips"]
        }
