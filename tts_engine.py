"""
TTS Engine — ElevenLabs (primary, human-quality) + Edge TTS (fallback, free).

Priority:
  1. ElevenLabs — if ELEVENLABS_API_KEY is set in .env → human-quality voice
  2. Edge TTS   — free Microsoft neural fallback (en-IN-NeerjaNeural)

ElevenLabs voice settings per niche:
  Tech/Education : stability=0.55, similarity=0.80, style=0.20  → clear, professional
  Horror Stories : stability=0.40, similarity=0.75, style=0.55  → dramatic, tense
  Motivational   : stability=0.50, similarity=0.80, style=0.45  → warm, inspiring
  True Crime     : stability=0.60, similarity=0.75, style=0.35  → measured, serious
  Mythology      : stability=0.45, similarity=0.80, style=0.50  → epic, grand
"""
import asyncio
import os
import re
import logging
import json
import subprocess
import requests
import edge_tts
from config import TTS_VOICES, TTS_VOLUME, AUDIO_DIR, CHANNEL_LANGUAGE, STORY_NICHES

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
ELEVENLABS_API_KEY  = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel default
ELEVENLABS_MODEL    = "eleven_multilingual_v2"
ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"

TTS_RATE_DEFAULT    = "-5%"   # Edge TTS rate (not used for ElevenLabs)

# Voice settings per niche — controls delivery character
_NICHE_VOICE_SETTINGS = {
    "Horror Stories India":      {"stability": 0.40, "similarity_boost": 0.75, "style": 0.55, "use_speaker_boost": True},
    "Motivational Stories India": {"stability": 0.50, "similarity_boost": 0.80, "style": 0.45, "use_speaker_boost": True},
    "True Crime India":          {"stability": 0.60, "similarity_boost": 0.75, "style": 0.35, "use_speaker_boost": True},
    "Indian Mythology & History": {"stability": 0.45, "similarity_boost": 0.80, "style": 0.50, "use_speaker_boost": True},
    # Default (tech/educational)
    "_default":                  {"stability": 0.55, "similarity_boost": 0.80, "style": 0.20, "use_speaker_boost": True},
}


def _voice_settings_for_niche(niche: str) -> dict:
    return _NICHE_VOICE_SETTINGS.get(niche, _NICHE_VOICE_SETTINGS["_default"])


# ── ElevenLabs TTS ─────────────────────────────────────────────────────────────

