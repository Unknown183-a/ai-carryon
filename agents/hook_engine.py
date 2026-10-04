# agents/hook_engine.py
"""
Universal Hook Engine — every Short opens on a topic-relevant visual hook.

    script -> story analysis + hook intent (1 LLM call, heuristic fallback)
           -> 3-5 hook queries -> Pexels retrieval (10-20 candidates)
           -> scoring (1 batched LLM call, lexical fallback)
           -> relevance >= 70% gate -> duplicate check -> best hook
           -> download + quality control -> hook dict for the renderer

Shared by the English, Hindi, Cricket and Bhakti pipelines (Gaming cuts its hook
from the real gameplay: agents_gaming/gameplay_hook.py). Per-channel behaviour
lives in CHANNEL_PROFILES.

Pexels: this module does NOT talk to Pexels itself. Retrieval goes through
agents.video_clip_agent.search_hook_videos(), the existing Pexels client.

Honest limitation: Pexels returns no tags or description, only the page title
(the URL slug). Relevance is therefore judged from that title text, not from the
pixels. That is why the LLM relevance is blended with a deterministic
keyword-overlap check instead of being trusted alone.

Contract: select_hook() NEVER raises and returns None when there is no suitable
hook, in which case the pipeline renders exactly as it did before.
Kill switches: HOOK_ENGINE=0 (all channels) or HOOK_ENGINE_<CHANNEL>=0.
"""
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

# ── Spec constants ────────────────────────────────────────────────────────
MIN_RELEVANCE = float(os.getenv("HOOK_MIN_RELEVANCE", "0.70"))       # spec §10 quality gate
WEIGHTS = {"relevance": 0.40, "visual": 0.25, "curiosity": 0.20,     # spec §11
           "emotional": 0.10, "continuity": 0.05}
HOOK_TYPES = ("shock", "curiosity", "action", "emotional", "mystery")   # spec §7
HOOK_DIR = "assets/hook_clips"
MIN_QUERIES, MAX_QUERIES = 3, 5
MAX_CANDIDATES = 20
MIN_POOL = 6                       # fewer usable candidates than this -> expand queries
MIN_HOOK_SEC, MAX_HOOK_SEC = 0.8, 3.0
REUSE_COOLDOWN_DAYS = int(os.getenv("HOOK_REUSE_COOLDOWN_DAYS", "14"))
REUSE_PENALTY = 0.05               # per previous use (outside the cooldown)
MAX_REMEMBERED_CLIPS = 300
MAX_LOG_ENTRIES = 30

# Clip-duration window requested from Pexels (spec §8: 1-10s).
PEXELS_DURATION_MIN, PEXELS_DURATION_MAX = 1, 10

_BASE_DURATION = {"action": 1.2, "shock": 1.5, "curiosity": 2.0,       # spec §12
                  "emotional": 2.5, "mystery": 2.5}

CHANNEL_PROFILES = {
    "english": {
        "hook_types": HOOK_TYPES,
        "anchors": ["technology", "ai", "computer"],
        "fallback_queries": ["artificial intelligence technology", "computer code screen",
                             "futuristic technology interface"],
        "block_terms": (),
        "style": "tech / AI news for a US audience; prefer screens, hardware, robots, code, labs",
    },
    "hindi": {
        "hook_types": HOOK_TYPES,
        "anchors": ["experiment", "science", "technology"],
        "fallback_queries": ["science experiment close up", "laboratory liquid reaction",
                             "circuit board close up"],
        "block_terms": (),
        "style": "experiment / science / tech videos for an Indian audience; concrete objects and reactions",
    },
    "cricket": {
        "hook_types": HOOK_TYPES,
        "anchors": ["cricket", "stadium"],
        "fallback_queries": ["cricket stadium crowd", "cricket player celebration",
                             "cricket match action"],
        "block_terms": ("football", "soccer", "basketball", "tennis", "baseball"),
        "style": "cricket match / news Shorts; player reactions, crowd, stadium, boundary moments",
    },
    "bhakti": {
        # Devotional channel: reverent hooks only. No shock/action framing.
        "hook_types": ("emotional", "mystery", "curiosity"),
        "anchors": ["temple", "diya", "aarti"],
        "fallback_queries": ["diya flame close up", "temple bells", "aarti lamp"],
        "block_terms": ("shock", "shocked", "dramatic", "intense", "explosion", "fire",
                        "fight", "weapon", "blood", "violent", "scary", "horror", "demon",
                        "statue", "idol", "god"),
        "style": "devotional Hindi Shorts; calm, reverent stock footage: diya, temple, aarti, flowers, "
                 "river ghats. Never dramatic or violent imagery, never depictions of deities",
    },
    "gaming": {
        "hook_types": HOOK_TYPES,
        "anchors": ["gaming"],
        "fallback_queries": [],
        "block_terms": (),
        "style": "gaming moments (hook is cut from the real gameplay, not Pexels)",
    },
}
_DEFAULT_PROFILE = CHANNEL_PROFILES["english"]

