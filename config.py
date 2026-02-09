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

# Telegram Bot
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_USER_IDS = [
    int(uid.strip()) 
    for uid in os.getenv("ADMIN_USER_IDS", "").split(",") 
    if uid.strip()
]

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

# Bot Settings
MAX_LESSONS_PER_USER = int(os.getenv("MAX_LESSONS_PER_USER", "100"))
REMINDER_DAYS = int(os.getenv("REMINDER_DAYS", "3"))
BROADCAST_RATE_LIMIT = int(os.getenv("BROADCAST_RATE_LIMIT", "30"))

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

# Telegram API Limits
MAX_MESSAGE_LENGTH = 4096
MAX_CAPTION_LENGTH = 1024
BROADCAST_SLEEP_SECONDS = 0.05  # 20 messages per second (safe limit)
FILE_SIZE_LIMIT = 50 * 1024 * 1024  # 50 MB

# Messages
MESSAGES = {
    "welcome": "🎓 به دوره آموزشی ما خوش آمدید!\n\nبرای شروع، لطفاً اطلاعات خود را وارد کنید.",
    "registration_complete": "✅ ثبت‌نام شما با موفقیت انجام شد!\n\nدرس اول به زودی برای شما ارسال می‌شود.",
    "lesson_sent": "📚 درس {lesson_number} - {lesson_title}\n\n{description}",
    "lesson_completed": "✅ تبریک! درس {lesson_number} را تکمیل کردید.\n\n🎯 پیشرفت شما: {progress}%",
    "course_completed": "🎉 تبریک! شما دوره را با موفقیت تکمیل کردید!\n\n🏆 آفرین!",
    "admin_welcome": "👋 سلام ادمین عزیز!\n\nبه پنل مدیریت خوش آمدید.",
    "unauthorized": "⛔️ شما اجازه دسترسی به این بخش را ندارید.",
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
