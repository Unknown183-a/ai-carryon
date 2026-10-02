# agents_bhakti/bhakti_qa_agent.py
"""Final QA + publish gate (spec sections 22, 29). ffmpeg/ffprobe based, no extra deps.

run_quality_check returns:
  {"scores": {visual, voice, audio, story, caption, technical}, "approved": bool,
   "failed_scenes": [scene_id, ...], "issues": [...]}
Scene-level problems (black frames, too dark) are mapped to scene ids so the
pipeline can swap just that clip and re-render instead of redoing everything.
"""

import os
import re
import subprocess

THRESHOLD = float(os.environ.get("BHAKTI_QA_THRESHOLD", "7"))   # spec suggests 8; calibrate after testing
MIN_DURATION, MAX_DURATION = 15.0, 60.0


def _ff():
    try:
        from agents.video_agent import get_ffmpeg
        return get_ffmpeg()
    except Exception:
        return "ffmpeg"


def _stderr(args):
    return subprocess.run([_ff(), "-hide_banner", "-nostats"] + args, capture_output=True, text=True).stderr


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate",
         "-show_entries", "format=duration", "-of", "default=nw=1", path], capture_output=True, text=True).stdout
    info = {}
    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            info.setdefault(k, v)
    return info


def parse_black_intervals(stderr):
    return [(float(a), float(b)) for a, b in
            re.findall(r"black_start:([\d.]+)\s+black_end:([\d.]+)", stderr)]


def parse_silences(stderr):
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", stderr)]
    durs = [float(x) for x in re.findall(r"silence_duration: ([\d.]+)", stderr)]
    return list(zip(starts, durs))


def scenes_at(scenes, intervals, lead, tail_end):
    """Scene ids whose visual window overlaps any (start, end) interval (video timeline)."""
    hit = set()
    for i, sc in enumerate(scenes):
        a = 0.0 if i == 0 else sc.start + lead
        b = tail_end if i == len(scenes) - 1 else sc.end + lead
        for s, e in intervals:
            if s < b and e > a:
                hit.add(sc.scene_id)
    return sorted(hit)


def check_visual(video, scenes, lead, duration):
    issues, failed = [], []
    err = _stderr(["-i", video, "-vf", "blackdetect=d=0.3:pix_th=0.12", "-an", "-f", "null", "-"])
    black = parse_black_intervals(err)
    if black:
        failed += scenes_at(scenes, black, lead, duration)
        issues.append(f"black frames at {[(round(a, 1), round(b, 1)) for a, b in black]}")
    ids = [s.clip_id for s in scenes if s.clip_id]
    if len(ids) != len(set(ids)):
        issues.append("repeated clip across scenes")
        seen, dup = set(), []
        for s in scenes:
            if s.clip_id in seen:
                dup.append(s.scene_id)
            seen.add(s.clip_id)
        failed += dup
    # brightness sample at each scene midpoint
    for i, sc in enumerate(scenes):
        t = lead + (sc.start + sc.end) / 2
        raw = subprocess.run([_ff(), "-v", "error", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1",
                              "-vf", "scale=32:56,format=gray", "-f", "rawvideo", "-"],
                             capture_output=True).stdout
        if raw:
            mean = sum(raw) / len(raw)
            if mean < 25 or mean > 240:
                issues.append(f"scene {sc.scene_id} brightness {mean:.0f}")
                failed.append(sc.scene_id)
    failed = sorted(set(failed))
    score = max(0.0, 10 - 3 * len(failed) - (1 if issues and not failed else 0))
    return score, issues, failed


