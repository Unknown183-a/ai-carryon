"""
debug_peak.py — figure out why get_peak_hours() returns 0 hours with data
"""
from agents.database import db
from datetime import datetime as dt

videos = db.get_all_videos()
checked = 0
errors = []

for v in videos:
    snaps = db.get_snapshots(v["video_id"])
    if len(snaps) < 2:
        continue
    checked += 1
    for i in range(1, len(snaps)):
        prev = snaps[i-1]
        curr = snaps[i]
        try:
            t1 = dt.fromisoformat(prev["timestamp"].replace("Z", "+00:00"))
            t2 = dt.fromisoformat(curr["timestamp"].replace("Z", "+00:00"))
            hours_elapsed = (t2 - t1).total_seconds() / 3600
            print(f"video={v['video_id'][:8]} prev_ts={prev['timestamp']!r} curr_ts={curr['timestamp']!r} hours_elapsed={hours_elapsed}")
        except Exception as e:
            errors.append((v["video_id"], prev["timestamp"], curr["timestamp"], str(e)))

print()
print("Videos checked (2+ snapshots):", checked)
print("Errors:", len(errors))
for e in errors[:10]:
    print(" ", e)
