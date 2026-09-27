# agents_bhakti/research_agent.py
"""
Devotional research — asks for the story beats, meaning, and significance
behind a mythological topic/mantra/festival, rather than the generic
"important facts + latest information" framing used for tech topics.
"""

from agents_bhakti.model_invoke_agent_bhakti import safe_invoke


def research(topic):
    prompt = f"""
Aap ek Hindu dharm aur pauranik kathaon ke gyaani hain.

Is devotional topic par sahi, authentic jaankari do:

{topic}

Give:
1. Story/prasang ke mukhya beats (agar ek katha hai) YA mantra/concept ka
   arth (agar ek mantra/shlok hai)
2. Iska dharmik/aadhyatmik mahatva
3. Ek interesting ya kam-jaana-jaata hua detail
4. Is se judi koi sikh ya sandesh

Rules:
- Sirf authentic, widely-accepted pauranik/dharmik jaankari do — kalpना mat karo
- Respectful, devotional tone rakho
- Concise raho
"""
    response = safe_invoke(prompt, temperature=0.4)
    return response.content
