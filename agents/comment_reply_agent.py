# agents/comment_reply_agent.py
"""
Comment Reply Agent — English channel.

Thin wrapper around agents/comment_engine.py (shared by every channel).
All the logic (fetch, classify+reply in one LLM call, sanitise, publish,
retry/persist, daily window) lives in the engine.

    from agents.comment_reply_agent import process_comments
    process_comments()                  # run now, ignoring the daily window

    from agents.comment_reply_agent import run_scheduled
    run_scheduled(log_fn=log)           # what scheduler.py calls (gated)

Config (env):
    COMMENT_AUTO_REPLY=false   dry run: draft + store replies, don't publish
    COMMENT_FORCE=true         bypass the 19:00-23:59 IST once-a-day window

Requires an OAuth token with youtube.force-ssl (see generate_english_token.py).
"""

from agents import comment_engine as ce

CHANNEL = "english"
TOKEN_HINT = ("Run `python generate_english_token.py` locally (scopes: youtube.upload + "
              "youtube.force-ssl) and update the YOUTUBE_TOKEN_B64 secret.")


def _build_spec():
    from agents.upload_agent import authenticate_youtube_headless
    from agents.model_invoke_agent_english import safe_invoke

    return ce.ChannelSpec(
        name=CHANNEL,
        get_client=authenticate_youtube_headless,
        invoke=lambda prompt: safe_invoke(prompt, temperature=0.4).content,
        store=ce.DbStore(CHANNEL),
        profile=ce.PROFILES[CHANNEL],
        token_hint=TOKEN_HINT,
    )


def process_comments(max_results=50, log_fn=print):
    return ce.process(_build_spec(), max_results=max_results, log_fn=log_fn)


def run_scheduled(log_fn=print):
    return ce.run_daily(CHANNEL, lambda: process_comments(log_fn=log_fn), log_fn=log_fn)


if __name__ == "__main__":
    process_comments()
