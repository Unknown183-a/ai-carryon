

def get_news_summary(item):
    """item: one dict from news_agent.get_breaking_cricket_news(), tagged
    topic_type='news' by get_all_topics(). No scorecard data exists for
    news items — this just formats the headline for script generation."""
    lines = [
        f"Headline: {item.get('title', '')}",
        f"Source: {item.get('source', '')}",
        f"Published: {item.get('published', '')}",
    ]
    structured = {
        "match_id": None,
        "venue": None,
        "teams": [],
        "standout_player": None,
        "standout_type": None,
        "headline": item.get("title", ""),
        "link": item.get("link", ""),
    }
    return "\n".join(lines), structured


def get_upcoming_preview(match):
    """match: one dict from trending_agent.get_upcoming_matches(), tagged
    topic_type='upcoming'. No scorecard exists yet since the match hasn't
    started — this uses only the preview data already on hand (teams,
    venue, date) rather than making another CricAPI call."""
    lines = [
        f"Match: {match.get('name', '')}",
        f"Status: {match.get('status', 'Upcoming')}",
        f"Venue: {match.get('venue', '')}",
        f"Date: {match.get('date', '')}",
    ]
    structured = {
        "match_id": match.get("id"),
        "venue": match.get("venue", ""),
        "teams": match.get("teams", []),
        "standout_player": None,
        "standout_type": None,
    }
    return "\n".join(lines), structured


def get_summary_for_topic(topic):
    """Single entry point for script_agent.py — branches on topic_type
    (set by trending_agent.get_all_topics()) so callers don't need to know
    which source function produced the topic."""
    topic_type = topic.get("topic_type")
    if topic_type == "news":
        return get_news_summary(topic)
    if topic_type == "upcoming":
        return get_upcoming_preview(topic)
    return get_match_summary(topic)  # "live" or "finished"
