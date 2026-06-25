# agents/trending_agent.py
import os
import random
import googleapiclient.discovery
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

NICHE_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "chatgpt", "openai", "gemini", "claude", "llm", "gpt",
    "automation", "neural network", "python", "programming", "developer",
    "coding", "software engineer", "tech company", "startup", "algorithm",
    "data science", "cloud computing", "chip", "semiconductor", "quantum",
    "cybersecurity", "robotics", "autonomous", "self-driving", "model",
    "apple intelligence", "microsoft copilot", "github copilot"
]

REJECT_KEYWORDS = [
    "gps", "deal", "sale", "discount", "recipe", "food", "cook",
    "makeup", "beauty", "fashion", "sport", "game", "minecraft",
    "fortnite", "water", "alarm", "school", "prank", "vlog",
    "travel", "workout", "gym", "music", "song", "dance",
    "ps5", "xbox", "playstation", "overheating", "color", "materials",
    "craft", "diy", "invent", "bending", "monitor trick", "flex",
    "satisfying", "asmr", "life hack", "cleaning", "unboxing",
    "smashed", "fixing", "repair", "paint", "xpeng", "car", "vehicle repair",
    "replace it", "without paint", "scares me"
]

TITLE_PATTERNS = [
    "curiosity",
    "urgency",
    "revelation",
    "number",
    "question",
    "warning",
]

SEEDS = [
    "OpenAI latest news", "Google DeepMind breakthrough",
    "Anthropic Claude update", "Python automation trick",
    "AI agents replacing jobs", "LLM new capability",
    "Apple Intelligence feature", "AI coding tool",
    "quantum computing milestone", "cybersecurity AI tool",
    "autonomous vehicle update", "AI chip breakthrough",
    "open source AI model", "developer AI productivity",
    "machine learning trick", "AI startup funding"
]


def is_on_niche(title):
    title_lower = title.lower()
    for kw in REJECT_KEYWORDS:
        if kw in title_lower:
            return False
    for kw in NICHE_KEYWORDS:
        if kw in title_lower:
            return True
    return False


def get_llm_topic():
    from langchain_groq import ChatGroq
    llm = ChatGroq(model="llama-3.3-70b-versatile")
    seed = random.choice(SEEDS)
    prompt = (
        f"Generate ONE specific YouTube Shorts topic about: {seed}\n"
        "Rules:\n"
        "- Must be about AI, machine learning, coding, or cutting-edge tech\n"
        "- Must NOT be about gaming, food, sports, lifestyle, or DIY\n"
        "- Must be specific and fascinating to developers and tech fans\n"
        "- Must sound like a real news headline or fascinating fact\n"
        "- Return ONLY the topic phrase (6-12 words), nothing else, no quotes\n\n"
        "Topic:"
    )
    response = safe_invoke(prompt).content.strip()
    lines = [l.strip() for l in response.splitlines() if l.strip()]
    topic = lines[0] if lines else seed
    topic = topic.strip('"').strip("'").strip("-").strip()
    return topic




def safe_invoke(prompt):
    from langchain_groq import ChatGroq
    try:
        return get_llm_topic().invoke(prompt)
    except Exception as e:
        if "503" in str(e) or "capacity" in str(e) or "overloaded" in str(e):
            print("Falling back to llama3-8b-8192")
            return ChatGroq(model="llama3-8b-8192").invoke(prompt)
        raise e


def get_trending_topic(region_code="US"):
    youtube = googleapiclient.discovery.build(
        "youtube", "v3", developerKey=YOUTUBE_API_KEY
    )

    request = youtube.videos().list(
        part="snippet",
        chart="mostPopular",
        regionCode=region_code,
        maxResults=50,
        videoCategoryId="28"
    )
    response = request.execute()
    all_videos = response.get("items", [])

    pool = []
    seen = set()
    for video in all_videos:
        snippet = video["snippet"]
        title = snippet["title"]
        lang = snippet.get("defaultAudioLanguage", "")
        is_english = lang.startswith("en") or all(ord(c) < 128 for c in title)
        clean_title = title.split("#")[0].strip()
        if is_english and is_on_niche(title) and clean_title not in seen:
            pool.append(clean_title)
            seen.add(clean_title)

    # Load recently used topics to avoid repeats
    import json, os
    recent_file = "output/recent_topics.json"
    try:
        recent = json.load(open(recent_file)) if os.path.exists(recent_file) else []
    except Exception:
        recent = []

    # Filter out recently used topics
    fresh_pool = [t for t in pool if t not in recent]

    if len(fresh_pool) >= 2:
        # 50% chance to use LLM anyway for variety
        if random.random() > 0.5:
            topic = random.choice(fresh_pool)
        else:
            topic = get_llm_topic()
    elif len(fresh_pool) == 1:
        # 70% chance to use LLM to avoid repetition
        if random.random() > 0.3:
            topic = get_llm_topic()
        else:
            topic = fresh_pool[0]
    else:
        # No fresh trending topics — always use LLM
        topic = get_llm_topic()

    # Save to recent topics (keep last 20)
    recent = ([topic] + recent)[:20]
    os.makedirs("output", exist_ok=True)
    json.dump(recent, open(recent_file, "w"))

    # Rotate pattern truly randomly but avoid last used
    pattern = random.choice(TITLE_PATTERNS)
    return f"{topic}||PATTERN:{pattern}"