# Words that describe *style*, not subject: they must not count as topical overlap.
_STOP = {"the", "a", "an", "of", "in", "on", "at", "to", "and", "with", "for", "from", "by",
         "is", "are", "this", "that", "video", "footage", "stock", "clip", "shot", "view"}
_STYLE = {"dramatic", "intense", "reaction", "moment", "close", "up", "closeup", "slow",
          "motion", "cinematic", "scene", "shocked", "emotional", "epic", "amazing",
          "beautiful", "mystery", "mysterious", "suspense", "curious"}


# ── Models (spec §27) ─────────────────────────────────────────────────────
@dataclass
class HookCandidate:
    clip_id: str
    provider: str
    url: str
    duration: float
    relevance_score: float = 0.0
    visual_score: float = 0.0
    curiosity_score: float = 0.0
    emotional_score: float = 0.0
    continuity_score: float = 0.0
    final_score: float = 0.0
    query: str = ""
    # extras the renderer / logger need
    title: str = ""
    width: int = 0
    height: int = 0
    files: list = field(default_factory=list)
    scorer: str = ""
    penalty: float = 0.0


# ── Small utilities ───────────────────────────────────────────────────────
def hook_enabled(channel):
    if os.getenv("HOOK_ENGINE", "1").strip() == "0":
        return False
    return os.getenv(f"HOOK_ENGINE_{str(channel).upper()}", "1").strip() != "0"


def _profile(channel):
    return CHANNEL_PROFILES.get(channel, _DEFAULT_PROFILE)


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _norm01(x, default=0.0):
    """LLMs answer on 0-1, 0-10 or 0-100 scales; accept all, return 0-1."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    if v > 10:
        v /= 100.0
    elif v > 1:
        v /= 10.0
    return _clamp(v, 0.0, 1.0)


def _tokens(text):
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _stem(w):
    return w[:-1] if len(w) > 3 and w.endswith("s") else w


def slug_title(url):
    """Pexels page URL -> readable title.
    https://www.pexels.com/video/a-wifi-router-3045678/ -> 'a wifi router'"""
    m = re.search(r"/video/([^/]+)/?$", url or "")
    if not m:
        return ""
    return " ".join(w for w in m.group(1).split("-") if not w.isdigit())


def _extract_json(text):
    if not text:
        return None
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    # Prose around the JSON: try whichever bracket type opens FIRST, so an array
    # of objects ("Here you go: [{...}, {...}]") is not mistaken for one object.
    pairs = sorted((("{", "}"), ("[", "]")),
                   key=lambda p: text.find(p[0]) if p[0] in text else len(text) + 1)
    for open_c, close_c in pairs:
        a, b = text.find(open_c), text.rfind(close_c)
        if a != -1 and b > a:
            try:
                return json.loads(text[a:b + 1])
            except Exception:
                continue
    return None


def _call_llm(invoke, prompt):
    """Run a channel's safe_invoke; return text or None. Never raises."""
    if invoke is None:
        return None
    try:
        resp = invoke(prompt)
        content = getattr(resp, "content", resp)
        if isinstance(content, list):
            content = "".join(p if isinstance(p, str) else (p.get("text") or "") for p in content)
        return str(content or "")
    except Exception as e:
        print(f"[hook] LLM call failed: {e}")
        return None


