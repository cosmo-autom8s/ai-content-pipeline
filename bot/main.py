#!/usr/bin/env python3
"""
Video Pipeline Telegram Bot - Part A
Collects video/content links and stores them locally for batch processing.
"""
from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

import requests as http_requests

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS, CONTENT_TYPES, NOTION_API_KEY, NOTION_LINKS_DB_ID

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# URL detection rules (order matters — youtube.com/shorts must match before youtu.be)
URL_RULES = [
    (r"tiktok\.com|vm\.tiktok\.com",       "tiktoks"),
    (r"instagram\.com/(reel|reels)/",       "reels"),
    (r"youtube\.com/shorts/",               "yt_shorts"),
    (r"instagram\.com/p/",                  "carousels"),
    (r"youtube\.com/watch",                 "podcasts"),
    (r"youtu\.be/",                         "podcasts"),
    (r"spotify\.com",                       "podcasts"),
    (r"(twitter\.com|x\.com)/",             "x"),
    (r"linkedin\.com/(posts|feed/update)",  "linkedin"),
    (r"reddit\.com",                        "reddit"),
]

# Track last saved link per chat for /note
last_saved = {}
# Track last Notion page ID per chat for /note
last_notion_page = {}

# Map bot content types to Notion category select values
NOTION_CATEGORY_MAP = {
    "tiktoks": "tiktok",
    "reels": "reels",
    "yt_shorts": "yt_shorts",
    "carousels": "carousel",
    "podcasts": "podcast",
    "x": "x_post",
    "linkedin": "linkedin",
    "reddit": "reddit",
}

URL_PATTERN = re.compile(r'https?://\S+')


def extract_url_and_notes(text: str) -> tuple:
    """Extract first URL and any remaining text as notes."""
    match = URL_PATTERN.search(text)
    if not match:
        return text, None
    url = match.group(0)
    notes = text[match.end():].strip()
    return url, notes if notes else None


