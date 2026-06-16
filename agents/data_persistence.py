# agents/data_persistence.py
import os
import json
import base64
import urllib.request
import urllib.error

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
REPO = "Unknown183-a/ai-carryon"
BRANCH = "data"
FILE_PATH = "view_history.json"
HISTORY_FILE = "output/view_history.json"
API_BASE = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
RAW_URL = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{FILE_PATH}"


def restore_view_history():
    """Pull latest view_history.json from GitHub data branch on startup"""
    try:
        print("Restoring view history from GitHub...")
        os.makedirs("output", exist_ok=True)
        urllib.request.urlretrieve(f"{RAW_URL}?nocache={os.urandom(4).hex()}", HISTORY_FILE)
        data = json.load(open(HISTORY_FILE))
        total = sum(len(v["snapshots"]) for v in data.values())
        print(f"Restored {len(data)} videos, {total} total snapshots")
        return True
    except Exception as e:
        print(f"No existing backup found (starting fresh): {e}")
        return False


def backup_view_history():
    """Push view_history.json to GitHub data branch via API"""
    if not GITHUB_TOKEN:
        print("No GITHUB_TOKEN — skipping backup")
        return False

    if not os.path.exists(HISTORY_FILE):
        print("No view history file to backup")
        return False

    try:
        # Read current file content
        with open(HISTORY_FILE, "r") as f:
            content = f.read()

        # Encode to base64
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        # Get current file SHA (needed for update)
        sha = None
        try:
            req = urllib.request.Request(
                f"{API_BASE}?ref={BRANCH}",
                headers={
                    "Authorization": f"Bearer {GITHUB_TOKEN}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                }
            )
            with urllib.request.urlopen(req) as resp:
                file_info = json.loads(resp.read())
                sha = file_info.get("sha")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                sha = None  # File doesn't exist yet, will create
            else:
                raise

        # Prepare payload
        payload = {
            "message": "Auto: update view history",
            "content": content_b64,
            "branch": BRANCH
        }
        if sha:
            payload["sha"] = sha

        # Push to GitHub
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            API_BASE,
            data=data,
            method="PUT",
            headers={
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
        )
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            print(f"View history backed up to GitHub ✅ ({len(content)} bytes)")
            return True

    except Exception as e:
        print(f"Backup failed: {e}")
        return False
