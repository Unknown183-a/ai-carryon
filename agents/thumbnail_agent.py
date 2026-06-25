from dotenv import load_dotenv
load_dotenv()

def get_llm():
    from langchain_groq import ChatGroq
    try:
        llm = ChatGroq(model="llama-3.3-70b-versatile", request_timeout=15)
        safe_invoke("hi")
        return llm
    except Exception:
        return ChatGroq(model="llama3-8b-8192")


def safe_invoke(prompt):
    from langchain_groq import ChatGroq
    try:
        return get_llm().invoke(prompt)
    except Exception as e:
        if "503" in str(e) or "capacity" in str(e) or "overloaded" in str(e):
            print("Falling back to llama3-8b-8192")
            return ChatGroq(model="llama3-8b-8192").invoke(prompt)
        raise e


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

    response = safe_invoke(prompt)
    return response.content