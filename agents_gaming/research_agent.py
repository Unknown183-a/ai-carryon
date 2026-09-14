# agents_gaming/research_agent.py
"""Single entry point for script_agent.py — turns a raw Helix clip dict
(from clip_finder.find_best_unposted_clip) into (summary_text, structured),
same shape as agents_cricket/research_agent.get_summary_for_topic()."""


def get_summary_for_clip(clip):
    title = clip.get("title", "").strip()
    broadcaster = clip.get("broadcaster_name", "")
    game_name = clip.get("_source_game", "")  # only set for top_game clips
    views = clip.get("view_count", 0)
    created_at = clip.get("created_at", "")
    topic_type = clip.get("_topic_type", "clip")

    lines = [
        f"Clip title: {title}",
        f"Streamer: {broadcaster}",
    ]
    if game_name:
        lines.append(f"Game: {game_name}")
    lines.append(f"Views: {views:,}")
    if created_at:
        lines.append(f"Clipped: {created_at}")
    if topic_type == "streamer":
        lines.append(f"Source: followed streamer ({clip.get('_source_streamer', broadcaster)})")
    else:
        lines.append("Source: trending in this game category")

    structured = {
        "topic_type": topic_type,
        "clip_id": clip.get("id"),
        "clip_url": clip.get("url"),
        "embed_url": clip.get("embed_url"),
        "broadcaster": broadcaster,
        "game": game_name,
        "views": views,
        "title": title,
    }
    return "\n".join(lines), structured


def get_summary_for_topic(topic):
    """Alias kept for naming symmetry with the cricket/main agents — gaming
    only has one topic 'shape' (a clip dict), so this just delegates."""
    return get_summary_for_clip(topic)
