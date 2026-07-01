"""
verify_db.py — Run this to confirm SQLite migration + Phase 4 are fully working.
"""
from agents.database import db
import os

print("=== DATABASE FILE ===")
print("Path:", db.db_path)
print("Exists:", os.path.exists(db.db_path))
print("Size:", os.path.getsize(db.db_path) if os.path.exists(db.db_path) else 0, "bytes")
print()

print("=== VIDEOS TABLE ===")
videos = db.get_all_videos()
print("Total videos:", len(videos))
print()

print("=== SNAPSHOTS ===")
total_snaps = 0
videos_with_2plus = 0
for v in videos:
    snaps = db.get_snapshots(v["video_id"])
    total_snaps += len(snaps)
    if len(snaps) >= 2:
        videos_with_2plus += 1
print("Total snapshots:", total_snaps)
print("Videos with 2+ snapshots (usable for velocity):", videos_with_2plus, "/", len(videos))
print()

print("=== AB TITLE TESTS ===")
tests = db.get_ab_tests()
print("Total AB tests:", len(tests))
print()

print("=== POSTED TOPICS ===")
recent = db.get_recent_posted(hours=24 * 365)
print("Total posted topics tracked:", len(recent))
print()

print("=== PEAK HOURS (real calculation) ===")
peak = db.get_peak_hours()
nonzero = {h: d for h, d in peak.items() if d["sample_count"] > 0}
print("Hours with data:", len(nonzero))
for h, d in sorted(nonzero.items(), key=lambda x: -x[1]["avg_velocity"])[:5]:
    print(f"  {h:02d}:00 UTC — {d['avg_velocity']} v/hr ({d['sample_count']} samples)")
print()

best = db.get_best_upload_hour()
print("Best upload hour:", best)
print()

print("=== JSON FALLBACK STILL INTACT? ===")
print("view_history.json exists:", os.path.exists("output/view_history.json"))
print("title_ab_log.json exists:", os.path.exists("output/title_ab_log.json"))
