# agents_bhakti/trending_agent.py
"""
Topic source for the Bhakti (devotional) channel.

Unlike the tech/experiment channels, "trending" doesn't map cleanly onto
devotional content — the evergreen catalogue (Hanuman, Ram, Shiv-Parvati,
Krishna, Ganesh, Durga, festivals, mantras) is what performs, not news.
So this agent:

1. Rotates through a large evergreen topic pool (deity stories, mantra
   meanings, festival significance) — same spirit as the channel this
   pipeline models itself on (Bhakti_sagar_5550: "bhagwan ki bhakti,
   dharmik kahaniyan, pauranik kathayen").
2. Optionally checks YouTube for genuinely trending devotional/festival
   content (e.g. a festival happening this week) via a devotional-only
   search filter, so festival-day content can take priority.
3. Never repeats a topic already used in the last RECENT_DAYS, and never
   repeats a topic that was already turned into an uploaded video
   (permanent exclusion, same pattern as the other channels).
"""

import os
import re
import json
import random
import googleapiclient.discovery
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

RECENT_TOPICS_FILE = "output/recent_trending_topics_bhakti.json"
RECENT_DAYS = 10  # devotional catalogue repeats faster than tech news, so wait longer


# ─────────────────────────────────────────────
# Recent-topic memory (prevents repeats)
# ─────────────────────────────────────────────

def _normalize(title: str) -> str:
    t = title.lower()
    t = re.sub(r"#\w+", "", t)
    t = re.sub(r"[^\w\s]", " ", t)
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
    """Permanently exclude topics already turned into a real uploaded
    video on the Bhakti channel, regardless of how long ago."""
    from agents.database import db
    uploaded = []
    try:
        videos = db.get_all_videos(channel="bhakti")
        for v in videos:
            title = v.get("title")
            if title:
                uploaded.append({"title": title, "normalized": _normalize(title)})
    except Exception as e:
        print(f"Trending agent (bhakti): could not load uploaded titles from DB: {e}")
    return uploaded


# ─────────────────────────────────────────────
# Evergreen devotional topic pool
# ─────────────────────────────────────────────

TOPIC_POOL = [
    # Hanuman
    "Hanuman ji ka Sanjeevani booti laane ka prasang",
    "Hanuman Chalisa ki ek chaupai ka gehra arth",
    "Bal Hanuman ne surya ko phal samajh kar kyun nigla tha",
    "Hanuman ji ko Ram bhakt kyun kaha jaata hai",
    "Hanuman ji ki ashtasiddhi aur navnidhi ka rahasya",
    "Lanka dahan ka pura prasang aur uska sandesh",
    # Ram
    "Ram Setu banane ki kahani aur Nal-Neel ka yogdan",
    "Shabari ke jhoothe ber Ram ne kyun khaye the",
    "Ramayan ka woh prasang jo bhakti sikhata hai",
    "Ram aur Lakshman ke bhai ke prem ki kahani",
    "Ahilya uddhar ki katha — ek shraap se mukti",
    # Krishna
    "Krishna ne Sudama ki garibi kaise door ki",
    "Govardhan Parvat uthane ki katha",
    "Bhagavad Gita ka ek shlok jo jeevan badal sakta hai",
    "Makhan chor Krishna ki balpan ki leela",
    "Draupadi ke cheer haran mein Krishna ki raksha",
    "Kaliya Naag ka mardan — Krishna ki ek adbhut leela",
    # Shiv-Parvati
    "Shiv Parvati vivah ki katha",
    "Samudra manthan aur Shiv ka vishpaan",
    "Mahashivratri kyun manayi jaati hai",
    "Ganesh ji ka janm aur Shiv Parvati ka prem",
    "Rudraksha dharan karne ka mahatva",
    # Ganesh
    "Ganesh ji ko pratham pujya kyun kaha jaata hai",
    "Ganesh ji ka ek daant kaise toota",
    "Modak Ganesh ji ko itna priya kyun hai",
    # Durga / Devi
    "Maa Durga ne Mahishasur ka vadh kaise kiya",
    "Navratri ke nau roop aur unka mahatva",
    "Maa Kali ki utpatti ki katha",
    # Mantras & shlokas
    "Gayatri Mantra ka arth aur mahatva",
    "Om Namah Shivaya jaap karne ke fayde",
    "Hanuman Chalisa roz padhne se kya hota hai",
    "Mahamrityunjay Mantra ki shakti",
    # Festivals
    "Diwali kyun manayi jaati hai — Ram ke Ayodhya lautne ki katha",
    "Raksha Bandhan ka dharmik mahatva",
    "Janmashtami par Krishna janm ki katha",
    "Karva Chauth vrat ki kahani",
    # Temples / places
    "Kedarnath mandir ka rahasya",
    "Kashi Vishwanath mandir ki mahima",
    "Tirupati Balaji ke darshan ka mahatva",
    "Vaishno Devi yatra ki katha",
]


