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
from utils.keyboards import get_main_menu_keyboard, get_lesson_keyboard, get_confirm_keyboard
from utils.decorators import registered_only, log_errors, rate_limit
from utils.helpers import calculate_progress, format_duration
import config
from messages import USER, USER_BUTTONS, GENERAL, CONTENT_TYPES

logger = logging.getLogger(__name__)
router = Router()


class UserStates(StatesGroup):
    """FSM states for user interactions"""
    filling_form = State()  # User is filling a form lesson


# ===========================
# LESSON DELIVERY
# ===========================

@router.message(F.text == USER_BUTTONS["continue_course"])
@log_errors
@rate_limit(2)
async def continue_course(message: Message, state: FSMContext):
    """Send next lesson to user"""
    async with async_session_maker() as session:
        user_service = UserService(session)
        lesson_service = LessonService(session)

        user = await user_service.get_user_by_telegram_id(message.from_user.id)
        if not user:
            await message.answer(USER["please_register"])
            return

        # Get active courses
        courses = await lesson_service.get_all_courses(active_only=True)
        if not courses:
            await message.answer(USER["no_active_course"])
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
            USER["select_course"],
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
            await callback.message.answer(USER["course_not_found"])
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
            USER["course_already_completed"].format(title=course.title)
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
        await message.answer(USER["lesson_not_ready"])
        return

    # Get next lesson in this course
    next_lesson = await lesson_service.get_next_lesson_for_user(user.id, course_id=course.id)

    if not next_lesson:
        total = await lesson_service.get_total_lessons_count(course_id=course.id)
        if total == 0:
            await message.answer(USER["course_no_lessons"].format(title=course.title))
        else:
            await message.answer(USER["course_completed"])
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
    lesson_text = USER["lesson_sent"].format(
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
        USER["form_intro"].format(
            title=lesson.title,
            description=lesson.description or '',
            count=len(fields),
        )
    )

    # Ask first field
    await _ask_form_field(message, fields[0], 0, len(fields), lesson.id)


async def _ask_form_field(message: Message, field: dict, idx: int, total: int, lesson_id: int):
    """Ask user a single form field"""
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    label = field.get("label", f"سوال {idx + 1}")
    field_type = field.get("type", "text")

    text = USER["form_question"].format(idx=idx + 1, total=total, label=label)

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
        await message.answer(text + "\n\n" + USER["form_select_hint"], reply_markup=builder.as_markup())
    else:
        type_hints = {
            "text": USER["form_text_hint"],
            "number": USER["form_number_hint"],
        }
        hint = type_hints.get(field_type, USER["form_default_hint"])
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
        await callback.message.answer(USER["form_invalid"])
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
            await message.answer(USER["form_number_error"])
            return

    if not value:
        await message.answer(USER["form_empty_error"])
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
        text = USER["form_submitted"] + "\n\n"
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
    await callback.answer(USER["lesson_confirmed"])

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
        USER["quiz_intro"].format(
            title=lesson.title,
            count=len(questions),
            passing_score=passing_score,
        )
    )

    # Send first question
    await _send_quiz_question(message, questions, 0, lesson.id)


async def _send_quiz_question(message: Message, questions: list, q_idx: int, lesson_id: int):
    """Send a quiz question with options (single or multi-select)"""
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    question = questions[q_idx]
    text = question.get("text", "")
    options = question.get("options", [])
    is_multi = question.get("multi_select", False)

    q_text = USER["quiz_question"].format(idx=q_idx + 1, total=len(questions), text=text)
    if is_multi:
        q_text += "\n\n" + USER["quiz_multi_select_hint"]

    builder = InlineKeyboardBuilder()
    option_labels = ["🅰️", "🅱️", "🅲", "🅳", "🅴", "🅵"]

    if is_multi:
        # Multi-select: toggle buttons + confirm
        for opt_idx, opt in enumerate(options):
            label = option_labels[opt_idx] if opt_idx < len(option_labels) else f"{opt_idx + 1}."
            builder.row(
                InlineKeyboardButton(
                    text=f"⬜️ {label} {opt}",
                    callback_data=f"qm:{lesson_id}:{q_idx}:{opt_idx}"
                )
            )
        builder.row(
            InlineKeyboardButton(
                text=USER["quiz_confirm_selection"],
                callback_data=f"qmc:{lesson_id}:{q_idx}"
            )
        )
    else:
        # Single select
        for opt_idx, opt in enumerate(options):
            label = option_labels[opt_idx] if opt_idx < len(option_labels) else f"{opt_idx + 1}."
            builder.row(
                InlineKeyboardButton(
                    text=f"{label} {opt}",
                    callback_data=f"qa:{lesson_id}:{q_idx}:{opt_idx}"
                )
            )

    await message.answer(q_text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("qm:"))
