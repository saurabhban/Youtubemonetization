"""
Avatar Engine — anime talking-head character overlay for CloudSignalHQ.

Draws a cel-shaded anime mascot using Pillow (no external assets needed).
Generates a talking-head MP4 clip with mouth animation synced to narration timing.
The clip is overlaid in the bottom-left corner of footage scenes.

Character design:
  - Dark indigo hair with blue sheen (tech-vibe)
  - Large blue eyes with triple highlights
  - Warm peach skin, soft blush
  - Simple dark top with electric-blue collar
  - 3 mouth states cycling at ~4 Hz to simulate speech

To use your own anime character image:
  Drop a PNG at assets/avatar/custom_character.png (transparent background).
  The engine will use it automatically with mouth animation overlay.
"""

import os
import math
import shutil
import logging
import subprocess
import tempfile
from PIL import Image, ImageDraw, ImageFilter

logger = logging.getLogger(__name__)

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
AVATAR_DIR  = os.path.join(BASE_DIR, "assets", "avatar")
os.makedirs(AVATAR_DIR, exist_ok=True)

# ── Palette ─────────────────────────────────────────────────────────────────
SKIN        = (255, 214, 170)
SKIN_SHADOW = (240, 185, 140)
HAIR        = (30,  20,  80)     # Deep indigo
HAIR_SHINE  = (70,  60, 160)     # Blue highlight
EYE_WHITE   = (245, 248, 255)
IRIS        = (60,  130, 230)    # Bright blue
IRIS_DARK   = (30,   70, 160)    # Iris shadow
PUPIL       = (15,   10,  35)
MOUTH_IN    = (210,  90,  90)    # Inside mouth
LIP         = (210, 130, 110)    # Lip color
BLUSH       = (255, 170, 155, 90)
OUTLINE     = (30,   20,  50)    # Main outline
EYE_LINE    = (20,   10,  40)
CLOTH_DARK  = (15,   20,  50)    # Top/outfit
COLLAR      = (0,   120, 255)    # Electric blue collar
BG_DARK     = (8,   12,  28)     # Circle background
BORDER_GLOW = (0,   120, 255)
BORDER_CORE = (80,  180, 255)

# Draw at 2× for crisp anti-aliasing, then downscale
_AV   = 300      # Final avatar size (px)
_D    = _AV * 2  # Drawing canvas size


def _o(v): return int(v * 2)   # Scale value to drawing coords
def _e(x, y, rx, ry):          # Ellipse bbox from centre + radii
    return [_o(x - rx), _o(y - ry), _o(x + rx), _o(y + ry)]


# ── Face drawing ─────────────────────────────────────────────────────────────

def _draw_hair_back(draw: ImageDraw.Draw):
    """Back layer of hair (drawn before face)."""
    # Main hair mass — dome shape
    draw.ellipse([_o(48), _o(28), _o(252), _o(210)],
                 fill=HAIR, outline=HAIR)
    # Top dome fill
    draw.rectangle([_o(48), _o(100), _o(252), _o(200)], fill=HAIR)

    # Side strands — left
    left_strand = [
        (_o(58), _o(110)), (_o(30), _o(180)),
        (_o(42), _o(230)), (_o(65), _o(185)), (_o(70), _o(115)),
    ]
    draw.polygon(left_strand, fill=HAIR, outline=HAIR)

    # Side strands — right
    right_strand = [
        (_o(242), _o(110)), (_o(270), _o(180)),
        (_o(258), _o(230)), (_o(235), _o(185)), (_o(230), _o(115)),
    ]
    draw.polygon(right_strand, fill=HAIR, outline=HAIR)

    # Hair shine streaks
    for ox, oy in [(-30, 0), (0, 0), (20, 5)]:
        draw.arc(
            [_o(80 + ox), _o(38 + oy), _o(160 + ox), _o(90 + oy)],
            start=200, end=330,
            fill=HAIR_SHINE, width=_o(4),
        )


