#!/bin/bash
# ============================================================
# India YouTube Video Generator — One-click Setup Script
# Run: bash setup.sh
# ============================================================

set -e
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo "🎬 India YouTube Video Generator — Setup"
echo "========================================="

# ── Check Python ──────────────────────────────────────────────
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found. Install from https://python.org${NC}"
    exit 1
fi
PY_VER=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✓ Python ${PY_VER}${NC}"

# ── Check FFmpeg ──────────────────────────────────────────────
if ! command -v ffmpeg &> /dev/null; then
    echo -e "${YELLOW}⚠️  FFmpeg not found. Installing...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install ffmpeg
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get install -y ffmpeg
    else
        echo -e "${RED}Please install FFmpeg manually: https://ffmpeg.org/download.html${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✓ FFmpeg$(ffmpeg -version 2>&1 | head -1 | awk '{print " "$3}')${NC}"

# ── Virtual Environment ───────────────────────────────────────
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"

# ── Install Dependencies ──────────────────────────────────────
echo "Installing Python packages..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo -e "${GREEN}✓ All packages installed${NC}"

# ── Create .env ───────────────────────────────────────────────
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${YELLOW}⚠️  Created .env — please fill in your API keys!${NC}"
else
    echo -e "${GREEN}✓ .env already exists${NC}"
fi

# ── Create asset directories ──────────────────────────────────
mkdir -p assets/bgm assets/fonts output/{videos,audio,footage} logs

# ── Download Indian font ──────────────────────────────────────
FONT_URL="https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Bold.ttf"
FONT_PATH="assets/fonts/NotoSans-Bold.ttf"
if [ ! -f "$FONT_PATH" ]; then
    echo "Downloading NotoSans font..."
    curl -sL "$FONT_URL" -o "$FONT_PATH" 2>/dev/null || echo -e "${YELLOW}⚠️  Font download failed — text overlays will use system font${NC}"
fi
[ -f "$FONT_PATH" ] && echo -e "${GREEN}✓ NotoSans font ready${NC}"

echo ""
echo "========================================="
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Edit .env and add your API keys"
echo "  2. Run: python webapp.py"
echo "  3. Open: http://localhost:5000"
echo ""
echo "API Keys needed:"
echo "  • OpenAI:  https://platform.openai.com/api-keys"
echo "  • Pexels:  https://www.pexels.com/api/"
echo "  • YouTube: https://console.cloud.google.com"
echo ""
echo "💡 Recommended niche: Personal Finance India (CPM ₹100-250)"
echo "========================================="
