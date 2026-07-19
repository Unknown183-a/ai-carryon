import streamlit as st
import os
import glob

st.set_page_config(
    page_title="AI CarryON",
    page_icon="🤖",
    layout="wide"
)

from agents.dashboard_sync import sync_all_channel_data
_sync_status = sync_all_channel_data()


st.markdown("""
<style>
/* ── Base ── */
[data-testid="stAppViewContainer"] { background: #0a0a0f; }
[data-testid="stSidebar"] { background: #0f0f1a; border-right: 1px solid #1e1e2e; }
section.main > div { padding-top: 1.5rem; }

/* ── Typography ── */
h1, h2, h3 { color: #e2e8f0 !important; font-family: 'Inter', sans-serif; letter-spacing: -0.5px; }
p, label, .stMarkdown { color: #94a3b8 !important; }

/* ── Tabs ── */
[data-testid="stTabs"] button {
    color: #64748b !important;
    font-weight: 600;
    border-bottom: 2px solid transparent;
    padding: 0.5rem 1.5rem;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #38bdf8 !important;
    border-bottom: 2px solid #38bdf8 !important;
    background: transparent !important;
}

/* ── Primary button ── */
[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #0ea5e9, #6366f1) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.6rem 2rem !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    letter-spacing: 0.5px !important;
    box-shadow: 0 0 20px rgba(14,165,233,0.3) !important;
    transition: all 0.2s ease !important;
}
[data-testid="stButton"] > button[kind="primary"]:hover {
    box-shadow: 0 0 30px rgba(14,165,233,0.5) !important;
    transform: translateY(-1px) !important;
}

/* ── Secondary buttons ── */
[data-testid="stButton"] > button {
    background: #1e1e2e !important;
    color: #94a3b8 !important;
    border: 1px solid #2d2d3d !important;
    border-radius: 8px !important;
}

/* ── Input ── */
[data-testid="stTextInput"] input {
    background: #1e1e2e !important;
    border: 1px solid #2d2d3d !important;
    color: #e2e8f0 !important;
    border-radius: 8px !important;
    font-size: 1rem !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #38bdf8 !important;
    box-shadow: 0 0 0 2px rgba(56,189,248,0.15) !important;
}

/* ── Radio ── */
[data-testid="stRadio"] label { color: #94a3b8 !important; }
[data-testid="stRadio"] [data-testid="stMarkdownContainer"] p { color: #e2e8f0 !important; }

/* ── Toggle ── */
[data-testid="stToggle"] label { color: #94a3b8 !important; }

/* ── Info / Success / Warning boxes ── */
[data-testid="stAlert"] {
    border-radius: 8px !important;
    border-left-width: 3px !important;
}

/* ── Code blocks (prompts) ── */
[data-testid="stCode"] {
    background: #1e1e2e !important;
    border: 1px solid #2d2d3d !important;
    border-radius: 8px !important;
    white-space: pre-wrap !important;
    word-break: break-word !important;
}
[data-testid="stCode"] code {
    color: #7dd3fc !important;
    font-size: 0.85rem !important;
    line-height: 1.6 !important;
}

/* ── Divider ── */
hr { border-color: #1e1e2e !important; }

/* ── Selectbox ── */
[data-testid="stSelectbox"] > div > div {
    background: #1e1e2e !important;
    border: 1px solid #2d2d3d !important;
    color: #e2e8f0 !important;
    border-radius: 8px !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background: #1e1e2e !important;
    border: 1px dashed #2d2d3d !important;
    border-radius: 8px !important;
    padding: 1rem !important;
}

/* ── Metrics ── */
[data-testid="stMetric"] {
    background: #1e1e2e;
    border: 1px solid #2d2d3d;
    border-radius: 10px;
    padding: 1rem;
}
[data-testid="stMetricValue"] { color: #38bdf8 !important; }

/* ── Spinner ── */
[data-testid="stSpinner"] { color: #38bdf8 !important; }
</style>
""", unsafe_allow_html=True)

def show_analytics():
    st.title("📊 YouTube Analytics Dashboard")
    col_refresh, col_auto, col_last = st.columns([1, 2, 3])
    with col_refresh:
        refresh = st.button("🔄 Refresh Now")
    with col_auto:
        auto_refresh = st.toggle("⏱️ Auto-refresh every 30 min", value=False)
    import time
    if "last_refresh" not in st.session_state:
        st.session_state["last_refresh"] = time.time()
    if auto_refresh:
        elapsed = time.time() - st.session_state["last_refresh"]
        remaining = max(0, 1800 - int(elapsed))
        mins, secs = divmod(remaining, 60)
        with col_last:
            st.caption(f"⏳ Next refresh in: {mins:02d}:{secs:02d}")
        if elapsed >= 1800:
            st.session_state["last_refresh"] = time.time()
            st.rerun()
    if refresh:
        st.session_state["last_refresh"] = time.time()
        st.rerun()
    with st.spinner("Fetching channel data..."):
        from agents.analytics_agent import get_channel_stats, get_recent_videos
        stats = get_channel_stats()
        videos = get_recent_videos(20)
    if auto_refresh:
        import streamlit as _st
        _st.markdown('<meta http-equiv="refresh" content="1800">', unsafe_allow_html=True)
    st.subheader("📡 Channel Overview")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👤 Subscribers", f"{stats['subscribers']:,}")
    col2.metric("👁️ Total Views", f"{stats['total_views']:,}")
    col3.metric("🎬 Videos", f"{stats['video_count']:,}")
    if videos:
        avg_views = sum(v['views'] for v in videos) // len(videos)
        col4.metric("📈 Avg Views", f"{avg_views:,}")
    st.divider()
    if not videos:
        st.info("No videos found.")
        return
    st.subheader("🏆 Top Videos by Views")
    import pandas as pd
    df = pd.DataFrame(videos)
    df['short_title'] = df['title'].str[:30] + "..."
    st.bar_chart(df.set_index('short_title')['views'])
    st.divider()
    st.subheader("📋 All Videos")
    for v in videos:
        with st.container():
            c1, c2, c3, c4, c5 = st.columns([4, 1, 1, 1, 1])
            c1.markdown(f"[{v['title']}]({v['url']})")
            c2.markdown(f"👁️ **{v['views']:,}**")
            c3.markdown(f"👍 {v['likes']:,}")
            c4.markdown(f"💬 {v['comments']:,}")
            c5.markdown(f"📅 {v['published']}")
        st.divider()

