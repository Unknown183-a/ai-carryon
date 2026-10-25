"""
semantic_features.py — per-candidate "how did similar past videos do?" features for the Brain's `semantic` type.

For each candidate topic this finds the channel's most similar PAST videos (frozen text encoder + cosine similarity)
and returns up to three numbers, exactly the ones the platform's `semantic-v1` Brain consumes:

  neighbor_ratio          similarity-weighted geometric mean of (views at 24h + 1) / (channel median + 1) over the
                          nearest neighbours that have a known 24h outcome (1.0 = same as the channel median)
  neighbor_count          how many neighbours stand behind that ratio
  max_similarity_recent   cosine similarity (clipped to [0, 1]) to the most similar video/topic posted recently

Rules:
  * Point in time. Only information available at `as_of` is used: a video's outcome counts only once its 24h
    window (plus tolerance) has closed, and "recent" means strictly before `as_of`. The candidate's own future
    can never leak in; the offline evaluation (tools/eval_semantic.py) calls the same function with as_of set to
    each video's publish time.
  * Per channel. Neighbours come from the same channel only (different languages and audiences are not mixed).
  * Fail-open and opt-in: every public entry point returns {} instead of raising when the feature is off, the
    encoder is missing or there is no usable history. Candidates without a feature simply have no evidence.
  * No text leaves this process; only the three numbers are sent to the engine.

Outcome definition (documented, versioned by OUTCOME_VERSION): views of the snapshot closest to publish + 24h,
accepted only within +/- 6h; otherwise the closed A/B-test `actual_views_24h` for that video, otherwise unknown.
"""
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import median

import numpy as np

from agents.text_encoder import load_encoder_from_env, normalize_text, text_hash

OUTCOME_VERSION = "views24h-v1"
WINDOW = timedelta(hours=24)
TOLERANCE = timedelta(hours=6)


@dataclass(frozen=True)
class SemanticConfig:
    k: int = 5                      # neighbours used
    min_similarity: float = 0.6     # cosine; a starting point to calibrate on logged data, not a tuned value
    recent_days: float = 14.0       # window for the near-repeat check
    min_history: int = 3            # videos with a known outcome needed before any ratio is produced
    history_limit: int = 1000       # most recent items considered

    @classmethod
    def from_env(cls):
        def num(name, default, cast, lo, hi):
            try:
                v = cast(os.environ.get(name, default))
                return v if lo <= v <= hi else default
            except (TypeError, ValueError):
                return default
        return cls(k=num("BRAIN_SEMANTIC_K", cls.k, int, 1, 50),
                   min_similarity=num("BRAIN_SEMANTIC_MIN_SIMILARITY", cls.min_similarity, float, 0.0, 1.0),
                   recent_days=num("BRAIN_SEMANTIC_RECENT_DAYS", cls.recent_days, float, 1.0, 365.0),
                   min_history=num("BRAIN_SEMANTIC_MIN_HISTORY", cls.min_history, int, 1, 1000),
                   history_limit=num("BRAIN_SEMANTIC_HISTORY_LIMIT", cls.history_limit, int, 10, 20000))


@dataclass(frozen=True)
class HistoryItem:
    text: str                       # normalized topic text
    published: datetime | None      # timezone-aware UTC
    views_24h: float | None         # None = outcome unknown (too recent, or never tracked)

    @property
    def outcome_available_at(self):
        """When this item's outcome became knowable (its 24h window plus tolerance has closed)."""
        return None if self.published is None else self.published + WINDOW + TOLERANCE


def enabled():
    return os.environ.get("BRAIN_SEMANTIC_ENABLED", "").strip().lower() in ("1", "true", "yes", "on")


def _parse_ts(value):
    if value is None:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def views_at_24h(published, snapshots):
    """Views of the snapshot closest to publish + 24h, only if within the tolerance; else None."""
    if published is None:
        return None
    target, best, best_gap = published + WINDOW, None, None
    for s in snapshots:
        ts = _parse_ts(s.get("timestamp"))
        views = s.get("views")
        if ts is None or views is None:
            continue
        gap = abs(ts - target)
        if gap <= TOLERANCE and (best_gap is None or gap < best_gap):
            best, best_gap = float(views), gap
    return best


def build_history(rows, as_of=None):
    """DB rows (Database.get_semantic_history_rows) -> [HistoryItem], newest first. Items published after `as_of`
    are dropped. Posted topics without a tracked video are kept for the near-repeat check (outcome unknown)."""
    as_of = as_of or datetime.now(timezone.utc)
    ab_topic, ab_views = {}, {}
    for r in rows.get("ab_tests", []):                  # ordered oldest -> newest: later rows win
        vid = r.get("video_id")
        if not vid:
            continue
        if (r.get("topic") or "").strip():
            ab_topic[vid] = r["topic"]
        if r.get("actual_views_24h") is not None:
            ab_views[vid] = float(r["actual_views_24h"])
    snaps = {}
    for s in rows.get("snapshots", []):
        snaps.setdefault(s["video_id"], []).append(s)

    items = []
    for v in rows.get("videos", []):
        published = _parse_ts(v.get("published"))
        text = normalize_text(ab_topic.get(v["video_id"]) or v.get("title") or "")
        if not text or published is None or published > as_of:
            continue
        views = views_at_24h(published, snaps.get(v["video_id"], []))
        if views is None:
            views = ab_views.get(v["video_id"])
        items.append(HistoryItem(text, published, views))
    for p in rows.get("posted", []):
        posted = _parse_ts(p.get("posted_at"))
        text = normalize_text(p.get("topic") or "")
        if text and posted is not None and posted <= as_of:
            items.append(HistoryItem(text, posted, None))
    items.sort(key=lambda i: i.published, reverse=True)
    return items


