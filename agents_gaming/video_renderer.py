# agents_gaming/video_renderer.py
"""
Gaming V2 Sprint 2 (Phases 7, 8, 9, 10) — render the Short.

Differences from the shared renderer (agents/video_agent.py), which this does
NOT replace for other channels:
  * the clip's OWN audio is kept (game + streamer), narration is mixed over it
    with sidechain ducking: the game dips while the narrator speaks and comes
    straight back when they stop (spec §10)
  * the video's length comes from the CLIP, not the voiceover; narration lines
    sit on the clip's timeline (hook, setup, tag) instead of one long voiceover
  * edits come from editor_agent's plan: a gentle punch-in on the payoff and, for
    the biggest moments, a short freeze frame; the Hook Engine's gameplay cold
    open (a cut of the clip's own peak, with its sound) can be prepended
  * layout "fit" (default) shows the WHOLE 16:9 gameplay over a blurred backdrop,
    so HUD / kill feed / facecam are never cropped, and captions live in the
    backdrop bars — they cannot cover gameplay by construction (spec §12). Layout
    "fill" keeps the old centre-crop look.

Output timeline:  [cold open T0] [clip, with an optional freeze] [end hold]
"""
import os
import subprocess

from agents_gaming.audio_peak import ffmpeg_bin, has_audio_stream
from agents_gaming.moment_analyzer import probe_duration

W, H = 1080, 1920
MAX_TOTAL_SECONDS = 58.5          # stay inside the Shorts limit
GAME_VOLUME = float(os.getenv("GAMING_GAME_VOLUME", "0.9"))          # spec: 70-100%
NARRATION_VOLUME = float(os.getenv("GAMING_NARRATION_VOLUME", "1.3"))
LAYOUT = os.getenv("GAMING_LAYOUT", "fit").lower()
X264_PRESET = os.getenv("GAMING_X264_PRESET", "veryfast")
FONTS_DIR = os.getenv("GAMING_FONTS_DIR", "assets/fonts")
CAPTION_FONT = os.getenv("GAMING_CAPTION_FONT", "Arial")

ACCENT_BY_MOMENT = {   # ASS colours are &HBBGGRR
    "CLUTCH": "&H0000D7FF&", "INSANE_PLAY": "&H0000D7FF&", "RECORD": "&H0000D7FF&",
    "FAIL": "&H003C3CFF&", "RAGE": "&H003C3CFF&",
    "FUNNY": "&H0000E6FF&", "TROLL": "&H0000E6FF&",
}
DEFAULT_ACCENT = "&H0076E600&"
_EMPHASIS = {"NO", "WAY", "INSANE", "CLUTCH", "ONE", "LAST", "NEVER", "DEAD", "WON", "WIN", "BRO"}


# ── probing ────────────────────────────────────────────────────────────────

def probe_video_size(path):
    import re
    r = subprocess.run([ffmpeg_bin(), "-i", path], capture_output=True, text=True)
    m = re.search(r"Video:.*?,\s*(\d{2,5})x(\d{2,5})", r.stderr or "")
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


# ── timeline mapping ───────────────────────────────────────────────────────

def out_time(m, cold_open, freeze):
    """Main-clip time -> output time."""
    t0 = float(cold_open["duration"]) if cold_open else 0.0
    shift = float(freeze["duration"]) if freeze and m > float(freeze["at"]) else 0.0
    return t0 + m + shift


# ── captions (ASS) ─────────────────────────────────────────────────────────

def _ass_time(sec):
    sec = max(sec, 0.0)
    h, rem = divmod(sec, 3600)
    mnt, s = divmod(rem, 60)
    return f"{int(h)}:{int(mnt):02d}:{s:05.2f}"


def _ass_escape(text):
    return str(text).replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def _is_emphasis(raw):
    core = raw.strip(".,!?\"'")
    return (any(c.isdigit() for c in core) or raw.endswith("!") or core.upper() in _EMPHASIS
            or (len(core) > 1 and core.isupper()))


