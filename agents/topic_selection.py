"""
topic_selection.py — Brain-ranked topic choice for a channel's scheduler.

brain_ranked_topic() returns a topic the Brain preferred, or None. None means "use the existing
selection unchanged" — and it is returned for every non-happy path (feature off, engine down or
uninformative, nothing eligible, every ranked topic rejected), so a channel without a Brain
behaves exactly as it did before this module existed. When the feature is off it does no work at
all (no YouTube call, no DB read).

Existing safeguards still apply to the Brain's choice: topics posted in the last 24h are dropped
before ranking, and each ranked topic still has to pass the saturation check, in Brain order.
Every Brain-assisted decision logs one `BRAIN_LOG {...}` line with the source, execution id,
policy version and Brain versions.

Two optional additions (both fail-open; neither changes what is returned):
  * Semantic features: when BRAIN_SEMANTIC_ENABLED is true and an encoder is configured, each candidate also
    carries neighbor_ratio / neighbor_count / max_similarity_recent (see agents/semantic_features.py).
  * Decision log: every ranking (all candidates, the features sent, each Brain's score including shadow Brains,
    the fused score) is written to the persistent topic_decisions table, and the topic the pipeline actually used
    is flagged. The engine itself is discarded after each CI job, so this is the only durable record.
"""
import json
import re
import uuid
from datetime import datetime, timedelta, timezone

from agents import brain_client

DEMAND_LOOKBACK_DAYS = 30
OVERLAP_THRESHOLD = 0.6
_STOP = {"the", "and", "for", "with", "this", "that", "from", "are", "was", "new", "how", "what",
         "why", "you", "your", "its", "has", "have", "will", "can", "all", "not", "but", "out", "now"}


def _words(text):
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if (len(w) >= 3 or w == "ai") and w not in _STOP}


def _similar(a, b):
    """Overlap coefficient: a short viewer request ('quantum computing') matches a long title."""
    if not a or not b:
        return False
    return len(a & b) / min(len(a), len(b)) >= OVERLAP_THRESHOLD


def demand_features(candidates, requests, now=None):
    """candidates: [{"title", "age_days"}]; requests: topic_requests rows (dicts with topic, timestamp,
    author_channel_id). Returns {title: features}. `unique_requesters` counts DISTINCT known
    authors (rows without an author id never count as a person), `similar_requests` is the sample
    size. Candidates nobody asked for get only the freshness signal."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=DEMAND_LOOKBACK_DAYS)
    recent = []
    for r in requests or []:
        try:
            ts = datetime.fromisoformat(str(r.get("timestamp")).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if ts >= cutoff:
            recent.append((_words(r.get("topic")) or _words(r.get("comment")), r.get("author_channel_id")))

    out = {}
    for c in candidates:
        feats = {}
        if c.get("age_days") is not None:
            feats["days_since_trend"] = round(float(c["age_days"]), 3)
        cw = _words(c["title"])
        matches = [author for words, author in recent if _similar(words, cw)]
        if matches:
            feats["similar_requests"] = len(matches)
            feats["unique_requesters"] = len({a for a in matches if a})
        out[c["title"]] = feats
    return out


def _with_semantic(features, candidates, channel, compute_semantic, log):
    """Merge semantic neighbour features into the per-topic feature dicts. Never raises."""
    try:
        if compute_semantic is None:
            from agents import semantic_features
            if not semantic_features.enabled():
                return features
            compute_semantic = semantic_features.semantic_features
        extra = compute_semantic(candidates, channel) or {}
    except Exception as e:
        log(f"Brain: semantic features skipped ({type(e).__name__})")
        return features
    merged = {t: dict(f) for t, f in features.items()}
    for title, feats in extra.items():
        merged.setdefault(title, {}).update(feats)
    if extra:
        log(f"Brain: semantic features for {len(extra)}/{len(candidates)} candidates")
    return merged


def _log_decision(result, run_id, topics, features, channel, log_decision, log):
    """Persist the ranking (all candidates + every Brain's score). A logging problem never affects topic choice."""
    try:
        if log_decision is None:
            from agents.database import db
            log_decision = db.log_topic_decision
        cleaned = {t: brain_client.clean_features((features or {}).get(t)) for t in topics}
        log_decision(run_id, channel, result.to_decision_rows(topics, cleaned))
    except Exception as e:
        log(f"Brain: decision log not written ({type(e).__name__})")


def _mark_selected(run_id, topic, mark_selected, log):
    try:
        if mark_selected is None:
            from agents.database import db
            mark_selected = db.mark_topic_selected
        mark_selected(run_id, topic)
    except Exception as e:
        log(f"Brain: selection not recorded ({type(e).__name__})")


def brain_ranked_topic(channel, region_code="US", *, recent_topics=(), max_attempts=5, log=print,
                       get_candidates=None, get_requests=None, check_saturation=None,
                       mark_used=None, rank=None, compute_semantic=None, log_decision=None, mark_selected=None):
    """Returns the chosen topic str, or None to fall back. All collaborators are injectable for tests."""
    if not brain_client.is_configured(channel):
        return None

    if get_candidates is None:
        from agents.trending_agent import get_trending_candidates as get_candidates
    if get_requests is None:
        def get_requests():
            from agents.database import db
            return db.get_topic_requests(channel, limit=500)
    if check_saturation is None:
        from agents.saturation_agent import check_saturation
    if mark_used is None:
        from agents.trending_agent import mark_topic_used as mark_used
    rank = rank or brain_client.rank_topics

    candidates = [c for c in get_candidates(region_code) if c["title"].lower().strip() not in set(recent_topics)]
    if len(candidates) < 2:
        log("Brain: fewer than 2 eligible candidates — using existing topic selection")
        return None

    try:
        features = demand_features(candidates, get_requests())
    except Exception as e:                       # a signal hiccup must never block topic selection
        log(f"Brain: demand signals unavailable ({type(e).__name__}) — ranking on freshness only")
        features = {c["title"]: ({"days_since_trend": c["age_days"]} if c.get("age_days") is not None else {})
                    for c in candidates}

    features = _with_semantic(features, candidates, channel, compute_semantic, log)

    topics = [c["title"] for c in candidates]
    result = rank(topics, channel, features=features)
    log("BRAIN_LOG " + json.dumps(result.to_log_dict(), default=str))
    run_id = uuid.uuid4().hex
    _log_decision(result, run_id, topics, features, channel, log_decision, log)
    if not result.applied:
        log(f"Brain: not applied ({result.reason}) — using existing topic selection")
        return None

    for attempt, topic in enumerate(result.ordered[:max_attempts], start=1):
        saturation = check_saturation(topic)
        log(f"Saturation check: score={saturation['opportunity_score']} — {saturation['reason']}")
        if saturation["proceed"]:
            mark_used(topic)
            _mark_selected(run_id, topic, mark_selected, log)
            log(f"Brain-ranked topic chosen (rank {attempt}): {topic}")
            return topic
        log(f"Brain-ranked topic too saturated, trying next ({attempt}/{max_attempts}): {topic}")
    log("Brain: every ranked topic was saturated — using existing topic selection")
    return None
