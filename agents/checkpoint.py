# agents/checkpoint.py
"""
English-pipeline checkpoints, stored in the database (meta table) instead of
output/checkpoints/*.json. A file on local disk is wiped on every Cloud Run
Job / CI run; the database survives, so a run that stopped can resume.

Same function names as before, so scheduler.py keeps working.
A checkpoint older than MAX_AGE_HOURS, or already resumed MAX_RESUMES times
without finishing, is dropped so one bad topic can't block the channel.
"""
import json
import time

MAX_AGE_HOURS = 12
MAX_RESUMES = 3
INDEX_KEY = "checkpoint_index"


def _db():
    from agents.database import db
    return db


def _safe(topic):
    s = "".join(c for c in topic if c.isalnum() or c in " _-")[:50]
    return s.replace(" ", "_")


def _key(topic):
    return f"checkpoint:{_safe(topic)}"


def _index():
    try:
        return json.loads(_db().get_meta(INDEX_KEY) or "[]")
    except Exception:
        return []


def _write_index(items):
    _db().set_meta(INDEX_KEY, json.dumps(items))


def save_checkpoint(topic, stage, data):
    """Save progress at each stage"""
    checkpoint = load_checkpoint(topic) or {
        "topic": topic, "created_at": time.time(),
        "stages_completed": [], "data": {}, "resumes": 0,
    }
    checkpoint["updated_at"] = time.time()
    checkpoint["last_stage"] = stage
    if stage not in checkpoint["stages_completed"]:
        checkpoint["stages_completed"].append(stage)
    checkpoint["data"][stage] = data

    _db().set_meta(_key(topic), json.dumps(checkpoint))
    idx = _index()
    if _safe(topic) not in idx:
        _write_index(idx + [_safe(topic)])
    print(f"✅ Checkpoint saved: {stage}")
    return checkpoint


def load_checkpoint(topic):
    """Load existing checkpoint for topic"""
    try:
        raw = _db().get_meta(_key(topic))
        return json.loads(raw) if raw else None
    except Exception:
        return None


def is_stage_done(topic, stage):
    checkpoint = load_checkpoint(topic)
    if not checkpoint:
        return False
    return stage in checkpoint.get("stages_completed", [])


def get_stage_data(topic, stage):
    checkpoint = load_checkpoint(topic)
    if not checkpoint:
        return None
    return checkpoint.get("data", {}).get(stage)


def clear_checkpoint(topic):
    """Clear checkpoint after successful completion"""
    _db().set_meta(_key(topic), "")
    _write_index([t for t in _index() if t != _safe(topic)])
    print(f"🗑️ Checkpoint cleared: {topic}")


def note_resume(topic):
    """Count one more resume of this topic. Returns the new count."""
    cp = load_checkpoint(topic)
    if not cp:
        return 0
    cp["resumes"] = cp.get("resumes", 0) + 1
    _db().set_meta(_key(topic), json.dumps(cp))
    return cp["resumes"]


def list_checkpoints():
    """List all pending checkpoints (newest first). Old or over-resumed ones are dropped."""
    out = []
    for safe in _index():
        try:
            raw = _db().get_meta(f"checkpoint:{safe}")
            cp = json.loads(raw) if raw else None
        except Exception:
            cp = None
        if not cp:
            _write_index([t for t in _index() if t != safe])
            continue
        age_h = (time.time() - cp.get("updated_at", 0)) / 3600.0
        if age_h > MAX_AGE_HOURS or cp.get("resumes", 0) >= MAX_RESUMES:
            print(f"🗑️ Dropping stale checkpoint: {cp.get('topic')} (age {age_h:.1f}h, resumes {cp.get('resumes', 0)})")
            clear_checkpoint(cp["topic"])
            continue
        out.append(cp)
    return sorted(out, key=lambda x: x.get("updated_at", 0), reverse=True)


def get_resume_stage(topic):
    checkpoint = load_checkpoint(topic)
    if not checkpoint:
        return None
    return checkpoint.get("last_stage")
