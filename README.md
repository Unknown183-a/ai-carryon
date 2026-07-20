# AI CarryON — Autonomous YouTube Channel Intelligence System

An autonomous AI system that researches trending topics, generates video scripts, creates YouTube Shorts, and uploads them automatically — while learning from channel performance data to improve over time. Runs **three fully independent channels** (English, Hindi, and Cricket) with separate learning, separate audiences, and separate scheduling.

**Live Dashboard**: https://ai-carryon-dashboard-344405691065.us-central1.run.app
**Repo**: https://github.com/Unknown183-a/ai-carryon
**Channels**: AI CarryON (English, Tech/AI niche, US audience) + Hindi AI CarryON (Hindi, Tech/AI niche, India audience) + Cricket AI CarryON (English, Indian cricket — IPL, Men's/Women's national team, domestic)

---

## What This Does

Each channel runs its own scheduled job that, without human input:

1. Checks if the current hour matches a data-driven peak engagement window (adaptive — falls back to safe defaults until enough data exists)
2. Fetches a trending topic (niche-filtered to reject off-topic content; Cricket filters to Indian cricket specifically)
3. Checks topic saturation — skips topics already covered by 20+ recent videos or major authority channels
4. Runs a competitor comparison — pulls top 10 videos on the same topic, benchmarks views/engagement/title length/duration
5. Researches the topic and writes a script (length tuned per channel)
6. Generates 3 title variations using different psychological patterns (curiosity, urgency, revelation, number, question, warning, contrarian, personal), scores each, picks the winner
7. Generates SEO description and hashtags, using the A/B-tested title
8. Creates a thumbnail
9. Generates background visuals — **generative (Imagen 3)** by default on unattended/scheduled runs, with automatic fallback to real-photo/stock images if generation fails; either mode also selectable manually from the dashboard
10. Generates voiceover — Sarvam AI Bulbul v3 (`shubh` voice) for Hindi and Cricket, Edge TTS for English
11. Renders captions and final video
12. Uploads to YouTube with full SEO metadata and thumbnail
13. Records a view snapshot for ongoing intelligence

Each channel's worker tracks view/like/comment counts for its own recent videos on a schedule and writes them to Firestore, partitioned by channel so English, Hindi, and Cricket learning never mix.

---

## Current Architecture

### Pipeline (per channel)

```
Adaptive Hour Check (Phase 4)
    -> Trending Topic (niche-filtered; Cricket = Indian cricket only)
    -> Saturation Check (Phase 1.5)
    -> Competitor Comparison (Phase 2)
    -> Research (Groq LLaMA 3.3-70B, Gemini fallback)
    -> Script (channel-specific length/style)
    -> A/B Title Test (Phase 3) — 3 patterns scored, winner selected
    -> SEO (description, hashtags)
    -> Thumbnail
    -> Background visuals (Imagen 3 generative, auto-fallback to real-photo/stock)
    -> Voiceover (Sarvam AI Bulbul v3 "shubh" / Edge TTS)
    -> Captions (word-by-word SRT)
    -> Video render (ffmpeg)
    -> YouTube Upload
    -> View Snapshot -> Firestore (channel-tagged)
```

### Services (Google Cloud)

Migrated off Railway/Render + Supabase onto Firebase (Blaze plan) + Cloud Run, after Railway's free-tier limits were exhausted.

| Component            | Platform                        | Role                                                    |
| --------------------- | -------------------------------- | -------------------------------------------------------- |
| Dashboard              | Cloud Run                        | Streamlit web dashboard (all three channels)              |
| English worker         | Cloud Run + Cloud Scheduler       | Generation + view tracking, triggered on schedule          |
| Hindi worker           | Cloud Run + Cloud Scheduler       | Generation + view tracking, adaptive hourly check          |
| Cricket worker         | Cloud Run + Cloud Scheduler       | Generation + view tracking, capped at 2-3 videos/day       |
| Database               | Firestore                        | Videos, snapshots, AB tests, posted topics/matches — replaces both the old SQLite file and Cricket's separate Supabase Postgres instance |
| Secrets                | Secret Manager                   | API keys and OAuth tokens (previously plain Railway env vars) |

### Agents — English (`agents/`)

