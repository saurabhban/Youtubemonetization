"""
Script Generator — uses Claude (Haiku) to write full video scripts.
Returns structured JSON: title, description, tags, scenes, thumbnail info.
"""
import json
import logging
import os
import anthropic
from config import NICHES, CHANNEL_LANGUAGE

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are an expert Indian YouTube script writer and SEO specialist.
You write engaging, faceless educational video scripts for Indian audiences.
You also produce SEO-optimized YouTube metadata: titles, descriptions with timestamps,
and 30-50 high-traffic tags that help videos rank and get discovered.

Always return valid JSON only — no markdown fences, no extra text."""


def generate_script(topic: str, niche: str, channel_name: str,
                    language: str = "English", duration_min: int = 8) -> dict:
    """Generate a complete video script + SEO metadata for the given topic."""

    # Build prompt using concatenation to avoid f-string brace issues with JSON examples
    prompt = (
        'Write a complete YouTube video script for this topic: "' + topic + '"\n\n'
        "Channel: " + channel_name + "\n"
        "Niche: " + niche + "\n"
        "Target Language: " + language + "\n"
        "Target Duration: ~" + str(duration_min) + " minutes\n\n"
        "Return a JSON object with this EXACT structure:\n"
        "{\n"
        '  "title": "SEO-optimized video title (60 chars max, include year 2026 if relevant)",\n'
        '  "description": "Full YouTube description (see DESCRIPTION RULES below)",\n'
        '  "tags": ["array", "of", "30-50", "SEO", "tags"],\n'
        '  "thumbnail_text": "3-4 word punch text for thumbnail",\n'
        '  "thumbnail_subtitle": "5-6 word subtitle for thumbnail",\n'
        '  "hook": "Opening 30-second hook script to grab attention",\n'
        '  "scenes": [\n'
        '    {\n'
        '      "id": 1,\n'
        '      "duration_sec": 45,\n'
        '      "narration": "Full narration text for this scene",\n'
        '      "visual_description": "What to show on screen for stock footage",\n'
        '      "search_keywords": ["keyword1", "keyword2"],\n'
        '      "on_screen_text": "Key text bullet to display on screen",\n'
        '      "transition": "cut"\n'
        '    }\n'
        '  ],\n'
        '  "outro_script": "30-second outro with subscribe CTA",\n'
        '  "total_scenes": 8,\n'
        '  "estimated_duration_sec": 480\n'
        "}\n\n"
        "SCRIPT RULES:\n"
        "- Include 8-10 scenes, each 40-90 seconds of narration\n"
        "- Use Indian examples: INR amounts, Indian banks, SEBI, RBI, Indian cities\n"
        "- Visual descriptions must be searchable stock footage keywords\n"
        "- Include 2-3 mid-video engagement prompts (like/comment hooks)\n\n"
        "DESCRIPTION RULES (very important for SEO):\n"
        "- Start with 2-3 keyword-rich sentences about the video\n"
        "- Add timestamps section like: 00:00 Intro\\n01:30 Topic 1\\netc.\n"
        "- Add a Resources/Links section (can be placeholder)\n"
        "- End with Subscribe CTA and channel description\n"
        "- Include 5-8 hashtags at the very end\n"
        "- Total description: 800-1000 characters\n\n"
        "TAG RULES (crucial for discovery):\n"
        "- Generate 30-50 tags total\n"
        "- Mix: broad tags (cloud computing), specific tags (aws certification india 2026), long-tail tags\n"
        "- Include Hindi transliteration where relevant (e.g. 'cloud computing kya hai')\n"
        "- Include competitor/trending topic tags\n"
        "- Include channel-specific tags (cloudsignalhq, cloud signal)\n"
        "- Use lowercase for all tags\n"
        "- Include year tags (2026)\n"
    )

    logger.info(f"Generating script for: '{topic}'")

    msg = _claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = msg.content[0].text.strip()
    # Strip markdown fences if Claude wraps in them
    if raw.startswith("```"):
        raw = raw.lstrip("```json").lstrip("```").rstrip("```").strip()

    script = json.loads(raw)
    script["topic"] = topic
    script["niche"]  = niche

    logger.info(
        f"Script ready: '{script.get('title')}' | "
        f"{len(script.get('scenes', []))} scenes | "
        f"{len(script.get('tags', []))} tags"
    )
    return script


def generate_topic_ideas(niche: str, count: int = 10) -> list:
    """Generate fresh AI-powered topic ideas for a niche."""
    niche_info = NICHES.get(niche, {})
    existing   = niche_info.get("topic_ideas", [])[:5]

    prompt = (
        "Generate " + str(count) + " unique, high-CPM YouTube video topic ideas for an Indian audience.\n"
        "Niche: " + niche + "\n"
        "Description: " + niche_info.get("description", niche) + "\n"
        "Avoid repeating these existing topics: " + str(existing) + "\n\n"
        "Rules:\n"
        "- Titles must be SEO-rich and curiosity-driven\n"
        "- Use numbers, years (2026), rupee amounts where relevant\n"
        "- Target Indian audience specifically\n"
        "- Vary format: How to, X Ways, Why, Truth About, Complete Guide, etc.\n\n"
        'Return JSON only: {"topics": ["topic1", "topic2", ...]}'
    )

    msg = _claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.lstrip("```json").lstrip("```").rstrip("```").strip()

    data = json.loads(raw)
    return data.get("topics", [])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    script = generate_script(
        topic="AWS vs Azure vs GCP – Which Cloud to Learn in India 2026",
        niche="AI & Technology India",
        channel_name="CloudSignalHQ",
    )
    print(json.dumps(script, indent=2, ensure_ascii=False))
