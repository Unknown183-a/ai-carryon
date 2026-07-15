with open("pages/1_Dashboard.py", "r") as f:
    content = f.read()

marker = "# ════════════════════════════════════════════════════════════════\n# CRICKET CHANNEL"
idx = content.find(marker)

if idx == -1:
    print("⚠️ Could not find cricket block marker — no changes made")
else:
    new_block = '''# ════════════════════════════════════════════════════════════════
# CRICKET CHANNEL (fully automated — same pipeline as Render)
# ════════════════════════════════════════════════════════════════
with cricket_tab:
    st.title("🏏 AI CarryON - Cricket Channel")
    st.markdown("Finds a recently finished match, writes the recap, generates voice/video, and uploads to YouTube — fully automatic.")
    st.caption("This runs the same pipeline that fires automatically on Render every ~20 min. Use this to trigger a cycle manually anytime.")

    st.markdown("---")

    cricket_generate_clicked = st.button(
        "🔥 Find Trending Match & Generate + Upload",
        type="primary",
        key="cricket_auto_generate_btn"
    )

    if cricket_generate_clicked:
        with st.spinner("Checking for recently finished matches..."):
            try:
                from agents_cricket.trending_agent import get_finished_matches
                matches = get_finished_matches(limit=5)
            except Exception as e:
                st.error(f"Error fetching matches: {e}")
                matches = []

        if not matches:
            st.warning("No recently finished T20/ODI/Test matches found right now. Try again later.")
        else:
            st.info(f"Found {len(matches)} finished match(es) — processing the newest one not already posted...")

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
                    st.info("All recently finished matches have already been posted. Nothing new right now.")
                elif status == "scorecard_fetch_failed":
                    st.warning(f"Could not fetch the scorecard for {result.get('match','')}. Try again shortly.")
                else:
                    st.info(f"Result: {result}")
'''
    content = content[:idx].rstrip("\n") + "\n\n" + new_block
    with open("pages/1_Dashboard.py", "w") as f:
        f.write(content)
    print("✅ Replaced cricket tab with fully automated pipeline")
