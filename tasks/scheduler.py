"""
Task scheduler - APScheduler jobs for periodic tasks
Reminders, daily stats, scheduled messages, webhook retries
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
from services.event_emitter import retry_failed_events, check_inactive_users

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

    @scheduler.scheduled_job(
        IntervalTrigger(minutes=30),
        id="check_lesson_deadlines",
        name="Check lesson deadlines and send reminders",
    )
    async def check_lesson_deadlines_job():
        """Check for lesson deadline reminders"""
        try:
            async with async_session_maker() as session:
                reminder_service = ReminderService(session, bot)
                result = await reminder_service.check_lesson_deadlines()
                if result["sent"] > 0 or result["failed"] > 0:
                    logger.info(
                        f"Deadline reminders: {result['sent']} sent, {result['failed']} failed"
                    )
        except Exception as e:
            logger.error(f"Error checking lesson deadlines: {e}")

    # ── Webhook retry & inactivity jobs ──

    @scheduler.scheduled_job(
        IntervalTrigger(hours=1),
        id="send_lesson_nudges",
        name="Send lesson nudge reminders (unconfirmed lessons)",
    )
    async def send_lesson_nudges_job():
        """Send nudge reminders to users who haven't confirmed their lesson"""
        try:
            async with async_session_maker() as session:
                reminder_service = ReminderService(session, bot)
                result = await reminder_service.send_lesson_nudge_reminders()
                if result["sent"] > 0 or result["failed"] > 0:
                    logger.info(
                        f"Lesson nudges: {result['sent']} sent, "
                        f"{result['skipped']} skipped, {result['failed']} failed"
                    )
        except Exception as e:
            logger.error(f"Error in lesson nudge job: {e}")

    @scheduler.scheduled_job(
        CronTrigger(hour=11, minute=0),  # Every day at 11:00 AM
        id="send_start_nudges",
        name="Send start course reminders (never-started users)",
    )
    async def send_start_nudges_job():
        """Send reminders to users who registered but never started"""
        try:
            async with async_session_maker() as session:
                reminder_service = ReminderService(session, bot)
                result = await reminder_service.send_start_course_reminders()
                if result["sent"] > 0 or result["failed"] > 0:
                    logger.info(
                        f"Start nudges: {result['sent']} sent, "
                        f"{result['skipped']} skipped, {result['failed']} failed"
                    )
        except Exception as e:
            logger.error(f"Error in start nudge job: {e}")

    @scheduler.scheduled_job(
        CronTrigger(hour=4, minute=0),  # 4:00 AM UTC = 7:30 AM Iran time
        id="send_morning_teasers",
        name="Send morning lesson teasers",
    )
    async def send_morning_teasers_job():
        """Send morning teaser to users with a lesson due today"""
        try:
            async with async_session_maker() as session:
                reminder_service = ReminderService(session, bot)
                result = await reminder_service.send_morning_lesson_teasers()
                if result["sent"] > 0 or result["failed"] > 0:
                    logger.info(
                        f"Morning teasers: {result['sent']} sent, "
                        f"{result['skipped']} skipped, {result['failed']} failed"
                    )
        except Exception as e:
            logger.error(f"Error in morning teaser job: {e}")

    @scheduler.scheduled_job(
        IntervalTrigger(minutes=5),
        id="retry_failed_webhooks",
        name="Retry failed webhook events",
    )
    async def retry_failed_webhooks_job():
        """Retry webhook events that failed delivery"""
        try:
            async with async_session_maker() as session:
                result = await retry_failed_events(session)
                if result["retried"] > 0:
                    logger.info(
                        f"Webhook retry: {result['retried']} processed, "
                        f"{result['resolved']} resolved, {result['abandoned']} abandoned"
                    )
        except Exception as e:
            logger.error(f"Error retrying failed webhooks: {e}")

    @scheduler.scheduled_job(
        CronTrigger(hour="*/12"),  # Every 12 hours
        id="check_inactivity",
        name="Check for inactive users and emit webhook",
    )
    async def check_inactivity_job():
        """Emit inactivity.timeout for users inactive 48h+"""
        try:
            async with async_session_maker() as session:
                result = await check_inactive_users(session)
                if result["emitted"] > 0:
                    logger.info(
                        f"Inactivity check: {result['emitted']} timeout events emitted"
                    )
        except Exception as e:
            logger.error(f"Error checking inactivity: {e}")

    # ── Smart Re-engagement: last-chance reminders ──

    @scheduler.scheduled_job(
        CronTrigger(hour=15, minute=0),  # 3 PM UTC ≈ 18:30 Iran
        id="last_chance_reminders",
        name="Send last-chance re-engagement reminders",
    )
    async def last_chance_reminders_job():
        """Send last-chance reminders to users who exhausted regular nudges"""
        try:
            async with async_session_maker() as session:
                service = ReminderService(session, bot)
                result = await service.send_last_chance_reminders()
                if result["sent"] > 0:
                    logger.info(
                        f"Last-chance reminders: {result['sent']} sent, "
                        f"{result['skipped']} skipped, {result['failed']} failed"
                    )
        except Exception as e:
            logger.error(f"Error sending last-chance reminders: {e}")

    # ── Cross-platform sync: flush pending events to peer ──

    @scheduler.scheduled_job(
        IntervalTrigger(seconds=30),
        id="flush_sync_events",
        name="Flush pending sync events to peer server",
    )
    async def flush_sync_events_job():
        """Push pending sync events to the peer platform."""
        try:
            from services.sync_service import flush_pending_events
            result = await flush_pending_events()
            flushed = result.get("flushed", 0)
            failed = result.get("failed", 0)
            if flushed > 0 or failed > 0:
                logger.info(
                    f"Sync flush: {flushed} pushed, {failed} failed"
                )
        except Exception as e:
            logger.error(f"Error flushing sync events: {e}")

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