# ── 1. Story analysis + hook intent (spec §5-§7) ──────────────────────────
STORY_FIELDS = ("main_topic", "main_event", "emotion", "subject", "location",
                "action", "story_type", "target_audience")


def _clean_query(q, block_terms=()):
    q = re.sub(r"[^a-zA-Z0-9 ]", " ", str(q)).lower()
    words = [w for w in q.split() if w and w not in _STOP][:4]
    if any(w in block_terms for w in words):
        return ""
    return " ".join(words)


def _dedupe_keep_order(items):
    seen, out = set(), []
    for x in items:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _fallback_plan(topic, hint_hook_type, profile):
    """No-LLM plan: topic keywords + the channel's anchor/fallback footage."""
    words = [w for w in _tokens(topic) if len(w) > 2 and w not in _STOP][:4]
    story = {k: "" for k in STORY_FIELDS}
    story.update(main_topic=topic, subject=" ".join(words[:2]))
    hook_type = hint_hook_type if hint_hook_type in profile["hook_types"] else profile["hook_types"][0]
    keywords = _dedupe_keep_order(words + list(profile["anchors"]))
    intent = {"hook_type": hook_type, "emotion": "", "visual_need": [],
              "keywords": keywords, "minimum_relevance": MIN_RELEVANCE}
    queries = []
    if words:
        queries.append(" ".join(words[:3]))
    queries += list(profile["fallback_queries"])
    return story, intent, queries


def generate_story_and_intent(topic, script, channel, invoke=None, hint_hook_type=None, context=""):
    """One LLM call -> (story_analysis, hook_intent, queries). Falls back to a
    deterministic plan if the LLM is unavailable or returns garbage."""
    profile = _profile(channel)
    allowed = [t for t in profile["hook_types"]]
    fb_story, fb_intent, fb_queries = _fallback_plan(topic, hint_hook_type, profile)

    prompt = f"""You are the hook planner for a vertical YouTube Short ({profile['style']}).
Pick the opening visual (1-3 seconds of STOCK FOOTAGE from Pexels) that best fits this story.

Topic: {topic}
{('Extra context: ' + context) if context else ''}
Script (opening): {(script or '')[:700]}

Return ONLY this JSON:
{{"story": {{"main_topic": "", "main_event": "", "emotion": "", "subject": "", "location": "",
            "action": "", "story_type": "", "target_audience": ""}},
 "intent": {{"hook_type": "<one of {allowed}>", "emotion": "", "visual_need": ["..."],
            "keywords": ["5-8 English words that describe the subject/event"]}},
 "queries": ["3 to 5 stock-footage search queries"]}}

Rules:
- Choose hook_type from the story itself{(' (a text hook of type ' + hint_hook_type + ' was already written; prefer it)') if hint_hook_type else ''}: shock = something unexpected, curiosity = information gap, action = intense movement, emotional = feeling-led story, mystery = suspense.
- Queries: English, 2-4 words, things a camera can film (objects, close-ups, reactions, places). Most specific first. Each query a different idea, all tied to the subject and event.
- No brand names, logos, on-screen text or news events. Never pick footage of an unrelated subject just because it is dramatic."""
    data = _extract_json(_call_llm(invoke, prompt)) if invoke else None

    if not isinstance(data, dict) or not isinstance(data.get("queries"), list):
        if invoke:
            print("[hook] planner fell back to heuristic plan")
        story, intent, queries = fb_story, fb_intent, fb_queries
    else:
        story = {k: str((data.get("story") or {}).get(k, "") or "") for k in STORY_FIELDS}
        raw_intent = data.get("intent") or {}
        htype = str(raw_intent.get("hook_type", "")).strip().lower()
        if htype not in allowed:
            htype = hint_hook_type if hint_hook_type in allowed else fb_intent["hook_type"]
        kws = [w for w in (str(k).lower().strip() for k in (raw_intent.get("keywords") or [])) if w]
        intent = {
            "hook_type": htype,
            "emotion": str(raw_intent.get("emotion", "") or story.get("emotion", "")),
            "visual_need": [str(v) for v in (raw_intent.get("visual_need") or [])][:5],
            "keywords": _dedupe_keep_order(kws + fb_intent["keywords"]),
            "minimum_relevance": MIN_RELEVANCE,
        }
        queries = list(data["queries"])

    queries = build_queries(queries, intent, profile, fb_queries)
    return story, intent, queries


