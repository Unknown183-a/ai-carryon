# agents_cricket/asset_registry.py
"""
Cricket V2 — Phase 1 (steps 1 and 4): persistent asset registry + usage tracking.

Tables (new — the existing cricket_videos table is left untouched):
  cricket_assets        every clip we have seen (source, hashes, quality, usage)
  cricket_asset_usage   which video used which clip, and which seconds of it

Works on Postgres (DATABASE_URL) and SQLite exactly like CricketDatabase, by
borrowing its connection. Every public function is fail-safe: if the registry
is unavailable the callers fall back to the old behaviour instead of crashing
the pipeline.
"""
import os
from datetime import datetime, timezone, timedelta

from agents_cricket import duplicate_detector as dd
from agents_cricket.database import db as _cdb, USE_POSTGRES

_ready = False


def _now():
    return datetime.now(timezone.utc).isoformat()


def ensure_tables():
    global _ready
    if _ready or _cdb is None:
        return _ready
    id_col = "id SERIAL PRIMARY KEY" if USE_POSTGRES else "id INTEGER PRIMARY KEY AUTOINCREMENT"
    with _cdb._conn() as conn:
        conn.executescript(f"""
            CREATE TABLE IF NOT EXISTS cricket_assets (
                {id_col},
                source           TEXT,
                source_url       TEXT,
                local_path       TEXT,
                source_video_id  TEXT,
                start_time       REAL,
                end_time         REAL,
                player           TEXT,
                team             TEXT,
                opponent         TEXT,
                match_name       TEXT,
                tournament       TEXT,
                category         TEXT,
                subcategory      TEXT,
                duration         REAL,
                width            INTEGER,
                height           INTEGER,
                fps              REAL,
                file_hash        TEXT,
                perceptual_hash  TEXT,
                visual_embedding TEXT,
                quality_score    REAL,
                relevance_score  REAL,
                usage_count      INTEGER DEFAULT 0,
                last_used_at     TEXT,
                created_at       TEXT,
                updated_at       TEXT
            );
            CREATE TABLE IF NOT EXISTS cricket_asset_usage (
                {id_col},
                asset_id    INTEGER NOT NULL,
                video_id    TEXT,
                start_time  REAL,
                end_time    REAL,
                used_at     TEXT NOT NULL,
                FOREIGN KEY (asset_id) REFERENCES cricket_assets(id)
            );
            CREATE INDEX IF NOT EXISTS idx_cricket_assets_source
                ON cricket_assets(source, source_video_id);
            CREATE INDEX IF NOT EXISTS idx_cricket_assets_file_hash
                ON cricket_assets(file_hash);
            CREATE INDEX IF NOT EXISTS idx_cricket_usage_asset
                ON cricket_asset_usage(asset_id);
        """)
    _ready = True
    return True


# ── Steps 5 + 6: cheap pre-download check (metadata / cooldown / overlap) ──

def check_source_segment(source, source_video_id, start, end):
    """Returns (ok, reason). Rejects a source segment that is still on
    cooldown or temporally overlaps an earlier use of the same source video.
    Runs BEFORE downloading, so rejected candidates cost no bandwidth."""
    try:
        if not ensure_tables():
            return True, "registry unavailable"
        cutoff = (datetime.now(timezone.utc)
                  - timedelta(days=dd.CONFIG["clip_cooldown_days"])).isoformat()
        with _cdb._conn() as conn:
            rows = conn.execute("""
                SELECT u.start_time, u.end_time, u.used_at
                FROM cricket_asset_usage u
                JOIN cricket_assets a ON a.id = u.asset_id
                WHERE a.source = ? AND a.source_video_id = ?
            """, (source, str(source_video_id))).fetchall()
        recent = [r for r in rows if r["used_at"] >= cutoff]
        for r in recent:
            if dd.significant_overlap(start, end, r["start_time"], r["end_time"]):
                return False, "temporal overlap with a recently used segment"
        if len(recent) >= dd.CONFIG["max_recent_video_usage"]:
            return False, "source video on cooldown"
        return True, "ok"
    except Exception as e:
        print(f"[registry] source check skipped: {e}")
        return True, f"check error: {e}"


# ── Steps 2 + 3: post-download hash checks ────────────────────────────────

