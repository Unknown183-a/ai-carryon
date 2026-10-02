# agents_bhakti/bhakti_research_agent.py
"""Structured devotional research (spec section 3).

Extends agents_bhakti.research_agent: same sourcing rules, but returns a
dict the scene/story agents can rely on. Falls back to the legacy free-text
research wrapped in a minimal dict if the LLM does not return valid JSON.
"""

import json
import re

from agents_bhakti.model_invoke_agent_bhakti import safe_invoke

REQUIRED_KEYS = ["topic", "deity", "main_event", "emotion", "setting", "key_visuals"]


def _extract_json(text):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found")
    return json.loads(text[start:end + 1])


def research_bhakti_topic(topic):
    clean_topic = topic.split("||PATTERN:")[0].strip()
    prompt = f"""You are an expert in Hindu dharma and puranic stories.
Research this devotional topic accurately: {clean_topic}

Return ONLY a JSON object (no markdown) with these keys:
{{
  "topic": "...",
  "deity": "main deity (Krishna/Shiva/Hanuman/Ram/Durga/Ganesh/Radha/Vishnu/Lakshmi/Saraswati/other)",
  "main_story": "3-5 sentence summary of the story or meaning",
  "characters": ["..."],
  "location": "...",
  "context": "mythological/historical context, 1-2 sentences",
  "main_event": "the key event",
  "emotional_moment": "the most moving moment",
  "ending": "how it ends / the lesson",
  "facts": ["1-3 authentic, widely accepted facts"],
  "emotion": "one word: devotion|wonder|compassion|courage|peace",
  "setting": "real-world setting, e.g. ancient temple, river bank, forest",
  "key_visuals": ["5-8 REAL-WORLD photographable things: temple, diya, river, sunrise, devotee praying..."]
}}

Rules: only authentic, widely accepted sources; never invent miracles or
quotes; respectful tone. key_visuals must be real scenery, not deity faces."""
    try:
        data = _extract_json(safe_invoke(prompt, temperature=0.3).content)
        for k in REQUIRED_KEYS:
            data.setdefault(k, [] if k == "key_visuals" else "")
        if not isinstance(data["key_visuals"], list):
            data["key_visuals"] = [str(data["key_visuals"])]
        data["topic"] = data.get("topic") or clean_topic
        return data
    except Exception as e:
        print(f"[bhakti_research] structured research failed ({e}) — using legacy research")
        from agents_bhakti.research_agent import research
        return {
            "topic": clean_topic, "deity": "", "main_event": "", "emotion": "devotion",
            "setting": "temple", "key_visuals": ["temple", "diya", "devotee praying", "sunrise"],
            "main_story": research(clean_topic),
        }