| File                                          | Purpose                                                                                                |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| trending_agent.py                              | Mass-appeal tech topics only — strict tech-signal filter + blocklist for politics/sports/entertainment  |
| saturation_agent.py                            | Phase 1.5 — opportunity scoring, skips oversaturated topics                                              |
| comparison_agent.py                            | Phase 2 — competitor benchmarking via YouTube search                                                     |
| velocity_agent.py                              | Phase 1 — view velocity calculation, peak hour aggregation                                                |
| ab_title_agent.py                              | Phase 3 — 8 title patterns, LLM scoring, winner selection                                                 |
| adaptive_scheduler.py                          | Phase 4 — best-hour calculation and wait/skip logic                                                       |
| database.py                                    | Firestore data layer — videos, snapshots, AB tests, posted topics, spy cache                              |
| research_agent.py                              | Topic research via LLM                                                                                    |
| script_agent.py                                | Script generation, hook scoring + rewrite                                                                 |
| seo_agent.py                                   | Title (AB-tested), description, hashtags                                                                  |
| flow_prompt_agent.py                           | Cinematic clip prompts for Google Flow/Veo — continuous 3-part story structure                            |
| veo_agent.py                                   | Direct Veo API clip generation (requires billing-enabled key)                                             |
| thumbnail_generator.py / thumbnail_agent.py    | Thumbnail generation                                                                                      |
| image_agent.py                                 | Background visuals — Pexels stock (manual toggle) or generative                                            |
| voice_agent.py                                 | Edge TTS voiceover (English)                                                                              |
| caption_agent.py                               | Word-by-word SRT captions                                                                                 |
| video_agent.py                                 | Video rendering — Pillow frames or Flow clip stitching                                                     |
| upload_agent.py                                | YouTube upload with SEO metadata                                                                          |
| analytics_agent.py                             | Channel stats via YouTube API                                                                             |
| view_tracker_agent.py                          | Scheduled snapshots, writes to Firestore                                                                  |
| spy_agent.py                                   | Monitor top AI/tech channels                                                                              |

### Agents — Hindi (`agents_hindi/`)

Mirrors the English structure with Hindi-specific logic — same architecture, completely separate learning data (`channel="hindi"` in Firestore):

| File                    | Purpose                                                                                                                                          |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| saturation_agent.py      | Indian authority channels (Technical Guruji, Trakin Tech, Tech Burner, Beebom)                                                                     |
| velocity_agent.py        | Hindi-only peak hour calculation                                                                                                                    |
| ab_title_agent.py        | Hinglish title patterns, separate scoring/logging                                                                                                   |
| comparison_agent.py      | Indian market competitor search (regionCode=IN, relevanceLanguage=hi), Groq-generated Hinglish recommendations                                     |
| adaptive_scheduler.py    | Hindi-only best-hour logic                                                                                                                          |
| view_tracker_agent.py    | Uses readonly-scoped YouTube client, writes `channel="hindi"` snapshots                                                                             |
| script_agent.py          | Hinglish script, 110-130 word target (~45s, under 60s Shorts limit), retry-expand if too short                                                     |
| seo_agent.py             | Hinglish SEO, accepts AB-tested title override                                                                                                      |
| voice_agent.py           | Sarvam AI Bulbul v3 — primary speaker `shubh`, fallback `vijay`, edge-tts as final fallback. Handles multi-chunk audio concatenation (Sarvam splits long text into multiple WAV segments) |
| flow_prompt_agent.py     | Hinglish cinematic clip prompts, same continuous-story structure as English                                                                        |
| upload_agent.py          | Two YouTube clients — upload-scope and readonly-scope (needed for view tracking)                                                                    |
| spy_agent.py             | Groq-generated trending Hindi tech topics (LLM-based, no YouTube API dependency)                                                                    |
| trending_agent.py        | Fallback trending agent for Hindi region                                                                                                            |

### Agents — Cricket (`agents_cricket/`)

Third channel, added after English and Hindi were stable. English-language content, scoped to Indian cricket only (IPL, Men's/Women's national team, domestic tournaments) — not general/global match coverage.

