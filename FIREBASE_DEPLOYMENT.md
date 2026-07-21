# AI CarryON — Firebase Deployment & Improvement Guide

> **Purpose:** This document describes the current architecture, Firebase migration status, and specific improvement recommendations. Give this file to any AI assistant alongside the repo link to get context-aware suggestions.

---

## Current Architecture (as of July 2026)

### Deployment Stack
| Layer | Service | Status |
|---|---|---|
| English Scheduler | Railway (`strong-simplicity` worker) | ✅ Live |
| Hindi Scheduler | Railway (`giving-beauty` worker) | ✅ Live |
| Streamlit Dashboard | Railway (`strong-simplicity` ai-carryon) | ✅ Live |
| Database | SQLite (`output/aicarryon.db`) on Railway | ⚠️ Ephemeral risk |
| Data Backup | GitHub Contents API (legacy `view_history.json`) | ⚠️ Legacy |
| Firebase/Firestore | Partially migrated | 🔄 In Progress |

### Pipeline Flow (Both Channels)
```
Adaptive Hour Check
    → Trending Topic (niche-filtered)
    → Saturation Check
    → Competitor Comparison
    → Research (Groq LLaMA 3.3-70B, Gemini fallback)
    → Script Generation
    → A/B Title Test (3 patterns, LLM scored)
    → SEO (description, hashtags)
    → Thumbnail
    → Background Visuals (Pexels auto / Flow Veo manual)
    → Voiceover (Edge TTS / Sarvam AI Bulbul v2)
    → Captions (word-by-word SRT)
    → Video Render (ffmpeg)
    → YouTube Upload
    → View Snapshot → SQLite
```

---

## Firebase Migration Status

### What's Migrated to Firebase
- [ ] Firestore replacing SQLite for `videos` table
- [ ] Firestore replacing SQLite for `view_snapshots` table
- [ ] Firestore replacing SQLite for `ab_title_tests` table
- [ ] Firestore replacing SQLite for `posted_topics` table
- [ ] Firestore replacing SQLite for `spy_cache` table
- [ ] Firebase Auth for dashboard login (replacing `APP_PASSWORD`)
- [ ] Firebase Hosting for Streamlit alternative

### What Still Needs Migration
- [ ] `database.py` — rewrite connection layer for Firestore
- [ ] `view_tracker_agent.py` — write snapshots to Firestore
- [ ] `ab_title_agent.py` — log title tests to Firestore
- [ ] Dashboard queries — read from Firestore instead of SQLite
- [ ] Scheduler state persistence — store last run time in Firestore

### Firebase Collections Structure (Recommended)
```
/channels/{english|hindi}/
    /videos/{video_id}
        title, topic, upload_time, youtube_id, channel
    /snapshots/{snapshot_id}
        video_id, views, likes, comments, timestamp, channel
    /ab_tests/{test_id}
        topic, patterns[], scores[], winner, channel, timestamp
    /posted_topics/{topic_hash}
        topic, posted_at, channel
    /spy_cache/{cache_id}
        topic, fetched_at, channel
/config/
    /english_scheduler
        last_run, best_hours[], daily_count
    /hindi_scheduler
        last_run, best_hours[], daily_count
```

---

## Improvement Recommendations

### 1. LangChain Integration — Where It Helps Most

#### A. Research Agent (`agents/research_agent.py`)
**Current:** Single LLM call with raw topic string
**Problem:** No memory of what was researched before, no structured retrieval

**Fix with LangChain:**
```python
from langchain.chains import LLMChain
from langchain.memory import ConversationSummaryMemory
from langchain_groq import ChatGroq

# Add memory so research builds on previous context
memory = ConversationSummaryMemory(llm=llm, max_token_limit=500)
research_chain = LLMChain(llm=llm, prompt=research_prompt, memory=memory)
```
**Impact:** Research agent remembers what topics it already covered, avoids repetition, builds richer context per topic.

#### B. Script Agent (`agents/script_agent.py`)
**Current:** One-shot script generation
**Problem:** Hook scoring and rewrite are separate calls with no shared context

**Fix with LangChain:**
```python
from langchain.chains import SequentialChain

# Chain: draft → score hook → rewrite if weak → finalize
script_chain = SequentialChain(
    chains=[draft_chain, hook_scorer_chain, rewrite_chain],
    input_variables=["topic", "research", "competitor_data"],
    output_variables=["final_script", "hook_score"]
)
```
**Impact:** Cleaner pipeline, hook score flows automatically into rewrite decision.

