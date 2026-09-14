# agents_gaming/clip_finder.py
"""
Twitch already does the 'find the best moment' work for us — Clips are
viewer-cut highlights, and Helix returns view_count directly. So unlike
agents_cricket/moment_finder.py (which had to score raw scorecards), this
just ranks and dedups what trending_agent.get_all_topics() already fetched.
"""


def rank_clips(clips):
    """Sort candidates by view_count desc. Streamer clips get a small boost
    over top-game clips so a followed streamer's good moment beats a
    mediocre viral clip from an untracked game, all else equal."""
    def score(c):
        boost = 1.15 if c.get("_topic_type") == "streamer" else 1.0
        return c.get("view_count", 0) * boost

    return sorted(clips, key=score, reverse=True)


def find_best_unposted_clip(clips, already_posted_ids):
    """clips: raw list from trending_agent.get_all_topics().
    already_posted_ids: set of clip IDs already uploaded (from gaming_db).
    Returns the single best clip dict, or None if everything's been posted."""
    ranked = rank_clips(clips)
    for clip in ranked:
        if clip.get("id") not in already_posted_ids:
            return clip
    return None


def find_top_clips(clips, already_posted_ids, limit=5):
    """Top N unposted clips, for a dashboard picker — mirrors
    agents_cricket/moment_finder.find_top_matches()."""
    ranked = rank_clips(clips)
    out = [c for c in ranked if c.get("id") not in already_posted_ids]
    return out[:limit]
