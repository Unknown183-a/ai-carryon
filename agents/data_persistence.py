# agents/data_persistence.py
# Backs up and restores view_history.json to/from GitHub
import os
import json
import subprocess

HISTORY_FILE = "output/view_history.json"
GITHUB_RAW_URL = "https://raw.githubusercontent.com/Unknown183-a/ai-carryon/data/view_history.json"


def restore_view_history():
    """Pull latest view_history.json from GitHub data branch on startup"""
    try:
        import urllib.request
        print("Restoring view history from GitHub...")
        os.makedirs("output", exist_ok=True)
        urllib.request.urlretrieve(GITHUB_RAW_URL, HISTORY_FILE)
        data = json.load(open(HISTORY_FILE))
        total_snapshots = sum(len(v["snapshots"]) for v in data.values())
        print(f"Restored {len(data)} videos, {total_snapshots} total snapshots")
        return True
    except Exception as e:
        print(f"No existing backup found (starting fresh): {e}")
        return False


def backup_view_history():
    """Push view_history.json to GitHub data branch after each tracking run"""
    if not os.path.exists(HISTORY_FILE):
        print("No view history file to backup")
        return False

    try:
        # Configure git
        subprocess.run(["git", "config", "user.email", "railway@aicarryon.com"], 
                      capture_output=True)
        subprocess.run(["git", "config", "user.name", "AI CarryON Bot"], 
                      capture_output=True)

        # Switch to data branch, copy file, commit, push, switch back
        result = subprocess.run(
            ["git", "stash"], capture_output=True, text=True
        )

        subprocess.run(
            ["git", "checkout", "data"], capture_output=True
        )

        # Copy the history file
        import shutil
        shutil.copy(HISTORY_FILE, "view_history.json")

        subprocess.run(["git", "add", "view_history.json"], capture_output=True)

        result = subprocess.run(
            ["git", "commit", "-m", "Auto: update view history"],
            capture_output=True, text=True
        )

        if "nothing to commit" in result.stdout:
            print("View history unchanged, no backup needed")
        else:
            # Get GitHub token from env for push auth
            github_token = os.getenv("GITHUB_TOKEN", "")
            if github_token:
                remote = f"https://{github_token}@github.com/Unknown183-a/ai-carryon.git"
                subprocess.run(
                    ["git", "push", remote, "data"],
                    capture_output=True
                )
                print("View history backed up to GitHub")
            else:
                print("No GITHUB_TOKEN — skipping push (data saved locally only)")

        subprocess.run(["git", "checkout", "main"], capture_output=True)
        subprocess.run(["git", "stash", "pop"], capture_output=True)
        return True

    except Exception as e:
        print(f"Backup failed: {e}")
        # Make sure we're back on main
        subprocess.run(["git", "checkout", "main"], capture_output=True)
        return False
