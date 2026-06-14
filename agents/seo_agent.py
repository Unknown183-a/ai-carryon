from dotenv import load_dotenv
load_dotenv()

def generate_seo(topic, script):
    from langchain_groq import ChatGroq
    llm = ChatGroq(model="llama-3.3-70b-versatile")

    prompt = f"""
You are a YouTube SEO expert specializing in viral AI/Tech Shorts content.

Given the topic and script below, generate ORIGINAL YouTube SEO content that:
- Has a UNIQUE angle (never copy or closely paraphrase other videos)
- Is copyright-safe (original wording, your own perspective)
- Is optimized for YouTube algorithm and click-through rate
- Targets AI, tech, and automation audience

Topic: {topic}
Script: {script}

TITLE RULES:
- Under 60 characters
- Use power words: Secret, Insane, Revealed, Warning, Finally, Nobody, Crazy
- Create curiosity or urgency
- Never copy the original video title
- Add numbers or emojis where natural

DESCRIPTION RULES:
- 3-4 sentences, 150-200 words total
- First sentence must hook the viewer instantly
- Include the main keyword naturally 2-3 times
- End with a call to action (Like, Subscribe, Comment)
- Completely original — not copied from any source

TAGS RULES:
- 15 hashtags mixing: broad (#AI #Tech #Shorts) + specific (#AIAutomation #MachineLearning) + trending (#2026Tech)
- All lowercase except first letter
- No brand names or copyrighted terms

Return in EXACTLY this format, no extra text:

TITLE: <title here>
DESCRIPTION: <full description here>
HASHTAGS: <15 hashtags space-separated>
"""

    response = llm.invoke(prompt).content

    title = ""
    description = ""
    hashtags = ""

    for line in response.split("\n"):
        line = line.strip()
        if line.upper().startswith("TITLE:"):
            title = line.split(":", 1)[1].strip()
        elif line.upper().startswith("DESCRIPTION:"):
            description = line.split(":", 1)[1].strip()
        elif line.upper().startswith("HASHTAGS:"):
            hashtags = line.split(":", 1)[1].strip()

    # Clean up title — remove quotes if any
    title = title.strip('"').strip("'")

    # Parse hashtags into list
    hashtag_list = [h.strip() for h in hashtags.split() if h.startswith("#")]

    return {
        "title": title,
        "description": description,
        "hashtags": hashtag_list
    }
