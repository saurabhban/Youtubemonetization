"""
Thumbnail Generator — creates a professional 1280×720 YouTube thumbnail using Pillow.
Design: dark gradient background, bold title, accent bar, channel branding.
No external APIs needed — runs fully offline.
"""
import os
import textwrap
import logging
from PIL import Image, ImageDraw, ImageFont, ImageFilter

logger = logging.getLogger(__name__)

THUMB_W, THUMB_H = 1280, 720
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(BASE_DIR, "assets", "fonts")
THUMB_DIR = os.path.join(BASE_DIR, "output", "thumbnails")
os.makedirs(THUMB_DIR, exist_ok=True)
os.makedirs(FONT_DIR, exist_ok=True)

# Brand palette for CloudSignalHQ
PALETTE = {
    "bg_top":    (10, 14, 30),      # deep navy
    "bg_bottom": (5, 7, 18),        # near-black
    "accent":    (0, 120, 255),     # electric blue
    "accent2":   (80, 200, 255),    # sky blue
    "gold":      (255, 200, 0),
    "white":     (255, 255, 255),
    "gray":      (160, 170, 190),
    "dark_bar":  (0, 0, 0, 180),
}

# Niche-specific accent colors
NICHE_COLORS = {
    "AI & Technology India": ((0, 120, 255), (80, 200, 255)),
    "Personal Finance India": ((255, 107, 0), (255, 200, 0)),
    "Government Jobs India":  ((0, 160, 80),  (100, 220, 140)),
    "Health & Wellness India": ((180, 60, 200), (240, 120, 255)),
}


def _get_font(size: int, bold: bool = True):
    candidates = []
    if bold:
        candidates += [
            os.path.join(FONT_DIR, "NotoSans-Bold.ttf"),
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    else:
        candidates += [
            os.path.join(FONT_DIR, "NotoSans-Bold.ttf"),
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _text_size(draw, text, font):
    try:
        bb = draw.textbbox((0, 0), text, font=font)
        return bb[2] - bb[0], bb[3] - bb[1]
    except AttributeError:
        return draw.textsize(text, font=font)


def _gradient_bg(img: Image.Image, top: tuple, bottom: tuple):
    """Fill image with a vertical gradient."""
    draw = ImageDraw.Draw(img)
    for y in range(THUMB_H):
        t = y / THUMB_H
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        draw.line([(0, y), (THUMB_W, y)], fill=(r, g, b))


def _draw_grid_lines(draw, accent):
    """Subtle perspective grid lines for tech feel."""
    vanish_x, vanish_y = THUMB_W // 2, THUMB_H // 2
    line_color = (*accent, 18)
    # Horizontal
    for y in range(0, THUMB_H, 60):
        draw.line([(0, y), (THUMB_W, y)], fill=line_color, width=1)
    # Perspective verticals from vanishing point
    for x in range(0, THUMB_W + 1, 80):
        draw.line([(vanish_x, vanish_y), (x, THUMB_H)], fill=line_color, width=1)


def _draw_accent_bar(draw, accent1, accent2, y_pos, height=6):
    """Horizontal gradient accent bar."""
    for x in range(THUMB_W):
        t = x / THUMB_W
        r = int(accent1[0] + (accent2[0] - accent1[0]) * t)
        g = int(accent1[1] + (accent2[1] - accent1[1]) * t)
        b = int(accent1[2] + (accent2[2] - accent1[2]) * t)
        draw.line([(x, y_pos), (x, y_pos + height)], fill=(r, g, b))


def _draw_glow_circle(img: Image.Image, cx: int, cy: int, radius: int, color: tuple):
    """Soft glow circle effect."""
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r in range(radius, 0, -1):
        alpha = int(40 * (r / radius) ** 2)
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*color, alpha))
    img.paste(Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB"),
              (0, 0))


def _wrap_title(title: str, max_chars_per_line: int = 22, max_lines: int = 3) -> list:
    """Wrap title into short lines for large display."""
    words = title.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if len(test) <= max_chars_per_line:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
        if len(lines) >= max_lines - 1 and cur:
            break
    if cur:
        lines.append(cur)
    return lines[:max_lines]


