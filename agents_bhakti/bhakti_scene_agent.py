# agents_bhakti/bhakti_scene_agent.py
"""Scene planner (spec section 6, 8, 11): script -> story-following visual scenes."""

import json
import re

from agents_bhakti.bhakti_types import Scene
from agents_bhakti.model_invoke_agent_bhakti import safe_invoke

PURPOSES = ["hook", "setup", "conflict", "divine", "resolution", "ending"]
CAMERAS = ["slow_zoom_in", "slow_zoom_out", "pan_left", "pan_right", "vertical_pan"]
MOOD_BY_PURPOSE = {"hook": "mysterious", "setup": "warm", "conflict": "serious",
                   "divine": "reverent", "resolution": "uplifting", "ending": "calm"}
DEFAULT_SFX = {"hook": ["temple_bell"], "setup": ["birds"], "conflict": ["wind"],
               "divine": ["divine_chime"], "resolution": [], "ending": ["temple_bell"]}


def split_sentences(script):
    lines = [l.strip() for l in script.splitlines() if l.strip()]
    if len(lines) < 4:  # model ignored one-sentence-per-line
        lines = [s.strip() for s in re.split(r"(?<=[।.!?])\s+", script) if s.strip()]
    return lines


def group_into_scenes(sentences, min_scenes=5, max_scenes=8):
    """Group sentences into 5-8 contiguous scenes with roughly equal word counts."""
    total = sum(len(s.split()) for s in sentences) or 1
    n = max(min(len(sentences), max_scenes), min(min_scenes, len(sentences)))
    target = total / n
    groups, cur, cur_w = [], [], 0
    for i, s in enumerate(sentences):
        cur.append(s)
        cur_w += len(s.split())
        remaining_sentences = len(sentences) - i - 1
        remaining_groups = n - len(groups) - 1
        full_enough = cur_w >= target and remaining_sentences >= remaining_groups
        must_split = remaining_sentences == remaining_groups  # each leftover sentence needs its own scene
        if remaining_groups > 0 and (full_enough or must_split):
            groups.append(" ".join(cur))
            cur, cur_w = [], 0
    if cur:
        groups.append(" ".join(cur))
    return groups


def assign_purposes(count):
    """Map scene index -> story purpose along the 6-beat arc."""
    if count == 1:
        return ["hook"]
    out = []
    for i in range(count):
        idx = round(i * (len(PURPOSES) - 1) / (count - 1))
        out.append(PURPOSES[idx])
    out[0], out[-1] = "hook", "ending"
    return out


def _fallback_scene(i, purpose, narration, research):
    visuals = research.get("key_visuals") or ["temple", "diya", "sunrise"]
    v = visuals[i % len(visuals)]
    base = {
        "hook": ["Indian temple sunrise golden light", "Hindu temple morning mist"],
        "setup": ["Indian temple courtyard devotees", "ancient Hindu temple exterior"],
        "conflict": ["dark clouds storm temple", "wind blowing diya flame"],
        "divine": ["divine golden light rays", "aarti flame temple close up"],
        "resolution": ["devotee praying temple peaceful", "folded hands prayer silhouette"],
        "ending": ["diya oil lamp glowing", "temple bell sunset silhouette"],
    }[purpose]
    return Scene(
        scene_id=i + 1, purpose=purpose, narration=narration,
        visual_description=v, pexels_queries=[f"Indian {v}", f"Hindu {v}"] + base,
        camera=CAMERAS[i % len(CAMERAS)], mood=MOOD_BY_PURPOSE[purpose],
        music="soft devotional", sfx=list(DEFAULT_SFX[purpose]),
    )


def create_scene_plan(script, research):
    sentences = split_sentences(script)
    groups = group_into_scenes(sentences)
    purposes = assign_purposes(len(groups))
    numbered = "\n".join(f"{i+1} [{p}]: {g}" for i, (p, g) in enumerate(zip(purposes, groups)))
    prompt = f"""You are a film editor planning B-roll for a Hindi devotional Short.
Topic: {research.get('topic','')}  Deity: {research.get('deity','')}  Setting: {research.get('setting','')}
Available real-world visuals: {research.get('key_visuals')}

Scenes (narration already split):
{numbered}

For EACH scene return JSON. Visuals must follow the story continuity
(temple -> devotee enters -> prays -> problem/weather change -> divine light -> resolution),
not random scenery. Use ONLY real photographable stock footage ideas (temples, diyas, rivers,
sunrise, devotees seen from behind, storms, light rays, flowers). Never describe a deity's face/form
in pexels_queries; if the moment truly needs a deity or a supernatural event, set "needs_ai": true
AND still give symbolic stock queries (golden light, diya, temple) as fallback.

Return ONLY a JSON list:
[{{"scene_id":1,"visual_description":"...","pexels_queries":["3-5 English queries, 2-5 words each"],
"camera":"one of {CAMERAS}","mood":"...","music":"...","sfx":["subset of: temple_bell, conch, diya_fire, wind, rain, river, birds, footsteps, forest, crowd, divine_chime, thunder"],
"emphasis":["1-2 key Hindi words copied exactly from the narration"],"needs_ai":false}}]"""
    plan = {}
    try:
        raw = safe_invoke(prompt, temperature=0.4).content
        data = json.loads(raw[raw.find("["): raw.rfind("]") + 1])
        plan = {int(d["scene_id"]): d for d in data}
    except Exception as e:
        print(f"[bhakti_scene] LLM scene plan failed ({e}) — using deterministic plan")

    scenes = []
    for i, (p, g) in enumerate(zip(purposes, groups)):
        d = plan.get(i + 1)
        if not d or not d.get("pexels_queries"):
            scenes.append(_fallback_scene(i, p, g, research))
            continue
        cam = d.get("camera") if d.get("camera") in CAMERAS else CAMERAS[i % len(CAMERAS)]
        queries = [q for q in d["pexels_queries"] if isinstance(q, str)][:5]
        # always keep at least one safe symbolic fallback query
        queries.append("temple diya golden light")
        scenes.append(Scene(
            scene_id=i + 1, purpose=p, narration=g,
            visual_description=d.get("visual_description", ""),
            pexels_queries=queries, camera=cam,
            mood=d.get("mood") or MOOD_BY_PURPOSE[p], music=d.get("music", "soft devotional"),
            sfx=[s for s in d.get("sfx", []) if isinstance(s, str)][:2],
            emphasis=[w for w in d.get("emphasis", []) if isinstance(w, str) and w in g][:2],
            needs_ai=bool(d.get("needs_ai", False)),
        ))
    return scenes
