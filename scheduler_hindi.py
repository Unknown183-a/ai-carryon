# scheduler_hindi.py - Hindi Channel Scheduler
import schedule
import time
import os
import datetime

LOG_FILE = "output/scheduler_hindi_log.txt"
POSTED_FILE = "output/posted_topics_hindi.txt"

def log(message):
    os.makedirs("output", exist_ok=True)
    utc_now = datetime.datetime.utcnow()
    ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
    timestamp = ist_now.strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp} IST] {message}"
    print(entry, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")

def get_recent_topics(hours=24):
    if not os.path.exists(POSTED_FILE):
        return []
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=hours)
    recent = []
    with open(POSTED_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line or "|" not in line:
                continue
            ts_str, topic = line.split("|", 1)
            try:
                ts = datetime.datetime.fromisoformat(ts_str)
            except ValueError:
                continue
            if ts >= cutoff:
                recent.append(topic.lower().strip())
    return recent

def mark_posted(topic):
    os.makedirs("output", exist_ok=True)
    ts = datetime.datetime.utcnow().isoformat()
    with open(POSTED_FILE, "a") as f:
        f.write(f"{ts}|{topic}\n")

def generate_and_upload():
    log("=== Hindi video generation shuru ho raha hai ===")
    try:
        from agents_hindi.trending_agent import get_trending_topic
        from agents_hindi.pipeline import run_pipeline

        log("Trending topic fetch ho raha hai (India)...")
        recent = get_recent_topics(hours=24)

        for _ in range(5):
            topic = get_trending_topic(region_code="IN")
            if topic.lower().strip() not in recent:
                break

        log(f"Topic: {topic}")
        log("Hindi pipeline chal raha hai...")
        result = run_pipeline(topic, upload=True)

        mark_posted(topic)
        log(f"SUCCESS: {result.get('youtube_url', 'N/A')}")

    except Exception as e:
        import traceback
        log(f"ERROR: {str(e)}")
        log(f"TRACEBACK: {traceback.format_exc()}")

schedule.every(1).hours.do(generate_and_upload)

if __name__ == "__main__":
    log("Hindi Scheduler shuru hua!")
    log("Schedule: har 1 ghante mein")
    while True:
        schedule.run_pending()
        time.sleep(30)
