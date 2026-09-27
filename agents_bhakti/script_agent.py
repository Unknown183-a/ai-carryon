# agents_bhakti/script_agent.py
from agents_bhakti.model_invoke_agent_bhakti import safe_invoke


def create_script(research_data, topic=None, comparison_insights=None):
    competitor_context = ""
    if comparison_insights and not comparison_insights.get("error"):
        top_title    = comparison_insights.get("top_competitor_title", "")
        avg_duration = comparison_insights.get("competitor_avg_duration_seconds", 0)
        recs         = comparison_insights.get("recommendations", [])
        competitor_context = f"""
COMPETITOR INTELLIGENCE (devotional market ke liye):
- Is topic par sabse popular video: "{top_title}"
- Ideal duration: {avg_duration}s — iske around rakho
- Suggestions: {'; '.join(recs[:2]) if recs else 'None'}
"""

    prompt = f"""
Ek YouTube Shorts devotional (Bhakti) script likho is research ke basis par.
Target duration: 30-40 seconds bolne mein (STRICT — 45 seconds se zyada nahi).
Target word count: EXACTLY 70 to 90 words. Yeh STRICT requirement hai.
{competitor_context}

Rules:
- Pure Hindi mein likho (Hinglish allowed for flow)
- Shraddha aur bhakti bhaav wala, shaant aur respectful tone — koi mazak ya
  clickbait tone NAHI, yeh dharmik content hai
- Short, spasht sentences. Max 10 words per sentence.
- Pehle 3 seconds mein ek bhavनात्मक ya curiosity wala hook — jaise "Kya aapko pata hai..."
  ya "Ek baar ki baat hai..."
- Kahani/mantra ke 3-4 mukhya baatein batao (story beats ya arth)
- "Kehte hain ki...", "Shastron mein likha hai...", "Isi liye..." jaisi
  transitions use karo
- End mein ek chhota aashirwad/CTA: "Jai Shri Ram. Aisi hi bhakti videos ke
  liye follow karein" (topic ke devta ke anusaar badlo — Krishna topic ho to
  "Radhe Radhe" ya "Jai Shri Krishna", Shiv topic ho to "Har Har Mahadev", etc.)
- Koi labels mat likho jaise "Hook:", "CTA:"
- Sirf bolne wale words likho, kuch aur nahi
- Script ekdum tight aur crisp rakho — 70-90 words se zyada mat jaana
- Kisi devta/dharm ka apmaan ya galat jaankari bilkul mat likho

Research: {research_data}

Example style (yeh example ~82 words ka hai, isi length ka target rakho):
Ek baar ki baat hai, jab Ram Setu banana tha, tab ek gilhari bhi madad karne
aayi thi. Sab bade-bade vanar patthar utha rahe the, par gilhari sirf apne
badan par ret lagakar samundar mein daal rahi thi. Kuch vanaron ne uska
mazak udaya, par Ram ji ne use pyar se utha liya. Unhone kaha, chhota
prayaas bhi utna hi mahatvapurna hai jitna bada. Isi liye Ram ji ko itna
karunamay mana jaata hai. Jai Shri Ram. Aisi hi bhakti videos ke liye
follow karein.
"""

    response = safe_invoke(prompt)
    script = response.content.strip()

    for attempt in range(3):
        words = script.split()
        if len(words) >= 70:
            break
        print(f"Bhakti script too short ({len(words)} words) — expanding, attempt {attempt+1}")
        prompt2 = (
            f"Yeh script sirf {len(words)} words ka hai. Isse EXACTLY 80 words tak expand karo.\n"
            f"Same bhakti bhaav, tone, aur topic rakho. Aur 1 devotional detail add karo.\n"
            f"Sirf expanded script return karo, koi labels ya explanation nahi.\n\n"
            f"Script to expand:\n{script}"
        )
        script = safe_invoke(prompt2).content.strip()
        print(f"Expansion attempt {attempt+1}: {len(script.split())} words")

    words = script.split()
    if len(words) > 95:
        script = " ".join(words[:95])
        print(f"Trimmed script to 95 words to stay under ~45s limit")

    final_word_count = len(script.split())
    print(f"Final Bhakti script: {final_word_count} words")

    return script