# ── Password protection ──────────────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔐 AI CarryON - Login")
    st.info(
        "This panel is password protected — it controls live video generation and "
        "uploads to real YouTube channels using API credentials, so public access isn't allowed."
    )
    password = st.text_input("Enter Password", type="password")
    if st.button("Login"):
        if password == os.getenv("APP_PASSWORD", "aicarryon2026"):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Wrong password!")
    st.stop()

# ── Main Tabs ────────────────────────────────────────────────────
english_tab, hindi_tab, cricket_tab = st.tabs(["🇬🇧 English Channel", "🇮🇳 Hindi Channel", "🏏 Cricket Channel"])

# ════════════════════════════════════════════════════════════════
# ENGLISH CHANNEL
# ════════════════════════════════════════════════════════════════
with english_tab:
    page = st.sidebar.selectbox("📂 Navigation", ["🎬 Generate Video", "📊 Analytics", "🕵️ Trending Spy"])

    if st.session_state.get("go_generate"):
        st.session_state["go_generate"] = False
        page = "🎬 Generate Video"

    if page == "🕵️ Trending Spy":
        st.title("🕵️ Trending Spy")
        st.markdown("Top performing Shorts from leading AI/Tech channels — click to generate your own version!")
        with st.spinner("Fetching trending topics from top channels..."):
            from agents.spy_agent import get_trending_topics
            topics = get_trending_topics()
        if not topics:
            st.warning("No topics found.")
            st.stop()
        for t in topics:
            with st.container():
                c1, c2, c3, c4, c5 = st.columns([4, 1, 1, 1, 2])
                c1.markdown(f"[{t['title']}]({t['url']})")
                c2.markdown(f"📺 **{t['channel']}**")
                c3.markdown(f"👁️ {t['views']:,}")
                c4.markdown(f"👍 {t['likes']:,}")
                if c5.button("🎬 Make This Video", key=t['url']):
                    st.session_state["trending_topic"] = t["topic"]
                    st.session_state["go_generate"] = True
                    st.rerun()
            st.divider()

    elif page == "📊 Analytics":
        show_analytics()

    else:
        # Generate Video page
        from agents.research_agent import research
        from agents.script_agent import create_script
        from agents.seo_agent import generate_seo
        from agents.thumbnail_agent import generate_thumbnail_text
        from agents.thumbnail_generator import generate_thumbnail
        from agents.image_agent import generate_backgrounds
        from agents.voice_agent import generate_voice
        from agents.caption_agent import create_srt
        from agents.video_agent import create_video
        from agents.manim_agent import render_manim_animation
        from agents.upload_agent import upload_video

        st.title("🤖 AI CarryON")
        st.markdown("Generate AI-powered YouTube Shorts automatically")

        topic = st.text_input(
            "Enter Topic",
            placeholder="What is LangChain?",
            value=st.session_state.get("trending_topic", ""),
            key="english_topic_input"
        )

        if st.button("🔥 Use Trending Topic Instead"):
            with st.spinner("Fetching trending topic..."):
                from agents.trending_agent import get_trending_topic
                try:
                    trending = get_trending_topic()
                    st.session_state["trending_topic"] = trending
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

        if "trending_topic" in st.session_state:
            topic = st.session_state["trending_topic"]
            st.success(f"Trending topic: **{topic}**")

        auto_upload = st.toggle("Auto-upload to YouTube after generation", value=False)

        st.markdown("---")
        st.markdown("**🎬 Video Background Mode**")
        video_mode_pre = st.radio(
            "Video Background Mode",
            ["🎥 Flow clips — cinematic AI video (recommended)", "🖼️ Auto image backgrounds — no upload needed"],
            index=0,
            label_visibility="collapsed",
            key="video_mode_radio",
            horizontal=True
        )
        if "Flow clips" in video_mode_pre:
            st.info("📋 After generating, copy the Veo prompts → go to [labs.google/flow](https://labs.google/flow) → generate VIDEO clips → download MP4s → upload them back here")
        else:
            st.info("🖼️ Pexels backgrounds will be generated automatically — no upload needed")
        st.markdown("---")

        col_gen, col_clear = st.columns([3, 1])
        with col_gen:
            generate_clicked = st.button("Generate", type="primary")
        with col_clear:
            if st.button("🔄 New Topic"):
                for k in ["eng_research","eng_script","eng_seo","eng_prompts","eng_thumb_text","eng_thumb_img","eng_topic_done"]:
                    st.session_state.pop(k, None)
                st.rerun()

        if generate_clicked:
            if not topic.strip():
                st.warning("Please enter a topic.")
                st.stop()
            st.session_state["eng_topic_done"] = topic
            try:
                with st.spinner("🔍 Researching..."):
                    st.session_state["eng_research"] = research(topic)
                with st.spinner("✍️ Generating Script..."):
                    st.session_state["eng_script"] = create_script(st.session_state.get("eng_research", ""))
                with st.spinner("📈 Generating SEO..."):
                    st.session_state["eng_seo"] = generate_seo(topic, st.session_state.get("eng_script", ""))
                with st.spinner("🎬 Generating Flow/Veo Prompts..."):
                    from agents.flow_prompt_agent import generate_flow_prompts
                    st.session_state["eng_prompts"] = generate_flow_prompts(topic, st.session_state.get("eng_script", ""), num_clips=3)
                with st.spinner("🎯 Generating Thumbnail Text..."):
                    st.session_state["eng_thumb_text"] = generate_thumbnail_text(topic)
                with st.spinner("🖼️ Generating Thumbnail Image..."):
                    st.session_state["eng_thumb_img"] = generate_thumbnail(st.session_state.get("eng_seo", {}).get("title", ""), topic)

            except Exception as e:
                st.error(f"Generation failed: {e}")
                st.stop()

        if st.session_state.get("eng_topic_done"):
            research_data = st.session_state.get("eng_research", "")
            script = st.session_state.get("eng_script", "")
            seo = st.session_state.get("eng_seo", {})
            flow_prompts = st.session_state.get("eng_prompts", [])
            thumbnail_text = st.session_state.get("eng_thumb_text", "")
            thumbnail_image = st.session_state.get("eng_thumb_img", "")

            try:
                st.subheader("📚 Research")
                st.write(research_data)
                st.subheader("📝 YouTube Script")
                st.write(script)
                st.subheader("📈 SEO")
                st.markdown(f"**Title:** {seo['title']}")
                st.markdown(f"**Description:** {seo['description']}")
                st.markdown(f"**Hashtags:** {seo['hashtags']}")

                use_flow_clips = "Flow clips" in st.session_state.get("video_mode_radio", "")

                # ── Flow Prompts ──────────────────────────────────
                st.divider()
                st.subheader("🎬 Flow / Veo 3 Cinematic Prompts")
                if use_flow_clips:
                    st.info("📋 **Step 1:** Copy prompt → **Step 2:** Paste in [labs.google/flow](https://labs.google/flow) → Generate VIDEO → **Step 3:** Download MP4 → **Step 4:** Upload below")
                else:
                    st.caption("💡 Reference prompts — auto image mode is active")

                for i, fp in enumerate(flow_prompts):
                    st.markdown(f"**Clip {i+1}**")
                    st.code(fp, language=None)

                if use_flow_clips:
                    st.subheader("📤 Upload Your Flow Clips")
                    uploaded_clips = st.file_uploader(
                        "Upload all MP4 clips here, then scroll down to Generate Video",
                        type=["mp4", "mov"],
                        accept_multiple_files=True,
                        key="flow_clips_uploader"
                    )
                    if uploaded_clips:
                        os.makedirs("assets/flow_clips", exist_ok=True)
                        for f in glob.glob("assets/flow_clips/*.mp4"):
                            os.remove(f)
                        for i, clip in enumerate(uploaded_clips):
                            clip_path = f"assets/flow_clips/clip_{i:02d}.mp4"
                            with open(clip_path, "wb") as f:
                                f.write(clip.read())
                        st.success(f"✅ {len(uploaded_clips)} clip(s) ready — cinematic video mode active")
                    else:
                        if os.path.isdir("assets/flow_clips"):
                            for f in glob.glob("assets/flow_clips/*.mp4"):
                                os.remove(f)
                        st.warning("⬆️ Upload your downloaded Flow clips above to proceed with cinematic mode")
                else:
                    if os.path.isdir("assets/flow_clips"):
                        for f in glob.glob("assets/flow_clips/*.mp4"):
                            os.remove(f)

                st.subheader("🖼️ Thumbnail Text")
                st.success(thumbnail_text)
                st.subheader("🖼️ Thumbnail Image")
                st.image(thumbnail_image, width="stretch")

                # Skip Pexels if Flow clips mode is active
                _flow_clips_exist = bool(glob.glob("assets/flow_clips/*.mp4"))
                _use_flow = "Flow clips" in st.session_state.get("video_mode_radio", "")
                if _use_flow and not _flow_clips_exist:
                    st.warning("⏸️ Flow clips mode is ON — upload your 3 clips above first, then click Generate Video below")
                    st.stop()
                elif _flow_clips_exist:
                    image_paths, image_errors = [], []
                    st.success("🎥 Flow clips detected — using cinematic clips")
                else:
                    with st.spinner("🎨 Generating Background Images..."):
                        image_paths, image_errors = generate_backgrounds(topic, script, num_images=4)
                if image_errors:
                    st.warning("Some images failed to generate:")
                    for err in image_errors:
                        st.text(err)
                if image_paths:
                    st.subheader("🖼️ Generated Backgrounds")
                    cols = st.columns(len(image_paths))
                    for col, img_path in zip(cols, image_paths):
                        col.image(img_path)
                elif not (_use_flow or _flow_clips_exist):
                    st.error("No background images were generated. Cannot continue.")
                    st.stop()

                with st.spinner("🎤 Generating Voiceover..."):
                    voice_file = generate_voice(script)
                st.subheader("🔊 Voiceover")
                st.audio(voice_file)

                with st.spinner("✏️ Generating Captions..."):
                    caption_file = create_srt(script, voice_file)
                st.subheader("📄 Captions")
                st.code(open(caption_file).read())

                if st.button("🎬 Generate Final Video", key="eng_make_video_btn", type="primary"):
                    with st.spinner("🎬 Creating Final Video..."):
                        video_file = create_video(manim_path=None, use_flow_clips=_flow_clips_exist)
                    st.session_state["eng_video_file"] = video_file

                from moviepy import AudioFileClip as AFC
                duration = AFC("output/voice.mp3").duration
                if duration > 60:
                    st.warning(f"⚠️ Video is {duration:.1f}s — over 60s Shorts limit!")
                else:
                    st.success(f"✅ Shorts-ready! Duration: {duration:.1f}s")

                st.subheader("🎥 Generated Video")
                st.video(video_file)
                st.success("✅ Video Created Successfully!")

                with open(video_file, "rb") as f:
                    st.download_button(
                        label="📱 Download for Instagram Reels",
                        data=f,
                        file_name="reel.mp4",
                        mime="video/mp4"
                    )

                st.info("""**📱 Post to Instagram Reels manually:**
1. Download the video above
2. Open Instagram on your phone
3. Tap **+** → **Reel**
4. Select the downloaded video
5. Add caption and post!""")

                if auto_upload:
                    with st.spinner("📤 Uploading to YouTube..."):
                        video_id, video_url = upload_video(
                            video_path=video_file,
                            title=seo["title"],
                            description=seo["description"],
                            hashtags=seo["hashtags"],
                            thumbnail_path=thumbnail_image
                        )
                    st.subheader("📤 YouTube Upload")
                    st.success("Uploaded successfully!")
                    st.markdown(f"**Watch here:** [{video_url}]({video_url})")
                else:
                    st.info("Auto-upload is OFF. Toggle it on to upload directly to YouTube.")

            except Exception as e:
                st.error(str(e))