def _unit(matrix):
    m = np.asarray(matrix, dtype=np.float64)
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0                             # a zero vector stays zero: similarity 0 to everything
    return m / norms


def neighbor_features(cand_vecs, history, as_of, cfg=SemanticConfig()):
    """cand_vecs: {title: vector}; history: [(HistoryItem, vector)]. Returns {title: features} with only the
    features that have evidence. Pure function of its inputs (no clock, no I/O)."""
    if not cand_vecs or not history:
        return {}
    titles = list(cand_vecs)
    C = _unit([cand_vecs[t] for t in titles])
    H = _unit([vec for _, vec in history])
    if C.shape[1] != H.shape[1]:
        raise ValueError(f"embedding dimension mismatch: candidates {C.shape[1]} vs history {H.shape[1]}")
    S = C @ H.T

    recent_cut = as_of - timedelta(days=cfg.recent_days)
    recent = [i for i, (it, _) in enumerate(history) if it.published is not None and recent_cut <= it.published < as_of]
    known = [i for i, (it, _) in enumerate(history)
             if it.views_24h is not None and it.outcome_available_at is not None and it.outcome_available_at <= as_of]
    have_baseline = len(known) >= cfg.min_history
    if have_baseline:
        baseline = median(history[i][0].views_24h for i in known)
        log_ratio = {i: math.log((history[i][0].views_24h + 1.0) / (baseline + 1.0)) for i in known}

    out = {}
    for j, title in enumerate(titles):
        feats = {}
        if recent:
            feats["max_similarity_recent"] = round(float(min(1.0, max(0.0, S[j, recent].max()))), 4)
        if have_baseline:
            cand = sorted(((float(S[j, i]), i) for i in known if S[j, i] >= cfg.min_similarity), reverse=True)[:cfg.k]
            if cand:
                wsum = sum(s for s, _ in cand)
                mean_log = sum(s * log_ratio[i] for s, i in cand) / wsum
                feats["neighbor_ratio"] = round(math.exp(mean_log), 4)
                feats["neighbor_count"] = len(cand)
        if feats:
            out[title] = feats
    return out


def embed_texts(texts, encoder, db):
    """{normalized text: vector} for every non-empty text, using the cache for anything already embedded under
    this exact model/revision/preprocessing and encoding only the rest. Validates what the encoder returns."""
    uniq = list(dict.fromkeys(n for n in (normalize_text(t) for t in texts) if n))
    if not uniq:
        return {}
    hashes = {n: text_hash(n) for n in uniq}
    cached = db.get_cached_embeddings(list(hashes.values()), encoder.model_id, encoder.revision,
                                      encoder.preprocessing_version)
    vecs = {n: cached[hashes[n]] for n in uniq if hashes[n] in cached}
    missing = [n for n in uniq if n not in vecs]
    if missing:
        fresh = encoder.encode(missing)
        if len(fresh) != len(missing):
            raise ValueError(f"encoder returned {len(fresh)} vectors for {len(missing)} texts")
        dims = {len(v) for v in fresh} | {len(v) for v in vecs.values()}
        if len(dims) != 1 or 0 in dims:
            raise ValueError(f"inconsistent embedding dimensions: {sorted(dims)}")
        for v in fresh:
            if not all(math.isfinite(x) for x in v):
                raise ValueError("encoder returned a non-finite value")
        db.save_embeddings([(hashes[n], v) for n, v in zip(missing, fresh)], encoder.model_id, encoder.revision,
                           encoder.preprocessing_version)
        vecs.update(zip(missing, fresh))
    return vecs


_ENCODER = {}


def default_encoder():
    """Process-wide encoder from the environment (loaded once; None when the feature isn't configured)."""
    if "enc" not in _ENCODER:
        _ENCODER["enc"] = load_encoder_from_env()
    return _ENCODER["enc"]


def semantic_features(candidates, channel, *, db=None, encoder=None, now=None, cfg=None, log=print):
    """candidates: [{"title": str, ...}] (the shape topic_selection uses). Returns {title: features}; {} when the
    feature is off, there is no encoder or history, or anything goes wrong. Never raises."""
    try:
        encoder = encoder or default_encoder()
        if encoder is None:
            return {}
        if db is None:
            from agents.database import db as _db
            db = _db
        cfg = cfg or SemanticConfig.from_env()
        now = now or datetime.now(timezone.utc)
        history = build_history(db.get_semantic_history_rows(channel), as_of=now)[:cfg.history_limit]
        if not history:
            return {}
        titles = [c["title"] for c in candidates if c.get("title")]
        vecs = embed_texts([h.text for h in history] + titles, encoder, db)
        hist_vecs = [(h, vecs[h.text]) for h in history if h.text in vecs]
        cand_vecs = {t: vecs[normalize_text(t)] for t in titles if normalize_text(t) in vecs}
        return neighbor_features(cand_vecs, hist_vecs, now, cfg)
    except Exception as e:
        log(f"Semantic: features unavailable ({type(e).__name__}): {e}")
        return {}
