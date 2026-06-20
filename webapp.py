"""
Web Dashboard — Flask app for managing the video generation pipeline.
Features: topic management, video generation, upload scheduling, analytics.
"""
import os
import json
import uuid
import threading
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from config import CHANNEL_NAME, CHANNEL_NICHE, CHANNEL_LANGUAGE, NICHES, VIDEOS_DIR

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", uuid.uuid4().hex)
logger = logging.getLogger(__name__)

# Track background OAuth flow state
_auth_state = {"running": False, "done": False, "error": None}

# In-memory job tracker (use Redis/DB for production)
JOBS: dict[str, dict] = {}


def run_pipeline_async(job_id: str, topic: str, niche: str, language: str,
                       privacy: str, upload: bool, show_subtitles: bool = False,
                       voice_id: str = None):
    """Run pipeline in background thread, update JOBS dict."""
    from pipeline import VideoGenerationPipeline
    JOBS[job_id]["status"] = "running"

    def on_progress(status):
        JOBS[job_id]["progress"] = status

    pipeline = VideoGenerationPipeline(
        channel_name=CHANNEL_NAME,
        niche=niche,
        language=language,
    )
    result = pipeline.run(
        topic=topic,
        privacy=privacy,
        upload=upload,
        on_progress=on_progress,
        show_subtitles=show_subtitles,
        voice_id=voice_id,
    )
    JOBS[job_id]["result"]  = result
    JOBS[job_id]["status"]  = "done" if result["success"] else "error"
    JOBS[job_id]["updated"] = datetime.now().isoformat()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    return render_template("dashboard.html", channel_name=CHANNEL_NAME)


@app.route("/api/niches")
def get_niches():
    return jsonify({
        k: {
            "description": v["description"],
            "cpm_range":   v["cpm_range"],
            "topic_ideas": v["topic_ideas"],
        }
        for k, v in NICHES.items()
    })


@app.route("/api/generate-topics", methods=["POST"])
def api_generate_topics():
    """Generate fresh topic ideas for a niche using AI."""
    data  = request.get_json()
    niche = data.get("niche", CHANNEL_NICHE)
    count = int(data.get("count", 10))
    try:
        from script_generator import generate_topic_ideas
        topics = generate_topic_ideas(niche, count)
        return jsonify({"topics": topics, "niche": niche})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/start-video", methods=["POST"])
def api_start_video():
    """Kick off video generation for a topic."""
    data            = request.get_json()
    topic           = data.get("topic", "").strip()
    niche           = data.get("niche",           CHANNEL_NICHE)
    language        = data.get("language",        CHANNEL_LANGUAGE)
    privacy         = data.get("privacy",         "private")
    upload          = data.get("upload",          True)
    show_subtitles  = data.get("show_subtitles",  False)
    voice_id        = data.get("voice_id",        None)

    if not topic:
        return jsonify({"error": "Topic is required"}), 400

    job_id = f"job_{uuid.uuid4().hex[:8]}"
    JOBS[job_id] = {
        "id":       job_id,
        "topic":    topic,
        "niche":    niche,
        "language": language,
        "privacy":  privacy,
        "upload":   upload,
        "status":   "queued",
        "progress": {"step": "queued", "message": "Waiting to start", "progress": 0},
        "result":   None,
        "created":  datetime.now().isoformat(),
        "updated":  datetime.now().isoformat(),
    }

    thread = threading.Thread(
        target=run_pipeline_async,
        args=(job_id, topic, niche, language, privacy, upload, show_subtitles, voice_id),
        daemon=True,
    )
    thread.start()
    return jsonify({"job_id": job_id, "status": "queued"})


@app.route("/api/job/<job_id>")
def api_job_status(job_id: str):
    """Poll job status and progress."""
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({
        "id":       job["id"],
        "topic":    job["topic"],
        "status":   job["status"],
        "progress": job["progress"],
        "result":   {
            k: v for k, v in (job.get("result") or {}).items()
            if k != "script"   # don't send full script in poll
        } if job.get("result") else None,
    })


