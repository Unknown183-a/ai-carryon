import re

with open("app.py", "r") as f:
    content = f.read()

# 1. Add cricket channel URL next to the other channel URLs
content = content.replace(
    'HINDI_CHANNEL_URL = "https://youtube.com/@AIcarryONHindi"',
    'HINDI_CHANNEL_URL = "https://youtube.com/@AIcarryONHindi"\n'
    'CRICKET_CHANNEL_URL = "https://youtube.com/@AIcarryONCricket"  # update to your real handle once set'
)

# 2. Expand the 3-column channel button row into 4 columns
old_cols = '''col1, col2, col3 = st.columns(3)
with col1:
    st.link_button("🎬 Watch: English Channel", ENGLISH_CHANNEL_URL, use_container_width=True)
with col2:
    st.link_button("🎬 Watch: Hindi Channel", HINDI_CHANNEL_URL, use_container_width=True)
with col3:
    st.link_button("💻 View Source on GitHub", GITHUB_URL, use_container_width=True)'''

new_cols = '''col1, col2, col3, col4 = st.columns(4)
with col1:
    st.link_button("🎬 Watch: English Channel", ENGLISH_CHANNEL_URL, use_container_width=True)
with col2:
    st.link_button("🎬 Watch: Hindi Channel", HINDI_CHANNEL_URL, use_container_width=True)
with col3:
    st.link_button("🏏 Watch: Cricket Channel", CRICKET_CHANNEL_URL, use_container_width=True)
with col4:
    st.link_button("💻 View Source on GitHub", GITHUB_URL, use_container_width=True)'''

if old_cols in content:
    content = content.replace(old_cols, new_cols)
    print("✅ Patched channel buttons (4 columns)")
else:
    print("⚠️  Could not find exact column block — check app.py formatting manually")

# 3. Update the subheader mention of "Two fully independent channels"
content = content.replace(
    "Two fully independent channels (English + Hindi), each running its own",
    "Three fully independent channels (English + Hindi + Cricket), each running its own"
)

with open("app.py", "w") as f:
    f.write(content)

print("Done — review app.py before committing.")
