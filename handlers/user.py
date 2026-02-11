"""
User handlers - handles user-facing bot interactions
Lesson delivery, progress tracking, support, quiz, form
"""
import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import async_session_maker
from database.models import ContentType, ScheduledMessage, MessageStatus, QuizAttempt, FormResponse
from services.user_service import UserService
from services.lesson_service import LessonService
from services.webhook_service import WebhookService
from utils.keyboards import get_main_menu_keyboard, get_lesson_keyboard
from utils.decorators import registered_only, log_errors, rate_limit
from utils.helpers import calculate_progress, format_duration
import config

logger = logging.getLogger(__name__)
router = Router()


class UserStates(StatesGroup):
    """FSM states for user interactions"""
    filling_form = State()  # User is filling a form lesson


# ===========================
# LESSON DELIVERY
# ===========================

@router.message(F.text == "📚 ادامه دوره")
@log_errors
@rate_limit(2)
async def continue_course(message: Message, state: FSMContext):
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

        # Get active courses
        courses = await lesson_service.get_all_courses(active_only=True)
        if not courses:
            await message.answer("📭 هنوز دوره‌ای فعال نیست. لطفاً بعداً مراجعه کنید.")
            return

        # If user has a current_course_id, use that
        # Otherwise, if only 1 course, auto-select
        # If multiple courses, show selection
        if user.current_course_id:
            course = await lesson_service.get_course_by_id(user.current_course_id)
            if course and course.is_active:
                await _continue_specific_course(message, state, user, course, session, lesson_service)
                return

        if len(courses) == 1:
            # Auto-select single course
            course = courses[0]
            user.current_course_id = course.id
            await session.commit()
            await _continue_specific_course(message, state, user, course, session, lesson_service)
            return

        # Multiple courses — show selection
        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()

        completed_courses = user.completed_courses or {}
        for course in courses:
            is_done = completed_courses.get(str(course.id), False)
            status = "✅" if is_done else "📖"
            progress = await lesson_service.get_user_progress(user.id, course_id=course.id)
            builder.row(
                InlineKeyboardButton(
                    text=f"{status} {course.title} ({progress['progress_percent']}%)",
                    callback_data=f"select_course:{course.id}"
                )
            )

        await message.answer(
            "📚 <b>انتخاب دوره</b>\n\nکدام دوره را می‌خواهید ادامه دهید؟",
            reply_markup=builder.as_markup()
        )


@router.callback_query(F.data.startswith("select_course:"))
async def select_course(callback: CallbackQuery, state: FSMContext):
    """User selects a course to continue"""
    course_id = int(callback.data.split(":")[1])
    await callback.answer()

    async with async_session_maker() as session:
        user_service = UserService(session)
        lesson_service = LessonService(session)

        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        if not user:
            return

        course = await lesson_service.get_course_by_id(course_id)
        if not course:
            await callback.message.answer("❌ دوره یافت نشد.")
            return

        user.current_course_id = course.id
        await session.commit()

        await _continue_specific_course(callback.message, state, user, course, session, lesson_service)


