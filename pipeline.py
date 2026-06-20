"""
Main Pipeline — orchestrates the full video generation workflow:
  1. Generate script (GPT-4o)
  2. Generate voiceover audio (Edge-TTS)
  3. Fetch stock footage (Pexels)
  4. Assemble video (FFmpeg)
  5. Upload to YouTube (YouTube Data API)

Can be run from CLI or imported by the web app.
"""
import os
import uuid
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from config import CHANNEL_NAME, CHANNEL_NICHE, CHANNEL_LANGUAGE, LOGS_DIR, VIDEOS_DIR

# Configure logging
log_file = os.path.join(LOGS_DIR, f"pipeline_{datetime.now().strftime('%Y%m%d')}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger("pipeline")


class VideoGenerationPipeline:
    """Full end-to-end video generation pipeline."""

    def __init__(
        self,
        channel_name: str = None,
        niche: str = None,
        language: str = None,
    ):
        self.channel_name = channel_name or CHANNEL_NAME
        self.niche        = niche or CHANNEL_NICHE
        self.language     = language or CHANNEL_LANGUAGE
        self.status       = {}   # tracks progress for the web UI

    def _update_status(self, step: str, message: str, progress: int, error: str = None):
        self.status = {
            "step":     step,
            "message":  message,
            "progress": progress,
            "error":    error,
            "ts":       datetime.now().isoformat(),
        }
        logger.info(f"[{progress}%] {step}: {message}")

    def run(
        self,
        topic: str,
        privacy: str = "private",
        upload: bool = True,
        publish_at: str = None,
        duration_min: int = 8,
        on_progress=None,
    ) -> dict:
        """
        Run the full pipeline for a given topic.

        Args:
            topic:       Video topic/title
            privacy:     YouTube privacy ("private"|"unlisted"|"public")
            upload:      Whether to upload to YouTube
            publish_at:  ISO 8601 scheduled publish time
            duration_min: Target video duration in minutes
            on_progress: Callback fn(status_dict) for real-time updates

        Returns:
            result dict with video_path, youtube_url, script, metadata
        """
        video_id = f"vid_{uuid.uuid4().hex[:8]}"
        result   = {"video_id": video_id, "topic": topic, "success": False}

        def progress(step, msg, pct, err=None):
            self._update_status(step, msg, pct, err)
            if on_progress:
                on_progress(self.status)

        try:
            # ── Step 1: Generate Script ──────────────────────────────
            progress("script", f"Writing script for: {topic}", 5)
            from script_generator import generate_script
            script = generate_script(
                topic=topic,
                niche=self.niche,
                channel_name=self.channel_name,
                language=self.language,
                duration_min=duration_min,
            )
            result["script"] = script
            result["title"]  = script.get("title", topic)

            # Save script JSON
            script_path = os.path.join(VIDEOS_DIR, f"{video_id}_script.json")
            with open(script_path, "w", encoding="utf-8") as f:
                json.dump(script, f, indent=2, ensure_ascii=False)
            progress("script", f"Script ready: '{script.get('title')}'", 15)

            # ── Step 2: Generate TTS Audio ───────────────────────────
            progress("audio", "Generating voiceover audio...", 20)
            from tts_engine import generate_scene_audio
            scenes = script.get("scenes", [])
            scenes = generate_scene_audio(scenes, video_id, self.language)
            total_audio = sum(s.get("actual_duration_sec", 0) for s in scenes)
            progress("audio", f"Audio done: {total_audio:.0f}s narration across {len(scenes)} scenes", 40)

            # ── Step 3: Fetch Stock Footage ──────────────────────────
            progress("footage", "Downloading stock footage from Pexels...", 45)
            from footage_fetcher import fetch_all_footage
            scenes = fetch_all_footage(scenes, video_id)
            total_clips = sum(len(s.get("footage_paths", [])) for s in scenes)
            progress("footage", f"Downloaded {total_clips} video clips", 65)

            # ── Step 4: Assemble Video ───────────────────────────────
            progress("assembly", "Assembling final video with FFmpeg...", 70)
            from video_assembler import assemble_video
            video_path = assemble_video(script, scenes, video_id, self.channel_name, niche=self.niche)

            if not video_path or not os.path.exists(video_path):
                raise RuntimeError("Video assembly failed — check FFmpeg logs")

            size_mb = os.path.getsize(video_path) / (1024 * 1024)
            progress("assembly", f"Video assembled: {size_mb:.1f} MB", 85)
            result["video_path"] = video_path

            # ── Step 5: Generate Thumbnail ───────────────────────────
            thumbnail_path = None
            try:
                progress("thumbnail", "Generating custom thumbnail...", 86)
                from thumbnail_generator import generate_thumbnail
                thumbnail_path = generate_thumbnail(
                    title=script.get("title", topic),
                    thumbnail_text=script.get("thumbnail_text", ""),
                    thumbnail_subtitle=script.get("thumbnail_subtitle", ""),
                    channel_name=self.channel_name,
                    niche=self.niche,
                    video_id=video_id,
                    tags=script.get("tags", [])[:4],
                )
                result["thumbnail_path"] = thumbnail_path
                progress("thumbnail", f"Thumbnail ready: {os.path.basename(thumbnail_path)}", 88)
            except Exception as thumb_err:
                logger.warning(f"Thumbnail generation failed (non-fatal): {thumb_err}")

            # ── Step 6: Upload to YouTube ────────────────────────────
            if upload:
                progress("upload", "Uploading to YouTube...", 90)
                from youtube_uploader import upload_video
                upload_result = upload_video(
                    video_path=video_path,
                    script=script,
                    niche=self.niche,
                    privacy=privacy,
                    publish_at=publish_at,
                    thumbnail_path=thumbnail_path,
                )
                result["youtube_url"]  = upload_result["url"]
                result["youtube_id"]   = upload_result["video_id"]
                result["upload_result"]= upload_result
                thumb_status = "✅ thumbnail set" if upload_result.get("thumbnail_set") else "⚠️ no thumbnail"
                progress("done", f"✅ Uploaded: {upload_result['url']} | {upload_result['tags_count']} tags | {thumb_status}", 100)
            else:
                progress("done", f"✅ Video ready (upload skipped): {video_path}", 100)

            result["success"] = True

        except Exception as e:
            logger.exception(f"Pipeline failed: {e}")
            progress("error", str(e), self.status.get("progress", 0), error=str(e))
            result["error"] = str(e)

        # Save result manifest
        manifest_path = os.path.join(VIDEOS_DIR, f"{video_id}_manifest.json")
        with open(manifest_path, "w") as f:
            safe_result = {k: v for k, v in result.items() if k not in ("script",)}
            json.dump(safe_result, f, indent=2, default=str)

        return result


def list_generated_videos() -> list[dict]:
    """Return metadata of all generated videos."""
    videos = []
    for f in sorted(Path(VIDEOS_DIR).glob("*_manifest.json"), reverse=True):
        try:
            with open(f) as fp:
                videos.append(json.load(fp))
        except Exception:
            pass
    return videos


# ── CLI entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="India Faceless YouTube Video Generator")
    parser.add_argument("topic",     help="Video topic")
    parser.add_argument("--niche",   default=CHANNEL_NICHE, help="Channel niche")
    parser.add_argument("--lang",    default=CHANNEL_LANGUAGE, help="Language (English/Hindi)")
    parser.add_argument("--privacy", default="private", choices=["private","unlisted","public"])
    parser.add_argument("--no-upload", action="store_true", help="Skip YouTube upload")
    parser.add_argument("--duration", type=int, default=8, help="Target duration (minutes)")
    args = parser.parse_args()

    pipeline = VideoGenerationPipeline(niche=args.niche, language=args.lang)
    result   = pipeline.run(
        topic=args.topic,
        privacy=args.privacy,
        upload=not args.no_upload,
        duration_min=args.duration,
    )

    if result["success"]:
        print(f"\n✅ Done!")
        print(f"   Video:   {result.get('video_path')}")
        print(f"   YouTube: {result.get('youtube_url', '(not uploaded)')}")
    else:
        print(f"\n❌ Failed: {result.get('error')}")
        exit(1)
