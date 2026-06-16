# AI CarryON — Autonomous YouTube Channel Intelligence System

An autonomous AI system that researches trending topics, generates video scripts, creates YouTube Shorts, and uploads them automatically — while learning from channel performance data to improve over time.

**Live**: https://ai-carryon-production.up.railway.app  
**Repo**: https://github.com/Unknown183-a/ai-carryon  
**Channel**: AI CarryON (Tech/AI niche)

---

## What This Does

Every 5 hours, without any human input, the system:

1. Fetches a trending AI/tech topic (with niche guard to reject off-topic content)
2. Researches it and writes a 30-45 second script
3. Generates SEO-optimized title, description, and hashtags
4. Creates a thumbnail using Pexels images
5. Generates a human-sounding voiceover (Edge TTS)
6. Renders a 1080x1920 Shorts video with word-by-word captions and Ken Burns zoom
7. Uploads to YouTube with thumbnail
8. Records a timestamped view snapshot for intelligence analysis

Every hour, it tracks view/like/comment counts for the 20 most recent videos and backs up this data to GitHub for persistence across redeployments.

---

## Current Architecture

### Pipeline

```
Trending Topic (niche-filtered)
    -> Research (Groq LLaMA 3.3-70B)
    -> Script (30-45s)
    -> SEO (title pattern rotation, 15 hashtags)
    -> Thumbnail (Pexels + text overlay)
    -> Background Images (Pexels)
    -> Voiceover (Edge TTS: en-US-AndrewMultilingualNeural)
    -> Captions (word-by-word SRT, auto-fit font)
    -> Video (Pillow frames + Ken Burns + ffmpeg)
    -> YouTube Upload (with thumbnail)
    -> View Snapshot (backed up to GitHub)
```

### Services (Railway)

| Service | Role | Schedule |
|---|---|---|
| worker | Scheduler — video generation + view tracking | Video: every 5h, Tracking: every 1h |
| ai-carryon | Streamlit web dashboard | Always on |

### Agents

| File | Purpose |
|---|---|
| trending_agent.py | Trending topics with niche guard and LLM fallback |
| research_agent.py | Topic research via LLM |
| script_agent.py | 30-45s video script generation |
| seo_agent.py | Title (6 rotating patterns), description, hashtags |
| thumbnail_generator.py | 1080x1920 thumbnail with Pexels background |
| image_agent.py | Background images from Pexels |
| voice_agent.py | Edge TTS voiceover with gTTS fallback |
| caption_agent.py | Word-by-word SRT caption generation |
| video_agent.py | Video rendering — Pillow frames, Ken Burns, ffmpeg stitch |
| upload_agent.py | YouTube upload with SEO metadata and thumbnail |
| analytics_agent.py | Channel stats and video performance via YouTube API |
| view_tracker_agent.py | Hourly view/likes/comments snapshots |
| spy_agent.py | Monitor top AI/tech channels (6h cache) |
| data_persistence.py | Backup and restore view_history.json via GitHub API |

### Environment Variables

| Variable | Purpose |
|---|---|
| GROQ_API_KEY | LLM inference |
| PEXELS_API_KEY | Background and thumbnail images |
| YOUTUBE_API_KEY | YouTube Data API |
| YOUTUBE_TOKEN_B64 | OAuth upload token (base64) |
| YOUTUBE_CLIENT_SECRETS_B64 | OAuth client secrets (base64) |
| YOUTUBE_ANALYTICS_TOKEN_B64 | Analytics OAuth token (base64) |
| GITHUB_TOKEN | View history backup to data branch |
| APP_PASSWORD | Streamlit dashboard login |

---

## Dashboard

The Streamlit app at ai-carryon-production.up.railway.app has three pages:

- **Generate Video** — manual topic input, trending topic button, optional auto-upload toggle
- **Analytics** — channel stats, video performance table, bar chart, auto-refresh every 30 minutes
- **Trending Spy** — top Shorts from Fireship, MKBHD, Two Minute Papers, Computerphile, AI Explained with one-click "Make This Video" button

---

## Intelligence Roadmap

The system is designed to evolve from a simple auto-uploader into a self-improving channel intelligence brain. Each phase builds on the previous one and requires real channel data to function meaningfully.

---

### Phase 0 — Data Collection
**Status: Complete (June 16, 2026)**

Hourly snapshots of views, likes, and comments for the 20 most recent videos. Each snapshot includes a UTC timestamp, enabling view velocity calculation over time.

Data is stored in `output/view_history.json` and automatically backed up to the `data` branch on GitHub after every tracking run, making it safe across Railway redeployments.

```json
{
  "video_id": {
    "title": "Video Title",
    "published": "2026-06-15",
    "snapshots": [
      {"timestamp": "2026-06-16T12:00:00", "views": 709, "likes": 7, "comments": 0},
      {"timestamp": "2026-06-16T13:00:00", "views": 724, "likes": 8, "comments": 0}
    ]
  }
}
```

---

### Phase 1 — Velocity Analysis and Peak Hour Detection
**Target: June 19-20, 2026**

