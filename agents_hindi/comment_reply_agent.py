# agents_hindi/comment_reply_agent.py
"""
Comment Reply Agent — Hindi channel.

Mirrors agents/comment_reply_agent.py exactly, but:
  - reuses agents_hindi.upload_agent's authenticated client instead of English's
  - writes to separate output files so English/Hindi never collide
  - replies in Hindi/Hinglish, matching this channel's actual voice

Does not modify any existing agent or scheduler. Pluggable standalone:

    from agents_hindi.comment_reply_agent import process_comments_hindi
    process_comments_hindi()

Config:
    AUTO_REPLY = False  -> only generate + save replies locally, don't publish
    AUTO_REPLY = True   -> also publish replies to YouTube via the API
"""

import os
import json
import datetime

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────

AUTO_REPLY = False  # flip to True to actually publish replies to YouTube

COMMENT_HISTORY_FILE = "output/comment_history_hindi.json"
TOPIC_REQUESTS_FILE = "output/topic_requests_hindi.json"

MAX_REPLY_WORDS = 40

VALID_CATEGORIES = [
    "Question", "Appreciation", "Suggestion", "Criticism",
    "AI Related", "Spam", "Offensive", "Other",
]

NO_REPLY_CATEGORIES = {"Spam", "Offensive"}


# ─────────────────────────────────────────────
# Local storage helpers
# ─────────────────────────────────────────────

def _load_json(path):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    return []


def _save_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _already_processed_ids():
    history = _load_json(COMMENT_HISTORY_FILE)
    return {entry.get("comment_id") for entry in history if entry.get("comment_id")}


def save_comment_history(comment_id, video_id, username, original_comment,
                          category, generated_reply):
    """Append a processed comment record to output/comment_history_hindi.json."""
    history = _load_json(COMMENT_HISTORY_FILE)
    history.append({
        "comment_id": comment_id,
        "video_id": video_id,
        "username": username,
        "original_comment": original_comment,
        "category": category,
        "generated_reply": generated_reply,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })
    _save_json(COMMENT_HISTORY_FILE, history)


def save_topic_request(topic, comment, video_id):
    """Append a video-topic suggestion to output/topic_requests_hindi.json."""
    requests_list = _load_json(TOPIC_REQUESTS_FILE)
    requests_list.append({
        "topic": topic,
        "comment": comment,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "video_id": video_id,
    })
    _save_json(TOPIC_REQUESTS_FILE, requests_list)


# ─────────────────────────────────────────────
# YouTube fetch / publish (reuses existing Hindi auth)
# ─────────────────────────────────────────────

def fetch_new_comments(max_results=50):
    """
    Fetch recent top-level comment threads across the Hindi channel,
    skipping any comment_id already present in comment_history_hindi.json.

    Returns a list of dicts:
        {comment_id, video_id, username, text}
    """
    from agents_hindi.upload_agent import get_youtube_client_readonly

    youtube = get_youtube_client_readonly()
    already_seen = _already_processed_ids()

    channel_response = youtube.channels().list(part="id", mine=True).execute()
    items = channel_response.get("items", [])
    if not items:
        print("[comment_reply_agent_hindi] Could not resolve channel id — skipping fetch")
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

                if comment_id in already_seen:
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
        print(f"[comment_reply_agent_hindi] Error fetching comments: {e}")

    print(f"[comment_reply_agent_hindi] Fetched {len(fetched)} new comment(s)")
    return fetched


def publish_reply(comment_id, reply_text):
    """
    Publish a reply to a specific top-level comment via the YouTube API.

    NOTE: comments().insert requires the youtube.force-ssl scope, which
    is broader than the upload/readonly scopes this channel's token was
    originally issued with. If AUTO_REPLY=True fails with insufficient
    scope, the token needs regenerating with youtube.force-ssl added —
    same re-auth process used for the view-tracking token fix.
    """
    from agents_hindi.upload_agent import get_youtube_client

    try:
        youtube = get_youtube_client()
        youtube.comments().insert(
            part="snippet",
            body={
                "snippet": {
                    "parentId": comment_id,
                    "textOriginal": reply_text,
                }
            },
        ).execute()
        print(f"[comment_reply_agent_hindi] Reply published for comment {comment_id}")
        return True
    except Exception as e:
        print(f"[comment_reply_agent_hindi] Failed to publish reply for {comment_id}: {e}")
        return False


# ─────────────────────────────────────────────
# LLM classification + reply generation
# ─────────────────────────────────────────────

def _get_llm():
    """Same Groq setup pattern used elsewhere in this codebase."""
    from langchain_groq import ChatGroq
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.4,
        groq_api_key=os.getenv("GROQ_API_KEY"),
    )


