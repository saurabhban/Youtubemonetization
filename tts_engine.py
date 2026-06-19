"""
TTS Engine — Microsoft Edge TTS (100% free, high-quality neural voices).
Converts script narration text to .mp3 audio files per scene.
Supports Indian English, Hindi, and Hinglish voices.
"""
import asyncio
import os
import logging
import json
import subprocess
import edge_tts
from config import TTS_VOICES, TTS_RATE, TTS_VOLUME, AUDIO_DIR, CHANNEL_LANGUAGE

logger = logging.getLogger(__name__)


async def _synthesize(text: str, voice: str, output_path: str, rate: str, volume: str):
    """Internal async TTS call."""
    communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
    await communicate.save(output_path)


def text_to_speech(
    text: str,
    output_filename: str,
    language: str = None,
    voice_gender: str = "female",  # "male" | "female"
    rate: str = None,
    volume: str = None,
) -> str:
    """
    Convert text to speech and save as .mp3.
    Returns path to the generated audio file.
    """
    lang = language or CHANNEL_LANGUAGE
    rate = rate or TTS_RATE
    volume = volume or TTS_VOLUME

    # Pick voice
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

    logger.info(f"TTS: voice={voice} | chars={len(text)} | → {output_filename}")
    asyncio.run(_synthesize(text, voice, output_path, rate, volume))
    return output_path


def get_audio_duration(audio_path: str) -> float:
    """Return duration of audio file in seconds using ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", audio_path],
        capture_output=True, text=True
    )
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])


def generate_scene_audio(scenes: list[dict], video_id: str, language: str = None) -> list[dict]:
    """
    Generate TTS audio for all scenes.
    Returns scenes list with 'audio_path' and 'actual_duration_sec' added.
    """
    lang = language or CHANNEL_LANGUAGE
    updated_scenes = []

    for scene in scenes:
        scene_id = scene["id"]
        narration = scene.get("narration", "")
        if not narration.strip():
            logger.warning(f"Scene {scene_id} has no narration, skipping TTS")
            scene["audio_path"] = None
            scene["actual_duration_sec"] = 0
            updated_scenes.append(scene)
            continue

        filename = f"{video_id}_scene_{scene_id:02d}.mp3"
        audio_path = text_to_speech(
            text=narration,
            output_filename=filename,
            language=lang,
        )
        duration = get_audio_duration(audio_path)
        scene["audio_path"] = audio_path
        scene["actual_duration_sec"] = round(duration, 2)
        logger.info(f"  Scene {scene_id}: {duration:.1f}s audio")
        updated_scenes.append(scene)

    return updated_scenes


def generate_hook_audio(hook_text: str, video_id: str, language: str = None) -> str:
    """Generate TTS for the hook/intro separately."""
    filename = f"{video_id}_hook.mp3"
    return text_to_speech(hook_text, filename, language=language)


def generate_outro_audio(outro_text: str, video_id: str, language: str = None) -> str:
    """Generate TTS for the outro/CTA separately."""
    filename = f"{video_id}_outro.mp3"
    return text_to_speech(outro_text, filename, language=language)


def list_available_voices() -> list[dict]:
    """List all available Edge TTS voices (async wrapper)."""
    async def _list():
        voices = await edge_tts.list_voices()
        return [v for v in voices if "IN" in v.get("ShortName", "")]  # Indian voices only

    return asyncio.run(_list())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Quick test
    path = text_to_speech(
        "Namaste! Welcome to Money Mantra India. Aaj hum baat karenge income tax bachane ke baare mein.",
        "test_tts.mp3",
        language="English",
    )
    print(f"Generated: {path} | Duration: {get_audio_duration(path):.1f}s")
