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


def upload_video(
    video_path: str,
    script: dict,
    niche: str = "Personal Finance India",
    privacy: str = "private",   # "private" | "unlisted" | "public"
    publish_at: str = None,     # ISO 8601 for scheduled publish
    made_for_kids: bool = False,
) -> dict:
    """
    Upload a video to YouTube.

    Args:
        video_path: Local path to the .mp4 file
        script: Script dict with title, description, tags
        niche: Channel niche for category mapping
        privacy: Privacy status
        publish_at: Schedule publish time (ISO 8601 UTC)
        made_for_kids: Whether content is for children

    Returns:
        dict with video_id, url, and upload metadata
    """
    if not GOOGLE_LIBS_AVAILABLE:
        raise RuntimeError("Google API libraries not installed")

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    title       = script.get("title", "Untitled Video")[:100]
    description = script.get("description", "")[:5000]
    tags        = script.get("tags", [])[:500]   # YouTube max 500 chars total
    category_id = NICHE_TO_CATEGORY.get(niche, "27")

    # Build description with standard footer
    full_description = f"""{description}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 {CHANNEL_NAME} — India's go-to channel for smart money moves.
🔔 Subscribe & hit the bell icon for weekly videos!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

#IndiaFinance #MoneyTips #PersonalFinance #Investment #India2026

⚠️ Disclaimer: This video is for educational purposes only and does not constitute financial advice. Please consult a SEBI-registered financial advisor before investing.
"""

    body = {
        "snippet": {
            "title":       title,
            "description": full_description[:5000],
            "tags":        tags,
            "categoryId":  category_id,
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus":        privacy,
            "madeForKids":          made_for_kids,
            "selfDeclaredMadeForKids": made_for_kids,
        },
    }

    # Scheduled publish
    if publish_at and privacy == "private":
        body["status"]["publishAt"] = publish_at
        body["status"]["privacyStatus"] = "private"

    logger.info(f"Uploading: '{title}' ({os.path.getsize(video_path)/(1024*1024):.1f} MB)")

    youtube = build_youtube_service()

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 8,   # 8 MB chunks
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            logger.info(f"  Upload progress: {pct}%")

    video_id  = response.get("id")
    video_url = f"https://www.youtube.com/watch?v={video_id}"

    logger.info(f"✅ Uploaded successfully: {video_url}")

    return {
        "video_id":     video_id,
        "url":          video_url,
        "title":        title,
        "privacy":      privacy,
        "category_id":  category_id,
        "response":     response,
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
