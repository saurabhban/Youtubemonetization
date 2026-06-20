"""
BGM Generator — creates royalty-free ambient background music tracks
using Python stdlib (wave + math). No external dependencies.

Generates 3 tracks:
  ambient_tech.mp3    — deep space drone, slow pulse (tech/AI topics)
  lofi_calm.mp3       — warm lo-fi pads (finance/education topics)
  cinematic_rise.mp3  — building orchestral swell (dramatic topics)

Tracks are ~3 min each, 44100 Hz mono WAV → converted to MP3 via FFmpeg.
Run once: python bgm_generator.py
"""
import math
import random
import struct
import subprocess
import os
import wave
import logging

logger = logging.getLogger(__name__)

SAMPLE_RATE = 44100
DURATION    = 180       # 3 minutes per track
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
BGM_DIR     = os.path.join(BASE_DIR, "assets", "bgm")
os.makedirs(BGM_DIR, exist_ok=True)


# ── Sample-level synthesis ──────────────────────────────────────────────────

def _fade(t: float, total: float, fade_in: float = 3.0, fade_out: float = 5.0) -> float:
    """Linear fade envelope."""
    if t < fade_in:
        return t / fade_in
    if t > total - fade_out:
        return (total - t) / fade_out
    return 1.0


def _sine(freq: float, t: float) -> float:
    return math.sin(2 * math.pi * freq * t)


def _noise(scale: float = 0.015) -> float:
    """Very soft white noise for texture."""
    return random.uniform(-scale, scale)


def _lfo(rate: float, t: float, depth: float = 0.3, offset: float = 1.0) -> float:
    """Low-frequency oscillator for slow amplitude modulation."""
    return offset + depth * math.sin(2 * math.pi * rate * t)


# ── Track definitions ───────────────────────────────────────────────────────

def _sample_ambient_tech(t: float) -> float:
    """
    Deep space drone — fundamental at 55 Hz with harmonics,
    slow LFO at 0.07 Hz, pad shimmer at 880 Hz.
    """
    # Foundation drone (low-end pad)
    s  = 0.45 * _sine(55,    t) * _lfo(0.07, t, depth=0.25)
    s += 0.20 * _sine(110,   t) * _lfo(0.11, t, depth=0.20, offset=0.9)
    s += 0.12 * _sine(165,   t) * _lfo(0.05, t, depth=0.15, offset=0.95)
    # High shimmer
    s += 0.06 * _sine(880,   t) * _lfo(0.13, t, depth=0.5,  offset=0.5)
    s += 0.03 * _sine(1320,  t) * _lfo(0.09, t, depth=0.6,  offset=0.4)
    # Subtle texture
    s += _noise(0.008)
    return s * 0.55


def _sample_lofi_calm(t: float) -> float:
    """
    Warm lo-fi pads — jazz-ish chords implied by 4 tones,
    gentle pulse, soft high-shelf roll-off simulated by weak harmonics.
    """
    # Root chord tones (major 7th feel: C, E, G, B approximated in Hz)
    s  = 0.35 * _sine(261.6, t) * _lfo(0.06, t, depth=0.20)   # C4
    s += 0.28 * _sine(329.6, t) * _lfo(0.08, t, depth=0.22)   # E4
    s += 0.22 * _sine(392.0, t) * _lfo(0.05, t, depth=0.18)   # G4
    s += 0.14 * _sine(493.9, t) * _lfo(0.10, t, depth=0.25)   # B4
    # Warm sub
    s += 0.20 * _sine(130.8, t) * _lfo(0.04, t, depth=0.15, offset=0.92)
    # Very soft vinyl crackle texture
    s += _noise(0.006)
    return s * 0.48


