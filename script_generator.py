"""
Script Generator — uses Claude Haiku to write storytelling-grade video scripts.
Returns structured JSON: title, description, tags, scenes with visual_type hints.
"""
import json
import logging
import os
import anthropic
from config import NICHES, CHANNEL_LANGUAGE

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are a world-class YouTube script writer who specializes in viral Indian educational content.
You combine the storytelling of Kunal Shah with the data-driven clarity of Ali Abdaal.
Your scripts make complex topics feel like a conversation between two smart friends at a chai shop.

Rules you NEVER break:
1. HOOK in first 30 seconds — start with a shocking fact, a relatable pain, or a provocative question
2. Every sentence is SHORT (10-15 words max), complete, and self-contained
3. Use simple conversational English — "you", "we", "let me tell you", "here's the thing"
4. Ground every claim in a specific Indian example: salary in LPA, cost in ₹, city names, company names
5. Build CURIOSITY across scenes — each scene ends leaving the viewer wanting more
6. Never use jargon without immediately explaining it in plain words
7. SSML-friendly: no lists with asterisks or dashes inside narration — write full sentences only

Return ONLY valid JSON — no markdown, no extra text."""


def generate_script(topic: str, niche: str, channel_name: str,
                    language: str = "English", duration_min: int = 12) -> dict:
    """
    Generate a full video script optimised for engagement, clear narration,
    and animated visual elements (charts, bullets, tables).
    """
    prompt = (
        'Write a complete, high-quality YouTube video script for: "' + topic + '"\n\n'
        "Channel: " + channel_name + "\n"
        "Niche: " + niche + "\n"
        "Language: " + language + "\n"
        "Target Duration: " + str(duration_min) + " minutes (~" + str(duration_min * 130) + " words of narration)\n\n"
        "Return a JSON object with EXACTLY this structure:\n"
        "{\n"
        '  "title": "Curiosity-gap title, 60 chars max, includes year 2026 or rupee amount",\n'
        '  "description": "Full YouTube description — see DESCRIPTION RULES below",\n'
        '  "tags": ["30 to 50 SEO tags — see TAG RULES below"],\n'
        '  "thumbnail_text": "3-4 word SHOCKING stat or claim for thumbnail",\n'
        '  "thumbnail_subtitle": "5-6 word context line for thumbnail",\n'
        '  "hook": "First 45 seconds — start with a shocking fact or relatable problem. No filler. Pure hook.",\n'
        '  "scenes": [\n'
        '    {\n'
        '      "id": 1,\n'
        '      "title": "Short scene title for internal use",\n'
        '      "duration_sec": 60,\n'
        '      "visual_type": "footage",\n'
        '      "narration": "Full narration — SHORT sentences only. 10-15 words each. Conversational tone.",\n'
        '      "visual_description": "Stock footage search keywords (people working, cloud servers, India city etc)",\n'
        '      "search_keywords": ["keyword1", "keyword2"],\n'
        '      "on_screen_text": "Short punchy key point shown on screen. Max 60 chars.",\n'
        '      "animation_data": null,\n'
        '      "transition": "cut"\n'
        '    }\n'
        '  ],\n'
        '  "outro_script": "45-second outro — give final takeaway, then subscribe/like CTA",\n'
        '  "total_scenes": 12,\n'
        '  "estimated_duration_sec": 720\n'
        "}\n\n"

        "SCENE RULES (critical):\n"
        "- Generate 12-15 scenes for a " + str(duration_min) + "-minute video\n"
        "- Scene 1: Hook (45-60s) — shocking opening\n"
        "- Scene 2: Promise (30s) — tell them exactly what they will learn\n"
        "- Scenes 3-11: Core content — each scene = one complete idea, fully explained\n"
        "- Scene 12: Summary + CTA (45s)\n"
        "- Each narration must be 100-180 words of CONVERSATIONAL speech\n"
        "- End each scene with either a cliffhanger OR a strong takeaway\n\n"

        "VISUAL TYPE — set visual_type per scene to one of these values:\n"
        '- "footage"            → Use stock footage as background (narrative scenes)\n'
        '- "bullet_list"        → Animated bullet points appearing one by one\n'
        '- "bar_chart"          → Animated growing bar chart\n'
        '- "stat_card"          → Giant stat with animated counter\n'
        '- "comparison_table"   → Side-by-side comparison (A vs B)\n\n'

        "ANIMATION DATA — when visual_type is NOT footage, fill animation_data like these examples:\n\n"
        'For bullet_list: {"title": "Top 3 Cloud Certifications", "items": ["AWS Solutions Architect — ₹18 LPA avg", "Google Cloud Professional — ₹22 LPA avg", "Azure Administrator — ₹15 LPA avg"]}\n\n'
        'For bar_chart: {"title": "Average Salary by Cloud Skill (LPA)", "labels": ["AWS", "Azure", "GCP", "DevOps"], "values": [18, 15, 22, 20], "unit": "LPA"}\n\n'
        'For stat_card: {"stats": [{"label": "Cloud Engineers Hired in India 2025", "value": "2,40,000", "context": "Source: NASSCOM 2025"}]}\n\n'
        'For comparison_table: {"title": "AWS vs Azure vs GCP", "headers": ["Feature", "AWS", "Azure", "GCP"], "rows": [["Free Tier", "12 months", "12 months", "Always free"], ["India Regions", "3", "2", "1"], ["Best For", "Startups", "Enterprise", "AI/ML"]]}\n\n'

        "NARRATION STYLE GUIDE:\n"
        "BAD: 'Cloud computing is a paradigm that enables on-demand access to computing resources.'\n"
        "GOOD: 'Imagine paying for electricity only when you use it. Cloud computing works exactly like that.'\n\n"
        "BAD: 'There are several certifications that can help you get a job.'\n"
        "GOOD: 'There is one certification that added ₹6 lakh to my friend Rahul's salary. In just 3 months.'\n\n"
        "BAD: 'In this video, we will discuss the various aspects of...'\n"
        "GOOD: 'By the end of this video, you will know exactly which cloud to learn — and why.'\n\n"

        "DESCRIPTION RULES:\n"
        "- Line 1-3: Keyword-rich intro about the video topic\n"
        "- Timestamps section (use realistic chapter markers)\n"
        "- Resources section (mention free courses, official docs)\n"
        "- Subscribe CTA\n"
        "- 6-8 hashtags\n"
        "- 800-1000 chars total\n\n"

        "TAG RULES:\n"
        "- 35-50 tags\n"
        "- Mix: broad (cloud computing), specific (aws certification india 2026), Hindi (cloud computing kya hai)\n"
        "- Always include: cloudsignalhq, cloud signal india\n"
        "- Include salary/career tags: tech jobs india, lpa salary, it jobs 2026\n"
        "- All lowercase\n"
    )

    logger.info(f"Generating {duration_min}-min script for: '{topic}'")

    msg = _claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.lstrip("```json").lstrip("```").rstrip("```").strip()

    script = json.loads(raw)
    script["topic"] = topic
    script["niche"]  = niche

    scene_types = [s.get("visual_type", "footage") for s in script.get("scenes", [])]
    logger.info(
        f"Script: '{script.get('title')}' | "
        f"{len(script.get('scenes', []))} scenes | "
        f"{len(script.get('tags', []))} tags | "
        f"visual_types={scene_types}"
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
        "Avoid repeating: " + str(existing) + "\n\n"
        "Rules:\n"
        "- Use curiosity gaps, shocking stats, or controversial angles\n"
        "- Include specific numbers, rupee amounts, years (2026)\n"
        "- Target Indian audience — Indian companies, Indian salaries, Indian problems\n"
        "- Vary format: 'How I', 'Why Most Indians', 'The Truth About', 'X Things', etc.\n"
        "- Each title should make someone stop scrolling\n\n"
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

    return json.loads(raw).get("topics", [])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    script = generate_script(
        topic="AWS vs Azure vs GCP – Which Cloud to Learn in India 2026",
        niche="AI & Technology India",
        channel_name="CloudSignalHQ",
    )
    print(json.dumps(script, indent=2, ensure_ascii=False))
