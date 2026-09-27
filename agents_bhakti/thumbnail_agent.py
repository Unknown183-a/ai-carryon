# agents_bhakti/thumbnail_agent.py
"""
Thumbnail generation for the Bhakti channel.

Reuses the same PIL text-overlay technique as agents/thumbnail_generator.py,
but with a devotional-appropriate Pexels search (temples/diyas/aarti/rivers)
instead of that module's tech-biased "{topic} person using" query.
"""

import os
import re
import random
import requests
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from dotenv import load_dotenv

from agents.video_agent import _strip_emoji

load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
FONT_PATH = "assets/fonts/Arial-Bold.ttf"

DEVOTIONAL_SEARCH_TERMS = [
    "hindu temple sunrise", "diya oil lamp temple", "aarti flame incense",
    "temple bells", "ganges river ghat", "marigold garland temple",
]


def _devotional_query(topic):
    clean_topic = re.sub(r"#\S+", "", topic)
    clean_topic = re.sub(r"[^a-zA-Z0-9\s]", "", clean_topic).strip()

    # Devotional topics are mythological/story-based (deity names, prasang
    # descriptions) which rarely match real stock photos directly, so bias
    # toward generic temple/ritual imagery instead of the literal topic text.
    lowered = clean_topic.lower()
    for deity, term in [
        ("hanuman", "hanuman temple statue"),
        ("ram", "ram temple"),
        ("krishna", "krishna temple flute"),
        ("shiv", "shiva temple"),
        ("durga", "durga temple"),
        ("ganesh", "ganesh temple"),
        ("mandir", "hindu temple"),
        ("mantra", "meditation temple incense"),
        ("vrat", "hindu temple puja"),
    ]:
        if deity in lowered:
            return term
    return random.choice(DEVOTIONAL_SEARCH_TERMS)


def get_thumbnail_image(topic):
    search_query = _devotional_query(topic)
    try:
        headers = {"Authorization": PEXELS_API_KEY}
        url = f"https://api.pexels.com/v1/search?query={search_query}&orientation=portrait&per_page=10"
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        photos = data.get("photos", [])

        if not photos:
            url = "https://api.pexels.com/v1/search?query=hindu temple&orientation=portrait&per_page=10"
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
        path = "assets/thumbnails/bg_bhakti.jpg"
        with open(path, "wb") as f:
            f.write(img_response.content)
        return path
    except Exception as e:
        print(f"Bhakti thumbnail image fetch failed: {e}")
        return None


def generate_thumbnail(title, topic):
    os.makedirs("output", exist_ok=True)
    output_path = "output/thumbnail.jpg"

    bg_path = get_thumbnail_image(topic)
    if bg_path:
        bg = Image.open(bg_path).convert("RGB")
        bg = bg.resize((1080, 1920))
        bg = ImageEnhance.Contrast(bg).enhance(1.1)
        bg = ImageEnhance.Color(bg).enhance(1.2)  # slightly warmer/richer for devotional gold tones
        bg = ImageEnhance.Brightness(bg).enhance(0.9)
    else:
        bg = Image.new("RGB", (1080, 1920), color=(30, 15, 5))

    draw = ImageDraw.Draw(bg)

    try:
        font_caption = ImageFont.truetype(FONT_PATH, 68)
    except Exception:
        font_caption = ImageFont.load_default()

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
    lines = lines[:3]

    line_height = 82
    total_height = len(lines) * line_height
    y_start = 1450 - total_height

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_caption)
        text_w = bbox[2] - bbox[0]
        x = (1080 - text_w) // 2
        for ox, oy in [(-3, -3), (3, -3), (-3, 3), (3, 3), (-3, 0), (3, 0), (0, -3), (0, 3)]:
            draw.text((x + ox, y_start + oy), line, font=font_caption, fill=(0, 0, 0))
        # Warm saffron/gold caption color, matching devotional aesthetics
        draw.text((x, y_start), line, font=font_caption, fill=(255, 170, 20))
        y_start += line_height

    bg.save(output_path, quality=95)
    return output_path
