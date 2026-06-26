# agents_hindi/seo_agent.py
import re
import json


def safe_invoke(prompt):
    import threading
    from langchain_groq import ChatGroq
    from langchain_google_genai import ChatGoogleGenerativeAI
    import os as _os

    result = [None]

    def try_groq():
        try:
            llm = ChatGroq(model="llama-3.3-70b-versatile")
            result[0] = llm.invoke(prompt)
        except Exception:
            pass

    t = threading.Thread(target=try_groq)
    t.start()
    t.join(timeout=20)

    if result[0] is not None:
        return result[0]

    print("Groq timeout/fail — falling back to Gemini Flash")
    try:
        gemini = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=_os.getenv("GEMINI_API_KEY")
        )
        return gemini.invoke(prompt)
    except Exception:
        from langchain_groq import ChatGroq
        return ChatGroq(model="llama-3.1-8b-instant").invoke(prompt)


def generate_seo(topic, script, comparison_insights=None, competitor_data=None):
    # Build context from comparison insights (Phase 2)
    competitor_context = ""
    if comparison_insights and not comparison_insights.get("error"):
        top_title = comparison_insights.get("top_competitor_title", "")
        top_views = comparison_insights.get("top_competitor_views", 0)
        if top_title:
            competitor_context = f"""
COMPETITOR INTELLIGENCE:
- Is topic par sabse popular title: "{top_title}" ({top_views:,} views)
- Iska style dekho par COPY mat karo — better aur original likho
"""
    # Fallback to old competitor_data format (from spy agent)
    elif competitor_data:
        competitor_context = f"""
Trending reference (inspiration only):
- Trending topic: {competitor_data.get('topic', '')}
- Why trending: {competitor_data.get('why_trending', '')}
- Suggested tags: {', '.join(competitor_data.get('tags', []))}
In tags aur description se INSPIRATION lo. Exact words COPY mat karo.
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

    response = safe_invoke(prompt).content.strip()
    response = re.sub(r'^```json\n?', '', response)
    response = re.sub(r'^```\n?', '', response)
    response = re.sub(r'\n?```$', '', response)

    try:
        data = json.loads(response)
        if competitor_data and competitor_data.get('tags'):
            existing = data.get('hashtags', [])
            extra = [t for t in competitor_data['tags'] if t not in existing]
            data['hashtags'] = (existing + extra)[:20]
        return data
    except Exception:
        return {
            "title": f"{topic} - Hindi Facts",
            "description": f"{topic} ke baare mein amazing facts. {script[:100]}",
            "hashtags": ["hindi", "technology", "facts", "shorts", "viral",
                        "india", "tech", "trending", "ai", "techtips",
                        "hinditech", "indiantech", "techshorts", "viralshorts", "techfacts"]
        }