def generate_thumbnail(
    title: str,
    thumbnail_text: str,
    thumbnail_subtitle: str,
    channel_name: str,
    niche: str,
    video_id: str,
    tags: list = None,
) -> str:
    """
    Generate a 1280×720 YouTube thumbnail and save it as JPEG.
    Returns path to the thumbnail file.
    """
    accent1, accent2 = NICHE_COLORS.get(niche, ((0, 120, 255), (80, 200, 255)))

    # ── Base image ──────────────────────────────────────────────
    img = Image.new("RGB", (THUMB_W, THUMB_H))
    _gradient_bg(img, PALETTE["bg_top"], PALETTE["bg_bottom"])

    # Grid overlay
    overlay = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 0))
    _draw_grid_lines(ImageDraw.Draw(overlay), accent1)
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    # Glow effects
    _draw_glow_circle(img, int(THUMB_W * 0.75), int(THUMB_H * 0.3), 280, accent1)
    _draw_glow_circle(img, int(THUMB_W * 0.15), int(THUMB_H * 0.7), 200, accent2)

    draw = ImageDraw.Draw(img)

    # ── Top accent bar ───────────────────────────────────────────
    _draw_accent_bar(draw, accent1, accent2, 0, height=5)

    # ── BIG punch text (thumbnail_text) ─────────────────────────
    punch = (thumbnail_text or "").upper()[:30]
    if punch:
        font_punch = _get_font(110)
        pw, ph = _text_size(draw, punch, font_punch)
        # semi-transparent slab behind punch text
        pad = 16
        slab = Image.new("RGBA", (pw + pad * 2, ph + pad), (0, 0, 0, 140))
        img.paste(Image.alpha_composite(
            Image.new("RGBA", img.size, (0, 0, 0, 0)),
            Image.new("RGBA", img.size, (0, 0, 0, 0))
        ).convert("RGB"), (0, 0))  # noop — just draw directly
        draw.text((60 - pad, 60), punch, font=font_punch, fill=(*accent2, 255))

    # ── Subtitle text ────────────────────────────────────────────
    sub = (thumbnail_subtitle or "").upper()[:40]
    if sub:
        font_sub = _get_font(42)
        sw, sh = _text_size(draw, sub, font_sub)
        draw.text((64, 60 + 120), sub, font=font_sub, fill=(*PALETTE["gray"], 255))

    # ── Main title (wrapped) ─────────────────────────────────────
    lines = _wrap_title(title, max_chars_per_line=20, max_lines=3)
    font_title = _get_font(82)
    y = 270
    for line in lines:
        lw, lh = _text_size(draw, line, font_title)
        # Dark shadow
        draw.text((64 + 3, y + 3), line, font=font_title, fill=(0, 0, 0, 180))
        draw.text((64, y), line, font=font_title, fill=PALETTE["white"])
        y += lh + 12

    # ── Bottom bar ───────────────────────────────────────────────
    bar_y = THUMB_H - 72
    bar_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(bar_overlay).rectangle(
        [(0, bar_y), (THUMB_W, THUMB_H)], fill=(0, 0, 0, 200)
    )
    img = Image.alpha_composite(img.convert("RGBA"), bar_overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Accent line above bar
    _draw_accent_bar(draw, accent1, accent2, bar_y, height=3)

    # Channel name in bar
    font_ch = _get_font(34)
    draw.text((64, bar_y + 18), f"☁ {channel_name}", font=font_ch, fill=(*accent2, 255))

    # Tags preview (right side of bar)
    if tags:
        tag_str = "  #" + "  #".join(t.replace(" ", "") for t in tags[:4])
        font_tag = _get_font(24, bold=False)
        tw, _ = _text_size(draw, tag_str, font_tag)
        draw.text((THUMB_W - tw - 40, bar_y + 24), tag_str,
                  font=font_tag, fill=(*PALETTE["gray"], 200))

    # ── Bottom accent bar ─────────────────────────────────────────
    _draw_accent_bar(draw, accent2, accent1, THUMB_H - 5, height=5)

    # ── Save ──────────────────────────────────────────────────────
    out_path = os.path.join(THUMB_DIR, f"{video_id}_thumb.jpg")
    img.save(out_path, "JPEG", quality=95, optimize=True)
    logger.info(f"Thumbnail saved: {out_path}")
    return out_path
