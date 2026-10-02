# agents_hindi/spy_agent.py
import os
import json
import time
import re
import random
from datetime import datetime
from dotenv import load_dotenv
from agents_hindi.categories import normalize_category

load_dotenv()

def get_hindi_trending_topics():
    CACHE_FILE = "output/spy_cache_hindi.json"

    # Cache valid for 30 min only
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            cache = json.load(f)
        if time.time() - cache["timestamp"] < 1800:
            return cache["topics"]

    from agents_hindi.model_invoke_agent_hindi import safe_invoke

    # Random seed to force different results every time
    random_seed = random.randint(1000, 9999)
    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    prompt = f"""
Current date and time: {today}
Random seed: {random_seed}

You are a viral-shorts trend analyst for India. Find 12 DIFFERENT visually striking
EXPERIMENT ideas that would make excellent 30-45 second YouTube Shorts for an Indian
Hindi-speaking audience.

Every idea must be an EXPERIMENT or a TEST (something that is tried and the result is shown)
in exactly one of these 4 categories — 3 ideas per category:
- "science": viral chemical reactions, physics demos, pressure/vacuum tricks, magnetism,
  non-Newtonian fluids, optical illusions, everyday "myth or fact" science tests
- "ai": experiments with AI tools (chatbots, image/video/voice AI) — e.g. "AI se X banwaya,
  result dekho", AI vs human tests, what AI gets wrong
- "tech": experiments with technology — wifi/bluetooth range tests, robots, drones, 3D printing,
  simple electronics, internet/app tricks
- "gadgets": experiments with gadgets — phone tests (water/drop/battery), earbuds, power banks,
  smartwatches, cameras, "does this gadget really work?" tests

Do NOT include history, general facts lists, news, or topics that are not an experiment/test.

For each idea, make sure it is:
1. DIFFERENT from common topics already done to death (no basic baking-soda-volcano)
2. Visually specific — describe the concrete experiment/materials/result, not vague "facts"
3. Safe to depict and describe without real safety risk, and clearly explainable in under 45 seconds

Return JSON array of 12 items:
[
  {{
    "category": "one of: science, ai, tech, gadgets",
    "channel": "type of channel eg: Chemical Experiment, AI Test, Gadget Test",
    "title": "catchy hindi title for this experiment",
    "topic": "specific experiment in english with concrete materials/setup/result",
    "why_trending": "why this experiment is visually striking / shareworthy",
    "tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8","tag9","tag10"],
    "description": "50 word hindi description",
    "views": 150000
  }}
]

Return ONLY the JSON array. Make all 12 experiment ideas UNIQUE and DIFFERENT from each other.
"""

    try:
        response = safe_invoke(prompt, temperature=0.9)  # High temperature = more variety

        content = response.content or ""
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
            'category': normalize_category(
                t.get('category'), f"{t.get('topic', '')} {t.get('title', '')}"),
            'channel': t.get('channel', 'Hindi Experiment'),
            'title': t.get('title', t.get('topic', '')),
            'topic': t.get('topic', ''),
            'why_trending': t.get('why_trending', ''),
            'tags': t.get('tags', ['hindi', 'experiment', 'science', 'shorts', 'viral', 'india']),
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


def get_best_hindi_topic(category=None):
    """Pick a topic. If category is given (science/ai/tech/gadgets), prefer
    ideas from that category; fall back to any idea if none match."""
    topics = get_hindi_trending_topics()
    if not topics:
        return None
    if category:
        matching = [t for t in topics if t.get('category') == category]
        if matching:
            return random.choice(matching[:5])
    return random.choice(topics[:5])  # Random from top 5