def build_queries(queries, intent, profile, fallback_queries=()):
    """Clean, dedupe, and pad/trim to 3-5 queries (spec §9)."""
    block = tuple(profile.get("block_terms", ()))
    out = _dedupe_keep_order([_clean_query(q, block) for q in queries])
    kws = [k for k in intent.get("keywords", []) if k not in _STOP]
    if len(out) < MIN_QUERIES and kws:                      # top up from intent keywords
        out = _dedupe_keep_order(out + [_clean_query(" ".join(kws[:2]), block),
                                        _clean_query(" ".join(kws[:3]), block)])
    if len(out) < MIN_QUERIES:                              # then the channel's safe footage
        out = _dedupe_keep_order(out + [_clean_query(q, block) for q in
                                        list(fallback_queries) + list(profile["fallback_queries"])])
    return out[:MAX_QUERIES]


def expand_queries(queries, intent, profile):
    """Query expansion (spec §21): broader but still story-connected queries,
    used only when the first retrieval pool is thin."""
    block = tuple(profile.get("block_terms", ()))
    kws = [k for k in intent.get("keywords", []) if k not in _STOP]
    extra = []
    for q in queries[:2]:
        words = q.split()
        if len(words) > 2:
            extra.append(" ".join(words[:2]))               # drop the tail
            extra.append(" ".join(words[-2:]))              # drop the head
    if kws:
        extra += [" ".join(kws[:2]), f"{kws[0]} close up"]
    for a in profile["anchors"][:2]:
        extra.append(f"{a} close up")                       # channel theme, still on-topic
    extra += list(profile["fallback_queries"])
    extra = [_clean_query(q, block) for q in extra]
    return [q for q in _dedupe_keep_order(extra) if q not in set(queries)][:MAX_QUERIES]


# ── 2. Retrieval (spec §8-§9) ─────────────────────────────────────────────
def _default_search(queries, **kw):
    from agents.video_clip_agent import search_hook_videos      # the existing Pexels client
    return search_hook_videos(queries, **kw)


def retrieve_candidates(queries, intent, profile, exclude_ids=(), search_fn=None):
    """Search Pexels with the hook queries (+ one expansion round if the pool is
    thin). Returns a list of HookCandidate (unscored)."""
    search = search_fn or _default_search
    kw = dict(orientation="portrait", duration_min=PEXELS_DURATION_MIN,
              duration_max=PEXELS_DURATION_MAX, per_query=6, max_total=MAX_CANDIDATES,
              exclude_ids=list(exclude_ids))
    try:
        raw = list(search(queries, **kw))
        if len(raw) < MIN_POOL:
            extra = expand_queries(queries, intent, profile)
            if extra:
                print(f"[hook] thin pool ({len(raw)}) - expanding queries: {extra}")
                have = {str(c["id"]) for c in raw}
                raw += [c for c in search(extra, **kw) if str(c["id"]) not in have]
    except Exception as e:
        print(f"[hook] retrieval failed: {e}")
        return []
    out = []
    for c in raw[:MAX_CANDIDATES]:
        out.append(HookCandidate(
            clip_id=str(c["id"]), provider="pexels", url=c.get("url", ""),
            duration=float(c.get("duration") or 0), query=c.get("query", ""),
            title=slug_title(c.get("url", "")), width=int(c.get("width") or 0),
            height=int(c.get("height") or 0), files=c.get("files") or []))
    return out


# ── 3. Scoring (spec §10-§11) ─────────────────────────────────────────────
def topical_terms(story, intent):
    """Stemmed subject/event words (style words and stopwords removed)."""
    text = " ".join([str(story.get(k, "")) for k in
                     ("main_topic", "main_event", "subject", "location", "action")]
                    + list(intent.get("keywords", [])))
    return {_stem(w) for w in _tokens(text)
            if len(w) > 2 and w not in _STOP and w not in _STYLE}


def lexical_relevance(title, terms):
    """Deterministic overlap score: two distinct topical words in the clip title
    = 1.0, one = 0.5, none = 0."""
    hits = len(terms & {_stem(w) for w in _tokens(title)})
    return min(1.0, hits / 2.0)


