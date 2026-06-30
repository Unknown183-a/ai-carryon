# AI CarryON — Autonomous YouTube Channel Intelligence System

An autonomous AI system that researches trending topics, generates video scripts, creates YouTube Shorts, and uploads them automatically — while learning from channel performance data to improve over time. Runs **two fully independent channels** (English and Hindi) with separate learning, separate audiences, and separate scheduling.

**English Live**: https://ai-carryon-production.up.railway.app  
**Repo**: https://github.com/Unknown183-a/ai-carryon  
**Channels**: AI CarryON (English, Tech/AI niche, US audience) + Hindi AI CarryON (Hindi, Tech/AI niche, India audience)

---

## What This Does

Each channel runs its own scheduler that, without human input:

1. Checks if the current hour matches a data-driven peak engagement window (adaptive — falls back to safe defaults until enough data exists)
2. Fetches a trending topic (niche-filtered to reject off-topic content)
3. Checks topic saturation — skips topics already covered by 20+ recent videos or major authority channels
4. Runs a competitor comparison — pulls top 10 videos on the same topic, benchmarks views/engagement/title length/duration
5. Researches the topic and writes a script (length tuned per channel)
6. Generates 3 title variations using different psychological patterns (curiosity, urgency, revelation, number, question, warning, contrarian, personal), scores each, picks the winner
7. Generates SEO description and hashtags, using the A/B-tested title
8. Creates a thumbnail
9. Generates background visuals — either Pexels stock footage (free, automated) or Google Flow/Veo cinematic clips (manual upload step, premium quality)
10. Generates voiceover — Edge TTS for English, Sarvam AI native Indian voices for Hindi
11. Renders captions and final video
12. Uploads to YouTube with full SEO metadata and thumbnail
13. Records a view snapshot for ongoing intelligence

Every hour, each channel's worker tracks view/like/comment counts for its own recent videos and writes them to a shared SQLite database, partitioned by `channel` so English and Hindi learning never mix.

---

## Current Architecture

### Pipeline (per channel)

```
Adaptive Hour Check (Phase 4)
    -> Trending Topic (niche-filtered)
    -> Saturation Check (Phase 1.5)
    -> Competitor Comparison (Phase 2)
    -> Research (Groq LLaMA 3.3-70B, Gemini fallback)
    -> Script (channel-specific length/style)
    -> A/B Title Test (Phase 3) — 3 patterns scored, winner selected
    -> SEO (description, hashtags)
    -> Thumbnail
    -> Background visuals (Pexels auto OR Flow/Veo manual clips)
    -> Voiceover (Edge TTS / Sarvam AI)
    -> Captions (word-by-word SRT)
    -> Video render (ffmpeg)
    -> YouTube Upload
    -> View Snapshot -> SQLite (channel-tagged)
```

### Services (Railway)

Two separate Railway projects, each with two services:

| Project | Service | Role | Schedule |
|---|---|---|---|
| `strong-simplicity` | worker | English scheduler — generation + view tracking | Generation: every 5h, Tracking: every 1h |
| `strong-simplicity` | ai-carryon | Streamlit web dashboard (both channels) | Always on |
| `giving-beauty` | worker | Hindi scheduler — generation + view tracking | Generation: adaptive hourly check (max 3/day), Tracking: every 1h |

### Agents — English (`agents/`)

| File | Purpose |
|---|---|
| trending_agent.py | Mass-appeal tech topics only — strict tech-signal filter + blocklist for politics/sports/entertainment |
| saturation_agent.py | Phase 1.5 — opportunity scoring, skips oversaturated topics |
| comparison_agent.py | Phase 2 — competitor benchmarking via YouTube search |
| velocity_agent.py | Phase 1 — view velocity calculation, peak hour aggregation |
| ab_title_agent.py | Phase 3 — 8 title patterns, LLM scoring, winner selection |
| adaptive_scheduler.py | Phase 4 — best-hour calculation and wait/skip logic |
| database.py | Shared SQLite layer — videos, snapshots, AB tests, posted topics, spy cache |
| research_agent.py | Topic research via LLM |
| script_agent.py | Script generation, hook scoring + rewrite |
| seo_agent.py | Title (AB-tested), description, hashtags |
| flow_prompt_agent.py | Cinematic clip prompts for Google Flow/Veo — continuous 3-part story structure |
| veo_agent.py | Direct Veo API clip generation (requires billing-enabled key) |
| thumbnail_generator.py / thumbnail_agent.py | Thumbnail generation |
| image_agent.py | Pexels background images/clips |
| voice_agent.py | Edge TTS voiceover |
| caption_agent.py | Word-by-word SRT captions |
| video_agent.py | Video rendering — Pillow frames or Flow clip stitching |
| upload_agent.py | YouTube upload with SEO metadata |
| analytics_agent.py | Channel stats via YouTube API |
| view_tracker_agent.py | Hourly snapshots, writes to SQLite |
| spy_agent.py | Monitor top AI/tech channels |
| data_persistence.py | GitHub backup/restore for view_history.json (legacy, SQLite is now primary) |

