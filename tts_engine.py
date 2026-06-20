"""
TTS Engine — Microsoft Edge TTS (100% free, high-quality neural voices).
Converts script narration text to .mp3 audio files per scene.

Key features:
  - SSML sentence-level breaks for natural pauses
  - Slightly slower rate (-5%) for clear Indian English delivery
  - Proper paragraph breathing room
"""
import asyncio
import os
import re
import logging
import json
import subprocess
import edge_tts
from config import TTS_VOICES, TTS_VOLUME, AUDIO_DIR, CHANNEL_LANGUAGE

logger = logging.getLogger(__name__)

# Slightly slower than default — sounds more professional and clearer
TTS_RATE_DEFAULT = "-5%"


# ── SSML preprocessing ─────────────────────────────────────────────────────

def _escape_xml(text: str) -> str:
    """Escape characters that break SSML XML."""
    text = text.replace("&", "and")
    text = text.replace("<", "")
    text = text.replace(">", "")
    text = text.replace('"', "'")
    return text


def _text_to_ssml(text: str, rate: str = TTS_RATE_DEFAULT) -> str:
    """
    Convert plain narration text to SSML with natural pauses.

    Rules:
      . ! ?   → 650ms break  (sentence end)
      —  …    → 400ms break  (dramatic pause)
      ,  ;    → 200ms break  (clause boundary)
      :       → 300ms break  (list intro / explanation)
      \\n\\n  → 800ms break  (paragraph)
    """
    text = _escape_xml(text.strip())

    # Paragraph breaks first (double newline)
    text = re.sub(r'\n\s*\n', ' <break time="800ms"/> ', text)
    # Single newline → short pause
    text = re.sub(r'\n', ' <break time="400ms"/> ', text)

    # Sentence endings — but don't break on abbreviations (Mr. Dr. vs. etc.)
    # Only break when followed by a space + capital letter or end of string
    text = re.sub(r'([.!?])(\s+)(?=[A-Z"\'(])', r'\1<break time="650ms"/>\2', text)
    text = re.sub(r'([.!?])\s*$', r'\1<break time="650ms"/>', text)

    # Em dash / ellipsis — dramatic pause
    text = re.sub(r'[—–]\s*', ' <break time="400ms"/> ', text)
    text = re.sub(r'\.\.\.\s*', '<break time="400ms"/> ', text)

    # Colons introducing lists or explanations
    text = re.sub(r':\s+', ': <break time="300ms"/> ', text)

    # Commas and semicolons (short breath)
    text = re.sub(r'([,;])\s+', r'\1 <break time="200ms"/> ', text)

    # Numbers with units — add space so they sound natural
    text = re.sub(r'(\d)(lakh|crore|thousand|million|billion)', r'\1 \2', text, flags=re.IGNORECASE)
    text = re.sub(r'₹(\d)', r'rupees \1', text)

    ssml = (
        f'<speak>'
        f'<prosody rate="{rate}" pitch="+0Hz">'
        f'{text}'
        f'</prosody>'
        f'</speak>'
    )
    return ssml


# ── Core TTS call ───────────────────────────────────────────────────────────

async def _synthesize(ssml: str, voice: str, output_path: str, volume: str):
    """Internal async TTS call using SSML."""
    communicate = edge_tts.Communicate(ssml, voice, volume=volume)
    await communicate.save(output_path)


def text_to_speech(
    text: str,
    output_filename: str,
    language: str = None,
    voice_gender: str = "female",
    rate: str = None,
    volume: str = None,
) -> str:
    """
    Convert narration text to speech and save as .mp3.
    Automatically wraps text in SSML for natural pauses.
    Returns path to the generated audio file.
    """
    lang   = language or CHANNEL_LANGUAGE
    rate   = rate or TTS_RATE_DEFAULT
    volume = volume or TTS_VOLUME

    # Voice selection
    if lang == "Hindi":
        voice_key = "Hindi_M" if voice_gender == "male" else "Hindi"
    elif lang in ("English", "Hinglish"):
        voice_key = "English_M" if voice_gender == "male" else "English"
    else:
        voice_key = "English"

    voice = TTS_VOICES[voice_key]

    output_path = os.path.join(AUDIO_DIR, output_filename)
    if not output_path.endswith(".mp3"):
        output_path += ".mp3"

    ssml = _text_to_ssml(text, rate=rate)

    logger.info(f"TTS: voice={voice} | rate={rate} | chars={len(text)} → {output_filename}")
    asyncio.run(_synthesize(ssml, voice, output_path, volume))
    return output_path


# ── Duration helper ─────────────────────────────────────────────────────────

def get_audio_duration(audio_path: str) -> float:
    """Return duration of audio file in seconds using ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", audio_path],
        capture_output=True, text=True,
    )
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except Exception:
        return 0.0


# ── Scene-level batch generation ────────────────────────────────────────────

def generate_scene_audio(scenes: list, video_id: str, language: str = None) -> list:
    """
    Generate TTS audio for every scene.
    Returns the scenes list with 'audio_path' and 'actual_duration_sec' added.
    """
    lang = language or CHANNEL_LANGUAGE
    updated = []

    for scene in scenes:
        sid       = scene["id"]
        narration = scene.get("narration", "").strip()

        if not narration:
            logger.warning(f"Scene {sid} has no narration — skipping TTS")
            scene["audio_path"]         = None
            scene["actual_duration_sec"] = 0
            updated.append(scene)
            continue

        filename   = f"{video_id}_scene_{sid:02d}.mp3"
        audio_path = text_to_speech(narration, filename, language=lang)
        duration   = get_audio_duration(audio_path)

        scene["audio_path"]          = audio_path
        scene["actual_duration_sec"] = round(duration, 2)
        logger.info(f"  Scene {sid}: {duration:.1f}s audio")
        updated.append(scene)

    return updated


# ── Misc ────────────────────────────────────────────────────────────────────

def generate_hook_audio(hook_text: str, video_id: str, language: str = None) -> str:
    return text_to_speech(hook_text, f"{video_id}_hook.mp3", language=language)


def generate_outro_audio(outro_text: str, video_id: str, language: str = None) -> str:
    return text_to_speech(outro_text, f"{video_id}_outro.mp3", language=language)


def list_available_voices() -> list:
    async def _list():
        voices = await edge_tts.list_voices()
        return [v for v in voices if "IN" in v.get("ShortName", "")]
    return asyncio.run(_list())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sample = (
        "Namaste! Welcome to CloudSignalHQ. "
        "Today, we're going to answer one of the most common questions I get: "
        "AWS, Azure, or Google Cloud — which one should you learn in 2026? "
        "Stick around, because by the end of this video, you'll have a clear answer. "
        "Let's dive in."
    )
    path = text_to_speech(sample, "test_tts.mp3", language="English")
    print(f"Generated: {path} | Duration: {get_audio_duration(path):.1f}s")
