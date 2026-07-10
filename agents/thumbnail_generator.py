# agents/thumbnail_generator.py
import os
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from agents.video_agent import _strip_emoji
from dotenv import load_dotenv

load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
FONT_PATH = "assets/fonts/Arial-Bold.ttf"


def get_thumbnail_image(topic):
    import re
    import random

    # Clean topic - remove hashtags and special chars, keep plain words
    clean_topic = re.sub(r"#\S+", "", topic)
    clean_topic = re.sub(r"[^a-zA-Z0-9\s]", "", clean_topic).strip()
    if not clean_topic:
        clean_topic = "technology"

    # Bias search toward people reacting/using tech, matching the
    # face-forward, expressive style of top-performing thumbnails —
    # instead of plain product/object shots.
    search_query = f"{clean_topic} person using"

    try:
        headers = {"Authorization": PEXELS_API_KEY}
        url = f"https://api.pexels.com/v1/search?query={search_query}&orientation=portrait&per_page=10"
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        photos = data.get("photos", [])

        # Fallback: if the "person using X" query returns nothing, retry
        # with just the plain topic
        if not photos:
            url = f"https://api.pexels.com/v1/search?query={clean_topic}&orientation=portrait&per_page=10"
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            photos = data.get("photos", [])

        if not photos:
            return None

        chosen = random.choice(photos[:min(6, len(photos))])
        image_url = chosen["src"]["portrait"]

        img_response = requests.get(image_url, timeout=30)
        img_response.raise_for_status()
        os.makedirs("assets/thumbnails", exist_ok=True)
        path = "assets/thumbnails/bg.jpg"
        with open(path, "wb") as f:
            f.write(img_response.content)
        return path
    except Exception as e:
        print(f"Thumbnail image fetch failed: {e}")
        return None


def generate_thumbnail(title, topic):
    os.makedirs("output", exist_ok=True)
    output_path = "output/thumbnail.jpg"

    # Background — keep it bright and visible, matching reference style
    # where the photo itself does most of the work
    bg_path = get_thumbnail_image(topic)
    if bg_path:
        bg = Image.open(bg_path).convert("RGB")
        bg = bg.resize((1080, 1920))
        bg = ImageEnhance.Contrast(bg).enhance(1.1)
        bg = ImageEnhance.Color(bg).enhance(1.15)
        bg = ImageEnhance.Brightness(bg).enhance(0.92)
    else:
        bg = Image.new("RGB", (1080, 1920), color=(10, 10, 20))

    draw = ImageDraw.Draw(bg)

    # Fonts — smaller than before, caption-style rather than a giant
    # headline covering the middle of the frame
    try:
        font_caption = ImageFont.truetype(FONT_PATH, 68)
    except Exception:
        font_caption = ImageFont.load_default()

    # Caption text — short, bold, lower-third placement, matching the
    # reference thumbnails (yellow text, black outline, no background box)
    caption = _strip_emoji(title).upper()
    max_width = 980

    words = caption.split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font_caption)
        if bbox[2] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)

    # Cap at 3 lines max — keep it caption-sized, not a headline block
    lines = lines[:3]

    line_height = 82
    total_height = len(lines) * line_height
    y_start = 1450 - total_height  # anchor higher, clear of YouTube Shorts UI overlay at bottom

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_caption)
        text_w = bbox[2] - bbox[0]
        x = (1080 - text_w) // 2
        # Black outline for legibility over any background
        for ox, oy in [(-3, -3), (3, -3), (-3, 3), (3, 3), (-3, 0), (3, 0), (0, -3), (0, 3)]:
            draw.text((x + ox, y_start + oy), line, font=font_caption, fill=(0, 0, 0))
        # Yellow caption text
        draw.text((x, y_start), line, font=font_caption, fill=(255, 220, 0))
        y_start += line_height

    bg.save(output_path, quality=95)
    return output_path