def technical_score(c):
    """Objective visual quality from the metadata Pexels gives us."""
    short = min(c.width, c.height) if c.width and c.height else 0
    res = 1.0 if short >= 1080 else 0.7 if short >= 720 else 0.3
    orient = 1.0 if c.height > c.width else 0.6
    dur = 1.0 if 1.5 <= c.duration <= 8 else 0.7
    return 0.5 * res + 0.3 * orient + 0.2 * dur


def final_score(c):
    return (c.relevance_score * WEIGHTS["relevance"] + c.visual_score * WEIGHTS["visual"]
            + c.curiosity_score * WEIGHTS["curiosity"] + c.emotional_score * WEIGHTS["emotional"]
            + c.continuity_score * WEIGHTS["continuity"])


def score_candidates(cands, story, intent, invoke=None):
    """Fill every score on every candidate (in place) and return them.

    relevance = 0.75 * LLM judgement + 0.25 * keyword overlap, so an LLM that is
    merely 'impressed' by a vague title cannot reach 70% without any word in
    common with the story. Without an LLM: keyword overlap only (strict)."""
    terms = topical_terms(story, intent)
    llm = {}
    if invoke and cands:
        lines = "\n".join(f"{i}. \"{c.title or 'untitled'}\" ({c.duration:.0f}s, "
                          f"{'portrait' if c.height > c.width else 'landscape'})"
                          for i, c in enumerate(cands))
        prompt = f"""Rate stock-footage clips as the opening hook of a Short. You only see each clip's title.

Story: {json.dumps(story, ensure_ascii=False)}
Hook intent: {json.dumps({k: intent[k] for k in ('hook_type', 'emotion', 'visual_need', 'keywords')}, ensure_ascii=False)}

Clips:
{lines}

For EACH clip give scores from 0.0 to 1.0:
- relevance: would this footage visibly match the story's SUBJECT and EVENT?
    0.70-0.90 = clearly the right subject or a fitting scene of the same theme (e.g. a stadium crowd for a cricket comeback)
    0.40-0.65 = same broad area but wrong subject/event (generic batting for one player's catch)
    below 0.30 = different topic. A vague title can never score above 0.6.
- visual: how striking/scroll-stopping would it look
- curiosity: does it make a viewer want to know what happens
- emotional: strength of emotion it carries
- continuity: how smoothly the story can continue from it
Be harsh; most clips deserve below 0.7 relevance.

Return ONLY JSON: [{{"i": 0, "relevance": 0.0, "visual": 0.0, "curiosity": 0.0, "emotional": 0.0, "continuity": 0.0}}]"""
        data = _extract_json(_call_llm(invoke, prompt))
        if isinstance(data, dict):
            data = data.get("scores") or data.get("clips") or []
        for row in data if isinstance(data, list) else []:
            if isinstance(row, dict) and isinstance(row.get("i"), int) and 0 <= row["i"] < len(cands):
                llm[row["i"]] = row

    for i, c in enumerate(cands):
        lex = lexical_relevance(c.title, terms)
        tech = technical_score(c)
        row = llm.get(i)
        if row:
            c.scorer = "llm"
            c.relevance_score = round(0.75 * _norm01(row.get("relevance")) + 0.25 * lex, 3)
            c.visual_score = round(0.6 * _norm01(row.get("visual"), tech) + 0.4 * tech, 3)
            c.curiosity_score = round(_norm01(row.get("curiosity"), 0.5), 3)
            c.emotional_score = round(_norm01(row.get("emotional"), 0.5), 3)
            c.continuity_score = round(_norm01(row.get("continuity"), c.relevance_score), 3)
        else:
            c.scorer = "lexical"
            c.relevance_score = round(lex, 3)
            c.visual_score = round(tech, 3)
            c.curiosity_score = c.emotional_score = 0.5
            c.continuity_score = round(lex, 3)
        c.final_score = round(final_score(c), 4)
    return cands


# ── 4. Duplicate memory (spec §23-§24, channel-isolated) ──────────────────
def _hist_key(channel):
    return f"hook_history:{channel}"


