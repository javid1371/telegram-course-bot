"""
Task scheduler - APScheduler jobs for periodic tasks
Reminders, daily stats, scheduled messages
"""
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from aiogram import Bot

from database import async_session_maker
from services.reminder_service import ReminderService
from services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def setup_scheduler(bot: Bot):
    """Setup and configure the scheduler with all jobs"""

    @scheduler.scheduled_job(
        CronTrigger(hour=10, minute=0),  # Every day at 10:00 AM
        id="send_reminders",
        name="Send reminders to inactive users",
    )
    async def send_reminders_job():
        """Send reminders to inactive users"""
        logger.info("Running reminders job...")
        try:
            async with async_session_maker() as session:
                reminder_service = ReminderService(session, bot)
                result = await reminder_service.send_reminders_to_inactive()
                logger.info(
                    f"Reminders job completed: {result['sent']} sent, "
                    f"{result['failed']} failed out of {result['total']}"
                )
        except Exception as e:
            logger.error(f"Error in reminders job: {e}")

    @scheduler.scheduled_job(
        CronTrigger(hour=23, minute=55),  # Every day at 23:55
        id="save_daily_stats",
        name="Save daily statistics",
    )
    async def save_daily_stats_job():
        """Save daily statistics snapshot"""
        logger.info("Running daily stats job...")
        try:
            async with async_session_maker() as session:
                analytics_service = AnalyticsService(session)
                await analytics_service.save_daily_stats()
                logger.info("Daily stats saved successfully")
        except Exception as e:
            logger.error(f"Error in daily stats job: {e}")

    @scheduler.scheduled_job(
        IntervalTrigger(minutes=5),
        id="process_scheduled_messages",
        name="Process scheduled messages",
    )
    async def process_scheduled_messages_job():
        """Process and send due scheduled messages"""
        try:
            async with async_session_maker() as session:
                reminder_service = ReminderService(session, bot)
                result = await reminder_service.process_scheduled_messages()
                if result["sent"] > 0 or result["failed"] > 0:
                    logger.info(
                        f"Scheduled messages: {result['sent']} sent, {result['failed']} failed"
                    )
        except Exception as e:
            logger.error(f"Error processing scheduled messages: {e}")

    return scheduler


def start_scheduler():
    """Start the scheduler"""
    if not scheduler.running:
        scheduler.start()
        logger.info("✅ Scheduler started")


def stop_scheduler():
    """Stop the scheduler"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("🛑 Scheduler stopped")
