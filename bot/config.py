"""Configuration loader for the video pipeline bot."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Support multiple authorized users (comma-separated IDs)
_chat_ids_raw = os.getenv("TELEGRAM_CHAT_IDS", os.getenv("TELEGRAM_CHAT_ID", ""))
TELEGRAM_CHAT_IDS = {int(x.strip()) for x in _chat_ids_raw.split(",") if x.strip()}

# Notion config
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_LINKS_DB_ID = os.getenv("NOTION_LINKS_DB_ID")

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
LINKS_DIR = PROJECT_ROOT / "links"

# Content types with emoji, file path, and label
CONTENT_TYPES = {
    "tiktoks":   {"emoji": "🎵", "file": LINKS_DIR / "pending_tiktoks.txt",   "label": "TikToks"},
    "reels":     {"emoji": "📸", "file": LINKS_DIR / "pending_reels.txt",     "label": "Reels"},
    "yt_shorts": {"emoji": "🎬", "file": LINKS_DIR / "pending_yt_shorts.txt", "label": "YT Shorts"},
    "carousels": {"emoji": "🎠", "file": LINKS_DIR / "pending_carousels.txt", "label": "Carousels"},
    "podcasts":  {"emoji": "🎙️", "file": LINKS_DIR / "pending_podcasts.txt",  "label": "Podcasts"},
    "x":         {"emoji": "𝕏",  "file": LINKS_DIR / "pending_x.txt",         "label": "X Posts"},
    "linkedin":  {"emoji": "💼", "file": LINKS_DIR / "pending_linkedin.txt",  "label": "LinkedIn"},
    "reddit":    {"emoji": "🤖", "file": LINKS_DIR / "pending_reddit.txt",    "label": "Reddit"},
}
