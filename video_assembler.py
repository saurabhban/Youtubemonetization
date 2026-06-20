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
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from config import (
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS,
    VIDEOS_DIR, AUDIO_DIR, FOOTAGE_DIR, BASE_DIR
)

logger = logging.getLogger(__name__)

BGM_DIR   = os.path.join(BASE_DIR, "assets", "bgm")
FONT_DIR  = os.path.join(BASE_DIR, "assets", "fonts")
FONT_PATH = os.path.join(FONT_DIR, "NotoSans-Bold.ttf")

os.makedirs(BGM_DIR, exist_ok=True)
os.makedirs(FONT_DIR, exist_ok=True)

# Auto-download NotoSans font if missing
if not os.path.exists(FONT_PATH):
    try:
        url = "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Bold.ttf"
        logger.info("Downloading NotoSans-Bold font...")
        urllib.request.urlretrieve(url, FONT_PATH)
        logger.info(f"Font saved to {FONT_PATH}")
    except Exception as e:
        logger.warning(f"Font download failed: {e} — will use system font")


# ── Helpers ────────────────────────────────────────────────────────────────

def run_ffmpeg(cmd: list, step: str = "") -> bool:
    """Run an FFmpeg command, log output, return success."""
    logger.debug(f"FFmpeg {step}: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        logger.error(f"FFmpeg {step} failed:\n{result.stderr[-1000:]}")
        return False
    return True


def get_video_duration(path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
        capture_output=True, text=True
    )
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except Exception:
        return 0.0


def has_audio_stream(path: str) -> bool:
    """Return True if the file has at least one audio stream."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path],
        capture_output=True, text=True
    )
    try:
        streams = json.loads(result.stdout).get("streams", [])
        return any(s.get("codec_type") == "audio" for s in streams)
    except Exception:
        return False


def add_silent_audio(input_path: str, output_path: str, duration: float) -> bool:
    """Add a silent AAC audio track to a video-only file, normalised to 44100 Hz stereo."""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k",
        "-t", str(duration),
        output_path,
    ]
    return run_ffmpeg(cmd, "add_silent_audio")


def _get_font(size: int):
    """Load a TrueType font at given size, with fallback chain."""
    candidates = [
        FONT_PATH,
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNS.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    # Last resort: PIL built-in (tiny, but at least it works)
    return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("0x").lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _text_size(draw, text, font):
    """Measure text, compatible with Pillow 9 and 10+."""
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        return draw.textsize(text, font=font)


# ── PNG helpers ───────────────────────────────────────────────────────────

def _make_text_overlay_png(text: str, width: int, height: int,
                            y_frac: float, fontsize: int,
                            color_hex: str, with_box: bool, png_path: str):
    """Transparent PNG with centered text at a fractional vertical position."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _get_font(fontsize)
    lines = textwrap.wrap(text[:120], width=38)
    y = int(height * y_frac)
    rgb = _hex_to_rgb(color_hex) if color_hex.startswith("0x") else (255, 255, 255)
    for line in lines[:3]:
        tw, th = _text_size(draw, line, font)
        x = (width - tw) // 2
        if with_box:
            draw.rectangle([x - 12, y - 6, x + tw + 12, y + th + 6], fill=(0, 0, 0, 170))
        draw.text((x, y), line, font=font, fill=rgb + (255,))
        y += th + 10
    img.save(png_path)


def _make_caption_bar_png(text: str, width: int, height: int,
                           bar_h: int, fontsize: int, png_path: str):
    """Semi-transparent caption bar at the bottom of the frame."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    bar_y = height - bar_h
    draw.rectangle([0, bar_y, width, height], fill=(0, 0, 0, 185))
    font = _get_font(fontsize)
    lines = textwrap.wrap(text[:130], width=75)
    caption = "  ".join(lines[:2])
    tw, th = _text_size(draw, caption, font)
    x = max(0, (width - tw) // 2)
    y = bar_y + (bar_h - th) // 2
    draw.text((x, y), caption, font=font, fill=(255, 255, 255, 255))
    img.save(png_path)


def _make_card_image(lines: list, bg_color: tuple, text_colors: list,
                     font_sizes: list, png_path: str):
    """Full-frame card image with multiple lines of centered text."""
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), bg_color)
    draw = ImageDraw.Draw(img)
    rendered = []
    total_h = 0
    for i, line in enumerate(lines):
        font = _get_font(font_sizes[i] if i < len(font_sizes) else 40)
        tw, th = _text_size(draw, line, font)
        color = text_colors[i] if i < len(text_colors) else (255, 255, 255)
        rendered.append((line, font, tw, th, color))
        total_h += th + 24
    y = max(0, (VIDEO_HEIGHT - total_h) // 2)
    for line, font, tw, th, color in rendered:
        x = max(0, (VIDEO_WIDTH - tw) // 2)
        draw.text((x, y), line, font=font, fill=color)
        y += th + 24
    img.save(png_path)


def _overlay_png_on_video(input_path: str, png_path: str, output_path: str) -> bool:
    """Overlay a transparent PNG on top of a video."""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-i", png_path,
        "-filter_complex", "[0:v][1:v]overlay=0:0",
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "copy",
        output_path,
    ]
    return run_ffmpeg(cmd, "png_overlay")


def _image_to_video(png_path: str, duration_sec: float, output_path: str,
                    with_audio: bool = False) -> bool:
    """Convert a static PNG to a video of given duration, optionally with silent audio."""
    silent_video = output_path + "_noaudio.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", png_path,
        "-t", str(duration_sec),
        "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},fps={VIDEO_FPS}",
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        silent_video,
    ]
    ok = run_ffmpeg(cmd, "image_to_video")
    if not ok:
        return False
    if with_audio:
        ok2 = add_silent_audio(silent_video, output_path, duration_sec)
        try:
            os.remove(silent_video)
        except Exception:
            pass
        return ok2
    else:
        shutil.move(silent_video, output_path)
        return True


# ── Scene building ────────────────────────────────────────────────────────

def prepare_footage_clip(input_path: str, output_path: str, duration_sec: float) -> bool:
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-t", str(duration_sec),
        "-vf", (
            f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},fps={VIDEO_FPS}"
        ),
        "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        output_path,
    ]
    return run_ffmpeg(cmd, f"prepare_clip({Path(input_path).name})")


def create_color_background(output_path: str, duration_sec: float,
                             color: str = "0x1a1a2e") -> bool:
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c={color}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:r={VIDEO_FPS}:d={duration_sec}",
        "-c:v", "libx264", "-preset", "fast",
        output_path,
    ]
    return run_ffmpeg(cmd, "color_bg")


def add_text_overlay(input_path: str, output_path: str, text: str,
                     fontsize: int = 52, color: str = "0xFFD700",
                     box: bool = True, **kwargs) -> bool:
    png_path = output_path + "_ovl.png"
    color_hex = color if color.startswith("0x") else "0xFFFFFF"
    _make_text_overlay_png(text, VIDEO_WIDTH, VIDEO_HEIGHT,
                           y_frac=0.10, fontsize=fontsize,
                           color_hex=color_hex, with_box=box, png_path=png_path)
    ok = _overlay_png_on_video(input_path, png_path, output_path)
    try:
        os.remove(png_path)
    except Exception:
        pass
    return ok


def add_caption_bar(input_path: str, output_path: str,
                    text: str, duration_sec: float) -> bool:
    png_path = output_path + "_cap.png"
    _make_caption_bar_png(text, VIDEO_WIDTH, VIDEO_HEIGHT,
                          bar_h=110, fontsize=34, png_path=png_path)
    ok = _overlay_png_on_video(input_path, png_path, output_path)
    try:
        os.remove(png_path)
    except Exception:
        pass
    return ok


def merge_video_audio(video_path: str, audio_path: str, output_path: str) -> bool:
    """Merge silent video with narration audio, normalising audio to 44100 Hz stereo AAC."""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path, "-i", audio_path,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k",
        "-shortest",
        output_path,
    ]
    return run_ffmpeg(cmd, "merge_av")


def build_scene_clip(scene: dict, video_id: str, tmp_dir: str):
    """Build one scene: footage → overlay → caption → merge audio. Robust fallbacks at each step."""
    sid       = scene["id"]
    audio_path = scene.get("audio_path")
    footage   = scene.get("footage_paths", [])
    duration  = scene.get("actual_duration_sec", scene.get("duration_sec", 45))
    narration = scene.get("narration", "")
    on_screen = scene.get("on_screen_text", "")

    logger.info(f"Building scene {sid}: {duration:.1f}s | footage={len(footage)}")

    # Step 1: footage
    footage_out = os.path.join(tmp_dir, f"scene{sid:02d}_footage.mp4")
    if footage:
        ok = prepare_footage_clip(footage[0], footage_out, duration)
        if not ok:
            create_color_background(footage_out, duration)
    else:
        create_color_background(footage_out, duration)

    # Step 2: text overlay (fallback = copy)
    overlay_out = os.path.join(tmp_dir, f"scene{sid:02d}_overlay.mp4")
    if on_screen and os.path.exists(footage_out):
        ok = add_text_overlay(footage_out, overlay_out, text=on_screen)
        if not ok or not os.path.exists(overlay_out):
            shutil.copy2(footage_out, overlay_out)
    elif os.path.exists(footage_out):
        shutil.copy2(footage_out, overlay_out)

    # Step 3: caption bar (fallback = copy)
    caption_out = os.path.join(tmp_dir, f"scene{sid:02d}_caption.mp4")
    if narration and len(narration) > 10 and os.path.exists(overlay_out):
        caption_text = narration[:100] + ("..." if len(narration) > 100 else "")
        ok = add_caption_bar(overlay_out, caption_out, caption_text, duration)
        if not ok or not os.path.exists(caption_out):
            shutil.copy2(overlay_out, caption_out)
    elif os.path.exists(overlay_out):
        shutil.copy2(overlay_out, caption_out)

    # Step 4: merge audio
    if audio_path and os.path.exists(audio_path) and os.path.exists(caption_out):
        scene_out = os.path.join(tmp_dir, f"scene{sid:02d}_final.mp4")
        ok = merge_video_audio(caption_out, audio_path, scene_out)
        if ok and os.path.exists(scene_out):
            return scene_out

    # Fallback: return silent caption clip (will add silent audio at concat stage)
    return caption_out if os.path.exists(caption_out) else None


# ── Cards ─────────────────────────────────────────────────────────────────

def create_title_card(title: str, subtitle: str, duration_sec: float, output_path: str) -> bool:
    png_path = output_path + "_title.png"
    _make_card_image(
        lines=[title[:55], subtitle[:45]],
        bg_color=(26, 26, 46),
        text_colors=[(255, 215, 0), (255, 255, 255)],
        font_sizes=[68, 40],
        png_path=png_path,
    )
    ok = _image_to_video(png_path, duration_sec, output_path, with_audio=True)
    try:
        os.remove(png_path)
    except Exception:
        pass
    return ok


def create_outro_card(channel_name: str, duration_sec: float, output_path: str) -> bool:
    png_path = output_path + "_outro.png"
    _make_card_image(
        lines=["Like  |  Subscribe  |  Notify", channel_name, "New videos every week!"],
        bg_color=(13, 13, 13),
        text_colors=[(255, 107, 0), (255, 255, 255), (204, 204, 204)],
        font_sizes=[52, 38, 30],
        png_path=png_path,
    )
    ok = _image_to_video(png_path, duration_sec, output_path, with_audio=True)
    try:
        os.remove(png_path)
    except Exception:
        pass
    return ok


# ── Concatenation ─────────────────────────────────────────────────────────

def _ensure_audio(clip_path: str, tmp_dir: str, idx: int) -> str:
    """If a clip has no audio, add a silent audio track and return new path."""
    if not has_audio_stream(clip_path):
        dur = get_video_duration(clip_path)
        silent_path = os.path.join(tmp_dir, f"silent_{idx:03d}.mp4")
        ok = add_silent_audio(clip_path, silent_path, dur)
        if ok and os.path.exists(silent_path):
            return silent_path
    return clip_path


def concatenate_clips(clip_paths: list, output_path: str, tmp_dir: str) -> bool:
    """
    Normalise all clips to identical stream parameters then concatenate.
    Each clip is re-encoded to 1920x1080 h264 + 44100Hz AAC before joining,
    so the concat demuxer never sees mismatched streams.
    """
    ready_clips = []
    for i, p in enumerate(clip_paths):
        if not os.path.exists(p):
            logger.warning(f"Clip missing, skipping: {p}")
            continue
        norm = os.path.join(tmp_dir, f"norm_{i:03d}.mp4")
        has_a = has_audio_stream(p)
        audio_filter = "aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo" if has_a else ""
        audio_input  = [] if has_a else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        a_map        = "1:a:0" if not has_a else "0:a:0"

        cmd = [
            "ffmpeg", "-y",
            "-i", p,
        ] + audio_input + [
            "-map", "0:v:0", "-map", a_map,
            "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,"
                   f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,fps={VIDEO_FPS}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k",
            "-t", str(get_video_duration(p)) if not has_a else "999999",
            norm,
        ]
        if has_a:
            # simpler path when audio already present
            cmd = [
                "ffmpeg", "-y", "-i", p,
                "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,"
                       f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,fps={VIDEO_FPS}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k",
                norm,
            ]
        ok = run_ffmpeg(cmd, f"normalise_{i}")
        if ok and os.path.exists(norm):
            ready_clips.append(norm)
        else:
            logger.warning(f"Normalise failed for clip {i}, skipping")

    if not ready_clips:
        logger.error("No clips to concatenate after normalisation")
        return False

    list_file = output_path + "_concat.txt"
    with open(list_file, "w") as f:
        for p in ready_clips:
            f.write(f"file '{p}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", list_file,
        "-c", "copy",          # streams are already normalised — just mux
        "-movflags", "+faststart",
        output_path,
    ]
    ok = run_ffmpeg(cmd, "concatenate")
    try:
        os.remove(list_file)
    except Exception:
        pass
    return ok


def add_background_music(input_path: str, output_path: str, bgm_volume: float = 0.08) -> bool:
    bgm_files = [f for f in os.listdir(BGM_DIR) if f.endswith(".mp3")] if os.path.exists(BGM_DIR) else []
    if not bgm_files:
        logger.info("No BGM files — skipping background music")
        shutil.copy2(input_path, output_path)
        return True
    import random
    bgm_path = os.path.join(BGM_DIR, random.choice(bgm_files))
    duration = get_video_duration(input_path)
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-stream_loop", "-1", "-i", bgm_path,
        "-t", str(duration),
        "-filter_complex",
        f"[1:a]volume={bgm_volume},afade=t=out:st={max(0,duration-5)}:d=5[bgm];"
        f"[0:a][bgm]amix=inputs=2:duration=first[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac",
        output_path,
    ]
    return run_ffmpeg(cmd, "add_bgm")


# ── Main assembly ─────────────────────────────────────────────────────────

def assemble_video(script: dict, scenes: list, video_id: str, channel_name: str):
    """Full pipeline: title + scenes + outro → concat → bgm → final MP4."""
    tmp_dir = os.path.join(VIDEOS_DIR, f"tmp_{video_id}")
    os.makedirs(tmp_dir, exist_ok=True)

    title     = script.get("title", "Video")
    thumbnail = script.get("thumbnail_text", "Watch Now")
    all_clips = []

    # Title card
    logger.info("Creating title card...")
    title_path = os.path.join(tmp_dir, "00_title.mp4")
    create_title_card(title, thumbnail, 4.0, title_path)
    if os.path.exists(title_path):
        all_clips.append(title_path)

    # Scene clips
    for scene in scenes:
        logger.info(f"Assembling scene {scene['id']}...")
        clip = build_scene_clip(scene, video_id, tmp_dir)
        if clip and os.path.exists(clip):
            all_clips.append(clip)

    # Outro card
    logger.info("Creating outro card...")
    outro_path = os.path.join(tmp_dir, "99_outro.mp4")
    create_outro_card(channel_name, 6.0, outro_path)
    if os.path.exists(outro_path):
        all_clips.append(outro_path)

    if not all_clips:
        logger.error("No clips assembled!")
        return None

    # Concatenate (handles mixed audio/silent clips)
    logger.info(f"Concatenating {len(all_clips)} clips...")
    concat_path = os.path.join(tmp_dir, "concat_raw.mp4")
    ok = concatenate_clips(all_clips, concat_path, tmp_dir)
    if not ok:
        return None

    # BGM
    logger.info("Adding background music...")
    bgm_path = os.path.join(tmp_dir, "with_bgm.mp4")
    add_background_music(concat_path, bgm_path)

    # Final export
    final_path = os.path.join(VIDEOS_DIR, f"{video_id}_final.mp4")
    src = bgm_path if os.path.exists(bgm_path) else concat_path
    cmd = [
        "ffmpeg", "-y", "-i", src,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        final_path,
    ]
    ok = run_ffmpeg(cmd, "final_export")
    if ok and os.path.exists(final_path):
        size_mb = os.path.getsize(final_path) / (1024 * 1024)
        logger.info(f"Final video: {final_path} ({size_mb:.1f} MB)")
        return final_path
    return None