#### C. SEO Agent (`agents/seo_agent.py`)
**Current:** Generates description/hashtags from topic alone
**Problem:** Doesn't use competitor title data or channel performance history

**Fix with LangChain + Firestore retrieval:**
```python
from langchain.tools import Tool
from langchain.agents import initialize_agent

# Tool that fetches top-performing past titles from Firestore
firestore_tool = Tool(
    name="PastTitles",
    func=fetch_top_titles_from_firestore,
    description="Fetches top 5 best-performing titles from this channel's history"
)
seo_agent = initialize_agent([firestore_tool], llm, agent="zero-shot-react-description")
```
**Impact:** SEO uses real channel performance data, not just LLM guess.

---

### 2. LangGraph Integration — Where It Helps Most

#### A. Full Pipeline Orchestration
**Current:** `pipeline.py` is a linear sequential chain with no retry logic or state
**Problem:** If one agent fails, entire pipeline crashes with no recovery

**Fix with LangGraph:**
```python
from langgraph.graph import StateGraph, END

# Define pipeline as a graph with retry edges
graph = StateGraph(PipelineState)
graph.add_node("research", run_research)
graph.add_node("script", run_script)
graph.add_node("title_ab", run_title_ab)
graph.add_node("video", run_video)
graph.add_node("upload", run_upload)

# Add conditional edges — retry on failure, skip on quota exceeded
graph.add_conditional_edges("research", should_retry_or_proceed)
graph.add_conditional_edges("upload", handle_quota_error)
```
**Impact:** Pipeline becomes fault-tolerant. Each node can retry independently. State is preserved in Firestore between runs.

#### B. Adaptive Scheduler as a Graph
**Current:** `adaptive_scheduler.py` uses simple if/else hour checking
**Problem:** No ability to handle multi-step decisions (check hour → check quota → check saturation → decide)

**Fix with LangGraph:**
```python
graph = StateGraph(SchedulerState)
graph.add_node("check_hour", check_peak_hour)
graph.add_node("check_quota", check_youtube_quota)
graph.add_node("check_saturation", check_topic_saturation)
graph.add_node("generate", run_pipeline)
graph.add_node("wait", wait_for_next_window)

graph.add_conditional_edges("check_hour", route_by_hour)
graph.add_conditional_edges("check_quota", route_by_quota)
```
**Impact:** Scheduler becomes a proper decision tree, easier to debug and extend.

---

### 3. RAG (Retrieval Augmented Generation) — Where It Helps Most

#### A. Topic Research with Channel Memory
**Current:** Research agent has no memory of past videos
**Problem:** Makes similar videos on same topics, wastes quota

**RAG Implementation:**
```python
from langchain.vectorstores import Chroma  # or Firestore Vector Search
from langchain.embeddings import GoogleGenerativeAIEmbeddings

# Store all past video scripts as embeddings
vectorstore = Chroma(embedding_function=embeddings)

# Before researching a new topic, check similarity to past videos
def is_topic_too_similar(new_topic):
    similar_docs = vectorstore.similarity_search(new_topic, k=3)
    return any(doc.metadata['similarity_score'] > 0.85 for doc in similar_docs)
```
**Impact:** System never makes near-duplicate videos. Saturation check becomes smarter.

#### B. A/B Title Pattern Learning
**Current:** Title pattern scoring is pure LLM prediction
**Problem:** LLM doesn't know which patterns actually worked on YOUR channel

**RAG Implementation:**
```python
# Store successful titles with their actual view counts in vector DB
# When generating new titles, retrieve similar successful ones as examples

def get_successful_title_examples(topic, channel):
    query = f"successful title for topic: {topic} on channel: {channel}"
    examples = vectorstore.similarity_search(
        query, 
        k=5,
        filter={"views": {"$gt": 1000}, "channel": channel}
    )
    return examples
```
**Impact:** Title generation is grounded in YOUR channel's real performance data, not generic LLM knowledge.

#### C. Script Style Consistency (Channel DNA)
**Current:** Each script is generated from scratch with no brand memory
**Problem:** No consistent tone, style, or personality across videos

**RAG Implementation:**
```python
# Store top-performing scripts as "brand examples"
# Retrieve 2-3 before generating new script

def get_brand_examples(channel):
    return vectorstore.similarity_search(
        "high performing engaging script hook",
        filter={"channel": channel, "views_percentile": {"$gt": 75}},
        k=3
    )

# Pass as few-shot examples to script agent
script_prompt = f"""
Here are examples of our best-performing scripts:
{format_examples(brand_examples)}

Now write a new script for: {topic}
Match the tone, hook style, and pacing of the examples above.
"""
```
**Impact:** Videos develop a consistent channel identity and voice.

