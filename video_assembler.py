"""
Video Assembler — uses FFmpeg + Pillow to assemble the final YouTube video.
Pipeline: footage clips → trim/scale → add narration audio → add captions →
          add background music → add intro/outro → export final MP4.
Text overlays use Pillow (PIL) instead of FFmpeg drawtext (no libfreetype needed).
"""
import os
import subprocess
import logging
import json
import textwrap
import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from config import (
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS,
    VIDEOS_DIR, AUDIO_DIR, FOOTAGE_DIR, BASE_DIR
)

logger = logging.getLogger(__name__)

# Background music: royalty-free lo-fi (user can add their own in assets/bgm/)
BGM_DIR       = os.path.join(BASE_DIR, "assets", "bgm")
FONT_PATH     = os.path.join(BASE_DIR, "assets", "fonts", "NotoSans-Bold.ttf")
LOGO_PATH     = os.path.join(BASE_DIR, "assets", "logo.png")
INTRO_IMG     = os.path.join(BASE_DIR, "assets", "intro.png")
OUTRO_IMG     = os.path.join(BASE_DIR, "assets", "outro.png")

# Brand colors (saffron/tricolor theme)
COLOR_BG      = "0x1a1a2e"   # Dark navy
COLOR_ACCENT  = "0xFF6B00"   # Saffron/orange
COLOR_TEXT    = "0xFFFFFF"   # White
COLOR_SUBTITLE= "0xFFD700"   # Gold

os.makedirs(BGM_DIR, exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "assets", "fonts"), exist_ok=True)


def run_ffmpeg(cmd: list[str], step: str = "") -> bool:
    """Run an FFmpeg command, log output, return success."""
    logger.debug(f"FFmpeg {step}: {' '.join(cmd)}")
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=300
    )
    if result.returncode != 0:
        logger.error(f"FFmpeg {step} failed:\n{result.stderr[-1000:]}")
        return False
    return True


def get_video_duration(path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        data = json.loads(result.stdout)
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                return float(stream.get("duration", 0))
    except Exception:
        pass
    return 0.0


def prepare_footage_clip(input_path: str, output_path: str, duration_sec: float) -> bool:
    """Scale, crop, and trim a footage clip to exact duration at target resolution."""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-t", str(duration_sec),
        "-vf", (
            f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
            f"fps={VIDEO_FPS}"
        ),
        "-an",          # strip audio from footage
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        output_path,
    ]
    return run_ffmpeg(cmd, f"prepare_clip({Path(input_path).name})")


def create_color_background(output_path: str, duration_sec: float, color: str = "0x1a1a2e") -> bool:
    """Create a solid color background video (fallback when no footage)."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c={color}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:r={VIDEO_FPS}:d={duration_sec}",
        "-c:v", "libx264",
        "-preset", "fast",
        output_path,
    ]
    return run_ffmpeg(cmd, "color_bg")


def _get_font(size: int):
    """Load a font, falling back to PIL default if not available."""
    if os.path.exists(FONT_PATH):
        try:
            return ImageFont.truetype(FONT_PATH, size)
        except Exception:
            pass
    try:
        # Try common system fonts on macOS
        for path in [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Arial.ttf",
            "/Library/Fonts/Arial.ttf",
        ]:
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
    except Exception:
        pass
    return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color string to RGB tuple."""
    hex_color = hex_color.lstrip("0x").lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _make_text_overlay_png(text: str, width: int, height: int,
                            y_frac: float, fontsize: int,
                            color_hex: str, with_box: bool, png_path: str):
    """Create a transparent PNG with centered text at given vertical position."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _get_font(fontsize)
    # Wrap text
    lines = textwrap.wrap(text[:120], width=40)
    y = int(height * y_frac)
    for line in lines[:3]:
        try:
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except AttributeError:
            tw, th = draw.textsize(line, font=font)
        x = (width - tw) // 2
        if with_box:
            draw.rectangle([x - 10, y - 5, x + tw + 10, y + th + 5],
                           fill=(0, 0, 0, 160))
        rgb = _hex_to_rgb(color_hex) if color_hex.startswith("0x") else (255, 255, 255)
        draw.text((x, y), line, font=font, fill=rgb + (255,))
        y += th + 8
    img.save(png_path)


def _make_caption_bar_png(text: str, width: int, height: int, bar_h: int,
                           fontsize: int, png_path: str):
    """Create a PNG with a semi-transparent bar + caption text at the bottom."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Semi-transparent bar
    bar_y = height - bar_h
    draw.rectangle([0, bar_y, width, height], fill=(0, 0, 0, 180))
    font = _get_font(fontsize)
    lines = textwrap.wrap(text[:120], width=70)
    caption = " | ".join(lines[:2])
    try:
        bbox = draw.textbbox((0, 0), caption, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    except AttributeError:
        tw, th = draw.textsize(caption, font=font)
    x = (width - tw) // 2
    y = bar_y + (bar_h - th) // 2
    draw.text((x, y), caption, font=font, fill=(255, 255, 255, 255))
    img.save(png_path)


def _overlay_png_on_video(input_path: str, png_path: str, output_path: str) -> bool:
    """Overlay a PNG (RGBA) on top of a video using FFmpeg overlay filter."""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-i", png_path,
        "-filter_complex", "overlay=0:0",
        "-c:v", "libx264",
        "-preset", "fast",
        "-c:a", "copy",
        output_path,
    ]
    return run_ffmpeg(cmd, "png_overlay")


