"""
User handlers - handles user-facing bot interactions
Lesson delivery, progress tracking, support
"""
import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from database import async_session_maker
from database.models import ContentType, ScheduledMessage, MessageStatus
from services.user_service import UserService
from services.lesson_service import LessonService
from services.webhook_service import WebhookService
from utils.keyboards import get_main_menu_keyboard, get_lesson_keyboard
from utils.decorators import registered_only, log_errors, rate_limit
from utils.helpers import calculate_progress, format_duration
import config

logger = logging.getLogger(__name__)
router = Router()


# ===========================
# LESSON DELIVERY
# ===========================

@router.message(F.text == "📚 ادامه دوره")
@log_errors
@rate_limit(2)
async def continue_course(message: Message):
    """Send next lesson to user"""
    async with async_session_maker() as session:
        user_service = UserService(session)
        lesson_service = LessonService(session)

        user = await user_service.get_user_by_telegram_id(message.from_user.id)
        if not user:
            await message.answer(
                "⚠️ لطفاً ابتدا ثبت‌نام کنید.\nدستور /start را ارسال کنید."
            )
            return

        if user.is_completed:
            await message.answer(config.MESSAGES["course_completed"])
            return

        # Get next lesson
        next_lesson = await lesson_service.get_next_lesson_for_user(user.id)

        if not next_lesson:
            # Check if there are any lessons at all
            total = await lesson_service.get_total_lessons_count()
            if total == 0:
                await message.answer("📭 هنوز درسی اضافه نشده. لطفاً بعداً مراجعه کنید.")
            else:
                await message.answer(config.MESSAGES["course_completed"])
                user.is_completed = True
                await session.commit()
            return

        # Mark lesson as started
        await lesson_service.mark_lesson_started(user.id, next_lesson.id)

        # Update user's current lesson
        user.current_lesson_id = next_lesson.id
        await session.commit()

        # Send lesson content
        await _send_lesson(message, next_lesson)

        # Send webhook
        webhook_service = WebhookService(session)
        await webhook_service.send_webhook(
            "lesson_sent",
            user,
            extra_data={
                "lesson_id": next_lesson.id,
                "lesson_title": next_lesson.title,
                "lesson_order": next_lesson.order,
            }
        )


async def _send_lesson(message: Message, lesson):
    """Send lesson content based on type"""
    # Prepare lesson message
    description = lesson.description or ""
    lesson_text = config.MESSAGES["lesson_sent"].format(
        lesson_number=lesson.order,
        lesson_title=lesson.title,
        description=description,
    )

    keyboard = get_lesson_keyboard(
        lesson.id,
        cta_text=lesson.cta_text,
        cta_url=lesson.cta_url,
    )

    if lesson.content_type == ContentType.TEXT:
        # Text lesson
        full_text = lesson_text
        if lesson.text_content:
            full_text += f"\n\n{lesson.text_content}"
        await message.answer(full_text, reply_markup=keyboard)

    elif lesson.content_type == ContentType.VIDEO:
        if lesson.file_id:
            await message.answer_video(
                video=lesson.file_id,
                caption=lesson_text,
                reply_markup=keyboard,
            )
        else:
            await message.answer(lesson_text, reply_markup=keyboard)

    elif lesson.content_type == ContentType.AUDIO:
        if lesson.file_id:
            await message.answer_audio(
                audio=lesson.file_id,
                caption=lesson_text,
                reply_markup=keyboard,
            )
        else:
            await message.answer(lesson_text, reply_markup=keyboard)

    elif lesson.content_type == ContentType.VOICE:
        if lesson.file_id:
            await message.answer_voice(
                voice=lesson.file_id,
                caption=lesson_text,
                reply_markup=keyboard,
            )
        else:
            await message.answer(lesson_text, reply_markup=keyboard)

    elif lesson.content_type == ContentType.DOCUMENT:
        if lesson.file_id:
            await message.answer_document(
                document=lesson.file_id,
                caption=lesson_text,
                reply_markup=keyboard,
            )
        else:
            await message.answer(lesson_text, reply_markup=keyboard)

    elif lesson.content_type == ContentType.PHOTO:
        if lesson.file_id:
            await message.answer_photo(
                photo=lesson.file_id,
                caption=lesson_text,
                reply_markup=keyboard,
            )
        else:
            await message.answer(lesson_text, reply_markup=keyboard)


# ===========================
# LESSON CONFIRMATION
# ===========================

