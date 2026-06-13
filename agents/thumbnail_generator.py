# agents/thumbnail_generator.py
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import glob

# YouTube Shorts thumbnail dimensions (9:16 vertical)
THUMB_WIDTH = 1080
THUMB_HEIGHT = 1920

FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_REGULAR = "/System/Library/Fonts/Supplemental/Arial.ttf"

# Branding colors
GRADIENT_TOP = (10, 10, 20)
GRADIENT_BOTTOM = (25, 8, 50)
ACCENT_COLOR = (255, 50, 50)       # red
TEXT_COLOR = (255, 255, 255)       # white
HIGHLIGHT_COLOR = (255, 220, 0)    # yellow
SHADOW_COLOR = (0, 0, 0)


def create_gradient_background(width, height, color_top, color_bottom):
    base = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(base)
    for y in range(height):
        ratio = y / height
        r = int(color_top[0] + (color_bottom[0] - color_top[0]) * ratio)
        g = int(color_top[1] + (color_bottom[1] - color_top[1]) * ratio)
        b = int(color_top[2] + (color_bottom[2] - color_top[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return base


def add_background_image(width, height, bg_image_path):
    """Blend background image with dark gradient overlay"""
    try:
        bg = Image.open(bg_image_path).convert("RGB")

        # Crop to 9:16 ratio
        orig_w, orig_h = bg.size
        target_ratio = width / height
        orig_ratio = orig_w / orig_h

        if orig_ratio > target_ratio:
            new_w = int(orig_h * target_ratio)
            left = (orig_w - new_w) // 2
            bg = bg.crop((left, 0, left + new_w, orig_h))
        else:
            new_h = int(orig_w / target_ratio)
            top = (orig_h - new_h) // 2
            bg = bg.crop((0, top, orig_w, top + new_h))

        bg = bg.resize((width, height), Image.LANCZOS)

        # Enhance contrast and saturation
        bg = ImageEnhance.Contrast(bg).enhance(1.3)
        bg = ImageEnhance.Color(bg).enhance(1.4)

        # Dark gradient overlay (transparent at top, dark at bottom)
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)

        for y in range(height):
            ratio = y / height
            # More transparent at top, darker at bottom
            alpha = int(180 + 60 * ratio)
            overlay_draw.line(
                [(0, y), (width, y)],
                fill=(0, 0, 10, alpha)
            )

        bg = bg.convert("RGBA")
        bg = Image.alpha_composite(bg, overlay)
        return bg.convert("RGB")

    except Exception as e:
        print(f"Background image failed: {e}")
        return create_gradient_background(width, height,
                                          GRADIENT_TOP, GRADIENT_BOTTOM)


def draw_text_with_glow(draw, pos, text, font, 
                         text_color, glow_color=(0, 0, 0),
                         glow_radius=3):
    """Draw text with shadow/glow for readability"""
    x, y = pos
    # Draw shadow multiple times for glow effect
    for dx in range(-glow_radius, glow_radius + 1):
        for dy in range(-glow_radius, glow_radius + 1):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text,
                          font=font, fill=glow_color)
    # Draw main text
    draw.text((x, y), text, font=font, fill=text_color)


def wrap_text(text, font, max_width, draw):
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]

    if current_line:
        lines.append(" ".join(current_line))

    return lines


def generate_thumbnail(title, topic, output_path="output/thumbnail.jpg"):
    os.makedirs("output", exist_ok=True)

    # 1. Get background image
    bg_images = []
    bg_folder = "assets/backgrounds"
    if os.path.isdir(bg_folder):
        for ext in ("*.jpg", "*.jpeg", "*.png"):
            found = glob.glob(os.path.join(bg_folder, ext))
            bg_images.extend(
                [f for f in found if "_shorts" not in f]
            )
    bg_images.sort()

    if bg_images:
        base = add_background_image(THUMB_WIDTH, THUMB_HEIGHT, bg_images[0])
    else:
        base = create_gradient_background(
            THUMB_WIDTH, THUMB_HEIGHT, GRADIENT_TOP, GRADIENT_BOTTOM
        )

    draw = ImageDraw.Draw(base)

    # 2. Load fonts — larger sizes for 1080x1920
    try:
        font_huge = ImageFont.truetype(FONT_BOLD, 140)
        font_big = ImageFont.truetype(FONT_BOLD, 110)
        font_mid = ImageFont.truetype(FONT_BOLD, 70)
        font_small = ImageFont.truetype(FONT_REGULAR, 55)
        font_tag = ImageFont.truetype(FONT_REGULAR, 50)
    except Exception:
        font_huge = ImageFont.load_default()
        font_big = font_huge
        font_mid = font_huge
        font_small = font_huge
        font_tag = font_huge

    # 3. Top branding bar
    draw.rectangle([0, 0, THUMB_WIDTH, 110], fill=(0, 0, 0, 180))
    draw_text_with_glow(
        draw, (50, 25),
        "🤖 AI CarryON",
        font_small, ACCENT_COLOR
    )

    # 4. Accent bar (left side)
    draw.rectangle([50, 200, 70, 650], fill=ACCENT_COLOR)

    # 5. Main title text
    title_upper = title.upper()
    max_text_width = THUMB_WIDTH - 160
    lines = wrap_text(title_upper, font_big, max_text_width, draw)
    lines = lines[:4]  # max 4 lines

    y_text = 210
    for i, line in enumerate(lines):
        color = HIGHLIGHT_COLOR if i == 0 else TEXT_COLOR
        draw_text_with_glow(
            draw, (90, y_text),
            line, font_big,
            text_color=color,
            glow_color=(0, 0, 0),
            glow_radius=4
        )
        bbox = draw.textbbox((0, 0), line, font=font_big)
        line_height = bbox[3] - bbox[1]
        y_text += line_height + 20

    # 6. Divider line
    draw.rectangle(
        [50, y_text + 20, THUMB_WIDTH - 50, y_text + 25],
        fill=ACCENT_COLOR
    )

    # 7. Bottom section — topic tag + Shorts badge
    bottom_y = THUMB_HEIGHT - 180

    # Dark bottom bar
    draw.rectangle(
        [0, bottom_y - 20, THUMB_WIDTH, THUMB_HEIGHT],
        fill=(0, 0, 0)
    )

    # Topic hashtag
    tag_text = f"#{topic.replace(' ', '').replace('?', '')[:25]}"
    draw_text_with_glow(
        draw, (55, bottom_y + 10),
        tag_text, font_tag,
        text_color=ACCENT_COLOR
    )

    # SHORTS badge
    badge_text = "▶ SHORTS"
    bbox = draw.textbbox((0, 0), badge_text, font=font_mid)
    badge_w = bbox[2] - bbox[0]
    badge_h = bbox[3] - bbox[1]
    badge_x = THUMB_WIDTH - badge_w - 80
    badge_y = bottom_y + 5

    # Badge background
    draw.rectangle(
        [badge_x - 20, badge_y - 10,
         badge_x + badge_w + 20, badge_y + badge_h + 10],
        fill=ACCENT_COLOR
    )
    draw.text((badge_x, badge_y), badge_text, font=font_mid, fill=TEXT_COLOR)

    # 8. Save high quality
    base.save(output_path, "JPEG", quality=98)
    print(f"Thumbnail saved: {output_path} ({THUMB_WIDTH}x{THUMB_HEIGHT})")
    return output_path