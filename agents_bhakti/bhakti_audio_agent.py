# agents_bhakti/bhakti_audio_agent.py
"""Final audio mix (spec section 19): voice > music (timeline + sidechain duck) > SFX."""

import os
import shutil
import subprocess

LEAD_IN = float(os.environ.get("BHAKTI_LEAD_IN", "1.0"))   # music-only seconds before voice
TAIL = float(os.environ.get("BHAKTI_TAIL", "1.8"))          # music rings out after the voice
MUSIC_BASE_DB = -18.0                                      # spec: -16..-22 dB under voice
OUT_PATH = "output/bhakti_mix.m4a"


def _ffmpeg():
    try:
        from agents.video_agent import get_ffmpeg
        return get_ffmpeg()
    except Exception:
        return shutil.which("ffmpeg") or "ffmpeg"


def _volume_expr(timeline, lead):
    """Piecewise-constant gain with 0.6s smoothing is approximated by nested if();
    ffmpeg's volume filter re-evaluates per frame with eval=frame."""
    if not timeline:
        return "1"
    expr = str(timeline[-1][2])
    for start, end, gain in reversed(timeline[:-1]):
        expr = f"if(lt(t,{end + lead:.2f}),{gain},{expr})"
    return expr


def build_filter_graph(n_sfx, voice_len, timeline, sfx_plan, lead=LEAD_IN, tail=TAIL):
    total = lead + voice_len + tail
    lead_ms = int(lead * 1000)
    fade_out_st = max(total - tail - 0.3, 0)
    g = [
        # input 0 = voice, 1 = music, 2.. = sfx
        f"[0:a]adelay={lead_ms}|{lead_ms},apad=whole_dur={total:.2f},asplit=2[vkey][vmix]",
        f"[1:a]volume={MUSIC_BASE_DB}dB,volume='{_volume_expr(timeline, lead)}':eval=frame,"
        f"afade=t=in:st=0:d=1.2,afade=t=out:st={fade_out_st:.2f}:d={tail + 0.3:.2f},"
        f"atrim=0:{total:.2f}[bg]",
        "[bg][vkey]sidechaincompress=threshold=0.03:ratio=8:attack=25:release=600:makeup=1[duck]",
    ]
    labels = ["[duck]", "[vmix]"]
    for i, s in enumerate(sfx_plan):
        at_ms = int((s["at"] + lead) * 1000)
        g.append(
            f"[{i + 2}:a]atrim=0:{s['max_dur']:.2f},afade=t=out:st={max(s['max_dur'] - 0.5, 0):.2f}:d=0.5,"
            f"volume={s['gain_db']}dB,adelay={at_ms}|{at_ms},apad=whole_dur={total:.2f}[sfx{i}]"
        )
        labels.append(f"[sfx{i}]")
    g.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:dropout_transition=0:normalize=0,"
             f"alimiter=limit=0.89,loudnorm=I=-14:TP=-1.5:LRA=8,atrim=0:{total:.2f}[aout]")
    return ";".join(g), total


def mix_audio(voice_path, music_path, timeline, sfx_plan=None, out_path=OUT_PATH):
    """Returns (out_path, total_duration, lead_in). Raises on ffmpeg failure."""
    from agents_bhakti.bhakti_voice_agent import probe_duration
    sfx_plan = sfx_plan or []
    voice_len = probe_duration(voice_path)
    graph, total = build_filter_graph(len(sfx_plan), voice_len, timeline, sfx_plan)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cmd = [_ffmpeg(), "-y", "-i", voice_path, "-stream_loop", "-1", "-i", music_path]
    for s in sfx_plan:
        cmd += ["-i", s["path"]]
    cmd += ["-filter_complex", graph, "-map", "[aout]", "-t", f"{total:.2f}",
            "-c:a", "aac", "-b:a", "192k", out_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 and sfx_plan:
        print(f"[bhakti_audio] mix with SFX failed, retrying without: {r.stderr[-300:]}")
        return mix_audio(voice_path, music_path, timeline, [], out_path)
    if r.returncode != 0:
        raise RuntimeError(f"Audio mix failed: {r.stderr[-500:]}")
    return out_path, total, LEAD_IN
