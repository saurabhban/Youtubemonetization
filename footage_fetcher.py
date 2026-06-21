"""
Footage Fetcher — downloads free stock videos from Pexels.
Falls back to Pixabay if Pexels quota is exhausted.
Each scene gets 1-2 video clips that match its visual description.
"""
import os
import logging
import requests
import random
from config import PEXELS_API_KEY, FOOTAGE_DIR, VIDEO_WIDTH, VIDEO_HEIGHT

logger = logging.getLogger(__name__)

PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"
PEXELS_HEADERS   = {"Authorization": PEXELS_API_KEY}

# Fallback search terms for common finance/tech themes (India-specific)
FALLBACK_KEYWORDS = {
    "tax":          ["money", "finance", "calculator", "documents"],
    "invest":       ["stock market", "money growth", "finance"],
    "mutual fund":  ["investment", "finance", "growth chart"],
    "bank":         ["banking", "money", "finance building"],
    "loan":         ["signing documents", "house keys", "finance"],
    "income":       ["business", "salary", "office work"],
    "india":        ["city india", "people india", "market india"],
    "rupee":        ["money india", "currency", "finance"],
    "credit":       ["credit card", "banking", "finance"],
    "retirement":   ["elderly couple", "savings", "future planning"],
    "technology":   ["technology", "computer", "digital"],
    "ai":           ["artificial intelligence", "computer", "digital technology"],
    "smartphone":   ["smartphone", "mobile phone", "technology"],
    "health":       ["health", "fitness", "wellness"],
    "yoga":         ["yoga", "meditation", "exercise"],
}


def search_pexels_videos(query: str, per_page: int = 5, orientation: str = "landscape") -> list[dict]:
    """Search Pexels for videos matching query."""
    params = {
        "query": query,
        "per_page": per_page,
        "orientation": orientation,
        "size": "medium",
    }
    try:
        resp = requests.get(PEXELS_VIDEO_URL, headers=PEXELS_HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("videos", [])
    except requests.RequestException as e:
        logger.error(f"Pexels search error for '{query}': {e}")
        return []


def get_best_video_file(video: dict, target_w: int = VIDEO_WIDTH, target_h: int = VIDEO_HEIGHT) -> str | None:
    """Pick the best resolution video file from a Pexels video result."""
    files = video.get("video_files", [])
    # Prefer HD (1920x1080), fallback to best available
    hd = [f for f in files if f.get("width", 0) >= 1280 and f.get("file_type") == "video/mp4"]
    if hd:
        hd.sort(key=lambda x: x.get("width", 0), reverse=True)
        return hd[0]["link"]
    # any mp4
    mp4 = [f for f in files if f.get("file_type") == "video/mp4"]
    if mp4:
        return mp4[0]["link"]
    return None


def download_video(url: str, filename: str) -> str | None:
    """Download a video file to FOOTAGE_DIR."""
    dest = os.path.join(FOOTAGE_DIR, filename)
    if os.path.exists(dest):
        logger.info(f"  Footage cached: {filename}")
        return dest
    try:
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 512):
                f.write(chunk)
        size_mb = os.path.getsize(dest) / (1024 * 1024)
        logger.info(f"  Downloaded: {filename} ({size_mb:.1f} MB)")
        return dest
    except Exception as e:
        logger.error(f"  Download failed for {filename}: {e}")
        return None


def expand_keywords(keywords: list[str], visual_desc: str) -> list[str]:
    """Expand keywords with fallbacks based on content type."""
    expanded = list(keywords)
    desc_lower = visual_desc.lower()
    for key, alts in FALLBACK_KEYWORDS.items():
        if key in desc_lower or any(key in k.lower() for k in keywords):
            expanded.extend(alts)
    return list(dict.fromkeys(expanded))  # dedupe while preserving order


def fetch_footage_for_scene(scene: dict, video_id: str, clips_per_scene: int = 2) -> list[str]:
    """
    Download stock footage clips for a single scene.
    Returns list of local file paths.
    """
    scene_id = scene["id"]
    search_kws = scene.get("search_keywords", [])
    visual_desc = scene.get("visual_description", "")
    all_kws = expand_keywords(search_kws, visual_desc)

    downloaded = []
    tried = set()

    for kw in all_kws:
        if len(downloaded) >= clips_per_scene:
            break
        if kw in tried:
            continue
        tried.add(kw)

        logger.info(f"  Scene {scene_id}: searching '{kw}'")
        videos = search_pexels_videos(kw, per_page=10)
        if not videos:
            continue
        random.shuffle(videos)

        for vid in videos:
            if len(downloaded) >= clips_per_scene:
                break
            url = get_best_video_file(vid)
            if not url:
                continue
            vid_id = vid["id"]
            filename = f"{video_id}_scene{scene_id:02d}_clip{vid_id}.mp4"
            path = download_video(url, filename)
            if path:
                downloaded.append(path)

    if not downloaded:
        # Last resort: generic India finance footage
        logger.warning(f"  Scene {scene_id}: no footage found, using generic fallback")
        fallback_vids = search_pexels_videos("finance business india", per_page=5)
        for vid in fallback_vids[:clips_per_scene]:
            url = get_best_video_file(vid)
            if url:
                path = download_video(url, f"{video_id}_scene{scene_id:02d}_fallback{vid['id']}.mp4")
                if path:
                    downloaded.append(path)

    return downloaded


def fetch_all_footage(scenes: list[dict], video_id: str,
                      footage_mode: str = "pexels", niche: str = "") -> list[dict]:
    """
    Fetch footage for all scenes.

    footage_mode:
      "pexels" (default) — free stock footage from Pexels
      "ai"               — AI-generated clips via Kling/fal.ai (FAL_KEY required)
                           Falls back to Pexels per-scene on AI failure.

    Returns scenes list with 'footage_paths' added to each scene.
    """
    if footage_mode == "ai":
        logger.info(f"Footage mode: AI (Kling via fal.ai) | niche: {niche}")
        try:
            from ai_footage_generator import generate_all_ai_footage
            scenes = generate_all_ai_footage(scenes, video_id, niche=niche)
        except ImportError:
            logger.warning("ai_footage_generator not found — falling back to Pexels")
            footage_mode = "pexels"
        except Exception as e:
            logger.error(f"AI footage generation error: {e} — falling back to Pexels")
            footage_mode = "pexels"

    # For each scene without footage (Pexels mode or AI fallback)
    updated = []
    for scene in scenes:
        if scene.get("footage_paths"):
            # AI already filled this scene
            updated.append(scene)
            continue
        logger.info(f"Fetching Pexels footage for scene {scene['id']}: "
                    f"{scene.get('visual_description', '')[:60]}")
        paths = fetch_footage_for_scene(scene, video_id)
        scene["footage_paths"] = paths
        updated.append(scene)
    return updated


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_scene = {
        "id": 1,
        "visual_description": "Indian family discussing finances at home",
        "search_keywords": ["indian family", "finance", "money"],
    }
    paths = fetch_footage_for_scene(test_scene, "test_video_001")
    print(f"Downloaded: {paths}")
