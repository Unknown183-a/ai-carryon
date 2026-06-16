# 🤖 AI CarryON — Autonomous YouTube Channel Intelligence System

> **Vision**: A self-learning AI brain that autonomously manages, optimizes, and grows any YouTube channel — from content generation to upload scheduling to performance analysis.

---

## 📌 Current Status (June 16, 2026)

**Stage**: Build → Deploy → Observe → Improve

The system is live, autonomous, and actively collecting data on Railway cloud infrastructure.

- **Channel**: AI CarryON (Tech/AI niche)
- **Live URL**: https://ai-carryon-production.up.railway.app
- **GitHub**: https://github.com/Unknown183-a/ai-carryon
- **Deployment**: Railway (2 services: `worker` + `ai-carryon` Streamlit app)

---

## 🏗️ Current Architecture

### Pipeline (Fully Automated)
```
Trending Topic
    ↓ (niche guard: AI/tech only)
Research Agent (Groq LLaMA 3.3-70B)
    ↓
Script Agent (30-45 second script)
    ↓
SEO Agent (title diversity: 6 rotating patterns)
    ↓
Thumbnail Agent (text + Pexels image)
    ↓
Image Agent (background images via Pexels)
    ↓
Voice Agent (Edge TTS: en-US-AndrewMultilingualNeural)
    ↓
Caption Agent (word-by-word SRT)
    ↓
Video Agent (Pillow frames + Ken Burns zoom + ffmpeg)
    ↓
Upload Agent (YouTube API + thumbnail)
    ↓
View Tracker (hourly snapshots → GitHub backup)
```

### Services on Railway
| Service | Function | Schedule |
|---|---|---|
| `worker` | Scheduler (video generation + view tracking) | Video: every 5h / Tracking: every 1h |
| `ai-carryon` | Streamlit web app (manual generation + analytics) | Always on |

### Key Agents (`/agents/`)
| Agent | Purpose |
|---|---|
| `trending_agent.py` | Fetch trending topics, niche filter, LLM fallback |
| `research_agent.py` | Research topic via LLM |
| `script_agent.py` | Generate 30-45s video script |
| `seo_agent.py` | Generate title (6 patterns), description, 15 hashtags |
| `thumbnail_generator.py` | Create 1080x1920 thumbnail |
| `image_agent.py` | Fetch background images from Pexels |
| `voice_agent.py` | Generate voiceover (Edge TTS + gTTS fallback) |
| `caption_agent.py` | Generate word-by-word SRT captions |
| `video_agent.py` | Render final video (Ken Burns + captions + ffmpeg) |
| `upload_agent.py` | Upload to YouTube with SEO metadata |
| `analytics_agent.py` | Fetch channel stats and video performance |
| `view_tracker_agent.py` | Hourly view/likes/comments snapshots |
| `spy_agent.py` | Monitor top AI/tech channels (6h cache) |
| `data_persistence.py` | Backup/restore view_history.json via GitHub API |

### Environment Variables (Railway)
| Variable | Service | Purpose |
|---|---|---|
| `GROQ_API_KEY` | both | LLM inference |
| `PEXELS_API_KEY` | both | Background images |
| `YOUTUBE_API_KEY` | both | YouTube Data API |
| `YOUTUBE_TOKEN_B64` | both | OAuth upload token |
| `YOUTUBE_CLIENT_SECRETS_B64` | both | OAuth client secrets |
| `YOUTUBE_ANALYTICS_TOKEN_B64` | both | Analytics OAuth token |
| `ELEVENLABS_API_KEY` | both | (reserved, not active) |
| `GITHUB_TOKEN` | worker | View history backup |
| `APP_PASSWORD` | ai-carryon | Streamlit login |

---

## 📊 Streamlit Dashboard Pages

1. **🎬 Generate Video** — manual topic input, trending topic button, auto-upload toggle
2. **📊 Analytics** — channel stats, video performance table, bar chart, auto-refresh
3. **🕵️ Trending Spy** — top videos from Fireship, MKBHD, Two Minute Papers, Computerphile, AI Explained