# ════════════════════════════════════════════════════════════════
# HINDI CHANNEL
# ════════════════════════════════════════════════════════════════
with hindi_tab:
    # Handle redirect from Banao button
    if st.session_state.get("hindi_nav_override"):
        st.session_state["hindi_page_current"] = st.session_state["hindi_nav_override"]
        st.session_state["hindi_nav_override"] = None

    hindi_nav_options = ["🎬 Video Banao", "📊 Analytics", "🕵️ Trending Spy"]
    current_page = st.session_state.get("hindi_page_current", "🎬 Video Banao")
    hindi_nav_default = hindi_nav_options.index(current_page) if current_page in hindi_nav_options else 0

    hindi_page = st.sidebar.selectbox(
        "📂 Hindi Navigation",
        hindi_nav_options,
        index=hindi_nav_default,
        key="hindi_nav"
    )
    # Update current page on manual selection
    st.session_state["hindi_page_current"] = hindi_page

    # ── Trending Spy ─────────────────────────────────────────────
    if hindi_page == "🕵️ Trending Spy":
        st.title("🕵️ Hindi Trending Spy")
        st.markdown("Top Hindi Tech channels ke viral topics — click karo apna version banane ke liye!")

        with st.spinner("Hindi channels ke trending topics fetch ho rahe hain..."):
            try:
                from agents_hindi.spy_agent import get_hindi_trending_topics
                topics = get_hindi_trending_topics()
            except Exception as e:
                st.error(str(e))
                topics = []

        if not topics:
            st.warning("Koi topics nahi mile.")
        else:
            for i, t in enumerate(topics):
                with st.container():
                    c1, c2, c3, c4, c5 = st.columns([4, 1, 1, 1, 2])
                    c1.markdown(f"**{t['title']}**")
                    c2.markdown(f"📺 {t['channel']}")
                    c3.markdown(f"👁️ {t['views']:,}")
                    c4.markdown(f"🔥 {t.get('why_trending', 'Viral')[:30]}")
                    if c5.button("🎬 Banao", key=f"hindi_{i}_{t['topic'][:20]}"):
                        st.session_state["hindi_topic"] = t["topic"]
                        st.session_state["hindi_competitor"] = t
                        st.session_state["hindi_nav_override"] = "🎬 Video Banao"
                        st.rerun()
                st.divider()

    # ── Analytics ────────────────────────────────────────────────
    elif hindi_page == "📊 Analytics":
        st.title("📊 Hindi Channel Analytics")
        st.info("Hindi channel analytics coming soon! Railway deploy ke baad available hoga.")

    # ── Generate Video ───────────────────────────────────────────
    else:
        from agents_hindi.script_agent import create_script as hindi_create_script
        from agents_hindi.seo_agent import generate_seo as hindi_generate_seo
        from agents_hindi.voice_agent import generate_voice as hindi_generate_voice
        from agents_hindi.trending_agent import get_trending_topic as hindi_get_trending

        st.title("🇮🇳 AI CarryON - Hindi Channel")
        st.markdown("Hindi YouTube Shorts ke liye AI-powered video banao!")

        if st.session_state.get("hindi_go_generate"):
            st.session_state["hindi_go_generate"] = False

        # Auto-fill from trending spy or trending button
        prefilled = st.session_state.get("hindi_topic", "")
        hindi_topic = st.text_input(
            "Topic daalo (Hindi ya English mein)",
            placeholder="Artificial Intelligence kya hai?",
            value=prefilled,
            key="hindi_topic_input"
        )

        col_trend, col_clear = st.columns([2, 1])
        with col_trend:
            if st.button("🔥 Trending Topic Lo (India)", key="hindi_trending_btn"):
                with st.spinner("India ka trending topic fetch ho raha hai..."):
                    try:
                        t = hindi_get_trending(region_code="IN")
                        st.session_state["hindi_topic"] = t
                        st.session_state["hindi_competitor"] = None
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
        with col_clear:
            if st.button("🗑️ Clear", key="hindi_clear_btn"):
                st.session_state.pop("hindi_topic", None)
                st.session_state.pop("hindi_competitor", None)
                st.rerun()

        if st.session_state.get("hindi_topic"):
            st.success(f"✅ Topic ready: **{st.session_state['hindi_topic']}**")
            if st.session_state.get("hindi_competitor"):
                st.caption(f"📺 Source: {st.session_state['hindi_competitor'].get('channel', '')} — {st.session_state['hindi_competitor'].get('why_trending', '')}")

        hindi_upload = st.toggle(
            "Auto-upload to Hindi YouTube Channel",
            value=False,
            key="hindi_upload_toggle"
        )

        if st.button("🎬 Hindi Video Banao", key="hindi_generate_btn"):
            if not hindi_topic.strip():
                st.warning("Pehle topic daalo!")
            else:
                try:
                    with st.spinner("🔍 Research ho raha hai..."):
                        from agents.research_agent import research
                        st.session_state["hindi_research"] = research(hindi_topic)
                    with st.spinner("✍️ Hindi script likh raha hai..."):
                        st.session_state["hindi_script"] = hindi_create_script(st.session_state["hindi_research"])
                    with st.spinner("📈 Hindi SEO generate ho raha hai..."):
                        competitor_data = st.session_state.get("hindi_competitor", None)
                        st.session_state["hindi_seo"] = hindi_generate_seo(hindi_topic, st.session_state["hindi_script"], competitor_data=competitor_data)
                    with st.spinner("🖼️ Thumbnail ban raha hai..."):
                        from agents.thumbnail_generator import generate_thumbnail
                        st.session_state["hindi_thumb"] = generate_thumbnail(st.session_state["hindi_seo"]["title"], hindi_topic)
                    with st.spinner("🌆 Background images fetch ho rahi hain..."):
                        from agents.image_agent import generate_backgrounds
                        imgs, errs = generate_backgrounds(hindi_topic, st.session_state["hindi_script"], num_images=4)
                        st.session_state["hindi_images"] = imgs
                        st.session_state["hindi_img_errors"] = errs
                    with st.spinner("🎙️ Hindi awaaz generate ho rahi hai..."):
                        st.session_state["hindi_voice"] = hindi_generate_voice(st.session_state["hindi_script"])
                    with st.spinner("💬 Captions ban rahe hain..."):
                        from agents.caption_agent import create_srt
                        st.session_state["hindi_captions"] = create_srt(st.session_state["hindi_script"], st.session_state["hindi_voice"])
                    with st.spinner("🎬 Flow/Veo Prompts generate ho rahe hain..."):
                        from agents_hindi.flow_prompt_agent import generate_flow_prompts_hindi
                        st.session_state["hindi_prompts"] = generate_flow_prompts_hindi(
                            st.session_state.get("hindi_topic", ""), st.session_state["hindi_script"]
                        )
                    st.session_state["hindi_generated"] = True
                    st.session_state["hindi_video_file"] = None
                except Exception as e:
                    st.error(str(e))
                    import traceback
                    st.code(traceback.format_exc())

        # ── Display all generated content from session state ──
        if st.session_state.get("hindi_generated"):
                research_data = st.session_state.get("hindi_research", "")
                script = st.session_state.get("hindi_script", "")
                seo = st.session_state.get("hindi_seo", {})

                st.subheader("📚 Research")
                st.write(research_data)
                st.subheader("📝 Hindi Script")
                st.write(script)
                st.subheader("📈 SEO")
                st.markdown(f"**Title:** {seo.get('title','')}")
                st.markdown(f"**Description:** {seo.get('description','')}")
                st.markdown(f"**Hashtags:** {seo.get('hashtags','')}")

                st.subheader("🖼️ Thumbnail")
                st.image(st.session_state.get("hindi_thumb"), width="stretch")

                image_paths = st.session_state.get("hindi_images", [])
                image_errors = st.session_state.get("hindi_img_errors", [])
                if image_errors:
                    for err in image_errors:
                        st.warning(err)
                if image_paths:
                    st.subheader("🖼️ Background Images")
                    cols = st.columns(len(image_paths))
                    for col, img_path in zip(cols, image_paths):
                        col.image(img_path)

                voice = st.session_state.get("hindi_voice")
                st.subheader("🔊 Hindi Awaaz")
                if voice:
                    st.audio(voice)

                caption_file = st.session_state.get("hindi_captions")
                st.subheader("📄 Captions")
                if caption_file:
                    st.code(open(caption_file).read())

                hindi_flow_prompts = st.session_state.get("hindi_prompts", [])

                st.subheader("🎬 Flow Video Prompts (Google Flow / Veo 3)")
                st.info("Har prompt copy karo → labs.google/flow mein paste karo → clip download karo → neeche upload karo")

                for i, fp in enumerate(hindi_flow_prompts):
                    st.code(fp, language=None)

                st.divider()
                st.subheader("🎬 Video Mode Chuno")

                col_auto, col_flow = st.columns(2)
                with col_auto:
                    if st.button("🤖 Auto (Pexels images)", key="hindi_mode_auto",
                                 type="primary" if st.session_state.get("hindi_mode") != "flow" else "secondary"):
                        st.session_state["hindi_mode"] = "auto"
                        if os.path.isdir("assets/flow_clips"):
                            for f in glob.glob("assets/flow_clips/*.mp4"):
                                os.remove(f)
                with col_flow:
                    if st.button("🎬 Flow clips use karo", key="hindi_mode_flow",
                                 type="primary" if st.session_state.get("hindi_mode") == "flow" else "secondary"):
                        st.session_state["hindi_mode"] = "flow"

                hindi_mode = st.session_state.get("hindi_mode", "auto")

                if hindi_mode == "flow":
                    st.success("✅ Flow clips mode active hai")
                    st.markdown("**📤 Teeno clips upload karo (MP4):**")
                    hindi_uploaded_clips = st.file_uploader(
                        "Flow clips upload karo",
                        type=["mp4", "mov"],
                        accept_multiple_files=True,
                        key="hindi_flow_clips_uploader"
                    )
                    if hindi_uploaded_clips:
                        os.makedirs("assets/flow_clips", exist_ok=True)
                        for f in glob.glob("assets/flow_clips/*.mp4"):
                            os.remove(f)
                        for i, clip in enumerate(hindi_uploaded_clips):
                            clip_path = f"assets/flow_clips/clip_{i:02d}.mp4"
                            with open(clip_path, "wb") as f:
                                f.write(clip.read())
                        st.success(f"✅ {len(hindi_uploaded_clips)} clip(s) upload ho gaye!")
                    else:
                        st.warning("⚠️ Abhi tak koi clip upload nahi hua — clips upload karo phir Video Banao click karo")
                else:
                    st.info("🤖 Auto mode — Pexels se background images use honge")
                    if os.path.isdir("assets/flow_clips"):
                        for f in glob.glob("assets/flow_clips/*.mp4"):
                            os.remove(f)

                _hindi_clips_exist = bool(glob.glob("assets/flow_clips/*.mp4"))
                _hindi_use_flow = hindi_mode == "flow"

                if _hindi_use_flow and not _hindi_clips_exist:
                    st.warning("⬆️ Pehle clips upload karo, phir Video Banao click karo")
                else:
                    if st.button("🎬 Video Banao (Final)", key="hindi_make_video_btn", type="primary"):
                        with st.spinner("🎬 Video ban raha hai..."):
                            from agents.video_agent import create_video
                            st.session_state["hindi_video_file"] = create_video(use_flow_clips=_hindi_clips_exist)
                            for _f in glob.glob("assets/flow_clips/*.mp4"):
                                os.remove(_f)

                video_file = st.session_state.get("hindi_video_file")
                if video_file:
                    from moviepy import AudioFileClip as AFC
                    duration = AFC("output/voice.mp3").duration
                    if duration > 60:
                        st.warning(f"⚠️ Video {duration:.1f}s ka hai — 60s Shorts limit se zyada!")
                    else:
                        st.success(f"✅ Shorts-ready! Duration: {duration:.1f}s")

                    st.subheader("🎥 Generated Hindi Video")
                    st.video(video_file)
                    st.success("✅ Video ban gaya!")

                    with open(video_file, "rb") as f:
                        st.download_button(
                            label="📱 Instagram Reels ke liye Download karo",
                            data=f,
                            file_name="hindi_reel.mp4",
                            mime="video/mp4",
                            key="hindi_download"
                        )

                    if hindi_upload:
                        with st.spinner("📤 YouTube Hindi channel par upload ho raha hai..."):
                            from agents_hindi.upload_agent import upload_video as hindi_upload_fn
                            video_id, video_url = hindi_upload_fn(
                                video_path=video_file,
                                title=seo.get("title",""),
                                description=seo.get("description",""),
                                hashtags=seo.get("hashtags",""),
                                thumbnail_path=st.session_state.get("hindi_thumb")
                            )
                        st.success("✅ YouTube par upload ho gaya!")
                        st.balloons()
                        st.markdown(f"**▶️ Yahan dekho:** [{video_url}]({video_url})")
                        st.session_state.pop("hindi_topic", None)
                        st.session_state.pop("hindi_competitor", None)
                    else:
                        st.info("💡 Auto-upload OFF hai. Toggle on karo YouTube par seedha upload karne ke liye.")

