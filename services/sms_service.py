"""
SMS Service — Kavenegar integration for re-engagement SMS messages.
Used as the last resort after all Telegram nudges have been exhausted.

Tiers:
  SMS ① — 72h+ inactive, ≥40% progress
  SMS ② — 7 days inactive
  SMS ③ — 14 days inactive (final goodbye)
Max 3 SMS per user lifetime.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

import aiohttp
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, ScheduledMessage, MessageStatus
from services.lesson_service import LessonService
import config
from messages import REMINDERS

logger = logging.getLogger(__name__)

# Kavenegar API
KAVENEGAR_API_URL = "https://api.kavenegar.com/v1/{api_key}/sms/send.json"

# SMS tiers: (inactive_days, tier_name, message_key)
SMS_TIERS = [
    (3, "sms_tier_1", "sms_nudge_1"),     # 72h
    (7, "sms_tier_2", "sms_nudge_2"),     # 7 days
    (14, "sms_tier_3", "sms_nudge_3"),    # 14 days — final
]

MAX_SMS_PER_USER = 3
MIN_PROGRESS_PERCENT = 40
SEND_HOUR_START = 6   # UTC ~09:30 Iran
SEND_HOUR_END = 16    # UTC ~19:30 Iran


class SMSService:
    """Kavenegar SMS service for user re-engagement."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.api_key = getattr(config, "KAVENEGAR_API_KEY", "")
        self.sender = getattr(config, "KAVENEGAR_SENDER", "")
        self.enabled = getattr(config, "SMS_ENABLED", False)

    async def send_sms(self, phone: str, message: str) -> bool:
        """Send a single SMS via Kavenegar API."""
        if not self.enabled or not self.api_key:
            logger.warning("SMS is disabled or API key not set")
            return False

        # Normalize phone: ensure starts with 0 for Iranian numbers
        phone = phone.strip()
        if phone.startswith("+98"):
            phone = "0" + phone[3:]
        elif phone.startswith("98") and len(phone) == 12:
            phone = "0" + phone[2:]

        url = KAVENEGAR_API_URL.format(api_key=self.api_key)
        params = {
            "receptor": phone,
            "message": message,
        }
        if self.sender:
            params["sender"] = self.sender

        try:
            async with aiohttp.ClientSession() as http:
                async with http.post(url, data=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    result = await resp.json()
                    status = result.get("return", {}).get("status")
                    if status == 200:
                        logger.info(f"SMS sent to {phone[:4]}***{phone[-2:]}")
                        return True
                    else:
                        msg = result.get("return", {}).get("message", "unknown")
                        logger.error(f"Kavenegar error: {status} — {msg}")
                        return False
        except Exception as e:
            logger.error(f"SMS send failed for {phone[:4]}***: {e}")
            return False

    async def _get_user_phone(self, user: User) -> Optional[str]:
        """Extract phone from user's registration data."""
        # Try registration_data fields first
        reg = user.registration_data or {}
        for key in ("phone", "mobile", "شماره تماس", "شماره موبایل", "شماره همراه"):
            val = reg.get(key)
            if val and len(str(val).strip()) >= 10:
                return str(val).strip()
        return None

    async def _count_sms_sent(self, user_id: int) -> int:
        """Count total SMS sent to this user."""
        result = await self.session.execute(
            select(func.count(ScheduledMessage.id)).where(
                ScheduledMessage.user_id == user_id,
                ScheduledMessage.message_type.like("sms_tier_%"),
                ScheduledMessage.status == MessageStatus.SENT,
            )
        )
        return result.scalar() or 0

    async def _has_tier_been_sent(self, user_id: int, tier_name: str) -> bool:
        """Check if a specific SMS tier was already sent to this user."""
        result = await self.session.execute(
            select(func.count(ScheduledMessage.id)).where(
                ScheduledMessage.user_id == user_id,
                ScheduledMessage.message_type == tier_name,
                ScheduledMessage.status == MessageStatus.SENT,
            )
        )
        return (result.scalar() or 0) > 0

    async def send_sms_nudge_reminders(self) -> dict:
        """
        Send SMS re-engagement reminders.
        Runs once daily. Checks all active non-completed users against
        SMS tiers based on inactivity duration.

        Returns: {"sent": N, "failed": N, "skipped": N}
        """
        if not self.enabled:
            return {"sent": 0, "failed": 0, "skipped": 0}

        # Check sending hours (UTC)
        now = datetime.utcnow()
        if now.hour < SEND_HOUR_START or now.hour >= SEND_HOUR_END:
            logger.info("SMS: outside sending hours, skipping")
            return {"sent": 0, "failed": 0, "skipped": 0}

        sent = 0
        failed = 0
        skipped = 0

        lesson_service = LessonService(self.session)

        # Find inactive users (active, not completed, last_activity 3+ days ago)
        cutoff = now - timedelta(days=SMS_TIERS[0][0])  # earliest tier = 3 days
        result = await self.session.execute(
            select(User).where(
                User.is_active == True,
                User.is_completed == False,
                User.last_activity_at.isnot(None),
                User.last_activity_at <= cutoff,
            )
        )
        users = list(result.scalars().all())

        if not users:
            return {"sent": 0, "failed": 0, "skipped": 0}

        for user in users:
            try:
                # Check max SMS cap
                total_sms = await self._count_sms_sent(user.id)
                if total_sms >= MAX_SMS_PER_USER:
                    skipped += 1
                    continue

                # Get phone
                phone = await self._get_user_phone(user)
                if not phone:
                    skipped += 1
                    continue

                # Get progress
                course_id = user.current_course_id
                progress = await lesson_service.get_user_progress(user.id, course_id=course_id)
                percent = progress.get("progress_percent", 0)
                remaining = progress.get("remaining", 999)

                if percent < MIN_PROGRESS_PERCENT:
                    skipped += 1
                    continue

                # Calculate inactive days
                last_act = user.last_activity_at
                if last_act and last_act.tzinfo:
                    last_act = last_act.replace(tzinfo=None)
                inactive_days = (now - last_act).days if last_act else 999

                # Find the highest applicable tier not yet sent
                applicable_tier = None
                for days_threshold, tier_name, msg_key in SMS_TIERS:
                    if inactive_days >= days_threshold and not await self._has_tier_been_sent(user.id, tier_name):
                        applicable_tier = (days_threshold, tier_name, msg_key)

                if not applicable_tier:
                    skipped += 1
                    continue

                _, tier_name, msg_key = applicable_tier
                name = user.first_name or "دوست عزیز"

                # Build bot link
                bot_base = "https://ble.ir" if config.PLATFORM == "bale" else "https://t.me"
                bot_link = f"{bot_base}/{config.BOT_USERNAME}"

                # Get message template
                msg_text = REMINDERS.get(msg_key, "").format(
                    name=name,
                    percent=percent,
                    remaining=remaining,
                    bot_link=bot_link,
                )

                if not msg_text:
                    skipped += 1
                    continue

                # Send SMS
                success = await self.send_sms(phone, msg_text)

                if success:
                    # Log in scheduled_messages
                    log_entry = ScheduledMessage(
                        user_id=user.id,
                        message=f"SMS {tier_name}: {msg_text[:80]}",
                        message_type=tier_name,
                        send_at=now,
                        status=MessageStatus.SENT,
                        sent_at=now,
                    )
                    self.session.add(log_entry)
                    sent += 1
                    logger.info(
                        f"SMS {tier_name} sent to user {user.id} "
                        f"(phone: {phone[:4]}***, {percent}% done, {inactive_days}d inactive)"
                    )
                else:
                    failed += 1

            except Exception as e:
                logger.error(f"SMS processing error for user {user.id}: {e}")
                failed += 1

        await self.session.commit()
        logger.info(f"SMS nudges: {sent} sent, {skipped} skipped, {failed} failed")
        return {"sent": sent, "failed": failed, "skipped": skipped}
