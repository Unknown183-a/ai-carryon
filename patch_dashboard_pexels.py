"""
Patches pages/1_Dashboard.py so the Streamlit Dashboard uses the same
dynamic Pexels video-clip pipeline that scheduler.py already uses,
instead of the old static-image generator.
"""
import re
import sys

PATH = "pages/1_Dashboard.py"

with open(PATH, "r") as f:
    content = f.read()
original = content

new_content, n1 = re.subn(
    r'([ \t]*)from agents\.image_agent import generate_backgrounds\n',
    r'\1from agents.image_agent import generate_backgrounds\n\1from agents.video_clip_agent import generate_background_clips\n',
    content,
)
content = new_content

english_old = 'image_paths, image_errors = generate_backgrounds(topic, script, num_images=4)'
english_new = (
    'image_paths, image_errors = generate_background_clips(topic, script, num_clips=4)\n'
    '                        if len(image_paths) < 2:\n'
    '                            image_paths, image_errors = generate_backgrounds(topic, script, num_images=4)\n'
    '                            use_pexels = False\n'
    '                        else:\n'
    '                            use_pexels = True'
)
n2 = content.count(english_old)
content = content.replace(english_old, english_new)

hindi_old = 'imgs, errs = generate_backgrounds(hindi_topic, st.session_state["hindi_script"], num_images=4)'
hindi_new = (
    'imgs, errs = generate_background_clips(hindi_topic, st.session_state["hindi_script"], num_clips=4)\n'
    '                        if len(imgs) < 2:\n'
    '                            imgs, errs = generate_backgrounds(hindi_topic, st.session_state["hindi_script"], num_images=4)\n'
    '                            hindi_use_pexels = False\n'
    '                        else:\n'
    '                            hindi_use_pexels = True'
)
n3 = content.count(hindi_old)
content = content.replace(hindi_old, hindi_new)

print(f"Import lines patched: {n1}")
print(f"English call site replaced: {n2}")
print(f"Hindi call site replaced: {n3}")

if content == original:
    print("\nNo changes made — none of the expected patterns were found.")
    sys.exit(1)

if n2 == 0 or n3 == 0:
    print("\nWARNING: a call-site line wasn't found exactly — check formatting.")

with open(PATH, "w") as f:
    f.write(content)

print(f"\nWrote changes to {PATH}")
print("Now run: python3 -m py_compile pages/1_Dashboard.py")