# ════════════════════════════════════════════════════════════════
# CRICKET CHANNEL (fully automated — same pipeline as Render)
# ════════════════════════════════════════════════════════════════
with cricket_tab:
    cricket_page = st.sidebar.selectbox(
        "📂 Cricket Navigation", ["🎬 Generate + Upload", "📊 Analytics"], key="cricket_nav"
    )

if cricket_page == "📊 Analytics":
    with cricket_tab:
        st.title("📊 Cricket Channel Analytics")
        st.caption("Live stats pulled from the cricket channel's own YouTube credentials, and snapshot history from its own Firestore collections.")

        col_refresh, col_track = st.columns([1, 2])
        with col_refresh:
            if st.button("🔄 Refresh", key="cricket_analytics_refresh"):
                st.rerun()
        with col_track:
            if st.button("📸 Track views now", key="cricket_track_now",
                         help="Manually pull current view counts for cricket videos into Postgres — normally happens automatically ~hourly."):
                with st.spinner("Fetching current view counts from YouTube..."):
                    try:
                        from agents_cricket.view_tracker_agent import track_views_cricket
                        tracked = track_views_cricket()
                        st.success(f"✅ Tracked {len(tracked)} cricket video(s)")
                    except Exception as e:
                        st.error(f"Tracking failed: {e}")

        st.divider()

        with st.spinner("Fetching cricket channel data..."):
            try:
                from agents_cricket.analytics_agent import get_channel_stats, get_recent_videos
                cricket_stats = get_channel_stats()
                cricket_videos = get_recent_videos(20)
                cricket_fetch_error = None
            except Exception as e:
                cricket_stats, cricket_videos = None, []
                cricket_fetch_error = str(e)

        if cricket_fetch_error:
            st.error(f"Couldn't reach the cricket channel's YouTube API: {cricket_fetch_error}")
            st.caption("Check that CRICKET_YOUTUBE_TOKEN_B64 is set for this environment and has youtube.readonly scope.")
        else:
            st.subheader("📡 Channel Overview")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("👤 Subscribers", f"{cricket_stats['subscribers']:,}")
            c2.metric("👁️ Total Views", f"{cricket_stats['total_views']:,}")
            c3.metric("🎬 Videos", f"{cricket_stats['video_count']:,}")
            if cricket_videos:
                avg_views = sum(v["views"] for v in cricket_videos) // len(cricket_videos)
                c4.metric("📈 Avg Views", f"{avg_views:,}")

            st.divider()

            if not cricket_videos:
                st.info("No cricket videos found yet.")
            else:
                st.subheader("🏆 Top Videos by Views")
                import pandas as pd
                df = pd.DataFrame(cricket_videos)
                df["short_title"] = df["title"].str[:30] + "..."
                st.bar_chart(df.set_index("short_title")["views"])

                st.divider()
                st.subheader("📋 All Cricket Videos")
                for v in cricket_videos:
                    with st.container():
                        vc1, vc2, vc3, vc4, vc5 = st.columns([4, 1, 1, 1, 1])
                        vc1.markdown(f"[{v['title']}]({v['url']})")
                        vc2.markdown(f"👁️ **{v['views']:,}**")
                        vc3.markdown(f"👍 {v['likes']:,}")
                        vc4.markdown(f"💬 {v['comments']:,}")
                        vc5.markdown(f"📅 {v['published']}")
                    st.divider()

        st.divider()
        st.subheader("🕐 Match Post History")
        try:
            from agents_cricket.database import db as _cdb, db_init_error as _cdb_err
            if _cdb is None:
                st.info(f"Match history unavailable here: {_cdb_err}")
            else:
                posted_ids = _cdb.get_all_posted_match_ids()
                st.metric("Matches posted (all-time)", len(posted_ids))
        except Exception as e:
            st.info(f"Match history unavailable: {e}")

        st.caption("For hour-by-hour peak upload windows, see the **Peak Hours** and **Schedule** pages in the sidebar — select \"Cricket AI CarryON\" there.")

    st.stop()