| File                    | Purpose                                                                                                          |
| ------------------------ | -------------------------------------------------------------------------------------------------------------- |
| trending_agent.py        | Finished-match/news lookup, filtered to Indian cricket                                                          |
| research_agent.py        | Match scorecard/summary fetch                                                                                    |
| script_agent.py          | Cricket recap script generation                                                                                  |
| seo_agent.py              | Title, description, hashtags (`#Cricket #IPL #Shorts`)                                                          |
| image_agent.py            | Generative (Imagen 3) background visuals by default, with real-photo priority preserved as fallback              |
| voice_agent.py            | Sarvam AI Bulbul v3 — primary speaker `shubh`, fallback `vijay`, English (`en-IN`); independent from `agents/voice_agent.py` so voice changes never affect the English channel |
| video_agent.py            | Lightweight low-memory renderer (static crop-to-fit clips)                                                       |
| upload_agent.py           | YouTube upload with SEO metadata, separate cricket channel credentials                                          |
| analytics_agent.py        | Channel stats via YouTube API (cricket channel's own credentials)                                                |
| view_tracker_agent.py     | Scheduled snapshots, writes to Firestore under the cricket channel                                              |
| velocity_agent.py         | Cricket-only peak hour calculation                                                                              |
| database.py               | Firestore data layer for cricket (`cricket_*` collections)                                                       |

### Environment Variables / Secrets

Migrated from plain Railway env vars into Secret Manager during the Firebase move; rotated all credentials in the process.

| Variable                                  | Purpose                                                                          | Scope    |
| ------------------------------------------- | ----------------------------------------------------------------------------------- | -------- |
| GROQ_API_KEY                                | LLM inference                                                                       | All      |
| GEMINI_API_KEY                              | LLM fallback + Imagen 3 generative images                                           | All      |
| PEXELS_API_KEY                              | Background images (manual/stock mode)                                               | All      |
| YOUTUBE_API_KEY                             | YouTube Data API (search, public stats)                                             | All      |
| YOUTUBE_TOKEN_B64                           | English OAuth upload token (base64)                                                 | English  |
| YOUTUBE_CLIENT_SECRETS_B64                  | English OAuth client secrets (base64)                                               | English  |
| YOUTUBE_ANALYTICS_TOKEN_B64                 | English analytics OAuth token (base64)                                              | English  |
| YOUTUBE_TOKEN_JSON / HINDI_TOKEN_JSON       | Hindi OAuth token (raw JSON, needs `youtube.upload` + `youtube.readonly` scopes)      | Hindi    |
| CRICKET_YOUTUBE_TOKEN_B64                   | Cricket OAuth token (base64) — needs both `youtube.upload` and `youtube.readonly`     | Cricket  |
| SARVAM_API_KEY                              | Bulbul v3 native TTS voice                                                          | Hindi, Cricket |
| CRICAPI_KEY                                 | Cricket match/scorecard data (cricketdata.org)                                      | Cricket  |
| APP_PASSWORD                                | Streamlit dashboard login                                                           | All      |
| INSTAGRAM_USERNAME / INSTAGRAM_PASSWORD     | Instagram Reels cross-posting                                                       | English  |

---

## Dashboard

The Streamlit app has these pages, most supporting a channel selector (English/Hindi/Cricket):

- **Generate Video** — manual topic input, trending topic button, image mode toggle (generative / Pexels-stock), auto-upload toggle
- **Peak Hours** — view velocity by hour of day, top 5 upload windows, per-video sparkline (channel selector)
- **Comparison** — competitor benchmark, views/engagement charts, recommendations (channel selector)
- **A/B Titles** — pattern win-rate chart, recent title test log, manual title tester
- **Schedule** — current best upload hour, 24h velocity chart, adaptive scheduler explanation (channel selector)

---

## Intelligence Roadmap — Actual Build History

This replaces the original planned roadmap below with what was actually shipped. Phase numbering reflects real build order, not the original plan.

---

### Phase 0 — Data Collection

**Status: Complete**

Hourly snapshots of views, likes, and comments. Originally JSON with GitHub backup, then migrated to SQLite, then migrated again to **Firestore** as part of the Firebase move (see "Firebase Migration" below).

---

### Phase 1 — Velocity Analysis and Peak Hour Detection

**Status: Complete — all three channels**

Calculates view velocity (views gained per hour) per video per snapshot interval, aggregated by hour of day. Powers the Peak Hours dashboard and feeds Phase 4. Built separately per channel, each reading its own partition of Firestore data.

---

### Phase 1.5 — Saturation Engine

**Status: Complete — all three channels**

Scores topics 0-100 based on recent competing video count and authority-channel coverage before research begins. Fails open (proceeds) if the YouTube API is unavailable rather than blocking the pipeline.

---

### Phase 2 — Comparison Engine

**Status: Complete — English and Hindi**

Fetches top 10 competing videos per topic, computes average views/engagement/title length/duration, identifies the best upload hour among top performers, and generates concrete recommendations. Wired into script and SEO generation so competitor intelligence directly shapes content.

---

### Phase 3 — A/B Title Testing

**Status: Complete — English and Hindi**

Generates 3 title variations per video using 8 possible psychological patterns, scores each on a 10-point rubric, and selects the winner for upload. Logs every test for pattern-performance tracking over time.

---

### Phase 4 — Adaptive Scheduling

**Status: Complete — all three channels**

Checks on a schedule whether the current UTC hour matches a learned peak-velocity window (minimum sample threshold required), and only generates+uploads when it does. Falls back to spread-out default hours until enough real data accumulates. Cricket capped at 2-3 videos/day.

---

### SQLite Migration

**Status: Complete, superseded by Firebase Migration below**

Originally replaced fragile per-feature JSON files with a single SQLite database shared by English and Hindi, partitioned by a `channel` column. This has since been migrated to Firestore.

---

### Voice Quality Fixes (Hindi + Cricket)

**Status: Complete**

Replaced edge-tts (generic voices) with Sarvam AI's **Bulbul v3** model (39 speakers, LLM-based prosody modeling for natural Hindi/Indian-English rhythm, vs. v2's 7 speakers with no emotion/temperature control). Selected `shubh` as the primary voice for both Hindi and Cricket after generating and comparing demo clips across a shortlist of 12 candidate voices. Cricket runs its own independent `voice_agent.py` (English, `en-IN`) rather than sharing English's edge-tts file, so voice changes to one channel never affect another. Fixed a critical bug where Sarvam splits long text into multiple WAV segments and only the first was being saved (silently cutting audio) — fixed by concatenating all returned segments.

