# agents_hindi/script_agent.py
from langchain_groq import ChatGroq
def get_llm():
    from langchain_groq import ChatGroq
    try:
        llm = ChatGroq(model="llama-3.3-70b-versatile", request_timeout=15)
        safe_invoke("hi")
        return llm
    except Exception as e:
        if "503" in str(e) or "capacity" in str(e) or "over_capacity" in str(e) or "overloaded" in str(e):
            print("Falling back to llama-3.1-8b-instant")
            return ChatGroq(model="llama-3.1-8b-instant")
        return ChatGroq(model="llama-3.1-8b-instant")


llm = get_llm()

def safe_invoke(prompt):
    import threading
    from langchain_groq import ChatGroq
    from langchain_google_genai import ChatGoogleGenerativeAI
    import os as _os

    result = [None]
    error = [None]

    def try_groq():
        try:
            llm = ChatGroq(model="llama-3.3-70b-versatile")
            result[0] = llm.invoke(prompt)
        except Exception as e:
            error[0] = e

    t = threading.Thread(target=try_groq)
    t.start()
    t.join(timeout=20)  # Wait max 20 seconds

    if result[0] is not None:
        return result[0]

    # Groq timed out or failed — use Gemini
    print("Groq timeout/fail — falling back to Gemini Flash")
    try:
        gemini = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=_os.getenv("GEMINI_API_KEY")
        )
        return gemini.invoke(prompt)
    except Exception:
        # Last resort — llama-3.1-8b-instant
        return ChatGroq(model="llama-3.1-8b-instant").invoke(prompt)


def create_script(research_data):
    prompt = f"""
    Ek YouTube Shorts script likho is research ke basis par.
    Target duration: 45-60 seconds bolne mein.
    Target word count: 150-200 words.

    Rules:
    - Pure Hindi mein likho (Hinglish allowed)
    - Ekdum natural aur conversational tone
    - Short punchy sentences. Max 10 words per sentence.
    - Pehle 3 seconds mein shocking hook
    - "Yaar suno...", "Sach mein?", "Aur suno...", "Bilkul sach hai..." jaisi expressions use karo
    - 3-4 interesting facts batao topic ke baare mein
    - "Par yahan baat aur hai...", "Aur sabse mast part..." jaisi transitions use karo
    - End mein CTA: "Follow karo aur aisi videos dekhte raho"
    - Koi labels mat likho jaise "Hook:", "CTA:"
    - Sirf bolne wale words likho, kuch aur nahi

    Research: {research_data}

    Example style:
    Yaar suno, ye sun ke tumhara dimaag ghoom jayega. Tumhare phone mein jo chip hai, usme itne transistors hain jitne Milky Way mein taare hain. Sach mein! Ek chip mein 15 billion transistors hote hain. Aur ye sab tumhari thumbnail se bhi chote hain. Aur suno, har transistor second mein billions baar on-off hota hai. Isliye tumhara phone itna fast hai. Par yahan baat aur hai. Ab hum aur chota nahi kar sakte. Physics ke laws aad aa rahe hain. Electrons seedha wall ke through nikal jaate hain. Ye main jhooth nahi bol raha. Toh companies ab chips ko upar ki taraf stack kar rahi hain. Future upar ki taraf ja raha hai. Follow karo aur aisi videos dekhte raho.
    """

    response = safe_invoke(prompt).content
    return response.strip()
