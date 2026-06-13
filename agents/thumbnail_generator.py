# agents/thumbnail_generator.py
import os
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from dotenv import load_dotenv

load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
FONT_PATH = "assets/fonts/Arial-Bold.ttf"


def get_thumbnail_image(topic):
    """Fetch a relevant image from Pexels for the thumbnail"""
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/v1/search?query={topic}&orientation=landscape&per_page=1"

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()

    if not data.get("photos"):
        return None

    image_url = data["photos"][0]["src"]["landscape"]
    img_response = requests.get(image_url, timeout=30)
    img_response.raise_for_status()

    os.makedirs("assets/thumbnails", exist_ok=True)
    path = "assets/thumbnails/bg.jpg"
    with open(path, "wb") as f:
        f.write(img_response.content)

    return path


def generate_thumbnail(title, topic):
    os.makedirs("output", exist_ok=True)
    output_path = "output/thumbnail.jpg"

    # --- Background ---
    bg_path = get_thumbnail_image(topic)

    if bg_path:
        bg = Image.open(bg_path).convert("RGB")
        bg = bg.resize((1280, 720))
        # Darken + blur background
        bg = bg.filter(ImageFilter.GaussianBlur(radius=3))
        bg = ImageEnhance.Brightness(bg).enhance(0.4)
    else:
        bg = Image.new("RGB", (1280, 720), color=(10, 10, 20))

    draw = ImageDraw.Draw(bg)

    # --- Gradient dark overlay ---
    overlay = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    for y in range(720):
        alpha = int(180 * (y / 720))
        for x in range(1280):
            overlay.putpixel((x, y), (0, 0, 0, alpha))
    bg.paste(Image.new("RGB", (1280, 720), (0, 0, 0)),
             mask=overlay.split()[3])

    # --- Fonts ---
    try:
        font_big = ImageFont.truetype(FONT_PATH, 100)
        font_mid = ImageFont.truetype(FONT_PATH, 50)
        font_small = ImageFont.truetype(FONT_PATH, 36)
    except:
        font_big = ImageFont.load_default()
        font_mid = font_big
        font_small = font_big

    # --- Topic tag (top left) ---
    tag_text = "⚡ SHORTS"
    draw.rectangle([40, 40, 220, 95], fill=(255, 69, 0))
    draw.text((55, 48), tag_text, font=font_small, fill="white")

    # --- Main title (center, word wrap) ---
    words = title.upper().split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font_big)
        if bbox[2] > 1150:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)

    total_text_height = len(lines) * 110
    y_start = (720 - total_text_height) // 2 - 30

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_big)
        x = (1280 - bbox[2]) // 2

        # Glow effect (orange shadow)
        for offset in [(3, 3), (-3, 3), (3, -3), (-3, -3)]:
            draw.text((x + offset[0], y_start + offset[1]),
                      line, font=font_big, fill=(255, 100, 0))

        # Main white text
        draw.text((x, y_start), line, font=font_big, fill="white")
        y_start += 115

    # --- Subtitle ---
    subtitle = "Watch till the end 🔥"
    bbox = draw.textbbox((0, 0), subtitle, font=font_mid)
    x = (1280 - bbox[2]) // 2
    draw.text((x, y_start + 20), subtitle, font=font_mid, fill=(255, 165, 0))

    # --- Bottom bar ---
    draw.rectangle([0, 670, 1280, 720], fill=(255, 69, 0))
    bottom_text = "FOLLOW FOR MORE AI CONTENT"
    bbox = draw.textbbox((0, 0), bottom_text, font=font_small)
    x = (1280 - bbox[2]) // 2
    draw.text((x, 678), bottom_text, font=font_small, fill="white")

    bg.save(output_path, quality=95)
    return output_path
