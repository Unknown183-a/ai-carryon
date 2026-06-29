# agents/checkpoint.py
import os
import json
import time

CHECKPOINT_DIR = "output/checkpoints"

def get_checkpoint_path(topic):
    """Get checkpoint file path for a topic"""
    safe_topic = "".join(c for c in topic if c.isalnum() or c in " _-")[:50]
    safe_topic = safe_topic.replace(" ", "_")
    return os.path.join(CHECKPOINT_DIR, f"{safe_topic}.json")

def save_checkpoint(topic, stage, data):
    """Save progress at each stage"""
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    path = get_checkpoint_path(topic)

    # Load existing checkpoint
    checkpoint = load_checkpoint(topic) or {
        "topic": topic,
        "created_at": time.time(),
        "stages_completed": [],
        "data": {}
    }

    # Update
    checkpoint["updated_at"] = time.time()
    checkpoint["last_stage"] = stage
    if stage not in checkpoint["stages_completed"]:
        checkpoint["stages_completed"].append(stage)
    checkpoint["data"][stage] = data

    with open(path, "w") as f:
        json.dump(checkpoint, f, indent=2)

    print(f"✅ Checkpoint saved: {stage}")
    return checkpoint

def load_checkpoint(topic):
    """Load existing checkpoint for topic"""
    path = get_checkpoint_path(topic)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None

def is_stage_done(topic, stage):
    """Check if a stage is already completed"""
    checkpoint = load_checkpoint(topic)
    if not checkpoint:
        return False
    return stage in checkpoint.get("stages_completed", [])

def get_stage_data(topic, stage):
    """Get saved data from a completed stage"""
    checkpoint = load_checkpoint(topic)
    if not checkpoint:
        return None
    return checkpoint.get("data", {}).get(stage)

def clear_checkpoint(topic):
    """Clear checkpoint after successful completion"""
    path = get_checkpoint_path(topic)
    if os.path.exists(path):
        os.remove(path)
        print(f"🗑️ Checkpoint cleared: {topic}")

def list_checkpoints():
    """List all pending checkpoints"""
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    checkpoints = []
    for f in os.listdir(CHECKPOINT_DIR):
        if f.endswith(".json"):
            with open(os.path.join(CHECKPOINT_DIR, f)) as fp:
                try:
                    cp = json.load(fp)
                    checkpoints.append(cp)
                except:
                    pass
    return sorted(checkpoints, key=lambda x: x.get("updated_at", 0), reverse=True)

def get_resume_stage(topic):
    """Get the next stage to run from checkpoint"""
    checkpoint = load_checkpoint(topic)
    if not checkpoint:
        return None
    return checkpoint.get("last_stage")