def caption_chunks(text, start, end, max_words=3):
    """Split a line into <=3-word chunks timed proportionally to word length.
    -> [(start, end, [(word, emphasised)])]"""
    words = [w for w in str(text).replace("...", " ").split() if w]
    if not words or end <= start:
        return []
    chunks = [words[i:i + max_words] for i in range(0, len(words), max_words)]
    weights = [sum(len(w) + 1 for w in c) for c in chunks]
    total, span, t, out = sum(weights), end - start, start, []
    for c, w in zip(chunks, weights):
        dur = span * w / total
        out.append((round(t, 2), round(t + dur, 2), [(x.upper().strip(), _is_emphasis(x)) for x in c]))
        t += dur
    return out


def _hook_size(text):
    n = len(str(text).split())
    return 92 if n <= 6 else 80 if n <= 10 else 68


def build_ass(placed, hook_text, cold_open, freeze, moment, layout, total):
    """Captions in OUTPUT time. Hook text in the top safe zone for the cold open
    + the voiced hook; narration lines as short chunks in the lower safe zone."""
    accent = ACCENT_BY_MOMENT.get((moment or {}).get("moment_type", ""), DEFAULT_ACCENT)
    fit = layout == "fit"
    hook_y, cap_y = (330, 1420) if fit else (300, 1380)
    head = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Hook,{CAPTION_FONT},84,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,6,0,5,70,70,0,1\n"
        f"Style: Cap,{CAPTION_FONT},76,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,5,0,5,70,70,0,1\n"
        f"Style: Reaction,{CAPTION_FONT},96,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,6,0,5,70,70,0,1\n"
        "\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    events = []

    def add(start, end, style, y, words, size=None):
        if end <= start:
            return
        parts = []
        for word, emph in words:
            w = _ass_escape(word)
            parts.append(f"{{\\c{accent}}}{w}{{\\c&H00FFFFFF&}}" if emph else w)
        pre = f"{{\\an5\\pos(540,{y})" + (f"\\fs{size}" if size else "") + "}"
        events.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(min(end, total))},{style},,0,0,0,,{pre}{' '.join(parts)}")

    # on-screen hook: over the cold open and until the voiced hook ends
    voiced_hook = next((p for p in placed if p["kind"] == "hook"), None)
    if hook_text:
        hook_end = out_time(voiced_hook["end"], cold_open, freeze) + 0.3 if voiced_hook else (
            (float(cold_open["duration"]) if cold_open else 0.0) + 2.2)
        words = [(w.upper(), _is_emphasis(w)) for w in str(hook_text).split()]
        add(0.0, hook_end, "Hook", hook_y, words, size=_hook_size(hook_text))

    for p in placed:
        if p["kind"] == "hook":
            continue
        s, e = out_time(p["start"], cold_open, freeze), out_time(p["end"], cold_open, freeze)
        style, size = ("Reaction", None) if p["kind"] == "tag" else ("Cap", None)
        for cs, ce, words in caption_chunks(p["text"], s, e):
            add(cs, ce, style, cap_y, words, size)
    return head + "\n".join(events) + "\n"


# ── filter graph ───────────────────────────────────────────────────────────

def _q(expr):
    return f"'{expr}'"


def _zoom_expr(zoom, t0):
    s, p, h, e = (float(zoom[k]) + t0 for k in ("start", "peak", "hold_until", "end"))
    up = f"min(1,max(0,(t-{s:.3f})/{max(p - s, 0.05):.3f}))"
    down = f"(1-min(1,max(0,(t-{h:.3f})/{max(e - h, 0.05):.3f})))"
    return f"{zoom['amount']:.4f}*{up}*{down}"