def _draw_face(draw: ImageDraw.Draw):
    """Skin-coloured face oval with chin taper."""
    # Main face
    draw.ellipse(_e(150, 165, 90, 110), fill=SKIN, outline=OUTLINE, width=_o(2))
    # Chin softener
    draw.ellipse(_e(150, 220, 55, 65), fill=SKIN, outline=SKIN)

    # Ear hints
    draw.ellipse(_e(63, 165, 14, 18), fill=SKIN, outline=OUTLINE, width=_o(1))
    draw.ellipse(_e(237, 165, 14, 18), fill=SKIN, outline=OUTLINE, width=_o(1))

    # Neck
    draw.rectangle([_o(128), _o(248), _o(172), _o(290)],
                   fill=SKIN, outline=None)

    # Cheek blush — left
    blush_img = Image.new("RGBA", (_D, _D), (0, 0, 0, 0))
    bd = ImageDraw.Draw(blush_img)
    bd.ellipse(_e(105, 195, 26, 14), fill=BLUSH)
    bd.ellipse(_e(195, 195, 26, 14), fill=BLUSH)
    draw._image.paste(blush_img, (0, 0), blush_img)


def _draw_eyes(draw: ImageDraw.Draw):
    """Large anime eyes with iris, pupil, and triple highlight."""
    for cx in [112, 188]:
        # Eye white
        draw.ellipse(_e(cx, 162, 33, 22), fill=EYE_WHITE, outline=EYE_LINE, width=_o(2))

        # Iris (slightly shorter than white — cut by top eyelid)
        draw.ellipse(_e(cx, 166, 22, 20), fill=IRIS, outline=None)

        # Iris shading (darker lower half)
        draw.arc(_e(cx, 170, 22, 18), start=0, end=180, fill=IRIS_DARK, width=_o(12))

        # Pupil
        draw.ellipse(_e(cx, 168, 10, 11), fill=PUPIL, outline=None)

        # Highlights
        draw.ellipse(_e(cx - 8, 158, 6, 6), fill=(255, 255, 255), outline=None)
        draw.ellipse(_e(cx + 9, 163, 4, 4), fill=(220, 235, 255), outline=None)
        draw.ellipse(_e(cx + 3, 175, 2, 2), fill=(200, 220, 255), outline=None)

        # Top eyelid (thick)
        draw.arc(_e(cx, 157, 33, 22), start=195, end=345,
                 fill=EYE_LINE, width=_o(4))

        # Lower lash (thin)
        draw.arc(_e(cx, 167, 33, 20), start=15, end=165,
                 fill=EYE_LINE, width=_o(2))

    # Eyebrows
    for cx, lean in [(112, -1), (188, 1)]:
        pts = [
            (_o(cx - 26 + lean * 4), _o(136)),
            (_o(cx + 24 + lean * 2), _o(132)),
        ]
        draw.line(pts, fill=HAIR, width=_o(5))
        # Inner brow arch
        draw.arc(
            [_o(cx - 26 + lean * 4), _o(128),
             _o(cx + 24 + lean * 2), _o(143)],
            start=195, end=350,
            fill=HAIR, width=_o(3),
        )


def _draw_nose(draw: ImageDraw.Draw):
    """Minimal anime nose — two small dots."""
    draw.ellipse(_e(143, 200, 4, 3), fill=SKIN_SHADOW)
    draw.ellipse(_e(157, 200, 4, 3), fill=SKIN_SHADOW)


def _draw_mouth(draw: ImageDraw.Draw, state: int):
    """
    Mouth animation states:
      0 → closed (gentle smile)
      1 → half-open
      2 → open (speaking)
    """
    cx, cy = 150, 222

    if state == 0:
        # Gentle closed smile
        draw.arc([_o(cx - 20), _o(cy - 8), _o(cx + 20), _o(cy + 10)],
                 start=15, end=165, fill=LIP, width=_o(4))
        # Corner dots
        draw.ellipse(_e(cx - 20, cy + 1, 3, 3), fill=LIP)
        draw.ellipse(_e(cx + 20, cy + 1, 3, 3), fill=LIP)

    elif state == 1:
        # Half-open mouth
        draw.ellipse(_e(cx, cy + 2, 16, 8), fill=MOUTH_IN, outline=LIP, width=_o(2))
        # Upper lip arch
        draw.arc([_o(cx - 16), _o(cy - 6), _o(cx + 16), _o(cy + 8)],
                 start=195, end=345, fill=LIP, width=_o(3))

    else:  # state == 2
        # Open mouth
        draw.ellipse(_e(cx, cy + 3, 22, 13), fill=MOUTH_IN, outline=LIP, width=_o(2))
        # Upper lip
        draw.arc([_o(cx - 22), _o(cy - 8), _o(cx + 22), _o(cy + 10)],
                 start=195, end=345, fill=LIP, width=_o(3))
        # Tongue hint
        draw.ellipse(_e(cx, cy + 10, 10, 5), fill=(230, 120, 120))

    # Mouth corners
    draw.ellipse(_e(cx - 22, cy + 2, 3, 3), fill=LIP)
    draw.ellipse(_e(cx + 22, cy + 2, 3, 3), fill=LIP)


