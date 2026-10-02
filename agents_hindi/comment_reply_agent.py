# agents_hindi/comment_reply_agent.py
"""
Comment Reply Agent — Hindi channel.

Thin wrapper around agents/comment_engine.py (shared by every channel);
replies in casual Hindi/Hinglish. State is stored in the shared database
under channel="hindi", so it never mixes with English.

    from agents_hindi.comment_reply_agent import process_comments_hindi
    process_comments_hindi()            # run now, ignoring the daily window

    from agents_hindi.comment_reply_agent import run_scheduled
    run_scheduled(log_fn=log)           # what scheduler_hindi.py calls (gated)

Config (env):
    COMMENT_AUTO_REPLY=false   dry run
    COMMENT_FORCE=true         bypass the 19:00-23:59 IST once-a-day window

Requires a token with youtube.force-ssl (see generate_hindi_token_v3.py).
"""

from agents import comment_engine as ce

CHANNEL = "hindi"
TOKEN_HINT = ("Run `python generate_hindi_token_v3.py` locally (scopes: youtube.upload + "
              "youtube.readonly + youtube.force-ssl) and update the HINDI_TOKEN_JSON secret.")


def _build_spec():
    from agents_hindi.upload_agent import get_youtube_client_readonly
    from agents_hindi.model_invoke_agent_hindi import safe_invoke

    return ce.ChannelSpec(
        name=CHANNEL,
        # SCOPES_READ already includes force-ssl, so ONE client both reads
        # and posts. (The old code posted with the upload-only client.)
        get_client=get_youtube_client_readonly,
        invoke=lambda prompt: safe_invoke(prompt, temperature=0.4).content,
        store=ce.DbStore(CHANNEL),
        profile=ce.PROFILES[CHANNEL],
        token_hint=TOKEN_HINT,
    )


def process_comments_hindi(max_results=50, log_fn=print):
    return ce.process(_build_spec(), max_results=max_results, log_fn=log_fn)


def run_scheduled(log_fn=print):
    return ce.run_daily(CHANNEL, lambda: process_comments_hindi(log_fn=log_fn), log_fn=log_fn)


if __name__ == "__main__":
    process_comments_hindi()
