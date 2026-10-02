# agents_bhakti/comment_reply_agent.py
"""
Comment Reply Agent — Bhakti (devotional) channel.

Thin wrapper around agents/comment_engine.py (shared by every channel).
Devotional voice: respectful, short, mirrors greetings ("Jai Shree Ram" ->
"Jai Shree Ram 🙏"), never jokes about deities, never promises miracles, and
never answers religious arguments (category "Religious Debate" is skipped,
like Spam/Offensive). State is stored in the shared database under
channel="bhakti".

    from agents_bhakti.comment_reply_agent import process_comments_bhakti
    process_comments_bhakti()           # run now, ignoring the daily window

    from agents_bhakti.comment_reply_agent import run_scheduled
    run_scheduled(log_fn=log)           # what scheduler_bhakti.py calls (gated)

Config (env):
    COMMENT_AUTO_REPLY=false   dry run
    COMMENT_FORCE=true         bypass the 19:00-23:59 IST once-a-day window

Requires BHAKTI_TOKEN_JSON to include youtube.force-ssl
(regenerate with generate_bhakti_token.py).
"""

from agents import comment_engine as ce

CHANNEL = "bhakti"
TOKEN_HINT = ("Run `python generate_bhakti_token.py` locally (scopes: youtube.upload + "
              "youtube.readonly + youtube.force-ssl) and update the BHAKTI_TOKEN_JSON secret.")


def _build_spec():
    from agents_bhakti.upload_agent import get_youtube_client_readonly
    from agents_bhakti.model_invoke_agent_bhakti import safe_invoke

    return ce.ChannelSpec(
        name=CHANNEL,
        # SCOPES_READ includes force-ssl, so one client both reads and posts.
        get_client=get_youtube_client_readonly,
        invoke=lambda prompt: safe_invoke(prompt, temperature=0.4).content,
        store=ce.DbStore(CHANNEL),
        profile=ce.PROFILES[CHANNEL],
        token_hint=TOKEN_HINT,
    )


def process_comments_bhakti(max_results=50, log_fn=print):
    return ce.process(_build_spec(), max_results=max_results, log_fn=log_fn)


def run_scheduled(log_fn=print):
    return ce.run_daily(CHANNEL, lambda: process_comments_bhakti(log_fn=log_fn), log_fn=log_fn)


if __name__ == "__main__":
    process_comments_bhakti()
