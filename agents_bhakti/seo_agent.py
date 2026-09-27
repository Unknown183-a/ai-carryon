# agents_bhakti/seo_agent.py
import re
import json

from agents_bhakti.model_invoke_agent_bhakti import safe_invoke

DEFAULT_HASHTAGS = [
    "bhakti", "bhaktistatus", "shorts", "jaishriram", "harharmahadev",
    "radheradhe", "hanumanji", "bholenath", "krishna", "ram",
    "devotional", "hindudharm", "spiritual", "temple", "viral",
]


def generate_seo(topic, script, comparison_insights=None, competitor_data=None):
    competitor_context = ""
    if comparison_insights and not comparison_insights.get("error"):
        top_title = comparison_insights.get("top_competitor_title", "")
        top_views = comparison_insights.get("top_competitor_views", 0)
        if top_title:
            competitor_context = f"""
COMPETITOR INTELLIGENCE:
- Is topic par sabse popular title: "{top_title}" ({top_views:,} views)
- Iska style dekho par COPY mat karo — apna original aur respectful likho
"""
    elif competitor_data:
        competitor_context = f"""
Trending reference (inspiration only):
- Trending topic: {competitor_data.get('topic', '')}
- Why trending: {competitor_data.get('why_trending', '')}
"""

    prompt = f"""
Is YouTube Shorts devotional (Bhakti) video ke liye ORIGINAL Hindi SEO banao.

Topic: {topic}
Script: {script[:300]}
{competitor_context}

Rules:
- Title Hindi/Hinglish mein (max 60 chars), shraddha jagaye — jaise blessing
  ya story-hook style ("Jai Shri Ram", "Yeh Kahani Aapko Rula Degi", etc.)
- Title mein kisi devta ka apmaan ya galat baat NAHI honi chahiye
- Description 100-150 words, Hindi mein, respectful aur original
- 15 hashtags — devotional Hindi + English mix (bhakti, deity names, festival
  names, #shorts, etc.)
- Competitor ke exact words BILKUL copy mat karo

Ye EXACT JSON format mein return karo:
{{
    "title": "your original hindi devotional title",
    "description": "your original hindi devotional description",
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
            "title": f"{topic[:50]} 🙏",
            "description": f"{topic} — ek bhakti bhari kahani. {script[:100]}",
            "hashtags": DEFAULT_HASHTAGS,
        }
