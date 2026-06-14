from dotenv import load_dotenv
load_dotenv()

def create_script(research_data):
    from langchain_groq import ChatGroq
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.8)

    prompt = f"""
    Create a YouTube Shorts script based on this research:

    {research_data}

    STRICT RULES:
    - Total word count: 60 to 80 words MAXIMUM
    - When spoken aloud at normal pace, this must be 20-35 seconds long
    - Hook in first 5 words
    - Fast paced, Fireship style
    - End with "Follow for more wild tech facts"
    - Plain text only, NO symbols, NO hashtags, NO stage directions
    - NO lines like "Hook:" or "CTA:" — just the words to be spoken

    Return ONLY the script text, nothing else.
    """

    response = llm.invoke(prompt)
    script = response.content.strip()

    # Hard trim to 80 words if LLM ignores the limit
    words = script.split()
    if len(words) > 80:
        script = " ".join(words[:80])

    return script