def classify_comment(comment_text):
    """
    Classify a comment (Hindi, Hinglish, or English) into one of
    VALID_CATEGORIES using the LLM. Falls back to 'Other' on any
    parsing/LLM failure — never crashes the caller.
    """
    llm = _get_llm()

    prompt = f"""Classify this YouTube comment (may be in Hindi, Hinglish, or English)
into EXACTLY ONE of these categories:
Question, Appreciation, Suggestion, Criticism, AI Related, Spam, Offensive, Other

Rules:
- "Spam" = promotional links, unrelated ads, bot-like repeated text
- "Offensive" = insults, hate speech, harassment, explicit content
- "AI Related" = comments specifically about AI, this being AI-generated, or asking if the content is AI
- "Suggestion" = comment asks for or proposes a future video topic
- Reply with ONLY the category name, nothing else.

Comment: "{comment_text}"

Category:"""

    try:
        response = llm.invoke(prompt)
        raw = response.content.strip()
        for category in VALID_CATEGORIES:
            if category.lower() in raw.lower():
                return category
        return "Other"
    except Exception as e:
        print(f"[comment_reply_agent_hindi] Classification failed, defaulting to 'Other': {e}")
        return "Other"


def generate_reply(comment_text, category):
    """
    Generate a reply for a classified comment, in Hindi/Hinglish to match
    this channel's actual voice (mirrors the Hinglish tone used in this
    channel's video titles and scripts elsewhere in agents_hindi/).

    Returns the literal string "NO_REPLY" for Spam/Offensive categories.
    """
    if category in NO_REPLY_CATEGORIES:
        return "NO_REPLY"

    llm = _get_llm()

    prompt = f"""Write a reply to this YouTube comment. The comment was classified as: {category}

STRICT RULES:
- Reply in natural Hinglish (Hindi + English mix) if the original comment is in
  Hindi or Hinglish; reply in plain English if the original comment is in English
- Friendly, polite, helpful, human-sounding, professional
- Under {MAX_REPLY_WORDS} words
- No emojis
- Never rude, never argue, never hallucinate facts you don't know
- If it's a question you can't confidently answer, politely say you're not sure rather than guessing
- Do not mention that you are an AI unless the comment specifically asks
- Reply with ONLY the reply text, nothing else — no quotes, no preamble

Comment: "{comment_text}"

Reply:"""

    try:
        response = llm.invoke(prompt)
        reply = response.content.strip().strip('"')

        words = reply.split()
        if len(words) > MAX_REPLY_WORDS:
            reply = " ".join(words[:MAX_REPLY_WORDS])

        return reply
    except Exception as e:
        print(f"[comment_reply_agent_hindi] Reply generation failed: {e}")
        return "NO_REPLY"


def _extract_topic_suggestion(comment_text):
    """
    For Suggestion-category comments, ask the LLM to extract a short,
    clean topic phrase (in English, for consistency with the topic
    pipeline regardless of what language the comment was written in).
    """
    llm = _get_llm()
    prompt = f"""Extract a short video topic (5-10 words, in English) suggested in this comment,
even if the comment itself is in Hindi or Hinglish.
Reply with ONLY the topic phrase, nothing else.

Comment: "{comment_text}"

Topic:"""
    try:
        response = llm.invoke(prompt)
        topic = response.content.strip().strip('"')
        return topic if topic else comment_text[:80]
    except Exception:
        return comment_text[:80]


# ─────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────

def process_comments_hindi(max_results=50, log_fn=print):
    """
    Main entry point — fetch new comments, classify, generate replies,
    save history, save topic requests, and publish if AUTO_REPLY is True.

    Safe to call repeatedly (e.g. from scheduler_hindi.py's hourly loop) —
    already-processed comments are skipped via comment_history_hindi.json.
    """
    log_fn("[comment_reply_agent_hindi] Naye comments check ho rahe hain...")

    comments = fetch_new_comments(max_results=max_results)
    if not comments:
        log_fn("[comment_reply_agent_hindi] Koi naya comment nahi mila")
        return {"processed": 0, "replied": 0, "published": 0, "topic_requests": 0}

    stats = {"processed": 0, "replied": 0, "published": 0, "topic_requests": 0}

    for c in comments:
        try:
            category = classify_comment(c["text"])
            reply = generate_reply(c["text"], category)

            save_comment_history(
                comment_id=c["comment_id"],
                video_id=c["video_id"],
                username=c["username"],
                original_comment=c["text"],
                category=category,
                generated_reply=reply,
            )
            stats["processed"] += 1

            if category == "Suggestion":
                topic = _extract_topic_suggestion(c["text"])
                save_topic_request(topic=topic, comment=c["text"], video_id=c["video_id"])
                stats["topic_requests"] += 1

            if reply != "NO_REPLY":
                stats["replied"] += 1
                log_fn(f"[comment_reply_agent_hindi] [{category}] {c['username']}: {c['text'][:60]}... -> {reply[:60]}...")

                if AUTO_REPLY:
                    if publish_reply(c["comment_id"], reply):
                        stats["published"] += 1
            else:
                log_fn(f"[comment_reply_agent_hindi] [{category}] {c['username']}: skipped (NO_REPLY)")

        except Exception as e:
            log_fn(f"[comment_reply_agent_hindi] Error processing comment {c.get('comment_id')}: {e}")
            continue

    log_fn(f"[comment_reply_agent_hindi] Done. Processed {stats['processed']}, "
           f"replied {stats['replied']}, published {stats['published']}, "
           f"topic requests {stats['topic_requests']}")
    return stats


if __name__ == "__main__":
    process_comments_hindi()
