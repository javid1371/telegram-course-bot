"""
Reminder service - handles reminders for inactive users
"""
import logging
from datetime import datetime, timedelta
from typing import List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models import User, Lesson, ScheduledMessage, MessageStatus, ContentType
from services.lesson_service import LessonService
import config

logger = logging.getLogger(__name__)


class ReminderService:
    """Service for managing reminders"""

    def __init__(self, session: AsyncSession, bot: Bot):
        self.session = session
        self.bot = bot

    async def find_inactive_users(self, days: int = None) -> List[User]:
        """Find users who haven't been active for specified days"""
        if days is None:
            days = config.REMINDER_DAYS

        cutoff = datetime.utcnow() - timedelta(days=days)

        result = await self.session.execute(
            select(User).where(
                User.is_active == True,
                User.is_completed == False,
                User.last_activity_at < cutoff,
            )
        )
        return list(result.scalars().all())

    async def send_reminder(self, user: User, message: str = None) -> bool:
        """Send reminder to inactive user"""
        if not message:
            message = (
                "👋 سلام!\n\n"
                "مدتیه که از دوره بازدید نکردید.\n"
                "درس‌های جدیدی منتظر شماست! 📚\n\n"
                "برای ادامه دوره دکمه /start را بزنید."
            )

        try:
            await self.bot.send_message(
                chat_id=user.telegram_user_id,
                text=message,
            )
            logger.info(f"Reminder sent to user {user.telegram_user_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to send reminder to {user.telegram_user_id}: {e}")
            return False

    async def send_reminders_to_inactive(self) -> dict:
        """Send reminders to all inactive users"""
        inactive_users = await self.find_inactive_users()

        sent = 0
        failed = 0

        for user in inactive_users:
            if await self.send_reminder(user):
                sent += 1
            else:
                failed += 1

        logger.info(f"Reminders sent: {sent} success, {failed} failed out of {len(inactive_users)}")
        return {
            "total": len(inactive_users),
            "sent": sent,
            "failed": failed,
        }

    async def schedule_message(
        self,
        message: str,
        send_at: datetime,
        user_id: int = None,
        message_type: str = "reminder",
    ) -> ScheduledMessage:
        """Schedule a message for later delivery"""
        scheduled = ScheduledMessage(
            user_id=user_id,
            message=message,
            message_type=message_type,
            send_at=send_at,
        )
        self.session.add(scheduled)
        await self.session.commit()
        await self.session.refresh(scheduled)
        return scheduled

    async def process_scheduled_messages(self) -> dict:
        """Process and send due scheduled messages"""
        now = datetime.utcnow()

        result = await self.session.execute(
            select(ScheduledMessage).where(
                ScheduledMessage.status == MessageStatus.PENDING,
                ScheduledMessage.send_at <= now,
            )
        )
        messages = list(result.scalars().all())

        sent = 0
        failed = 0

        for msg in messages:
            try:
                if msg.user_id:
                    # Get user's telegram ID
                    user_result = await self.session.execute(
                        select(User).where(User.id == msg.user_id)
                    )
                    user = user_result.scalar_one_or_none()
                    if user:
                        if msg.message_type == "next_lesson":
                            # Send the next lesson to the user
                            await self._send_next_lesson(user)
                        else:
                            await self.bot.send_message(
                                chat_id=user.telegram_user_id,
                                text=msg.message,
                            )

                msg.status = MessageStatus.SENT
                msg.sent_at = datetime.utcnow()
                sent += 1

            except Exception as e:
                msg.status = MessageStatus.FAILED
                msg.error_message = str(e)
                failed += 1
                logger.error(f"Failed to send scheduled message {msg.id}: {e}")

        await self.session.commit()
        return {"sent": sent, "failed": failed}

    async def _send_next_lesson(self, user: User):
        """Send the next lesson to a user (for delayed delivery)"""
        lesson_service = LessonService(self.session)
        next_lesson = await lesson_service.get_next_lesson_for_user(user.id)

        if not next_lesson:
            return

        # Mark lesson as started
        await lesson_service.mark_lesson_started(user.id, next_lesson.id)

        # Update user's current lesson
        user.current_lesson_id = next_lesson.id
        await self.session.commit()

        # Build caption
        description = next_lesson.description or ""
        lesson_text = config.MESSAGES["lesson_sent"].format(
            lesson_number=next_lesson.order,
            lesson_title=next_lesson.title,
            description=description,
        )

        # Build keyboard
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="✅ دیدم، ادامه بده",
                callback_data=f"confirm_lesson:{next_lesson.id}"
            )
        )
        if next_lesson.cta_text and next_lesson.cta_url:
            builder.row(
                InlineKeyboardButton(
                    text=next_lesson.cta_text,
                    url=next_lesson.cta_url
                )
            )
        keyboard = builder.as_markup()

        chat_id = user.telegram_user_id

        if next_lesson.content_type == ContentType.TEXT:
            full_text = lesson_text
            if next_lesson.text_content:
                full_text += f"\n\n{next_lesson.text_content}"
            await self.bot.send_message(chat_id=chat_id, text=full_text, reply_markup=keyboard)
        elif next_lesson.content_type == ContentType.VIDEO and next_lesson.file_id:
            await self.bot.send_video(chat_id=chat_id, video=next_lesson.file_id, caption=lesson_text, reply_markup=keyboard)
        elif next_lesson.content_type == ContentType.AUDIO and next_lesson.file_id:
            await self.bot.send_audio(chat_id=chat_id, audio=next_lesson.file_id, caption=lesson_text, reply_markup=keyboard)
        elif next_lesson.content_type == ContentType.VOICE and next_lesson.file_id:
            await self.bot.send_voice(chat_id=chat_id, voice=next_lesson.file_id, caption=lesson_text, reply_markup=keyboard)
        elif next_lesson.content_type == ContentType.DOCUMENT and next_lesson.file_id:
            await self.bot.send_document(chat_id=chat_id, document=next_lesson.file_id, caption=lesson_text, reply_markup=keyboard)
        elif next_lesson.content_type == ContentType.PHOTO and next_lesson.file_id:
            await self.bot.send_photo(chat_id=chat_id, photo=next_lesson.file_id, caption=lesson_text, reply_markup=keyboard)
        else:
            await self.bot.send_message(chat_id=chat_id, text=lesson_text, reply_markup=keyboard)

        logger.info(f"Delayed lesson {next_lesson.id} sent to user {user.telegram_user_id}")
