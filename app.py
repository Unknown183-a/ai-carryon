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

st.title("🤖 AI CarryON")
st.markdown("Generate AI-powered YouTube Shorts automatically")

topic = st.text_input(
    "Enter Topic",
    placeholder="What is LangChain?"
)

# Trending topic button
if st.button("🔥 Use Trending Topic Instead"):
    with st.spinner("Fetching trending YouTube topics..."):
        from agents.trending_agent import get_trending_topic
        try:
            trending = get_trending_topic()
            st.success(f"Trending topic selected: **{trending}**")
            topic = trending
        except Exception as e:
            st.error(str(e))

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