### Agents — Hindi (`agents_hindi/`)

Mirrors the English structure with Hindi-specific logic — same architecture, completely separate learning data (`channel="hindi"` in SQLite):

| File | Purpose |
|---|---|
| saturation_agent.py | Indian authority channels (Technical Guruji, Trakin Tech, Tech Burner, Beebom) |
| velocity_agent.py | Hindi-only peak hour calculation |
| ab_title_agent.py | Hinglish title patterns, separate scoring/logging |
| comparison_agent.py | Indian market competitor search (regionCode=IN, relevanceLanguage=hi), Groq-generated Hinglish recommendations |
| adaptive_scheduler.py | Hindi-only best-hour logic |
| view_tracker_agent.py | Uses readonly-scoped YouTube client, writes `channel="hindi"` snapshots |
| script_agent.py | Hinglish script, 110-130 word target (~45s, under 60s Shorts limit), retry-expand if too short |
| seo_agent.py | Hinglish SEO, accepts AB-tested title override |
| voice_agent.py | Sarvam AI (Bulbul v2) — primary speaker `karun`, fallback `hitesh`, edge-tts as final fallback. Handles multi-chunk audio concatenation (Sarvam splits long text into multiple WAV segments) |
| flow_prompt_agent.py | Hinglish cinematic clip prompts, same continuous-story structure as English |
| upload_agent.py | Two YouTube clients — upload-scope and readonly-scope (needed for view tracking) |
| spy_agent.py | Groq-generated trending Hindi tech topics (LLM-based, no YouTube API dependency) |
| trending_agent.py | Fallback trending agent for Hindi region |

### Environment Variables

| Variable | Purpose | Scope |
|---|---|---|
| GROQ_API_KEY | LLM inference | Both |
| GEMINI_API_KEY | LLM fallback | Both |
| PEXELS_API_KEY | Background images | Both |
| YOUTUBE_API_KEY | YouTube Data API (search, public stats) | Both |
| YOUTUBE_TOKEN_B64 | English OAuth upload token (base64) | English |
| YOUTUBE_CLIENT_SECRETS_B64 | English OAuth client secrets (base64) | English |
| YOUTUBE_ANALYTICS_TOKEN_B64 | English analytics OAuth token (base64) | English |
| YOUTUBE_TOKEN_JSON / HINDI_TOKEN_JSON | Hindi OAuth token (raw JSON, needs `youtube.upload` + `youtube.readonly` scopes) | Hindi |
| SARVAM_API_KEY | Hindi native TTS voice | Hindi |
| GITHUB_TOKEN | Legacy view history backup, repo access | Both |
| GITHUB_REPO | Dashboard data branch reads | Both |
| APP_PASSWORD | Streamlit dashboard login | Both |
| INSTAGRAM_USERNAME / INSTAGRAM_PASSWORD | Instagram Reels cross-posting | English |

---

## Dashboard

The Streamlit app has these pages, most supporting a channel selector (English/Hindi):

- **Generate Video** — manual topic input, trending topic button, Pexels or Flow-clip video mode, auto-upload toggle (both channel tabs)
- **Peak Hours** — view velocity by hour of day, top 5 upload windows, per-video sparkline (channel selector)
- **Comparison** — competitor benchmark, views/engagement charts, recommendations (channel selector)
- **A/B Titles** — pattern win-rate chart, recent title test log, manual title tester
- **Schedule** — current best upload hour, 24h velocity chart, adaptive scheduler explanation (channel selector)