def load_history(channel, meta_get):
    empty = {"clips": {}, "log": []}
    if not meta_get:
        return empty
    try:
        raw = meta_get(_hist_key(channel))
        data = json.loads(raw) if raw else empty
        data.setdefault("clips", {})
        data.setdefault("log", [])
        return data
    except Exception as e:
        print(f"[hook] history unavailable (load): {e}")
        return empty


def _days_since(iso):
    try:
        t = datetime.fromisoformat(iso)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - t).total_seconds() / 86400.0
    except Exception:
        return 9999.0


def apply_history(cands, history):
    """Reject clips this channel used within the cooldown; penalise older reuse.
    Returns the surviving candidates (final_score already adjusted)."""
    kept = []
    for c in cands:
        h = history["clips"].get(c.clip_id)
        if h:
            if _days_since(h.get("used_at", "")) < REUSE_COOLDOWN_DAYS:
                continue
            c.penalty = min(0.2, REUSE_PENALTY * int(h.get("usage_count", 1)))
            c.final_score = round(c.final_score - c.penalty, 4)
        kept.append(c)
    return kept


def record_usage(hook, topic, channel, meta_get, meta_set, video_id=None):
    """Call AFTER a successful upload (same convention as cricket's asset
    registry), so a failed run never burns a clip. Also writes the spec §29
    selection log. Never raises."""
    if not hook:
        return
    entry = {
        "video_id": video_id, "channel_id": channel, "topic": topic,
        "hook_query": hook.get("query"), "hook_clip_id": hook.get("clip_id"),
        "hook_provider": hook.get("provider"), "hook_type": hook.get("hook_type"),
        "relevance_score": hook.get("relevance"), "visual_score": hook.get("visual_score"),
        "curiosity_score": hook.get("curiosity_score"), "final_score": hook.get("final_score"),
        "hook_duration": hook.get("duration"), "selection_reason": hook.get("selection_reason"),
        "used_at": datetime.now(timezone.utc).isoformat(),
    }
    print("HOOK_LOG " + json.dumps(entry, ensure_ascii=False))
    if not (meta_get and meta_set):
        return
    try:
        hist = load_history(channel, meta_get)
        if hook.get("provider") == "pexels" and hook.get("clip_id"):
            prev = hist["clips"].get(str(hook["clip_id"]), {})
            hist["clips"][str(hook["clip_id"])] = {
                "usage_count": int(prev.get("usage_count", 0)) + 1,
                "used_at": entry["used_at"], "topic": topic}
            if len(hist["clips"]) > MAX_REMEMBERED_CLIPS:
                newest = sorted(hist["clips"].items(), key=lambda kv: kv[1].get("used_at", ""))
                hist["clips"] = dict(newest[-MAX_REMEMBERED_CLIPS:])
        hist["log"] = (hist["log"] + [entry])[-MAX_LOG_ENTRIES:]
        meta_set(_hist_key(channel), json.dumps(hist))
    except Exception as e:
        print(f"[hook] history not saved: {e}")


# ── 5. Selection, duration, QC (spec §12, §22, §26) ───────────────────────
def hook_duration(hook_type, clip_duration):
    """Dynamic target: action 1.2s, shock 1.5s, curiosity 2s, emotional/mystery
    2.5s, never longer than the clip itself, clamped to 0.8-3s."""
    base = _BASE_DURATION.get(hook_type, 2.0)
    return round(_clamp(min(base, float(clip_duration or base)), MIN_HOOK_SEC, MAX_HOOK_SEC), 2)


def quality_check(hook, min_relevance=MIN_RELEVANCE):
    """Pre-render QC (spec §22). Returns (ok, reason)."""
    if not hook:
        return False, "no hook"
    if float(hook.get("relevance", 0)) < min_relevance:
        return False, f"relevance {hook.get('relevance')} < {min_relevance}"
    if not (MIN_HOOK_SEC <= float(hook.get("duration", 0)) <= MAX_HOOK_SEC + 0.2):
        return False, f"duration {hook.get('duration')}s outside {MIN_HOOK_SEC}-{MAX_HOOK_SEC}s"
    path = hook.get("path", "")
    if not path or not os.path.exists(path) or os.path.getsize(path) < 10_000:
        return False, "file missing or too small (broken download)"
    w, h = hook.get("width", 0), hook.get("height", 0)
    if w and h and min(w, h) < 540:
        return False, f"resolution {w}x{h} too low"
    return True, "ok"


