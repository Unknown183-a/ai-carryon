# agents_hindi/script_agent.py
from langchain_groq import ChatGroq


def safe_invoke(prompt):
    import threading
    from langchain_groq import ChatGroq
    from langchain_google_genai import ChatGoogleGenerativeAI
    import os as _os

    result = [None]

    def try_groq():
        try:
            llm = ChatGroq(model="llama-3.3-70b-versatile")
            result[0] = llm.invoke(prompt)
        except Exception:
            pass

    t = threading.Thread(target=try_groq)
    t.start()
    t.join(timeout=20)

    if result[0] is not None:
        return result[0]

    print("Groq timeout/fail — falling back to Gemini Flash")
    try:
        gemini = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=_os.getenv("GEMINI_API_KEY")
        )
        return gemini.invoke(prompt)
    except Exception:
        return ChatGroq(model="llama-3.1-8b-instant").invoke(prompt)


def create_script(research_data, topic=None, comparison_insights=None):
    # Build competitor context if available
    competitor_context = ""
    if comparison_insights and not comparison_insights.get("error"):
        top_title    = comparison_insights.get("top_competitor_title", "")
        avg_views    = comparison_insights.get("competitor_avg_views", 0)
        avg_duration = comparison_insights.get("competitor_avg_duration_seconds", 0)
        recs         = comparison_insights.get("recommendations", [])
        competitor_context = f"""
COMPETITOR INTELLIGENCE (Hindi market ke liye):
- Is topic par sabse popular video: "{top_title}"
- Competitor average views: {avg_views:,}
- Ideal duration: {avg_duration}s — iske around rakho
- Suggestions: {'; '.join(recs[:2]) if recs else 'None'}
"""

    prompt = f"""
Ek YouTube Shorts script likho is research ke basis par.
Target duration: 45-60 seconds bolne mein.
Target word count: EXACTLY 150 to 180 words. Yeh STRICT requirement hai.
{competitor_context}

Rules:
- Pure Hindi mein likho (Hinglish allowed)
- Ekdum natural aur conversational tone
- Short punchy sentences. Max 10 words per sentence.
- Pehle 3 seconds mein shocking hook
- "Yaar suno...", "Sach mein?", "Aur suno...", "Bilkul sach hai..." jaisi expressions use karo
- 4-5 interesting facts batao topic ke baare mein (zyada detail mein)
- "Par yahan baat aur hai...", "Aur sabse mast part..." jaisi transitions use karo
- End mein CTA: "Follow karo aur aisi videos dekhte raho"
- Koi labels mat likho jaise "Hook:", "CTA:"
- Sirf bolne wale words likho, kuch aur nahi
- IMPORTANT: Script chota mat likhna — kam se kam 150 words zaroor likho

Research: {research_data}

Example style (yeh example bhi 150+ words ka hai, isi length ka target rakho):
Yaar suno, ye sun ke tumhara dimaag ghoom jayega. Tumhare phone mein jo chip hai, usme itne transistors hain jitne Milky Way mein taare hain. Sach mein! Ek chip mein 15 billion transistors hote hain. Aur ye sab tumhari thumbnail se bhi chote hain. Aur suno, har transistor second mein billions baar on-off hota hai. Isliye tumhara phone itna fast hai. Par yahan baat aur hai. Ab hum aur chota nahi kar sakte. Physics ke laws aad aa rahe hain. Electrons seedha wall ke through nikal jaate hain. Ye main jhooth nahi bol raha. Toh companies ab chips ko upar ki taraf stack kar rahi hain. Ek aur interesting baat — yeh stacking technology already smartphones mein use ho rahi hai. Samsung aur TSMC dono is par kaam kar rahe hain. Aane wale 5 saalon mein yeh aur bhi advanced ho jayega. Future upar ki taraf ja raha hai, literally. Follow karo aur aisi videos dekhte raho.
"""

    response = safe_invoke(prompt)
    script = response.content.strip()

    # Hard enforce minimum 150 words — retry up to 3 times
    for attempt in range(3):
        words = script.split()
        if len(words) >= 150:
            break
        print(f"Hindi script too short ({len(words)} words) — expanding, attempt {attempt+1}")
        prompt2 = (
            f"Yeh script sirf {len(words)} words ka hai. Isse EXACTLY 170 words tak expand karo.\n"
            f"Same hook, style, aur topic rakho. Aur 2-3 specific facts, numbers, ya examples add karo.\n"
            f"Sirf expanded script return karo, koi labels ya explanation nahi.\n\n"
            f"Script to expand:\n{script}"
        )
        script = safe_invoke(prompt2).content.strip()
        print(f"Expansion attempt {attempt+1}: {len(script.split())} words")

    # Trim if way too long (over 220 words)
    words = script.split()
    if len(words) > 220:
        script = " ".join(words[:220])

    final_word_count = len(script.split())
    print(f"Final Hindi script: {final_word_count} words")

    return script
