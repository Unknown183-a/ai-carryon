from dotenv import load_dotenv
load_dotenv()

# Title pattern instructions for diversity
PATTERN_PROMPTS = {
    "curiosity": "Start with 'Did You Know', 'Here's Why', or 'The Reason' — spark curiosity",
    "urgency": "Use urgency: 'This Changes Everything', 'Stop Doing This', 'Act Now Before'",
    "revelation": "Reveal a secret: 'Nobody Told You', 'The Hidden Truth', 'They Don't Want You to Know'",
    "number": "Use a number: '5 Reasons Why', '3 Things About', 'Top 7'",
    "question": "Ask a question: 'Is This the Future?', 'Can AI Really...?', 'What Happens When'",
    "warning": "Give a warning: 'Warning:', 'Before You Try', 'Don't Make This Mistake'",
}


def get_llm():
    from langchain_groq import ChatGroq
    try:
        llm = ChatGroq(model="llama-3.3-70b-versatile", request_timeout=15)
        safe_invoke("hi")
        return llm
    except Exception:
        from langchain_groq import ChatGroq
        return ChatGroq(model="llama-3.1-8b-instant")


def safe_invoke(prompt):
    from langchain_groq import ChatGroq
    try:
        return get_llm().invoke(prompt)
    except Exception as e:
        if "503" in str(e) or "capacity" in str(e) or "overloaded" in str(e):
            print("Falling back to llama-3.1-8b-instant")
            return ChatGroq(model="llama-3.1-8b-instant").invoke(prompt)
        raise e


def generate_seo(topic, script):
    llm = get_llm()

    # Extract pattern hint if present
    pattern = None
    if "||PATTERN:" in topic:
        topic, pattern_str = topic.split("||PATTERN:")
        pattern = pattern_str.strip()
        topic = topic.strip()

    pattern_instruction = PATTERN_PROMPTS.get(
        pattern,
        "Use a UNIQUE style — avoid starting with 'Crazy', 'Insane', or 'Amazing'"
    )

    prompt = f"""You are a YouTube SEO expert for an AI/Tech Shorts channel.

Generate ORIGINAL YouTube SEO content for this topic and script.

Topic: {topic}
Script: {script}

STRICT RULES:
- Channel niche: AI, Technology, Automation, Developer tools, Future Tech ONLY
- NEVER use these overused words to start titles: Crazy, Insane, Amazing, Unbelievable, Shocking
- Title pattern to use: {pattern_instruction}
- Title must reference the actual topic — not be generic (e.g. avoid just 'They Don\'t Know' with no context)
- Title must be under 60 characters
- Description must be original — never copy source material
- Tags must be AI/tech focused

TITLE RULES:
- Under 60 characters
- Follow the pattern instruction above strictly
- Make it click-worthy without being clickbait
- Add 1 relevant emoji at the end

DESCRIPTION RULES:
- 3-4 sentences, completely original angle
- First sentence hooks the viewer instantly
- Include main keyword 2-3 times naturally
- End with: "Like & Subscribe for daily AI insights! 🔔"

TAGS RULES:
- 15 hashtags: mix of broad (#AI #Tech #Shorts) + specific + trending 2026 tags
- All relevant to AI/tech niche only
- No brand names or copyrighted terms

Return in EXACTLY this format, no extra text:

TITLE: <title here>
DESCRIPTION: <description here>
HASHTAGS: <15 hashtags space-separated>
"""

    response = safe_invoke(prompt).content

    title = ""
    description = ""
    hashtags = ""

    for line in response.split("\n"):
        line = line.strip()
        if line.upper().startswith("TITLE:"):
            title = line.split(":", 1)[1].strip().strip('"').strip("'")
        elif line.upper().startswith("DESCRIPTION:"):
            description = line.split(":", 1)[1].strip()
        elif line.upper().startswith("HASHTAGS:"):
            hashtags = line.split(":", 1)[1].strip()

    hashtag_list = [h.strip() for h in hashtags.split() if h.startswith("#")]

    return {
        "title": title,
        "description": description,
        "hashtags": hashtag_list,
        "topic": topic,
        "pattern": pattern
    }
