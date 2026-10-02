# Bhakti Channel — 5th Pipeline Setup

This adds a **5th, fully independent pipeline** to ai-carryon: a Hindi
devotional (Bhakti) YouTube Shorts channel, modeled on channels like
[@bhakti_sagar_5550](https://youtube.com/@bhakti_sagar_5550) — mythological
stories (Ram, Krishna, Hanuman, Shiv-Parvati, Durga, Ganesh), mantra
meanings, and festival significance, narrated in Hindi over devotional
stock footage (temples, diyas, aarti, rivers).

It reuses the exact same architecture as the English/Hindi channels — same
SQLite database (`agents/database.py`), same video/caption/render/cleanup
machinery — partitioned by `channel="bhakti"` so its learning data never
mixes with the other channels.

## Pipeline (same 15 stages, devotional content throughout)

```
Adaptive Hour Check
    -> Devotional Topic (evergreen catalogue + live festival check)
    -> Saturation Check
    -> Competitor Comparison
    -> Devotional Research (story beats / mantra meaning)
    -> Script (devotional tone, 70-90 words Hindi)
    -> A/B Title Test (8 devotional-safe patterns: blessing, story-hook,
       revelation, devotion, question, significance, blessing-promise, personal)
    -> SEO (description, hashtags)
    -> Thumbnail (temple/deity-appropriate Pexels search)
    -> Background visuals (Pexels temples/diyas/aarti/rivers — no AI-generated
       deity depictions, by design)
    -> Voiceover (Sarvam AI, slower/calmer pace than the tech channel)
    -> Captions
    -> Video render
    -> YouTube Upload
    -> View Snapshot -> SQLite (channel="bhakti")
```

## New files added

```
agents_bhakti/
  __init__.py
  model_invoke_agent_bhakti.py   # LLM router (own Groq/Gemini budget)
  trending_agent.py              # devotional topic pool + live trend check
  saturation_agent.py            # Phase 1.5
  comparison_agent.py            # Phase 2
  research_agent.py              # story/mantra research
  script_agent.py                # devotional narration script
  seo_agent.py                   # Hindi devotional SEO
  ab_title_agent.py              # Phase 3, devotional title patterns
  thumbnail_agent.py             # temple/deity-safe thumbnail search
  image_agent.py                 # devotional-only Pexels visuals
  voice_agent.py                 # Sarvam AI, devotional pace
  upload_agent.py                # separate YouTube OAuth client
  view_tracker_agent.py
  velocity_agent.py              # Phase 1

scheduler_bhakti.py              # top-level orchestrator (5th pipeline)
generate_bhakti_token.py         # one-time OAuth token generator
```

Modified: `render.yaml` (added `worker-bhakti` service), `Procfile` (added
`worker_bhakti` process).

## What you need to do to go live

### 1. Create/choose the YouTube channel
Create the Bhakti YouTube channel (or use an existing one) under whichever
Google account you want to own it.

### 2. Get a YouTube OAuth token for that channel
In Google Cloud Console, under the project you use for YouTube API access:
- Create an OAuth client ID (Desktop app) if you don't already have one for
  this channel, download it as `client_secrets_bhakti.json` into the repo root.
- Log into the **Bhakti channel's** Google account in your browser (or an
  incognito window), then run locally:
  ```
  python generate_bhakti_token.py
  ```
  This produces `token_bhakti.json`.

### 3. Set environment variables
On whichever host runs `worker-bhakti` (Railway/Render project), set:

| Variable | Purpose | Notes |
|---|---|---|
| `BHAKTI_TOKEN_JSON` | Bhakti channel OAuth token | Paste the full contents of `token_bhakti.json` |
| `YOUTUBE_BHAKTI_CHANNEL_ID` | Bhakti channel's YouTube channel ID | Used by comparison_agent to fetch your own recent video |
| `BHAKTI_AUTHORITY_CHANNEL_IDS` | (optional) comma-separated channel IDs of big Bhakti channels | Used for saturation scoring; safe to leave empty |
| `BHAKTI_VIDEOS_PER_DAY` | (optional) daily upload cap | Defaults to 6 |

These are shared with the other channels already, no new setup needed:
`GROQ_API_KEY`, `GEMINI_API_KEY`, `PEXELS_API_KEY`, `YOUTUBE_API_KEY`,
`SARVAM_API_KEY`.

### 4. Deploy the new worker
- **Railway**: create a third service in a project (or reuse one), set its
  Start Command to `python scheduler_bhakti.py`, and run it on a cron/hourly
  schedule the same way the English/Hindi workers are set up.
