"""
Video Assembler — uses FFmpeg to assemble the final YouTube video.
Pipeline: footage clips → trim/scale → add narration audio → add captions →
          add background music → add intro/outro → export final MP4.
"""
import os
import subprocess
import logging
import json
import uuid
import textwrap
from pathlib import Path
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


def add_text_overlay(input_path: str, output_path: str, text: str,
                     x: str = "(w-text_w)/2", y: str = "h-100",
                     fontsize: int = 48, color: str = "white",
                     box: bool = True, duration_sec: float = None) -> bool:
    """Add text overlay to a video clip."""
    # Escape special chars for FFmpeg drawtext
    safe_text = text.replace("'", "\\'").replace(":", "\\:")[:80]
    box_str = f":box=1:boxcolor=black@0.5:boxborderw=10" if box else ""

    font_str = f":fontfile={FONT_PATH}" if os.path.exists(FONT_PATH) else ""
    duration_str = f":enable='between(t,0,{duration_sec})'" if duration_sec else ""

    vf = (f"drawtext=text='{safe_text}'"
          f":x={x}:y={y}"
          f":fontsize={fontsize}"
          f":fontcolor={color}"
          f"{font_str}{box_str}{duration_str}")

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "fast",
        "-c:a", "copy",
        output_path,
    ]
    return run_ffmpeg(cmd, "text_overlay")


def add_caption_bar(input_path: str, output_path: str, text: str, duration_sec: float) -> bool:
    """Add animated caption bar at the bottom of the video."""
    # Split long text into lines
    lines = textwrap.wrap(text, width=60)
    caption = " ".join(lines[:2])  # max 2 lines
    safe_caption = caption.replace("'", "\\'").replace(":", "\\:")

    font_str = f":fontfile={FONT_PATH}" if os.path.exists(FONT_PATH) else ""

    vf = (
        # Semi-transparent bottom bar
        f"drawbox=x=0:y=ih-120:w=iw:h=120:color=black@0.7:t=fill,"
        # Caption text
        f"drawtext=text='{safe_caption}'"
        f":x=(w-text_w)/2:y=h-80"
        f":fontsize=36:fontcolor=white"
        f"{font_str}"
        f":box=0"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "fast",
        "-c:a", "copy",
        output_path,
    ]
    return run_ffmpeg(cmd, "caption_bar")


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
        import shutil
        shutil.copy2(footage_out, overlay_out)

    # ── Step 3: Add caption bar ───────────────────────────────────
    caption_out = os.path.join(tmp_dir, f"scene{sid:02d}_caption.mp4")
    if narration and len(narration) > 10:
        # Use first 100 chars of narration as caption
        caption_text = narration[:100] + ("..." if len(narration) > 100 else "")
        add_caption_bar(overlay_out, caption_out, caption_text, duration)
    else:
        import shutil
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


def create_title_card(title: str, subtitle: str, duration_sec: float, output_path: str) -> bool:
    """Create an animated title card as intro."""
    safe_title    = title.replace("'", "\\'").replace(":", "\\:")[:50]
    safe_subtitle = subtitle.replace("'", "\\'").replace(":", "\\:")[:40]

    vf = (
        f"color=c=0x1a1a2e:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:r={VIDEO_FPS}:d={duration_sec}[bg];"
        f"[bg]drawtext=text='{safe_title}'"
        f":x=(w-text_w)/2:y=(h-text_h)/2-60"
        f":fontsize=72:fontcolor=0xFFD700"
        f":alpha='if(lt(t,0.5),t/0.5,1)',"
        f"drawtext=text='{safe_subtitle}'"
        f":x=(w-text_w)/2:y=(h-text_h)/2+60"
        f":fontsize=42:fontcolor=white"
    )
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", vf,
        "-t", str(duration_sec),
        "-c:v", "libx264",
        "-preset", "fast",
        output_path,
    ]
    return run_ffmpeg(cmd, "title_card")


def create_outro_card(channel_name: str, duration_sec: float, output_path: str) -> bool:
    """Create a branded outro/end screen."""
    safe_name = channel_name.replace("'", "\\'")

    vf = (
        f"color=c=0x0D0D0D:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:r={VIDEO_FPS}:d={duration_sec}[bg];"
        f"[bg]drawtext=text='Like ♥ Subscribe ♥ Notify'"
        f":x=(w-text_w)/2:y=(h-text_h)/2-80"
        f":fontsize=56:fontcolor=0xFF6B00,"
        f"drawtext=text='{safe_name}'"
        f":x=(w-text_w)/2:y=(h-text_h)/2+20"
        f":fontsize=40:fontcolor=white,"
        f"drawtext=text='New videos every week!'"
        f":x=(w-text_w)/2:y=(h-text_h)/2+100"
        f":fontsize=32:fontcolor=0xCCCCCC"
    )
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", vf,
        "-t", str(duration_sec),
        "-c:v", "libx264",
        "-preset", "fast",
        output_path,
    ]
    return run_ffmpeg(cmd, "outro_card")


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
