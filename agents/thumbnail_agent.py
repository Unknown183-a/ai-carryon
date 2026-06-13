from dotenv import load_dotenv
load_dotenv()

def generate_thumbnail_text(topic):
    from langchain_groq import ChatGroq
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=1)

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

    response = llm.invoke(prompt)
    return response.content