def build_graph(*, n_lines, placed, plan, cold_open, end_hold, main_dur, has_audio, layout,
                src_w, src_h, total, ass_path=None, fonts_dir=None):
    """Returns the filter_complex string. Input 0 = the clip; inputs 1..n = narration mp3s."""
    freeze = plan.get("freeze") if plan else None
    zoom = plan.get("zoom") if plan else None
    t0 = float(cold_open["duration"]) if cold_open else 0.0
    fz = float(freeze["duration"]) if freeze else 0.0
    f_at = float(freeze["at"]) if freeze else 0.0
    g = []

    # ---- video: cold open + main (+ freeze, + end hold) ----
    v_main_src, v_co_src = "vm", "vc"
    g.append("[0:v]fps=30,format=yuv420p,setsar=1," + ("split=2[vm][vc]" if cold_open else "null[vm]"))
    if cold_open:
        s = float(cold_open["start"])
        g.append(f"[vc]trim=start={s:.3f}:end={s + t0:.3f},setpts=PTS-STARTPTS[vco]")
    if freeze:
        k = max(int(round(fz * 30)), 1)
        g.append(f"[vm]split=2[vm1][vm2]")
        g.append(f"[vm1]trim=start=0:end={f_at:.3f},setpts=PTS-STARTPTS[va]")
        g.append(f"[vm2]trim=start={f_at:.3f},setpts=PTS-STARTPTS,loop=loop={k}:size=1:start=0[vb]")
        g.append("[va][vb]concat=n=2:v=1:a=0[vmain0]")
        main = "vmain0"
    else:
        main = "vm"
    if end_hold > 0:
        g.append(f"[{main}]tpad=stop_mode=clone:stop_duration={end_hold:.3f}[vmain]")
        main = "vmain"
    if cold_open:
        g.append(f"[vco][{main}]concat=n=2:v=1:a=0[vall]")
    else:
        g.append(f"[{main}]null[vall]")

    # ---- layout + zoom ----
    z = _zoom_expr(zoom, t0) if zoom else None
    use_fit = layout == "fit" and src_w and src_h and src_w > src_h
    if use_fit:
        fg_h = int(round(W * src_h / src_w / 2.0)) * 2
        g.append("[vall]split=2[bgs][fgs]")
        g.append(f"[bgs]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                 "boxblur=24:6,eq=brightness=-0.12:saturation=0.9[bg]")
        if z:
            g.append(f"[fgs]scale=w={_q(f'{W}*(1+{z})')}:h=-2:eval=frame,"
                     f"crop=w={W}:h={fg_h}:x={_q(f'(in_w-{W})/2')}:y={_q(f'(in_h-{fg_h})/2')}[fg]")
        else:
            g.append(f"[fgs]scale={W}:{fg_h}[fg]")
        g.append(f"[bg][fg]overlay=x=0:y=(H-h)/2[vl]")
    else:
        g.append(f"[vall]scale=-2:{H}:force_original_aspect_ratio=increase,setsar=1[vcov]")
        if z:
            g.append(f"[vcov]scale=w={_q(f'iw*(1+{z})')}:h=-2:eval=frame,"
                     f"crop=w={W}:h={H}:x={_q(f'(in_w-{W})/2')}:y={_q(f'(in_h-{H})/2')}[vl]")
        else:
            g.append(f"[vcov]crop={W}:{H}[vl]")
    if ass_path:
        fd = f":fontsdir={fonts_dir}" if fonts_dir else ""
        g.append(f"[vl]ass=filename={ass_path}{fd}[vout]")
    else:
        g.append("[vl]null[vout]")

    # ---- audio: game (with cold open / freeze silence / end hold) ----
    fmt = "aformat=sample_rates=48000:channel_layouts=stereo"
    if has_audio:
        g.append(f"[0:a]{fmt},volume={GAME_VOLUME}," + ("asplit=2[am][ac]" if cold_open else "anull[am]"))
    else:
        total_src = main_dur + t0 + 1.0
        g.append(f"anullsrc=r=48000:cl=stereo:d={total_src:.3f}," + ("asplit=2[am][ac]" if cold_open else "anull[am]"))
    if cold_open:
        s = float(cold_open["start"])
        g.append(f"[ac]atrim=start={s:.3f}:end={s + t0:.3f},asetpts=PTS-STARTPTS[aco]")
    if freeze:
        g.append("[am]asplit=2[am1][am2]")
        g.append(f"[am1]atrim=start=0:end={f_at:.3f},asetpts=PTS-STARTPTS[x1]")
        g.append(f"anullsrc=r=48000:cl=stereo:d={fz:.3f}[xs]")
        g.append(f"[am2]atrim=start={f_at:.3f},asetpts=PTS-STARTPTS[x2]")
        g.append("[x1][xs][x2]concat=n=3:v=0:a=1[amain0]")
        a_main = "amain0"
    else:
        a_main = "am"
    if end_hold > 0:
        g.append(f"[{a_main}]apad=pad_dur={end_hold:.3f}[amain]")
        a_main = "amain"
    if cold_open:
        g.append(f"[aco][{a_main}]concat=n=2:v=0:a=1[game]")
    else:
        g.append(f"[{a_main}]anull[game]")

    # ---- narration bus + ducking ----
    if n_lines:
        names = []
        for i, p in enumerate(placed):
            delay = int(round(out_time(p["start"], cold_open, freeze) * 1000))
            g.append(f"[{i + 1}:a]{fmt},volume={NARRATION_VOLUME},adelay={delay}|{delay}[n{i}]")
            names.append(f"[n{i}]")
        g.append((f"{''.join(names)}amix=inputs={n_lines}:duration=longest:normalize=0[narr]" if n_lines > 1
                  else f"{names[0]}anull[narr]"))
        # The narration bus must be as long as the video: sidechaincompress ends its output when
        # the sidechain input ends, which would silence the game audio after the last voice line.
        g.append(f"[narr]apad=whole_dur={total:.3f},asplit=2[nsc][nmix]")
        g.append("[game][nsc]sidechaincompress=threshold=0.03:ratio=8:attack=15:release=400:makeup=1[duck]")
        g.append("[duck][nmix]amix=inputs=2:duration=first:normalize=0[mix]")
        g.append("[mix]alimiter=limit=0.95[aout]")
    else:
        g.append("[game]alimiter=limit=0.95[aout]")
    return ";".join(g)


# ── render ─────────────────────────────────────────────────────────────────

def render_gaming_video(clip_path, placed, plan, hook_text, moment, cold_open=None, end_hold=0.0,
                        out_path="output/final_video.mp4", layout=None, work_dir="output/gaming_render"):
    """Render the Short. Returns {'path','duration','layout','graph'}; raises
    RuntimeError if ffmpeg fails (the scheduler then falls back to the shared renderer)."""
    layout = (layout or LAYOUT)
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    d = probe_duration(clip_path)
    if not d or d <= 0:
        raise RuntimeError("could not read the clip's duration")
    src_w, src_h = probe_video_size(clip_path)
    plan = plan or {}
    freeze = plan.get("freeze")
    t0 = float(cold_open["duration"]) if cold_open else 0.0
    fz = float(freeze["duration"]) if freeze else 0.0
    placed = [p for p in (placed or []) if p.get("path") and os.path.exists(p["path"])]
    total = min(t0 + d + fz + end_hold, MAX_TOTAL_SECONDS)

    ass_path = os.path.join(work_dir, "captions.ass")
    use_fit = layout == "fit" and src_w and src_h and src_w > src_h
    ass = build_ass(placed, hook_text, cold_open, freeze, moment, "fit" if use_fit else "fill", total)

    def run(with_captions):
        if with_captions:
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(ass)
        graph = build_graph(
            n_lines=len(placed), placed=placed, plan=plan, cold_open=cold_open, end_hold=end_hold,
            main_dur=d, has_audio=has_audio_stream(clip_path), layout=layout, src_w=src_w, src_h=src_h,
            total=total, ass_path=ass_path if with_captions else None,
            fonts_dir=FONTS_DIR if with_captions and os.path.isdir(FONTS_DIR) else None,
        )
        cmd = [ffmpeg_bin(), "-y", "-i", clip_path]
        for p in placed:
            cmd += ["-i", p["path"]]
        cmd += ["-filter_complex", graph, "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.3f}",
                "-c:v", "libx264", "-preset", X264_PRESET, "-crf", "23", "-pix_fmt", "yuv420p", "-r", "30",
                "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out_path]
        r = subprocess.run(cmd, capture_output=True, text=True)
        return r, graph

    r, graph = run(True)
    if r.returncode != 0:
        print(f"Render with captions failed, retrying without them: {(r.stderr or '')[-400:]}")
        r, graph = run(False)
    if r.returncode != 0:
        raise RuntimeError(f"gaming render failed: {(r.stderr or '')[-600:]}")

    out_d = probe_duration(out_path) or 0.0
    if abs(out_d - total) > 1.0 or not has_audio_stream(out_path):
        raise RuntimeError(f"rendered file looks wrong (duration {out_d:.1f}s vs expected {total:.1f}s)")
    print(f"Gaming video ready: {out_path} ({out_d:.1f}s, layout={'fit' if use_fit else 'fill'}, "
          f"{len(placed)} narration lines, zoom={bool(plan.get('zoom'))}, freeze={bool(freeze)}, "
          f"cold_open={bool(cold_open)})")
    return {"path": out_path, "duration": out_d, "layout": "fit" if use_fit else "fill", "graph": graph}
