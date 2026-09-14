# agents_cricket/comment_reply_agent.py
"""
Comment Reply Agent — Cricket channel.

Mirrors agents_hindi/comment_reply_agent.py, but:
  - reuses agents_cricket.upload_agent's authenticated client
  - stores processed-comment history in Postgres (cricket_comment_history
    table, via agents_cricket.database) instead of a local JSON file — so
    dedup actually survives across GitHub Actions runs, unlike English/
    Hindi's current local-JSON approach which resets every run
  - replies in casual Hindi/Hinglish, matching the cricket script's language
    and a cricket-fan's actual comment style (not a tech-channel voice)

Pluggable standalone, same as the Hindi version:
    from agents_cricket.comment_reply_agent import process_comments_cricket
    process_comments_cricket()

Config:
    AUTO_REPLY = False -> only generate + save replies, don't publish
    AUTO_REPLY = True  -> also publish replies to YouTube via the API
"""

import os
import datetime
from dotenv import load_dotenv

load_dotenv()

AUTO_REPLY = True  # flip to False to dry-run without publishing

MAX_REPLY_WORDS = 40

VALID_CATEGORIES = [
    "Question", "Appreciation", "Suggestion", "Criticism",
    "Match Request", "Spam", "Offensive", "Other",
]

NO_REPLY_CATEGORIES = {"Spam", "Offensive"}


# ─────────────────────────────────────────────
# Storage helpers — backed by agents_cricket.database's Postgres tables
# (cricket_comment_history, cricket_match_requests)
# ─────────────────────────────────────────────

def _already_processed(comment_id):
    from agents_cricket.database import db
    if db is None:
        return False
    try:
        return db.is_comment_processed(comment_id)
    except Exception as e:
        print(f"[comment_reply_agent_cricket] History check failed: {e}")
        return False


def save_comment_history(comment_id, video_id, username, original_comment,
                          category, generated_reply):
    from agents_cricket.database import db
    if db is None:
        return
    try:
        db.save_comment_history(
            comment_id=comment_id, video_id=video_id, username=username,
            original_comment=original_comment, category=category,
            generated_reply=generated_reply,
        )
    except Exception as e:
        print(f"[comment_reply_agent_cricket] History save failed: {e}")


def save_match_request(request_text, comment, video_id):
    """Fans often ask 'cover X match please' — logged separately so it can
    feed match selection later, same role topic_requests plays for English/Hindi."""
    from agents_cricket.database import db
    if db is None:
        return
    try:
        db.save_match_request(request_text=request_text, comment=comment, video_id=video_id)
    except Exception as e:
        print(f"[comment_reply_agent_cricket] Match request save failed: {e}")


# ─────────────────────────────────────────────
# YouTube fetch / publish (reuses existing cricket auth)
# ─────────────────────────────────────────────

def fetch_new_comments(max_results=50):
    """Returns a list of dicts: {comment_id, video_id, username, text}."""
    from agents_cricket.upload_agent import get_youtube_client_readonly

    youtube = get_youtube_client_readonly()

    channel_response = youtube.channels().list(part="id", mine=True).execute()
    items = channel_response.get("items", [])
    if not items:
        print("[comment_reply_agent_cricket] Could not resolve channel id — skipping fetch")
        return []
    channel_id = items[0]["id"]

    fetched = []
    page_token = None

    try:
        while len(fetched) < max_results:
            response = youtube.commentThreads().list(
                part="snippet",
                allThreadsRelatedToChannelId=channel_id,
                maxResults=min(50, max_results - len(fetched)),
                order="time",
                pageToken=page_token,
                textFormat="plainText",
            ).execute()

            for item in response.get("items", []):
                top_comment = item["snippet"]["topLevelComment"]
                comment_id = top_comment["id"]

                if _already_processed(comment_id):
                    continue
                if item["snippet"].get("totalReplyCount", 0) > 0:
                    continue

                snippet = top_comment["snippet"]
                fetched.append({
                    "comment_id": comment_id,
                    "video_id": snippet.get("videoId", ""),
                    "username": snippet.get("authorDisplayName", "unknown"),
                    "text": snippet.get("textOriginal", snippet.get("textDisplay", "")),
                })

            page_token = response.get("nextPageToken")
            if not page_token:
                break

    except Exception as e:
        print(f"[comment_reply_agent_cricket] Error fetching comments: {e}")

    print(f"[comment_reply_agent_cricket] Fetched {len(fetched)} new comment(s)")
    return fetched


def publish_reply(comment_id, reply_text):
    """comments().insert needs youtube.force-ssl — if AUTO_REPLY=True fails
    with insufficient scope, regenerate CRICKET_YOUTUBE_TOKEN_B64 with that
    scope added, same as the English/Hindi tokens needed for this feature."""
    from agents_cricket.upload_agent import authenticate_youtube

    try:
        youtube = authenticate_youtube()
        youtube.comments().insert(
            part="snippet",
            body={"snippet": {"parentId": comment_id, "textOriginal": reply_text}},
        ).execute()
        print(f"[comment_reply_agent_cricket] Reply published for comment {comment_id}")
        return True
    except Exception as e:
        print(f"[comment_reply_agent_cricket] Failed to publish reply for {comment_id}: {e}")
        return False


# ─────────────────────────────────────────────
# LLM classification + reply generation
# ─────────────────────────────────────────────

def _get_llm():
    from langchain_groq import ChatGroq
    return ChatGroq(model="openai/gpt-oss-120b", temperature=0.4, groq_api_key=os.getenv("GROQ_API_KEY"))