with cricket_tab:
    st.title("🏏 AI CarryON - Cricket Channel")
    st.markdown("Finds a live or recently finished Indian cricket match, writes a one-moment highlight recap, generates voice/video, and uploads to YouTube.")

    cricket_auto_upload = st.toggle(
        "Auto-upload to YouTube after generation", value=False, key="cricket_auto_upload_toggle"
    )

    st.markdown("---")
    st.markdown("**Step 1 — Find a live or recently finished match**")

    col_find, col_quick = st.columns(2)
    with col_find:
        cricket_find_clicked = st.button("🔍 Find Recently Finished Matches", key="cricket_find_matches_btn")
    with col_quick:
        cricket_quick_clicked = st.button(
            "🔥 Quick Mode: Auto Generate + Upload (no preview)", key="cricket_auto_generate_btn"
        )

    if cricket_find_clicked:
        with st.spinner("Checking CricAPI for live or recently finished matches..."):
            try:
                from agents_cricket.trending_agent import get_all_topics
                from agents_cricket.database import db as _cdb_find, db_init_error as _cdb_find_err
                cricket_matches = get_all_topics(limit=8)
                cricket_posted_ids = _cdb_find.get_all_posted_match_ids() if _cdb_find else set()
                st.session_state["cricket_matches"] = cricket_matches
                st.session_state["cricket_posted_ids"] = cricket_posted_ids
                if _cdb_find is None:
                    st.warning(f"Couldn't check post history: {_cdb_find_err}")
            except Exception as e:
                st.error(f"Error fetching matches: {e}")
                st.session_state["cricket_matches"] = []

    cricket_matches = st.session_state.get("cricket_matches", [])
    cricket_posted_ids = st.session_state.get("cricket_posted_ids", set())

    if cricket_find_clicked and not cricket_matches:
        st.warning("No live or recently finished Indian T20/ODI/Test matches found right now. Try again later.")

    if cricket_matches:
        cricket_match_options = {}
        for m in cricket_matches:
            m_label = m.get("name") or m.get("title", "")
            m_status = m.get("status") or m.get("topic_type", "")
            label = f"[{m.get('topic_type','?')}] {m_label} — {m_status}"
            if m["id"] in cricket_posted_ids:
                label += " ✅ already posted"
            cricket_match_options[label] = m

        cricket_selected_label = st.selectbox(
            "Pick a match to generate a recap for",
            list(cricket_match_options.keys()),
            key="cricket_match_select",
        )
        cricket_selected_match = cricket_match_options[cricket_selected_label]

        if cricket_selected_match["id"] in cricket_posted_ids:
            st.warning("This match has already been posted to the cricket channel.")

        st.markdown("**Step 2 — Generate the recap**")
        if st.button("✍️ Generate Recap for This Match", type="primary", key="cricket_generate_pipeline_btn"):
            st.session_state["cricket_selected_match"] = cricket_selected_match
            for k in ["cricket_summary", "cricket_script", "cricket_seo", "cricket_images",
                      "cricket_img_errors", "cricket_voice", "cricket_captions",
                      "cricket_video_file", "cricket_match_done"]:
                st.session_state.pop(k, None)
            try:
                with st.spinner("📚 Researching topic..."):
                    from agents_cricket.research_agent import get_summary_for_topic
                    cricket_summary, cricket_structured = get_summary_for_topic(cricket_selected_match)
                if not cricket_summary:
                    st.error("Could not fetch details for this topic. Try another one from the list above.")
                    st.stop()
                st.session_state["cricket_summary"] = cricket_summary
                st.session_state["cricket_structured"] = cricket_structured

                with st.spinner("✍️ Writing recap script..."):
                    from agents_cricket.script_agent import create_cricket_script
                    st.session_state["cricket_script"] = create_cricket_script(
                        cricket_summary, standout_player=cricket_structured.get("standout_player")
                    )

                with st.spinner("📈 Generating SEO..."):
                    from agents_cricket.seo_agent import generate_cricket_seo
                    st.session_state["cricket_seo"] = generate_cricket_seo(
                        cricket_summary, st.session_state["cricket_script"]
                    )

                with st.spinner("🎨 Generating background images..."):
                    from agents_cricket.image_agent import generate_backgrounds
                    img_paths, img_errors = generate_backgrounds(
                        cricket_summary, num_images=4, structured=cricket_structured
                    )
                    st.session_state["cricket_images"] = img_paths
                    st.session_state["cricket_img_errors"] = img_errors

                with st.spinner("🎤 Generating voiceover..."):
                    from agents_cricket.voice_agent import generate_voice
                    st.session_state["cricket_voice"] = generate_voice(
                        st.session_state["cricket_script"], output_path="output/voice.mp3"
                    )

                with st.spinner("✏️ Generating captions..."):
                    from agents.caption_agent import create_srt
                    st.session_state["cricket_captions"] = create_srt(
                        st.session_state["cricket_script"], audio_path="output/voice.mp3"
                    )

                st.session_state["cricket_match_done"] = True
            except Exception as e:
                st.error(f"Generation failed: {e}")

    # ── Display generated pipeline output ──────────────────────────────
    if st.session_state.get("cricket_match_done"):
        cmatch = st.session_state.get("cricket_selected_match", {})
        csummary = st.session_state.get("cricket_summary", "")
        cscript = st.session_state.get("cricket_script", "")
        cseo = st.session_state.get("cricket_seo", {})
        cimages = st.session_state.get("cricket_images", [])
        cimg_errors = st.session_state.get("cricket_img_errors", [])
        cvoice = st.session_state.get("cricket_voice")
        ccaptions = st.session_state.get("cricket_captions")

        st.divider()
        st.subheader(f"🏏 {cmatch.get('name', '')}")
        st.subheader("📚 Match Research")
        st.text(csummary)
        st.subheader("📝 Recap Script")
        st.write(cscript)
        st.subheader("📈 SEO")
        st.markdown(f"**Title:** {cseo.get('title', '')}")
        st.markdown(f"**Description:** {cseo.get('description', '')}")
        st.markdown(f"**Hashtags:** {' '.join(cseo.get('hashtags', []))}")

        if cimg_errors:
            for err in cimg_errors:
                st.warning(err)
        if cimages:
            st.subheader("🖼️ Background Images")
            cols = st.columns(len(cimages))
            for col, img_path in zip(cols, cimages):
                col.image(img_path)

        st.subheader("🔊 Voiceover")
        if cvoice:
            st.audio(cvoice)

        st.subheader("📄 Captions")
        if ccaptions and os.path.exists(ccaptions):
            st.code(open(ccaptions).read())

        st.divider()
        st.markdown("**Step 3 — Render and upload**")
        if st.button("🎬 Generate Final Video", key="cricket_make_video_btn", type="primary"):
            with st.spinner("🎬 Rendering video..."):
                from agents_cricket.video_agent import create_video
                st.session_state["cricket_video_file"] = create_video()

        cvideo_file = st.session_state.get("cricket_video_file")
        if cvideo_file:
            from moviepy import AudioFileClip as AFC
            cduration = AFC("output/voice.mp3").duration
            if cduration > 60:
                st.warning(f"⚠️ Video is {cduration:.1f}s — over 60s Shorts limit!")
            else:
                st.success(f"✅ Shorts-ready! Duration: {cduration:.1f}s")

            st.subheader("🎥 Generated Video")
            st.video(cvideo_file)

            with open(cvideo_file, "rb") as f:
                st.download_button(
                    label="📱 Download for Instagram Reels",
                    data=f,
                    file_name="cricket_reel.mp4",
                    mime="video/mp4",
                    key="cricket_download",
                )

            cricket_already_posted = cmatch.get("id") in st.session_state.get("cricket_posted_ids", set())

            def _do_cricket_upload():
                with st.spinner("📤 Uploading to YouTube..."):
                    try:
                        from agents_cricket.upload_agent import upload_video
                        from agents_cricket.database import db as _cdb_up
                        from datetime import datetime, timezone
                        video_id, video_url = upload_video(
                            cvideo_file, cseo["title"], cseo["description"], cseo["hashtags"]
                        )
                        if _cdb_up:
                            _cdb_up.mark_posted(cmatch["id"], cmatch.get("name", ""))
                            _cdb_up.upsert_video(
                                video_id, cseo["title"],
                                datetime.now(timezone.utc).isoformat(),
                                match_id=cmatch["id"],
                            )
                        st.success("✅ Uploaded to Cricket channel!")
                        st.balloons()
                        st.markdown(f"**▶️ Watch here:** [{video_url}]({video_url})")
                        st.session_state.pop("cricket_matches", None)
                        st.session_state.pop("cricket_match_done", None)
                    except Exception as e:
                        st.error(f"Upload failed: {e}")

            if cricket_already_posted:
                st.warning("This match was already posted — pick a different match above to avoid a duplicate upload.")
            elif cricket_auto_upload:
                _do_cricket_upload()
            else:
                if st.button("📤 Upload to YouTube", key="cricket_manual_upload_btn", type="primary"):
                    _do_cricket_upload()
                st.info("💡 Auto-upload is OFF. Toggle it on above, or click the button to upload manually.")

    st.divider()
    st.markdown("**Or — quick mode**")
    st.caption("Runs the exact same pipeline that fires automatically on Render every ~20 min, with no preview step.")

    if cricket_quick_clicked:
        with st.spinner("Checking for live or recently finished matches..."):
            try:
                from agents_cricket.trending_agent import get_all_topics
                quick_matches = get_all_topics(limit=8)
            except Exception as e:
                st.error(f"Error fetching topics: {e}")
                quick_matches = []

        if not quick_matches:
            st.warning("No live or recently finished Indian T20/ODI/Test matches found right now. Try again later.")
        else:
            st.info(f"Found {len(quick_matches)} finished match(es) — processing the newest one not already posted...")

            with st.spinner("Running full pipeline: research → script → SEO → voice → video → upload... this can take 1-2 minutes"):
                try:
                    from scheduler_cricket import run_cricket_cycle
                    result = run_cricket_cycle()
                except Exception as e:
                    st.error(f"Pipeline error: {e}")
                    result = None

            if result:
                status = result.get("status")
                if status == "uploaded":
                    st.success("✅ Uploaded to Cricket channel!")
                    st.balloons()
                    st.markdown(f"**Title:** {result.get('title','')}")
                    video_url = result.get("video_url", "")
                    st.markdown(f"**▶️ Watch here:** [{video_url}]({video_url})")
                elif status == "no_new_match":
                    st.info("All recent topics have already been posted. Nothing new right now.")
                elif status == "summary_fetch_failed":
                    st.warning(f"Could not fetch details for {result.get('topic','')}. Try again shortly.")
                else:
                    st.info(f"Result: {result}")
