# Troubleshooting Guide

## How to View Logs

### Live logs while running
```bash
PORT=3000 python webapp.py 2>&1 | tee logs/app.log
```

### Tail live log in a second terminal
```bash
tail -f logs/app.log
```

### Filter for errors only
```bash
grep -i error logs/app.log
```

### Filter for a specific job ID (shown in dashboard URL)
```bash
grep "job_abc123" logs/app.log
```

### View last 100 lines
```bash
tail -100 logs/app.log
```

---

## Common Errors & Fixes

---

### ❌ `ModuleNotFoundError: No module named 'anthropic'`

**Cause:** `anthropic` package not installed in the active venv.

**Fix:**
```bash
source venv/bin/activate
pip install anthropic
```

---

### ❌ `json.decoder.JSONDecodeError: Unterminated string`

**Cause:** Claude's response was cut off — `max_tokens` too low for a full script.

**Fix:**
```bash
sed -i '' 's/max_tokens=4000/max_tokens=8192/' script_generator.py
```

---

### ❌ `No module named 'pyaudioop'` / `No module named 'audioop'`

**Cause:** `pydub` uses `audioop`, which was removed in Python 3.13+.

**Fix:** Already patched in `tts_engine.py` — it now uses `ffprobe` for audio duration instead of pydub. If you see this, make sure you have the latest `tts_engine.py` from this repo.

---

### ❌ `[AVFilterGraph] No such filter: 'drawtext'`

**Cause:** FFmpeg was compiled without `libfreetype`, so `drawtext` is unavailable.

**Fix:** Already patched in `video_assembler.py` — text overlays now use Pillow (PIL) to generate PNG images, which are then composited with FFmpeg's `overlay` filter. No freetype needed.

Make sure Pillow is installed:
```bash
pip install Pillow
```

---

### ❌ Port already in use (`Address already in use`)

**Cause:** A previous instance of the app is still running.

**Fix:**
```bash
# Kill whatever is on port 3000
lsof -ti:3000 | xargs kill -9 2>/dev/null
sleep 1
PORT=3000 python webapp.py
```

Change `3000` to whichever port you're using.

---

### ❌ Port 5000 not working (macOS)

**Cause:** macOS AirPlay Receiver uses port 5000.

**Fix:** Use a different port:
```bash
PORT=3000 python webapp.py
```

Or disable AirPlay: System Settings → General → AirDrop & Handoff → AirPlay Receiver → Off.

---

### ❌ FFmpeg not found / `arch` error on Apple Silicon

**Cause:** Wrong FFmpeg binary architecture on M1/M2 Mac.

**Fix:**
```bash
arch -arm64 brew install ffmpeg
```

Verify:
```bash
ffmpeg -version   # should show arm64
```

---

### ❌ YouTube OAuth `403 access_denied`

**Cause:** Your Gmail is not added as a test user in Google Cloud Console.

**Fix:**
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Select your project → APIs & Services → OAuth consent screen
3. Audience → Test users → Add user → enter your Gmail
4. Delete `youtube_token.json` and re-authenticate:
```bash
python -c "from youtube_uploader import get_credentials; get_credentials()"
```

---

### ❌ YouTube OAuth browser conflicts with Flask server

**Cause:** Both Flask and the OAuth flow try to use the same port.

**Fix:** Stop the Flask server first, authenticate, then restart:
```bash
# Stop Flask (Ctrl+C), then:
python -c "from youtube_uploader import get_credentials; get_credentials()"
# Token saved as youtube_token.json
# Now restart Flask:
PORT=3000 python webapp.py
```

---

### ❌ `SyntaxError: invalid syntax` in `script_generator.py`

**Cause:** Old Gemini/OpenAI version of the file with broken f-string syntax.

**Fix:** Ensure `script_generator.py` uses the Claude API version (in this repo). Key indicator of the correct version:
```python
import anthropic
_claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
```

---

### ❌ `RuntimeError: Run: pip install anthropic`

**Cause:** Same as above — old script_generator.py or anthropic not installed.

**Fix:**
```bash
source venv/bin/activate
pip install anthropic
```

---

### ❌ Gemini API key `ACCESS_TOKEN_TYPE_UNSUPPORTED`

**Cause:** Keys starting with `AQ.` are OAuth access tokens, not API keys. Gemini requires an API key from [aistudio.google.com](https://aistudio.google.com).

**Fix:** This project now uses Claude (Anthropic) instead of Gemini. No Gemini key needed.

---

### ❌ OpenAI `429 quota exceeded`

**Cause:** OpenAI free-tier quota exhausted.

**Fix:** This project now uses Claude (Anthropic) instead of OpenAI. No OpenAI key needed.

---

### ❌ `zsh: quote>` prompt (terminal gets stuck)

**Cause:** Pasting a multi-line Python command with unmatched quotes into zsh.

**Fix:** Press `Ctrl+C` to exit, then type commands manually (don't paste multi-line commands).

---

### ❌ `setup.sh` overwrites `.env`

**Cause:** `setup.sh` copies `.env.example` to `.env` if `.env` doesn't exist — but if you run it again it skips. However some editors auto-run it.

**Fix:** After running `setup.sh`, always manually verify `.env` has your real keys:
```bash
cat .env
```

---

### ❌ `webapp.py` file not found with strange characters

**Cause:** Invisible Unicode characters got pasted into the terminal command.

**Fix:** Type the command manually, don't copy-paste:
```
PORT=3000 python webapp.py
```

---

## Viewing the Pipeline in Detail

Each video job has a unique ID (e.g., `job_abc123`). You can monitor it:

### In the dashboard
Open [http://localhost:3000](http://localhost:3000) → click the job row → watch live progress.

### In logs
```bash
grep "job_abc123" logs/app.log
```

### Pipeline stages and their log prefixes
| Stage | Log prefix | What's happening |
|-------|-----------|-----------------|
| Script | `[5%] script:` | Claude writing the video script |
| Audio | `[20%] audio:` | Edge TTS generating voiceover MP3s |
| Footage | `[50%] footage:` | Pexels downloading stock clips |
| Assembly | `[70%] assembly:` | FFmpeg building the video |
| Upload | `[90%] upload:` | YouTube API uploading |
| Done | `[100%] done:` | Video live on YouTube |

---

## Resetting Everything

If things go very wrong, do a clean restart:

```bash
# Kill app
lsof -ti:3000 | xargs kill -9 2>/dev/null

# Clear temp video files (keeps final outputs)
rm -rf output/videos/tmp_*

# Clear audio cache
rm -f output/audio/*.mp3

# Restart
source venv/bin/activate
PORT=3000 python webapp.py 2>&1 | tee logs/app.log
```

---

## Getting Help

1. Check `logs/app.log` first — the error message is almost always there
2. Search this file for the error text
3. If stuck, open an issue on GitHub with the relevant log lines