async def _continue_specific_course(message: Message, state: FSMContext, user, course, session, lesson_service):
    """Continue a specific course — deliver next lesson"""
    # Check if course is completed for this user
    completed_courses = user.completed_courses or {}
    if completed_courses.get(str(course.id), False):
        await message.answer(
            f"🎉 شما دوره «{course.title}» را تکمیل کرده‌اید!\n\n"
            "برای انتخاب دوره دیگر، دوباره «📚 ادامه دوره» را بزنید."
        )
        # Reset current_course_id so next time they see the selection
        user.current_course_id = None
        await session.commit()
        return

    # Check if there's a pending scheduled lesson (delay active)
    from sqlalchemy import select as sa_select
    pending_result = await session.execute(
        sa_select(ScheduledMessage).where(
            ScheduledMessage.user_id == user.id,
            ScheduledMessage.message_type == "next_lesson",
            ScheduledMessage.status == MessageStatus.PENDING,
            ScheduledMessage.send_at > datetime.utcnow(),
        )
    )
    pending_scheduled = pending_result.scalars().first()
    if pending_scheduled:
        await message.answer(
            "⏳ درس بعدی هنوز آماده نیست.\n"
            "درس بعدی به‌صورت خودکار برای شما ارسال خواهد شد. لطفاً صبور باشید. 🙏"
        )
        return

    # Get next lesson in this course
    next_lesson = await lesson_service.get_next_lesson_for_user(user.id, course_id=course.id)

    if not next_lesson:
        total = await lesson_service.get_total_lessons_count(course_id=course.id)
        if total == 0:
            await message.answer(f"📭 دوره «{course.title}» هنوز درسی ندارد.")
        else:
            await message.answer(config.MESSAGES["course_completed"])
            # Mark course as completed
            if not completed_courses.get(str(course.id)):
                completed_courses[str(course.id)] = True
                user.completed_courses = completed_courses
                # Check if ALL courses done
                all_courses = await lesson_service.get_all_courses(active_only=True)
                all_done = all(completed_courses.get(str(c.id), False) for c in all_courses)
                user.is_completed = all_done
                await session.commit()
        return

    # Mark lesson as started
    await lesson_service.mark_lesson_started(user.id, next_lesson.id)

    # Update user's current lesson
    user.current_lesson_id = next_lesson.id
    await session.commit()

    # Handle FORM type lessons
    if next_lesson.content_type == ContentType.FORM and next_lesson.form_data:
        await _start_form_filling(message, state, next_lesson, user.id)
    else:
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
            "course_id": course.id,
            "course_title": course.title,
            "has_quiz": bool(next_lesson.quiz_data),
            "has_form": bool(next_lesson.form_data),
        }
    )


async def _send_lesson(message: Message, lesson):
    """Send lesson content based on type"""
    # Prepare lesson header
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

    # Multi-content delivery
    if lesson.contents and len(lesson.contents) > 0:
        for i, block in enumerate(lesson.contents):
            is_first = (i == 0)
            is_last = (i == len(lesson.contents) - 1)

            # First block gets the lesson header, last gets the keyboard
            caption = lesson_text if is_first else None
            kb = keyboard if is_last else None

            await _send_content_block(message, block, caption, kb)
        return

    # Single-content fallback (backward compat)
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

    elif lesson.content_type == ContentType.FORM:
        # FORM type with no form_data fallback — show as text
        full_text = lesson_text
        if lesson.text_content:
            full_text += f"\n\n{lesson.text_content}"
        await message.answer(full_text, reply_markup=keyboard)


async def _send_content_block(message: Message, block: dict, caption: str = None, keyboard=None):
    """Send a single content block (for multi-content lessons)"""
    block_type = block.get("type", "text")

    if block_type == "text":
        text = caption or ""
        if block.get("text"):
            text = f"{caption}\n\n{block['text']}" if caption else block["text"]
        if not text:
            text = "📝"
        await message.answer(text, reply_markup=keyboard)
    elif block_type == "video" and block.get("file_id"):
        await message.answer_video(video=block["file_id"], caption=caption, reply_markup=keyboard)
    elif block_type == "audio" and block.get("file_id"):
        await message.answer_audio(audio=block["file_id"], caption=caption, reply_markup=keyboard)
    elif block_type == "voice" and block.get("file_id"):
        await message.answer_voice(voice=block["file_id"], caption=caption, reply_markup=keyboard)
    elif block_type == "document" and block.get("file_id"):
        await message.answer_document(document=block["file_id"], caption=caption, reply_markup=keyboard)
    elif block_type == "photo" and block.get("file_id"):
        await message.answer_photo(photo=block["file_id"], caption=caption, reply_markup=keyboard)
    else:
        # Fallback
        text = caption or block.get("text", "📝")
        await message.answer(text, reply_markup=keyboard)


# ===========================
# FORM FILLING FLOW
# ===========================

