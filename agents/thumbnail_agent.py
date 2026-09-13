from dotenv import load_dotenv
load_dotenv()

from agents.model_invoke_agent_english import safe_invoke


def generate_thumbnail_text(topic):
    prompt = f"""
        You are a YouTube growth expert.

        Generate ONE viral thumbnail text.

        Rules:
        - 2 to 5 words
        - ALL CAPS
        - Curiosity driven
        - Emotional
        - Click-worthy
        
        Topic:
        {topic}

        Examples:

        THIS CHANGES EVERYTHING

        AI IS TAKING OVER

        YOU NEED THIS TOOL

        DON'T MISS THIS

        Return ONLY thumbnail text.
        """

    response = safe_invoke(prompt, temperature=1)
    return response.content