---

## 🧠 Brain Intelligence Roadmap

The core vision: a self-improving AI that learns from channel data, adapts content strategy, and autonomously grows any YouTube channel.

---

### Phase 0 — Data Collection ✅ COMPLETE (Jun 16, 2026)
**What**: Hourly snapshots of views/likes/comments for 20 most recent videos, stored with timestamps.

**Files**:
- `agents/view_tracker_agent.py` — collects snapshots
- `agents/data_persistence.py` — backs up to GitHub `data` branch
- `output/view_history.json` — local data store

**Data structure**:
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

**Status**: Running. Backed up to GitHub `data` branch after every hourly run.

---

### Phase 1 — Velocity Analysis & Peak Hour Detection
**Target date**: June 19-20, 2026

**What to build**:
- `agents/velocity_agent.py` — compute views-gained-per-hour for each video at each snapshot
- Aggregate velocity by hour-of-day (IST) across all videos
- Identify peak engagement windows (e.g., "6-9 PM IST: high velocity")
- Add "📈 Peak Hours" tab to Streamlit dashboard with hourly velocity chart

**Implementation**:
```python
# For each video, for each consecutive snapshot pair:
velocity = (views_t2 - views_t1) / hours_between

# Aggregate by hour of day:
peak_hours[hour_of_day].append(velocity)

# Output: ranked list of hours by average velocity
```

**Needs**: 48-72 hourly snapshots per video (2-3 days of data)

---

### Phase 2 — Comparison Engine
**Target date**: June 20-21, 2026

**What to build**:
- Group videos uploaded within similar time windows (±2 hours)
- Rank by view velocity within each group
- Extract metadata for top vs. bottom performers:
  - Title, description, hashtags, topic, upload hour, pattern used
- Output structured comparison pairs

**Implementation**:
```python
# For each group of videos uploaded close together:
top_video = max(group, key=lambda v: v['velocity'])
bottom_video = min(group, key=lambda v: v['velocity'])

comparison = {
    "top": {"title": ..., "topic": ..., "tags": ..., "velocity": ...},
    "bottom": {"title": ..., "topic": ..., "tags": ..., "velocity": ...}
}
```

**Needs**: Phase 1 complete + at least 10 videos with velocity data

---

### Phase 3 — LLM-Powered Insight Generation (The Brain)
**Target date**: June 21-22, 2026

**What to build**:
- `agents/insight_agent.py` — feed comparison pairs to LLM
- Prompt: "Video A got 3x more views than Video B uploaded same evening. Here's both titles/descriptions/tags/topics/hooks. What caused the difference? Give 3 actionable improvements."
- Store insights in `output/insights.json` with timestamps
- Build "🧠 Channel Insights" tab in Streamlit dashboard

**Also build**:
- **Hook Analyzer** — score first line of every new script (1-10) before video generation
- **Retention Predictor** — score full script for predicted watch time, rewrite if score < 7

**Implementation**:
```python
# Hook scoring
hook_score = llm.invoke(f"Score this YouTube Short opening line 1-10: '{first_line}'")
if hook_score < 7:
    first_line = llm.invoke(f"Rewrite this hook to be more compelling: '{first_line}'")
```

**Needs**: Phase 2 complete

---

### Phase 4 — Feedback Loop into SEO Generation
**Target date**: June 22-23, 2026

**What to build**:
- Modify `seo_agent.py` to inject recent insights from `insights.json`
- Add "viral pattern memory" — track which title patterns, topics, and hooks historically performed best
- `agents/pattern_memory_agent.py` — stores and retrieves best performing patterns

**Implementation**:
```python
# In seo_agent.py prompt:
recent_insights = load_top_insights(n=3)
prompt += f"\nChannel learnings from past performance:\n{recent_insights}"
prompt += f"\nBest performing title pattern historically: {best_pattern}"
prompt += f"\nTopics that drove highest velocity: {top_topics}"
```

**Needs**: Phase 3 complete + insights.json with at least 5 entries

---

### Phase 5 — Adaptive Scheduling
**Target date**: June 23-24, 2026