def classify_comment(comment_text):
    llm = _get_llm()
    prompt = f"""Classify this YouTube comment (may be in Hindi, Hinglish, or English)
on a cricket-highlights channel into EXACTLY ONE of these categories:
Question, Appreciation, Suggestion, Criticism, Match Request, Spam, Offensive, Other

Rules:
- "Spam" = promotional links, unrelated ads, bot-like repeated text
- "Offensive" = insults, hate speech, harassment, explicit content
- "Match Request" = asks the channel to cover a specific match/player/team
- "Suggestion" = general format/style suggestion, not a specific match request
- Reply with ONLY the category name, nothing else.

Comment: "{comment_text}"

Category:"""

    try:
        raw = llm.invoke(prompt).content.strip()
        for category in VALID_CATEGORIES:
            if category.lower() in raw.lower():
                return category
        return "Other"
    except Exception as e:
        print(f"[comment_reply_agent_cricket] Classification failed, defaulting to 'Other': {e}")
        return "Other"


def generate_reply(comment_text, category):
    if category in NO_REPLY_CATEGORIES:
        return "NO_REPLY"

    llm = _get_llm()

    extra_note = ""
    if category == "Match Request":
        extra_note = """
Yeh comment kisi specific match/player/team ko cover karne ki request hai.
Casually commit mat karo aur casually deny bhi mat karo — real creator jaisa
reply do (jaise "dekhta hun" ya "already list mein hai bhai")."""

    prompt = f"""Is YouTube comment ka reply likho jaise ek cricket-highlights channel
ka asli creator apne phone se casually type kar raha ho. Support agent jaisa BILKUL nahi.

Comment ki category: {category}
{extra_note}

STRICT RULES:
- Agar original comment Hindi/Hinglish mein hai to natural Hinglish mein reply karo
  (jaise real cricket fans YouTube comments mein type karte hain — casual)
- Agar original comment pure English mein hai to casual English mein reply karo
- {MAX_REPLY_WORDS} words se kam, lekin chhota reply (5-15 words) aksar best hota hai
- Jo comment mein specifically likha hai usi par react karo — generic phrasing nahi
- Kabhi mat likho: "main samajh sakta hoon", "aapka feedback appreciate karte hain"
- Agar comment ek team/player ko troll kar raha hai to halka-fulka banter theek hai,
  lekin kisi real player/team ki toxic beizzati mat karo
- Emoji mat use karo jab tak comment khud bahut casual/funny na ho (🏏🔥 chalega)
- Kabhi bhi nasty level tak rude mat bano, jhoothe scores/facts mat bolo
- Agar score/fact confidently nahi pata to short aur honest raho, guess mat karo
- Sirf reply text do — koi quotes, koi preamble nahi

Tone jaisa hona chahiye, examples:
"haha bilkul bhai wahi match winning over tha"
"agla wala aayega jaldi, stay tuned"
"lol yeh toh sabne dekha hi hoga"
"scorecard check karo, exact figures wahan hain"

Comment: "{comment_text}"

Reply:"""

    try:
        reply = llm.invoke(prompt).content.strip().strip('"')
        words = reply.split()
        if len(words) > MAX_REPLY_WORDS:
            reply = " ".join(words[:MAX_REPLY_WORDS])
        return reply
    except Exception as e:
        print(f"[comment_reply_agent_cricket] Reply generation failed: {e}")
        return "NO_REPLY"


def _extract_match_request(comment_text):
    llm = _get_llm()
    prompt = f"""Extract the specific match, player, or team being requested
(5-10 words, in English) from this comment, even if it's in Hindi/Hinglish.
Reply with ONLY the request phrase, nothing else.

Comment: "{comment_text}"

Request:"""
    try:
        req = llm.invoke(prompt).content.strip().strip('"')
        return req if req else comment_text[:80]
    except Exception:
        return comment_text[:80]


# ─────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────

def process_comments_cricket(max_results=50, log_fn=print):
    """Safe to call repeatedly (e.g. from scheduler_cricket.py's cycle) —
    already-processed comments are skipped via Postgres's cricket_comment_history."""
    log_fn("[comment_reply_agent_cricket] Naye comments check ho rahe hain...")

    comments = fetch_new_comments(max_results=max_results)
    if not comments:
        log_fn("[comment_reply_agent_cricket] Koi naya comment nahi mila")
        return {"processed": 0, "replied": 0, "published": 0, "match_requests": 0}

    stats = {"processed": 0, "replied": 0, "published": 0, "match_requests": 0}

    for c in comments:
        try:
            category = classify_comment(c["text"])
            reply = generate_reply(c["text"], category)

            save_comment_history(
                comment_id=c["comment_id"], video_id=c["video_id"], username=c["username"],
                original_comment=c["text"], category=category, generated_reply=reply,
            )
            stats["processed"] += 1

            if category == "Match Request":
                request = _extract_match_request(c["text"])
                save_match_request(request_text=request, comment=c["text"], video_id=c["video_id"])
                stats["match_requests"] += 1

            if reply != "NO_REPLY":
                stats["replied"] += 1
                log_fn(f"[comment_reply_agent_cricket] [{category}] {c['username']}: {c['text'][:60]}... -> {reply[:60]}...")
                if AUTO_REPLY:
                    if publish_reply(c["comment_id"], reply):
                        stats["published"] += 1
            else:
                log_fn(f"[comment_reply_agent_cricket] [{category}] {c['username']}: skipped (NO_REPLY)")

        except Exception as e:
            log_fn(f"[comment_reply_agent_cricket] Error processing comment {c.get('comment_id')}: {e}")
            continue

    log_fn(f"[comment_reply_agent_cricket] Done. Processed {stats['processed']}, "
           f"replied {stats['replied']}, published {stats['published']}, "
           f"match requests {stats['match_requests']}")
    return stats


if __name__ == "__main__":
    process_comments_cricket()