Calculate view velocity (views gained per hour) for each video at each snapshot interval. Aggregate velocity by hour of day across all videos to identify peak engagement windows for the channel.

Build a "Peak Hours" tab in the Streamlit dashboard showing average view velocity per hour of day as a chart. This becomes the data foundation for adaptive scheduling in Phase 5.

Requires: 48-72 hourly snapshots per video (2-3 days of data).

New file: `agents/velocity_agent.py`

---

### Phase 1.5 — Saturation Engine
**Target: June 20, 2026**

Before researching a topic, check how saturated it is. Score each candidate topic by how many similar videos were uploaded in the last 24 hours and how many high-authority channels have already covered it.

Only proceed with topics that have an opportunity score above a threshold. This prevents producing content that is competing against dozens of identical videos on the same day.

Pipeline becomes: Trend -> Saturation Check -> Research

---

### Phase 2 — Comparison Engine
**Target: June 20-21, 2026**

Group videos uploaded within similar time windows (within 2 hours of each other). Rank each group by view velocity. For the top and bottom performers in each group, extract their stored metadata: title, description, hashtags, topic, upload hour, and title pattern used.

Output is structured comparison pairs that feed directly into Phase 3.

Requires: Phase 1 complete, at least 10 videos with velocity data.

---

### Phase 3 — LLM Insight Generation
**Target: June 21-22, 2026**

Feed comparison pairs from Phase 2 into an LLM with a structured prompt: given two videos uploaded at the same time, one performing 3x better than the other, analyze the differences in title, hook, topic specificity, and tags, and produce three concrete improvement actions.

Store insights in `output/insights.json` with timestamps. Build a "Channel Insights" tab in the Streamlit dashboard.

Also build at this stage:
- **Hook Analyzer** — score the opening line of every new script before video generation. Rewrite if score is below 7/10.
- **Failure Intelligence** — track why videos underperform (weak hook, over-saturated topic, bad upload time) so these patterns are not repeated.

New files: `agents/insight_agent.py`, `agents/failure_agent.py`

---

### Phase 3.5 — Narrative Intelligence
**Target: June 22, 2026**

The current script agent generates content but does not optimize for retention structure. Add a narrative scoring layer that evaluates each script for curiosity density, tension curve, open loops, and surprise pacing.

Score each script before rendering. If the score is below threshold, regenerate with explicit narrative instructions.

New file: `agents/narrative_agent.py`

---

### Phase 4 — Feedback into SEO Generation
**Target: June 22-23, 2026**

Modify `seo_agent.py` to inject recent insights from `insights.json` into the generation prompt. Add viral pattern memory that tracks which title patterns, hooks, and topic angles historically drove the highest velocity on this channel.

Future videos are generated with awareness of what has actually worked, not just general best practices.

New file: `agents/pattern_memory_agent.py`

---

### Phase 4.5 — Persona Engine
**Target: June 23, 2026**

Before audience intelligence data is available from YouTube Analytics, manually define audience personas (Developer, Beginner, Student, Founder). Script style adapts per persona: developer persona gets technical, fast, high-density content; beginner persona gets simple, relatable, slower explanation.

This can later be replaced by data-driven persona detection from Phase 6.

---

### Phase 5 — Adaptive Scheduling
**Target: June 23-24, 2026**

Replace the fixed 5-hour interval with a dynamic schedule built from Phase 1 peak hour data. Distribute 5 daily uploads across the identified peak engagement windows. Re-evaluate the schedule weekly as more data accumulates.

---

### Phase 5.5 — Channel DNA Engine
**Target: June 24, 2026**

Store the channel's identity: best title patterns, best video durations, best hooks, best tones, best thumbnail styles. This becomes channel identity memory — distinct from viral pattern memory because it tracks consistent brand attributes rather than one-off wins.

Critical for later multi-channel support, where each channel needs its own DNA profile.

New file: `agents/channel_dna_agent.py`

---

### Phase 6 — Audience Intelligence
**Target: July 1+, 2026**

Pull YouTube Analytics audience data: demographics, watch time, traffic sources, viewer geography. Build audience personas from real data rather than manual definitions. Script style, hook style, and topic selection adapt to the dominant audience segment.

Requires: 2-4 weeks of channel data, yt-analytics.readonly OAuth scope.

---

### Phase 7 — Opportunity Intelligence
**Target: July 7+, 2026**

Predict what will trend next rather than reacting to what is already trending. Aggregate signals from GitHub star velocity, Reddit mention growth, Google Trends acceleration, and Product Hunt launches. Score topics by "about to trend" probability and make the channel a consistent first mover.

New file: `agents/opportunity_agent.py`

---

### Phase 8 — Vision Intelligence
**Target: July 14+, 2026**

Analyze top-performing thumbnails visually using OpenCV and CLIP. Extract features: text density, color intensity, contrast, face presence, emotion. Generate thumbnail recommendations based on what visual patterns perform best in the AI/tech niche specifically.

New file: `agents/vision_agent.py`

---

### Phase 9 — Monetization Intelligence
**Target: July 21+, 2026**

