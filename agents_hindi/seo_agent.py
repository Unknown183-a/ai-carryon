# agents_hindi/seo_agent.py
from langchain_groq import ChatGroq
def get_llm():
    from langchain_groq import ChatGroq
    try:
        llm = ChatGroq(model="llama-3.3-70b-versatile")
        llm.invoke("hi")
        return llm
    except Exception as e:
        if "503" in str(e) or "capacity" in str(e) or "over_capacity" in str(e) or "overloaded" in str(e):
            print("Falling back to llama3-8b-8192")
            return ChatGroq(model="llama3-8b-8192")
        return ChatGroq(model="llama3-8b-8192")


llm = get_llm()

def generate_seo(topic, script, competitor_data=None):
    competitor_context = ""
    if competitor_data:
        competitor_context = f"""
Trending reference (inspiration only - rewrite everything originally):
- Trending topic: {competitor_data.get('topic', '')}
- Why trending: {competitor_data.get('why_trending', '')}
- Suggested tags: {', '.join(competitor_data.get('tags', []))}
- Suggested description: {competitor_data.get('description', '')}

In tags aur description se INSPIRATION lo.
Exact words COPY mat karo — copyright claim aayega.
Apne original words mein likho same topic par.
"""

    prompt = f"""
Is YouTube Shorts video ke liye ORIGINAL Hindi SEO banao.

Topic: {topic}
Script: {script[:300]}
{competitor_context}

Rules:
- Title Hindi/Hinglish mein (max 60 chars)
- Title curiosity jagaye — shocking, surprising angle lo
- Description 100-150 words, Hindi mein, original likho
- 15 hashtags — Hindi + English tech mix
- Competitor ke exact words BILKUL copy mat karo
- Copyright se bachne ke liye apna unique angle lo

Ye EXACT JSON format mein return karo:
{{
    "title": "your original hindi title",
    "description": "your original hindi description",
    "hashtags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10", "tag11", "tag12", "tag13", "tag14", "tag15"]
}}
"""

    response = llm.invoke(prompt).content.strip()
    response = re.sub(r'^```json\n?', '', response)
    response = re.sub(r'^```\n?', '', response)
    response = re.sub(r'\n?```$', '', response)

    try:
        data = json.loads(response)
        # Use competitor tags as additional tags if available
        if competitor_data and competitor_data.get('tags'):
            existing = data.get('hashtags', [])
            extra = [t for t in competitor_data['tags'] if t not in existing]
            data['hashtags'] = (existing + extra)[:20]
        return data
    except:
        return {
            "title": f"{topic} - Hindi Facts",
            "description": f"{topic} ke baare mein amazing facts. {script[:100]}",
            "hashtags": ["hindi", "technology", "facts", "shorts", "viral",
                        "india", "tech", "trending", "ai", "techtips",
                        "hinditech", "indiantech", "techshorts", "viralshorts", "techfacts"]
        }
