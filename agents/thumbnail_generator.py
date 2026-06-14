# agents/thumbnail_generator.py
import os
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from dotenv import load_dotenv

load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
FONT_PATH = "assets/fonts/Arial-Bold.ttf"

def get_thumbnail_image(topic):
    import re

    # Clean topic - remove hashtags and special chars, keep plain words
    clean_topic = re.sub(r"#\S+", "", topic)
    clean_topic = re.sub(r"[^a-zA-Z0-9\s]", "", clean_topic).strip()
    if not clean_topic:
        clean_topic = "technology"

    try:
        headers = {"Authorization": PEXELS_API_KEY}
        url = f"https://api.pexels.com/v1/search?query={clean_topic}&orientation=portrait&per_page=1"
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        if not data.get("photos"):
            return None
        image_url = data["photos"][0]["src"]["portrait"]
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

    # Background
    bg_path = get_thumbnail_image(topic)
    if bg_path:
        bg = Image.open(bg_path).convert("RGB")
        bg = bg.resize((1080, 1920))
        bg = bg.filter(ImageFilter.GaussianBlur(radius=4))
        bg = ImageEnhance.Brightness(bg).enhance(0.35)
    else:
        bg = Image.new("RGB", (1080, 1920), color=(10, 10, 20))

    # Fast dark overlay
    overlay = Image.new("RGBA", (1080, 1920), (0, 0, 0, 150))
    bg.paste(Image.new("RGB", (1080, 1920), (0, 0, 0)), mask=overlay.split()[3])

    draw = ImageDraw.Draw(bg)

    # Fonts
    try:
        font_big = ImageFont.truetype(FONT_PATH, 120)
        font_mid = ImageFont.truetype(FONT_PATH, 60)
        font_small = ImageFont.truetype(FONT_PATH, 42)
    except:
        font_big = ImageFont.load_default()
        font_mid = font_big
        font_small = font_big

    # SHORTS tag top left
    draw.rectangle([50, 80, 300, 150], fill=(255, 69, 0))
    draw.text((70, 90), "⚡ SHORTS", font=font_small, fill="white")

    # Main title - word wrap
    words = title.upper().split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font_big)
        if bbox[2] > 980:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)

    total_height = len(lines) * 130
    y_start = (1920 - total_height) // 2 - 100

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_big)
        x = (1080 - bbox[2]) // 2
        # Orange glow
        for ox, oy in [(4,4),(-4,4),(4,-4),(-4,-4)]:
            draw.text((x+ox, y_start+oy), line, font=font_big, fill=(255, 100, 0))
        # White text
        draw.text((x, y_start), line, font=font_big, fill="white")
        y_start += 135

    # Subtitle
    subtitle = "Watch till the end 🔥"
    bbox = draw.textbbox((0, 0), subtitle, font=font_mid)
    x = (1080 - bbox[2]) // 2
    draw.text((x, y_start + 30), subtitle, font=font_mid, fill=(255, 165, 0))

    # Bottom bar
    draw.rectangle([0, 1820, 1080, 1920], fill=(255, 69, 0))
    bottom_text = "FOLLOW FOR MORE AI CONTENT"
    bbox = draw.textbbox((0, 0), bottom_text, font=font_small)
    x = (1080 - bbox[2]) // 2
    draw.text((x, 1840), bottom_text, font=font_small, fill="white")

    bg.save(output_path, quality=95)
    return output_path
