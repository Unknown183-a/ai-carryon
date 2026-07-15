with open("pages/1_Dashboard.py", "r") as f:
    content = f.read()

# 1. Add cricket_tab to the tab declaration
old_tabs = 'english_tab, hindi_tab = st.tabs(["🇬🇧 English Channel", "🇮🇳 Hindi Channel"])'
new_tabs = 'english_tab, hindi_tab, cricket_tab = st.tabs(["🇬🇧 English Channel", "🇮🇳 Hindi Channel", "🏏 Cricket Channel"])'

if old_tabs in content:
    content = content.replace(old_tabs, new_tabs)
    print("✅ Patched tab declaration")
else:
    print("⚠️  Could not find exact tabs line — check manually")

# 2. Append the cricket tab block at the end of the file
cricket_block = '''

# ════════════════════════════════════════════════════════════════
# CRICKET CHANNEL (manual upload only — no automated pipeline UI yet)
# ════════════════════════════════════════════════════════════════
with cricket_tab:
    st.title("🏏 AI CarryON - Cricket Channel")
    st.markdown("Manually upload a rendered match recap video to the cricket channel.")
    st.caption("This channel runs its own automated pipeline on Render (trending match → script → video → upload). This tab is a manual override / backup upload path only.")

    st.markdown("---")

    cricket_video_file = st.file_uploader(
        "Upload video file (MP4)",
        type=["mp4"],
        key="cricket_video_upload"
    )

    cricket_title = st.text_input("Title", key="cricket_title_input", placeholder="e.g. India's Stunning Last-Over Chase Against Australia")
    cricket_description = st.text_area("Description", key="cricket_desc_input", height=100, placeholder="Match recap description...")
    cricket_hashtags_raw = st.text_input("Hashtags (space or comma separated)", key="cricket_hashtags_input", placeholder="#Cricket #IPL #Shorts")

    cricket_upload_clicked = st.button("📤 Upload to YouTube — Cricket Channel", type="primary", key="cricket_upload_btn")

    if cricket_upload_clicked:
        if not cricket_video_file:
            st.warning("Please upload a video file first.")
        elif not cricket_title.strip():
            st.warning("Please enter a title.")
        else:
            with st.spinner("📤 Uploading to Cricket YouTube channel..."):
                try:
                    import tempfile
                    import os as _os

                    # Save uploaded file to a temp path — upload_video() expects a filesystem path
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                        tmp.write(cricket_video_file.read())
                        tmp_path = tmp.name

                    hashtags_list = [h for h in cricket_hashtags_raw.replace(",", " ").split() if h.startswith("#")]
                    if not hashtags_list:
                        hashtags_list = ["#Cricket", "#Shorts"]

                    from agents_cricket.upload_agent import upload_video as cricket_upload_fn
                    video_id, video_url = cricket_upload_fn(
                        video_path=tmp_path,
                        title=cricket_title.strip(),
                        description=cricket_description.strip(),
                        hashtags=hashtags_list,
                    )

                    _os.remove(tmp_path)

                    st.success("✅ Uploaded to Cricket channel!")
                    st.balloons()
                    st.markdown(f"**▶️ Watch here:** [{video_url}]({video_url})")

                except Exception as e:
                    st.error(str(e))
'''

content = content.rstrip("\n") + cricket_block + "\n"

with open("pages/1_Dashboard.py", "w") as f:
    f.write(content)

print("✅ Appended cricket tab block")
print("Done — review with: git diff pages/1_Dashboard.py")
