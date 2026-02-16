"""
Telegram Course Bot - Main Entry Point
A complete course delivery bot with advanced admin panel
"""
import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

import config
from database import init_db
from utils.platform import platform_label
from utils.platform_bot import PlatformBot


# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    """Actions to perform on bot startup"""
    logger.info(f"🚀 Starting Course Bot on {platform_label()}...")

    # Validate configuration
    errors = config.validate_config()
    if errors:
        logger.error("❌ Configuration errors:")
        for error in errors:
            logger.error(f"  - {error}")
        sys.exit(1)

    # Initialize database with retry logic
    max_retries = 5
    retry_delay = 5

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Attempt {attempt}/{max_retries} to connect to database...")
            await init_db()
            logger.info("✅ Database initialized successfully")

            # Load text overrides from database
            from text_manager import load_overrides
            await load_overrides()
            logger.info("✅ Text overrides loaded")

            break
        except Exception as e:
            logger.warning(f"Failed to initialize database (attempt {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"❌ Failed to initialize database after {max_retries} attempts")
                sys.exit(1)

    # Send startup message to admins
    for admin_id in config.ADMIN_USER_IDS:
        try:
            await bot.send_message(
                admin_id,
                "✅ ربات با موفقیت راه‌اندازی شد!\n\n"
                "برای دسترسی به پنل ادمین دستور /admin را ارسال کنید."
            )
        except Exception as e:
            logger.warning(f"Failed to send startup message to admin {admin_id}: {e}")

    logger.info("✅ Bot started successfully")


async def on_shutdown(bot: Bot):
    """Actions to perform on bot shutdown"""
    logger.info("🛑 Shutting down bot...")

    # Send shutdown message to admins
    for admin_id in config.ADMIN_USER_IDS:
        try:
            await bot.send_message(
                admin_id,
                "⚠️ ربات متوقف شد."
            )
        except Exception as e:
            logger.warning(f"Failed to send shutdown message to admin {admin_id}: {e}")

    logger.info("✅ Bot shutdown complete")


async def main():
    """Main function to run the bot"""

    # Initialize bot and dispatcher
    # For Bale: use custom API URL via AiohttpSession
    session = None
    if config.PLATFORM == "bale":
        bale_api = TelegramAPIServer(
            base=f"{config.API_BASE_URL}/bot{{token}}/{{method}}",
            file=f"{config.API_BASE_URL}/file/bot{{token}}/{{path}}",
        )
        session = AiohttpSession(api=bale_api)

    bot = PlatformBot(
        token=config.BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML if config.PLATFORM == "telegram" else None
        )
    )

    dp = Dispatcher()

    # Register handlers
    from handlers.registration import router as registration_router
    from handlers.user import router as user_router
    from handlers.admin import router as admin_router
    from handlers.migration import router as migration_router

    dp.include_router(registration_router)
    dp.include_router(admin_router)
    dp.include_router(migration_router)
    dp.include_router(user_router)  # User router last (catch-all menus)

    # Setup scheduler
    from tasks.scheduler import setup_scheduler, start_scheduler, stop_scheduler
    setup_scheduler(bot)

    # Register startup and shutdown handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Start polling
    try:
        start_scheduler()
        logger.info("📡 Starting polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"❌ Error during polling: {e}")
        raise
    finally:
        stop_scheduler()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⚠️ Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
