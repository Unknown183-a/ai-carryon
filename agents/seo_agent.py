from dotenv import load_dotenv
load_dotenv()

from agents.model_invoke_agent_english import safe_invoke

PATTERN_PROMPTS = {
    "curiosity": "Start with 'Did You Know', 'Here's Why', or 'The Reason' — spark curiosity",
    "urgency": "Use urgency: 'This Changes Everything', 'Stop Doing This', 'Act Now Before'",
    "revelation": "Reveal a secret: 'Nobody Told You', 'The Hidden Truth', 'They Don't Want You to Know'",
    "number": "Use a number: '5 Reasons Why', '3 Things About', 'Top 7'",
    "question": "Ask a question: 'Is This the Future?', 'Can AI Really...?', 'What Happens When'",
    "warning": "Give a warning: 'Warning:', 'Before You Try', 'Don't Make This Mistake'",
}


def generate_seo(topic, script, comparison_insights=None, use_ab_titles=True):

    pattern = None
    if "||PATTERN:" in topic:
        topic, pattern_str = topic.split("||PATTERN:")
        pattern = pattern_str.strip()
        topic = topic.strip()

    pattern_instruction = PATTERN_PROMPTS.get(
        pattern,
        "Use a UNIQUE style — avoid starting with 'Crazy', 'Insane', or 'Amazing'"
    )

    # Add competitor title context if available
    competitor_context = ""
    if comparison_insights and not comparison_insights.get("error"):
        top_title = comparison_insights.get("top_competitor_title", "")
        top_views = comparison_insights.get("top_competitor_views", 0)
        if top_title:
            competitor_context = f"""
COMPETITOR INTELLIGENCE:
- Top performing title on this topic: "{top_title}" ({top_views:,} views)
- Study its style but DO NOT copy it — create something better and original
"""

    # Phase 3 — A/B Title Testing
    ab_winner_title = None
    ab_variations = []
    if use_ab_titles:
        try:
            from agents.ab_title_agent import get_best_title
            print("Running A/B title test...")
            ab_result = get_best_title(topic, script)
            ab_winner_title = ab_result["winner"]["title"]
            ab_variations = ab_result["variations"]
            print(f"A/B winner: {ab_winner_title} (score: {ab_result['winner']['score']}/10)")
        except Exception as e:
            print(f"A/B title test failed: {e}")

    prompt = f"""You are a YouTube SEO expert for an AI/Tech Shorts channel.

Generate ORIGINAL YouTube SEO content for this topic and script.

Topic: {topic}
Script: {script}
{competitor_context}

STRICT RULES:
- Channel niche: AI, Technology, Automation, Developer tools, Future Tech ONLY
- NEVER use these overused words to start titles: Crazy, Insane, Amazing, Unbelievable, Shocking
- Title pattern to use: {pattern_instruction}
- Title must reference the actual topic — not be generic
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

    # Use A/B tested title if available and scored higher
    final_title = ab_winner_title if ab_winner_title else title

    return {
        "title": final_title,
        "description": description,
        "hashtags": hashtag_list,
        "topic": topic,
        "pattern": pattern,
        "ab_variations": ab_variations,
        "ab_winner": ab_winner_title,
    }
