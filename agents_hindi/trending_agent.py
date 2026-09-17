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
    from agents.database import db
    uploaded = []
    try:
        videos = db.get_all_videos(channel="hindi")
        for v in videos:
            title = v.get("title")
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
            q="experiment OR science experiment OR chemistry experiment OR physics experiment",
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
    """Fallback chart search — mostPopular has no query param, so we filter
    titles for experiment-related keywords after fetching category 28."""
    EXPERIMENT_KEYWORDS = (
        "experiment", "chemistry", "chemical", "physics", "reaction",
        "science", "prayog", "vigyan",
    )
    try:
        response = youtube.videos().list(
            part="snippet",
            chart="mostPopular",
            regionCode=region_code,
            maxResults=max_results,
            videoCategoryId="28",
        ).execute()
        items = response.get("items", [])
        filtered = [
            v for v in items
            if any(k in v["snippet"]["title"].lower() for k in EXPERIMENT_KEYWORDS)
        ]
        return filtered or items
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


def _generate_dynamic_topic(recent_used, attempts=3):
    """
    Ask the LLM to invent a fresh Hinglish tech video topic when the
    static fallback list has been exhausted.
    Routed through model_invoke_agent_hindi — shares the run's Groq
    budget/circuit breaker and falls back to Gemini automatically.
    """
    from agents_hindi.model_invoke_agent_hindi import safe_invoke

    used_titles = [e["title"] for e in recent_used][-25:]
    used_list = "\n".join(f"- {t}" for t in used_titles) if used_titles else "(none yet)"

    prompt = f"""Generate ONE punchy YouTube video title idea in casual Hinglish about a
visually striking science/chemical/physical EXPERIMENT (color-change reactions, foam,
crystal growth, dry ice, pressure/vacuum demos, magnetism, optical illusions,
non-Newtonian fluids, DIY science tricks, etc). Write it in Roman/Latin script
(Hinglish), NOT Devanagari script. Style should be like viral Hindi experiment/science shorts — but NOT similar in
content or wording to ANY of these already-used titles:

{used_list}

Rules:
- Under 12 words
- No quotes, no hashtags, no emojis
- Reply with ONLY the title text, nothing else"""

    for _ in range(attempts):
        try:
            response = safe_invoke(prompt, temperature=0.9)
            title = response.content.strip().strip('"')
            if title and not _is_repeat(title, recent_used):
                return title
        except Exception as e:
            print(f"Trending agent (hindi): dynamic fallback generation failed: {e}")
            break

    return None


def _fallback_topic():
    """Proven high-performing Hindi/Hinglish experiment topics, excluding recent ones.
    Falls through to LLM-generated topics if the static list is exhausted."""
    fallbacks = [
        "Yeh chemical mix karo toh instant baraf ban jaati hai",
        "Coca Cola aur Mentos ka asli reaction kya hota hai",
        "Yeh liquid aag ki tarah dikhta hai par jalta nahi",
        "Dry ice paani mein daalo toh yeh hota hai",
        "Yeh powder paani ko instant solid bana deta hai",
        "Egg ko vinegar mein daalo toh bouncy ball ban jaata hai",
        "Magnet se yeh cheez uda sakte ho, believe nahi hoga",
        "Non-Newtonian fluid — chalo par toh solid, ruko toh liquid",
        "Yeh chemical reaction se rangeen aag banti hai",
        "Balloon ko needle se pierce karo par phate nahi",
        "Yeh crystal ek raat mein khud ban jaata hai",
        "Vacuum mein marshmallow ka kya hota hai dekho",
        "Yeh do liquids milao toh foam explosion hota hai",
        "Static electricity se paani ka flow mod sakte ho",
        "Yeh optical illusion se dimaag confuse ho jaata hai",
        "Copper coin ko is chemical mein daalo, color badal jaayega",
        "Yeh experiment se pata chalta hai density kaise kaam karti hai",
        "Ice cube salt ke saath itni jaldi kyun pighalta hai",
        "Yeh DIY lava lamp ghar pe 2 minute mein banta hai",
        "Pressure difference se can crush ho jaata hai seconds mein",
        "Yeh liquid nitrogen se phool touch karte hi toot jaata hai",
        "Simple chemicals se rocket jaisa launch ho sakta hai",
        "Yeh trick se paani upside down glass mein ruka rehta hai",
        "Elephant toothpaste experiment — itna foam kaise banta hai",
        "Yeh acid-base reaction se instant color change hota hai",
        "Chumbak se yeh dhaatu float karti hai, kaise",
        "Yeh experiment se pata chalta hai surface tension kya hai",
        "Baloon ko candle ke upar rakho, phate ga ya nahi",
        "Yeh simple setup se apna mini volcano bana sakte ho",
        "Sound waves se paani ka pattern kaise badalta hai dekho",
    ]
    recent_used = _load_recent() + _load_uploaded_titles()
    unused = [t for t in fallbacks if not _is_repeat(t, recent_used)]

    if unused:
        return random.choice(unused)

    dynamic = _generate_dynamic_topic(recent_used)
    if dynamic:
        return dynamic

    return random.choice(fallbacks)