def add_text_overlay(input_path: str, output_path: str, text: str,
                     x: str = "(w-text_w)/2", y: str = "h-100",
                     fontsize: int = 48, color: str = "white",
                     box: bool = True, duration_sec: float = None) -> bool:
    """Add text overlay to a video clip using Pillow PNG."""
    png_path = output_path + "_overlay.png"
    color_hex = color if color.startswith("0x") else "0xFFFFFF"
    _make_text_overlay_png(
        text=text, width=VIDEO_WIDTH, height=VIDEO_HEIGHT,
        y_frac=0.10, fontsize=fontsize, color_hex=color_hex,
        with_box=box, png_path=png_path
    )
    ok = _overlay_png_on_video(input_path, png_path, output_path)
    try:
        os.remove(png_path)
    except Exception:
        pass
    return ok


def add_caption_bar(input_path: str, output_path: str, text: str, duration_sec: float) -> bool:
    """Add caption bar at the bottom of the video using Pillow PNG."""
    png_path = output_path + "_caption.png"
    _make_caption_bar_png(
        text=text, width=VIDEO_WIDTH, height=VIDEO_HEIGHT,
        bar_h=110, fontsize=32, png_path=png_path
    )
    ok = _overlay_png_on_video(input_path, png_path, output_path)
    try:
        os.remove(png_path)
    except Exception:
        pass
    return ok


def merge_video_audio(video_path: str, audio_path: str, output_path: str) -> bool:
    """Merge a silent video clip with narration audio."""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        output_path,
    ]
    return run_ffmpeg(cmd, "merge_av")