@app.route("/api/jobs")
def api_list_jobs():
    """List all jobs (newest first)."""
    jobs = sorted(JOBS.values(), key=lambda j: j["created"], reverse=True)
    return jsonify([{
        "id":       j["id"],
        "topic":    j["topic"],
        "niche":    j["niche"],
        "status":   j["status"],
        "progress": j["progress"].get("progress", 0),
        "created":  j["created"],
        "youtube_url": (j.get("result") or {}).get("youtube_url"),
        "video_path":  (j.get("result") or {}).get("video_path"),
    } for j in jobs])


@app.route("/api/videos")
def api_list_videos():
    """List previously generated videos from disk."""
    from pipeline import list_generated_videos
    return jsonify(list_generated_videos())


@app.route("/api/channel-info")
def api_channel_info():
    """Get YouTube channel stats."""
    try:
        from youtube_uploader import get_channel_info
        info = get_channel_info()
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e), "message": "Connect YouTube first"}), 500


@app.route("/api/youtube-auth-status")
def api_youtube_auth_status():
    from config import YOUTUBE_TOKEN_FILE
    authenticated = os.path.exists(YOUTUBE_TOKEN_FILE)
    channel = {}
    if authenticated:
        try:
            from youtube_uploader import get_channel_info
            channel = get_channel_info()
        except Exception:
            pass
    return jsonify({
        "authenticated": authenticated,
        "channel": channel,
        "auth_running": _auth_state["running"],
        "auth_error": _auth_state["error"],
    })


@app.route("/api/youtube-auth", methods=["POST"])
def api_youtube_auth():
    """Trigger OAuth flow in background thread (opens browser)."""
    global _auth_state
    if _auth_state["running"]:
        return jsonify({"started": True, "message": "Auth already in progress — check your browser."})

    _auth_state = {"running": True, "done": False, "error": None}

    def _run_auth():
        global _auth_state
        try:
            from youtube_uploader import get_credentials
            get_credentials()
            _auth_state = {"running": False, "done": True, "error": None}
        except Exception as e:
            _auth_state = {"running": False, "done": False, "error": str(e)}
            logger.error(f"YouTube auth failed: {e}")

    threading.Thread(target=_run_auth, daemon=True).start()
    return jsonify({"started": True, "message": "Browser should open for Google login. Complete it, then the status will update automatically."})


@app.route("/api/elevenlabs-voices")
def api_elevenlabs_voices():
    """Return available ElevenLabs voices (or fallback Edge TTS voices)."""
    try:
        from tts_engine import list_available_voices
        voices = list_available_voices()
        provider = "elevenlabs" if os.getenv("ELEVENLABS_API_KEY") else "edge_tts"
        return jsonify({"provider": provider, "voices": voices})
    except Exception as e:
        return jsonify({"error": str(e), "voices": []}), 500


@app.route("/api/elevenlabs-status")
def api_elevenlabs_status():
    """Check whether ElevenLabs is configured."""
    key = os.getenv("ELEVENLABS_API_KEY", "")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    return jsonify({
        "configured": bool(key),
        "voice_id": voice_id,
        "key_preview": f"{key[:8]}..." if key else None,
    })


@app.route("/output/videos/<path:filename>")
def serve_video(filename):
    return send_from_directory(VIDEOS_DIR, filename)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "channel": CHANNEL_NAME, "ts": datetime.now().isoformat()})


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import webbrowser
    port = int(os.getenv("PORT", 5000))
    print(f"\n🎬 India YouTube Video Generator")
    print(f"   Dashboard: http://localhost:{port}")
    print(f"   Channel:   {CHANNEL_NAME}\n")
    webbrowser.open(f"http://localhost:{port}")
    app.run(debug=False, host="0.0.0.0", port=port, threaded=True)
