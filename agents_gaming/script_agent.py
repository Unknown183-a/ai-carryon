# agents_gaming/script_agent.py
from dotenv import load_dotenv
load_dotenv()

# Reuses the same Groq-first/Gemini-fallback invoke helper as the English
# channel — gaming scripts are English, same as agents/script_agent.py.
from agents.model_invoke_agent_english import safe_invoke


def create_gaming_script(clip_summary, structured=None):
    """One-clip hype/commentary script, ~20-35s of speech (roughly 55-90
    words at the pace used in agents/voice_agent.py). Written to sit OVER
    the real Twitch clip footage, not narrate a static image."""
    structured = structured or {}
    game = structured.get("game", "")
    broadcaster = structured.get("broadcaster", "")

    context_line = ""
    if broadcaster:
        context_line = f"This clip is from streamer {broadcaster}"
        if game:
            context_line += f" playing {game}."
        else:
            context_line += "."

    prompt = f"""You are a hype gaming commentator writing a YouTube Shorts voiceover
script that plays OVER a real gameplay clip (the viewer is watching the clip
while you talk, not looking at you).

Clip data:
{clip_summary}
{context_line}

STRICT RULES:
- 20-35 seconds of speech — total word count: 55-90 words
- First line is a HOOK about what's about to happen in the clip — specific to
  THIS clip; avoid stock openers like "Watch what happens", "You won't believe",
  "Nobody expected" or "Let's take a look"
- Do NOT describe the clip play-by-play like a boring recap — react to it
  like a hype gaming commentator would, short punchy sentences
- Mention the streamer's name and the game naturally, once each
- Last line: a short call to follow for more gaming clips
- Plain text only — no stage directions, no labels like "Hook:", no emojis,
  no hashtags

Return ONLY the script text, nothing else."""

    response = safe_invoke(prompt)
    script = response.content.strip()

    words = script.split()
    for _ in range(2):
        if len(words) >= 55:
            break
        prompt2 = (
            f"This script is only {len(words)} words. Expand it to ~75 words.\n"
            f"Keep the same hook and single-clip focus — do not add a second clip "
            f"or a full recap.\n\nScript:\n{script}"
        )
        script = safe_invoke(prompt2).content.strip()
        words = script.split()

    if len(words) > 90:
        script = " ".join(words[:90])

    return script


# ── Gaming V2 (Phases 3-5): hook -> commentary -> quality gate ──────────────

import json

RECENT_SCRIPTS_KEY = "gaming_recent_scripts"
RECENT_HOOKS_KEY = "gaming_recent_hook_types"
MAX_SCRIPT_ATTEMPTS = 3


def _load_recent(db, key, limit):
    try:
        raw = db.get_meta(key)
        return json.loads(raw)[-limit:] if raw else []
    except Exception:
        return []


def remember_script(db, script, hook_type=None):
    """Keep the last few scripts/hook types so later runs can detect repeated
    phrasing and hook types (bounded; stored in gaming_meta)."""
    try:
        scripts = _load_recent(db, RECENT_SCRIPTS_KEY, 9) + [script]
        db.set_meta(RECENT_SCRIPTS_KEY, json.dumps(scripts[-10:]))
        if hook_type:
            hooks = _load_recent(db, RECENT_HOOKS_KEY, 9) + [hook_type]
            db.set_meta(RECENT_HOOKS_KEY, json.dumps(hooks[-10:]))
    except Exception as e:
        print(f"Could not store recent script memory: {e}")


def create_gaming_script_v2(clip, moment, summary, structured, db=None):
    """V2 script pipeline for one analysed clip.

    Returns a dict:
      {"script", "hook", "quality", "attempts", "passed", "fallback"}
    `passed` is False when every attempt failed the quality bar — the caller
    must NOT upload that script. If hook/commentary generation breaks outright
    (LLM outage), falls back to the legacy single-prompt script (`fallback`=True).
    """
    from agents_gaming.hook_agent import generate_hooks
    from agents_gaming.commentary_agent import generate_commentary
    from agents_gaming.script_quality_agent import evaluate_script

    recent_scripts = _load_recent(db, RECENT_SCRIPTS_KEY, 5) if db else []
    recent_hooks = _load_recent(db, RECENT_HOOKS_KEY, 3) if db else []
    duration = clip.get("duration")

    hook = generate_hooks(moment, summary, recent_hook_types=recent_hooks)
    if hook:
        print(f"Hook [{hook['type']} {hook['score']}]: {hook['text']}")

    feedback, last = None, None
    for attempt in range(1, MAX_SCRIPT_ATTEMPTS + 1):
        try:
            script, local_issues = generate_commentary(
                moment, hook, summary, structured, duration=duration,
                recent_scripts=recent_scripts, feedback=feedback,
            )
        except Exception as e:
            print(f"Commentary generation failed ({e}) — falling back to legacy script")
            return {"script": create_gaming_script(summary, structured), "hook": hook,
                    "quality": None, "attempts": attempt, "passed": True, "fallback": True}

        quality = evaluate_script(script, moment, hook, summary, recent_scripts)
        if local_issues:  # a draft that still tripped a local guard can't pass
            quality["passed"] = False
            quality["issues"] = quality["issues"] + local_issues
        s = quality["scores"]
        print(f"Script attempt {attempt}: passed={quality['passed']} scores={s} issues={quality['issues']}")
        cand = {"script": script, "hook": hook, "quality": quality, "attempts": attempt,
                "passed": quality["passed"], "fallback": False}
        if quality["passed"]:
            return cand
        last = cand
        feedback = quality["feedback"] or "; ".join(quality["issues"])

    return last  # every attempt failed the bar -> passed=False (final draft, for logging)
