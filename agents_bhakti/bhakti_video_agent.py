# agents_bhakti/bhakti_video_agent.py
"""Cinematic per-scene editing + final composition (spec sections 10, 11, 21).

Each scene clip is cropped to 9:16, given a subtle camera move, a warm
devotional grade and vignette, then segments are joined with crossfades,
captions are burned in and the pre-mixed audio is muxed. Segments are
cached by (scene, clip, duration) so QA can re-render a single scene."""

import datetime
import os
import shutil
import subprocess

W, H, FPS = 1080, 1920, 30
XFADE = 0.4
SEG_DIR = "output/bhakti_segs"
CRF = os.environ.get("BHAKTI_CRF", "21")
PRESET = os.environ.get("BHAKTI_PRESET", "veryfast")


def _ffmpeg():
    try:
        from agents.video_agent import get_ffmpeg
        return get_ffmpeg()
    except Exception:
        return shutil.which("ffmpeg") or "ffmpeg"


def _probe_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", path], capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def camera_filter(camera, d):
    """Cropped-to-9:16 stream -> moving 1080x1920 stream. Subtle (<=12% travel)."""
    d = max(d, 0.5)
    cover = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    if camera == "slow_zoom_out":
        return (f"{cover},scale=w='trunc({W}*(1.12-0.12*t/{d:.3f})/2)*2':h=-2:eval=frame,"
                f"crop={W}:{H}")
    if camera in ("pan_left", "pan_right"):
        big_w, big_h = int(W * 1.15) // 2 * 2, int(H * 1.15) // 2 * 2
        x = f"(iw-{W})*t/{d:.3f}" if camera == "pan_right" else f"(iw-{W})*(1-t/{d:.3f})"
        return (f"scale={big_w}:{big_h}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H}:x='{x}':y='(ih-{H})/2'")
    if camera == "vertical_pan":
        big_w, big_h = int(W * 1.15) // 2 * 2, int(H * 1.15) // 2 * 2
        return (f"scale={big_w}:{big_h}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H}:x='(iw-{W})/2':y='(ih-{H})*(1-t/{d:.3f})'")
    # default: slow_zoom_in
    return (f"{cover},scale=w='trunc({W}*(1+0.12*t/{d:.3f})/2)*2':h=-2:eval=frame,"
            f"crop={W}:{H}")


def grade_filter(purpose):
    f = ["eq=contrast=1.05:saturation=1.10:gamma=0.98",
         "colorbalance=rm=0.04:bm=-0.04:rh=0.03:bh=-0.03",     # warm golden tint
         "vignette=PI/5"]
    if purpose == "divine":
        # soft bloom: blend a blurred copy back with screen
        f.append("split[a][b];[b]gblur=sigma=22[bl];[a][bl]blend=all_mode=screen:all_opacity=0.22")
    return ",".join(f)


def render_segment(scene, duration, seg_path=None):
    """Render one scene to a silent 1080x1920 mp4 of `duration` seconds."""
    os.makedirs(SEG_DIR, exist_ok=True)
    seg = seg_path or os.path.join(SEG_DIR, f"seg_{scene.scene_id}_{scene.clip_id}_{duration:.2f}_{scene.camera}.mp4")
    if os.path.exists(seg) and os.path.getsize(seg) > 1000:
        return seg
    clip_len = _probe_duration(scene.clip_path)
    pre = ""
    if 0 < clip_len < duration:
        ratio = duration / clip_len
        if ratio <= 1.35:                       # stretch gently instead of visibly looping
            pre = f"setpts={ratio:.4f}*PTS,"
    vf = f"{pre}fps={FPS},{camera_filter(scene.camera, duration)},{grade_filter(scene.purpose)},setsar=1,format=yuv420p"
    cmd = [_ffmpeg(), "-y", "-stream_loop", "-1", "-i", scene.clip_path, "-t", f"{duration:.3f}",
           "-an", "-vf", vf, "-r", str(FPS), "-c:v", "libx264", "-preset", PRESET,
           "-crf", CRF, "-pix_fmt", "yuv420p", seg]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        if os.path.exists(seg):
            os.remove(seg)
        raise RuntimeError(f"segment {scene.scene_id} render failed: {r.stderr[-400:]}")
    return seg


def scene_durations(scenes, lead, tail):
    """Visual length per scene: first absorbs the music lead-in, last the tail."""
    ds = [max(s.end - s.start, 1.5) for s in scenes]
    ds[0] += lead
    ds[-1] += tail
    return ds


def compose_video(scenes, audio_path, captions_path, lead, tail, out_dir="output"):
    """Segments -> xfade chain -> burn captions -> mux mixed audio. Returns final path."""
    ff = _ffmpeg()
    durs = scene_durations(scenes, lead, tail)
    n = len(scenes)
    segs = []
    for i, (sc, d) in enumerate(zip(scenes, durs)):
        seg_len = d + (XFADE if i < n - 1 else 0)   # overlap eaten by the next crossfade
        segs.append(render_segment(sc, seg_len))

    if n == 1:
        chain, last = "", "[0:v]"
    else:
        parts, last, cum = [], "[0:v]", 0.0
        for i in range(1, n):
            cum += durs[i - 1]
            kind = "fadewhite" if scenes[i].purpose == "divine" else "fade"
            out = f"[x{i}]"
            parts.append(f"{last}[{i}:v]xfade=transition={kind}:duration={XFADE}:offset={cum:.3f}{out}")
            last = out
        chain = ";".join(parts) + ";"
    total = sum(durs)
    has_caps = captions_path and os.path.exists(captions_path)
    fonts = "/usr/share/fonts"
    cap = (f"{last}ass='{captions_path}':fontsdir={fonts}[vout]" if has_caps else f"{last}null[vout]")
    graph = chain + cap

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(out_dir, f"video_{ts}.mp4")

    def run(g, with_caps):
        cmd = [ff, "-y"]
        for s in segs:
            cmd += ["-i", s]
        cmd += ["-i", audio_path, "-filter_complex", g, "-map", "[vout]", "-map", f"{n}:a",
                "-t", f"{total:.3f}", "-r", str(FPS), "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out]
        return subprocess.run(cmd, capture_output=True, text=True)

    r = run(graph, True)
    if r.returncode != 0 and has_caps:
        print(f"[bhakti_video] caption burn failed, retrying without: {r.stderr[-300:]}")
        r = run(chain + f"{last}null[vout]", False)
    if r.returncode != 0:
        raise RuntimeError(f"compose failed: {r.stderr[-600:]}")
    final = os.path.join(out_dir, "final_video.mp4")
    shutil.copy(out, final)
    return final