---

### Clip Prompt Engineering (English + Hindi)

**Status: Complete**

Iterated through several versions of `flow_prompt_agent.py` to fix recurring issues: clips describing the scene but never delivering actual information (fixed by extracting concrete facts from the script and forcing them as on-screen text), each clip reading as a disconnected scene rather than one conversation (fixed by writing the full dialogue first, then splitting into 3 parts), and dialogue pasting the raw topic title into the script unnaturally (fixed by instructing concept extraction instead of literal title insertion).

---

### Cricket Channel (Phase — new)

**Status: Complete**

Third channel added after English and Hindi were stable. Built with its own agent set (`agents_cricket/`), initially deployed on Render's free tier with Supabase Postgres (no persistent disk on Render, hence Postgres over SQLite). Migrated to Firestore along with the other two channels during the Firebase move. Scoped specifically to Indian cricket — IPL, Men's and Women's national teams, domestic cricket — rather than global match coverage, with a 2-3 videos/day cap.

---

### Generative Image Agent

**Status: Complete — all three channels**

Added Imagen 3 as a generative alternative to Pexels stock/real-photo images. Selectable manually per run from the dashboard (Generative vs. Pexels/Pixel toggle); adaptive/unattended scheduled runs always use generative by default, with automatic fallback to the real-photo/stock pipeline if generation fails, so the pipeline never blocks on an Imagen error. Cricket retains "real-photo priority" as its fallback specifically, given the value of authentic match imagery when available.

---

### Firebase Migration

**Status: Complete**

Migrated the entire backend and hosting off Railway/Render + Supabase onto Firebase (Blaze plan) + Cloud Run, after Railway's free-tier limits were exhausted. Key changes:

