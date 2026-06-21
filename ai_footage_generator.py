"""
AI Footage Generator — Kling v1.6 via fal.ai

Generates short video clips (5s, 16:9) from scene narration / visual prompts.
Used as an alternative to Pexels stock footage when footage_mode="ai".

Cost: ~$0.003–0.005 per 5-second clip (Kling Standard via fal.ai)
API:  https://fal.ai/models/fal-ai/kling-video/v1.6/standard/text-to-video

Setup:
  FAL_KEY=<your_fal_key>  in .env
  pip install fal-client>=0.4.0

Quality tips for story channels:
  - Horror:      "dark, atmospheric, cinematic, low-key lighting, ominous"
  - Motivational: "golden hour, inspirational, cinematic, warm tones"
  - True Crime:  "noir, dramatic shadows, documentary style"
  - Mythology:   "epic, grand, ancient India, divine lighting, painterly"
"""
import os
import logging
import time
import uuid
import requests
from pathlib import Path
from config import VIDEOS_DIR

logger = logging.getLogger(__name__)

FAL_KEY  = os.getenv("FAL_KEY", "")
FAL_URL  = "https://queue.fal.run/fal-ai/kling-video/v1.6/standard/text-to-video"
FAL_POLL = "https://queue.fal.run/fal-ai/kling-video/v1.6/standard/text-to-video/requests/{request_id}"

CLIP_DURATION = "5"   # seconds (Kling: "5" or "10")
CLIP_RATIO    = "16:9"

# Niche → cinematic style suffix appended to every visual prompt
_STYLE_SUFFIX = {
    "Horror Stories India":       "dark atmospheric cinematic, deep shadows, ominous mood, horror aesthetic, 4K",
    "Motivational Stories India":  "golden hour, warm cinematic tones, inspiring, soft bokeh, uplifting, 4K",
    "True Crime India":            "noir, dramatic shadows, documentary realism, desaturated tones, tense, 4K",
    "Indian Mythology & History":  "epic ancient India, divine golden light, painterly, grand scale, mythological, 4K",
    "_default":                    "cinematic, professional, smooth motion, 4K",
}


def _style_for_niche(niche: str) -> str:
    return _STYLE_SUFFIX.get(niche, _STYLE_SUFFIX["_default"])


def _build_visual_prompt(scene: dict, niche: str) -> str:
    """
    Build a Kling text-to-video prompt from scene data.
    Uses scene's visual_prompt if present, else derives from narration.
    """
    base = (
        scene.get("visual_prompt")
        or scene.get("footage_keywords")
        or scene.get("narration", "")[:120]
    )
    style = _style_for_niche(niche)
    return f"{base}, {style}"