def check_audio(video, duration):
    issues, score = [], 10.0
    err = _stderr(["-i", video, "-vn", "-af", "volumedetect,silencedetect=noise=-50dB:d=1.5", "-f", "null", "-"])
    mx = re.search(r"max_volume: (-?[\d.]+) dB", err)
    mean = re.search(r"mean_volume: (-?[\d.]+) dB", err)
    if mx and float(mx.group(1)) > -0.1:
        issues.append("audio clipping"); score -= 3
    if mean and float(mean.group(1)) < -30:
        issues.append(f"audio too quiet ({mean.group(1)} dB mean)"); score -= 3
    if mean and float(mean.group(1)) > -8:
        issues.append(f"audio too loud ({mean.group(1)} dB mean)"); score -= 2
    long_sil = [(s, d) for s, d in parse_silences(err) if s + d < duration - 2.5]  # ignore natural tail
    if long_sil:
        issues.append(f"long silence {long_sil[:2]}"); score -= 3
    return max(score, 0), issues


def check_voice(voice_path):
    if not voice_path or not os.path.exists(voice_path):
        return 0.0, ["voice file missing"]
    err = _stderr(["-i", voice_path, "-af", "volumedetect", "-f", "null", "-"])
    mean = re.search(r"mean_volume: (-?[\d.]+) dB", err)
    if not mean:
        return 3.0, ["voice unreadable"]
    m = float(mean.group(1))
    if m < -32:
        return 3.0, [f"voice too quiet ({m} dB)"]
    return 10.0, []


def check_captions(ass_path, duration):
    issues, score = [], 10.0
    if not ass_path or not os.path.exists(ass_path):
        return 4.0, ["captions missing"]
    events = []
    with open(ass_path, encoding="utf-8") as fh:
        lines = fh.readlines()
    for line in lines:
        if line.startswith("Dialogue:"):
            f = line.split(",", 9)
            def sec(t):
                h, m, s = t.split(":"); return int(h) * 3600 + int(m) * 60 + float(s)
            text = re.sub(r"\{[^}]*\}", "", f[9]).strip()
            events.append((sec(f[1]), sec(f[2]), text))
    if not events:
        return 2.0, ["no caption events"]
    for (s1, e1, _), (s2, _, _) in zip(events, events[1:]):
        if e1 > s2 + 0.02:
            issues.append("overlapping captions"); score -= 3; break
    if any(e > duration + 0.3 for _, e, _ in events):
        issues.append("caption past end of video"); score -= 2
    if any(len(t) > 34 for _, _, t in events):   # ~2 lines at 92px inside 900px
        issues.append("caption too long for safe area"); score -= 2
    if any(re.search(r"(?i)\b(hook|cta)\b\s*:", t) or not t for _, _, t in events):
        issues.append("label/empty caption text"); score -= 3
    if any(e - s < 0.3 for s, e, _ in events):
        issues.append("caption flashes too briefly"); score -= 1
    return max(score, 0), issues


def check_technical(video):
    info, issues, score = probe(video), [], 10.0
    if info.get("width") != "1080" or info.get("height") != "1920":
        issues.append(f"wrong resolution {info.get('width')}x{info.get('height')}"); score -= 5
    if info.get("codec_name") != "h264":
        issues.append("not h264"); score -= 3
    dur = float(info.get("duration", 0) or 0)
    if not (MIN_DURATION <= dur <= MAX_DURATION):
        issues.append(f"duration {dur:.1f}s outside {MIN_DURATION}-{MAX_DURATION}s"); score -= 5
    return max(score, 0), issues, dur


def run_quality_check(job, lead, threshold=THRESHOLD):
    video = job.final_video
    tech, tech_issues, duration = check_technical(video)
    vis, vis_issues, failed = check_visual(video, job.scenes, lead, duration)
    aud, aud_issues = check_audio(video, duration)
    voc, voc_issues = check_voice(job.voice_path)
    cap, cap_issues = check_captions(job.captions_path, duration)
    story = float(job.retention.get("average", 8)) if job.retention else 8.0
    scores = {"visual": vis, "voice": voc, "audio": aud, "story": story, "caption": cap, "technical": tech}
    # a scene-level failure (black frame, bad brightness, duplicate clip) always blocks publishing
    approved = all(v >= threshold for v in scores.values()) and not failed
    return {"scores": scores, "approved": approved, "failed_scenes": failed, "threshold": threshold,
            "issues": tech_issues + vis_issues + aud_issues + voc_issues + cap_issues}
