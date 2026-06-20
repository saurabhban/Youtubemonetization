"""
Script Generator — Claude Haiku powered, storytelling-first.

Quality contract per call:
  - Pure English only (no Hindi, no Hinglish words in narration)
  - 130-180 words of narration per scene
  - scene_headline: 3-5 words ONLY (lower-third title)
  - on_screen_text: 4-7 words ONLY (key stat or fact)
  - 12-15 scenes → ~12 minute video
  - Script is regenerated automatically if it fails word-count validation
"""
import json
import logging
import os
import re
import anthropic
from config import NICHES, CHANNEL_LANGUAGE, STORY_NICHES

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ── System prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a world-class YouTube script writer for India's top tech education channel.
Your scripts are in PURE ENGLISH ONLY — not a single Hindi or Hinglish word in the narration.
You write like a knowledgeable friend who explains complex tech topics simply and engagingly.
Think: the clarity of Kurzgesagt + the warmth of Mark Rober + Indian context.

NON-NEGOTIABLE RULES:
1. Every narration sentence: 8-15 words max. Short, punchy, clear.
2. scene_headline: 3-5 words ONLY. It's a title, not a sentence. Example: "Why AWS Wins" NOT "Why AWS is winning in India".
3. on_screen_text: 4-7 words ONLY. A stat, a fact, a number. Example: "₹18 LPA average salary" NOT a sentence.
4. ZERO Hindi/Hinglish words anywhere in narration or on_screen_text.
5. Each scene = ONE complete idea, fully explained. Never cut mid-example.
6. Each narration: minimum 130 words, maximum 180 words.
7. Build a continuous thread — each scene connects logically to the next.
8. Return ONLY valid JSON. No markdown. No extra text."""


# ── Story system prompt ──────────────────────────────────────────────────────
STORY_SYSTEM_PROMPT = """You are a world-class storyteller for a faceless YouTube channel.
You write immersive, cinematic narration in PURE ENGLISH — no Hindi, no Hinglish.
Your stories grip the listener from the first sentence and don't let go.

Think: the pacing of Ryan Trahan + the tension of Karan Johar's true stories + Indian cultural depth.