async def _start_form_filling(message: Message, state: FSMContext, lesson, user_id: int):
    """Start the form filling process for a FORM lesson"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    form_data = lesson.form_data
    fields = form_data.get("fields", [])

    if not fields:
        # No fields — just show description and auto-complete
        desc = lesson.description or lesson.title
        await message.answer(f"📋 <b>{lesson.title}</b>\n\n{desc}")
        return

    # Store form state
    await state.set_state(UserStates.filling_form)
    await state.update_data(
        form_lesson_id=lesson.id,
        form_user_id=user_id,
        form_fields=fields,
        form_field_idx=0,
        form_responses={},
        form_title=lesson.title,
    )

    # Send intro
    await message.answer(
        f"📋 <b>{lesson.title}</b>\n\n"
        f"{lesson.description or ''}\n\n"
        f"لطفاً به سوالات زیر پاسخ دهید ({len(fields)} سوال):"
    )

    # Ask first field
    await _ask_form_field(message, fields[0], 0, len(fields), lesson.id)


async def _ask_form_field(message: Message, field: dict, idx: int, total: int, lesson_id: int):
    """Ask user a single form field"""
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    label = field.get("label", f"سوال {idx + 1}")
    field_type = field.get("type", "text")

    text = f"📝 سوال {idx + 1} از {total}:\n\n<b>{label}</b>"

    if field_type == "select":
        options = field.get("options", [])
        builder = InlineKeyboardBuilder()
        for opt_idx, opt in enumerate(options):
            builder.row(
                InlineKeyboardButton(
                    text=opt,
                    callback_data=f"fo:{lesson_id}:{idx}:{opt_idx}"
                )
            )
        await message.answer(text + "\n\nیکی از گزینه‌ها را انتخاب کنید:", reply_markup=builder.as_markup())
    else:
        type_hints = {
            "text": "پاسخ خود را تایپ کنید:",
            "number": "یک عدد وارد کنید:",
        }
        hint = type_hints.get(field_type, "پاسخ خود را وارد کنید:")
        await message.answer(f"{text}\n\n{hint}")


@router.callback_query(F.data.startswith("fo:"))
async def form_option_selected(callback: CallbackQuery, state: FSMContext):
    """Handle form select option selection"""
    parts = callback.data.split(":")
    lesson_id = int(parts[1])
    field_idx = int(parts[2])
    opt_idx = int(parts[3])

    await callback.answer()

    data = await state.get_data()
    if not data or data.get("form_lesson_id") != lesson_id:
        await callback.message.answer("⚠️ فرم نامعتبر. لطفاً دوباره تلاش کنید.")
        return

    fields = data.get("form_fields", [])
    if field_idx >= len(fields):
        return

    field = fields[field_idx]
    options = field.get("options", [])
    if opt_idx >= len(options):
        return

    selected_value = options[opt_idx]
    field_name = field.get("name", f"field_{field_idx}")

    # Save response
    responses = data.get("form_responses", {})
    responses[field_name] = selected_value

    next_idx = field_idx + 1

    if next_idx < len(fields):
        # Ask next field
        await state.update_data(form_responses=responses, form_field_idx=next_idx)
        await _ask_form_field(callback.message, fields[next_idx], next_idx, len(fields), lesson_id)
    else:
        # Form complete
        await state.clear()
        await _submit_form(callback.message, lesson_id, responses, callback.from_user.id, data.get("form_title", ""))


@router.message(UserStates.filling_form)
async def process_form_text_input(message: Message, state: FSMContext):
    """Handle text/number input for form fields"""
    data = await state.get_data()
    if not data:
        await state.clear()
        return

    fields = data.get("form_fields", [])
    field_idx = data.get("form_field_idx", 0)
    lesson_id = data.get("form_lesson_id")

    if field_idx >= len(fields):
        await state.clear()
        return

    field = fields[field_idx]
    field_type = field.get("type", "text")
    field_name = field.get("name", f"field_{field_idx}")

    # Validate based on type
    value = message.text.strip() if message.text else ""

    if field_type == "number":
        try:
            value = float(value)
            if value == int(value):
                value = int(value)
            value = str(value)
        except ValueError:
            await message.answer("⚠️ لطفاً یک عدد معتبر وارد کنید:")
            return

    if not value:
        await message.answer("⚠️ پاسخ نمی‌تواند خالی باشد. لطفاً دوباره وارد کنید:")
        return

    # Save response
    responses = data.get("form_responses", {})
    responses[field_name] = value

    next_idx = field_idx + 1

    if next_idx < len(fields):
        # Ask next field
        await state.update_data(form_responses=responses, form_field_idx=next_idx)
        await _ask_form_field(message, fields[next_idx], next_idx, len(fields), lesson_id)
    else:
        # Form complete
        form_title = data.get("form_title", "")
        await state.clear()
        await _submit_form(message, lesson_id, responses, message.from_user.id, form_title)


async def _submit_form(message: Message, lesson_id: int, responses: dict, telegram_user_id: int, form_title: str):
    """Save form response and complete the lesson"""
    async with async_session_maker() as session:
        user_service = UserService(session)
        lesson_service = LessonService(session)
        webhook_service = WebhookService(session)

        user = await user_service.get_user_by_telegram_id(telegram_user_id)
        if not user:
            return

        # Save form response
        form_response = FormResponse(
            user_id=user.id,
            lesson_id=lesson_id,
            response_data=responses,
        )
        session.add(form_response)
        await session.commit()

        # Show confirmation
        text = "✅ <b>فرم با موفقیت ارسال شد!</b>\n\n"
        text += f"📋 {form_title}\n\n"
        for key, val in responses.items():
            text += f"• {key}: {val}\n"
        await message.answer(text)

        # Send webhook
        await webhook_service.send_webhook(
            "form_submitted",
            user,
            extra_data={
                "lesson_id": lesson_id,
                "lesson_title": form_title,
                "form_title": form_title,
                "form_fields": list(responses.keys()),
                "form_responses": responses,
            }
        )

        # Complete the lesson
        await _complete_lesson_flow(message, user, lesson_id, session)


# ===========================
# LESSON CONFIRMATION
# ===========================

@router.callback_query(F.data.startswith("confirm_lesson:"))
async def confirm_lesson(callback: CallbackQuery, state: FSMContext):
    """Handle lesson confirmation"""
    lesson_id = int(callback.data.split(":")[1])
    await callback.answer("✅ تایید شد!")

    async with async_session_maker() as session:
        user_service = UserService(session)
        lesson_service = LessonService(session)

        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        if not user:
            return

        # Get current lesson to check for quiz
        current_lesson = await lesson_service.get_lesson_by_id(lesson_id)
        if not current_lesson:
            return

        # If lesson has a quiz, start quiz instead of completing
        if current_lesson.quiz_data and current_lesson.quiz_data.get("questions"):
            await _start_quiz(callback.message, state, current_lesson, user.id)
            return

        # No quiz — complete directly
        await _complete_lesson_flow(callback.message, user, lesson_id, session)


# ===========================
# QUIZ FLOW
# ===========================

async def _start_quiz(message: Message, state: FSMContext, lesson, user_id: int):
    """Start quiz for a lesson"""
    quiz_data = lesson.quiz_data
    questions = quiz_data.get("questions", [])
    passing_score = quiz_data.get("passing_score", 70)

    if not questions:
        return

    # Store quiz state
    await state.update_data(
        quiz_lesson_id=lesson.id,
        quiz_user_id=user_id,
        quiz_questions=questions,
        quiz_passing_score=passing_score,
        quiz_answers=[],
        quiz_current=0,
        quiz_title=lesson.title,
    )

    await message.answer(
        f"📝 <b>آزمون درس: {lesson.title}</b>\n\n"
        f"تعداد سوالات: {len(questions)}\n"
        f"حد نصاب قبولی: {passing_score}%\n\n"
        "بیایید شروع کنیم! 🚀"
    )

    # Send first question
    await _send_quiz_question(message, questions, 0, lesson.id)


async def _send_quiz_question(message: Message, questions: list, q_idx: int, lesson_id: int):
    """Send a quiz question with options"""
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    question = questions[q_idx]
    text = question.get("text", "")
    options = question.get("options", [])

    q_text = f"❓ سوال {q_idx + 1} از {len(questions)}:\n\n<b>{text}</b>"

    builder = InlineKeyboardBuilder()
    option_labels = ["🅰️", "🅱️", "🅲", "🅳", "🅴", "🅵"]

    for opt_idx, opt in enumerate(options):
        label = option_labels[opt_idx] if opt_idx < len(option_labels) else f"{opt_idx + 1}."
        builder.row(
            InlineKeyboardButton(
                text=f"{label} {opt}",
                callback_data=f"qa:{lesson_id}:{q_idx}:{opt_idx}"
            )
        )

    await message.answer(q_text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("qa:"))
async def quiz_answer(callback: CallbackQuery, state: FSMContext):
    """Handle quiz answer selection"""
    parts = callback.data.split(":")
    lesson_id = int(parts[1])
    q_idx = int(parts[2])
    opt_idx = int(parts[3])

    await callback.answer()

    data = await state.get_data()
    if not data or data.get("quiz_lesson_id") != lesson_id:
        await callback.message.answer("⚠️ آزمون نامعتبر. لطفاً درس را دوباره تایید کنید.")
        return

    questions = data.get("quiz_questions", [])
    answers = data.get("quiz_answers", [])

    if q_idx >= len(questions):
        return

    question = questions[q_idx]
    correct = question.get("correct", 0)
    is_correct = (opt_idx == correct)

    # Store answer
    answers.append({
        "question_idx": q_idx,
        "selected": opt_idx,
        "correct": correct,
        "is_correct": is_correct,
    })
    await state.update_data(quiz_answers=answers, quiz_current=q_idx + 1)

    # Show feedback
    option_text = question.get("options", [])[opt_idx] if opt_idx < len(question.get("options", [])) else "?"
    if is_correct:
        await callback.message.answer(f"✅ صحیح! {option_text}")
    else:
        correct_text = question.get("options", [])[correct] if correct < len(question.get("options", [])) else "?"
        await callback.message.answer(f"❌ اشتباه! پاسخ صحیح: {correct_text}")

    next_idx = q_idx + 1
    if next_idx < len(questions):
        # Next question
        await _send_quiz_question(callback.message, questions, next_idx, lesson_id)
    else:
        # Quiz finished
        await _finish_quiz(callback.message, state, answers, data)


async def _finish_quiz(message: Message, state: FSMContext, answers: list, quiz_data: dict):
    """Finish quiz, calculate score, and handle result"""
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    lesson_id = quiz_data.get("quiz_lesson_id")
    user_id = quiz_data.get("quiz_user_id")
    passing_score = quiz_data.get("quiz_passing_score", 70)
    quiz_title = quiz_data.get("quiz_title", "")

    total = len(answers)
    correct_count = sum(1 for a in answers if a.get("is_correct"))
    score = round((correct_count / total * 100) if total > 0 else 0, 1)
    passed = score >= passing_score

    await state.clear()

    async with async_session_maker() as session:
        # Save quiz attempt
        attempt = QuizAttempt(
            user_id=user_id,
            lesson_id=lesson_id,
            score=score,
            passed=passed,
            answers=answers,
        )
        session.add(attempt)
        await session.commit()

        user_service = UserService(session)
        # We need telegram_user_id to get user, but we have internal user_id
        # Get user by id
        from sqlalchemy import select
        from database.models import User
        user_result = await session.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()

        if passed:
            text = (
                f"🎉 <b>تبریک! آزمون قبول شد!</b>\n\n"
                f"📝 {quiz_title}\n"
                f"✅ پاسخ‌های صحیح: {correct_count} از {total}\n"
                f"📊 نمره: {score}%\n"
                f"🎯 حد نصاب: {passing_score}%"
            )
            await message.answer(text)

            # Send webhook
            if user:
                webhook_service = WebhookService(session)
                questions = quiz_data.get("quiz_questions", [])
                detailed_answers = []
                for ans in answers:
                    q = questions[ans["question_idx"]] if ans["question_idx"] < len(questions) else {}
                    opts = q.get("options", [])
                    detailed_answers.append({
                        "question": q.get("text", ""),
                        "selected_answer": opts[ans["selected"]] if ans["selected"] < len(opts) else "",
                        "correct_answer": opts[ans["correct"]] if ans["correct"] < len(opts) else "",
                        "is_correct": ans["is_correct"],
                    })
                await webhook_service.send_webhook(
                    "quiz_passed",
                    user,
                    extra_data={
                        "lesson_id": lesson_id,
                        "quiz_title": quiz_title,
                        "score": score,
                        "passing_score": passing_score,
                        "correct": correct_count,
                        "total": total,
                        "answers": detailed_answers,
                    }
                )

                # Complete the lesson
                await _complete_lesson_flow(message, user, lesson_id, session)
        else:
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(
                    text="🔄 تلاش مجدد",
                    callback_data=f"qr:{lesson_id}"
                )
            )

            text = (
                f"❌ <b>متأسفانه آزمون قبول نشد.</b>\n\n"
                f"📝 {quiz_title}\n"
                f"✅ پاسخ‌های صحیح: {correct_count} از {total}\n"
                f"📊 نمره: {score}%\n"
                f"🎯 حد نصاب: {passing_score}%\n\n"
                f"می‌توانید دوباره تلاش کنید:"
            )
            await message.answer(text, reply_markup=builder.as_markup())

            # Send webhook
            if user:
                webhook_service = WebhookService(session)
                questions = quiz_data.get("quiz_questions", [])
                detailed_answers = []
                for ans in answers:
                    q = questions[ans["question_idx"]] if ans["question_idx"] < len(questions) else {}
                    opts = q.get("options", [])
                    detailed_answers.append({
                        "question": q.get("text", ""),
                        "selected_answer": opts[ans["selected"]] if ans["selected"] < len(opts) else "",
                        "correct_answer": opts[ans["correct"]] if ans["correct"] < len(opts) else "",
                        "is_correct": ans["is_correct"],
                    })
                await webhook_service.send_webhook(
                    "quiz_failed",
                    user,
                    extra_data={
                        "lesson_id": lesson_id,
                        "quiz_title": quiz_title,
                        "score": score,
                        "passing_score": passing_score,
                        "correct": correct_count,
                        "total": total,
                        "answers": detailed_answers,
                    }
                )


@router.callback_query(F.data.startswith("qr:"))
async def quiz_retry(callback: CallbackQuery, state: FSMContext):
    """Handle quiz retry"""
    lesson_id = int(callback.data.split(":")[1])
    await callback.answer("🔄 شروع مجدد آزمون...")

    async with async_session_maker() as session:
        user_service = UserService(session)
        lesson_service = LessonService(session)

        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        if not user:
            return

        lesson = await lesson_service.get_lesson_by_id(lesson_id)
        if not lesson or not lesson.quiz_data:
            await callback.message.answer("⚠️ آزمون یافت نشد.")
            return

        await _start_quiz(callback.message, state, lesson, user.id)


# ===========================
# COMPLETE LESSON HELPER
# ===========================

async def _complete_lesson_flow(message: Message, user, lesson_id: int, session):
    """Handle post-completion: delay, scheduling, webhook"""
    lesson_service = LessonService(session)
    webhook_service = WebhookService(session)

    # Mark lesson as completed
    await lesson_service.mark_lesson_completed(user.id, lesson_id)

    # Get current lesson to check delay
    current_lesson = await lesson_service.get_lesson_by_id(lesson_id)
    delay_minutes = current_lesson.delay_hours if current_lesson else 0
    course_id = current_lesson.course_id if current_lesson else None

    # Get progress (course-specific)
    progress = await lesson_service.get_user_progress(user.id, course_id=course_id)

    if progress["remaining"] == 0:
        await message.answer(config.MESSAGES["course_completed"])

        # Send webhook
        await webhook_service.send_webhook(
            "course_completed",
            user,
            extra_data={
                "total_lessons": progress.get("total", 0),
                "completed_at": datetime.utcnow().isoformat(),
                "course_id": course_id,
                "course_title": current_lesson.course.title if current_lesson and current_lesson.course else "",
            }
        )
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

            await message.answer(
                config.MESSAGES["lesson_completed"].format(
                    lesson_number=lesson.order if lesson else "?",
                    progress=progress["progress_percent"],
                ) + f"\n\n📩 درس بعدی به‌صورت خودکار برای شما ارسال خواهد شد."
            )
        else:
            # Instant - tell user to click continue
            await message.answer(
                config.MESSAGES["lesson_completed"].format(
                    lesson_number=lesson.order if lesson else "?",
                    progress=progress["progress_percent"],
                ) + f"\n\n📚 برای دریافت درس بعدی روی «ادامه دوره» کلیک کنید."
            )

        # Send webhook
        await webhook_service.send_webhook(
            "lesson_completed",
            user,
            extra_data={
                "lesson_id": lesson_id,
                "lesson_title": current_lesson.title if current_lesson else "",
                "lesson_order": current_lesson.order if current_lesson else 0,
                "progress_percent": progress["progress_percent"],
                "completed_count": progress.get("completed", 0),
                "total_lessons": progress.get("total", 0),
            }
        )


# ===========================
# PROGRESS
# ===========================

@router.message(F.text == "📊 پیشرفت من")
@log_errors
async def show_progress(message: Message):
    """Show user's progress across all courses"""
    async with async_session_maker() as session:
        user_service = UserService(session)
        lesson_service = LessonService(session)

        user = await user_service.get_user_by_telegram_id(message.from_user.id)
        if not user:
            await message.answer("⚠️ لطفاً ابتدا ثبت‌نام کنید.\nدستور /start را ارسال کنید.")
            return

        courses = await lesson_service.get_all_courses(active_only=True)
        completed_courses = user.completed_courses or {}

        if not courses:
            # Fallback to overall progress
            progress = await lesson_service.get_user_progress(user.id)
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
            await message.answer(text)
            return

        text = "📊 <b>پیشرفت شما</b>\n\n"

        total_all = 0
        completed_all = 0

        for course in courses:
            progress = await lesson_service.get_user_progress(user.id, course_id=course.id)
            is_done = completed_courses.get(str(course.id), False)

            filled = int(progress["progress_percent"] / 10)
            bar = "🟢" * filled + "⚪️" * (10 - filled)

            status = "🎉 تکمیل شده" if is_done else f"{progress['progress_percent']}%"
            text += (
                f"📚 <b>{course.title}</b> — {status}\n"
                f"{bar}\n"
                f"✅ {progress['completed']}/{progress['total']} درس\n\n"
            )

            total_all += progress["total"]
            completed_all += progress["completed"]

        overall_pct = round(completed_all / total_all * 100) if total_all > 0 else 0
        text += f"📈 <b>مجموع:</b> {completed_all}/{total_all} درس ({overall_pct}%)"

        if user.is_completed:
            text += "\n\n🎉 تبریک! شما تمام دوره‌ها را تکمیل کرده‌اید!"

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
        courses = await lesson_service.get_all_courses(active_only=True)

        if not courses:
            total = await lesson_service.get_total_lessons_count()
            text = (
                f"📚 <b>درباره دوره</b>\n\n"
                f"تعداد درس‌ها: {total}\n\n"
                "برای شروع یا ادامه دوره از منوی اصلی استفاده کنید."
            )
        else:
            text = "📚 <b>دوره‌های موجود</b>\n\n"
            for course in courses:
                lesson_count = await lesson_service.get_course_lesson_count(course.id)
                text += f"📖 <b>{course.title}</b>\n"
                if course.description:
                    text += f"📝 {course.description}\n"
                text += f"📊 تعداد درس‌ها: {lesson_count}\n\n"
            text += "برای شروع یا ادامه دوره از منوی اصلی استفاده کنید."

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
