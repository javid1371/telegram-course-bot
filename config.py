"""
Configuration module for Telegram Course Bot
Loads environment variables and provides configuration settings
"""
import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base Directory
BASE_DIR = Path(__file__).resolve().parent

# ── Platform ──────────────────────────────────────────────
# "telegram" or "bale" — set via PLATFORM env var
PLATFORM = os.getenv("PLATFORM", "telegram").lower()

# Bot credentials (same env var name for both platforms)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "course_bot")
ADMIN_USER_IDS = [
    int(uid.strip())
    for uid in os.getenv("ADMIN_USER_IDS", "").split(",")
    if uid.strip()
]

# Platform-specific API endpoints
PLATFORM_API_URLS = {
    "telegram": "https://api.telegram.org",
    "bale":     "https://tapi.bale.ai",
}
API_BASE_URL = PLATFORM_API_URLS.get(PLATFORM, PLATFORM_API_URLS["telegram"])

# Bale only supports Markdown (not HTML)
# telegram → "HTML", bale → None (Bale auto-renders Markdown)
PARSE_MODE = "HTML" if PLATFORM == "telegram" else None

# File download base — used for getFile results
FILE_BASE_URL = API_BASE_URL

# Database
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "course_bot")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Database URL
DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# Webhook
WEBHOOK_ENABLED = os.getenv("WEBHOOK_ENABLED", "False").lower() == "true"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8443"))

# Webhook Security — HMAC-SHA256 signing for CRM/n8n verification
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# CRM Field Mapping
# Keys = registration_data field names
# Values = CRM field path (e.g. "person.name", "person.phone") or "note"
# Fields not listed here are automatically included as notes
FIELD_MAPPING = {
    "name": "person.name",
    "phone": "person.phone",
    "mobile": "person.phone",
    "email": "person.email",
}

# Bot Settings
MAX_LESSONS_PER_USER = int(os.getenv("MAX_LESSONS_PER_USER", "100"))
REMINDER_DAYS = int(os.getenv("REMINDER_DAYS", "3"))
BROADCAST_RATE_LIMIT = int(os.getenv("BROADCAST_RATE_LIMIT", "30"))

# Referral promo: show referral invitation at these lesson completion milestones
# Comma-separated lesson numbers (e.g., "3,7")
REFERRAL_PROMO_LESSONS = [
    int(x.strip()) for x in os.getenv("REFERRAL_PROMO_LESSONS", "3,7").split(",") if x.strip()
]

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "bot.log")

# File Storage
UPLOAD_DIR = BASE_DIR / os.getenv("UPLOAD_DIR", "files/")
BACKUP_DIR = BASE_DIR / os.getenv("BACKUP_DIR", "backups/")
EXPORT_DIR = BASE_DIR / os.getenv("EXPORT_DIR", "exports/")

# Create directories if they don't exist
UPLOAD_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)
EXPORT_DIR.mkdir(exist_ok=True)

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this")
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "True").lower() == "true"

# Platform API Limits
MAX_MESSAGE_LENGTH = 4096
MAX_CAPTION_LENGTH = 1024
BROADCAST_SLEEP_SECONDS = 0.05  # 20 messages per second (safe limit)
FILE_SIZE_LIMIT = 50 * 1024 * 1024  # 50 MB

# Migration: code TTL in seconds (24 hours)
MIGRATION_CODE_TTL = int(os.getenv("MIGRATION_CODE_TTL", "86400"))

# Sync endpoint — the *other* platform's API for cross-platform sync
# E.g. on the Bale server this points to the Telegram server REST sync API
SYNC_PEER_URL = os.getenv("SYNC_PEER_URL", "")  # e.g. https://int-server:8800/sync
SYNC_SECRET = os.getenv("SYNC_SECRET", "")

# Cross-platform bot link — shown to users so they can also join the other platform
# On Telegram server set this to the Bale bot link (e.g. https://ble.ir/bot_username)
# On Bale server set this to the Telegram bot link (e.g. https://t.me/bot_username)
CROSS_PLATFORM_BOT_LINK = os.getenv("CROSS_PLATFORM_BOT_LINK", "")
CROSS_PLATFORM_BOT_NAME = os.getenv("CROSS_PLATFORM_BOT_NAME", "")

# Messages - centralized in messages.py, kept here for backward compatibility
from messages import REGISTRATION, USER, ADMIN as ADMIN_MESSAGES
MESSAGES = {
    "welcome": REGISTRATION["welcome"],
    "registration_complete": REGISTRATION["registration_complete"],
    "lesson_sent": USER["lesson_sent"],
    "lesson_completed": USER["lesson_completed"],
    "course_completed": USER["course_completed"],
    "admin_welcome": ADMIN_MESSAGES["welcome"],
    "unauthorized": REGISTRATION.get("unauthorized", "⛔️ شما اجازه دسترسی به این بخش را ندارید."),
    "error": "❌ خطایی رخ داد. لطفاً دوباره تلاش کنید.",
}

# Validation
def validate_config() -> List[str]:
    """Validate required configuration"""
    errors = []

    if not BOT_TOKEN:
        errors.append("BOT_TOKEN is required")

    if not ADMIN_USER_IDS:
        errors.append("At least one ADMIN_USER_ID is required")

    if not DB_PASSWORD:
        errors.append("DB_PASSWORD is required")

    return errors


if __name__ == "__main__":
    # Test configuration
    errors = validate_config()
    if errors:
        print("❌ Configuration errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("✅ Configuration is valid")
        print(f"📊 Database: {DB_HOST}:{DB_PORT}/{DB_NAME}")
        print(f"👥 Admins: {len(ADMIN_USER_IDS)}")