def _elevenlabs_tts(text: str, output_path: str, voice_id: str = None,
                    niche: str = "") -> bool:
    """
    Call ElevenLabs Text-to-Speech API and save mp3 to output_path.
    Returns True on success, False on failure.
    """
    vid      = voice_id or ELEVENLABS_VOICE_ID
    settings = _voice_settings_for_niche(niche)

    url = f"{ELEVENLABS_BASE_URL}/text-to-speech/{vid}"
    headers = {
        "xi-api-key":   ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept":       "audio/mpeg",
    }
    payload = {
        "text":           text,
        "model_id":       ELEVENLABS_MODEL,
        "voice_settings": settings,
        "output_format":  "mp3_44100_128",
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(resp.content)
            logger.info(f"ElevenLabs TTS: {len(text)} chars → {os.path.basename(output_path)}")
            return True
        else:
            logger.error(f"ElevenLabs API error {resp.status_code}: {resp.text[:300]}")
            return False
    except Exception as e:
        logger.error(f"ElevenLabs TTS exception: {e}")
        return False


def list_elevenlabs_voices() -> list:
    """Fetch available voices from ElevenLabs account."""
    if not ELEVENLABS_API_KEY:
        return []
    try:
        resp = requests.get(
            f"{ELEVENLABS_BASE_URL}/voices",
            headers={"xi-api-key": ELEVENLABS_API_KEY},
            timeout=15,
        )
        if resp.status_code == 200:
            voices = resp.json().get("voices", [])
            return [
                {
                    "voice_id":    v["voice_id"],
                    "name":        v["name"],
                    "category":    v.get("category", ""),
                    "description": v.get("description", ""),
                    "preview_url": v.get("preview_url", ""),
                    "labels":      v.get("labels", {}),
                }
                for v in voices
            ]
    except Exception as e:
        logger.error(f"Failed to fetch ElevenLabs voices: {e}")
    return []


# ── Edge TTS (fallback) ────────────────────────────────────────────────────────

def _escape_xml(text: str) -> str:
    text = text.replace("&", "and")
    text = text.replace("<", "")
    text = text.replace(">", "")
    text = text.replace('"', "'")
    return text


def _text_to_ssml(text: str, rate: str = TTS_RATE_DEFAULT) -> str:
    """
    Minimal SSML for Edge TTS — light pauses only, no paragraph blasts.
    """
    text = _escape_xml(text.strip())
    text = re.sub(r'\n+', ' ', text)

    # Numbers with units
    text = re.sub(r'(\d)(lakh|crore|thousand|million|billion)', r'\1 \2', text, flags=re.IGNORECASE)
    text = re.sub(r'₹(\d)', r'rupees \1', text)

    # Sentence endings
    text = re.sub(r'([.!?])(\s+)(?=[A-Z"\'(])', r'\1<break time="300ms"/>\2', text)
    text = re.sub(r'([.!?])\s*$', r'\1<break time="300ms"/>', text)

    # Em dash / ellipsis
    text = re.sub(r'[—–]\s*', ' <break time="250ms"/> ', text)
    text = re.sub(r'\.\.\.\s*', '<break time="250ms"/> ', text)

    text = re.sub(r':\s+', ': <break time="150ms"/> ', text)
    text = re.sub(r'([,;])\s+', r'\1 <break time="100ms"/> ', text)

    return f'<speak><prosody rate="{rate}" pitch="+0Hz">{text}</prosody></speak>'


async def _edge_synthesize(ssml: str, voice: str, output_path: str, volume: str):
    communicate = edge_tts.Communicate(ssml, voice, volume=volume)
    await communicate.save(output_path)


def _edge_tts(text: str, output_path: str, language: str = None,
              rate: str = None, volume: str = None) -> bool:
    """Fallback TTS using Microsoft Edge neural voices."""
    lang   = language or CHANNEL_LANGUAGE
    rate   = rate or TTS_RATE_DEFAULT
    volume = volume or TTS_VOLUME

    voice_key = "English" if lang not in TTS_VOICES else lang
    if lang == "Hindi":
        voice_key = "Hindi"
    voice = TTS_VOICES.get(voice_key, TTS_VOICES["English"])

    ssml = _text_to_ssml(text, rate=rate)
    try:
        asyncio.run(_edge_synthesize(ssml, voice, output_path, volume))
        logger.info(f"Edge TTS: voice={voice} | {len(text)} chars → {os.path.basename(output_path)}")
        return True
    except Exception as e:
        logger.error(f"Edge TTS failed: {e}")
        return False


# ── Unified TTS entry point ────────────────────────────────────────────────────

def text_to_speech(
    text: str,
    output_filename: str,
    language: str = None,
    voice_gender: str = "female",
    rate: str = None,
    volume: str = None,
    niche: str = "",
    voice_id: str = None,
) -> str:
    """
    Convert narration text to speech and save as .mp3.

    Uses ElevenLabs when ELEVENLABS_API_KEY is set, else falls back to Edge TTS.
    Returns path to the generated audio file.
    """
    output_path = os.path.join(AUDIO_DIR, output_filename)
    if not output_path.endswith(".mp3"):
        output_path += ".mp3"

    if ELEVENLABS_API_KEY:
        ok = _elevenlabs_tts(text, output_path,
                             voice_id=voice_id or ELEVENLABS_VOICE_ID,
                             niche=niche)
        if ok:
            return output_path
        logger.warning("ElevenLabs failed — falling back to Edge TTS")

    # Fallback: Edge TTS
    _edge_tts(text, output_path, language=language, rate=rate, volume=volume)
    return output_path


# ── Duration helper ────────────────────────────────────────────────────────────

def get_audio_duration(audio_path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", audio_path],
        capture_output=True, text=True,
    )
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except Exception:
        return 0.0


# ── Scene-level batch generation ──────────────────────────────────────────────

def generate_scene_audio(scenes: list, video_id: str, language: str = None,
                         tts_rate: str = None, niche: str = "",
                         voice_id: str = None) -> list:
    """
    Generate TTS audio for every scene.
    tts_rate only applies to Edge TTS fallback (ElevenLabs uses voice_settings).
    niche controls ElevenLabs delivery style.
    """
    lang    = language or CHANNEL_LANGUAGE
    rate    = tts_rate or TTS_RATE_DEFAULT
    updated = []

    provider = "ElevenLabs" if ELEVENLABS_API_KEY else "Edge TTS"
    logger.info(f"TTS provider: {provider} | niche: {niche}")

    for scene in scenes:
        sid       = scene["id"]
        narration = scene.get("narration", "").strip()

        if not narration:
            logger.warning(f"Scene {sid} has no narration — skipping TTS")
            scene["audio_path"]          = None
            scene["actual_duration_sec"] = 0
            updated.append(scene)
            continue

        filename   = f"{video_id}_scene_{sid:02d}.mp3"
        audio_path = text_to_speech(
            narration, filename,
            language=lang, rate=rate, niche=niche, voice_id=voice_id,
        )
        duration = get_audio_duration(audio_path)

        scene["audio_path"]          = audio_path
        scene["actual_duration_sec"] = round(duration, 2)
        logger.info(f"  Scene {sid}: {duration:.1f}s audio ({provider})")
        updated.append(scene)

    return updated


# ── Misc ───────────────────────────────────────────────────────────────────────

def generate_hook_audio(hook_text: str, video_id: str, language: str = None) -> str:
    return text_to_speech(hook_text, f"{video_id}_hook.mp3", language=language)


def generate_outro_audio(outro_text: str, video_id: str, language: str = None) -> str:
    return text_to_speech(outro_text, f"{video_id}_outro.mp3", language=language)


def list_available_voices() -> list:
    """Return ElevenLabs voices if key is set, else Edge TTS voices."""
    if ELEVENLABS_API_KEY:
        return list_elevenlabs_voices()
    async def _list():
        voices = await edge_tts.list_voices()
        return [v for v in voices if "IN" in v.get("ShortName", "")]
    return asyncio.run(_list())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    provider = "ElevenLabs" if ELEVENLABS_API_KEY else "Edge TTS (no ElevenLabs key)"
    print(f"TTS provider: {provider}")
    sample = (
        "The clock read 11:47 PM when she heard the first knock. "
        "Three slow taps. Then silence. "
        "She pressed herself against the wall and held her breath."
    )
    path = text_to_speech(sample, "test_tts.mp3", niche="Horror Stories India")
    print(f"Generated: {path} | Duration: {get_audio_duration(path):.1f}s")
