"""
eval_semantic.py — offline, point-in-time check of the semantic neighbour signal against what actually happened.

For every video with a known 24h outcome, in time order, the neighbour features are rebuilt exactly as they would
have been at its publish time (only earlier videos, only outcomes whose 24h window had closed) and compared with
the real outcome. Nothing from the target's own future is used, and a video is never its own neighbour.

Target:      actual = log((views_24h + 1) / (channel median so far + 1))     (0 = exactly the median)
Baseline:    predict 0 for everything ("this video will do about the median")
Semantic:    predict log(neighbor_ratio) for videos that have neighbour evidence

Reported (on the videos that have neighbour evidence): sample size, MAE of both, mean improvement with a bootstrap
95% interval, and Spearman rank correlation between prediction and outcome. The promotion gate is deliberately
strict: at least MIN_EVAL samples, the interval's lower bound above 0 AND a positive rank correlation. A small
sample or one lucky split never passes. The script only REPORTS; promoting the Brain (shadow -> supporting) is a
manual decision.

Usage (needs DATABASE_URL for the pipeline database, and the encoder env from agents/text_encoder.py):
    python -m tools.eval_semantic --channel english [--json out.json] [--save]
"""
import argparse
import json
import math
import sys
from datetime import datetime, timezone
from statistics import median

import numpy as np

from agents import semantic_features as sf
from agents.text_encoder import normalize_text

MIN_EVAL = 30
BOOTSTRAP = 2000
SEED = 7


def _ranks(x):
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), dtype=float)
    i = 0
    xs = np.asarray(x)[order]
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[j + 1] == xs[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0           # ties share their average rank
        i = j + 1
    return ranks


def spearman(a, b):
    if len(a) < 3:
        return None
    ra, rb = _ranks(a), _ranks(b)
    if ra.std() == 0 or rb.std() == 0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def bootstrap_mean_ci(values, n=BOOTSTRAP, seed=SEED):
    v = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = rng.choice(v, size=(n, len(v)), replace=True).mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def evaluate_rows(history, vectors, cfg=sf.SemanticConfig()):
    """One row per target video, in time order: {"text", "actual", "ratio", "count"}. Each row is computed from
    information available at that video's publish time only."""
    items = [h for h in history if h.text in vectors and h.published is not None]
    items.sort(key=lambda h: h.published)
    rows = []
    for idx, target in enumerate(items):
        if target.views_24h is None:
            continue
        as_of = target.published
        past = [h for h in items[:idx] if h.published < as_of]           # strictly earlier: never itself
        known = [h.views_24h for h in past
                 if h.views_24h is not None and h.outcome_available_at is not None and h.outcome_available_at <= as_of]
        if len(known) < cfg.min_history:
            continue
        baseline = median(known)
        actual = math.log((target.views_24h + 1.0) / (baseline + 1.0))
        feats = sf.neighbor_features({target.text: vectors[target.text]},
                                     [(h, vectors[h.text]) for h in past], as_of, cfg).get(target.text, {})
        rows.append({"text": target.text, "actual": actual, "ratio": feats.get("neighbor_ratio"),
                     "count": feats.get("neighbor_count", 0)})
    return rows


def evaluate(history, vectors, cfg=sf.SemanticConfig(), min_eval=MIN_EVAL):
    """history: [HistoryItem] (any order); vectors: {normalized text: vector}. Returns a report dict."""
    rows = evaluate_rows(history, vectors, cfg)
    scored = [r for r in rows if r["ratio"] is not None]
    report = {"outcome": sf.OUTCOME_VERSION, "videos_with_outcome": len(rows), "videos_with_neighbours": len(scored),
              "min_eval": min_eval, "gate_passed": False}
    if not scored:
        report["note"] = "no video had neighbour evidence at its publish time"
        return report
    actual = np.array([r["actual"] for r in scored])
    pred = np.array([math.log(r["ratio"]) for r in scored])
    gain = np.abs(actual) - np.abs(actual - pred)                          # >0 when semantic beats "predict the median"
    rho = spearman(pred, actual)
    lo, hi = bootstrap_mean_ci(gain) if len(gain) >= 2 else (float("nan"), float("nan"))
    report.update(mae_baseline=float(np.abs(actual).mean()), mae_semantic=float(np.abs(actual - pred).mean()),
                  mean_gain=float(gain.mean()), gain_ci95=[lo, hi], spearman=rho)
    report["gate_passed"] = bool(len(scored) >= min_eval and lo > 0 and rho is not None and rho > 0)
    return report


def load(channel, db, encoder, now=None, cfg=None):
    cfg = cfg or sf.SemanticConfig.from_env()
    now = now or datetime.now(timezone.utc)
    history = sf.build_history(db.get_semantic_history_rows(channel), as_of=now)
    vecs = sf.embed_texts([h.text for h in history], encoder, db)
    return history, vecs, cfg


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--channel", required=True)
    ap.add_argument("--json", help="also write the report to this file")
    ap.add_argument("--save", action="store_true",
                    help="also store the report in the database (semantic_eval_reports) for the dashboard")
    args = ap.parse_args(argv)
    encoder = sf.default_encoder()
    if encoder is None:
        print("No encoder configured (BRAIN_TEXT_MODEL_NAME / BRAIN_TEXT_MODEL_REVISION).", file=sys.stderr)
        return 2
    from agents.database import db
    history, vecs, cfg = load(args.channel, db, encoder)
    report = evaluate(history, vecs, cfg)
    report["channel"] = args.channel
    report["model_id"], report["revision"] = encoder.model_id, encoder.revision
    print(json.dumps(report, indent=2))
    if args.save:
        db.save_semantic_eval(args.channel, report)
        print(f"Saved to semantic_eval_reports ({args.channel}).")
    if args.json:
        with open(args.json, "w") as f:
            json.dump(report, f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