- **Database**: SQLite (English/Hindi) and Supabase Postgres (Cricket) both replaced by Firestore, with Postgres joins reworked as either denormalized writes or client-side Python joins, and percentile calculations moved from SQL to Python
- **Persistence**: Cloud Run's ephemeral filesystem has the same disk-wipe problem Railway had — kept the existing GitHub Contents API workaround pattern where needed, and moved persisted assets to Firebase Storage where cleaner
- **Scheduling**: Replaced Railway's always-on worker loops with Cloud Scheduler triggering Cloud Run jobs per channel
- **Secrets**: Moved all API keys and OAuth tokens from plain env vars into Secret Manager; rotated every credential during the move, including a Supabase credential that had been accidentally committed to git history twice
- **Dashboard**: Streamlit dashboard deployed to Cloud Run (Firebase Hosting rewrites to it), rather than moved to a static host, since Firebase Hosting doesn't serve Python apps directly
- **Data migration**: Existing Supabase and SQLite data backfilled into Firestore via batch writes
- Verified end-to-end post-migration with a real cricket video generated and uploaded live to YouTube by the automated pipeline, confirming Firestore reads/writes, Cloud Run execution, and all three channels' credentials were correctly wired

---

## Deferred / Not Yet Built

These remain reasonable next steps, listed honestly rather than removed:

- **Hook Analyzer / Failure Intelligence** — script hooks are scored and rewritten if weak (already in `script_agent.py`), but no systematic failure-pattern tracking exists yet
- **Narrative Intelligence** — no dedicated retention-curve scoring layer
- **Channel DNA Engine** — no persistent "brand identity" memory separate from AB title pattern stats
- **Audience Intelligence** — no YouTube Analytics demographic pull
- **Opportunity Intelligence** — no pre-trend prediction (GitHub/Reddit/Trends signal aggregation)
- **Vision Intelligence** — no automated thumbnail visual analysis
- **Monetization Intelligence** — no RPM/revenue-correlated topic scoring
- **Closing the loop on Phase 3** — AB title scores are currently LLM-predicted, not yet fully validated against actual YouTube view counts after 24h for all channels
- **Phase 2/3 for Cricket** — Comparison Engine and A/B Title Testing exist for English/Hindi but haven't been built for Cricket yet
- **Centralized "brain" service** — deliberately deferred. All three channels currently share infrastructure patterns but run independently. A formal client-server brain (single API that every scheduler calls, auto-detecting channel/language) remains postponed until the pipeline is fully stable across all three channels

---

## Local Setup

```
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

# Run Cricket scheduler
python scheduler_cricket.py
```

---

## Deployment

```
git add .
git commit -m "description"
git push

# Deploy to Cloud Run (per service)
gcloud run deploy ai-carryon-dashboard --source . --region us-central1
```

Firebase/Cloud Run does not auto-deploy on push the way Railway did — each Cloud Run service (dashboard, English worker, Hindi worker, Cricket worker) needs its own explicit `gcloud run deploy`, or a CI/CD trigger set up separately if you want push-to-deploy back.

---

## Important Notes

**YouTube API quota**: 10,000 units/day per project. Each upload costs ~1,650 units. Per-channel cadences are tuned to stay within quota.

**Firestore persistence**: Firestore is now the source of truth for all three channels — replaces both the old SQLite file and Cricket's separate Supabase Postgres instance. Verify writes are landing correctly after any deploy that touches a worker.

**OAuth tokens**: All tokens (English upload, English analytics, Hindi combined, Cricket) can expire (`invalid_grant: Token has been expired or revoked`). Re-authenticate locally and update the relevant secret in Secret Manager. Hindi and Cricket tokens specifically need both `youtube.upload` and `youtube.readonly` scopes — a token with upload-only scope will silently fail view tracking with a 403 `insufficientPermissions` error.

**Sarvam AI text limits**: Long scripts get split into multiple audio chunks by the API — always concatenate `audio.audios[]` in full, never assume a single segment. Bulbul v3 speakers are not interchangeable with v2 speakers — using a v2-only name (e.g. `karun`, `hitesh`) with `model="bulbul:v3"` will fail.

**Flow/Veo clip generation**: Free tier is limited (Google AI Pro gives ~1,000 credits/month, each 8s clip costs 20). Brand/product names in clip prompts can trigger Flow's "prominent people/brands" policy rejection — sanitize scene descriptions (not spoken dialogue) before submission.

**Generative image fallback**: The generative image agent (Imagen 3) is expected to occasionally fail (quota, content policy, transient errors) — the pipeline always falls back to real-photo/stock images rather than blocking, by design. A failed generative attempt in the logs is not itself a bug.

---

*AI CarryON — Built by Amit Kumar*