def build_scene_clip(scene: dict, video_id: str, tmp_dir: str) -> str | None:
    """
    Build a single scene clip: footage + audio + captions.
    Returns path to assembled scene clip.
    """
    sid         = scene["id"]
    audio_path  = scene.get("audio_path")
    footage     = scene.get("footage_paths", [])
    duration    = scene.get("actual_duration_sec", scene.get("duration_sec", 45))
    narration   = scene.get("narration", "")
    on_screen   = scene.get("on_screen_text", "")

    logger.info(f"Building scene {sid}: {duration:.1f}s | footage={len(footage)}")

    # ── Step 1: Prepare footage or fallback ──────────────────────
    footage_out = os.path.join(tmp_dir, f"scene{sid:02d}_footage.mp4")
    if footage:
        clip_path = footage[0]
        ok = prepare_footage_clip(clip_path, footage_out, duration)
        if not ok:
            create_color_background(footage_out, duration)
    else:
        create_color_background(footage_out, duration)

    # ── Step 2: Add on-screen text overlay ───────────────────────
    overlay_out = os.path.join(tmp_dir, f"scene{sid:02d}_overlay.mp4")
    if on_screen:
        add_text_overlay(
            footage_out, overlay_out,
            text=on_screen,
            x="(w-text_w)/2", y="h*0.12",
            fontsize=52,
            color="0xFFD700",  # Gold text
        )
    else:
        shutil.copy2(footage_out, overlay_out)

    # ── Step 3: Add caption bar ───────────────────────────────────
    caption_out = os.path.join(tmp_dir, f"scene{sid:02d}_caption.mp4")
    if narration and len(narration) > 10:
        # Use first 100 chars of narration as caption
        caption_text = narration[:100] + ("..." if len(narration) > 100 else "")
        add_caption_bar(overlay_out, caption_out, caption_text, duration)
    else:
        shutil.copy2(overlay_out, caption_out)

    # ── Step 4: Merge with narration audio ───────────────────────
    if audio_path and os.path.exists(audio_path):
        scene_out = os.path.join(tmp_dir, f"scene{sid:02d}_final.mp4")
        ok = merge_video_audio(caption_out, audio_path, scene_out)
        if ok:
            return scene_out

    return caption_out  # silent fallback


def concatenate_clips(clip_paths: list[str], output_path: str) -> bool:
    """Concatenate multiple MP4 clips into a single video."""
    # Create file list for ffmpeg concat
    list_file = output_path + "_concat.txt"
    with open(list_file, "w") as f:
        for p in clip_paths:
            f.write(f"file '{p}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_file,
        "-c:v", "libx264",
        "-preset", "fast",
        "-c:a", "aac",
        "-movflags", "+faststart",
        output_path,
    ]
    ok = run_ffmpeg(cmd, "concatenate")
    os.remove(list_file)
    return ok


def add_background_music(input_path: str, output_path: str, bgm_volume: float = 0.08) -> bool:
    """Mix soft background music under the narration (8% volume)."""
    bgm_files = [f for f in os.listdir(BGM_DIR) if f.endswith(".mp3")] if os.path.exists(BGM_DIR) else []
    if not bgm_files:
        logger.info("No BGM files found in assets/bgm/ — skipping background music")
        import shutil
        shutil.copy2(input_path, output_path)
        return True

    import random
    bgm_path = os.path.join(BGM_DIR, random.choice(bgm_files))
    duration = get_video_duration(input_path)

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-stream_loop", "-1",
        "-i", bgm_path,
        "-t", str(duration),
        "-filter_complex",
        f"[1:a]volume={bgm_volume},afade=t=out:st={duration-5}:d=5[bgm];"
        f"[0:a][bgm]amix=inputs=2:duration=first[aout]",
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        output_path,
    ]
    return run_ffmpeg(cmd, "add_bgm")


def _make_card_image(lines: list, bg_color: tuple, text_colors: list,
                     font_sizes: list, png_path: str):
    """Create a full-frame card image using Pillow."""
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), bg_color)
    draw = ImageDraw.Draw(img)
    total_h = 0
    rendered = []
    for i, line in enumerate(lines):
        font = _get_font(font_sizes[i] if i < len(font_sizes) else 40)
        try:
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except AttributeError:
            tw, th = draw.textsize(line, font=font)
        rendered.append((line, font, tw, th, text_colors[i] if i < len(text_colors) else (255, 255, 255)))
        total_h += th + 20
    y = (VIDEO_HEIGHT - total_h) // 2
    for line, font, tw, th, color in rendered:
        x = (VIDEO_WIDTH - tw) // 2
        draw.text((x, y), line, font=font, fill=color)
        y += th + 20
    img.save(png_path)


def _image_to_video(png_path: str, duration_sec: float, output_path: str) -> bool:
    """Convert a static PNG image to a video clip of given duration."""
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", png_path,
        "-t", str(duration_sec),
        "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},fps={VIDEO_FPS}",
        "-c:v", "libx264",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        output_path,
    ]
    return run_ffmpeg(cmd, "image_to_video")


