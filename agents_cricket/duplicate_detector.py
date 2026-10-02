# agents_cricket/duplicate_detector.py
"""
Cricket V2 — Phase 1 (steps 2, 3, 5, 6): pure duplicate-detection helpers.

No database access here, so everything is unit-testable on its own. The
registry (agents_cricket/asset_registry.py) feeds these functions rows.

Cheap checks run before expensive ones (spec section 72):
    metadata/temporal/cooldown  ->  SHA-256  ->  perceptual hash
"""
import hashlib
import os

import numpy as np
from PIL import Image

# Starting values from the spec (sections 8 and 60) — tune from analytics.
CONFIG = {
    "clip_cooldown_days": int(os.getenv("CRICKET_CLIP_COOLDOWN_DAYS", "30")),
    "max_recent_video_usage": int(os.getenv("CRICKET_MAX_RECENT_USAGE", "1")),
    "phash_max_distance": 8,    # mean Hamming distance (of 64 bits) = "potential duplicate"
    "dhash_max_distance": 12,   # secondary visual check must agree
    "min_overlap_seconds": 1.0,  # "significant" temporal overlap
}

FRAME_POSITIONS = (0.2, 0.5, 0.8)  # relative positions sampled per clip


# ── Step 2: exact duplicates ──────────────────────────────────────────────

def calculate_sha256(file_path):
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            sha.update(chunk)
    return sha.hexdigest()


# ── Step 3: near duplicates (pHash / dHash / aHash) ───────────────────────

def _bits_to_hex(bits):
    value = 0
    for b in bits:
        value = (value << 1) | int(b)
    return f"{value:016x}"


def _dct_matrix(n):
    k = np.arange(n).reshape(-1, 1)
    i = np.arange(n).reshape(1, -1)
    m = np.cos(np.pi * (2 * i + 1) * k / (2 * n))
    m[0, :] *= 1 / np.sqrt(2)
    return m * np.sqrt(2 / n)


_DCT32 = _dct_matrix(32)


def phash(img):
    """64-bit DCT perceptual hash (hex). Survives resize/re-encode/compression."""
    g = np.asarray(img.convert("L").resize((32, 32), Image.LANCZOS), dtype=np.float64)
    dct = _DCT32 @ g @ _DCT32.T
    low = dct[:8, :8].flatten()
    return _bits_to_hex(low > np.median(low[1:]))


def dhash(img):
    g = np.asarray(img.convert("L").resize((9, 8), Image.LANCZOS), dtype=np.float64)
    return _bits_to_hex((g[:, 1:] > g[:, :-1]).flatten())


def ahash(img):
    g = np.asarray(img.convert("L").resize((8, 8), Image.LANCZOS), dtype=np.float64)
    return _bits_to_hex((g > g.mean()).flatten())


def hamming(hex_a, hex_b):
    return bin(int(hex_a, 16) ^ int(hex_b, 16)).count("1")


def perceptual_fingerprint(video_path):
    """Samples frames at fixed relative positions and returns
    'p1,p2,p3|d1,d2,d3|a1,a2,a3' (pHash | dHash | aHash per frame).
    Fixed *relative* positions make re-encoded/resized copies line up."""
    from moviepy import VideoFileClip

    clip = VideoFileClip(video_path)
    try:
        dur = clip.duration or 0.0
        frames = [clip.get_frame(min(dur * p, max(dur - 0.05, 0))) for p in FRAME_POSITIONS]
    finally:
        clip.close()
    imgs = [Image.fromarray(f) for f in frames]
    return "|".join(",".join(fn(im) for im in imgs) for fn in (phash, dhash, ahash))


def _mean_distance(group_a, group_b):
    a, b = group_a.split(","), group_b.split(",")
    n = min(len(a), len(b))
    if n == 0:
        return 64.0
    return sum(hamming(a[i], b[i]) for i in range(n)) / n


def is_near_duplicate(fp_a, fp_b, cfg=CONFIG):
    """Potential duplicate when pHash is close; confirmed only if dHash agrees
    (the 'secondary visual check' from spec section 5)."""
    try:
        pa, da, _ = fp_a.split("|")
        pb, db_, _ = fp_b.split("|")
    except ValueError:
        return False
    if _mean_distance(pa, pb) > cfg["phash_max_distance"]:
        return False
    return _mean_distance(da, db_) <= cfg["dhash_max_distance"]


# ── Step 6: temporal overlap ──────────────────────────────────────────────

def overlaps(a_start, a_end, b_start, b_end):
    return max(a_start, b_start) < min(a_end, b_end)


def significant_overlap(a_start, a_end, b_start, b_end, cfg=CONFIG):
    overlap = min(a_end, b_end) - max(a_start, b_start)
    return overlap >= min(cfg["min_overlap_seconds"],
                          (a_end - a_start), (b_end - b_start))


# ── Step 5: cooldown ──────────────────────────────────────────────────────

def in_cooldown(last_used_iso, recent_usage_count, allow_reuse=False, now=None,
                cfg=CONFIG):
    """True if the clip must not be reused yet."""
    from datetime import datetime, timezone

    if allow_reuse or not last_used_iso:
        return False
    now = now or datetime.now(timezone.utc)
    last = datetime.fromisoformat(last_used_iso.replace("Z", "+00:00"))
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    age_days = (now - last).total_seconds() / 86400
    return age_days < cfg["clip_cooldown_days"] and \
        recent_usage_count >= cfg["max_recent_video_usage"]