---

### 4. Memory System — Where to Add It

#### A. Cross-Session Pipeline Memory (Firestore)
```python
# Save pipeline state to Firestore after each stage
# Resume from last checkpoint if pipeline crashes

class FirestoreCheckpoint:
    def save(self, run_id, stage, state):
        db.collection('pipeline_runs').document(run_id).set({
            'stage': stage,
            'state': state,
            'timestamp': firestore.SERVER_TIMESTAMP
        })
    
    def resume(self, run_id):
        doc = db.collection('pipeline_runs').document(run_id).get()
        return doc.to_dict() if doc.exists else None
```

#### B. Channel Performance Memory (Firestore + LangChain)
```python
from langchain.memory import FirestoreChatMessageHistory

# Each scheduler run gets memory of last 10 runs
memory = FirestoreChatMessageHistory(
    collection_name="scheduler_memory",
    session_id=f"{channel}_scheduler"
)
```

---

### 5. Immediate Quick Wins (No LangChain/LangGraph needed)

| Issue | Fix | Priority |
|---|---|---|
| SQLite wiped on Railway redeploy | Fully migrate to Firestore | 🔴 Critical |
| No failure alerts | Add Telegram bot notification on crash | 🔴 Critical |
| Groq API key hardcoded in `call.js` | Move to env var | 🔴 Critical |
| `APP_PASSWORD` plaintext | Replace with Firebase Auth | 🟡 High |
| No mutex in scheduler | Add Firestore lock document to prevent overlapping runs | 🟡 High |
| AB title scores not validated | Pull actual views after 24h, store in Firestore | 🟡 High |
| `checkpoint.py` never called | Wire into `pipeline.py` properly | 🟡 High |
| Duplicate agent code in `agents/` and `agents_hindi/` | Extract shared base classes | 🟢 Medium |
| `GITHUB_TOKEN` full repo scope | Limit to contents:read only | 🟢 Medium |

---

### 6. Recommended Tech Stack Upgrade Path

```
Current:                          Recommended:
─────────────────────────────     ──────────────────────────────────
SQLite (ephemeral)           →    Firestore (persistent, real-time)
Linear pipeline.py           →    LangGraph state machine
Single LLM calls             →    LangChain chains with memory
No RAG                       →    Firestore Vector Search or Chroma
APP_PASSWORD login           →    Firebase Auth
Manual quota tracking        →    Cloud Functions quota monitor
GitHub as persistence layer  →    Firestore (drop GitHub dependency)
No observability             →    Firebase Crashlytics + Telegram alerts
```

---

### 7. Firebase Cloud Functions — Replace Railway Workers

Instead of always-on Railway workers, use Firebase Cloud Functions + Cloud Scheduler:

```python
# functions/main.py
from firebase_functions import scheduler_fn
from firebase_admin import firestore

@scheduler_fn.on_schedule(schedule="every 5 hours")  # English
def run_english_pipeline(event):
    # Run full pipeline
    # State saved to Firestore automatically
    pass

@scheduler_fn.on_schedule(schedule="every 1 hours")  # Hindi adaptive check
def run_hindi_check(event):
    # Check if current hour is peak hour
    # Run pipeline only if yes
    pass
```

**Benefits:**
- No always-on cost
- Auto-scales
- Built-in retry on failure
- Logs to Firebase Console

---

## Files to Read Before Suggesting Improvements

When giving this repo to an AI assistant, ask them to read these files first:

1. `agents/database.py` — understand the SQLite schema
2. `agents/pipeline.py` — understand the current linear flow
3. `scheduler.py` and `scheduler_hindi.py` — understand scheduling logic
4. `agents/ab_title_agent.py` — understand the title testing system
5. `agents/velocity_agent.py` — understand peak hour calculation
6. `app.py` — understand the Streamlit dashboard

---

## Known Issues (Do Not Suggest These as New Ideas)

- `checkpoint.py` exists but is never called from `pipeline.py` — needs wiring
- `create_video()` uses hardcoded shared output paths — race condition risk with concurrent runs
- `scheduler.py` has no mutex — overlapping runs possible
- Supabase credentials were accidentally exposed twice — rotate before next use
- Instagram automation abandoned — DNS blocking, do not attempt to revive
- Flow/Veo clips persist in `assets/flow_clips/` and get reused — use `use_flow_clips=False` parameter

---

*Last updated: July 2026 | Built by Amit Kumar | Repo: github.com/Unknown183-a/ai-carryon*
