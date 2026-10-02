# agents_bhakti/bhakti_caption_agent.py
"""Dynamic Shorts captions (spec section 20): short phrases, large Devanagari font,
timed to each scene's real narration window, emphasised words, subtle entrance."""

import os
import re

FONT_NAME = os.environ.get("BHAKTI_CAPTION_FONT", "Noto Sans Devanagari")
MAX_WORDS = 3
SAFE_MARGIN_V = 560     # px from bottom; keeps clear of Shorts UI (bottom ~20%) and top bar
MIN_PHRASE_SEC = 0.45

HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{FONT_NAME},92,&H00FFFFFF,&H000000FF,&H00000000,&H96000000,1,0,0,0,100,100,0,0,1,6,2,2,90,90,{SAFE_MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

YELLOW = "&H0000DCFF&"   # BGR of (255,220,0)
WHITE = "&H00FFFFFF&"


def _t(sec):
    sec = max(sec, 0)
    h, m = int(sec // 3600), int(sec % 3600 // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _esc(s):
    return s.replace("\\", "").replace("{", "").replace("}", "")


def split_phrases(text, max_words=MAX_WORDS):
    """Break at punctuation first, then into chunks of <= max_words."""
    out = []
    for part in re.split(r"(?<=[,;।.!?])\s+", text.strip()):
        words = part.split()
        for i in range(0, len(words), max_words):
            out.append(words[i:i + max_words])
    # avoid a dangling single word when it can merge with the previous phrase
    merged = []
    for p in out:
        if merged and len(p) == 1 and len(merged[-1]) < max_words + 1 and not re.search(r"[।.!?]$", merged[-1][-1]):
            merged[-1].extend(p)
        else:
            merged.append(p)
    return merged


def build_caption_events(scenes, segments, lead):
    """[(start, end, words, emphasis_set)] on the final video timeline."""
    seg_by_id = {s["scene_id"]: s for s in segments}
    events = []
    for sc in scenes:
        seg = seg_by_id.get(sc.scene_id)
        t0 = lead + (seg["start"] if seg else sc.start)
        t1 = lead + (seg["end"] if seg else sc.end)
        phrases = split_phrases(sc.narration)
        weights = [max(sum(len(w) for w in p), 1) for p in phrases]
        total_w = float(sum(weights))
        cur = t0
        for p, w in zip(phrases, weights):
            dur = max((t1 - t0) * w / total_w, MIN_PHRASE_SEC)
            events.append((cur, min(cur + dur, t1 + 0.05), p, set(sc.emphasis)))
            cur += dur
    # no overlaps: clamp each end to the next start
    for i in range(len(events) - 1):
        s, e, p, em = events[i]
        events[i] = (s, min(e, events[i + 1][0]), p, em)
    return events


def generate_captions(scenes, segments, lead, out_path="output/bhakti_captions.ass"):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    lines = [HEADER]
    for start, end, words, emph in build_caption_events(scenes, segments, lead):
        parts = []
        for w in words:
            bare = re.sub(r"[,;।.!?]", "", w)
            if any(bare and (bare in e or e in bare) for e in emph):
                parts.append(f"{{\\c{YELLOW}\\fscx108\\fscy108}}{_esc(w)}{{\\c{WHITE}\\fscx100\\fscy100}}")
            else:
                parts.append(_esc(w))
        text = " ".join(parts)
        # subtle entrance: quick fade + tiny scale-up settle
        anim = "{\\fad(90,40)\\fscx92\\fscy92\\t(0,140,\\fscx100\\fscy100)}"
        lines.append(f"Dialogue: 0,{_t(start)},{_t(end)},Caption,,0,0,0,,{anim}{text}")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return out_path