async def quiz_multi_toggle(callback: CallbackQuery, state: FSMContext):
    """Toggle option in multi-select quiz question"""
    parts = callback.data.split(":")
    lesson_id = int(parts[1])
    q_idx = int(parts[2])
    opt_idx = int(parts[3])
    await callback.answer()

    data = await state.get_data()
    if not data or data.get("quiz_lesson_id") != lesson_id:
        await callback.message.answer(USER["quiz_invalid"])
        return

    questions = data.get("quiz_questions", [])
    if q_idx >= len(questions):
        return

    # Get or init multi-select state
    multi_selected = data.get("quiz_multi_selected", [])
    if opt_idx in multi_selected:
        multi_selected.remove(opt_idx)
    else:
        multi_selected.append(opt_idx)
    await state.update_data(quiz_multi_selected=multi_selected)

    # Rebuild keyboard
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    question = questions[q_idx]
    options = question.get("options", [])
    option_labels = ["🅰️", "🅱️", "🅲", "🅳", "🅴", "🅵"]

    builder = InlineKeyboardBuilder()
    for i, opt in enumerate(options):
        label = option_labels[i] if i < len(option_labels) else f"{i + 1}."
        icon = "✅" if i in multi_selected else "⬜️"
        builder.row(
            InlineKeyboardButton(
                text=f"{icon} {label} {opt}",
                callback_data=f"qm:{lesson_id}:{q_idx}:{i}"
            )
        )
    builder.row(
        InlineKeyboardButton(
            text=USER["quiz_confirm_selection"],
            callback_data=f"qmc:{lesson_id}:{q_idx}"
        )
    )

    try:
        await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
    except Exception:
        pass