---

## Intelligence Roadmap — Actual Build History

This replaces the original planned roadmap below with what was actually shipped. Phase numbering reflects real build order, not the original June 16 plan (which had different content per phase number).

---

### Phase 0 — Data Collection
**Status: Complete**

Hourly snapshots of views, likes, and comments. Originally stored in `output/view_history.json` with GitHub backup; **migrated to SQLite** (`output/aicarryon.db`) as the primary store, with JSON kept as an untouched fallback. Fixed a critical timezone bug where mixed naive/aware timestamps silently broke velocity calculation (`_parse_ts_safe()` in `database.py`).

---

### Phase 1 — Velocity Analysis and Peak Hour Detection
**Status: Complete — both channels**

Calculates view velocity (views gained per hour) per video per snapshot interval, aggregated by hour of day. Powers the Peak Hours dashboard and feeds Phase 4. Built separately for English (`agents/velocity_agent.py`) and Hindi (`agents_hindi/velocity_agent.py`), reading the same SQLite database filtered by channel.

---

### Phase 1.5 — Saturation Engine
**Status: Complete — both channels**

Scores topics 0-100 based on recent competing video count and authority-channel coverage before research begins. English uses Fireship/MKBHD/Two Minute Papers/Computerphile/AI Explained as authority signals; Hindi uses Technical Guruji/Trakin Tech/Tech Burner/Beebom. Fails open (proceeds) if the YouTube API is unavailable rather than blocking the pipeline.

---

### Phase 2 — Comparison Engine
**Status: Complete — both channels**

Fetches top 10 competing videos per topic, computes average views/engagement/title length/duration, identifies the best upload hour among top performers, and generates concrete recommendations (lengthen/shorten title, upload at X hour, close the view gap). Wired into script and SEO generation so competitor intelligence directly shapes content. Has a dedicated dashboard page with views bar chart and engagement scatter plot.

---

### Phase 3 — A/B Title Testing
**Status: Complete — both channels**

Generates 3 title variations per video using 8 possible psychological patterns (curiosity, urgency, revelation, number, question, warning, contrarian, personal), scores each on a 10-point rubric (curiosity gap, specificity, emotional trigger, click-worthiness, length), and selects the winner for upload. Logs every test to SQLite for pattern-performance tracking over time. Dashboard shows win-rate by pattern and lets you manually test any topic.

---

### Phase 4 — Adaptive Scheduling
**Status: Complete — both channels**

Originally a fixed-interval scheduler (English: every 5h; Hindi: fixed 8am/1pm/7pm). Upgraded to fully adaptive: checks every hour whether the current UTC hour matches a learned peak-velocity window (minimum 3 samples required), and only generates+uploads when it does. Falls back to spread-out default hours until enough real data accumulates. Caps Hindi at 3 videos/day; English remains on its 5-hour cadence with peak-hour wait logic layered on top.

---

### SQLite Migration
**Status: Complete**

Replaced fragile per-feature JSON files (`view_history.json`, `title_ab_log.json`, `posted_topics.txt`, `spy_cache.json`) with a single `output/aicarryon.db` SQLite database (`agents/database.py`), shared by both channels and partitioned by a `channel` column. JSON files retained as untouched fallback per explicit requirement ("don't lose anything"). Migration script (`migrate_from_json()`) is idempotent.

---

### Voice Quality Fixes (Hindi)
**Status: Complete**

Replaced edge-tts (only 2 generic Hindi voices) with Sarvam AI's Bulbul v2 model (7 native Indian voices). Fixed two critical bugs found during testing: Sarvam splits text over a certain length into multiple WAV segments and only the first was being saved (silently cutting ~70% of every voiceover) — fixed by concatenating all returned segments. Also tuned script length from an initial 150-180 word target (which produced 60-78s audio, over the Shorts limit) down to 110-130 words (~45s), with retry-expand logic if the LLM underdelivers.

---

### Clip Prompt Engineering (Both Channels)
**Status: Complete**

