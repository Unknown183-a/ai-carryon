from dotenv import load_dotenv
load_dotenv()

def create_script(research_data):
    from langchain_groq import ChatGroq
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.8)

    prompt = f"""
    Create a YouTube Shorts script based on this research:

    {research_data}

    STRICT RULES:
    - Total word count: EXACTLY 80 to 100 words
    - Must be 25-35 seconds when spoken aloud
    - Hook in first 5 words
    - Fast paced, Fireship style
    - End with "Follow for more wild tech facts"
    - Plain text only, NO symbols, NO hashtags, NO stage directions
    - NO labels like "Hook:" or "CTA:" — just spoken words

    Return ONLY the script text, nothing else.
    """

    response = llm.invoke(prompt)
    script = response.content.strip()

    # Hard enforce minimum 80 words
    words = script.split()
    if len(words) < 80:
        # Ask again with stricter prompt
        prompt2 = f"""
        Expand this script to exactly 90 words. Keep the same style and topic.
        Add more interesting facts or details.
        Return ONLY the expanded script, no labels.
        
        Current script ({len(words)} words):
        {script}
        """
        script = llm.invoke(prompt2).content.strip()

    # Hard trim to 100 words max
    words = script.split()
    if len(words) > 100:
        script = " ".join(words[:100])

    return script