**What to build**:
- Replace fixed `schedule.every(5).hours` with dynamic peak-hour scheduling
- Read peak hours from Phase 1 analysis
- Distribute 5 daily uploads across identified peak windows
- Re-evaluate schedule weekly as more data accumulates

**Implementation**:
```python
# Instead of fixed 5-hour intervals:
peak_windows = get_peak_hours()  # e.g., [8, 13, 18, 20, 22] IST
for hour in peak_windows:
    schedule.every().day.at(f"{hour:02d}:00").do(generate_and_upload)
```

**Needs**: Phase 1 complete (peak hour data)

---

### Phase 6 — Audience Intelligence
**Target date**: July 1+, 2026

**What to build**:
- Analyze YouTube Analytics for audience demographics (age, country, watch time)
- Build audience personas: "US developers", "Indian students", "AI founders"
- Adapt script style, hook style, and topic selection per dominant persona
- `agents/audience_agent.py`

**Needs**: 2-4 weeks of channel data + YouTube Analytics API (yt-analytics.readonly scope)

---

### Phase 7 — Opportunity Intelligence
**Target date**: July 7+, 2026

**What to build**:
- Predict what will trend NEXT (not just what's trending now)
- Signal sources: GitHub stars rising, Reddit mentions, X/Twitter mentions, Google Trends
- `agents/opportunity_agent.py` — aggregates signals, scores topics by "about to trend" probability
- Makes your channel a first-mover on emerging topics

**Needs**: External API integrations (GitHub API, Reddit API, Google Trends)

---

### Phase 8 — Vision Intelligence
**Target date**: July 14+, 2026

**What to build**:
- Analyze top-performing thumbnails visually (text density, color, contrast, face presence)
- Use OpenCV/CLIP to extract visual features
- Generate thumbnail recommendations based on what works for your niche
- `agents/vision_agent.py`

**Needs**: OpenCV, CLIP library, collection of thumbnail performance data

---

### Phase 9 — Monetization Intelligence
**Target date**: July 21+, 2026

**What to build**:
- Track which video topics/niches attract higher RPM (revenue per mille)
- Identify which topics drive affiliate clicks, sponsorship inquiries
- Optimize topic selection for revenue, not just views
- `agents/monetization_agent.py`

**Needs**: Channel monetization data, 4+ weeks of history

---

## 🌐 Future Vision: Multi-Channel SaaS Product

**Target**: August 2026+

After the brain is proven on AI CarryON, generalize into a product any YouTube channel can use.

### What changes for multi-channel:
```python
# Channel config (per customer):
channel_config = {
    "channel_id": "UC...",
    "niche_keywords": ["cooking", "recipes", "food"],
    "reject_keywords": ["gaming", "tech", "finance"],
    "tone": "friendly and educational",
    "upload_frequency": 4,  # per day
    "target_audience": "home cooks aged 25-45"
}
```

### Architecture evolution:
```
Single channel (now)          Multi-channel SaaS (Aug+)
──────────────────            ─────────────────────────
Hardcoded tokens         →    Per-customer OAuth
Hardcoded niche          →    Auto-detected from channel history  
Single view_history.json →    Per-channel database
Fixed scheduling         →    Per-channel adaptive schedule
One Streamlit app        →    Multi-tenant dashboard
```

### Customer onboarding flow:
1. Customer connects their YouTube channel (OAuth)
2. Brain analyzes their last 50 videos to detect niche/tone/patterns
3. Brain configures itself automatically for their channel
4. Starts generating and uploading content
5. Learns and improves from their data independently

---

## 📁 Project Structure

```
AI carryON/
├── agents/
│   ├── analytics_agent.py       # YouTube Analytics
│   ├── caption_agent.py         # SRT caption generation
│   ├── data_persistence.py      # GitHub backup/restore
│   ├── image_agent.py           # Pexels background images
│   ├── research_agent.py        # Topic research (LLM)
│   ├── script_agent.py          # Video script (LLM)
│   ├── seo_agent.py             # Title/description/tags (LLM)
│   ├── spy_agent.py             # Competitor channel monitoring
│   ├── thumbnail_agent.py       # Thumbnail text generation
│   ├── thumbnail_generator.py   # Thumbnail image creation
│   ├── trending_agent.py        # Trending topic + niche guard
│   ├── upload_agent.py          # YouTube upload
│   ├── video_agent.py           # Video rendering (Pillow + ffmpeg)
│   ├── view_tracker_agent.py    # Hourly view snapshots
│   └── voice_agent.py           # TTS voiceover
├── assets/
│   ├── fonts/Arial-Bold.ttf     # Caption font
│   ├── music/background.wav     # Background music
│   └── thumbnails/              # Thumbnail assets
├── output/                      # Generated files (gitignored)
│   ├── view_history.json        # View tracking data
│   ├── insights.json            # Brain learnings (Phase 3+)
│   ├── posted_topics.txt        # Deduplication log
│   └── spy_cache.json           # Competitor data cache
├── app.py                       # Streamlit web dashboard
├── scheduler.py                 # Main automation scheduler
├── requirements.txt
├── Procfile                     # Railway process definitions
└── runtime.txt                  # Python version
```

---

## 🔧 Local Development

```bash
# Clone and setup
git clone https://github.com/Unknown183-a/ai-carryon.git
cd ai-carryon
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env  # fill in your API keys

# Run locally
streamlit run app.py

# Run scheduler locally
python scheduler.py
```

---

## 🚀 Deployment (Railway)

```bash
# Push to deploy (auto-deploys both services)
git add .
git commit -m "your message"
git push

# Force redeploy without code changes
git commit --allow-empty -m "Trigger redeploy"
git push
```

**Railway services**:
- `worker` → runs `python scheduler.py`
- `ai-carryon` → runs `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`

---

## ⚠️ Important Notes

1. **YouTube API Quota**: 10,000 units/day. Each upload ~1,650 units → max ~6 uploads/day. Current schedule: every 5 hours (~4-5/day) ✅
2. **View history persistence**: Backed up to GitHub `data` branch after every hourly tracking run. Safe across redeployments.
3. **Token rotation**: `YOUTUBE_TOKEN_B64` and `YOUTUBE_ANALYTICS_TOKEN_B64` may expire. Re-authenticate locally and update Railway variables if uploads start failing.
4. **Railway budget**: Monitor "days or $ left" in Railway dashboard. Current: ~$4.50 left on free plan.
5. **Niche guard**: Only AI/tech topics allowed. Off-niche topics are rejected and replaced with LLM-generated AI/tech topics.

---

## 📅 Development Timeline Summary

| Date | Milestone |
|---|---|
| Jun 13, 2026 | Project started, basic pipeline built |
| Jun 14, 2026 | Railway deployment, OOM fix, full pipeline working |
| Jun 14, 2026 | Analytics dashboard, Trending Spy, SEO upgrade |
| Jun 14, 2026 | Password protection, Railway Streamlit hosting |
| Jun 15, 2026 | Ken Burns effect, caption quality fix |
| Jun 16, 2026 | Niche guard, title diversity, view tracker, GitHub persistence |
| Jun 19-20, 2026 | **Phase 1**: Velocity analysis + peak hour dashboard |
| Jun 20-21, 2026 | **Phase 2**: Comparison engine |
| Jun 21-22, 2026 | **Phase 3**: LLM insights + Hook Analyzer |
| Jun 22-23, 2026 | **Phase 4**: SEO feedback loop + Pattern Memory |
| Jun 23-24, 2026 | **Phase 5**: Adaptive scheduling |
| Jul 1+, 2026 | **Phase 6**: Audience Intelligence |
| Jul 7+, 2026 | **Phase 7**: Opportunity Intelligence |
| Jul 14+, 2026 | **Phase 8**: Vision Intelligence |
| Jul 21+, 2026 | **Phase 9**: Monetization Intelligence |
| Aug+, 2026 | **Multi-channel SaaS** productization |

---

*Built by Amit Kumar | AI CarryON | Autonomous YouTube Intelligence System*
