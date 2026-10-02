# agents_cricket/comment_reply_agent.py
"""
Comment Reply Agent — Cricket channel.

Thin wrapper around agents/comment_engine.py (shared by every channel).
History goes to agents_cricket.database's cricket_comment_history table and
fan match requests to cricket_match_requests, so dedupe survives GitHub
Actions runs. Replies in casual Hinglish/English matching the commenter.

    python scheduler_cricket.py --comments     # what the 14:00 UTC cron runs

Config (env):
    COMMENT_AUTO_REPLY=false   dry run

Requires CRICKET_YOUTUBE_TOKEN_B64 to include youtube.force-ssl
(see generate_cricket_token.py) — the old upload+readonly token cannot post.
"""

from agents import comment_engine as ce

CHANNEL = "cricket"
TOKEN_HINT = ("Run `python generate_cricket_token.py` locally (scopes: youtube.upload + "
              "youtube.readonly + youtube.force-ssl) and update the CRICKET_YOUTUBE_TOKEN_B64 secret.")


def _build_spec():
    from agents_cricket.upload_agent import authenticate_youtube
    # Cricket has no router of its own; the Hindi one gives Groq + Gemini
    # fallback with a circuit breaker, and Hinglish is what this channel needs.
    from agents_hindi.model_invoke_agent_hindi import safe_invoke

    return ce.ChannelSpec(
        name=CHANNEL,
        get_client=authenticate_youtube,
        invoke=lambda prompt: safe_invoke(prompt, temperature=0.4).content,
        store=ce.CricketStore(),
        profile=ce.PROFILES[CHANNEL],
        token_hint=TOKEN_HINT,
    )


def process_comments_cricket(max_results=50, log_fn=print):
    return ce.process(_build_spec(), max_results=max_results, log_fn=log_fn)


if __name__ == "__main__":
    process_comments_cricket()
