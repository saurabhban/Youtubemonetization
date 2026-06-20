"""
YouTube Uploader — authenticates with YouTube Data API v3 and uploads videos.
Handles OAuth 2.0 flow, sets title/description/tags/category/privacy.
Stores auth token for reuse (no re-login on subsequent uploads).
"""
import os
import json
import logging
import pickle
from pathlib import Path
from config import (
    YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET,
    YOUTUBE_TOKEN_FILE, YOUTUBE_SECRETS_FILE,
    CHANNEL_NAME
)

logger = logging.getLogger(__name__)

try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False
    logger.warning("Google API libraries not installed. Run: pip install google-api-python-client google-auth-oauthlib")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube"]

# YouTube category IDs
CATEGORIES = {
    "Finance":          "27",
    "Education":        "27",
    "Science & Tech":   "28",
    "People & Blogs":   "22",
    "Entertainment":    "24",
    "Howto & Style":    "26",
}

NICHE_TO_CATEGORY = {
    "Personal Finance India": "27",
    "AI & Technology India":  "28",
    "Government Jobs India":  "27",
    "Health & Wellness India":"26",
}

# Niche-specific hashtags & disclaimers for the video description footer
NICHE_FOOTER = {
    "AI & Technology India": (
        "#CloudComputing #AWSIndia #DevOps #ArtificialIntelligence #TechIndia #CloudSignalHQ\n\n"
        "⚠️ Disclaimer: Tech certifications and job market data mentioned are based on publicly available "
        "information. Salary figures are approximate industry averages."
    ),
    "Personal Finance India": (
        "#IndiaFinance #MoneyTips #PersonalFinance #Investment #India2026 #CloudSignalHQ\n\n"
        "⚠️ Disclaimer: This video is for educational purposes only and does not constitute financial advice. "
        "Please consult a SEBI-registered financial advisor before investing."
    ),
    "Government Jobs India": (
        "#SarkariNaukri #GovernmentJobs #UPSC #SSC #BankPO #CloudSignalHQ\n\n"
        "⚠️ Disclaimer: Exam information is based on official notifications. Always verify from official websites."
    ),
    "Health & Wellness India": (
        "#HealthIndia #Ayurveda #Wellness #Yoga #IndianDiet #CloudSignalHQ\n\n"
        "⚠️ Disclaimer: Health information in this video is for general awareness only. "
        "Consult a qualified doctor before making any health decisions."
    ),
}