def create_title_card(title: str, subtitle: str, duration_sec: float, output_path: str) -> bool:
    """Create a title card as intro using Pillow."""
    png_path = output_path + "_title.png"
    _make_card_image(
        lines=[title[:55], subtitle[:45]],
        bg_color=(26, 26, 46),          # dark navy
        text_colors=[(255, 215, 0), (255, 255, 255)],  # gold, white
        font_sizes=[72, 42],
        png_path=png_path,
    )
    ok = _image_to_video(png_path, duration_sec, output_path)
    try:
        os.remove(png_path)
    except Exception:
        pass
    return ok


def create_outro_card(channel_name: str, duration_sec: float, output_path: str) -> bool:
    """Create a branded outro/end screen using Pillow."""
    png_path = output_path + "_outro.png"
    _make_card_image(
        lines=["Like  Subscribe  Notify", channel_name, "New videos every week!"],
        bg_color=(13, 13, 13),
        text_colors=[(255, 107, 0), (255, 255, 255), (204, 204, 204)],
        font_sizes=[56, 40, 32],
        png_path=png_path,
    )
    ok = _image_to_video(png_path, duration_sec, output_path)
    try:
        os.remove(png_path)
    except Exception:
        pass
    return ok


def assemble_video(script: dict, scenes: list[dict], video_id: str, channel_name: str) -> str | None:
    """
    Full assembly pipeline:
    title_card + scene_clips + outro_card → concat → bgm → final MP4.
    Returns path to the final video file.
    """
    tmp_dir     = os.path.join(VIDEOS_DIR, f"tmp_{video_id}")
    os.makedirs(tmp_dir, exist_ok=True)

    title       = script.get("title", "Video")
    thumbnail   = script.get("thumbnail_text", "Watch Now")

    all_clips   = []

    # ── Title Card ──────────────────────────────────────────────
    logger.info("Creating title card...")
    title_path = os.path.join(tmp_dir, "00_title.mp4")
    create_title_card(title, thumbnail, 4.0, title_path)
    if os.path.exists(title_path):
        all_clips.append(title_path)

    # ── Scene Clips ─────────────────────────────────────────────
    for scene in scenes:
        logger.info(f"Assembling scene {scene['id']}...")
        clip = build_scene_clip(scene, video_id, tmp_dir)
        if clip and os.path.exists(clip):
            all_clips.append(clip)

    # ── Outro Card ──────────────────────────────────────────────
    logger.info("Creating outro card...")
    outro_path = os.path.join(tmp_dir, "99_outro.mp4")
    create_outro_card(channel_name, 6.0, outro_path)
    if os.path.exists(outro_path):
        all_clips.append(outro_path)

    if not all_clips:
        logger.error("No clips assembled!")
        return None

    # ── Concatenate All Clips ───────────────────────────────────
    logger.info(f"Concatenating {len(all_clips)} clips...")
    concat_path = os.path.join(tmp_dir, "concat_raw.mp4")
    ok = concatenate_clips(all_clips, concat_path)
    if not ok:
        return None

    # ── Add Background Music ────────────────────────────────────
    logger.info("Adding background music...")
    bgm_path = os.path.join(tmp_dir, "with_bgm.mp4")
    add_background_music(concat_path, bgm_path)

    # ── Final Export ────────────────────────────────────────────
    final_filename = f"{video_id}_final.mp4"
    final_path     = os.path.join(VIDEOS_DIR, final_filename)

    src = bgm_path if os.path.exists(bgm_path) else concat_path
    cmd = [
        "ffmpeg", "-y",
        "-i", src,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        final_path,
    ]
    ok = run_ffmpeg(cmd, "final_export")
    if ok and os.path.exists(final_path):
        size_mb = os.path.getsize(final_path) / (1024 * 1024)
        logger.info(f"✅ Final video: {final_path} ({size_mb:.1f} MB)")
        return final_path

    return None