@router.callback_query(F.data.startswith("confirm_lesson:"))
async def confirm_lesson(callback: CallbackQuery):
    """Handle lesson confirmation"""
    lesson_id = int(callback.data.split(":")[1])
    await callback.answer("✅ تایید شد!")

    async with async_session_maker() as session:
        user_service = UserService(session)
        lesson_service = LessonService(session)

        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        if not user:
            return

        # Mark lesson as completed
        await lesson_service.mark_lesson_completed(user.id, lesson_id)

        # Get current lesson to check delay
        current_lesson = await lesson_service.get_lesson_by_id(lesson_id)
        delay_minutes = current_lesson.delay_hours if current_lesson else 0  # column is delay_hours but stores minutes

        # Get progress
        progress = await lesson_service.get_user_progress(user.id)

        if progress["remaining"] == 0:
            await callback.message.answer(config.MESSAGES["course_completed"])

            # Send webhook
            webhook_service = WebhookService(session)
            await webhook_service.send_webhook("course_completed", user)
        else:
            lesson = current_lesson

            if delay_minutes > 0:
                # Schedule next lesson delivery
                send_at = datetime.utcnow() + timedelta(minutes=delay_minutes)
                scheduled = ScheduledMessage(
                    user_id=user.id,
                    message="__next_lesson__",
                    message_type="next_lesson",
                    send_at=send_at,
                )
                session.add(scheduled)
                await session.commit()

                # Format delay text
                if delay_minutes < 60:
                    delay_text = f"{delay_minutes} دقیقه"
                elif delay_minutes < 1440:
                    hours = delay_minutes // 60
                    rem = delay_minutes % 60
                    if rem > 0:
                        delay_text = f"{hours} ساعت و {rem} دقیقه"
                    else:
                        delay_text = f"{hours} ساعت"
                else:
                    days = delay_minutes // 1440
                    remaining = delay_minutes % 1440
                    hours = remaining // 60
                    rem_min = remaining % 60
                    parts = [f"{days} روز"]
                    if hours > 0:
                        parts.append(f"{hours} ساعت")
                    if rem_min > 0:
                        parts.append(f"{rem_min} دقیقه")
                    delay_text = " و ".join(parts)

                await callback.message.answer(
                    config.MESSAGES["lesson_completed"].format(
                        lesson_number=lesson.order if lesson else "?",
                        progress=progress["progress_percent"],
                    ) + f"\n\n⏱ درس بعدی <b>{delay_text}</b> دیگر برای شما ارسال می‌شود."
                )
            else:
                # Instant - tell user to click continue
                await callback.message.answer(
                    config.MESSAGES["lesson_completed"].format(
                        lesson_number=lesson.order if lesson else "?",
                        progress=progress["progress_percent"],
                    ) + f"\n\n📚 برای دریافت درس بعدی روی «ادامه دوره» کلیک کنید."
                )

            # Send webhook
            webhook_service = WebhookService(session)
            await webhook_service.send_webhook(
                "lesson_completed",
                user,
                extra_data={
                    "lesson_id": lesson_id,
                    "progress_percent": progress["progress_percent"],
                }
            )


# ===========================
# PROGRESS
# ===========================

@router.message(F.text == "📊 پیشرفت من")
@log_errors
async def show_progress(message: Message):
    """Show user's progress"""
    async with async_session_maker() as session:
        user_service = UserService(session)
        lesson_service = LessonService(session)

        user = await user_service.get_user_by_telegram_id(message.from_user.id)
        if not user:
            await message.answer("⚠️ لطفاً ابتدا ثبت‌نام کنید.\nدستور /start را ارسال کنید.")
            return

        progress = await lesson_service.get_user_progress(user.id)

        # Create progress bar
        filled = int(progress["progress_percent"] / 10)
        bar = "🟢" * filled + "⚪️" * (10 - filled)

        text = (
            f"📊 <b>پیشرفت شما</b>\n\n"
            f"{bar}\n"
            f"📈 {progress['progress_percent']}% تکمیل شده\n\n"
            f"✅ درس‌های تکمیل شده: {progress['completed']}\n"
            f"📚 کل درس‌ها: {progress['total']}\n"
            f"📋 باقی‌مانده: {progress['remaining']}\n"
        )

        if user.is_completed:
            text += "\n🎉 تبریک! شما دوره را تکمیل کرده‌اید!"

        await message.answer(text)


# ===========================
# ABOUT & SUPPORT
# ===========================

@router.message(F.text == "ℹ️ درباره دوره")
@log_errors
async def about_course(message: Message):
    """Show course information"""
    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        total = await lesson_service.get_total_lessons_count()

        text = (
            f"📚 <b>درباره دوره</b>\n\n"
            f"تعداد درس‌ها: {total}\n\n"
            "برای شروع یا ادامه دوره از منوی اصلی استفاده کنید."
        )
        await message.answer(text)


@router.message(F.text == "📞 پشتیبانی")
@log_errors
async def support(message: Message):
    """Show support info"""
    await message.answer(
        "📞 <b>پشتیبانی</b>\n\n"
        "در صورت وجود مشکل یا سوال، پیام خود را ارسال کنید.\n"
        "تیم پشتیبانی در اسرع وقت پاسخگو خواهد بود.\n\n"
        "همچنین می‌توانید از دستورات زیر استفاده کنید:\n"
        "/start - شروع مجدد\n"
        "/progress - مشاهده پیشرفت\n"
        "/help - راهنما"
    )


@router.message(Command("progress"))
@log_errors
async def cmd_progress(message: Message):
    """Handle /progress command"""
    await show_progress(message)


@router.message(Command("help"))
@log_errors
async def cmd_help(message: Message):
    """Handle /help command"""
    text = (
        "📖 <b>راهنمای ربات</b>\n\n"
        "🔹 /start - شروع یا ورود مجدد\n"
        "🔹 /progress - مشاهده پیشرفت\n"
        "🔹 /help - این راهنما\n\n"
        "📚 <b>ادامه دوره</b> - دریافت درس بعدی\n"
        "📊 <b>پیشرفت من</b> - مشاهده وضعیت پیشرفت\n"
        "ℹ️ <b>درباره دوره</b> - اطلاعات دوره\n"
        "📞 <b>پشتیبانی</b> - ارتباط با پشتیبانی"
    )
    await message.answer(text)
