"""
Script Generator — uses OpenAI GPT-4o to create full YouTube video scripts.
Returns structured JSON with title, description, tags, scenes, and thumbnail text.
"""
import json
import re
import logging
import openai
from config import OPENAI_API_KEY, OPENAI_MODEL, SCRIPT_MAX_TOKENS, NICHES, CHANNEL_LANGUAGE

logger = logging.getLogger(__name__)
client = openai.OpenAI(api_key=OPENAI_API_KEY)


SYSTEM_PROMPT = """You are an expert Indian YouTube script writer specializing in faceless educational videos.
You write engaging, SEO-optimized scripts for the Indian audience.
Your scripts are conversational, use simple language, include Indian examples (INR, Indian banks, SEBI, RBI etc),
and follow the proven Hook-Value-CTA formula.
Always return valid JSON only, no markdown fences."""


SCRIPT_TEMPLATE = """Write a complete YouTube video script for the topic: "{topic}"

Channel: {channel_name}
Niche: {niche}
Target Language: {language}
Target Duration: ~{duration} minutes

Return a JSON object with this EXACT structure:
{{
  "title": "SEO-optimized video title (60 chars max)",
  "description": "YouTube description with timestamps and keywords (800 chars)",
  "tags": ["tag1", "tag2", ...],  // 15 relevant tags
  "thumbnail_text": "Short punchy text for thumbnail (4 words max)",
  "thumbnail_subtitle": "Subtitle for thumbnail (5 words max)",
  "hook": "Opening 30-second hook script",
  "scenes": [
    {{
      "id": 1,
      "duration_sec": 45,
      "narration": "Full narration text for this scene",
      "visual_description": "What to show on screen (for stock footage search)",
      "search_keywords": ["keyword1", "keyword2"],  // for Pexels search
      "on_screen_text": "Key text to display on screen (optional)",
      "transition": "cut | fade | zoom"
    }}
  ],
  "outro_script": "30-second outro with subscribe CTA",
  "total_scenes": 8,
  "estimated_duration_sec": 480
}}

RULES:
- Include 8-10 scenes
- Each scene 40-90 seconds of narration
- Narration must be engaging, use Indian examples, rupee amounts
- Visual descriptions must be searchable stock footage (no text in descriptions)
- First scene is always the hook
- Last scene is always the outro CTA
- Include 2-3 mid-video engagement hooks ("Comment below if...")
"""


def generate_script(topic: str, niche: str, channel_name: str,
                    language: str = "English", duration_min: int = 8) -> dict:
    """Generate a complete video script for the given topic."""
    prompt = SCRIPT_TEMPLATE.format(
        topic=topic,
        niche=niche,
        channel_name=channel_name,
        language=language,
        duration=duration_min,
    )
    logger.info(f"Generating script for: {topic}")
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=SCRIPT_MAX_TOKENS,
            temperature=0.8,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        script = json.loads(raw)
        script["topic"] = topic
        script["niche"] = niche
        logger.info(f"Script generated: '{script.get('title')}' | {len(script.get('scenes', []))} scenes")
        return script
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        raise
    except openai.OpenAIError as e:
        logger.error(f"OpenAI error: {e}")
        raise


def generate_topic_ideas(niche: str, count: int = 10) -> list[str]:
    """Generate fresh topic ideas for a given niche."""
    niche_info = NICHES.get(niche, {})
    existing = niche_info.get("topic_ideas", [])
    prompt = f"""Generate {count} unique, high-CPM YouTube video topic ideas for an Indian audience.
Niche: {niche}
Description: {niche_info.get('description', niche)}
Existing topics (avoid repeating): {existing[:5]}

Rules:
- Titles must be SEO-rich and curiosity-driven
- Use numbers, years (2026), rupee amounts where relevant
- Target Indian audience specifically
- Each title should be different in format (How to, X Ways, Why, Truth About, etc.)

Return JSON: {{"topics": ["topic1", "topic2", ...]}}"""

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800,
        temperature=0.9,
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content)
    return data.get("topics", [])


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)
    script = generate_script(
        topic="How to Save Income Tax Legally in India 2026",
        niche="Personal Finance India",
        channel_name="Money Mantra India",
    )
    print(json.dumps(script, indent=2, ensure_ascii=False))