Track which video topics and niches correlate with higher RPM, affiliate engagement, and sponsorship interest. Optimize topic selection for revenue quality, not just view count. Not all views are equal — developer tools content consistently outperforms general tech content on revenue per view.

New file: `agents/monetization_agent.py`

---

### LangGraph Migration
**Target: After Phase 3 is complete**

The current pipeline uses sequential function calls. After Phase 3 stabilizes the workflow, migrate to LangGraph for proper agent orchestration. LangGraph works best when the workflow is stable — migrating while it is still changing adds unnecessary complexity.

---

## Future: Multi-Channel Product

After the brain is proven on AI CarryON, the system generalizes into a product any YouTube channel can connect to.

What changes:

```python
channel_config = {
    "channel_id": "UC...",
    "niche_keywords": ["cooking", "recipes", "food"],
    "reject_keywords": ["gaming", "tech", "finance"],
    "tone": "friendly and educational",
    "upload_frequency": 4,
    "target_audience": "home cooks aged 25-45"
}
```

Each customer connects their channel via OAuth. The brain analyzes their last 50 videos to detect niche, tone, and patterns automatically. It then configures itself and starts learning from their data independently.

The Channel DNA Engine (Phase 5.5) is the critical foundation for this — without per-channel identity memory, the multi-channel product cannot maintain brand consistency across different channels.

**Human Override Layer** (needed for SaaS): allow customers to force topic, reject topic, force upload time, force title style, force script style. Autonomous does not mean uncontrollable.

---

## Project Structure

```
AI carryON/
├── agents/
│   ├── analytics_agent.py
│   ├── caption_agent.py
│   ├── data_persistence.py
│   ├── image_agent.py
│   ├── research_agent.py
│   ├── script_agent.py
│   ├── seo_agent.py
│   ├── spy_agent.py
│   ├── thumbnail_agent.py
│   ├── thumbnail_generator.py
│   ├── trending_agent.py
│   ├── upload_agent.py
│   ├── video_agent.py
│   ├── view_tracker_agent.py
│   └── voice_agent.py
├── assets/
│   ├── fonts/Arial-Bold.ttf
│   ├── music/background.wav
│   └── thumbnails/
├── output/                      # gitignored
│   ├── view_history.json
│   ├── insights.json            # Phase 3+
│   ├── posted_topics.txt
│   └── spy_cache.json
├── app.py
├── scheduler.py
├── requirements.txt
├── Procfile
└── runtime.txt
```

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

# Run scheduler
python scheduler.py
```

---

## Deployment

```bash
# Deploy
git add .
git commit -m "description"
git push

# Force redeploy without code changes
git commit --allow-empty -m "Trigger redeploy"
git push
```

Railway auto-deploys both services on every push to main.

---

## Important Notes

**YouTube API quota**: 10,000 units per day. Each upload costs approximately 1,650 units. Maximum sustainable upload rate is 6 per day. Current schedule of every 5 hours produces 4-5 uploads per day, staying safely within quota.

**View history**: Backed up to the `data` branch on GitHub after every hourly tracking run. Safe across redeployments. Do not push code changes that restart the worker unnecessarily while accumulating data for Phase 1.

**OAuth tokens**: YOUTUBE_TOKEN_B64 and YOUTUBE_ANALYTICS_TOKEN_B64 may expire. Re-authenticate locally and update Railway variables if uploads start failing with authentication errors.

**Railway budget**: Monitor remaining balance in the Railway dashboard. Current plan: hobby tier.

---

## Development Timeline

| Date | Milestone |
|---|---|
| Jun 13, 2026 | Project started, basic pipeline built |
| Jun 14, 2026 | Railway deployment, OOM fix, full pipeline working end-to-end |
| Jun 14, 2026 | Analytics dashboard, Trending Spy, SEO upgrade, password protection |
| Jun 15, 2026 | Ken Burns zoom effect, caption quality improvements |
| Jun 16, 2026 | Niche guard, title diversity patterns, view tracker, GitHub data persistence |
| Jun 19-20, 2026 | Phase 1 — velocity analysis, peak hour dashboard |
| Jun 20-21, 2026 | Phase 1.5 + Phase 2 — saturation engine, comparison engine |
| Jun 21-22, 2026 | Phase 3 — LLM insights, hook analyzer, failure intelligence |
| Jun 22-23, 2026 | Phase 3.5 + Phase 4 — narrative intelligence, SEO feedback loop |
| Jun 23-24, 2026 | Phase 4.5 + Phase 5 — persona engine, adaptive scheduling |
| Jun 24, 2026 | Phase 5.5 — channel DNA engine |
| Jul 1+, 2026 | Phase 6 — audience intelligence |
| Jul 7+, 2026 | Phase 7 — opportunity intelligence |
| Jul 14+, 2026 | Phase 8 — vision intelligence |
| Jul 21+, 2026 | Phase 9 — monetization intelligence |
| Aug+, 2026 | Multi-channel SaaS productization |

---

*AI CarryON — Built by Amit Kumar*