def save_to_notion(content_type: str, full_text: str) -> str | None:
    """Save a link to the Notion Links Queue database. Returns page ID on success, None on failure."""
    if not NOTION_API_KEY or not NOTION_LINKS_DB_ID:
        logger.warning("Notion not configured, skipping Notion save")
        return None

    url, notes = extract_url_and_notes(full_text)
    category = NOTION_CATEGORY_MAP.get(content_type, "short_form")

    domain_match = re.search(r'//(?:www\.)?([^/]+)', url)
    name = domain_match.group(1) if domain_match else url[:50]

    properties = {
        "Name": {"title": [{"text": {"content": name}}]},
        "Link URL": {"url": url},
        "Category": {"select": {"name": category}},
        "Timestamp": {"date": {"start": datetime.now().isoformat()[:10]}},
        "Status": {"select": {"name": "pending"}},
    }
    if notes:
        properties["Notes"] = {"rich_text": [{"text": {"content": notes[:2000]}}]}

    try:
        resp = http_requests.post(
            "https://api.notion.com/v1/pages",
            headers={
                "Authorization": f"Bearer {NOTION_API_KEY}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28",
            },
            json={"parent": {"database_id": NOTION_LINKS_DB_ID}, "properties": properties},
            timeout=10,
        )
        if resp.status_code == 200:
            page_id = resp.json().get("id", "")
            logger.info(f"Notion: saved {url[:50]} (page: {page_id})")
            return page_id
        else:
            logger.error(f"Notion error {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        logger.error(f"Notion save failed: {e}")
        return None


def append_note_to_notion(page_id: str, note_text: str) -> bool:
    """Append a note to an existing Notion page's Notes field."""
    if not NOTION_API_KEY or not page_id:
        return False

    try:
        # First, read existing notes
        resp = http_requests.get(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers={
                "Authorization": f"Bearer {NOTION_API_KEY}",
                "Notion-Version": "2022-06-28",
            },
            timeout=10,
        )
        existing_notes = ""
        if resp.status_code == 200:
            notes_parts = resp.json().get("properties", {}).get("Notes", {}).get("rich_text", [])
            existing_notes = notes_parts[0]["plain_text"] if notes_parts else ""

        # Append new note
        combined = f"{existing_notes}\n{note_text}".strip() if existing_notes else note_text

        resp = http_requests.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers={
                "Authorization": f"Bearer {NOTION_API_KEY}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28",
            },
            json={"properties": {
                "Notes": {"rich_text": [{"text": {"content": combined[:2000]}}]}
            }},
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info(f"Notion: appended note to page {page_id}")
            return True
        else:
            logger.error(f"Notion note update error {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"Notion note append failed: {e}")
        return False


def is_authorized(update: Update) -> bool:
    """Check if the message is from an authorized user."""
    return update.effective_chat.id in TELEGRAM_CHAT_IDS


def detect_content_type(text: str) -> Optional[str]:
    """Detect content type from URL in text. Returns type key or None."""
    for pattern, content_type in URL_RULES:
        if re.search(pattern, text, re.IGNORECASE):
            return content_type
    return None


# ============ File Storage ============

def add_link(content_type: str, full_text: str) -> int:
    """Append the full message (URL + notes) as one line. Returns new count."""
    filepath = CONTENT_TYPES[content_type]["file"]
    with open(filepath, "a") as f:
        f.write(f"{full_text.strip()}\n")
    return get_count(content_type)


def get_count(content_type: str) -> int:
    """Count lines in a content type's file."""
    filepath = CONTENT_TYPES[content_type]["file"]
    if not filepath.exists():
        return 0
    with open(filepath, "r") as f:
        return len([line for line in f.readlines() if line.strip()])


def get_all_counts() -> dict:
    """Returns {type: count} for all content types."""
    return {ct: get_count(ct) for ct in CONTENT_TYPES}


def get_links(content_type: str, limit: int = 10) -> list[str]:
    """Read last N lines from a content type's file."""
    filepath = CONTENT_TYPES[content_type]["file"]
    if not filepath.exists():
        return []
    with open(filepath, "r") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    return lines[-limit:]


def clear_links(content_type: str) -> int:
    """Clear a content type's file. Returns count that was cleared."""
    count = get_count(content_type)
    filepath = CONTENT_TYPES[content_type]["file"]
    if filepath.exists():
        filepath.unlink()
    return count


def append_note_to_last_line(content_type: str, note: str) -> bool:
    """Append note text to the last line of a content type's file."""
    filepath = CONTENT_TYPES[content_type]["file"]
    if not filepath.exists():
        return False
    with open(filepath, "r") as f:
        lines = f.readlines()
    if not lines:
        return False
    # Find the last non-empty line and append note
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip():
            lines[i] = lines[i].rstrip("\n") + " " + note + "\n"
            break
    with open(filepath, "w") as f:
        f.writelines(lines)
    return True


# ============ Command Handlers ============

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if not is_authorized(update):
        await update.message.reply_text("⛔ Unauthorized")
        return

    types_list = "\n".join(
        f"  {info['emoji']} {info['label']}" for info in CONTENT_TYPES.values()
    )
    await update.message.reply_text(
        "👋 Video Pipeline Bot ready!\n\n"
        "Send me any link and I'll sort it:\n"
        f"{types_list}\n\n"
        "Commands:\n"
        "/status - Counts for all types\n"
        "/list - Show recent links\n"
        "/note - Add note to last saved link\n"
        "/clear - Clear pending links"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command."""
    if not is_authorized(update):
        return

    counts = get_all_counts()
    total = sum(counts.values())

    if total == 0:
        await update.message.reply_text("📭 No pending links.")
        return

    lines = []
    for ct, count in counts.items():
        if count > 0:
            info = CONTENT_TYPES[ct]
            lines.append(f"{info['emoji']} {info['label']}: {count}")

    message = "📊 Pending links:\n\n" + "\n".join(lines) + f"\n\nTotal: {total}"
    await update.message.reply_text(message)


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /list command. Supports /list or /list <type>."""
    if not is_authorized(update):
        return

    args = context.args
    if args:
        # /list <type> — show only that type
        type_key = args[0].lower()
        if type_key not in CONTENT_TYPES:
            valid = ", ".join(CONTENT_TYPES.keys())
            await update.message.reply_text(f"❌ Unknown type. Valid: {valid}")
            return
        links = get_links(type_key)
        info = CONTENT_TYPES[type_key]
        if not links:
            await update.message.reply_text(f"📭 No pending {info['label'].lower()}.")
            return
        message = f"{info['emoji']} {info['label']}:\n\n"
        for link in links:
            short = link[:60] + "..." if len(link) > 60 else link
            message += f"  {short}\n"
        count = get_count(type_key)
        if count > 10:
            message += f"\n... and {count - 10} more"
        message += f"\n📊 Total {info['label'].lower()}: {count}"
        await update.message.reply_text(message)
        return

    # /list — show all types
    counts = get_all_counts()
    total = sum(counts.values())

    if total == 0:
        await update.message.reply_text("📭 No pending links.")
        return

    message = "📋 Recent pending links:\n"
    for ct, count in counts.items():
        if count == 0:
            continue
        info = CONTENT_TYPES[ct]
        links = get_links(ct, limit=5)
        message += f"\n{info['emoji']} {info['label']} ({count}):\n"
        for link in links:
            short = link[:60] + "..." if len(link) > 60 else link
            message += f"  {short}\n"
        if count > 5:
            message += f"  ... and {count - 5} more\n"

    message += f"\n📊 Total: {total}"
    await update.message.reply_text(message)


async def cmd_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /note command — append note to last saved link."""
    if not is_authorized(update):
        return

    chat_id = update.effective_chat.id
    if chat_id not in last_saved:
        await update.message.reply_text("❌ No recent link to add a note to.")
        return

    note_text = " ".join(context.args) if context.args else ""
    if not note_text:
        await update.message.reply_text("❌ Usage: /note your note text here")
        return

    content_type = last_saved[chat_id]
    success = append_note_to_last_line(content_type, note_text)

    # Also update Notion
    notion_page_id = last_notion_page.get(chat_id)
    notion_ok = append_note_to_notion(notion_page_id, note_text) if notion_page_id else False
    notion_flag = " 📋" if notion_ok else ""

    if success:
        await update.message.reply_text(f"✅ Added note to last link{notion_flag}")
    else:
        await update.message.reply_text("❌ Couldn't add note — file is empty.")


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /clear command. Supports /clear or /clear <type>."""
    if not is_authorized(update):
        return

    args = context.args
    if args:
        # /clear <type>
        type_key = args[0].lower()
        if type_key not in CONTENT_TYPES:
            valid = ", ".join(CONTENT_TYPES.keys())
            await update.message.reply_text(f"❌ Unknown type. Valid: {valid}")
            return
        info = CONTENT_TYPES[type_key]
        count = clear_links(type_key)
        if count > 0:
            await update.message.reply_text(f"🗑️ Cleared {count} {info['label'].lower()}")
        else:
            await update.message.reply_text(f"📭 No {info['label'].lower()} to clear")
        return

    # /clear — clear all
    total = 0
    for ct in CONTENT_TYPES:
        total += clear_links(ct)

    if total > 0:
        await update.message.reply_text(f"🗑️ Cleared {total} links across all types")
    else:
        await update.message.reply_text("📭 No links to clear")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages with content links."""
    if not is_authorized(update):
        logger.warning(f"Unauthorized access attempt from chat_id: {update.effective_chat.id}")
        return

    text = update.message.text
    content_type = detect_content_type(text)

    if content_type:
        count = add_link(content_type, text)
        info = CONTENT_TYPES[content_type]
        last_saved[update.effective_chat.id] = content_type

        # Save to Notion — skip TikToks and Reels (those get Notion rows via TokScript CSV)
        # to avoid duplicates (bot stores shortened URLs, TokScript has full URLs)
        notion_page_id = None
        if content_type not in ("tiktoks", "reels"):
            notion_page_id = save_to_notion(content_type, text)
        notion_flag = " 📋" if notion_page_id else ""
        if notion_page_id:
            last_notion_page[update.effective_chat.id] = notion_page_id

        await update.message.reply_text(f"✅ {info['emoji']} {info['label']} saved ({count} pending){notion_flag}")
        logger.info(f"Added {content_type} link: {text[:50]}...")
    else:
        types_list = "\n".join(
            f"{info['emoji']} {info['label']}" for info in CONTENT_TYPES.values()
        )
        await update.message.reply_text(
            f"❌ Not a supported link.\n\nSupported:\n{types_list}"
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors."""
    logger.error(f"Exception while handling an update: {context.error}")


def main() -> None:
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN not set in .env file")
        return

    if not TELEGRAM_CHAT_IDS:
        print("❌ Error: TELEGRAM_CHAT_IDS not set in .env file")
        print("\nTo find a chat ID: message @userinfobot on Telegram")
        return

    print("🤖 Starting Video Pipeline Bot...")
    print(f"👤 Authorized chat IDs: {', '.join(str(x) for x in TELEGRAM_CHAT_IDS)}")
    print(f"📁 Content types: {len(CONTENT_TYPES)}")
    for ct, info in CONTENT_TYPES.items():
        print(f"   {info['emoji']} {info['label']} → {info['file'].name}")
    print(f"\nBot is running! Press Ctrl+C to stop.\n")

    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("list", cmd_list))
    application.add_handler(CommandHandler("note", cmd_note))
    application.add_handler(CommandHandler("clear", cmd_clear))

    # Add message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Add error handler
    application.add_error_handler(error_handler)

    # Start polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
