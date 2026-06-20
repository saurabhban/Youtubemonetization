"""
India Faceless YouTube Video Generator
Configuration & Settings
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ─── API KEYS ───────────────────────────────────────────────────
OPENAI_API_KEY      = os.getenv("OPENAI_API_KEY", "")
PEXELS_API_KEY      = os.getenv("PEXELS_API_KEY", "")          # free at pexels.com/api
YOUTUBE_CLIENT_ID   = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")

# ─── CHANNEL SETTINGS ───────────────────────────────────────────
CHANNEL_NAME        = os.getenv("CHANNEL_NAME", "CloudSignalHQ")
CHANNEL_NICHE       = os.getenv("CHANNEL_NICHE", "AI & Technology India")
CHANNEL_LANGUAGE    = os.getenv("CHANNEL_LANGUAGE", "English")  # English | Hindi | Hinglish

# ─── VIDEO SETTINGS ─────────────────────────────────────────────
VIDEO_WIDTH         = 1920
VIDEO_HEIGHT        = 1080
VIDEO_FPS           = 30
TARGET_DURATION_SEC = 720   # 12 min — longer = more ad breaks = higher revenue
INTRO_DURATION_SEC  = 5
OUTRO_DURATION_SEC  = 8

# ─── TTS SETTINGS ───────────────────────────────────────────────
# Edge-TTS voices (free, Microsoft neural)
TTS_VOICES = {
    "English":  "en-IN-NeerjaNeural",       # Indian English female
    "English_M":"en-IN-PrabhatNeural",      # Indian English male
    "Hindi":    "hi-IN-SwaraNeural",        # Hindi female
    "Hindi_M":  "hi-IN-MadhurNeural",       # Hindi male
    "Hinglish": "en-IN-NeerjaNeural",
}
TTS_RATE    = "-5%"      # slightly slower = clearer, more professional delivery
TTS_VOLUME  = "+0%"

# ─── AI SETTINGS ────────────────────────────────────────────────
OPENAI_MODEL        = "gpt-4o"
SCRIPT_MAX_TOKENS   = 3000

# ─── NICHES & TOPIC IDEAS ───────────────────────────────────────
NICHES = {
    "Personal Finance India": {
        "description": "Personal finance, investing, tax saving for Indians",
        "topic_ideas": [
            "How to Save Income Tax Legally in India 2026",
            "Best SIP Mutual Funds to Start in 2026",
            "PPF vs NPS vs ELSS – Which is Best for You?",
            "How to Build an Emergency Fund in India",
            "Credit Score Secrets Banks Don't Tell You",
            "How to Invest ₹5000 Per Month and Become Crorepati",
            "EPF vs NPS – Which Retirement Plan to Choose",
            "7 Government Schemes Every Indian Must Know",
            "How to File ITR Online – Step by Step 2026",
            "Gold vs Stock Market – Which Gives Better Returns",
            "How to Get a Home Loan at Lowest Interest Rate",
            "UPI Frauds – How to Protect Your Money",
        ],
        "keywords": ["finance", "money", "investment", "tax", "india", "rupee"],
        "cpm_range": "₹100–₹250",
    },
    "AI & Technology India": {
        "description": "Cloud computing, AI tools, DevOps, and tech careers for Indian professionals",
        "topic_ideas": [
            "AWS vs Azure vs GCP – Which Cloud to Learn in India 2026",
            "How to Get AWS Certified in 30 Days – Free Resources",
            "Top 10 AI Tools Every Indian Developer Must Know in 2026",
            "How to Land a Cloud Engineer Job with ₹15–30 LPA Salary",
            "Docker & Kubernetes Explained in Simple Hindi for Beginners",
            "ChatGPT vs Claude vs Gemini – Best AI for Indian Coders",
            "How to Build and Deploy a Python App on AWS for Free",
            "Top 5 Cloud Certifications That Actually Get You Hired in India",
            "What is Generative AI? Complete Guide for Indian Students",
            "GitHub Copilot vs Cursor – Which AI Coding Tool is Best?",
            "How Indians Are Earning ₹1 Lakh/Month with Cloud Freelancing",
            "Azure vs AWS in India – Which Has More Jobs in 2026?",
            "How to Set Up a Home Lab for Cloud Learning – Under ₹5000",
            "Terraform in 10 Minutes – Infrastructure as Code for Beginners",
            "Best Free Courses to Learn AI/ML in India (2026 Updated)",
        ],
        "keywords": ["cloud", "aws", "azure", "devops", "ai", "technology", "india", "tech career"],
        "cpm_range": "₹80–₹200",
    },
    "Government Jobs India": {
        "description": "UPSC, SSC, banking exams, government schemes",
        "topic_ideas": [
            "Top 10 Government Jobs with Highest Salary in India",
            "UPSC 2026 Preparation Strategy for Beginners",
            "Bank PO vs SSC CGL – Which is Better?",
            "7 PM Narendra Modi Yojana Every Indian Must Know",
        ],
        "keywords": ["government job", "sarkari naukri", "upsc", "ssc", "india"],
        "cpm_range": "₹60–₹150",
    },
    "Health & Wellness India": {
        "description": "Indian diet, Ayurveda, mental health, fitness",
        "topic_ideas": [
            "10 Indian Superfoods That Boost Immunity",
            "How to Lose Weight Eating Indian Food",
            "Yoga Poses for Office Workers – 10 Minutes Daily",
            "Mental Health Tips for Indians – Break the Stigma",
        ],
        "keywords": ["health", "wellness", "india", "yoga", "diet"],
        "cpm_range": "₹50–₹120",
    },

    # ── Faceless Story Niches ──────────────────────────────────────
    "Horror Stories India": {
        "description": "Scary stories, paranormal tales, ghost encounters set in India",
        "story_mode": True,
        "topic_ideas": [
            "The Haunted Haveli of Rajasthan — A True Ghost Story",
            "I Stayed in India's Most Haunted Hotel — This Happened",
            "The Crying Girl on NH8 — India's Most Chilling Urban Legend",
            "Bhangarh Fort at Midnight — What Really Happened to Us",
            "The Shadow at My Window — A True Story from Mumbai",
            "She Called My Name Three Times — A Village Horror Story",
            "The Last Train from Churchgate — A Mumbai Ghost Story",
            "The Child in White — A True Encounter from Shimla",
            "Our Ouija Board Session Went Terribly Wrong",
            "The Abandoned Village of Kuldhara — What Locals Won't Tell You",
            "I Saw Something in the Himalayas That I Can't Explain",
            "The Spirit in Sector 14 — A Real Account from Noida",
        ],
        "keywords": ["horror", "scary", "ghost", "haunted", "india", "paranormal", "true story"],
        "cpm_range": "₹60–₹180",
        "tts_rate": "-12%",
        "bgm_track": "suspense_dark",
        "footage_mood": "dark atmospheric horror",
    },
    "Motivational Stories India": {
        "description": "Real Indian success stories, comeback journeys, rags-to-riches tales",
        "story_mode": True,
        "topic_ideas": [
            "From ₹500 to ₹500 Crore — The Unbelievable Story of Ritesh Agarwal",
            "She Sold Pakodas to Send Her Son to IIT — A Mother's Story",
            "The Chai Seller Who Became India's Youngest Crorepati",
            "He Failed 12th Class Twice — Now He Runs a 200 Crore Company",
            "From a Mumbai Slum to Silicon Valley — Rajan's Impossible Journey",
            "The Farmer's Daughter Who Cracked UPSC in 1st Attempt",
            "They Said She Was Too Old to Start — She Built a ₹100 Cr Brand at 52",
            "The Blind Boy from Bihar Who Topped JEE Advanced",
            "He Lost Everything in a Fire — How He Rebuilt in 3 Years",
            "India's Youngest IPS Officer — The Story Nobody Told You",
            "She Walked 40 km a Day to Study — Now She's a Doctor",
            "The Watchman's Son Who Became a Google Engineer",
        ],
        "keywords": ["motivation", "success story", "india", "inspiration", "rags to riches", "true story"],
        "cpm_range": "₹80–₹200",
        "tts_rate": "-8%",
        "bgm_track": "cinematic_rise",
        "footage_mood": "inspirational uplifting bright",
    },
    "True Crime India": {
        "description": "Real Indian crime cases, mysteries, investigations — factual storytelling",
        "story_mode": True,
        "topic_ideas": [
            "The Aarushi Talwar Case — What Really Happened That Night",
            "India's Most Mysterious Disappearance — The Subhash Chandra Bose File",
            "The Stoneman Murders of Mumbai — India's Most Elusive Serial Killer",
            "The Nithari Killings — How India's Worst Crime Was Covered Up",
            "The Woman Who Fooled All of India — The Telgi Stamp Paper Scam",
            "Delhi's Most Chilling Cold Case That Was Never Solved",
            "The Man Who Duped 10,000 Indians With a WhatsApp Scheme",
            "India's Real Wolf of Wall Street — The Harshad Mehta Full Story",
            "The Railway Station Murder That Shocked the Nation",
            "She Vanished in Broad Daylight — India's Most Haunting Missing Case",
        ],
        "keywords": ["true crime", "crime india", "mystery", "investigation", "unsolved", "india"],
        "cpm_range": "₹100–₹250",
        "tts_rate": "-10%",
        "bgm_track": "suspense_dark",
        "footage_mood": "dark noir crime mystery",
    },
    "Indian Mythology & History": {
        "description": "Stories from Hindu mythology, Indian epics, historical figures, untold history",
        "story_mode": True,
        "topic_ideas": [
            "The Real Story of Karna — The Most Tragic Hero of Mahabharata",
            "Chanakya's Most Ruthless Strategy That Changed India Forever",
            "The Woman Who Brought Down an Empire — Rani Padmavati's True Story",
            "Why Shiva Drank Poison and Survived — The Story of Neelkanth",
            "The Lost City of Dwarka — Is Krishna's Kingdom Real?",
            "Rani Laxmibai's Last Battle — The Truth History Books Hide",
            "The Curse of Gandhari — How It Destroyed the Entire Kuru Dynasty",
            "Who Really Built the Taj Mahal — Myths vs Historical Truth",
            "The 14 Mysteries of the Mahabharata That Science Can't Explain",
            "Ashoka's Darkest Secret — The War He Never Wanted to Win",
            "The Real Story of Draupadi — Not What You Think",
            "How Tipu Sultan's Rockets Changed Modern Warfare",
        ],
        "keywords": ["mythology", "history india", "mahabharata", "ramayana", "chanakya", "untold history"],
        "cpm_range": "₹70–₹180",
        "tts_rate": "-8%",
        "bgm_track": "cinematic_rise",
        "footage_mood": "epic ancient mythological india",
    },
}

# ── Helper: detect story niches ──────────────────────────────────
STORY_NICHES = {k for k, v in NICHES.items() if v.get("story_mode")}

# ─── PATHS ──────────────────────────────────────────────────────
BASE_DIR            = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR          = os.path.join(BASE_DIR, "output")
VIDEOS_DIR          = os.path.join(OUTPUT_DIR, "videos")
AUDIO_DIR           = os.path.join(OUTPUT_DIR, "audio")
FOOTAGE_DIR         = os.path.join(OUTPUT_DIR, "footage")
LOGS_DIR            = os.path.join(BASE_DIR, "logs")
YOUTUBE_TOKEN_FILE  = os.path.join(BASE_DIR, "youtube_token.json")
YOUTUBE_SECRETS_FILE= os.path.join(BASE_DIR, "client_secrets.json")

for d in [OUTPUT_DIR, VIDEOS_DIR, AUDIO_DIR, FOOTAGE_DIR, LOGS_DIR]:
    os.makedirs(d, exist_ok=True)