@router.callback_query(F.data.startswith("qmc:"))
async def quiz_multi_confirm(callback: CallbackQuery, state: FSMContext):
    """Confirm multi-select quiz answer"""
    parts = callback.data.split(":")
    lesson_id = int(parts[1])
    q_idx = int(parts[2])

    data = await state.get_data()
    if not data or data.get("quiz_lesson_id") != lesson_id:
        await callback.message.answer(USER["quiz_invalid"])
        return

    multi_selected = sorted(data.get("quiz_multi_selected", []))
    if not multi_selected:
        await callback.answer(USER["quiz_select_at_least_one"])
        return

    await callback.answer()

    questions = data.get("quiz_questions", [])
    answers = data.get("quiz_answers", [])

    if q_idx >= len(questions):
        return

    question = questions[q_idx]
    correct = question.get("correct", [])
    if not isinstance(correct, list):
        correct = [correct]
    correct = sorted(correct)
    is_correct = (multi_selected == correct)

    # Store answer
    answers.append({
        "question_idx": q_idx,
        "selected": multi_selected,
        "correct": correct,
        "is_correct": is_correct,
        "multi_select": True,
    })
    await state.update_data(quiz_answers=answers, quiz_current=q_idx + 1, quiz_multi_selected=[])

    # Show feedback
    opts = question.get("options", [])
    if is_correct:
        await callback.message.answer(USER["quiz_multi_correct"])
    else:
        correct_labels = [opts[c] for c in correct if c < len(opts)]
        await callback.message.answer(
            USER["quiz_multi_wrong"].format(answers="، ".join(correct_labels))
        )

    next_idx = q_idx + 1
    if next_idx < len(questions):
        await _send_quiz_question(callback.message, questions, next_idx, lesson_id)
    else:
        await _finish_quiz(callback.message, state, answers, data)


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
        await callback.message.answer(USER["quiz_invalid"])
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
        await callback.message.answer(USER["quiz_correct"].format(answer=option_text))
    else:
        correct_text = question.get("options", [])[correct] if correct < len(question.get("options", [])) else "?"
        await callback.message.answer(USER["quiz_wrong"].format(answer=correct_text))

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
            text = USER["quiz_passed"].format(
                title=quiz_title,
                correct=correct_count,
                total=total,
                score=score,
                passing_score=passing_score,
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
                    text=USER["quiz_retry"],
                    callback_data=f"qr:{lesson_id}"
                )
            )

            text = USER["quiz_failed"].format(
                title=quiz_title,
                correct=correct_count,
                total=total,
                score=score,
                passing_score=passing_score,
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
    await callback.answer(USER["quiz_retry_start"])

    async with async_session_maker() as session:
        user_service = UserService(session)
        lesson_service = LessonService(session)

        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        if not user:
            return

        lesson = await lesson_service.get_lesson_by_id(lesson_id)
        if not lesson or not lesson.quiz_data:
            await callback.message.answer(USER["quiz_not_found"])
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
        await message.answer(USER["course_completed"])

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
                USER["lesson_completed"].format(
                    lesson_number=lesson.order if lesson else "?",
                    progress=progress["progress_percent"],
                ) + USER["lesson_completed_auto"]
            )
        else:
            # Instant - tell user to click continue
            await message.answer(
                USER["lesson_completed"].format(
                    lesson_number=lesson.order if lesson else "?",
                    progress=progress["progress_percent"],
                ) + USER["lesson_completed_manual"]
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

@router.message(F.text == USER_BUTTONS["my_progress"])
@log_errors
async def show_progress(message: Message):
    """Show user's progress across all courses"""
    async with async_session_maker() as session:
        user_service = UserService(session)
        lesson_service = LessonService(session)

        user = await user_service.get_user_by_telegram_id(message.from_user.id)
        if not user:
            await message.answer(USER["please_register"])
            return

        courses = await lesson_service.get_all_courses(active_only=True)
        completed_courses = user.completed_courses or {}

        if not courses:
            # Fallback to overall progress
            progress = await lesson_service.get_user_progress(user.id)
            filled = int(progress["progress_percent"] / 10)
            bar = "🟢" * filled + "⚪️" * (10 - filled)
            text = (
                USER["progress_header"]
                + f"{bar}\n"
                + USER["progress_percent"].format(percent=progress['progress_percent']) + "\n\n"
                + USER["progress_completed"].format(completed=progress['completed']) + "\n"
                + USER["progress_total"].format(total=progress['total']) + "\n"
                + USER["progress_remaining"].format(remaining=progress['remaining']) + "\n"
            )
            await message.answer(text)
            return

        text = USER["progress_header"]

        total_all = 0
        completed_all = 0

        for course in courses:
            progress = await lesson_service.get_user_progress(user.id, course_id=course.id)
            is_done = completed_courses.get(str(course.id), False)

            filled = int(progress["progress_percent"] / 10)
            bar = "🟢" * filled + "⚪️" * (10 - filled)

            status = USER["progress_course_status"] if is_done else f"{progress['progress_percent']}%"
            text += (
                f"📚 <b>{course.title}</b> — {status}\n"
                f"{bar}\n"
                f"✅ {progress['completed']}/{progress['total']} درس\n\n"
            )

            total_all += progress["total"]
            completed_all += progress["completed"]

        overall_pct = round(completed_all / total_all * 100) if total_all > 0 else 0
        text += USER["progress_summary"].format(completed=completed_all, total=total_all, percent=overall_pct)

        if user.is_completed:
            text += "\n\n" + USER["progress_all_done"]

        await message.answer(text)


# ===========================
# ABOUT & SUPPORT
# ===========================

@router.message(F.text == USER_BUTTONS["about_course"])
@log_errors
async def about_course(message: Message):
    """Show course information"""
    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        courses = await lesson_service.get_all_courses(active_only=True)

        if not courses:
            total = await lesson_service.get_total_lessons_count()
            text = USER["about_single"].format(total=total)
        else:
            text = USER["about_multi_header"]
            for course in courses:
                lesson_count = await lesson_service.get_course_lesson_count(course.id)
                text += f"📖 <b>{course.title}</b>\n"
                if course.description:
                    text += f"📝 {course.description}\n"
                text += USER["about_course_lessons"].format(count=lesson_count) + "\n\n"
            text += USER["about_footer"]

        await message.answer(text)


@router.message(F.text == USER_BUTTONS["support"])
@log_errors
async def support(message: Message):
    """Show support info"""
    await message.answer(USER["support_text"])


@router.message(Command("progress"))
@log_errors
async def cmd_progress(message: Message):
    """Handle /progress command"""
    await show_progress(message)


@router.message(Command("help"))
@log_errors
async def cmd_help(message: Message):
    """Handle /help command"""
    text = USER["help_text"]
    await message.answer(text)


# ===========================
# RESET PROGRESS
# ===========================

@router.message(Command("reset"))
@log_errors
async def cmd_reset(message: Message):
    """Handle /reset command - reset user progress"""
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    async with async_session_maker() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(message.from_user.id)
        if not user:
            await message.answer(USER["please_register"])
            return

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=GENERAL["confirm_yes"], callback_data="user:reset:confirm"),
        InlineKeyboardButton(text=GENERAL["confirm_no"], callback_data="user:reset:cancel")
    )
    await message.answer(USER["reset_confirm"], reply_markup=builder.as_markup())


@router.callback_query(F.data == "user:reset:confirm")
async def confirm_reset(callback: CallbackQuery):
    """Confirm user progress reset"""
    await callback.answer()
    async with async_session_maker() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        if not user:
            return

        if await user_service.reset_user_progress(user.id):
            await callback.message.edit_text(USER["reset_done"])
            await callback.message.answer(
                USER["reset_done"],
                reply_markup=get_main_menu_keyboard()
            )
        else:
            await callback.message.edit_text(USER["reset_error"])


@router.callback_query(F.data == "user:reset:cancel")
async def cancel_reset(callback: CallbackQuery):
    """Cancel user progress reset"""
    await callback.answer()
    await callback.message.edit_text(USER["reset_cancelled"])