STORYTELLING RULES:
1. Write in FIRST PERSON or THIRD PERSON — pick one and stay consistent.
2. Every sentence moves the story forward. No filler. No "so as I was saying".
3. Use SENSORY DETAILS: sounds, smells, the way light fell, what they felt.
4. Build TENSION gradually — don't reveal everything at once.
5. Each scene must end on a micro-hook: a question, a revelation, or a dread.
6. 130-180 words per scene narration. Short, punchy sentences for tension moments.
7. scene_headline: 3-5 atmospheric words. Example: "The Door Creaked Open" NOT "Scene 3".
8. on_screen_text: 4-7 words — a chilling quote, a date, a location, or a fact.
9. ZERO Hindi/Hinglish words anywhere.
10. Return ONLY valid JSON. No markdown. No extra text."""


def _build_story_prompt(topic: str, niche: str, channel_name: str, duration_min: int) -> str:
    """Build a narrative story script prompt — different structure than educational."""
    target_words = duration_min * 130

    # Tone per niche
    tone_map = {
        "Horror Stories India":       "terrifying, atmospheric, paranormal — make skin crawl",
        "Motivational Stories India":  "emotional, inspiring, triumphant — make eyes water",
        "True Crime India":           "investigative, dark, matter-of-fact — chilling and real",
        "Indian Mythology & History":  "epic, reverent, dramatic — timeless and grand",
    }
    tone = tone_map.get(niche, "engaging and dramatic")

    return (
        f'Write a complete faceless YouTube STORY SCRIPT about: "{topic}"\n\n'
        f"Channel: {channel_name} | Niche: {niche}\n"
        f"Tone: {tone}\n"
        f"Language: English ONLY (zero Hindi/Hinglish)\n"
        f"Duration: {duration_min} minutes | Target: {target_words}+ words total\n\n"

        "Return JSON with this EXACT structure:\n"
        "{\n"
        '  "title": "Gripping title, 60 chars max",\n'
        '  "description": "YouTube description with timestamps, 800-1000 chars",\n'
        '  "tags": ["35-50 lowercase SEO tags"],\n'
        '  "thumbnail_text": "3-4 WORD shocking hook",\n'
        '  "thumbnail_subtitle": "5-6 word teaser",\n'
        '  "scenes": [\n'
        '    {\n'
        '      "id": 1,\n'
        '      "scene_headline": "3-5 atmospheric words",\n'
        '      "duration_sec": 65,\n'
        '      "visual_type": "footage",\n'
        '      "narration": "130-180 words of pure story narration. Immersive. Sensory. Gripping.",\n'
        '      "visual_description": "Atmospheric footage keywords for this scene",\n'
        '      "search_keywords": ["dark forest night india", "old haveli", ...],\n'
        '      "on_screen_text": "Chilling quote or location or date",\n'
        '      "animation_data": null,\n'
        '      "transition": "fade"\n'
        '    }\n'
        '  ],\n'
        '  "outro_script": "30-second outro — tease next story + subscribe CTA",\n'
        '  "total_scenes": 12,\n'
        f' "estimated_duration_sec": {duration_min * 60}\n'
        "}\n\n"

        "STORY STRUCTURE (follow exactly):\n"
        "  Scene 1  — HOOK (45s): Drop the listener INTO the story. No intro. No 'today we will'. Start mid-action.\n"
        "  Scene 2  — SETUP (55s): Who, where, when. Make the listener care about the person.\n"
        "  Scene 3  — FIRST SIGN (60s): Something is wrong. The first crack in normal reality.\n"
        "  Scenes 4-6 — BUILDUP (65s each): Tension escalates. Each scene darker/more intense than last.\n"
        "  Scene 7  — MIDPOINT SHOCK (70s): A major revelation that reframes everything before it.\n"
        "  Scenes 8-9 — DESCENT (65s each): Things get worse. The protagonist is trapped / cornered.\n"
        "  Scene 10 — CLIMAX (70s): The most intense moment. Peak tension. Barely breathe.\n"
        "  Scene 11 — RESOLUTION (60s): What happened after. The truth revealed.\n"
        "  Scene 12 — AFTERMATH (50s): Lasting impact. Lesson or lingering question. Haunts the listener.\n\n"

        "VISUAL SEARCH KEYWORDS — match the mood:\n"
        "  Horror: dark forest, abandoned building, shadows, candle flame, empty corridor\n"
        "  Motivational: person running sunrise, family hug, celebration, study desk, cityscape\n"
        "  True Crime: police car lights, courtroom, evidence tape, newspaper, dark alley\n"
        "  Mythology: temple at dawn, fire ritual, ancient architecture, epic sky, warrior\n\n"

        "NARRATION QUALITY:\n"
        "  BAD:  'In this story we will explore what happened to Riya that night in October...'\n"
        "  GOOD: 'The clock read 11:47 PM when Riya heard the first knock. Three slow taps. Then silence.'\n\n"
        "  BAD:  'She was very scared and did not know what to do in the situation.'\n"
        "  GOOD: 'Her hands wouldn't stop shaking. She pressed herself against the wall and held her breath.'\n\n"

        "MICRO-HOOKS — end every scene with one:\n"
        "  'What she found behind that door changed everything.'\n"
        "  'That was the last time anyone saw him alive.'\n"
        "  'She had no idea the worst was still to come.'\n"
    )


# ── Prompt builder ────────────────────────────────────────────────────────────
def _build_script_prompt(topic: str, niche: str, channel_name: str,
                         duration_min: int) -> str:
    target_words = duration_min * 130   # ~130 wpm for clear narration

    return (
        f'Write a complete YouTube video script for: "{topic}"\n\n'
        f"Channel: {channel_name} | Niche: {niche}\n"
        f"Language: English ONLY (zero Hindi/Hinglish words)\n"
        f"Duration: {duration_min} minutes | Target narration: {target_words}+ words total\n\n"

        "Return JSON with this EXACT structure:\n"
        "{\n"
        '  "title": "Attention-grabbing title, 60 chars max, year 2026 or rupee amount",\n'
        '  "description": "Full YouTube description — see rules below",\n'
        '  "tags": ["35-50 lowercase SEO tags"],\n'
        '  "thumbnail_text": "3-4 WORD shocking claim",\n'
        '  "thumbnail_subtitle": "5-6 word context",\n'
        '  "scenes": [\n'
        '    {\n'
        '      "id": 1,\n'
        '      "scene_headline": "3-5 words ONLY",\n'
        '      "duration_sec": 65,\n'
        '      "visual_type": "footage",\n'
        '      "narration": "130-180 words of pure English narration. Short sentences. '
        'Conversational. One complete idea. No mid-example cuts.",\n'
        '      "visual_description": "Stock footage search keywords",\n'
        '      "search_keywords": ["keyword1", "keyword2"],\n'
        '      "on_screen_text": "4-7 words: stat or fact ONLY",\n'
        '      "animation_data": null,\n'
        '      "transition": "cut"\n'
        '    }\n'
        '  ],\n'
        '  "outro_script": "45-second outro — final takeaway + subscribe CTA",\n'
        '  "total_scenes": 13,\n'
        f' "estimated_duration_sec": {duration_min * 60}\n'
        "}\n\n"

        "SCENE STRUCTURE (follow exactly):\n"
        "  Scene 1   — Hook (55s): Shocking stat or painful question. Grab them in 10 seconds.\n"
        "  Scene 2   — Promise (45s): Tell them EXACTLY what they'll know by the end.\n"
        "  Scenes 3-11 — Core content (65-80s each): One idea per scene, fully explained.\n"
        "  Scene 12  — Summary (55s): Recap the 3 biggest takeaways.\n"
        "  Scene 13  — CTA (45s): Like, subscribe, comment their biggest question.\n\n"

        "VISUAL TYPE OPTIONS — assign per scene:\n"
        '  "footage"           — stock video background (narrative/story scenes)\n'
        '  "bullet_list"       — animated bullet points appearing one by one\n'
        '  "bar_chart"         — animated growing bar chart\n'
        '  "stat_card"         — giant number counting up\n'
        '  "comparison_table"  — side-by-side table with row reveals\n\n'

        "ANIMATION DATA — fill when visual_type ≠ footage:\n"
        '  bullet_list:       {"title": "...", "items": ["item 1", "item 2", "item 3"]}\n'
        '  bar_chart:         {"title": "...", "labels": [...], "values": [...], "unit": "LPA"}\n'
        '  stat_card:         {"stats": [{"label": "...", "value": "2,40,000", "context": "NASSCOM 2025"}]}\n'
        '  comparison_table:  {"title": "...", "headers": [...], "rows": [[...], ...]}\n\n'

        "NARRATION QUALITY — the most important rules:\n"
        "  BAD:  'In this section we will be discussing various aspects of cloud computing paradigm...'\n"
        "  GOOD: 'Here is a fact that will surprise you. AWS has more data centers in India than Azure and GCP combined.'\n\n"
        "  BAD:  'Cloud computing kya hai? Yeh ek bahut important technology hai...'\n"
        "  GOOD: 'What is cloud computing? Think of it like electricity. You pay for what you use.'\n\n"
        "  BAD:  'There are many tools available in the market for various purposes...'\n"
        "  GOOD: 'One tool changed everything for Rahul, a fresher from Pune. It got him a job at ₹22 LPA.'\n\n"

        "SCENE CONTINUITY — critical:\n"
        "  Each scene must be a COMPLETE thought. If you start an example in Scene 4, finish it in Scene 4.\n"
        "  Scene 5 starts fresh with a new idea.\n"
        "  End each scene with one of: a cliffhanger question, a strong takeaway, or a bridge to next scene.\n\n"

        "DESCRIPTION RULES:\n"
        "  Line 1-2: Keyword-rich hook sentence.\n"
        "  Timestamps: 00:00 Intro  01:30 [Topic]  etc.\n"
        "  Resources: 3-4 free links (can be placeholder)\n"
        "  Subscribe CTA\n"
        "  6-8 hashtags\n"
        "  Total: 800-1000 chars\n\n"

        "TAG RULES:\n"
        "  35-50 tags, all lowercase\n"
        "  Mix: broad + specific + long-tail + Hindi search terms\n"
        "  Always include: cloudsignalhq, cloud signal, india tech 2026\n"
        "  Career tags: it salary india, tech jobs 2026, lpa salary\n"
    )


# ── Validation ────────────────────────────────────────────────────────────────
def _validate_script(script: dict) -> tuple:
    """
    Check script meets minimum quality bar.
    Returns (ok: bool, reason: str).
    """
    scenes = script.get("scenes", [])
    if len(scenes) < 10:
        return False, f"Only {len(scenes)} scenes (need ≥10)"

    total_words = 0
    short_scenes = []
    hindi_pattern = re.compile(
        r'\b(kya|hai|hain|aur|ka|ki|ke|mein|par|se|nahi|nahin|bahut|'
        r'aate|kharch|agar|toh|yeh|woh|aap|hum|unka|unke)\b',
        re.IGNORECASE
    )

    for s in scenes:
        narr  = s.get("narration", "")
        words = len(narr.split())
        total_words += words

        if words < 100:
            short_scenes.append(f"Scene {s.get('id')}: {words} words")

        # Check for Hindi/Hinglish
        hindi_matches = hindi_pattern.findall(narr)
        if hindi_matches:
            logger.warning(f"  Scene {s.get('id')} has Hindi words: {hindi_matches[:5]}")

        # Enforce on_screen_text length
        ost = s.get("on_screen_text", "")
        if len(ost.split()) > 9:
            s["on_screen_text"] = " ".join(ost.split()[:7])

        # Enforce scene_headline length
        sh = s.get("scene_headline", "")
        if len(sh.split()) > 7:
            s["scene_headline"] = " ".join(sh.split()[:5])

    if total_words < 900:
        return False, f"Only {total_words} total words (need ≥900)"

    if short_scenes:
        logger.warning(f"Short scenes detected: {short_scenes}")
        # Not a hard fail — just warn

    logger.info(f"Script validated: {len(scenes)} scenes, {total_words} words")
    return True, "OK"


# ── Main generator ────────────────────────────────────────────────────────────
def generate_script(topic: str, niche: str, channel_name: str,
                    language: str = "English", duration_min: int = 12,
                    max_retries: int = 2) -> dict:
    """
    Generate a validated video script. Routes story niches to narrative prompts.
    Retries up to max_retries times if validation fails.
    """
    is_story = niche in STORY_NICHES
    system   = STORY_SYSTEM_PROMPT if is_story else SYSTEM_PROMPT
    prompt   = (_build_story_prompt(topic, niche, channel_name, duration_min)
                if is_story else
                _build_script_prompt(topic, niche, channel_name, duration_min))

    for attempt in range(max_retries + 1):
        if attempt > 0:
            logger.info(f"Retry {attempt}/{max_retries} — regenerating script...")

        logger.info(f"Generating {duration_min}-min script: '{topic}' (attempt {attempt+1})")

        msg = _claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=8192,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.lstrip("```json").lstrip("```").rstrip("```").strip()

        try:
            script = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse failed (attempt {attempt+1}): {e}")
            if attempt == max_retries:
                raise
            continue

        script["topic"]      = topic
        script["niche"]      = niche
        script["story_mode"] = is_story
        # Store niche TTS rate so pipeline can use it
        niche_cfg = NICHES.get(niche, {})
        script["tts_rate"] = niche_cfg.get("tts_rate", "-5%")

        ok, reason = _validate_script(script)
        if ok:
            scene_types = [s.get("visual_type", "footage") for s in script.get("scenes", [])]
            total_words = sum(len(s.get("narration","").split()) for s in script.get("scenes",[]))
            logger.info(
                f"Script ready: '{script.get('title')}' | "
                f"{len(script.get('scenes',[]))} scenes | "
                f"{total_words} words | "
                f"types={scene_types}"
            )
            return script
        else:
            logger.warning(f"Script failed validation: {reason}")
            if attempt == max_retries:
                logger.warning("Max retries reached — using best available script")
                return script

    return script


# ── Topic ideas ───────────────────────────────────────────────────────────────
def generate_topic_ideas(niche: str, count: int = 10) -> list:
    """Generate fresh curiosity-gap topic ideas for a niche."""
    niche_info = NICHES.get(niche, {})
    existing   = niche_info.get("topic_ideas", [])[:5]

    prompt = (
        f"Generate {count} unique high-CPM YouTube video topic ideas for an Indian audience.\n"
        f"Niche: {niche}\n"
        f"Description: {niche_info.get('description', niche)}\n"
        f"Avoid repeating: {existing}\n\n"
        "Rules:\n"
        "- Use curiosity gaps, shocking stats, or proven-wrong assumptions\n"
        "- Include specific numbers: salaries in LPA, costs in ₹, year 2026\n"
        "- Target: Indian professionals, students, job seekers\n"
        "- Vary format: 'The Truth About', 'Why Most Indians', 'How I', 'X Things', 'Complete Guide'\n"
        "- Every title must make someone stop scrolling\n"
        "- English titles only\n\n"
        '{"topics": ["title1", "title2", ...]}'
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
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s: %(message)s")
    script = generate_script(
        topic="AWS vs Azure vs GCP – Which Cloud to Learn in India 2026",
        niche="AI & Technology India",
        channel_name="CloudSignalHQ",
    )
    scenes = script.get("scenes", [])
    total  = sum(len(s.get("narration","").split()) for s in scenes)
    print(f"\nScenes: {len(scenes)} | Words: {total}")
    for s in scenes[:3]:
        print(f"\n--- Scene {s['id']}: {s.get('scene_headline')} ---")
        print(f"  on_screen_text: {s.get('on_screen_text')}")
        print(f"  narration ({len(s.get('narration','').split())} words): {s.get('narration','')[:120]}...")
