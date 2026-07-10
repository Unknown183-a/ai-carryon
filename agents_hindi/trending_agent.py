# agents_hindi/trending_agent.py
import os
import re
import json
import random
import googleapiclient.discovery
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

RECENT_TOPICS_FILE = "output/recent_trending_topics_hindi.json"
RECENT_DAYS = 7  # don't repeat a topic used within this many days


# ─────────────────────────────────────────────
# Recent-topic memory (prevents repeats)
# ─────────────────────────────────────────────

def _normalize(title: str) -> str:
    """Lowercase, strip punctuation/emoji/hashtags, collapse whitespace."""
    t = title.lower()
    t = re.sub(r"#\w+", "", t)              # remove hashtags
    t = re.sub(r"[^\w\s]", " ", t)          # remove punctuation/emoji
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _load_recent():
    if os.path.exists(RECENT_TOPICS_FILE):
        try:
            with open(RECENT_TOPICS_FILE) as f:
                data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    else:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)
    fresh = []
    for entry in data:
        try:
            ts = datetime.fromisoformat(entry["timestamp"])
            if ts >= cutoff:
                fresh.append(entry)
        except Exception:
            continue
    return fresh


def _save_recent(title: str):
    os.makedirs("output", exist_ok=True)
    recent = _load_recent()
    recent.append({
        "title": title,
        "normalized": _normalize(title),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    with open(RECENT_TOPICS_FILE, "w") as f:
        json.dump(recent, f, indent=2, ensure_ascii=False)


def _is_repeat(title: str, recent_entries) -> bool:
    norm = _normalize(title)
    for entry in recent_entries:
        if entry["normalized"] == norm:
            return True
        a = norm.split()[:3]
        b = entry["normalized"].split()[:3]
        if a and a == b:
            return True
    return False


def _load_uploaded_titles():
    """
    Permanently exclude topics that were already turned into a real
    uploaded video on the Hindi channel, regardless of how long ago.
    """
    import sqlite3
    db_path = os.environ.get("DB_PATH", "output/aicarryon.db")
    uploaded = []
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT title FROM videos WHERE channel = 'hindi'")
        rows = cur.fetchall()
        conn.close()
        for (title,) in rows:
            if title:
                uploaded.append({"title": title, "normalized": _normalize(title)})
    except Exception as e:
        print(f"Trending agent (hindi): could not load uploaded titles from DB: {e}")
    return uploaded


# ─────────────────────────────────────────────
# Fetch: recent search (primary) + mostPopular chart (fallback)
# ─────────────────────────────────────────────

def _is_relevant_lang(snippet):
    lang = snippet.get("defaultAudioLanguage", "")
    return lang.startswith("hi") or lang.startswith("en") or lang == ""


def _fetch_recent_search(youtube, region_code, hours=96, max_results=50):
    """Genuinely fresh videos from the last N hours, sorted by view count."""
    published_after = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    try:
        search_resp = youtube.search().list(
            part="snippet",
            type="video",
            order="viewCount",
            publishedAfter=published_after,
            regionCode=region_code,
            videoCategoryId="28",
            maxResults=max_results,
        ).execute()
        return [
            item["snippet"]["title"]
            for item in search_resp.get("items", [])
            if _is_relevant_lang(item["snippet"])
        ]
    except Exception as e:
        print(f"Trending agent (hindi) recent-search error: {e}")
        return []


def _fetch_most_popular(youtube, region_code, max_results=50):
    try:
        response = youtube.videos().list(
            part="snippet",
            chart="mostPopular",
            regionCode=region_code,
            maxResults=max_results,
            videoCategoryId="28",
        ).execute()
        return response.get("items", [])
    except Exception as e:
        print(f"Trending agent (hindi) mostPopular error: {e}")
        return []


def get_trending_topic(region_code="IN"):
    try:
        youtube = googleapiclient.discovery.build(
            "youtube", "v3", developerKey=YOUTUBE_API_KEY
        )

        recent_used = _load_recent() + _load_uploaded_titles()

        # Primary: genuinely fresh videos from last 96h
        fresh_titles = _fetch_recent_search(youtube, region_code, hours=96)
        candidates = [t for t in fresh_titles if not _is_repeat(t, recent_used)]

        if candidates:
            chosen = random.choice(candidates[:20])
            _save_recent(chosen)
            return chosen

        # Fallback: mostPopular chart (old behavior), still language-filtered
        all_videos = _fetch_most_popular(youtube, region_code)
        pool = []
        for video in all_videos:
            snippet = video["snippet"]
            title = snippet["title"]
            if _is_relevant_lang(snippet) and not _is_repeat(title, recent_used):
                pool.append(title)

        if not pool:
            pool = [
                v["snippet"]["title"] for v in all_videos
                if not _is_repeat(v["snippet"]["title"], recent_used)
            ]

        if pool:
            chosen = random.choice(pool)
            _save_recent(chosen)
            return chosen

    except Exception as e:
        print(f"Trending agent (hindi) error: {e}")

    chosen = _fallback_topic()
    _save_recent(chosen)
    return chosen


def _get_llm():
    from langchain_groq import ChatGroq
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.9,
        groq_api_key=os.getenv("GROQ_API_KEY"),
    )


def _generate_dynamic_topic(recent_used, attempts=3):
    """
    Ask the LLM to invent a fresh Hinglish tech video topic when the
    static fallback list has been exhausted.
    """
    try:
        llm = _get_llm()
    except Exception as e:
        print(f"Trending agent (hindi): LLM unavailable for dynamic fallback: {e}")
        return None

    used_titles = [e["title"] for e in recent_used][-25:]
    used_list = "\n".join(f"- {t}" for t in used_titles) if used_titles else "(none yet)"

    prompt = f"""Generate ONE punchy YouTube video title idea in casual Hinglish about a
technology or AI topic (new gadgets, AI tools, robots, phones, space tech, chips,
EVs, etc). Write it in Roman/Latin script (Hinglish), NOT Devanagari script. Style should be like viral Hindi tech-news shorts — but NOT similar in
content or wording to ANY of these already-used titles:

{used_list}

Rules:
- Under 12 words
- No quotes, no hashtags, no emojis
- Reply with ONLY the title text, nothing else"""

    for _ in range(attempts):
        try:
            response = llm.invoke(prompt)
            title = response.content.strip().strip('"')
            if title and not _is_repeat(title, recent_used):
                return title
        except Exception as e:
            print(f"Trending agent (hindi): dynamic fallback generation failed: {e}")
            break

    return None


def _fallback_topic():
    """Proven high-performing Hindi/Hinglish tech topics, excluding recent ones.
    Falls through to LLM-generated topics if the static list is exhausted."""
    fallbacks = [
        "Artificial Intelligence kya hai",
        "Naya AI robot jo sab kuch kar sakta hai",
        "iPhone 17 Pro ke chhupe hue features",
        "Google ka naya AI sabse best hai",
        "Yeh naya invention phone use karne ka tarika badal dega",
        "Tesla ka self-driving update sab kuch badal diya",
        "Naya humanoid robot launch hua hai",
        "OpenAI ne kuch naya release kiya hai",
        "Samsung Galaxy S26 ke leaked features dekho",
        "Yeh AI tool 10 apps ki jagah leta hai free mein",
        "Naya chip phone ko 10x fast banata hai",
        "NASA ne kuch aisa dhoondha jo sab kuch badal dega",
        "Yeh AI aapki awaaz clone kar sakta hai 3 second mein",
        "Yeh electric vehicle Tesla ko half price mein beat karta hai",
        "Google ne sabse powerful AI assistant launch kiya",
        "Yeh naya chip market ke sabse tez chip se bhi tez hai",
        "Apple ka secret AI project leak ho gaya",
        "Yeh robot khud khana bana sakta hai",
        "Naya drone 10 ghante tak udd sakta hai",
        "Yeh smart home gadget ek din mein sold out ho gaya",
        "Scientists ne dimaag jaisa sochne wala computer banaya",
        "Yeh AI seconds mein poori app likh sakta hai",
        "Naya satellite internet fiber se bhi tez hai",
        "Yeh gadget aapke phone ko laptop bana deta hai",
        "Naya battery tech phone ko 5 minute mein charge karta hai",
        "Yeh AI model ne real medical exam pass kiya",
        "Naya VR headset bilkul real jaisa lagta hai",
        "Is startup ne flying car banayi jo sach mein chalti hai",
        "Naya chip phone ke andar hi AI chala sakta hai",
        "Yeh robot dog darwaza khol sakta hai aur seedhi chad sakta hai",
    ]
    recent_used = _load_recent() + _load_uploaded_titles()
    unused = [t for t in fallbacks if not _is_repeat(t, recent_used)]

    if unused:
        return random.choice(unused)

    dynamic = _generate_dynamic_topic(recent_used)
    if dynamic:
        return dynamic

    return random.choice(fallbacks)
