"""
Script Generator — uses Claude (Anthropic) API for Indian YouTube content.
Returns structured JSON with title, description, tags, scenes, and thumbnail text.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

try:
    import anthropic
    _claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    logger.info("Using Claude (Anthropic) for script generation")
except ImportError:
    raise RuntimeError("Run: pip install anthropic")


SYSTEM_PROMPT = """You are an expert Indian YouTube script writer specializing in faceless educational videos.
You write engaging, SEO-optimized scripts for the Indian audience.
Your scripts are conversational, use simple language, include Indian examples (INR, Indian banks, SEBI, RBI etc),
and follow the proven Hook-Value-CTA formula.
Always return valid JSON only, no markdown fences, no extra text."""


SCRIPT_TEMPLATE = """Write a complete YouTube video script for the topic: "{topic}"

Channel: {channel_name}
Niche: {niche}
Target Language: {language}
Target Duration: ~{duration} minutes

Return a JSON object with this EXACT structure:
{{
  "title": "SEO-optimized video title (60 chars max)",
  "description": "YouTube description with timestamps and keywords (800 chars)",
  "tags": ["tag1", "tag2"],
  "thumbnail_text": "Short punchy text for thumbnail (4 words max)",
  "thumbnail_subtitle": "Subtitle for thumbnail (5 words max)",
  "hook": "Opening 30-second hook script",
  "scenes": [
    {{
      "id": 1,
      "duration_sec": 45,
      "narration": "Full narration text for this scene",
      "visual_description": "What to show on screen (for stock footage search)",
      "search_keywords": ["keyword1", "keyword2"],
      "on_screen_text": "Key text to display on screen",
      "transition": "cut"
    }}
  ],
  "outro_script": "30-second outro with subscribe CTA",
  "total_scenes": 8,
  "estimated_duration_sec": 480
}}

RULES:
- Include 8-10 scenes, each 40-90 seconds of narration
- Use Indian examples, rupee amounts, Indian institutions
- Visual descriptions must be searchable stock footage keywords
- First scene is the hook, last scene is the outro CTA
- Include 2-3 mid-video engagement prompts"""


def generate_script(topic: str, niche: str, channel_name: str,
                    language: str = "English", duration_min: int = 8) -> dict:
    """Generate a complete video script for the given topic."""
    prompt = SCRIPT_TEMPLATE.format(
        topic=topic, niche=niche, channel_name=channel_name,
        language=language, duration=duration_min,
    )
    logger.info(f"Generating script: '{topic}' via Claude")
    msg = _claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.lstrip("```json").lstrip("```").rstrip("```").strip()
    script = json.loads(raw)
    script["topic"] = topic
    script["niche"] = niche
    logger.info(f"Script ready: '{script.get('title')}' | {len(script.get('scenes', []))} scenes")
    return script


def generate_topic_ideas(niche: str, count: int = 10) -> list:
    """Generate fresh topic ideas for a given niche using Claude."""
    try:
        from config import NICHES
        niche_info = NICHES.get(niche, {})
        existing = niche_info.get("topic_ideas", [])
        avoid_str = str(existing[:5])
    except Exception:
        avoid_str = "[]"

    prompt = (
        "Generate " + str(count) + " unique, high-CPM YouTube video topic ideas for an Indian audience.\n"
        "Niche: " + niche + "\n"
        "Avoid repeating: " + avoid_str + "\n\n"
        "Rules:\n"
        "- Titles must be SEO-rich and curiosity-driven\n"
        "- Use numbers, years (2026), rupee amounts where relevant\n"
        "- Target Indian audience specifically\n"
        "- Vary the format (How to, X Ways, Why, Truth About, etc.)\n\n"
        'Return JSON only: {"topics": ["topic1", "topic2", ...]}'
    )

    msg = _claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.lstrip("```json").lstrip("```").rstrip("```").strip()
    data = json.loads(raw)
    return data.get("topics", [])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    script = generate_script(
        topic="How to Save Income Tax Legally in India 2026",
        niche="Personal Finance India",
        channel_name="Money Mantra India",
    )
    print(json.dumps(script, indent=2, ensure_ascii=False))
