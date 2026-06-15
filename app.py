import streamlit as st
import os

st.set_page_config(
    page_title="AI CarryON",
    page_icon="🤖",
    layout="wide"
)

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
    password = st.text_input("Enter Password", type="password")
    if st.button("Login"):
        if password == os.getenv("APP_PASSWORD", "aicarryon2026"):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Wrong password!")
    st.stop()

# ── Main Tabs ────────────────────────────────────────────────────
english_tab, hindi_tab = st.tabs(["🇬🇧 English Channel", "🇮🇳 Hindi Channel"])

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
            value=st.session_state.get("trending_topic", "")
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

        if st.button("Generate"):
            if not topic.strip():
                st.warning("Please enter a topic.")
                st.stop()
            try:
                with st.spinner("🔍 Researching..."):
                    research_data = research(topic)
                st.subheader("📚 Research")
                st.write(research_data)

                with st.spinner("✍️ Generating Script..."):
                    script = create_script(research_data)
                st.subheader("📝 YouTube Script")
                st.write(script)

                with st.spinner("📈 Generating SEO..."):
                    seo = generate_seo(topic, script)
                st.subheader("📈 SEO")
                st.markdown(f"**Title:** {seo['title']}")
                st.markdown(f"**Description:** {seo['description']}")
                st.markdown(f"**Hashtags:** {seo['hashtags']}")

                with st.spinner("🎯 Generating Thumbnail Text..."):
                    thumbnail_text = generate_thumbnail_text(topic)
                st.subheader("🖼️ Thumbnail Text")
                st.success(thumbnail_text)

                with st.spinner("🖼️ Generating Thumbnail Image..."):
                    thumbnail_image = generate_thumbnail(seo["title"], topic)
                st.subheader("🖼️ Thumbnail Image")
                st.image(thumbnail_image, use_container_width=True)

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
                else:
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

                with st.spinner("🎨 Generating Manim Animation (this takes 2-3 min)..."):
                    manim_video = render_manim_animation(topic, script)
                    if manim_video:
                        st.subheader("🎨 Manim Animation")
                        st.video(manim_video)
                    else:
                        st.warning("Manim animation failed, using background images instead")

                with st.spinner("🎬 Creating Final Video..."):
                    video_file = create_video(manim_path=manim_video if manim_video else None)

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
    hindi_page = st.sidebar.selectbox(
        "📂 Hindi Navigation",
        ["🎬 Video Banao", "📊 Analytics", "🕵️ Trending Spy"],
        key="hindi_nav"
    )

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
            for t in topics:
                with st.container():
                    c1, c2, c3, c4, c5 = st.columns([4, 1, 1, 1, 2])
                    c1.markdown(f"[{t['title']}]({t['url']})")
                    c2.markdown(f"📺 **{t['channel']}**")
                    c3.markdown(f"👁️ {t['views']:,}")
                    c4.markdown(f"👍 {t['likes']:,}")
                    if c5.button("🎬 Ye Video Banao", key=f"hindi_{t['url']}"):
                        st.session_state["hindi_topic"] = t["topic"]
                        st.session_state["hindi_competitor"] = t
                        st.session_state["hindi_go_generate"] = True
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

        hindi_topic = st.text_input(
            "Topic daalo (Hindi ya English mein)",
            placeholder="Artificial Intelligence kya hai?",
            value=st.session_state.get("hindi_topic", ""),
            key="hindi_topic_input"
        )

        if st.button("🔥 Trending Topic Lo (India)", key="hindi_trending_btn"):
            with st.spinner("India ka trending topic fetch ho raha hai..."):
                try:
                    t = hindi_get_trending(region_code="IN")
                    st.session_state["hindi_topic"] = t
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

        if st.session_state.get("hindi_topic"):
            hindi_topic = st.session_state["hindi_topic"]
            st.success(f"Trending topic: **{hindi_topic}**")

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
                        research_data = research(hindi_topic)
                    st.subheader("📚 Research")
                    st.write(research_data)

                    with st.spinner("✍️ Hindi script likh raha hai..."):
                        script = hindi_create_script(research_data)
                    st.subheader("📝 Hindi Script")
                    st.write(script)

                    with st.spinner("📈 Hindi SEO generate ho raha hai..."):
                        competitor_data = st.session_state.get("hindi_competitor", None)
                        seo = hindi_generate_seo(hindi_topic, script, competitor_data=competitor_data)
                    st.subheader("📈 SEO")
                    st.markdown(f"**Title:** {seo['title']}")
                    st.markdown(f"**Description:** {seo['description']}")
                    st.markdown(f"**Hashtags:** {seo['hashtags']}")

                    with st.spinner("🖼️ Thumbnail ban raha hai..."):
                        from agents.thumbnail_generator import generate_thumbnail
                        thumbnail = generate_thumbnail(seo["title"], hindi_topic)
                    st.subheader("🖼️ Thumbnail")
                    st.image(thumbnail, use_container_width=True)

                    with st.spinner("🌆 Background images fetch ho rahi hain..."):
                        from agents.image_agent import generate_backgrounds
                        image_paths, image_errors = generate_backgrounds(hindi_topic, script, num_images=4)
                    if image_errors:
                        for err in image_errors:
                            st.warning(err)
                    if image_paths:
                        st.subheader("🖼️ Background Images")
                        cols = st.columns(len(image_paths))
                        for col, img_path in zip(cols, image_paths):
                            col.image(img_path)
                    else:
                        st.error("Background images nahi bani. Ruko...")
                        st.stop()

                    with st.spinner("🎙️ Hindi awaaz generate ho rahi hai..."):
                        voice = hindi_generate_voice(script)
                    st.subheader("🔊 Hindi Awaaz")
                    st.audio(voice)

                    with st.spinner("💬 Captions ban rahe hain..."):
                        from agents.caption_agent import create_srt
                        caption_file = create_srt(script, voice)
                    st.subheader("📄 Captions")
                    st.code(open(caption_file).read())

                    with st.spinner("🎬 Video ban raha hai..."):
                        from agents.video_agent import create_video
                        video_file = create_video()

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
                        with st.spinner("📤 YouTube par upload ho raha hai..."):
                            from agents_hindi.upload_agent import upload_video as hindi_upload_fn
                            video_id, video_url = hindi_upload_fn(
                                video_path=video_file,
                                title=seo["title"],
                                description=seo["description"],
                                hashtags=seo["hashtags"],
                                thumbnail_path=thumbnail
                            )
                        st.success("✅ YouTube par upload ho gaya!")
                        st.markdown(f"**Yahan dekho:** [{video_url}]({video_url})")
                    else:
                        st.info("Auto-upload OFF hai. Toggle on karo YouTube par upload karne ke liye.")

                except Exception as e:
                    st.error(str(e))