def _draw_hair_front(draw: ImageDraw.Draw):
    """Front hair strands (drawn over face)."""
    # Fringe strands
    fringe_pts = [
        # Centre tuft
        [(_o(135), _o(100)), (_o(150), _o(68)), (_o(165), _o(100))],
        # Left tuft
        [(_o(90), _o(108)), (_o(100), _o(75)), (_o(118), _o(115))],
        # Right tuft
        [(_o(210), _o(108)), (_o(200), _o(75)), (_o(182), _o(115))],
        # Far-left
        [(_o(68), _o(118)), (_o(72), _o(90)), (_o(88), _o(124))],
        # Far-right
        [(_o(232), _o(118)), (_o(228), _o(90)), (_o(212), _o(124))],
    ]
    for pts in fringe_pts:
        draw.polygon(pts, fill=HAIR, outline=HAIR)

    # Hair shine on fringe
    draw.arc([_o(100), _o(72), _o(168), _o(115)],
             start=210, end=330, fill=HAIR_SHINE, width=_o(3))


def _draw_body(draw: ImageDraw.Draw):
    """Simple shoulders + outfit below the face."""
    # Shoulders / top
    shoulder_pts = [
        (_o(40), _o(300)), (_o(75), _o(265)), (_o(115), _o(255)),
        (_o(150), _o(258)),
        (_o(185), _o(255)), (_o(225), _o(265)), (_o(260), _o(300)),
    ]
    draw.polygon(shoulder_pts, fill=CLOTH_DARK, outline=OUTLINE, width=_o(2))

    # Collar
    collar_pts = [
        (_o(130), _o(255)), (_o(150), _o(268)), (_o(170), _o(255)),
        (_o(165), _o(285)), (_o(150), _o(275)), (_o(135), _o(285)),
    ]
    draw.polygon(collar_pts, fill=COLLAR, outline=COLLAR)


