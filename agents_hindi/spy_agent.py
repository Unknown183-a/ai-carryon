# agents_hindi/spy_agent.py
import os
import json
import time
import re
import random
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def get_hindi_trending_topics():
    CACHE_FILE = "output/spy_cache_hindi.json"

    # Cache valid for 30 min only
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            cache = json.load(f)
        if time.time() - cache["timestamp"] < 1800:
            return cache["topics"]

    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    # Random seed to force different results every time
    random_seed = random.randint(1000, 9999)
    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    prompt = f"""
Current date and time: {today}
Random seed: {random_seed}

You are a YouTube trend analyst for India. Find 10 DIFFERENT trending Hindi tech topics 
that are viral RIGHT NOW today in India.

Search for these specifically:
- Latest smartphone launched in India today
- Latest AI news in India today  
- Trending app in India today
- Viral tech fact in Hindi today
- Latest gadget review trending in India

For each topic, make sure it is:
1. DIFFERENT from common topics (no Samsung S23, no basic AI facts)
2. Specific and current — mention actual product names, dates, prices
3. Something Indians would search TODAY

Return JSON array of 10 items:
[
  {{
    "channel": "type of channel eg: Tech Review, AI News",
    "title": "catchy hindi title for this topic",
    "topic": "specific topic in english with details",
    "why_trending": "exact reason trending today in India",
    "tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8","tag9","tag10"],
    "description": "50 word hindi description",
    "views": 150000
  }}
]

Return ONLY the JSON array. Make all 10 topics UNIQUE and DIFFERENT from each other.
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,  # High temperature = more variety
            max_tokens=2000
        )

        content = response.choices[0].message.content or ""
        content = content.strip()
        content = re.sub(r'^```json\n?', '', content)
        content = re.sub(r'^```\n?', '', content)
        content = re.sub(r'\n?```$', '', content)

        topics = json.loads(content)
        if not isinstance(topics, list):
            topics = []

    except Exception as e:
        print(f"Groq error: {e}")
        topics = []

    # Normalize
    result = []
    for i, t in enumerate(topics):
        result.append({
            'channel': t.get('channel', 'Hindi Tech'),
            'title': t.get('title', t.get('topic', '')),
            'topic': t.get('topic', ''),
            'why_trending': t.get('why_trending', ''),
            'tags': t.get('tags', ['hindi', 'tech', 'shorts', 'viral', 'india']),
            'description': t.get('description', ''),
            'views': t.get('views', random.randint(50000, 500000)),
            'likes': t.get('likes', 0),
            'published': 'Today',
            'url': f"https://youtube.com",
        })

    os.makedirs("output", exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump({"timestamp": time.time(), "topics": result}, f)

    return result


def get_best_hindi_topic():
    topics = get_hindi_trending_topics()
    if topics:
        return random.choice(topics[:5])  # Random from top 5
    return None
