"""
Smart Reminder Service - handles reminders, scheduled messages, and delayed lesson delivery
with course awareness and intelligent reminder logic.
"""
import logging
import random
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models import User, Lesson, ScheduledMessage, MessageStatus, ContentType, UserProgress
from services.lesson_service import LessonService
from services.event_emitter import emit
import config
from messages import REMINDERS, USER, USER_BUTTONS

logger = logging.getLogger(__name__)

# Smart reminder messages - from centralized config
REMINDER_MESSAGES = REMINDERS["templates"]


class ReminderService:
    """Service for managing smart reminders and scheduled messages"""

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

    async def _get_smart_reminder(self, user: User) -> str:
        """Generate a personalized smart reminder message"""
        lesson_service = LessonService(self.session)

        name = user.first_name or REMINDERS["default_name"]
        days_ago = (datetime.utcnow() - user.last_activity_at).days if user.last_activity_at else 0

        # Get progress for the user's current course, or overall
        course_id = user.current_course_id
        progress = await lesson_service.get_user_progress(user.id, course_id=course_id)

        template = random.choice(REMINDER_MESSAGES)
        return template.format(
            name=name,
            remaining=progress.get("remaining", "?"),
            progress=progress.get("progress_percent", 0),
            days_ago=days_ago,
        )

    async def _should_send_reminder(self, user: User) -> bool:
        """Check if we should send a reminder (avoid spamming)"""
        # Don't send more than 1 reminder per 2 days
        two_days_ago = datetime.utcnow() - timedelta(days=2)

        result = await self.session.execute(
            select(func.count(ScheduledMessage.id)).where(
                ScheduledMessage.user_id == user.id,
                ScheduledMessage.message_type == "reminder",
                ScheduledMessage.status == MessageStatus.SENT,
                ScheduledMessage.sent_at > two_days_ago,
            )
        )
        recent_reminders = result.scalar() or 0

        if recent_reminders > 0:
            return False

        # Don't send more than 5 reminders total per user
        result = await self.session.execute(
            select(func.count(ScheduledMessage.id)).where(
                ScheduledMessage.user_id == user.id,
                ScheduledMessage.message_type == "reminder",
                ScheduledMessage.status == MessageStatus.SENT,
            )
        )
        total_reminders = result.scalar() or 0

        if total_reminders >= 5:
            return False

        return True

    async def send_reminder(self, user: User, message: str = None):
        """Send smart reminder to inactive user.

        Returns True on success, None if throttled/skipped, False on failure.
        """
        if not await self._should_send_reminder(user):
            logger.debug(f"Skipping reminder for user {user.telegram_user_id} (throttled)")
            return None

        if not message:
            message = await self._get_smart_reminder(user)

        try:
            await self.bot.send_message(
                chat_id=user.telegram_user_id,
                text=message,
            )

            # Log the reminder as a scheduled message (for tracking)
            reminder_log = ScheduledMessage(
                user_id=user.id,
                message=message,
                message_type="reminder",
                send_at=datetime.utcnow(),
                status=MessageStatus.SENT,
                sent_at=datetime.utcnow(),
            )
            self.session.add(reminder_log)
            await self.session.commit()

            # Emit webhook event
            await emit(
                "reminder", "sent", user, self.session,
                extra_payload={"reminder_text": message[:200] if message else ""},
            )

            logger.info(f"Smart reminder sent to user {user.telegram_user_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to send reminder to {user.telegram_user_id}: {e}")
            return False

    async def send_reminders_to_inactive(self) -> dict:
        """Send smart reminders to all inactive users"""
        inactive_users = await self.find_inactive_users()

        sent = 0
        failed = 0
        skipped = 0

        for user in inactive_users:
            result = await self.send_reminder(user)
            if result is True:
                sent += 1
            elif result is None:
                skipped += 1
            else:
                failed += 1

        logger.info(
            f"Smart reminders: {sent} sent, {skipped} skipped, {failed} failed "
            f"out of {len(inactive_users)} inactive users"
        )
        return {
            "total": len(inactive_users),
            "sent": sent,
            "skipped": skipped,
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
                    user_result = await self.session.execute(
                        select(User).where(User.id == msg.user_id)
                    )
                    user = user_result.scalar_one_or_none()
                    if user:
                        if msg.message_type == "next_lesson":
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
        """Send the next lesson to a user (for delayed delivery) — course-aware"""
        lesson_service = LessonService(self.session)

        # Use user's current course
        course_id = user.current_course_id
        next_lesson = await lesson_service.get_next_lesson_for_user(user.id, course_id=course_id)

        if not next_lesson:
            return

        # Mark lesson as started
        await lesson_service.mark_lesson_started(user.id, next_lesson.id)

        # Update user's current lesson
        user.current_lesson_id = next_lesson.id
        await self.session.commit()

        # Build caption
        description = next_lesson.description or ""
        lesson_text = USER["lesson_sent"].format(
            lesson_number=next_lesson.order,
            lesson_title=next_lesson.title,
            description=description,
        )

        # Build keyboard
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text=USER_BUTTONS["lesson_seen_delayed"],
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

        # Multi-content delivery
        if next_lesson.contents and len(next_lesson.contents) > 0:
            for i, block in enumerate(next_lesson.contents):
                is_first = (i == 0)
                is_last = (i == len(next_lesson.contents) - 1)
                caption = lesson_text if is_first else None
                kb = keyboard if is_last else None
                await self._send_content_block(chat_id, block, caption, kb)
        elif next_lesson.content_type == ContentType.TEXT:
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
        elif next_lesson.content_type == ContentType.FORM:
            form_text = REMINDERS["form_lesson"].format(
                order=next_lesson.order,
                title=next_lesson.title,
                description=next_lesson.description or '',
            )
            await self.bot.send_message(chat_id=chat_id, text=form_text)
        else:
            await self.bot.send_message(chat_id=chat_id, text=lesson_text, reply_markup=keyboard)

        logger.info(f"Delayed lesson {next_lesson.id} sent to user {user.telegram_user_id}")

    async def _send_content_block(self, chat_id: int, block: dict, caption: str = None, keyboard=None):
        """Send a single content block for multi-content lessons"""
        block_type = block.get("type", "text")

        if block_type == "text":
            text = caption or ""
            if block.get("text"):
                text = f"{caption}\n\n{block['text']}" if caption else block["text"]
            if not text:
                text = "📝"
            await self.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)
        elif block_type == "video" and block.get("file_id"):
            await self.bot.send_video(chat_id=chat_id, video=block["file_id"], caption=caption, reply_markup=keyboard)
        elif block_type == "audio" and block.get("file_id"):
            await self.bot.send_audio(chat_id=chat_id, audio=block["file_id"], caption=caption, reply_markup=keyboard)
        elif block_type == "voice" and block.get("file_id"):
            await self.bot.send_voice(chat_id=chat_id, voice=block["file_id"], caption=caption, reply_markup=keyboard)
        elif block_type == "document" and block.get("file_id"):
            await self.bot.send_document(chat_id=chat_id, document=block["file_id"], caption=caption, reply_markup=keyboard)
        elif block_type == "photo" and block.get("file_id"):
            await self.bot.send_photo(chat_id=chat_id, photo=block["file_id"], caption=caption, reply_markup=keyboard)
        else:
            text = caption or block.get("text", "📝")
            await self.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)

    async def check_lesson_deadlines(self) -> dict:
        """
        Check for users who have uncompleted lessons with deadlines.
        Send reminders at 50%, 75%, and 100% of the deadline.
        Uses message_type="deadline_50", "deadline_75", "deadline_100" to track.
        """
        now = datetime.utcnow()
        sent = 0
        failed = 0

        # Find all lessons with deadlines
        lesson_result = await self.session.execute(
            select(Lesson).where(
                Lesson.view_deadline_hours.isnot(None),
                Lesson.is_active == True,
            )
        )
        deadline_lessons = list(lesson_result.scalars().all())

        if not deadline_lessons:
            return {"sent": 0, "failed": 0}

        for lesson in deadline_lessons:
            deadline_hours = lesson.view_deadline_hours
            if not deadline_hours or deadline_hours <= 0:
                continue

            # Find users who started but haven't completed this lesson
            progress_result = await self.session.execute(
                select(UserProgress).join(User).where(
                    UserProgress.lesson_id == lesson.id,
                    UserProgress.completed_at.is_(None),
                    User.is_active == True,
                )
            )
            uncompleted = list(progress_result.scalars().all())

            for progress in uncompleted:
                if not progress.started_at:
                    continue

                elapsed = now - progress.started_at.replace(tzinfo=None)
                elapsed_hours = elapsed.total_seconds() / 3600
                percent = (elapsed_hours / deadline_hours) * 100

                # Determine which reminder tier to send
                reminder_tier = None
                if percent >= 100:
                    reminder_tier = "deadline_100"
                elif percent >= 75:
                    reminder_tier = "deadline_75"
                elif percent >= 50:
                    reminder_tier = "deadline_50"

                if not reminder_tier:
                    continue

                # Check if already sent this tier
                existing = await self.session.execute(
                    select(func.count(ScheduledMessage.id)).where(
                        ScheduledMessage.user_id == progress.user_id,
                        ScheduledMessage.message_type == reminder_tier,
                        ScheduledMessage.status == MessageStatus.SENT,
                        ScheduledMessage.message.contains(f"lesson:{lesson.id}"),
                    )
                )
                if (existing.scalar() or 0) > 0:
                    continue

                # Get user info
                user_result = await self.session.execute(
                    select(User).where(User.id == progress.user_id)
                )
                user = user_result.scalar_one_or_none()
                if not user:
                    continue

                name = user.first_name or REMINDERS["default_name"]
                hours_left = max(0, int(deadline_hours - elapsed_hours))

                # Choose reminder template
                template_key = f"{reminder_tier.replace('deadline_', 'deadline_reminder_')}"
                template = REMINDERS.get(template_key, REMINDERS["deadline_reminder_100"])

                msg_text = template.format(
                    name=name,
                    lesson_title=lesson.title,
                    hours_left=hours_left,
                )

                try:
                    await self.bot.send_message(
                        chat_id=user.telegram_user_id,
                        text=msg_text,
                    )

                    # Log the reminder
                    reminder_log = ScheduledMessage(
                        user_id=user.id,
                        message=f"lesson:{lesson.id} - {msg_text[:100]}",
                        message_type=reminder_tier,
                        send_at=now,
                        status=MessageStatus.SENT,
                        sent_at=now,
                    )
                    self.session.add(reminder_log)
                    sent += 1
                    logger.info(
                        f"Deadline reminder ({reminder_tier}) sent to user {user.telegram_user_id} "
                        f"for lesson {lesson.id}"
                    )
                except Exception as e:
                    failed += 1
                    logger.warning(
                        f"Failed to send deadline reminder to {user.telegram_user_id}: {e}"
                    )

        await self.session.commit()
        return {"sent": sent, "failed": failed}