def _draw_border_circle(img: Image.Image) -> Image.Image:
    """
    Circular clip with glowing blue border on a dark background.
    Returns a new RGBA image.
    """
    result = Image.new("RGBA", (_D, _D), (0, 0, 0, 0))
    rd     = ImageDraw.Draw(result)

    # Glow ring (soft, outer)
    for r in range(20, 0, -1):
        alpha = int(160 * (r / 20) ** 2)
        rd.ellipse([_D // 2 - _AV // 2 - r + 2, _D // 2 - _AV // 2 - r + 2,
                    _D // 2 + _AV // 2 + r - 2, _D // 2 + _AV // 2 + r - 2],
                   outline=(*BORDER_GLOW, alpha), width=2)

    # Dark background circle
    rd.ellipse([_D // 2 - _AV // 2 + 4, _D // 2 - _AV // 2 + 4,
                _D // 2 + _AV // 2 - 4, _D // 2 + _AV // 2 - 4],
               fill=(*BG_DARK, 255))

    # Paste character inside a circular mask
    char_mask = Image.new("L", (_D, _D), 0)
    ImageDraw.Draw(char_mask).ellipse(
        [_D // 2 - _AV // 2 + 6, _D // 2 - _AV // 2 + 6,
         _D // 2 + _AV // 2 - 6, _D // 2 + _AV // 2 - 6],
        fill=255,
    )
    result.paste(img, (0, 0), char_mask)

    # Hard border ring
    rd.ellipse([_D // 2 - _AV // 2 + 4, _D // 2 - _AV // 2 + 4,
                _D // 2 + _AV // 2 - 4, _D // 2 + _AV // 2 - 4],
               outline=BORDER_CORE, width=_o(4))

    return result


# ── Frame generation ─────────────────────────────────────────────────────────

def _render_frame(mouth_state: int) -> Image.Image:
    """Render one full avatar frame at 2× resolution."""
    img  = Image.new("RGBA", (_D, _D), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Attach the image to draw so blush layer can paste RGBA
    draw._image = img

    _draw_hair_back(draw)
    _draw_face(draw)
    _draw_eyes(draw)
    _draw_nose(draw)
    _draw_mouth(draw, mouth_state)
    _draw_hair_front(draw)
    _draw_body(draw)

    # Downscale 2× → 1× for clean anti-aliasing
    img_sm = img.resize((_D, _D), Image.LANCZOS)  # already _D, but smooth
    framed = _draw_border_circle(img_sm)

    # Final downscale to display size
    return framed.resize((_AV, _AV), Image.LANCZOS)


def build_avatar_frames(force: bool = False) -> dict:
    """
    Pre-render and cache the 3 mouth-state frames.
    Returns {"closed": path, "half": path, "open": path}
    """
    paths = {
        "closed": os.path.join(AVATAR_DIR, "avatar_mouth_0.png"),
        "half":   os.path.join(AVATAR_DIR, "avatar_mouth_1.png"),
        "open":   os.path.join(AVATAR_DIR, "avatar_mouth_2.png"),
    }
    all_exist = all(os.path.exists(p) for p in paths.values())
    if all_exist and not force:
        logger.info("Avatar frames already cached")
        return paths

    logger.info("Rendering avatar frames (one-time)...")
    for state, (key, path) in enumerate(paths.items()):
        frame = _render_frame(state)
        frame.save(path, "PNG")
        logger.info(f"  Saved: {path}")

    return paths


# ── Talking-head video ────────────────────────────────────────────────────────

# Mouth animation sequence: [state, state, ...] repeating at fps
# 4 Hz cycle: 30fps / ~4 = 7-8 frames per state
# Pattern: closed(4) → half(2) → open(3) → half(2) → closed(4) → open(3) ...
MOUTH_SEQ = [0, 0, 0, 0, 1, 1, 2, 2, 2, 1, 1, 0, 0, 0, 0, 2, 2, 2, 1, 1]


def create_talking_avatar_video(
    duration_sec: float,
    output_path: str,
    fps: int = 30,
    custom_png: str = None,
) -> bool:
    """
    Create a talking-head avatar video of given duration.
    Uses pre-rendered frames with mouth cycling to simulate speech.

    Args:
        duration_sec: Length of output video
        output_path:  Path to output MP4
        fps:          Frames per second (should match video FPS)
        custom_png:   Optional path to a user-provided PNG (transparent bg)

    Returns True on success.
    """
    # Check for user-provided custom character
    custom_default = os.path.join(AVATAR_DIR, "custom_character.png")
    if custom_png and os.path.exists(custom_png):
        pass  # use provided path
    elif os.path.exists(custom_default):
        custom_png = custom_default
    else:
        custom_png = None   # use built-in

    # Build / load frames
    if custom_png:
        logger.info(f"Using custom avatar: {custom_png}")
        frames = _load_custom_frames(custom_png)
    else:
        frame_paths = build_avatar_frames()
        frames = {
            k: Image.open(p).convert("RGBA")
            for k, p in frame_paths.items()
        }

    frame_list = [frames["closed"], frames["half"], frames["open"]]

    n_frames = int(duration_sec * fps)
    seq_len  = len(MOUTH_SEQ)

    tmp_dir = tempfile.mkdtemp()
    try:
        frame_dir = os.path.join(tmp_dir, "frames")
        os.makedirs(frame_dir)

        for i in range(n_frames):
            state     = MOUTH_SEQ[i % seq_len]
            frame_img = frame_list[state]
            frame_path = os.path.join(frame_dir, f"f_{i:06d}.png")
            frame_img.save(frame_path)

        # Build video from frames
        silent_path = output_path + "_avsilent.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", os.path.join(frame_dir, "f_%06d.png"),
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-pix_fmt", "yuva420p",
            "-vf", f"fps={fps}",
            silent_path,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            # Try without yuva420p (some builds don't support it)
            cmd2 = [
                "ffmpeg", "-y",
                "-framerate", str(fps),
                "-i", os.path.join(frame_dir, "f_%06d.png"),
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-pix_fmt", "yuv420p",
                "-vf", f"fps={fps}",
                silent_path,
            ]
            r = subprocess.run(cmd2, capture_output=True, text=True)
            if r.returncode != 0:
                logger.error(f"Avatar video encode failed:\n{r.stderr[-500:]}")
                return False

        # Add silent audio track
        cmd_a = [
            "ffmpeg", "-y",
            "-i", silent_path,
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k",
            "-t", str(duration_sec),
            output_path,
        ]
        r2 = subprocess.run(cmd_a, capture_output=True, text=True)
        if r2.returncode != 0:
            logger.error(f"Avatar audio add failed:\n{r2.stderr[-400:]}")
            return False

        logger.info(f"Avatar video: {os.path.basename(output_path)} ({duration_sec:.1f}s)")
        return True

    except Exception as e:
        logger.error(f"Avatar video generation failed: {e}")
        return False

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        if os.path.exists(output_path + "_avsilent.mp4"):
            os.remove(output_path + "_avsilent.mp4")


def _load_custom_frames(png_path: str) -> dict:
    """
    Load a user-provided transparent PNG and create 3 mouth states
    by drawing simple overlay ovals in the lower-center of the face.
    (Best-effort — works well when the face is centered in the image.)
    """
    base = Image.open(png_path).convert("RGBA").resize((_AV, _AV), Image.LANCZOS)
    frames = {}
    cx, cy_mouth = _AV // 2, int(_AV * 0.72)  # approximate mouth position

    for state, (key, mouth_draw) in enumerate({
        "closed": None,
        "half":   (12, 6),
        "open":   (18, 12),
    }.items()):
        frame = base.copy()
        if mouth_draw:
            w, h = mouth_draw
            overlay = Image.new("RGBA", (_AV, _AV), (0, 0, 0, 0))
            ImageDraw.Draw(overlay).ellipse(
                [cx - w, cy_mouth - h, cx + w, cy_mouth + h],
                fill=(200, 80, 80, 220),
            )
            frame = Image.alpha_composite(frame, overlay)
        frames[key] = frame

    return frames


# ── Composite onto video ─────────────────────────────────────────────────────

def overlay_avatar_on_video(
    video_path: str,
    avatar_video_path: str,
    output_path: str,
    position: str = "bottomleft",  # "bottomleft" | "bottomright"
    margin: int = 28,
    size: int = None,
) -> bool:
    """
    Composite the avatar video onto the main video using FFmpeg overlay filter.
    The avatar is rendered with a transparency pass when PNG has alpha.
    """
    size = size or _AV
    if position == "bottomleft":
        x_expr = str(margin)
        y_expr = f"H-h-{margin}"
    else:
        x_expr = f"W-w-{margin}"
        y_expr = f"H-h-{margin}"

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", avatar_video_path,
        "-filter_complex",
        (
            f"[1:v]scale={size}:{size}[av];"
            f"[0:v][av]overlay={x_expr}:{y_expr}:shortest=1"
        ),
        "-map", "0:a",          # keep original audio
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "copy",
        output_path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        logger.error(f"Avatar overlay failed:\n{r.stderr[-500:]}")
        return False
    logger.info(f"Avatar overlay applied: {os.path.basename(output_path)}")
    return True


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s: %(message)s")

    print("\n🎌 CloudSignalHQ Avatar Engine")
    print("Rendering avatar frames...")

    # Force re-render
    frames = build_avatar_frames(force=True)
    print(f"Frames saved to: {AVATAR_DIR}")
    for name, path in frames.items():
        sz = os.path.getsize(path) // 1024
        print(f"  {name:8s} → {os.path.basename(path)}  ({sz} KB)")

    print("\nGenerating 5-second test clip...")
    test_out = os.path.join(AVATAR_DIR, "avatar_test.mp4")
    ok = create_talking_avatar_video(5.0, test_out)
    print(f"{'✅' if ok else '❌'} Test clip: {test_out}")
