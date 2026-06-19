# 🎬 India Faceless YouTube Video Generator

Fully automated faceless YouTube video pipeline for Indian audiences. Type a topic → get a monetization-ready MP4 uploaded to your channel in 5–15 minutes.

**Best niche:** Personal Finance India (CPM ₹100–₹250 — highest in India)

---

## What It Does

1. **Claude AI** writes an 8-minute SEO-optimized script (Indian examples, INR amounts, SEBI/RBI references)
2. **Microsoft Edge TTS** generates free neural voiceover (`en-IN-NeerjaNeural` or `hi-IN-SwaraNeural`)
3. **Pexels API** downloads matching stock footage clips (free)
4. **FFmpeg + Pillow** assembles: title card → scenes with captions → branded outro
5. **YouTube Data API v3** uploads the final MP4 directly to your channel

---

## Tech Stack

| Component | Technology | Cost |
|-----------|-----------|------|
| Script generation | Claude Haiku (Anthropic) | ~₹1–2/video |
| Voiceover | Microsoft Edge TTS | Free |
| Stock footage | Pexels API | Free |
| Video assembly | FFmpeg + Pillow | Free |
| Upload | YouTube Data API v3 | Free |
| Dashboard | Flask (Python) | Free |

---

## Prerequisites

- Python 3.10+ (tested on 3.14)
- FFmpeg (ARM64 on Apple Silicon: `arch -arm64 brew install ffmpeg`)
- Git

---

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/saurabhban/Youtubemonetization.git
cd Youtubemonetization
```

### 2. Create virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install anthropic Pillow       # ensure these are present
```

### 3. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in:

```env
ANTHROPIC_API_KEY=sk-ant-...          # https://console.anthropic.com
PEXELS_API_KEY=...                    # https://www.pexels.com/api/
YOUTUBE_CLIENT_ID=...                 # Google Cloud Console
YOUTUBE_CLIENT_SECRET=...             # Google Cloud Console
CHANNEL_NAME=Money Mantra India
CHANNEL_NICHE=Personal Finance India
CHANNEL_LANGUAGE=English
FLASK_SECRET=change-this-secret
PORT=3000
```

### 4. Set up YouTube OAuth

Place your `client_secrets.json` (downloaded from Google Cloud Console) in the project root, then run the one-time auth:

```bash
python -c "from youtube_uploader import get_credentials; get_credentials()"
```

A browser window opens → log in → approve → token saved as `youtube_token.json`.

> **Google Cloud setup:**
> 1. Create project → enable YouTube Data API v3
> 2. Credentials → OAuth 2.0 Client ID → Desktop App → download JSON
> 3. OAuth consent screen → Audience → add your Gmail as test user

### 5. Run the dashboard

```bash
PORT=3000 python webapp.py
```

Open [http://localhost:3000](http://localhost:3000) → pick a topic → click **Generate & Upload**.

---

## CLI Usage

```bash
# Activate venv first
source venv/bin/activate

# Generate + upload (unlisted by default)
python pipeline.py "How to Save Income Tax in India 2026"

# Upload as public
python pipeline.py "Best SIP Funds 2026" --privacy public

# Generate only, no upload (for review)
python pipeline.py "Best SIP Funds 2026" --no-upload

# Hindi video
python pipeline.py "Income Tax Kaise Bachayein 2026" --lang Hindi
```

---

## Project Structure

```
Youtubemonetization/
├── webapp.py               Flask web dashboard (port 3000)
├── pipeline.py             Full pipeline orchestrator + CLI
├── script_generator.py     Claude AI script writing
├── tts_engine.py           Edge-TTS voiceover (free)
├── footage_fetcher.py      Pexels stock video download
├── video_assembler.py      FFmpeg + Pillow video assembly
├── youtube_uploader.py     YouTube Data API v3 upload
├── config.py               All settings, niche definitions
├── templates/
│   └── dashboard.html      Dark navy/saffron UI
├── assets/
│   ├── bgm/                Add .mp3 background music here
│   └── fonts/              NotoSans-Bold.ttf (auto-downloaded)
├── output/
│   ├── videos/             Final MP4 files
│   ├── audio/              TTS audio files (.mp3)
│   └── footage/            Downloaded stock clips
├── logs/
│   └── app.log             Application logs
├── .env                    Your API keys (never commit!)
├── .env.example            Template
├── client_secrets.json     Google OAuth (never commit!)
├── youtube_token.json      OAuth token (auto-generated, never commit!)
└── requirements.txt        Python packages
```

---

## Niches & CPM

| Niche | CPM (India) | Recommended |
|-------|------------|-------------|
| Personal Finance India | ₹100–₹250 | ⭐ Best |
| Stock Market & Trading | ₹80–₹200 | ⭐ Great |
| Tech & AI India | ₹60–₹150 | Good |
| Health & Wellness India | ₹40–₹100 | Moderate |

---

## Monetization Roadmap

```
Week 1–2:   Post 3–4 videos on Personal Finance India
Week 3–4:   Target 100 subscribers + watch time
Month 2–3:  Apply for YouTube Partner Program
             → Need: 1,000 subs + 4,000 watch hours
Month 3+:   Earn ₹100–250 per 1,000 views
             At 50,000 views/month = ₹5,000–₹12,500
```

**Tip:** This app generates a video in 5–15 minutes. Post 4–5 per week consistently.

---

## Cost Per Video

| Component | Cost |
|-----------|------|
| Claude Haiku script | ~₹1–2 |
| Edge TTS voiceover | Free |
| Pexels footage | Free |
| FFmpeg assembly | Free |
| YouTube upload | Free |
| **Total** | **~₹1–2 only** |

---

## Optional Enhancements

- Add `.mp3` files to `assets/bgm/` for background music
- ElevenLabs API for more natural voices
- Custom thumbnail generator (Pillow template)
- Multi-channel support (different `.env` per client)
- YouTube Shorts generator (60-sec vertical)
- Deploy on DigitalOcean/AWS → sell as SaaS at ₹999/month

---

## Security

Files that must **never** be committed to git (already in `.gitignore`):
- `.env`
- `client_secrets.json`
- `youtube_token.json`

---

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for a full list of errors and fixes.

---

## License

MIT — free to use, modify, and sell.