- **Render**: `render.yaml` now includes a `worker-bhakti` service — push
  and it will provision automatically alongside the existing two.

### 5. Test one run manually before scheduling
```
FORCE_GENERATE=true python scheduler_bhakti.py
```
This bypasses the adaptive-hour check and runs one full generate+upload
pass immediately, so you can confirm the whole chain (topic -> script ->
voice -> video -> upload) works end-to-end before leaving it on a cron.

## Not yet done (optional follow-ups)

- **Dashboard integration**: `app.py` and `pages/*.py` currently hardcode
  the English/Hindi channel selector. Wiring "Bhakti" into the Streamlit
  dashboard (Peak Hours, Comparison, A/B Titles tabs) is a separate,
  larger change to those existing files — say the word if you want that
  done too.
- **Authority channel IDs**: `BHAKTI_AUTHORITY_CHANNEL_IDS` ships empty
  since exact channel IDs for large devotional channels should be
  confirmed before hardcoding. Look up the channel ID (via its "About"
  page or the YouTube Data API) for any channels you want to track for
  saturation scoring, and add them there.
- **Copyright note**: this pipeline generates *original* narration over
  royalty-free/Pexels stock footage — it does not use or reproduce
  copyrighted bhajans, songs, or footage from other channels. Keep it
  that way if you extend it (e.g. don't wire in real bhajan audio tracks
  without proper licensing).

## Pipeline v2 (cinematic, scene-planned)

Implements `BHAKTI_PIPELINE_IMPLEMENTATION.md`. Enabled by default; set
`BHAKTI_PIPELINE=legacy` to use the original renderer. If v2 errors at any
stage the scheduler falls back to legacy automatically — **except** when
the QA gate rejects a finished video, which is never uploaded.

```
trending -> saturation -> comparison
  -> bhakti_research_agent   structured JSON (deity, event, key_visuals...)
  -> bhakti_story_agent      Devanagari script, hook/setup/conflict/divine/resolution/ending
  -> bhakti_retention_agent  heuristic + LLM scores, regenerates once if rejected
  -> bhakti_scene_agent      5-8 scenes, 3-5 Pexels queries each, camera/mood/sfx
  -> (A/B title, SEO, thumbnail: unchanged)
  -> bhakti_voice_agent      per-scene TTS with direction, silence trim, EQ/compress/loudnorm
  -> bhakti_visual_agent     multi-query Pexels search, filter+rank, no repeats (tracked across videos)
  -> bhakti_music_agent      deity-aware pick, avoids recent tracks, per-scene music gain timeline
  -> bhakti_sfx_agent        CC0 Freesound SFX synced to scene starts (optional)
  -> bhakti_audio_agent      voice > music (sidechain duck) > SFX, limiter, -14 LUFS
  -> bhakti_caption_agent    2-3 word Devanagari phrases, emphasis, fade/scale entrance
  -> bhakti_video_agent      crop + camera move + warm grade + vignette, crossfades, 1080x1920/30fps
  -> bhakti_qa_agent         visual/voice/audio/caption/technical/story scores; swaps only failed scenes
  -> upload
```

New environment variables (all optional):

| Variable | Default | Meaning |
|---|---|---|
| `BHAKTI_PIPELINE` | `v2` | `legacy` restores the old renderer |
| `BHAKTI_QA_THRESHOLD` | `7` | Minimum score per QA category (spec suggests 8; calibrate) |
| `BHAKTI_ENFORCE_QA_GATE` | `true` | `false` = log QA failures but still upload |
| `BHAKTI_RETENTION_THRESHOLD` | `7` | Minimum average story score |
| `BHAKTI_MAX_STORY_ATTEMPTS` | `2` | Story regenerations on retention failure |
| `BHAKTI_MAX_REPAIR_ROUNDS` | `1` | Scene-level re-render rounds after QA |
| `BHAKTI_ALLOW_AI_DEITY` | `false` | Reserved for the spec's hybrid AI-visual step (not implemented; see below) |
| `BHAKTI_CRF`, `BHAKTI_PRESET` | `21`, `veryfast` | Render quality/speed |
| `BHAKTI_VOICE_REVERB` | `1` | Very light temple-room tail on narration |

Captions need a Devanagari font: the workflow and Dockerfile now install
`fonts-noto-core`. Tests: `python -m unittest tests.test_bhakti_pipeline`.