def _sample_cinematic_rise(t: float) -> float:
    """
    Cinematic swell — strings implied by stacked 5ths + slow vibrato,
    builds in intensity over the first 60 s, then sustains.
    """
    build = min(1.0, t / 60.0)  # 0→1 over first 60 seconds

    # String pad (5ths: A2 + E3 + A3)
    vibrato = 1.0 + 0.004 * math.sin(2 * math.pi * 5.5 * t)  # 5.5 Hz vibrato
    s  = 0.40 * _sine(110   * vibrato, t) * _lfo(0.06, t, depth=0.18)
    s += 0.30 * _sine(164.8 * vibrato, t) * _lfo(0.07, t, depth=0.20)
    s += 0.22 * _sine(220   * vibrato, t) * _lfo(0.05, t, depth=0.16)

    # Brass swell that grows with build factor
    s += build * 0.18 * _sine(440, t) * _lfo(0.09, t, depth=0.30, offset=0.7)
    s += build * 0.10 * _sine(330, t) * _lfo(0.08, t, depth=0.28, offset=0.6)

    # Subtle timpani-like low pulse every ~4 s
    pulse_env = max(0.0, 1.0 - ((t % 4.0) / 0.8)) if (t % 4.0) < 0.8 else 0.0
    s += build * 0.12 * _sine(55, t) * pulse_env

    s += _noise(0.007)
    return s * 0.50


# ── WAV writer ──────────────────────────────────────────────────────────────

def _write_wav(path: str, sample_fn, duration: int = DURATION):
    """Write a mono 16-bit WAV by calling sample_fn(t) for each sample."""
    logger.info(f"Generating WAV: {os.path.basename(path)} ({duration}s)...")
    n_samples = duration * SAMPLE_RATE
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)      # 16-bit
        wf.setframerate(SAMPLE_RATE)
        for i in range(n_samples):
            t = i / SAMPLE_RATE
            raw = sample_fn(t) * _fade(t, duration)
            clamped = max(-0.98, min(0.98, raw))
            wf.writeframes(struct.pack("<h", int(clamped * 32767)))
    logger.info(f"  WAV written: {path}")


def _wav_to_mp3(wav_path: str, mp3_path: str) -> bool:
    """Convert WAV to MP3 at 128kbps via FFmpeg."""
    cmd = [
        "ffmpeg", "-y", "-i", wav_path,
        "-codec:a", "libmp3lame", "-b:a", "128k",
        mp3_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"MP3 conversion failed: {result.stderr[-400:]}")
        return False
    os.remove(wav_path)
    logger.info(f"  MP3 ready: {mp3_path}")
    return True


# ── Public API ──────────────────────────────────────────────────────────────

TRACKS = [
    ("ambient_tech.mp3",      _sample_ambient_tech,    "Deep space drone (tech/AI)"),
    ("lofi_calm.mp3",         _sample_lofi_calm,       "Warm lo-fi pads (finance/education)"),
    ("cinematic_rise.mp3",    _sample_cinematic_rise,  "Cinematic swell (dramatic topics)"),
]


def generate_all(force: bool = False) -> list:
    """
    Generate all BGM tracks if not already present.
    Returns list of generated/existing mp3 paths.

    Args:
        force: Re-generate even if files already exist
    """
    generated = []
    for filename, sample_fn, label in TRACKS:
        mp3_path = os.path.join(BGM_DIR, filename)
        if os.path.exists(mp3_path) and not force:
            logger.info(f"BGM already exists, skipping: {filename}")
            generated.append(mp3_path)
            continue

        logger.info(f"Generating track: {label}")
        wav_path = mp3_path.replace(".mp3", "_tmp.wav")
        try:
            _write_wav(wav_path, sample_fn)
            ok = _wav_to_mp3(wav_path, mp3_path)
            if ok:
                generated.append(mp3_path)
            elif os.path.exists(wav_path):
                # Keep WAV if MP3 conversion fails (assembler will skip non-mp3)
                logger.warning(f"Kept WAV (MP3 conversion failed): {wav_path}")
        except Exception as e:
            logger.error(f"Track generation failed for {filename}: {e}")
            if os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except Exception:
                    pass

    return generated


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s"
    )
    print("\n🎵 CloudSignalHQ BGM Generator")
    print(f"   Output dir: {BGM_DIR}\n")
    tracks = generate_all(force=False)
    print(f"\n✅ {len(tracks)} track(s) ready:")
    for t in tracks:
        size_kb = os.path.getsize(t) / 1024
        print(f"   {os.path.basename(t):30s}  {size_kb:.0f} KB")