def get_trending_topic(region_code="IN"):
    """Primary entrypoint — rotates the evergreen devotional pool, with an
    optional live check for festival-relevant content trending right now."""
    recent_used = _load_recent() + _load_uploaded_titles()

    # Try a live festival/devotional trending check first — cheap upside,
    # never blocks the pipeline if it fails.
    try:
        live_topic = _fetch_live_devotional_trend(region_code, recent_used)
        if live_topic:
            _save_recent(live_topic)
            return live_topic
    except Exception as e:
        print(f"Trending agent (bhakti) live check skipped: {e}")

    unused = [t for t in TOPIC_POOL if not _is_repeat(t, recent_used)]
    if unused:
        chosen = random.choice(unused)
        _save_recent(chosen)
        return chosen

    dynamic = _generate_dynamic_topic(recent_used)
    if dynamic:
        _save_recent(dynamic)
        return dynamic

    chosen = random.choice(TOPIC_POOL)
    _save_recent(chosen)
    return chosen


def _is_devotional(snippet):
    """Loose keyword filter so a generic search doesn't drag in unrelated
    Hindi content — must look devotional to be considered."""
    text = (snippet.get("title", "") + " " + snippet.get("description", "")).lower()
    keywords = (
        "bhakti", "bhagwan", "mandir", "aarti", "bhajan", "katha", "shiv",
        "ram", "krishna", "hanuman", "durga", "devi", "ganesh", "mantra",
        "puja", "vrat", "temple", "god", "spiritual", "dharmik",
    )
    return any(k in text for k in keywords)


def _fetch_live_devotional_trend(region_code, recent_used):
    """Check for a currently-relevant devotional/festival topic. Fails
    open (returns None) on any error so it never blocks generation."""
    if not YOUTUBE_API_KEY:
        return None
    try:
        youtube = googleapiclient.discovery.build(
            "youtube", "v3", developerKey=YOUTUBE_API_KEY
        )
        published_after = (
            datetime.now(timezone.utc) - timedelta(hours=72)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        resp = youtube.search().list(
            part="snippet",
            type="video",
            order="viewCount",
            publishedAfter=published_after,
            regionCode=region_code,
            relevanceLanguage="hi",
            q="bhakti OR mandir OR bhagwan katha OR aarti OR vrat katha",
            maxResults=25,
        ).execute()

        candidates = [
            item["snippet"]["title"]
            for item in resp.get("items", [])
            if _is_devotional(item["snippet"]) and not _is_repeat(item["snippet"]["title"], recent_used)
        ]
        if candidates:
            return random.choice(candidates[:10])
    except Exception as e:
        print(f"Trending agent (bhakti) live search error: {e}")
    return None


def _generate_dynamic_topic(recent_used, attempts=3):
    """Ask the LLM to invent a fresh devotional story/topic once the
    static pool is exhausted. Routed through model_invoke_agent_bhakti."""
    from agents_bhakti.model_invoke_agent_bhakti import safe_invoke

    used_titles = [e["title"] for e in recent_used][-30:]
    used_list = "\n".join(f"- {t}" for t in used_titles) if used_titles else "(none yet)"

    prompt = f"""Generate ONE short Hindi devotional (Bhakti) YouTube Shorts topic —
a mythological story, deity's leela, mantra meaning, or festival significance,
from Hindu dharmik tradition (Ram, Krishna, Shiv, Hanuman, Durga, Ganesh, etc).
Write it in Roman/Latin script (Hinglish), NOT Devanagari script.
It must NOT be similar in content or wording to ANY of these already-used topics:

{used_list}

Rules:
- Under 14 words
- No quotes, no hashtags, no emojis
- Respectful, devotional tone — no jokes, no irreverence
- Reply with ONLY the topic text, nothing else"""

    for _ in range(attempts):
        try:
            response = safe_invoke(prompt, temperature=0.9)
            title = response.content.strip().strip('"')
            if title and not _is_repeat(title, recent_used):
                return title
        except Exception as e:
            print(f"Trending agent (bhakti): dynamic fallback generation failed: {e}")
            break
    return None


if __name__ == "__main__":
    print(get_trending_topic())
