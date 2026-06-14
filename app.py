import streamlit as st
import os

from agents.research_agent import research
from agents.script_agent import create_script
from agents.seo_agent import generate_seo
from agents.thumbnail_agent import generate_thumbnail_text
from agents.thumbnail_generator import generate_thumbnail
from agents.image_agent import generate_backgrounds
from agents.voice_agent import generate_voice
from agents.caption_agent import create_srt
from agents.video_agent import create_video
from agents.upload_agent import upload_video

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

    # Auto-refresh logic
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
        _st.markdown(
            '<meta http-equiv="refresh" content="1800">',
            unsafe_allow_html=True
        )

    # Channel overview
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

    # Top performing videos bar chart
    st.subheader("🏆 Top Videos by Views")
    import pandas as pd
    df = pd.DataFrame(videos)
    df['short_title'] = df['title'].str[:30] + "..."
    st.bar_chart(df.set_index('short_title')['views'])

    st.divider()

    # Video table
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

# Sidebar navigation
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
    st.stop()

if page == "📊 Analytics":
    show_analytics()
    st.stop()


st.title("🤖 AI CarryON")
st.markdown("Generate AI-powered YouTube Shorts automatically")

topic = st.text_input(
    "Enter Topic",
    placeholder="What is LangChain?",
    value=st.session_state.get("trending_topic", "")
)

# Trending topic button
if st.button("🔥 Use Trending Topic Instead"):
    with st.spinner("Fetching trending topic..."):
        from agents.trending_agent import get_trending_topic
        try:
            trending = get_trending_topic()
            st.session_state["trending_topic"] = trending
        except Exception as e:
            st.error(str(e))

if "trending_topic" in st.session_state:
    topic = st.session_state["trending_topic"]
    st.success(f"Trending topic: **{topic}**")

# Upload toggle
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
            image_paths, image_errors = generate_backgrounds(
                topic, script, num_images=4
            )

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

        with st.spinner("🎬 Creating Video..."):
            video_file = create_video()

        # Shorts duration check
        from moviepy import AudioFileClip as AFC
        duration = AFC("output/voice.mp3").duration
        if duration > 60:
            st.warning(f"⚠️ Video is {duration:.1f}s — over 60s Shorts limit!")
        else:
            st.success(f"✅ Shorts-ready! Duration: {duration:.1f}s")

        st.subheader("🎥 Generated Video")
        st.video(video_file)

        st.success("✅ Video Created Successfully!")

        # Download button for Instagram
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

        # YouTube Upload
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




# Page routing