Iterated through several versions of `flow_prompt_agent.py` to fix recurring issues: clips describing the scene but never delivering actual information (fixed by extracting concrete facts from the script and forcing them as on-screen text), each clip reading as a disconnected scene rather than one conversation (fixed by writing the full dialogue first, then splitting into 3 parts), and dialogue pasting the raw topic title into the script unnaturally (fixed by instructing concept extraction instead of literal title insertion). Added brand-name sanitization for Flow's policy filter (real company/product names removed from scene descriptions, kept in spoken dialogue).

---

## Deferred / Not Yet Built

These were part of the original roadmap but have not been built. Listed honestly rather than removed, since they remain reasonable next steps:

- **Phase 5 (original numbering) — Hook Analyzer / Failure Intelligence** — script hooks are scored and rewritten if weak (already in `script_agent.py`), but no systematic failure-pattern tracking exists yet
- **Narrative Intelligence** — no dedicated retention-curve scoring layer
- **Channel DNA Engine** — no persistent "brand identity" memory separate from AB title pattern stats
- **Audience Intelligence** — no YouTube Analytics demographic pull
- **Opportunity Intelligence** — no pre-trend prediction (GitHub/Reddit/Trends signal aggregation)
- **Vision Intelligence** — no automated thumbnail visual analysis
- **Monetization Intelligence** — no RPM/revenue-correlated topic scoring
- **Closing the loop on Phase 3** — AB title scores are currently LLM-predicted, not yet validated against actual YouTube view counts after 24h. This is the natural next step: pull real performance back into `ab_title_tests` and let pattern selection be driven by ground truth instead of prediction
- **Centralized "brain" service** — deliberately deferred. Both channels currently share infrastructure (same `database.py`, same agent file structure) but run independently. A formal client-server brain (single API that both schedulers call, auto-detecting channel/language) was discussed and intentionally postponed until the pipeline is fully stable and a third channel is being added — premature abstraction would have meant maintaining two systems in parallel while the logic was still changing weekly
- **Veo API automation** — `agents/veo_agent.py` exists and works, but requires a billing-enabled Gemini API key (free tier returns 429 RESOURCE_EXHAUSTED for video generation). Currently using the manual Flow UI workflow with Google AI Pro's 1,000 monthly credits instead

---

## Local Setup

```bash
git clone https://github.com/Unknown183-a/ai-carryon.git
cd ai-carryon
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run dashboard
streamlit run app.py

# Run English scheduler
python scheduler.py

# Run Hindi scheduler
python scheduler_hindi.py
```

---

## Deployment

```bash
git add .
git commit -m "description"
git push

# Force redeploy without code changes
git commit --allow-empty -m "Trigger redeploy"
git push
```

Railway auto-deploys on push to main. **Two separate Railway projects** (`strong-simplicity` for English, `giving-beauty` for Hindi) each need their own deploy — pushing to the shared repo triggers both, but verify each worker's Start Command is correct (`python scheduler.py` vs `python scheduler_hindi.py`) after any project-level changes, since a misconfigured Start Command will silently run the wrong channel's scheduler.

---

## Important Notes

**YouTube API quota**: 10,000 units/day per project. Each upload costs ~1,650 units. English's 5-hour cadence and Hindi's 3/day cap both stay safely within quota.

**SQLite persistence**: `output/aicarryon.db` is the source of truth. Verify it survives Railway restarts — if a deploy wipes `output/`, the data is gone regardless of code correctness. Check via `verify_db.py` after any redeploy that touches the worker.

**OAuth tokens**: All tokens (English upload, English analytics, Hindi combined) can expire (`invalid_grant: Token has been expired or revoked`). Re-authenticate locally and update the relevant Railway variable. Hindi's token specifically needs both `youtube.upload` and `youtube.readonly` scopes — a token with upload-only scope will silently fail view tracking with a 403 `insufficientPermissions` error.

**Sarvam AI text limits**: Long scripts get split into multiple audio chunks by the API — always concatenate `audio.audios[]` in full, never assume a single segment.

**Flow/Veo clip generation**: Free tier is limited (Google AI Pro gives ~1,000 credits/month, each 8s clip costs 20). Brand/product names in clip prompts can trigger Flow's "prominent people/brands" policy rejection — sanitize scene descriptions (not spoken dialogue) before submission.

**Railway budget**: Two projects now consume credits independently — monitor both `strong-simplicity` and `giving-beauty` balances separately.

---

*AI CarryON — Built by Amit Kumar*