def _clear_dir(folder):
    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder):
        try:
            os.remove(os.path.join(folder, f))
        except OSError:
            pass


def _to_hook_dict(c, intent, topic, channel, path, n_eligible, n_total):
    return {
        "provider": c.provider, "clip_id": c.clip_id, "url": c.url, "path": path, "start": 0.0,
        "duration": hook_duration(intent["hook_type"], c.duration),
        "hook_type": intent["hook_type"], "query": c.query, "title": c.title,
        "relevance": c.relevance_score, "visual_score": c.visual_score,
        "curiosity_score": c.curiosity_score, "emotional_score": c.emotional_score,
        "continuity_score": c.continuity_score, "final_score": c.final_score,
        "width": c.width, "height": c.height, "scorer": c.scorer,
        "topic": topic, "channel": channel,
        "selection_reason": (f"best of {n_eligible} eligible / {n_total} candidates "
                             f"(relevance {c.relevance_score:.2f} via {c.scorer}, "
                             f"score {c.final_score:.2f})"),
    }


def select_hook(topic, script, channel, invoke=None, meta_get=None, meta_set=None,
                hint_hook_type=None, context="", search_fn=None, download_fn=None,
                out_dir=HOOK_DIR):
    """Run the whole engine. Returns a hook dict for the renderer, or None
    ('no suitable hook' -> pipeline keeps its normal opening). Never raises.

    invoke   : the channel's own safe_invoke(prompt) (keeps its circuit breaker/budget)
    meta_get / meta_set : the channel DB's get_meta / set_meta (duplicate memory)
    """
    try:
        if not hook_enabled(channel):
            print(f"[hook] disabled for channel '{channel}'")
            return None
        profile = _profile(channel)
        clean_topic = (topic or "").split("||PATTERN:")[0].strip()

        story, intent, queries = generate_story_and_intent(
            clean_topic, script, channel, invoke, hint_hook_type, context)
        print(f"[hook] intent: type={intent['hook_type']} keywords={intent['keywords'][:6]}")
        print(f"[hook] queries: {queries}")
        if not queries:
            return None

        history = load_history(channel, meta_get)
        cands = retrieve_candidates(queries, intent, profile, search_fn=search_fn)
        if not cands:
            print("[hook] no candidates - keeping the normal opening")
            return None

        score_candidates(cands, story, intent, invoke)
        min_rel = float(intent.get("minimum_relevance", MIN_RELEVANCE))
        eligible = [c for c in cands if c.relevance_score >= min_rel]
        for c in sorted(cands, key=lambda x: -x.relevance_score)[:5]:
            print(f"[hook]   {'PASS' if c.relevance_score >= min_rel else 'REJECT'} "
                  f"rel={c.relevance_score:.2f} final={c.final_score:.2f} '{c.title}' ({c.query})")
        eligible = apply_history(eligible, history)
        if not eligible:
            print(f"[hook] none of {len(cands)} candidates reached relevance "
                  f"{min_rel:.0%} (or all recently used) - keeping the normal opening")
            return None
        eligible.sort(key=lambda c: -c.final_score)

        if download_fn is None:
            from agents.video_clip_agent import download_video_file as download_fn
        _clear_dir(out_dir)
        for c in eligible[:3]:                       # try the best few, first that passes QC wins
            path = os.path.join(out_dir, "hook.mp4")
            try:
                download_fn({"files": c.files}, path)
            except Exception as e:
                print(f"[hook] download failed for {c.clip_id}: {e}")
                continue
            hook = _to_hook_dict(c, intent, clean_topic, channel, path, len(eligible), len(cands))
            ok, why = quality_check(hook, min_rel)
            if ok:
                print(f"[hook] SELECTED {c.clip_id} '{c.title}' {hook['duration']}s - {hook['selection_reason']}")
                return hook
            print(f"[hook] QC rejected {c.clip_id}: {why}")
        return None
    except Exception as e:
        print(f"[hook] engine error (continuing without hook): {e}")
        return None