def check_file(file_path):
    """Hashes the downloaded file and compares against what was used recently.
    Returns dict: ok, reason, file_hash, perceptual_hash."""
    result = {"ok": True, "reason": "ok", "file_hash": None, "perceptual_hash": None}
    try:
        result["file_hash"] = dd.calculate_sha256(file_path)
    except Exception as e:
        result["reason"] = f"sha256 failed: {e}"
        return result
    try:
        result["perceptual_hash"] = dd.perceptual_fingerprint(file_path)
    except Exception as e:
        print(f"[registry] perceptual hash failed ({e}) — continuing with SHA-256 only")

    try:
        if not ensure_tables():
            return result
        cutoff = (datetime.now(timezone.utc)
                  - timedelta(days=dd.CONFIG["clip_cooldown_days"])).isoformat()
        with _cdb._conn() as conn:
            rows = conn.execute("""
                SELECT id, file_hash, perceptual_hash, last_used_at, usage_count
                FROM cricket_assets
                WHERE usage_count > 0 AND last_used_at >= ?
                ORDER BY last_used_at DESC LIMIT 500
            """, (cutoff,)).fetchall()
        for r in rows:
            if r["file_hash"] and r["file_hash"] == result["file_hash"]:
                return {**result, "ok": False, "reason": f"exact duplicate of asset {r['id']}"}
            if (result["perceptual_hash"] and r["perceptual_hash"]
                    and dd.is_near_duplicate(result["perceptual_hash"], r["perceptual_hash"])):
                return {**result, "ok": False, "reason": f"near duplicate of asset {r['id']}"}
    except Exception as e:
        print(f"[registry] file check skipped: {e}")
    return result


# ── Step 1: registry ──────────────────────────────────────────────────────

def register_asset(source, source_video_id, source_url, local_path, start, end,
                   file_hash=None, perceptual_hash=None, duration=None,
                   width=None, height=None, fps=None, relevance_score=None,
                   quality_score=None, category=None, team=None, match_name=None):
    """Inserts the asset (or returns the existing row's id). None on failure."""
    try:
        if not ensure_tables():
            return None
        now = _now()
        with _cdb._conn() as conn:
            row = conn.execute("""
                SELECT id FROM cricket_assets
                WHERE source = ? AND source_video_id = ? AND
                      (file_hash = ? OR file_hash IS NULL)
                ORDER BY id LIMIT 1
            """, (source, str(source_video_id), file_hash)).fetchone()
            if row:
                conn.execute("""
                    UPDATE cricket_assets SET updated_at = ?,
                        file_hash = COALESCE(file_hash, ?),
                        perceptual_hash = COALESCE(perceptual_hash, ?)
                    WHERE id = ?
                """, (now, file_hash, perceptual_hash, row["id"]))
                return row["id"]
            conn.execute("""
                INSERT INTO cricket_assets
                (source, source_url, local_path, source_video_id, start_time, end_time,
                 team, match_name, category, duration, width, height, fps,
                 file_hash, perceptual_hash, quality_score, relevance_score,
                 usage_count, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?)
            """, (source, source_url, local_path, str(source_video_id), start, end,
                  team, match_name, category, duration, width, height, fps,
                  file_hash, perceptual_hash, quality_score, relevance_score, now, now))
            row = conn.execute("""
                SELECT id FROM cricket_assets
                WHERE source = ? AND source_video_id = ? ORDER BY id DESC LIMIT 1
            """, (source, str(source_video_id))).fetchone()
            return row["id"] if row else None
    except Exception as e:
        print(f"[registry] register failed: {e}")
        return None


# ── Step 4: usage tracking ────────────────────────────────────────────────

def record_usage(video_id, used):
    """used: list of {"asset_id", "start", "end"}. Call AFTER a successful upload
    so clips from a failed run aren't put on cooldown."""
    try:
        if not used or not ensure_tables():
            return
        now = _now()
        with _cdb._conn() as conn:
            for u in used:
                if not u.get("asset_id"):
                    continue
                conn.execute("""
                    INSERT INTO cricket_asset_usage (asset_id, video_id, start_time, end_time, used_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (u["asset_id"], video_id, u["start"], u["end"], now))
                conn.execute("""
                    UPDATE cricket_assets
                    SET usage_count = usage_count + 1, last_used_at = ?, updated_at = ?
                    WHERE id = ?
                """, (now, now, u["asset_id"]))
    except Exception as e:
        print(f"[registry] record_usage failed: {e}")