def get_credentials() -> "Credentials | None":
    """Get or refresh YouTube OAuth2 credentials."""
    if not GOOGLE_LIBS_AVAILABLE:
        raise RuntimeError("Google API libraries not installed")

    creds = None

    # Load saved token
    if os.path.exists(YOUTUBE_TOKEN_FILE):
        with open(YOUTUBE_TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    # Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(YOUTUBE_TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
        return creds

    if creds and creds.valid:
        return creds

    # First-time OAuth flow
    if not os.path.exists(YOUTUBE_SECRETS_FILE):
        # Create from env vars if secrets file doesn't exist
        secrets = {
            "installed": {
                "client_id": YOUTUBE_CLIENT_ID,
                "client_secret": YOUTUBE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
            }
        }
        with open(YOUTUBE_SECRETS_FILE, "w") as f:
            json.dump(secrets, f)

    flow = InstalledAppFlow.from_client_secrets_file(YOUTUBE_SECRETS_FILE, SCOPES)
    creds = flow.run_local_server(port=8080, prompt="consent")

    with open(YOUTUBE_TOKEN_FILE, "wb") as f:
        pickle.dump(creds, f)

    return creds


def build_youtube_service():
    """Build authenticated YouTube API service."""
    creds = get_credentials()
    return build("youtube", "v3", credentials=creds)


def _build_tags(script_tags: list, niche: str) -> list:
    """
    Merge script-generated tags with channel baseline tags.
    YouTube accepts up to 500 characters total; we trim by char count.
    """
    # Channel-level baseline tags always included
    base_tags = [
        "cloudsignalhq", "cloud signal", "india tech", "tech india 2026",
        "cloud computing india", "indian developer", "tech career india",
    ]
    all_tags = list(dict.fromkeys(script_tags + base_tags))  # dedupe, preserve order

    # Trim to YouTube's 500-char limit (tags joined by comma+space)
    selected, total = [], 0
    for tag in all_tags:
        cost = len(tag) + (2 if selected else 0)  # comma+space separator
        if total + cost > 490:
            break
        selected.append(tag)
        total += cost

    logger.info(f"Tags: {len(selected)} tags, {total} chars")
    return selected


def upload_video(
    video_path: str,
    script: dict,
    niche: str = "AI & Technology India",
    privacy: str = "private",
    publish_at: str = None,
    made_for_kids: bool = False,
    thumbnail_path: str = None,
) -> dict:
    """
    Upload a video to YouTube with SEO-optimized metadata and optional thumbnail.

    Args:
        video_path:     Local path to the .mp4 file
        script:         Script dict with title, description, tags from AI
        niche:          Channel niche for category/footer mapping
        privacy:        Privacy status ("private"|"unlisted"|"public")
        publish_at:     ISO 8601 scheduled publish time
        made_for_kids:  Whether content is for children
        thumbnail_path: Path to custom thumbnail JPEG (optional — uploaded after video)

    Returns:
        dict with video_id, url, and upload metadata
    """
    if not GOOGLE_LIBS_AVAILABLE:
        raise RuntimeError("Google API libraries not installed")

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    title       = script.get("title", "Untitled Video")[:100]
    raw_desc    = script.get("description", "")
    raw_tags    = script.get("tags", [])
    category_id = NICHE_TO_CATEGORY.get(niche, "28")

    # ── Build full description ───────────────────────────────────────
    niche_footer = NICHE_FOOTER.get(niche, (
        "#India #Education #CloudSignalHQ\n\n"
        "⚠️ This video is for educational purposes only."
    ))
    full_description = (
        raw_desc.strip()
        + "\n\n"
        + "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        + f"📌 {CHANNEL_NAME} — India's #1 channel for cloud & AI careers.\n"
        + "🔔 Subscribe & hit the bell icon — new videos every week!\n"
        + "💬 Drop your question in the comments below!\n"
        + "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        + niche_footer
    )[:5000]

    # ── Build tags ───────────────────────────────────────────────────
    tags = _build_tags(raw_tags, niche)

    body = {
        "snippet": {
            "title":           title,
            "description":     full_description,
            "tags":            tags,
            "categoryId":      category_id,
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus":           privacy,
            "madeForKids":             made_for_kids,
            "selfDeclaredMadeForKids": made_for_kids,
        },
    }

    if publish_at and privacy == "private":
        body["status"]["publishAt"] = publish_at

    size_mb = os.path.getsize(video_path) / (1024 * 1024)
    logger.info(f"Uploading: '{title}' ({size_mb:.1f} MB) | {len(tags)} tags")

    youtube = build_youtube_service()

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 8,   # 8 MB chunks
    )

    req = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        upload_status, response = req.next_chunk()
        if upload_status:
            pct = int(upload_status.progress() * 100)
            logger.info(f"  Upload progress: {pct}%")

    video_id  = response.get("id")
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    logger.info(f"✅ Uploaded successfully: {video_url}")

    # ── Auto-upload thumbnail ────────────────────────────────────────
    thumb_ok = False
    if thumbnail_path and os.path.exists(thumbnail_path):
        logger.info(f"Uploading thumbnail: {thumbnail_path}")
        thumb_ok = set_thumbnail(video_id, thumbnail_path)
    else:
        logger.info("No thumbnail provided — skipping thumbnail upload")

    return {
        "video_id":        video_id,
        "url":             video_url,
        "title":           title,
        "privacy":         privacy,
        "category_id":     category_id,
        "tags_count":      len(tags),
        "thumbnail_set":   thumb_ok,
        "response":        response,
    }


def set_thumbnail(video_id: str, thumbnail_path: str) -> bool:
    """Upload a custom thumbnail for an uploaded video."""
    if not os.path.exists(thumbnail_path):
        logger.warning(f"Thumbnail not found: {thumbnail_path}")
        return False

    youtube = build_youtube_service()
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg"),
        ).execute()
        logger.info(f"✅ Thumbnail set for video {video_id}")
        return True
    except Exception as e:
        logger.error(f"Thumbnail upload failed: {e}")
        return False


def get_channel_info() -> dict:
    """Get info about the authenticated channel."""
    youtube = build_youtube_service()
    resp = youtube.channels().list(part="snippet,statistics", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        return {}
    ch = items[0]
    return {
        "id":          ch["id"],
        "name":        ch["snippet"]["title"],
        "subscribers": ch["statistics"].get("subscriberCount", "0"),
        "views":       ch["statistics"].get("viewCount", "0"),
        "videos":      ch["statistics"].get("videoCount", "0"),
    }


def list_recent_uploads(max_results: int = 10) -> list[dict]:
    """List recently uploaded videos on the channel."""
    youtube = build_youtube_service()
    # Get uploads playlist
    ch = youtube.channels().list(part="contentDetails", mine=True).execute()
    playlist_id = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    items = youtube.playlistItems().list(
        part="snippet",
        playlistId=playlist_id,
        maxResults=max_results,
    ).execute().get("items", [])

    return [{
        "title":      i["snippet"]["title"],
        "video_id":   i["snippet"]["resourceId"]["videoId"],
        "url":        f"https://youtube.com/watch?v={i['snippet']['resourceId']['videoId']}",
        "published":  i["snippet"]["publishedAt"],
    } for i in items]


def revoke_auth():
    """Remove stored OAuth token (force re-login next time)."""
    if os.path.exists(YOUTUBE_TOKEN_FILE):
        os.remove(YOUTUBE_TOKEN_FILE)
        logger.info("YouTube auth token removed. Next upload will require re-authentication.")
