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
TARGET_DURATION_SEC = 480   # 8 min — sweet spot for YouTube monetization
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
TTS_RATE    = "+10%"     # speaking speed
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
}

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