def _poll_for_result(request_id: str, timeout: int = 180) -> dict | None:
    """Poll fal.ai queue until result is ready or timeout."""
    headers = {"Authorization": f"Key {FAL_KEY}"}
    url     = FAL_POLL.format(request_id=request_id)
    deadline = time.time() + timeout

    while time.time() < deadline:
        time.sleep(5)
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status", "")
                if status == "COMPLETED":
                    return data.get("output") or data.get("result", {})
                elif status in ("FAILED", "CANCELLED"):
                    logger.error(f"Kling job {request_id} failed: {data}")
                    return None
                # IN_QUEUE or IN_PROGRESS — keep polling
            else:
                logger.warning(f"Poll {request_id}: HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"Poll error: {e}")

    logger.error(f"Kling job {request_id} timed out after {timeout}s")
    return None


def _download_clip(video_url: str, output_path: str) -> bool:
    """Download generated clip to disk."""
    try:
        resp = requests.get(video_url, timeout=120, stream=True)
        if resp.status_code == 200:
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            logger.info(f"Downloaded AI clip: {os.path.basename(output_path)} ({size_mb:.1f} MB)")
            return True
        logger.error(f"Download failed: HTTP {resp.status_code}")
    except Exception as e:
        logger.error(f"Download error: {e}")
    return False


def generate_ai_clip(scene: dict, video_id: str, scene_index: int,
                     niche: str = "") -> str | None:
    """
    Generate a single AI video clip for a scene via Kling.

    Returns local path to .mp4 file, or None on failure.
    """
    if not FAL_KEY:
        logger.warning("FAL_KEY not set — cannot generate AI footage")
        return None

    prompt      = _build_visual_prompt(scene, niche)
    output_path = os.path.join(VIDEOS_DIR, f"{video_id}_ai_clip_{scene_index:02d}.mp4")

    logger.info(f"  Scene {scene_index} AI clip: {prompt[:80]}...")

    # Submit to fal.ai queue
    try:
        resp = requests.post(
            FAL_URL,
            headers={
                "Authorization": f"Key {FAL_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "prompt":        prompt,
                "duration":      CLIP_DURATION,
                "aspect_ratio":  CLIP_RATIO,
                "negative_prompt": "text, watermark, logo, blurry, low quality, distorted faces",
            },
            timeout=30,
        )
    except Exception as e:
        logger.error(f"Kling submit error: {e}")
        return None

    if resp.status_code not in (200, 201):
        logger.error(f"Kling submit HTTP {resp.status_code}: {resp.text[:300]}")
        return None

    data       = resp.json()
    request_id = data.get("request_id") or data.get("id")

    # If sync response already has video URL (fal.ai sometimes returns immediately)
    video_url = None
    if "video" in data:
        video_url = data["video"].get("url")
    elif "output" in data and "video" in data["output"]:
        video_url = data["output"]["video"].get("url")

    if not video_url:
        if not request_id:
            logger.error(f"No request_id in Kling response: {data}")
            return None
        logger.info(f"  Polling Kling job {request_id}...")
        result = _poll_for_result(request_id)
        if result and "video" in result:
            video_url = result["video"].get("url")

    if not video_url:
        logger.error(f"No video URL from Kling for scene {scene_index}")
        return None

    ok = _download_clip(video_url, output_path)
    return output_path if ok else None


def generate_all_ai_footage(scenes: list, video_id: str, niche: str = "") -> list:
    """
    Generate AI video clips for all scenes.
    Sets scene["footage_paths"] = [clip_path] or [] on failure.
    Falls back gracefully — failed scenes will use Pexels in footage_fetcher.
    """
    if not FAL_KEY:
        logger.warning("FAL_KEY not set — skipping AI footage generation")
        return scenes

    logger.info(f"🤖 Generating AI footage via Kling for {len(scenes)} scenes (niche: {niche})")

    for i, scene in enumerate(scenes):
        clip_path = generate_ai_clip(scene, video_id, i + 1, niche=niche)
        if clip_path and os.path.exists(clip_path):
            scene["footage_paths"] = [clip_path]
            scene["footage_source"] = "ai_kling"
            logger.info(f"  Scene {i+1}: AI clip ready → {os.path.basename(clip_path)}")
        else:
            logger.warning(f"  Scene {i+1}: AI clip failed — will fallback to Pexels")
            scene["footage_paths"]  = []   # footage_fetcher will fill this
            scene["footage_source"] = "pexels_fallback"

    return scenes


# ── Cost estimator ─────────────────────────────────────────────────────────────

def estimate_cost(num_scenes: int, duration_sec: int = 5) -> dict:
    """Estimate Kling API cost for a video."""
    cost_per_sec = 0.004   # ~$0.004/sec for Kling Standard via fal.ai
    total_sec    = num_scenes * duration_sec
    total_cost   = total_sec * cost_per_sec
    return {
        "num_scenes":    num_scenes,
        "clip_duration": duration_sec,
        "total_seconds": total_sec,
        "cost_usd":      round(total_cost, 3),
        "cost_inr":      round(total_cost * 84, 1),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    if not FAL_KEY:
        print("❌ Set FAL_KEY=<key> in .env to use AI footage generation")
        print("   Get a key at: https://fal.ai/dashboard/keys")
    else:
        print(f"✅ FAL_KEY set — Kling v1.6 ready")
        est = estimate_cost(12)
        print(f"   Cost estimate for 12-scene video: ${est['cost_usd']} (₹{est['cost_inr']})")
