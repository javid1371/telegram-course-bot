"""
Admin handlers - Admin panel for managing the bot
Lesson CRUD, User management, Broadcast, Analytics, Webhook settings
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

from database import async_session_maker
from database.models import ContentType, FieldType, Admin, RegistrationField, Course
from sqlalchemy import select
from services.user_service import UserService
from services.lesson_service import LessonService
from services.broadcast_service import BroadcastService
from services.analytics_service import AnalyticsService
from services.export_service import ExportService
from services.webhook_service import WebhookService
from utils.keyboards import (
    get_admin_main_menu, get_lesson_management_keyboard,
    get_lesson_list_keyboard, get_lesson_actions_keyboard,
    get_user_management_keyboard, get_user_actions_keyboard,
    get_broadcast_keyboard, get_stats_keyboard,
    get_registration_fields_keyboard, get_field_type_keyboard,
    get_field_actions_keyboard,
    get_webhook_keyboard, get_cancel_keyboard,
    get_back_keyboard, get_pagination_keyboard,
    get_confirm_keyboard,
)
from utils.decorators import admin_only, log_errors
from utils.helpers import format_number, format_duration, truncate_text
import config
from messages import ADMIN, ADMIN_BUTTONS, USER_BUTTONS, GENERAL, DELAY, CONTENT_TYPES

logger = logging.getLogger(__name__)
router = Router()


def _format_delay(minutes: int) -> str:
    """Format delay minutes into human-readable Persian text"""
    if minutes <= 0:
        return DELAY["instant"]
    if minutes < 60:
        return DELAY["minutes"].format(minutes=minutes)
    hours = minutes // 60
    remaining_min = minutes % 60
    if hours < 24:
        if remaining_min > 0:
            return DELAY["hours_minutes"].format(hours=hours, minutes=remaining_min)
        return DELAY["hours"].format(hours=hours)
    days = hours // 24
    remaining_hours = hours % 24
    parts = [DELAY["days"].format(days=days)]
    if remaining_hours > 0:
        parts.append(DELAY["hours"].format(hours=remaining_hours))
    if remaining_min > 0:
        parts.append(DELAY["minutes"].format(minutes=remaining_min))
    return " و ".join(parts)


# ===========================
# FSM STATES
# ===========================

class AdminStates(StatesGroup):
    """Admin panel FSM states"""
    # Lesson states
    waiting_lesson_title = State()
    waiting_lesson_content_type = State()
    waiting_lesson_content = State()
    waiting_lesson_description = State()
    waiting_lesson_delay = State()
    waiting_lesson_cta_text = State()
    waiting_lesson_cta_url = State()
    waiting_lesson_edit_field = State()
    waiting_lesson_edit_value = State()

    # Broadcast states
    waiting_broadcast_message = State()
    waiting_private_message = State()

    # User search
    waiting_user_search = State()

    # Registration field states
    waiting_field_name = State()
    waiting_field_label = State()
    waiting_field_type = State()
    waiting_field_required = State()
    waiting_field_options = State()

    # Webhook states
    waiting_webhook_name = State()
    waiting_webhook_url = State()
    waiting_webhook_method = State()

    # Tag management
    waiting_tag_input = State()

    # Quiz management
    waiting_quiz_passing_score = State()
    waiting_quiz_question_text = State()
    waiting_quiz_options = State()
    waiting_quiz_question_type = State()  # single or multi-select

    # Form builder
    waiting_form_field_label = State()
    waiting_form_field_type = State()
    waiting_form_field_options = State()

    # Field editing
    waiting_field_edit_label = State()

    # Lesson edit content (multi-content)
    waiting_lesson_edit_content = State()

    # Course management
    waiting_course_title = State()
    waiting_course_description = State()
    waiting_course_edit_title = State()
    waiting_course_edit_description = State()


# ===========================
# ADMIN ENTRY
# ===========================

@router.message(Command("admin"))
@admin_only
@log_errors
async def cmd_admin(message: Message, state: FSMContext):
    """Open admin panel"""
    await state.clear()

    # Ensure admin record exists in DB
    async with async_session_maker() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(Admin).where(Admin.telegram_user_id == message.from_user.id)
        )
        admin = result.scalar_one_or_none()
        if not admin:
            admin = Admin(
                telegram_user_id=message.from_user.id,
                username=message.from_user.username,
                full_name=message.from_user.full_name,
            )
            session.add(admin)
            await session.commit()

    await message.answer(
        ADMIN["panel_header"],
        reply_markup=get_admin_main_menu()
    )


# ===========================
# DASHBOARD
# ===========================

@router.message(F.text == ADMIN_BUTTONS["dashboard"])
@admin_only
@log_errors
async def show_dashboard(message: Message):
    """Show admin dashboard with enhanced analytics"""
    async with async_session_maker() as session:
        analytics = AnalyticsService(session)
        stats = await analytics.get_dashboard_stats()

        text = (
            ADMIN["dashboard_header"]
            + ADMIN["dashboard_total_users"].format(count=format_number(stats['total_users'])) + "\n"
            + ADMIN["dashboard_active_users"].format(count=format_number(stats['active_users'])) + "\n"
            + ADMIN["dashboard_completed"].format(count=format_number(stats['completed_all'])) + "\n"
            + ADMIN["dashboard_completion_rate"].format(rate=stats['completion_rate']) + "\n\n"
            + ADMIN["dashboard_courses"].format(count=format_number(stats['total_courses'])) + "\n"
            + ADMIN["dashboard_lessons"].format(count=format_number(stats['total_lessons'])) + "\n\n"
            + ADMIN["dashboard_activity_header"] + "\n"
            + "  " + ADMIN["dashboard_active_24h"].format(count=format_number(stats['active_24h'])) + "\n"
            + "  " + ADMIN["dashboard_active_7d"].format(count=format_number(stats['active_7d'])) + "\n\n"
            + ADMIN["dashboard_today_header"] + "\n"
            + "  " + ADMIN["dashboard_today_new"].format(count=format_number(stats['today_new_users'])) + "\n"
            + "  " + ADMIN["dashboard_today_lessons"].format(count=format_number(stats['today_completions'])) + "\n\n"
            + ADMIN["dashboard_week_header"] + "\n"
            + "  " + ADMIN["dashboard_week_new"].format(count=format_number(stats['week_new_users']))
        )

        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text=ADMIN_BUTTONS["funnel_analysis"], callback_data="admin:analytics:funnel"),
            InlineKeyboardButton(text=ADMIN_BUTTONS["courses_analytics"], callback_data="admin:analytics:courses")
        )

        await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "admin:analytics:funnel")
@admin_only
@log_errors
async def show_funnel_analysis(callback: CallbackQuery):
    """Show lesson-by-lesson funnel analysis"""
    await callback.answer()
    async with async_session_maker() as session:
        analytics = AnalyticsService(session)
        funnel = await analytics.get_funnel_analysis()

        if not funnel:
            await callback.message.answer(ADMIN["funnel_no_data"])
            return

        text = ADMIN["funnel_header"]
        for item in funnel[:20]:
            drop_indicator = ""
            if item["drop_off_rate"] > 30:
                drop_indicator = " ⚠️"
            elif item["drop_off_rate"] > 15:
                drop_indicator = " ⚡"

            text += (
                f"📖 {item['order']}. {item['title'][:20]}\n"
                f"   شروع: {item['started']} | تکمیل: {item['completed']} "
                f"({item['completion_rate']}%)"
            )
            if item["drop_off_rate"] > 0:
                text += f" | ریزش: {item['drop_off_rate']}%{drop_indicator}"
            text += "\n"

        text += "\n" + ADMIN["funnel_legend"]

        try:
            await callback.message.edit_text(text)
        except TelegramBadRequest:
            await callback.message.answer(text)


@router.callback_query(F.data == "admin:analytics:courses")
@admin_only
@log_errors
async def show_courses_analytics(callback: CallbackQuery):
    """Show per-course analytics"""
    await callback.answer()
    async with async_session_maker() as session:
        analytics = AnalyticsService(session)
        lesson_service = LessonService(session)
        courses = await lesson_service.get_all_courses(active_only=False)

        text = ADMIN["courses_analytics_header"]
        for course in courses:
            stats = await analytics.get_course_analytics(course.id)
            status = "✅" if course.is_active else "❌"
            text += (
                f"{status} <b>{course.title}</b>\n"
                f"   📖 {stats['total_lessons']} درس | 👥 {stats['enrolled']} ثبت‌نام\n"
                f"   🎓 {stats['completed_users']} تکمیل ({stats['completion_rate']}%)\n"
            )
            if stats['quiz_attempts'] > 0:
                text += (
                    f"   📝 آزمون: {stats['quiz_attempts']} تلاش | "
                    f"قبولی: {stats['quiz_pass_rate']}% | "
                    f"میانگین: {stats['avg_quiz_score']}\n"
                )
            text += "\n"

        try:
            await callback.message.edit_text(text)
        except TelegramBadRequest:
            await callback.message.answer(text)


# ===========================
# COURSE & LESSON MANAGEMENT
# ===========================

@router.message(F.text == ADMIN_BUTTONS["lessons"])
@admin_only
@log_errors
async def lesson_management_menu(message: Message):
    """Show course list as entry to lesson management"""
    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        courses = await lesson_service.get_all_courses(active_only=False)

        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()

        for course in courses:
            status = "✅" if course.is_active else "❌"
            lesson_count = await lesson_service.get_course_lesson_count(course.id)
            builder.row(
                InlineKeyboardButton(
                    text=f"{status} {course.title} ({lesson_count} درس)",
                    callback_data=f"admin:course:view:{course.id}"
                )
            )

        builder.row(
            InlineKeyboardButton(text=ADMIN_BUTTONS["add_course"], callback_data="admin:course:add")
        )
        builder.row(
            InlineKeyboardButton(text=GENERAL["back"], callback_data="admin:back")
        )

        await message.answer(
            ADMIN["courses_header"],
            reply_markup=builder.as_markup()
        )


@router.callback_query(F.data == "admin:courses")
@admin_only
@log_errors
async def courses_menu_callback(callback: CallbackQuery):
    """Show courses list via callback"""
    await callback.answer()
    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        courses = await lesson_service.get_all_courses(active_only=False)

        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()

        for course in courses:
            status = "✅" if course.is_active else "❌"
            lesson_count = await lesson_service.get_course_lesson_count(course.id)
            builder.row(
                InlineKeyboardButton(
                    text=f"{status} {course.title} ({lesson_count} درس)",
                    callback_data=f"admin:course:view:{course.id}"
                )
            )

        builder.row(
            InlineKeyboardButton(text=ADMIN_BUTTONS["add_course"], callback_data="admin:course:add")
        )
        builder.row(
            InlineKeyboardButton(text=GENERAL["back"], callback_data="admin:back")
        )

        try:
            await callback.message.edit_text(
                ADMIN["courses_header"],
                reply_markup=builder.as_markup()
            )
        except TelegramBadRequest:
            await callback.message.answer(
                ADMIN["courses_header"],
                reply_markup=builder.as_markup()
            )


@router.callback_query(F.data == "admin:course:add")
@admin_only
@log_errors
async def add_course_start(callback: CallbackQuery, state: FSMContext):
    """Start creating a new course"""
    await callback.answer()
    await callback.message.answer(
        ADMIN["course_create_title"],
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_course_title)


@router.message(AdminStates.waiting_course_title)
async def process_course_title(message: Message, state: FSMContext):
    """Process course title"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer(GENERAL["cancelled"], reply_markup=get_admin_main_menu())
        return

    await state.update_data(course_title=message.text)
    await message.answer(
        ADMIN["course_create_desc"],
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_course_description)


@router.message(AdminStates.waiting_course_description)
async def process_course_description(message: Message, state: FSMContext):
    """Process course description and save"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer(GENERAL["cancelled"], reply_markup=get_admin_main_menu())
        return

    data = await state.get_data()
    await state.clear()

    description = None if message.text == "/skip" else message.text

    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        course = await lesson_service.create_course(
            title=data["course_title"],
            description=description,
        )

        await message.answer(
            ADMIN["course_created"].format(title=course.title),
            reply_markup=get_admin_main_menu()
        )


@router.callback_query(F.data.startswith("admin:course:view:"))
@admin_only
@log_errors
async def view_course(callback: CallbackQuery):
    """View course details with lesson list"""
    course_id = int(callback.data.split(":")[3])
    await callback.answer()

    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        course = await lesson_service.get_course_by_id(course_id)
        if not course:
            await callback.message.answer(ADMIN["course_not_found"])
            return

        lessons = await lesson_service.get_all_lessons(active_only=False, course_id=course_id)
        stats = await lesson_service.get_course_stats(course_id)

        status = GENERAL["status_active"] if course.is_active else GENERAL["status_inactive"]
        text = (
            ADMIN["course_view_header"].format(title=course.title) + "\n"
            + ADMIN["course_view_desc"].format(description=course.description or '---') + "\n"
            + ADMIN["course_view_status"].format(status=status) + "\n\n"
            + ADMIN["course_view_stats_header"] + "\n"
            + "  " + ADMIN["course_view_lesson_count"].format(count=stats['total_lessons']) + "\n"
            + "  " + ADMIN["course_view_enrolled"].format(count=stats['enrolled']) + "\n"
            + "  " + ADMIN["course_view_completed"].format(count=stats['completed']) + "\n"
            + "  " + ADMIN["course_view_rate"].format(rate=stats['completion_rate']) + "\n\n"
        )

        if lessons:
            text += ADMIN["course_view_lessons_header"] + "\n"
            for l in lessons[:15]:
                ls = "✅" if l.is_active else "❌"
                text += f"  {ls} {l.order}. {l.title}\n"
            if len(lessons) > 15:
                text += "  " + ADMIN["course_view_more_lessons"].format(count=len(lessons) - 15) + "\n"

        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text=ADMIN_BUTTONS["add_lesson"], callback_data=f"admin:lesson:add:{course_id}"),
            InlineKeyboardButton(text=ADMIN_BUTTONS["lesson_list"], callback_data=f"admin:lesson:list:{course_id}")
        )
        builder.row(
            InlineKeyboardButton(text=ADMIN_BUTTONS["edit_title"], callback_data=f"admin:course:edit_title:{course_id}"),
            InlineKeyboardButton(text=ADMIN_BUTTONS["toggle_course"], callback_data=f"admin:course:toggle:{course_id}")
        )
        builder.row(
            InlineKeyboardButton(text=ADMIN_BUTTONS["delete_course"], callback_data=f"admin:course:delete:{course_id}")
        )
        builder.row(
            InlineKeyboardButton(text=GENERAL["back"], callback_data="admin:courses")
        )

        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup())
        except TelegramBadRequest:
            await callback.message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("admin:course:toggle:"))
@admin_only
@log_errors
async def toggle_course(callback: CallbackQuery):
    """Toggle course active status"""
    course_id = int(callback.data.split(":")[3])
    await callback.answer()

    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        course = await lesson_service.toggle_course(course_id)
        if course:
            status = ADMIN["course_toggled_active"] if course.is_active else ADMIN["course_toggled_inactive"]
            await callback.message.answer(
                ADMIN["course_toggled"].format(title=course.title, status=status),
                reply_markup=get_admin_main_menu()
            )


@router.callback_query(F.data.startswith("admin:course:delete:"))
@admin_only
@log_errors
async def delete_course(callback: CallbackQuery):
    """Delete a course"""
    course_id = int(callback.data.split(":")[3])
    await callback.answer()

    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        course = await lesson_service.get_course_by_id(course_id)
        if not course:
            return

        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text=ADMIN_BUTTONS["confirm_delete"], callback_data=f"admin:course:dodel:{course_id}"),
            InlineKeyboardButton(text=GENERAL["confirm_no"], callback_data=f"admin:course:view:{course_id}")
        )

        await callback.message.edit_text(
            ADMIN["course_delete_confirm"].format(title=course.title),
            reply_markup=builder.as_markup()
        )


@router.callback_query(F.data.startswith("admin:course:dodel:"))
@admin_only
@log_errors
async def delete_course_execute(callback: CallbackQuery):
    """Execute course deletion"""
    course_id = int(callback.data.split(":")[3])
    await callback.answer()

    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        await lesson_service.delete_course(course_id)
        await callback.message.answer(ADMIN["course_deleted"], reply_markup=get_admin_main_menu())


@router.callback_query(F.data.startswith("admin:course:edit_title:"))
@admin_only
@log_errors
async def edit_course_title_start(callback: CallbackQuery, state: FSMContext):
    """Start editing course title"""
    course_id = int(callback.data.split(":")[3])
    await callback.answer()
    await state.update_data(editing_course_id=course_id)
    await callback.message.answer(
        ADMIN["course_edit_title"],
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_course_edit_title)


@router.message(AdminStates.waiting_course_edit_title)
async def process_course_edit_title(message: Message, state: FSMContext):
    """Process course title edit"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer(GENERAL["cancelled"], reply_markup=get_admin_main_menu())
        return

    data = await state.get_data()
    await state.clear()

    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        course = await lesson_service.update_course(data["editing_course_id"], title=message.text)
        if course:
            await message.answer(ADMIN["course_title_updated"].format(title=course.title), reply_markup=get_admin_main_menu())


# ===========================
# LESSON MANAGEMENT (course-aware)
# ===========================

@router.callback_query(F.data == "admin:lessons")
@admin_only
@log_errors
async def lesson_menu_callback(callback: CallbackQuery):
    """Redirect to courses menu"""
    await callback.answer()
    # Redirect to courses list
    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        courses = await lesson_service.get_all_courses(active_only=False)

        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        for course in courses:
            status = "✅" if course.is_active else "❌"
            lesson_count = await lesson_service.get_course_lesson_count(course.id)
            builder.row(
                InlineKeyboardButton(
                    text=f"{status} {course.title} ({lesson_count} درس)",
                    callback_data=f"admin:course:view:{course.id}"
                )
            )
        builder.row(
            InlineKeyboardButton(text=ADMIN_BUTTONS["add_course"], callback_data="admin:course:add")
        )
        builder.row(
            InlineKeyboardButton(text=GENERAL["back"], callback_data="admin:back")
        )

        try:
            await callback.message.edit_text(
                ADMIN["courses_header"],
                reply_markup=builder.as_markup()
            )
        except TelegramBadRequest:
            await callback.message.answer(
                ADMIN["courses_header"],
                reply_markup=builder.as_markup()
            )


@router.callback_query(F.data.startswith("admin:lesson:add:"))
@admin_only
@log_errors
async def add_lesson_start(callback: CallbackQuery, state: FSMContext):
    """Start adding a new lesson to a specific course"""
    course_id = int(callback.data.split(":")[3])
    await callback.answer()
    await state.update_data(lesson_course_id=course_id)
    await callback.message.answer(
        ADMIN["lesson_add_title"],
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_lesson_title)


@router.message(AdminStates.waiting_lesson_title)
async def process_lesson_title(message: Message, state: FSMContext):
    """Process lesson title"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer(GENERAL["cancelled"], reply_markup=get_admin_main_menu())
        return

    await state.update_data(lesson_title=message.text)

    # Ask for content type
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["content_text"], callback_data="lesson_type:text"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["content_video"], callback_data="lesson_type:video"),
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["content_audio"], callback_data="lesson_type:audio"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["content_voice"], callback_data="lesson_type:voice"),
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["content_document"], callback_data="lesson_type:document"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["content_photo"], callback_data="lesson_type:photo"),
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["content_form"], callback_data="lesson_type:form"),
    )

    await message.answer(
        ADMIN["lesson_select_type"],
        reply_markup=builder.as_markup()
    )
    await state.set_state(AdminStates.waiting_lesson_content_type)


@router.callback_query(F.data.startswith("lesson_type:"), AdminStates.waiting_lesson_content_type)
async def process_lesson_type(callback: CallbackQuery, state: FSMContext):
    """Process lesson content type selection"""
    content_type = callback.data.split(":")[1]
    await callback.answer()
    await state.update_data(lesson_content_type=content_type)

    if content_type == "form":
        # Form type: go to form builder instead of content upload
        await state.update_data(form_fields=[])
        await callback.message.answer(
            ADMIN["form_builder_intro"],
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(AdminStates.waiting_form_field_label)
        return

    type_prompts = ADMIN["lesson_type_prompts"]

    await callback.message.answer(
        type_prompts.get(content_type, type_prompts["default"]),
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_lesson_content)


@router.message(AdminStates.waiting_lesson_content)
async def process_lesson_content(message: Message, state: FSMContext):
    """Process lesson content"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer(GENERAL["cancelled"], reply_markup=get_admin_main_menu())
        return

    data = await state.get_data()
    content_type = data["lesson_content_type"]

    file_id = None
    text_content = None

    if content_type == "text":
        text_content = message.text
    elif content_type == "video" and message.video:
        file_id = message.video.file_id
    elif content_type == "audio":
        if message.audio:
            file_id = message.audio.file_id
        elif message.voice:
            file_id = message.voice.file_id
            content_type = "voice"
        else:
            await message.answer(ADMIN["lesson_audio_error"])
            return
    elif content_type == "voice":
        if message.voice:
            file_id = message.voice.file_id
        elif message.audio:
            file_id = message.audio.file_id
            content_type = "audio"
        else:
            await message.answer(ADMIN["lesson_voice_error"])
            return
    elif content_type == "document" and message.document:
        file_id = message.document.file_id
    elif content_type == "photo" and message.photo:
        file_id = message.photo[-1].file_id  # Largest photo
    else:
        await message.answer(ADMIN["lesson_type_error"])
        return

    # Build content block
    block = {"type": content_type}
    if file_id:
        block["file_id"] = file_id
    if text_content:
        block["text"] = text_content

    # Append to contents list
    data = await state.get_data()
    lesson_contents = data.get("lesson_contents", [])
    lesson_contents.append(block)

    # Save first block info for backward compat
    if len(lesson_contents) == 1:
        await state.update_data(
            lesson_file_id=file_id,
            lesson_text_content=text_content,
            lesson_contents=lesson_contents,
        )
    else:
        await state.update_data(lesson_contents=lesson_contents)

    # Show summary and ask for more
    type_labels = {
        "text": "📝 متن", "video": "🎥 ویدیو", "audio": "🎵 صوت",
        "voice": "🎤 ویس", "document": "📄 فایل", "photo": "🖼 تصویر",
    }
    summary = ""
    for i, b in enumerate(lesson_contents, 1):
        summary += f"  {i}. {type_labels.get(b['type'], b['type'])} ✅\n"

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["add_more_content"], callback_data="lesson_content:more")
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["content_done"], callback_data="lesson_content:done")
    )

    await message.answer(
        ADMIN["lesson_content_added"].format(summary=summary),
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "lesson_content:more")
@admin_only
async def add_more_lesson_content(callback: CallbackQuery, state: FSMContext):
    """Add more content blocks to the lesson"""
    await callback.answer()

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["content_text"], callback_data="lesson_type:text"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["content_video"], callback_data="lesson_type:video"),
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["content_audio"], callback_data="lesson_type:audio"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["content_voice"], callback_data="lesson_type:voice"),
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["content_document"], callback_data="lesson_type:document"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["content_photo"], callback_data="lesson_type:photo"),
    )

    await callback.message.answer(
        ADMIN["lesson_select_next_type"],
        reply_markup=builder.as_markup()
    )
    await state.set_state(AdminStates.waiting_lesson_content_type)


@router.callback_query(F.data == "lesson_content:done")
@admin_only
async def lesson_content_done(callback: CallbackQuery, state: FSMContext):
    """Done adding content, proceed to description"""
    await callback.answer()

    await callback.message.answer(
        ADMIN["lesson_enter_description"],
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_lesson_description)


@router.message(AdminStates.waiting_lesson_description)
async def process_lesson_description(message: Message, state: FSMContext):
    """Process lesson description"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer(GENERAL["cancelled"], reply_markup=get_admin_main_menu())
        return

    description = None if message.text == "/skip" else message.text
    await state.update_data(lesson_description=description)

    await message.answer(
        ADMIN["lesson_enter_delay"],
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_lesson_delay)


@router.message(AdminStates.waiting_lesson_delay)
async def process_lesson_delay(message: Message, state: FSMContext):
    """Process lesson delay in minutes"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer(GENERAL["cancelled"], reply_markup=get_admin_main_menu())
        return

    try:
        delay_minutes = int(message.text)
        if delay_minutes < 0:
            raise ValueError
    except (ValueError, TypeError):
        await message.answer(ADMIN["lesson_delay_error"])
        return

    await state.update_data(lesson_delay_minutes=delay_minutes)

    # Save lesson
    data = await state.get_data()
    await state.clear()

    content_type_map = {
        "text": ContentType.TEXT,
        "video": ContentType.VIDEO,
        "audio": ContentType.AUDIO,
        "voice": ContentType.VOICE,
        "document": ContentType.DOCUMENT,
        "photo": ContentType.PHOTO,
        "form": ContentType.FORM,
    }

    # Determine primary content type from first content block
    contents = data.get("lesson_contents", [])
    if contents:
        primary_type = contents[0].get("type", "text")
        primary_file_id = contents[0].get("file_id")
        primary_text = contents[0].get("text")
    else:
        primary_type = data.get("lesson_content_type", "text")
        primary_file_id = data.get("lesson_file_id")
        primary_text = data.get("lesson_text_content")

    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        lesson = await lesson_service.create_lesson(
            title=data["lesson_title"],
            content_type=content_type_map[primary_type],
            course_id=data.get("lesson_course_id"),
            description=data.get("lesson_description"),
            file_id=primary_file_id,
            text_content=primary_text,
            delay_hours=delay_minutes,
        )

        # Save multi-content blocks
        if contents and len(contents) > 0:
            lesson.contents = contents
            await session.commit()
            await session.refresh(lesson)

        # Save form data if FORM type
        if data.get("lesson_content_type") == "form" and data.get("form_fields"):
            lesson.form_data = {"fields": data["form_fields"]}
            await session.commit()
            await session.refresh(lesson)

        delay_text = _format_delay(delay_minutes)
        content_count = len(contents) if contents else 1
        content_info = f"📦 تعداد محتوا: {content_count}" if content_count > 1 else f"📦 نوع: {primary_type}"

        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text=ADMIN["lesson_add_quiz_btn"], callback_data=f"admin:quiz:new:{lesson.id}")
        )
        builder.row(
            InlineKeyboardButton(text=ADMIN["lesson_back_to_panel"], callback_data="admin:back")
        )

        await message.answer(
            ADMIN["lesson_created"].format(
                title=lesson.title, order=lesson.order,
                content_info=content_info, delay=delay_text
            ) + "\n\n" + ADMIN["lesson_add_quiz_prompt"],
            reply_markup=builder.as_markup()
        )


@router.callback_query(F.data.startswith("admin:lesson:list:"))
@admin_only
@log_errors
async def list_lessons(callback: CallbackQuery):
    """List lessons for a specific course"""
    course_id = int(callback.data.split(":")[3])
    await callback.answer()

    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        lessons = await lesson_service.get_all_lessons(active_only=False, course_id=course_id)
        course = await lesson_service.get_course_by_id(course_id)
        course_title = course.title if course else ""

        if not lessons:
            from aiogram.types import InlineKeyboardButton
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text=ADMIN_BUTTONS["add_lesson"], callback_data=f"admin:lesson:add:{course_id}")
            )
            builder.row(
                InlineKeyboardButton(text=ADMIN_BUTTONS["back_to_course"], callback_data=f"admin:course:view:{course_id}")
            )
            await callback.message.edit_text(
                ADMIN["lesson_list_empty"].format(title=course_title),
                reply_markup=builder.as_markup()
            )
            return

        await callback.message.edit_text(
            ADMIN["lesson_list_header"].format(title=course_title, count=len(lessons)),
            reply_markup=get_lesson_list_keyboard(lessons, course_id=course_id)
        )


@router.callback_query(F.data.startswith("admin:lesson:view:"))
@admin_only
@log_errors
async def view_lesson(callback: CallbackQuery, lesson_id: int = None):
    """View lesson details"""
    if lesson_id is None:
        lesson_id = int(callback.data.split(":")[3])
    await callback.answer()

    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        lesson = await lesson_service.get_lesson_by_id(lesson_id)

        if not lesson:
            await callback.message.edit_text(ADMIN["lesson_not_found"])
            return

        stats = await lesson_service.get_lesson_stats(lesson_id)

        status = GENERAL["status_active"] if lesson.is_active else GENERAL["status_inactive"]
        delay_text = _format_delay(lesson.delay_hours)

        # Content info
        if lesson.contents and len(lesson.contents) > 1:
            parts = [CONTENT_TYPES.get(b.get("type", ""), b.get("type", "")) for b in lesson.contents]
            content_info = f"{len(lesson.contents)} بخش ({', '.join(parts)})"
        else:
            content_info = lesson.content_type.value

        text = (
            ADMIN["lesson_view_header"].format(order=lesson.order, title=lesson.title) + "\n\n"
            + ADMIN["lesson_view_content"].format(content=content_info) + "\n"
            + ADMIN["lesson_view_status"].format(status=status) + "\n"
            + ADMIN["lesson_view_delay"].format(delay=delay_text) + "\n"
            + ADMIN["lesson_view_desc"].format(desc=truncate_text(lesson.description or ADMIN["lesson_view_no_desc"], 200)) + "\n\n"
            + ADMIN["lesson_view_stats"] + "\n"
            + "  " + ADMIN["lesson_view_started"].format(count=stats['started']) + "\n"
            + "  " + ADMIN["lesson_view_completed"].format(count=stats['completed']) + "\n"
            + "  " + ADMIN["lesson_view_rate"].format(rate=stats['completion_rate'])
        )

        if lesson.cta_text:
            text += "\n\n" + ADMIN["lesson_view_cta"].format(text=lesson.cta_text) + f" → {lesson.cta_url or '-'}"

        if lesson.quiz_data and lesson.quiz_data.get("questions"):
            text += "\n\n" + ADMIN["lesson_view_quiz"].format(
                count=len(lesson.quiz_data['questions']),
                score=lesson.quiz_data.get('passing_score', 100)
            )

        try:
            await callback.message.edit_text(
                text, reply_markup=get_lesson_actions_keyboard(lesson_id, course_id=lesson.course_id)
            )
        except TelegramBadRequest:
            pass  # Same content, ignore


@router.callback_query(F.data.startswith("admin:lesson:stats:"))
@admin_only
@log_errors
async def lesson_stats(callback: CallbackQuery):
    """Show lesson stats - redirects to lesson view which includes stats"""
    lesson_id = int(callback.data.split(":")[3])
    await view_lesson(callback, lesson_id=lesson_id)


@router.callback_query(F.data.startswith("admin:lesson:edit:"))
@admin_only
@log_errors
async def edit_lesson(callback: CallbackQuery, state: FSMContext):
    """Show edit options for a lesson"""
    lesson_id = int(callback.data.split(":")[3])
    await callback.answer()

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["edit_title_field"], callback_data=f"admin:lesson:editf:title:{lesson_id}"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["edit_description"], callback_data=f"admin:lesson:editf:description:{lesson_id}"),
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["edit_delay"], callback_data=f"admin:lesson:editf:delay_hours:{lesson_id}"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["edit_content"], callback_data=f"admin:lesson:editf:content:{lesson_id}"),
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["edit_cta_text"], callback_data=f"admin:lesson:editf:cta_text:{lesson_id}"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["edit_cta_url"], callback_data=f"admin:lesson:editf:cta_url:{lesson_id}"),
    )
    builder.row(
        InlineKeyboardButton(text=GENERAL["back"], callback_data=f"admin:lesson:view:{lesson_id}")
    )

    await callback.message.edit_text(
        ADMIN["lesson_edit_header"],
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("admin:lesson:editf:"))
@admin_only
@log_errors
async def edit_lesson_field(callback: CallbackQuery, state: FSMContext):
    """Start editing a specific lesson field"""
    parts = callback.data.split(":")
    field_name = parts[3]
    lesson_id = int(parts[4])
    await callback.answer()

    await state.update_data(edit_lesson_id=lesson_id, edit_field=field_name)

    if field_name == "content":
        # Redirect to multi-content edit flow
        await state.update_data(edit_lesson_id=lesson_id, edit_field="content", lesson_contents=[])

        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text=ADMIN_BUTTONS["content_text"], callback_data="edit_ctype:text"),
            InlineKeyboardButton(text=ADMIN_BUTTONS["content_video"], callback_data="edit_ctype:video"),
        )
        builder.row(
            InlineKeyboardButton(text=ADMIN_BUTTONS["content_audio"], callback_data="edit_ctype:audio"),
            InlineKeyboardButton(text=ADMIN_BUTTONS["content_voice"], callback_data="edit_ctype:voice"),
        )
        builder.row(
            InlineKeyboardButton(text=ADMIN_BUTTONS["content_document"], callback_data="edit_ctype:document"),
            InlineKeyboardButton(text=ADMIN_BUTTONS["content_photo"], callback_data="edit_ctype:photo"),
        )

        await callback.message.edit_text(
            ADMIN["lesson_edit_content_header"],
            reply_markup=builder.as_markup()
        )
        return

    field_prompts = ADMIN["lesson_edit_prompts"]

    await callback.message.edit_text(
        field_prompts.get(field_name, field_prompts["default"]),
    )
    await state.set_state(AdminStates.waiting_lesson_edit_value)


@router.message(AdminStates.waiting_lesson_edit_value)
async def process_lesson_edit_value(message: Message, state: FSMContext):
    """Process the new value for a lesson field"""
    data = await state.get_data()
    lesson_id = data["edit_lesson_id"]
    field_name = data["edit_field"]
    await state.clear()

    update_data = {}

    if field_name == "title":
        update_data["title"] = message.text
    elif field_name == "description":
        update_data["description"] = None if message.text == "/skip" else message.text
    elif field_name == "delay_hours":
        try:
            val = int(message.text)
            if val < 0:
                raise ValueError
            update_data["delay_hours"] = val
        except (ValueError, TypeError):
            await message.answer("⚠️ عدد نامعتبر. ویرایش لغو شد.", reply_markup=get_admin_main_menu())
            return
    elif field_name == "content":
        # Should not reach here - content edit uses multi-content flow
        await message.answer("⚠️ خطا. لطفاً دوباره تلاش کنید.", reply_markup=get_admin_main_menu())
        return
    elif field_name in ("cta_text", "cta_url"):
        update_data[field_name] = None if message.text == "/skip" else message.text

    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        lesson = await lesson_service.update_lesson(lesson_id, **update_data)

        if lesson:
            await message.answer(
                ADMIN["lesson_edited"].format(title=lesson.title),
                reply_markup=get_admin_main_menu()
            )
        else:
            await message.answer(ADMIN["lesson_edit_failed"], reply_markup=get_admin_main_menu())


# ===========================
# EDIT CONTENT MULTI-CONTENT FLOW
# ===========================

@router.callback_query(F.data.startswith("edit_ctype:"))
@admin_only
async def edit_content_select_type(callback: CallbackQuery, state: FSMContext):
    """Select content type for edit multi-content flow"""
    content_type = callback.data.split(":")[1]
    await callback.answer()
    await state.update_data(edit_content_type=content_type)

    type_prompts = ADMIN["lesson_edit_content_prompts"]

    await callback.message.answer(
        type_prompts.get(content_type, type_prompts["default"]),
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_lesson_edit_content)


@router.message(AdminStates.waiting_lesson_edit_content)
async def process_edit_content(message: Message, state: FSMContext):
    """Process content block during edit"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer(GENERAL["cancelled"], reply_markup=get_admin_main_menu())
        return

    data = await state.get_data()
    content_type = data.get("edit_content_type", "text")

    file_id = None
    text_content = None

    if content_type == "text":
        text_content = message.text
    elif content_type == "video" and message.video:
        file_id = message.video.file_id
    elif content_type == "audio":
        if message.audio:
            file_id = message.audio.file_id
        elif message.voice:
            file_id = message.voice.file_id
            content_type = "voice"
        else:
            await message.answer(ADMIN["lesson_edit_content_audio_error"])
            return
    elif content_type == "voice":
        if message.voice:
            file_id = message.voice.file_id
        elif message.audio:
            file_id = message.audio.file_id
            content_type = "audio"
        else:
            await message.answer(ADMIN["lesson_edit_content_voice_error"])
            return
    elif content_type == "document" and message.document:
        file_id = message.document.file_id
    elif content_type == "photo" and message.photo:
        file_id = message.photo[-1].file_id
    else:
        await message.answer(ADMIN["lesson_edit_content_type_error"])
        return

    block = {"type": content_type}
    if file_id:
        block["file_id"] = file_id
    if text_content:
        block["text"] = text_content

    lesson_contents = data.get("lesson_contents", [])
    lesson_contents.append(block)
    await state.update_data(lesson_contents=lesson_contents)

    type_labels = {
        "text": "📝 متن", "video": "🎥 ویدیو", "audio": "🎵 صوت",
        "voice": "🎤 ویس", "document": "📄 فایل", "photo": "🖼 تصویر",
    }
    summary = ""
    for i, b in enumerate(lesson_contents, 1):
        summary += f"  {i}. {type_labels.get(b['type'], b['type'])} ✅\n"

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["add_more_content"], callback_data="edit_content:more")
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["content_save"], callback_data="edit_content:done")
    )

    await message.answer(
        ADMIN["lesson_edit_content_added"].format(summary=summary),
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "edit_content:more")
@admin_only
async def edit_content_add_more(callback: CallbackQuery, state: FSMContext):
    """Add more content blocks in edit mode"""
    await callback.answer()

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["content_text"], callback_data="edit_ctype:text"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["content_video"], callback_data="edit_ctype:video"),
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["content_audio"], callback_data="edit_ctype:audio"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["content_voice"], callback_data="edit_ctype:voice"),
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["content_document"], callback_data="edit_ctype:document"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["content_photo"], callback_data="edit_ctype:photo"),
    )

    await callback.message.answer(
        ADMIN["lesson_select_next_type"],
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "edit_content:done")
@admin_only
async def edit_content_done(callback: CallbackQuery, state: FSMContext):
    """Save edited multi-content to lesson"""
    await callback.answer()

    data = await state.get_data()
    lesson_id = data.get("edit_lesson_id")
    lesson_contents = data.get("lesson_contents", [])
    await state.clear()

    if not lesson_contents:
        await callback.message.answer(ADMIN["lesson_edit_no_content"], reply_markup=get_admin_main_menu())
        return

    # Determine primary type from first block
    first_block = lesson_contents[0]
    content_type_map = {
        "text": ContentType.TEXT, "video": ContentType.VIDEO,
        "audio": ContentType.AUDIO, "voice": ContentType.VOICE,
        "document": ContentType.DOCUMENT, "photo": ContentType.PHOTO,
    }
    primary_type = content_type_map.get(first_block.get("type", "text"), ContentType.TEXT)

    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        lesson = await lesson_service.get_lesson_by_id(lesson_id)
        if not lesson:
            await callback.message.answer(ADMIN["lesson_not_found"], reply_markup=get_admin_main_menu())
            return

        # Update lesson
        lesson.content_type = primary_type
        lesson.file_id = first_block.get("file_id")
        lesson.text_content = first_block.get("text")
        lesson.contents = lesson_contents
        await session.commit()

        await callback.message.answer(
            ADMIN["lesson_edit_content_saved"].format(title=lesson.title, count=len(lesson_contents)),
            reply_markup=get_admin_main_menu()
        )


@router.callback_query(F.data == "admin:lesson:reorder")
@admin_only
@log_errors
async def reorder_lessons(callback: CallbackQuery):
    """Show lessons with up/down buttons for reordering"""
    await callback.answer()
    await _show_reorder_lessons(callback)


async def _show_reorder_lessons(callback: CallbackQuery):
    """Display reorder interface for lessons"""
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        lessons = await lesson_service.get_all_lessons(active_only=False)

        if not lessons or len(lessons) < 2:
            await callback.message.edit_text(
                ADMIN["reorder_min_lessons"],
                reply_markup=get_back_keyboard()
            )
            return

        builder = InlineKeyboardBuilder()
        for i, lesson in enumerate(lessons):
            row_buttons = []
            if i > 0:
                row_buttons.append(InlineKeyboardButton(text="⬆️", callback_data=f"admin:lesson:moveup:{lesson.id}"))
            else:
                row_buttons.append(InlineKeyboardButton(text="  ", callback_data="noop"))
            row_buttons.append(InlineKeyboardButton(text=f"{lesson.order}. {lesson.title[:20]}", callback_data="noop"))
            if i < len(lessons) - 1:
                row_buttons.append(InlineKeyboardButton(text="⬇️", callback_data=f"admin:lesson:movedown:{lesson.id}"))
            else:
                row_buttons.append(InlineKeyboardButton(text="  ", callback_data="noop"))
            builder.row(*row_buttons)

        builder.row(InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:lessons"))

        await callback.message.edit_text(
            ADMIN["reorder_header"],
            reply_markup=builder.as_markup()
        )


@router.callback_query(F.data.startswith("admin:lesson:moveup:"))
@admin_only
@log_errors
async def move_lesson_up(callback: CallbackQuery):
    """Move lesson up in order"""
    lesson_id = int(callback.data.split(":")[3])
    await callback.answer()

    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        lessons = await lesson_service.get_all_lessons(active_only=False)
        lesson_ids = [l.id for l in lessons]

        idx = lesson_ids.index(lesson_id) if lesson_id in lesson_ids else -1
        if idx > 0:
            lesson_ids[idx], lesson_ids[idx - 1] = lesson_ids[idx - 1], lesson_ids[idx]
            await lesson_service.reorder_lessons(lesson_ids)

    await _show_reorder_lessons(callback)


@router.callback_query(F.data.startswith("admin:lesson:movedown:"))
@admin_only
@log_errors
async def move_lesson_down(callback: CallbackQuery):
    """Move lesson down in order"""
    lesson_id = int(callback.data.split(":")[3])
    await callback.answer()

    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        lessons = await lesson_service.get_all_lessons(active_only=False)
        lesson_ids = [l.id for l in lessons]

        idx = lesson_ids.index(lesson_id) if lesson_id in lesson_ids else -1
        if idx >= 0 and idx < len(lesson_ids) - 1:
            lesson_ids[idx], lesson_ids[idx + 1] = lesson_ids[idx + 1], lesson_ids[idx]
            await lesson_service.reorder_lessons(lesson_ids)

    await _show_reorder_lessons(callback)


@router.callback_query(F.data.startswith("admin:lesson:toggle:"))
@admin_only
@log_errors
async def toggle_lesson(callback: CallbackQuery):
    """Toggle lesson active status"""
    lesson_id = int(callback.data.split(":")[3])

    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        lesson = await lesson_service.toggle_lesson(lesson_id)

        if lesson:
            status = ADMIN["course_toggled_active"] if lesson.is_active else ADMIN["course_toggled_inactive"]
            await callback.answer(ADMIN["lesson_toggled"].format(status=status))
            # Refresh view
            await view_lesson(callback, lesson_id=lesson_id)
        else:
            await callback.answer(ADMIN["lesson_toggle_error"])


@router.callback_query(F.data.startswith("admin:lesson:delete:"))
@admin_only
@log_errors
async def delete_lesson_confirm(callback: CallbackQuery):
    """Confirm lesson deletion"""
    lesson_id = callback.data.split(":")[3]
    await callback.answer()
    await callback.message.edit_text(
        ADMIN["lesson_delete_confirm"],
        reply_markup=get_confirm_keyboard("delete_lesson", lesson_id)
    )


@router.callback_query(F.data.startswith("confirm:delete_lesson:"))
@admin_only
@log_errors
async def delete_lesson_execute(callback: CallbackQuery):
    """Execute lesson deletion"""
    lesson_id = int(callback.data.split(":")[2])
    await callback.answer()

    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        if await lesson_service.delete_lesson(lesson_id):
            await callback.message.edit_text(
                ADMIN["lesson_deleted"],
                reply_markup=get_back_keyboard()
            )
        else:
            await callback.message.edit_text(ADMIN["lesson_delete_error"])


@router.callback_query(F.data.startswith("cancel:delete_lesson:"))
@admin_only
@log_errors
async def cancel_delete_lesson(callback: CallbackQuery):
    """Cancel lesson deletion"""
    await callback.answer(ADMIN["operation_cancelled"])
    await view_lesson(callback, lesson_id=lesson_id)


# ===========================
# USER MANAGEMENT
# ===========================

@router.message(F.text == ADMIN_BUTTONS["users"])
@admin_only
@log_errors
async def user_management_menu(message: Message):
    """Show user management menu"""
    await message.answer(
        ADMIN["users_header"],
        reply_markup=get_user_management_keyboard()
    )


@router.callback_query(F.data == "admin:users:all")
@admin_only
@log_errors
async def list_all_users(callback: CallbackQuery):
    """List all users"""
    await callback.answer()
    await _show_users_list(callback, target="all", page=1)


@router.callback_query(F.data == "admin:users:active")
@admin_only
@log_errors
async def list_active_users(callback: CallbackQuery):
    """List active users"""
    await callback.answer()
    await _show_users_list(callback, target="active", page=1)


@router.callback_query(F.data == "admin:users:inactive")
@admin_only
@log_errors
async def list_inactive_users(callback: CallbackQuery):
    """List inactive users"""
    await callback.answer()
    await _show_users_list(callback, target="inactive", page=1)


@router.callback_query(F.data == "admin:users:completed")
@admin_only
@log_errors
async def list_completed_users(callback: CallbackQuery):
    """List completed users"""
    await callback.answer()
    await _show_users_list(callback, target="completed", page=1)


async def _show_users_list(callback: CallbackQuery, target: str, page: int):
    """Show paginated users list"""
    page_size = 10
    offset = (page - 1) * page_size

    async with async_session_maker() as session:
        user_service = UserService(session)

        is_active = None
        is_completed = None
        if target == "active":
            is_active = True
        elif target == "inactive":
            is_active = False
        elif target == "completed":
            is_completed = True

        users, total = await user_service.get_all_users(
            is_active=is_active,
            is_completed=is_completed,
            offset=offset,
            limit=page_size,
        )

        if not users:
            await callback.message.edit_text(
                ADMIN["users_empty"],
                reply_markup=get_user_management_keyboard()
            )
            return

        total_pages = (total + page_size - 1) // page_size
        text = ADMIN["users_list_header"].format(count=format_number(total))

        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()

        for user in users:
            status = "✅" if user.is_active else "❌"
            name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or str(user.telegram_user_id)
            builder.row(
                InlineKeyboardButton(
                    text=f"{status} {name}",
                    callback_data=f"admin:user:view:{user.id}"
                )
            )

        # Pagination
        nav_buttons = []
        if page > 1:
            nav_buttons.append(
                InlineKeyboardButton(text="◀️ قبلی", callback_data=f"admin:users:page:{target}:{page-1}")
            )
        nav_buttons.append(
            InlineKeyboardButton(text=ADMIN["users_page"].format(page=page, total=total_pages), callback_data="noop")
        )
        if page < total_pages:
            nav_buttons.append(
                InlineKeyboardButton(text="بعدی ▶️", callback_data=f"admin:users:page:{target}:{page+1}")
            )
        builder.row(*nav_buttons)

        builder.row(
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:back")
        )

        await callback.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("admin:users:page:"))
@admin_only
@log_errors
async def users_pagination(callback: CallbackQuery):
    """Handle users pagination"""
    parts = callback.data.split(":")
    target = parts[3]
    page = int(parts[4])
    await callback.answer()
    await _show_users_list(callback, target=target, page=page)


@router.callback_query(F.data.startswith("admin:user:view:"))
@admin_only
@log_errors
async def view_user(callback: CallbackQuery, user_id: int = None):
    """View user details"""
    if user_id is None:
        user_id = int(callback.data.split(":")[3])
    await callback.answer()

    async with async_session_maker() as session:
        user_service = UserService(session)
        stats = await user_service.get_user_stats(user_id)

        if not stats:
            await callback.message.edit_text(ADMIN["user_not_found"])
            return

        user = stats["user"]
        status = GENERAL["status_active"] if user.is_active else GENERAL["status_inactive"]
        name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "-"

        text = (
            ADMIN["user_info_header"] + "\n\n"
            + ADMIN["user_info_name"].format(name=name) + "\n"
            + ADMIN["user_info_username"].format(username=user.username or '-') + "\n"
            + ADMIN["user_info_id"].format(id=user.telegram_user_id) + "\n"
            + ADMIN["user_info_status"].format(status=status) + "\n"
            + ADMIN["user_info_completed"].format(
                status=ADMIN["user_completed_yes"] if user.is_completed else ADMIN["user_completed_no"]
            ) + "\n\n"
            + ADMIN["user_info_stats_header"] + "\n"
            + "  " + ADMIN["user_info_lessons"].format(
                completed=stats['completed_lessons'], total=stats['total_lessons']
            ) + "\n"
            + "  " + ADMIN["user_info_progress"].format(percent=stats['progress_percent']) + "\n"
            + "  " + ADMIN["user_info_time"].format(time=format_duration(stats['total_time_spent'])) + "\n\n"
            + ADMIN["user_info_tags"].format(
                tags=', '.join(stats['tags']) if stats['tags'] else '-'
            ) + "\n"
            + ADMIN["user_info_registered"].format(
                date=stats['registered_at'].strftime('%Y/%m/%d') if stats['registered_at'] else '-'
            ) + "\n"
        )

        # Show registration data
        if user.registration_data:
            text += "\n" + ADMIN["user_info_reg_data"] + "\n"
            for key, value in user.registration_data.items():
                text += f"  • {key}: {value}\n"

        try:
            await callback.message.edit_text(
                text, reply_markup=get_user_actions_keyboard(user_id)
            )
        except TelegramBadRequest:
            pass  # Same content, ignore


@router.callback_query(F.data.startswith("admin:user:message:"))
@admin_only
@log_errors
async def start_private_message(callback: CallbackQuery, state: FSMContext):
    """Start sending private message to user"""
    user_id = int(callback.data.split(":")[3])
    await callback.answer()
    await state.update_data(target_user_id=user_id)
    await callback.message.answer(
        ADMIN["user_message_prompt"],
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_private_message)


@router.message(AdminStates.waiting_private_message)
async def send_private_message(message: Message, state: FSMContext, bot: Bot):
    """Send private message to user"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer(GENERAL["cancelled"], reply_markup=get_admin_main_menu())
        return

    data = await state.get_data()
    user_id = data["target_user_id"]
    await state.clear()

    async with async_session_maker() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_id(user_id)

        if not user:
            await message.answer(ADMIN["user_not_found"], reply_markup=get_admin_main_menu())
            return

        broadcast_service = BroadcastService(session, bot)
        success = await broadcast_service.send_private_message(
            user.telegram_user_id, message.text
        )

        if success:
            await message.answer(ADMIN["user_message_sent"], reply_markup=get_admin_main_menu())
        else:
            await message.answer(ADMIN["user_message_error"], reply_markup=get_admin_main_menu())


@router.callback_query(F.data.startswith("admin:user:block:"))
@admin_only
@log_errors
async def block_user(callback: CallbackQuery):
    """Block a user"""
    user_id = int(callback.data.split(":")[3])
    await callback.answer()

    async with async_session_maker() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_id(user_id)

        if user and user.is_active:
            await user_service.block_user(user_id)
            await callback.message.edit_text(ADMIN["user_blocked"], reply_markup=get_back_keyboard())
        elif user:
            await user_service.unblock_user(user_id)
            await callback.message.edit_text(ADMIN["user_unblocked"], reply_markup=get_back_keyboard())


@router.callback_query(F.data.startswith("admin:user:delete:"))
@admin_only
@log_errors
async def delete_user_confirm(callback: CallbackQuery):
    """Confirm user deletion"""
    user_id = callback.data.split(":")[3]
    await callback.answer()
    await callback.message.edit_text(
        ADMIN["user_delete_confirm"],
        reply_markup=get_confirm_keyboard("delete_user", user_id)
    )


@router.callback_query(F.data.startswith("cancel:delete_user:"))
@admin_only
@log_errors
async def cancel_delete_user(callback: CallbackQuery):
    """Cancel user deletion"""
    await callback.answer(ADMIN["operation_cancelled"])
    user_id = int(callback.data.split(":")[2])
    # Go back to user view
    await view_user(callback, user_id=user_id)


@router.callback_query(F.data.startswith("admin:user:stats:"))
@admin_only
@log_errors
async def user_stats(callback: CallbackQuery):
    """Show user stats - redirects to user view which includes stats"""
    user_id = int(callback.data.split(":")[3])
    await view_user(callback, user_id=user_id)


@router.callback_query(F.data.startswith("confirm:delete_user:"))
@admin_only
@log_errors
async def delete_user_execute(callback: CallbackQuery):
    """Execute user deletion"""
    user_id = int(callback.data.split(":")[2])
    await callback.answer()

    async with async_session_maker() as session:
        user_service = UserService(session)
        if await user_service.delete_user(user_id):
            await callback.message.edit_text(ADMIN["user_deleted"], reply_markup=get_back_keyboard())
        else:
            await callback.message.edit_text(ADMIN["user_delete_error"])


@router.callback_query(F.data.startswith("admin:user:reset:"))
@admin_only
@log_errors
async def reset_user_progress(callback: CallbackQuery):
    """Reset user progress"""
    user_id = int(callback.data.split(":")[3])
    await callback.answer()

    async with async_session_maker() as session:
        user_service = UserService(session)
        if await user_service.reset_user_progress(user_id):
            await callback.message.edit_text(ADMIN["user_progress_reset"], reply_markup=get_back_keyboard())
        else:
            await callback.message.edit_text(ADMIN["user_progress_reset_error"])


@router.callback_query(F.data.startswith("admin:user:tags:"))
@admin_only
@log_errors
async def manage_user_tags(callback: CallbackQuery, state: FSMContext):
    """Start tag management for user"""
    user_id = int(callback.data.split(":")[3])
    await callback.answer()

    async with async_session_maker() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_id(user_id)
        current_tags = user.tags if user and user.tags else []

    await state.update_data(target_user_id=user_id)
    await callback.message.answer(
        ADMIN["tags_header"].format(
            tags=', '.join(current_tags) if current_tags else 'ندارد'
        ),
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_tag_input)


@router.message(AdminStates.waiting_tag_input)
async def process_tags(message: Message, state: FSMContext):
    """Process tag input"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer(GENERAL["cancelled"], reply_markup=get_admin_main_menu())
        return

    data = await state.get_data()
    user_id = data["target_user_id"]
    await state.clear()

    async with async_session_maker() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_id(user_id)

        if not user:
            await message.answer(ADMIN["user_not_found"], reply_markup=get_admin_main_menu())
            return

        if message.text.strip().lower() == "clear":
            user.tags = []
        else:
            tags = [t.strip() for t in message.text.split(",") if t.strip()]
            user.tags = tags

        await session.commit()
        await message.answer(
            ADMIN["tags_updated"].format(
                tags=', '.join(user.tags) if user.tags else 'ندارد'
            ),
            reply_markup=get_admin_main_menu()
        )


@router.callback_query(F.data == "admin:users:search")
@admin_only
@log_errors
async def start_user_search(callback: CallbackQuery, state: FSMContext):
    """Start user search"""
    await callback.answer()
    await callback.message.answer(
        ADMIN["search_prompt"],
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_user_search)


@router.message(AdminStates.waiting_user_search)
async def process_user_search(message: Message, state: FSMContext):
    """Process user search"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer(GENERAL["cancelled"], reply_markup=get_admin_main_menu())
        return

    await state.clear()

    async with async_session_maker() as session:
        user_service = UserService(session)
        users, total = await user_service.search_users(message.text)

        if not users:
            await message.answer(ADMIN["search_empty"], reply_markup=get_admin_main_menu())
            return

        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()

        for user in users:
            name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or str(user.telegram_user_id)
            builder.row(
                InlineKeyboardButton(
                    text=f"👤 {name}",
                    callback_data=f"admin:user:view:{user.id}"
                )
            )

        builder.row(InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:back"))

        await message.answer(
            ADMIN["search_results"].format(count=total),
            reply_markup=builder.as_markup()
        )


@router.callback_query(F.data == "admin:users:export")
@admin_only
@log_errors
async def export_users(callback: CallbackQuery):
    """Export users to Excel"""
    await callback.answer(ADMIN["export_preparing"])

    async with async_session_maker() as session:
        export_service = ExportService(session)
        excel_file = await export_service.export_users_to_excel()

        await callback.message.answer_document(
            document=BufferedInputFile(
                excel_file.read(),
                filename=f"users_export.xlsx"
            ),
            caption=ADMIN["export_users_caption"]
        )


# ===========================
# BROADCAST
# ===========================

@router.message(F.text == ADMIN_BUTTONS["broadcast"])
@admin_only
@log_errors
async def broadcast_menu(message: Message):
    """Show broadcast menu"""
    await message.answer(
        ADMIN["broadcast_header"],
        reply_markup=get_broadcast_keyboard()
    )


@router.callback_query(F.data.startswith("admin:broadcast:"))
@admin_only
@log_errors
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    """Start broadcast process"""
    target = callback.data.split(":")[2]
    if target == "back":
        return

    await callback.answer()
    await state.update_data(broadcast_target=target)
    await callback.message.answer(
        ADMIN["broadcast_enter_msg"],
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_broadcast_message)


@router.message(AdminStates.waiting_broadcast_message)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
    """Process and send broadcast"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer(GENERAL["cancelled"], reply_markup=get_admin_main_menu())
        return

    data = await state.get_data()
    target = data["broadcast_target"]
    await state.clear()

    await message.answer(ADMIN["broadcast_sending"])

    async with async_session_maker() as session:
        broadcast_service = BroadcastService(session, bot)
        result = await broadcast_service.broadcast_message(
            admin_id=message.from_user.id,
            message=message.text,
            target=target,
        )

        await message.answer(
            ADMIN["broadcast_result"].format(
                total=format_number(result.total_users),
                sent=format_number(result.success_count),
                failed=format_number(result.failed_count)
            ),
            reply_markup=get_admin_main_menu()
        )


# ===========================
# REGISTRATION FIELDS
# ===========================

@router.message(F.text == ADMIN_BUTTONS["reg_fields"])
@admin_only
@log_errors
async def registration_fields_menu(message: Message):
    """Show registration fields menu"""
    await message.answer(
        ADMIN["fields_header"],
        reply_markup=get_registration_fields_keyboard()
    )


@router.callback_query(F.data == "admin:field:add")
@admin_only
@log_errors
async def add_field_start(callback: CallbackQuery, state: FSMContext):
    """Start adding a registration field"""
    await callback.answer()
    await callback.message.answer(
        ADMIN["field_add_name"],
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_field_name)


@router.message(AdminStates.waiting_field_name)
async def process_field_name(message: Message, state: FSMContext):
    """Process field name"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer(GENERAL["cancelled"], reply_markup=get_admin_main_menu())
        return

    await state.update_data(field_name=message.text.strip().lower().replace(" ", "_"))
    await message.answer(ADMIN["field_add_label"])
    await state.set_state(AdminStates.waiting_field_label)


@router.message(AdminStates.waiting_field_label)
async def process_field_label(message: Message, state: FSMContext):
    """Process field label"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer(GENERAL["cancelled"], reply_markup=get_admin_main_menu())
        return

    await state.update_data(field_label=message.text.strip())
    await message.answer(
        ADMIN["field_add_type"],
        reply_markup=get_field_type_keyboard()
    )
    await state.set_state(AdminStates.waiting_field_type)


@router.callback_query(F.data.startswith("admin:field:type:"), AdminStates.waiting_field_type)
async def process_field_type(callback: CallbackQuery, state: FSMContext):
    """Process field type selection"""
    field_type = callback.data.split(":")[3]
    await callback.answer()
    await state.update_data(field_type=field_type)

    if field_type == "select":
        await callback.message.answer(
            ADMIN["field_add_options"],
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(AdminStates.waiting_field_options)
    else:
        # Save field
        await _save_registration_field(callback.message, state)


@router.message(AdminStates.waiting_field_options)
async def process_field_options(message: Message, state: FSMContext):
    """Process select field options"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer(GENERAL["cancelled"], reply_markup=get_admin_main_menu())
        return

    options = [o.strip() for o in message.text.split(",") if o.strip()]
    await state.update_data(field_options={"choices": options})
    await _save_registration_field(message, state)


async def _save_registration_field(message: Message, state: FSMContext):
    """Save registration field to database"""
    data = await state.get_data()
    await state.clear()

    field_type_map = {
        "text": FieldType.TEXT,
        "number": FieldType.NUMBER,
        "email": FieldType.EMAIL,
        "phone": FieldType.PHONE,
        "date": FieldType.DATE,
        "select": FieldType.SELECT,
    }

    async with async_session_maker() as session:
        from database.models import RegistrationField
        from sqlalchemy import select as sa_select, func as sa_func

        # Get next order
        max_order = (await session.execute(
            sa_select(sa_func.max(RegistrationField.order))
        )).scalar() or 0

        field = RegistrationField(
            field_name=data["field_name"],
            field_label=data["field_label"],
            field_type=field_type_map[data["field_type"]],
            order=max_order + 1,
            options=data.get("field_options"),
        )
        session.add(field)
        await session.commit()

        await message.answer(
            ADMIN["field_added"].format(
                label=field.field_label,
                type=data['field_type'],
                order=field.order
            ),
            reply_markup=get_admin_main_menu()
        )


@router.callback_query(F.data == "admin:field:list")
@admin_only
@log_errors
async def list_registration_fields(callback: CallbackQuery):
    """List all registration fields with action buttons"""
    await callback.answer()

    async with async_session_maker() as session:
        user_service = UserService(session)
        fields = await user_service.get_active_registration_fields()

        if not fields:
            await callback.message.edit_text(
                ADMIN["field_list_empty"],
                reply_markup=get_registration_fields_keyboard()
            )
            return

        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder

        text = ADMIN["field_list_header"]
        builder = InlineKeyboardBuilder()
        for f in fields:
            required = "✅" if f.is_required else "❌"
            active = "🟢" if f.is_active else "🔴"
            builder.row(InlineKeyboardButton(
                text=f"{active} {f.order}. {f.field_label} ({f.field_type.value}) {required}",
                callback_data=f"admin:field:view:{f.id}"
            ))
        builder.row(InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:back"))

        await callback.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "admin:field:reorder")
@admin_only
@log_errors
async def reorder_fields(callback: CallbackQuery):
    """Show fields with up/down buttons for reordering"""
    await callback.answer()
    await _show_reorder_fields(callback)


async def _show_reorder_fields(callback: CallbackQuery):
    """Display reorder interface for registration fields"""
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    async with async_session_maker() as session:
        user_service = UserService(session)
        fields = await user_service.get_active_registration_fields()

        if not fields or len(fields) < 2:
            await callback.message.edit_text(
                ADMIN["reorder_fields_min"],
                reply_markup=get_registration_fields_keyboard()
            )
            return

        builder = InlineKeyboardBuilder()
        for i, field in enumerate(fields):
            row_buttons = []
            if i > 0:
                row_buttons.append(InlineKeyboardButton(text="⬆️", callback_data=f"admin:field:moveup:{field.id}"))
            else:
                row_buttons.append(InlineKeyboardButton(text="  ", callback_data="noop"))
            row_buttons.append(InlineKeyboardButton(text=f"{field.order}. {field.field_label[:20]}", callback_data="noop"))
            if i < len(fields) - 1:
                row_buttons.append(InlineKeyboardButton(text="⬇️", callback_data=f"admin:field:movedown:{field.id}"))
            else:
                row_buttons.append(InlineKeyboardButton(text="  ", callback_data="noop"))
            builder.row(*row_buttons)

        builder.row(InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:back"))

        await callback.message.edit_text(
            ADMIN["reorder_fields_header"],
            reply_markup=builder.as_markup()
        )


@router.callback_query(F.data.startswith("admin:field:moveup:"))
@admin_only
@log_errors
async def move_field_up(callback: CallbackQuery):
    """Move field up in order"""
    field_id = int(callback.data.split(":")[3])
    await callback.answer()

    async with async_session_maker() as session:
        user_service = UserService(session)
        fields = await user_service.get_active_registration_fields()
        field_ids = [f.id for f in fields]

        idx = field_ids.index(field_id) if field_id in field_ids else -1
        if idx > 0:
            field_ids[idx], field_ids[idx - 1] = field_ids[idx - 1], field_ids[idx]
            await user_service.reorder_registration_fields(field_ids)

    await _show_reorder_fields(callback)


@router.callback_query(F.data.startswith("admin:field:movedown:"))
@admin_only
@log_errors
async def move_field_down(callback: CallbackQuery):
    """Move field down in order"""
    field_id = int(callback.data.split(":")[3])
    await callback.answer()

    async with async_session_maker() as session:
        user_service = UserService(session)
        fields = await user_service.get_active_registration_fields()
        field_ids = [f.id for f in fields]

        idx = field_ids.index(field_id) if field_id in field_ids else -1
        if idx >= 0 and idx < len(field_ids) - 1:
            field_ids[idx], field_ids[idx + 1] = field_ids[idx + 1], field_ids[idx]
            await user_service.reorder_registration_fields(field_ids)

    await _show_reorder_fields(callback)


@router.callback_query(F.data == "admin:field:cancel")
async def cancel_field_operation(callback: CallbackQuery, state: FSMContext):
    """Cancel field operation"""
    await state.clear()
    await callback.answer(ADMIN["operation_cancelled"])
    await callback.message.edit_text(
        ADMIN["fields_header"],
        reply_markup=get_registration_fields_keyboard()
    )


# ===========================
# FIELD VIEW / EDIT / TOGGLE / DELETE
# ===========================

@router.callback_query(F.data.startswith("admin:field:view:"))
@admin_only
@log_errors
async def view_field(callback: CallbackQuery, field_id: int = None):
    """View a registration field details"""
    if field_id is None:
        field_id = int(callback.data.split(":")[3])
    await callback.answer()

    async with async_session_maker() as session:
        result = await session.execute(
            select(RegistrationField).where(RegistrationField.id == field_id)
        )
        field = result.scalar_one_or_none()

        if not field:
            await callback.message.edit_text(ADMIN["field_not_found"])
            return

        required = ADMIN["field_required_yes"] if field.is_required else ADMIN["field_required_no"]
        active = GENERAL["status_active"] if field.is_active else GENERAL["status_inactive"]
        options_text = ""
        if field.options and field.options.get("choices"):
            options_text = "\n" + ADMIN["field_view_options"].format(options=', '.join(field.options['choices']))

        text = (
            ADMIN["field_view_header"] + "\n\n"
            + ADMIN["field_view_name"].format(name=field.field_name) + "\n"
            + ADMIN["field_view_label"].format(label=field.field_label) + "\n"
            + ADMIN["field_view_type"].format(type=field.field_type.value) + "\n"
            + ADMIN["field_view_required"].format(status=required) + "\n"
            + ADMIN["field_view_active"].format(status=active) + "\n"
            + ADMIN["field_view_order"].format(order=field.order)
            + options_text
        )

        await callback.message.edit_text(
            text, reply_markup=get_field_actions_keyboard(field_id)
        )


@router.callback_query(F.data.startswith("admin:field:togglereq:"))
@admin_only
@log_errors
async def toggle_field_required(callback: CallbackQuery):
    """Toggle field required status"""
    field_id = int(callback.data.split(":")[3])

    async with async_session_maker() as session:
        result = await session.execute(
            select(RegistrationField).where(RegistrationField.id == field_id)
        )
        field = result.scalar_one_or_none()
        if field:
            field.is_required = not field.is_required
            await session.commit()
            status = ADMIN["field_toggle_required_on"] if field.is_required else ADMIN["field_toggle_required_off"]
            await callback.answer(ADMIN["field_toggle_required"].format(status=status))

    # Refresh view
    await view_field(callback, field_id=field_id)


@router.callback_query(F.data.startswith("admin:field:toggle:"))
@admin_only
@log_errors
async def toggle_field_active(callback: CallbackQuery):
    """Toggle field active/inactive"""
    field_id = int(callback.data.split(":")[3])

    async with async_session_maker() as session:
        result = await session.execute(
            select(RegistrationField).where(RegistrationField.id == field_id)
        )
        field = result.scalar_one_or_none()
        if field:
            field.is_active = not field.is_active
            await session.commit()
            status = ADMIN["field_toggle_active_on"] if field.is_active else ADMIN["field_toggle_active_off"]
            await callback.answer(ADMIN["field_toggle_active"].format(status=status))

    await view_field(callback, field_id=field_id)


@router.callback_query(F.data.startswith("admin:field:del:"))
@admin_only
@log_errors
async def delete_field(callback: CallbackQuery):
    """Delete a registration field"""
    field_id = int(callback.data.split(":")[3])
    await callback.answer()

    async with async_session_maker() as session:
        result = await session.execute(
            select(RegistrationField).where(RegistrationField.id == field_id)
        )
        field = result.scalar_one_or_none()
        if field:
            await session.delete(field)
            await session.commit()
            await callback.message.edit_text(
                ADMIN["field_deleted"],
                reply_markup=get_registration_fields_keyboard()
            )
        else:
            await callback.message.edit_text(ADMIN["field_not_found"])


@router.callback_query(F.data.startswith("admin:field:editlbl:"))
@admin_only
@log_errors
async def edit_field_label_start(callback: CallbackQuery, state: FSMContext):
    """Start editing field label"""
    field_id = int(callback.data.split(":")[3])
    await callback.answer()
    await state.update_data(edit_field_id=field_id)
    await callback.message.answer(
        ADMIN["field_edit_label_prompt"],
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_field_edit_label)


@router.message(AdminStates.waiting_field_edit_label)
async def process_field_edit_label(message: Message, state: FSMContext):
    """Process new field label"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer(GENERAL["cancelled"], reply_markup=get_admin_main_menu())
        return

    data = await state.get_data()
    field_id = data["edit_field_id"]
    await state.clear()

    async with async_session_maker() as session:
        result = await session.execute(
            select(RegistrationField).where(RegistrationField.id == field_id)
        )
        field = result.scalar_one_or_none()
        if field:
            field.field_label = message.text.strip()
            await session.commit()
            await message.answer(
                ADMIN["field_label_updated"].format(label=field.field_label),
                reply_markup=get_admin_main_menu()
            )
        else:
            await message.answer(ADMIN["field_not_found"], reply_markup=get_admin_main_menu())


# ===========================
# FORM BUILDER (for FORM lesson type)
# ===========================

@router.message(AdminStates.waiting_form_field_label)
async def form_builder_field_label(message: Message, state: FSMContext):
    """Process form field label in form builder"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer(GENERAL["cancelled"], reply_markup=get_admin_main_menu())
        return

    await state.update_data(current_form_field_label=message.text.strip())

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=ADMIN["form_field_type_text"], callback_data="formft:text"),
        InlineKeyboardButton(text=ADMIN["form_field_type_number"], callback_data="formft:number"),
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN["form_field_type_select"], callback_data="formft:select"),
    )

    await message.answer(ADMIN["form_field_type"], reply_markup=builder.as_markup())
    await state.set_state(AdminStates.waiting_form_field_type)


@router.callback_query(F.data.startswith("formft:"), AdminStates.waiting_form_field_type)
async def form_builder_field_type(callback: CallbackQuery, state: FSMContext):
    """Process form field type"""
    field_type = callback.data.split(":")[1]
    await callback.answer()
    await state.update_data(current_form_field_type=field_type)

    if field_type == "select":
        await callback.message.answer(
            ADMIN["form_field_options"],
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(AdminStates.waiting_form_field_options)
    else:
        # Save field and ask for more
        await _save_form_field_and_ask_more(callback.message, state)


@router.message(AdminStates.waiting_form_field_options)
async def form_builder_field_options(message: Message, state: FSMContext):
    """Process form field select options"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer(GENERAL["cancelled"], reply_markup=get_admin_main_menu())
        return

    options = [o.strip() for o in message.text.split(",") if o.strip()]
    await state.update_data(current_form_field_options=options)
    await _save_form_field_and_ask_more(message, state)


async def _save_form_field_and_ask_more(message: Message, state: FSMContext):
    """Save current form field and ask if more needed"""
    data = await state.get_data()
    fields = data.get("form_fields", [])

    field = {
        "name": f"field_{len(fields) + 1}",
        "label": data["current_form_field_label"],
        "type": data["current_form_field_type"],
    }
    if data.get("current_form_field_options"):
        field["options"] = data["current_form_field_options"]

    fields.append(field)
    await state.update_data(
        form_fields=fields,
        current_form_field_label=None,
        current_form_field_type=None,
        current_form_field_options=None,
    )

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["add_another_field"], callback_data="form_add_more"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["finish_form"], callback_data="form_done"),
    )

    fields_text = "\n".join([f"  {i+1}. {f['label']} ({f['type']})" for i, f in enumerate(fields)])
    await message.answer(
        ADMIN["form_field_added"].format(label=field['label'], fields=fields_text),
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "form_add_more")
async def form_add_more_field(callback: CallbackQuery, state: FSMContext):
    """Add another form field"""
    await callback.answer()
    await callback.message.answer(
        ADMIN["form_next_field"],
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_form_field_label)


@router.callback_query(F.data == "form_done")
async def form_builder_done(callback: CallbackQuery, state: FSMContext):
    """Form building complete, continue to description"""
    await callback.answer()
    await callback.message.answer(
        ADMIN["form_enter_description"],
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_lesson_description)


# ===========================
# QUIZ MANAGEMENT
# ===========================

@router.callback_query(F.data.startswith("admin:lesson:quiz:"))
@admin_only
@log_errors
async def manage_lesson_quiz(callback: CallbackQuery, state: FSMContext):
    """Manage quiz for a lesson"""
    lesson_id = int(callback.data.split(":")[3])
    await callback.answer()

    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        lesson = await lesson_service.get_lesson_by_id(lesson_id)

        if not lesson:
            await callback.message.edit_text(ADMIN["lesson_not_found"])
            return

        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder

        if lesson.quiz_data and lesson.quiz_data.get("questions"):
            # Show existing quiz
            questions = lesson.quiz_data["questions"]
            passing = lesson.quiz_data.get("passing_score", 100)
            text = (
                ADMIN["quiz_header"].format(
                    title=lesson.title, count=len(questions), score=passing
                ) + "\n\n"
            )
            for i, q in enumerate(questions, 1):
                is_multi = q.get("multi_select", False)
                if is_multi:
                    correct_indices = q["correct"] if isinstance(q["correct"], list) else [q["correct"]]
                    correct_opts = [q["options"][c] for c in correct_indices if c < len(q["options"])]
                    correct_text = "، ".join(correct_opts)
                    text += f"<b>{i}.</b> ☑️ {q['text']}\n   " + ADMIN["quiz_correct_answer"].format(answer=correct_text) + "\n"
                else:
                    correct_opt = q["options"][q["correct"]] if q["correct"] < len(q["options"]) else "?"
                    text += f"<b>{i}.</b> 🔘 {q['text']}\n   " + ADMIN["quiz_correct_answer"].format(answer=correct_opt) + "\n"

            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text=ADMIN_BUTTONS["delete_quiz"], callback_data=f"admin:quiz:del:{lesson_id}"),
                InlineKeyboardButton(text=ADMIN_BUTTONS["rebuild_quiz"], callback_data=f"admin:quiz:new:{lesson_id}"),
            )
            builder.row(
                InlineKeyboardButton(text=GENERAL["back"], callback_data=f"admin:lesson:view:{lesson_id}")
            )
            await callback.message.edit_text(text, reply_markup=builder.as_markup())
        else:
            # No quiz - offer to create
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text=ADMIN_BUTTONS["add_quiz"], callback_data=f"admin:quiz:new:{lesson_id}"),
            )
            builder.row(
                InlineKeyboardButton(text=GENERAL["back"], callback_data=f"admin:lesson:view:{lesson_id}")
            )
            await callback.message.edit_text(
                ADMIN["quiz_no_quiz"].format(title=lesson.title),
                reply_markup=builder.as_markup()
            )


@router.callback_query(F.data.startswith("admin:quiz:del:"))
@admin_only
@log_errors
async def delete_quiz(callback: CallbackQuery):
    """Delete quiz from a lesson"""
    lesson_id = int(callback.data.split(":")[3])
    await callback.answer()

    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        lesson = await lesson_service.get_lesson_by_id(lesson_id)
        if lesson:
            lesson.quiz_data = None
            await session.commit()

    await callback.message.edit_text(
        ADMIN["quiz_deleted"],
        reply_markup=get_back_keyboard()
    )


@router.callback_query(F.data.startswith("admin:quiz:new:"))
@admin_only
@log_errors
async def start_quiz_creation(callback: CallbackQuery, state: FSMContext):
    """Start creating a new quiz"""
    lesson_id = int(callback.data.split(":")[3])
    await callback.answer()
    await state.update_data(quiz_lesson_id=lesson_id, quiz_questions=[])
    await callback.message.answer(
        ADMIN["quiz_enter_score"],
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_quiz_passing_score)


@router.message(AdminStates.waiting_quiz_passing_score)
async def process_quiz_passing_score(message: Message, state: FSMContext):
    """Process quiz passing score"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer(GENERAL["cancelled"], reply_markup=get_admin_main_menu())
        return

    try:
        score = int(message.text)
        if score < 1 or score > 100:
            raise ValueError
    except (ValueError, TypeError):
        await message.answer(ADMIN["quiz_score_error"])
        return

    await state.update_data(quiz_passing_score=score)
    await message.answer(
        ADMIN["quiz_enter_first_question"],
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_quiz_question_text)


@router.message(AdminStates.waiting_quiz_question_text)
async def process_quiz_question_text(message: Message, state: FSMContext):
    """Process quiz question text"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer(GENERAL["cancelled"], reply_markup=get_admin_main_menu())
        return

    await state.update_data(current_q_text=message.text.strip())
    await message.answer(
        ADMIN["quiz_enter_options"],
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_quiz_options)


@router.message(AdminStates.waiting_quiz_options)
async def process_quiz_options(message: Message, state: FSMContext):
    """Process quiz question options"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer(GENERAL["cancelled"], reply_markup=get_admin_main_menu())
        return

    options = [line.strip() for line in message.text.strip().split("\n") if line.strip()]
    if len(options) < 2:
        await message.answer(ADMIN["quiz_options_error"])
        return

    await state.update_data(current_q_options=options)

    # Ask question type: single or multi-select
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=ADMIN["quiz_type_single"], callback_data="quiz_type:single"),
        InlineKeyboardButton(text=ADMIN["quiz_type_multi"], callback_data="quiz_type:multi"),
    )
    await message.answer(
        ADMIN["quiz_question_type"],
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("quiz_type:"))
async def select_question_type(callback: CallbackQuery, state: FSMContext):
    """Handle question type selection (single or multi)"""
    q_type = callback.data.split(":")[1]
    await callback.answer()

    data = await state.get_data()
    options = data.get("current_q_options", [])
    await state.update_data(current_q_type=q_type)

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    if q_type == "multi":
        # Multi-select: allow toggling multiple correct answers
        await state.update_data(current_q_correct_multi=[])
        builder = InlineKeyboardBuilder()
        for i, opt in enumerate(options):
            builder.row(InlineKeyboardButton(text=f"⬜️ {opt}", callback_data=f"quizmc:{i}"))
        builder.row(InlineKeyboardButton(text=ADMIN["quiz_confirm_correct_multi"], callback_data="quizmc_done"))
        await callback.message.answer(
            ADMIN["quiz_select_correct_multi"],
            reply_markup=builder.as_markup()
        )
    else:
        # Single select: pick one correct answer
        builder = InlineKeyboardBuilder()
        for i, opt in enumerate(options):
            builder.row(InlineKeyboardButton(text=f"✅ {opt}", callback_data=f"quizc:{i}"))
        await callback.message.answer(
            ADMIN["quiz_select_correct"],
            reply_markup=builder.as_markup()
        )


@router.callback_query(F.data.startswith("quizmc:"))
async def toggle_multi_correct(callback: CallbackQuery, state: FSMContext):
    """Toggle a correct answer for multi-select question"""
    opt_idx = int(callback.data.split(":")[1])
    await callback.answer()

    data = await state.get_data()
    options = data.get("current_q_options", [])
    selected = data.get("current_q_correct_multi", [])

    if opt_idx in selected:
        selected.remove(opt_idx)
    else:
        selected.append(opt_idx)

    await state.update_data(current_q_correct_multi=selected)

    # Rebuild keyboard with updated toggles
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for i, opt in enumerate(options):
        icon = "✅" if i in selected else "⬜️"
        builder.row(InlineKeyboardButton(text=f"{icon} {opt}", callback_data=f"quizmc:{i}"))
    builder.row(InlineKeyboardButton(text=ADMIN["quiz_confirm_correct_multi"], callback_data="quizmc_done"))

    try:
        await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
    except Exception:
        pass


@router.callback_query(F.data == "quizmc_done")
async def confirm_multi_correct(callback: CallbackQuery, state: FSMContext):
    """Confirm multi-select correct answers and save question"""
    data = await state.get_data()
    selected = data.get("current_q_correct_multi", [])

    if not selected:
        await callback.answer(ADMIN["quiz_multi_select_at_least"])
        return

    await callback.answer(ADMIN["quiz_answer_saved"])

    questions = data.get("quiz_questions", [])
    questions.append({
        "text": data["current_q_text"],
        "options": data["current_q_options"],
        "correct": sorted(selected),
        "multi_select": True,
    })
    await state.update_data(
        quiz_questions=questions,
        current_q_text=None,
        current_q_options=None,
        current_q_type=None,
        current_q_correct_multi=None,
    )

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["next_question"], callback_data="quiz_more"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["save_quiz"], callback_data="quiz_save"),
    )

    await callback.message.answer(
        ADMIN["quiz_question_added"].format(n=len(questions)),
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("quizc:"))
async def select_correct_answer(callback: CallbackQuery, state: FSMContext):
    """Select correct answer for single-select quiz question"""
    correct_idx = int(callback.data.split(":")[1])
    await callback.answer(ADMIN["quiz_answer_saved"])

    data = await state.get_data()
    questions = data.get("quiz_questions", [])
    questions.append({
        "text": data["current_q_text"],
        "options": data["current_q_options"],
        "correct": correct_idx,
        "multi_select": False,
    })
    await state.update_data(
        quiz_questions=questions,
        current_q_text=None,
        current_q_options=None,
        current_q_type=None,
    )

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["next_question"], callback_data="quiz_more"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["save_quiz"], callback_data="quiz_save"),
    )

    await callback.message.answer(
        ADMIN["quiz_question_added"].format(n=len(questions)),
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "quiz_more")
async def quiz_add_more(callback: CallbackQuery, state: FSMContext):
    """Add more quiz questions"""
    await callback.answer()
    data = await state.get_data()
    q_num = len(data.get("quiz_questions", [])) + 1
    await callback.message.answer(
        ADMIN["quiz_enter_question"].format(n=q_num),
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_quiz_question_text)


@router.callback_query(F.data == "quiz_save")
@admin_only
async def quiz_save(callback: CallbackQuery, state: FSMContext):
    """Save quiz to lesson"""
    await callback.answer()
    data = await state.get_data()
    lesson_id = data.get("quiz_lesson_id")
    questions = data.get("quiz_questions", [])
    passing_score = data.get("quiz_passing_score", 100)
    await state.clear()

    if not questions:
        await callback.message.answer(ADMIN["quiz_empty"], reply_markup=get_admin_main_menu())
        return

    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        lesson = await lesson_service.get_lesson_by_id(lesson_id)
        if lesson:
            lesson.quiz_data = {
                "passing_score": passing_score,
                "questions": questions,
            }
            await session.commit()
            await callback.message.answer(
                ADMIN["quiz_saved"].format(count=len(questions), score=passing_score),
                reply_markup=get_admin_main_menu()
            )
        else:
            await callback.message.answer(ADMIN["lesson_not_found"], reply_markup=get_admin_main_menu())


# ===========================
# REPORTS & ANALYTICS
# ===========================

@router.message(F.text == ADMIN_BUTTONS["reports"])
@admin_only
@log_errors
async def reports_menu(message: Message):
    """Show reports menu"""
    await message.answer(
        ADMIN["reports_header"],
        reply_markup=get_stats_keyboard()
    )


@router.callback_query(F.data.startswith("admin:stats:"))
@admin_only
@log_errors
async def show_stats(callback: CallbackQuery):
    """Show statistics for selected period"""
    period = callback.data.split(":")[2]
    await callback.answer()

    if period == "export":
        await export_analytics(callback)
        return

    async with async_session_maker() as session:
        analytics = AnalyticsService(session)

        days_map = {"today": 1, "week": 7, "month": 30, "all": 365}
        days = days_map.get(period, 7)

        period_stats = await analytics.get_period_stats(days)
        lesson_stats = await analytics.get_lesson_completion_stats()

        period_labels = ADMIN["report_period_labels"]

        text = (
            ADMIN["report_header"].format(period=period_labels.get(period, period)) + "\n\n"
            + ADMIN["report_new_users"].format(count=format_number(period_stats['new_users'])) + "\n"
            + ADMIN["report_completed_lessons"].format(count=format_number(period_stats['completions'])) + "\n"
            + ADMIN["report_active_users"].format(count=format_number(period_stats['active_users'])) + "\n"
        )

        if lesson_stats:
            text += "\n" + ADMIN["report_lesson_stats_header"] + "\n"
            for ls in lesson_stats[:10]:
                text += "  " + ADMIN["report_lesson_stat"].format(
                    order=ls['order'], title=ls['title'],
                    completed=ls['completed'], rate=ls['completion_rate']
                ) + "\n"

        await callback.message.edit_text(text, reply_markup=get_stats_keyboard())


async def export_analytics(callback: CallbackQuery):
    """Export analytics to Excel"""
    async with async_session_maker() as session:
        export_service = ExportService(session)
        excel_file = await export_service.export_analytics_to_excel()

        await callback.message.answer_document(
            document=BufferedInputFile(
                excel_file.read(),
                filename="analytics_export.xlsx"
            ),
            caption=ADMIN["export_analytics_caption"]
        )


# ===========================
# WEBHOOK MANAGEMENT
# ===========================

@router.message(F.text == ADMIN_BUTTONS["webhook"])
@admin_only
@log_errors
async def webhook_menu(message: Message):
    """Show webhook management menu"""
    async with async_session_maker() as session:
        webhook_service = WebhookService(session)
        webhooks = await webhook_service.get_all_webhooks()

        text = ADMIN["webhook_header"] + "\n\n"

        if webhooks:
            for wh in webhooks:
                status = "✅" if wh.is_active else "❌"
                text += f"{status} <b>{wh.name}</b>\n  🌐 {wh.url}\n\n"
        else:
            text += ADMIN["webhook_empty"] + "\n\n"

        text += (
            ADMIN["webhook_structure_header"] + "\n"
            "هر رویداد با فرمت زیر ارسال می‌شود:\n\n"
            "<code>{\n"
            '  "event": "user_registered",\n'
            '  "bot": "bot_name",\n'
            '  "timestamp": "2026-...",\n'
            '  "user": { telegram_id, username,\n'
            '    first_name, registration_data,\n'
            '    tags, is_completed, ... },\n'
            '  "data": { ... }\n'
            "}</code>\n\n"
            + ADMIN["webhook_events_header"] + "\n"
            "• user_registered\n"
            "• lesson_sent\n"
            "• lesson_completed\n"
            "• quiz_passed / quiz_failed\n"
            "• form_submitted\n"
            "• course_completed"
        )

    await message.answer(text, reply_markup=get_webhook_keyboard())


@router.callback_query(F.data == "admin:webhook:add")
@admin_only
@log_errors
async def add_webhook_start(callback: CallbackQuery, state: FSMContext):
    """Start adding a webhook"""
    await callback.answer()
    await callback.message.answer(
        ADMIN["webhook_add_name"],
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_webhook_name)


@router.message(AdminStates.waiting_webhook_name)
async def process_webhook_name(message: Message, state: FSMContext):
    """Process webhook name"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer(GENERAL["cancelled"], reply_markup=get_admin_main_menu())
        return

    await state.update_data(webhook_name=message.text.strip())
    await message.answer(ADMIN["webhook_add_url"])
    await state.set_state(AdminStates.waiting_webhook_url)


@router.message(AdminStates.waiting_webhook_url)
async def process_webhook_url(message: Message, state: FSMContext):
    """Process webhook URL"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer(GENERAL["cancelled"], reply_markup=get_admin_main_menu())
        return

    data = await state.get_data()
    await state.clear()

    async with async_session_maker() as session:
        webhook_service = WebhookService(session)
        webhook = await webhook_service.create_webhook(
            name=data["webhook_name"],
            url=message.text.strip(),
        )

        await message.answer(
            ADMIN["webhook_added"].format(name=webhook.name, url=webhook.url),
            reply_markup=get_admin_main_menu()
        )


@router.callback_query(F.data == "admin:webhook:list")
@admin_only
@log_errors
async def list_webhooks(callback: CallbackQuery):
    """List all webhooks with management options"""
    await callback.answer()

    async with async_session_maker() as session:
        webhook_service = WebhookService(session)
        webhooks = await webhook_service.get_all_webhooks()

        if not webhooks:
            await callback.message.edit_text(
                ADMIN["webhook_list_empty"],
                reply_markup=get_webhook_keyboard()
            )
            return

        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder

        builder = InlineKeyboardBuilder()
        text = ADMIN["webhook_list_header"] + "\n\n"
        for wh in webhooks:
            status = "✅" if wh.is_active else "❌"
            text += f"{status} <b>{wh.name}</b>\n  🌐 {wh.url}\n\n"
            toggle_label = "❌ غیرفعال" if wh.is_active else "✅ فعال"
            builder.row(
                InlineKeyboardButton(text=f"🔄 {wh.name}: {toggle_label}", callback_data=f"admin:wh:toggle:{wh.id}"),
                InlineKeyboardButton(text=f"🗑 حذف", callback_data=f"admin:wh:delete:{wh.id}"),
            )

        builder.row(
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:back")
        )

        await callback.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("admin:wh:toggle:"))
@admin_only
@log_errors
async def toggle_webhook_status(callback: CallbackQuery):
    """Toggle webhook active/inactive"""
    webhook_id = int(callback.data.split(":")[3])
    await callback.answer()

    async with async_session_maker() as session:
        webhook_service = WebhookService(session)
        webhook = await webhook_service.toggle_webhook(webhook_id)
        if webhook:
            status = ADMIN["course_toggled_active"] if webhook.is_active else ADMIN["course_toggled_inactive"]
            await callback.message.answer(ADMIN["webhook_toggled"].format(name=webhook.name, status=status))

    await list_webhooks(callback)


@router.callback_query(F.data.startswith("admin:wh:delete:"))
@admin_only
@log_errors
async def delete_webhook_endpoint(callback: CallbackQuery):
    """Delete a webhook"""
    webhook_id = int(callback.data.split(":")[3])
    await callback.answer()

    async with async_session_maker() as session:
        webhook_service = WebhookService(session)
        await webhook_service.delete_webhook(webhook_id)

    await callback.message.answer(ADMIN["webhook_deleted"])
    await list_webhooks(callback)


@router.callback_query(F.data == "admin:webhook:test")
@admin_only
@log_errors
async def test_webhooks(callback: CallbackQuery):
    """Test all webhooks"""
    await callback.answer(ADMIN["webhook_testing"])

    async with async_session_maker() as session:
        webhook_service = WebhookService(session)
        webhooks = await webhook_service.get_active_webhooks()

        if not webhooks:
            await callback.message.edit_text(
                ADMIN["webhook_list_empty"],
                reply_markup=get_webhook_keyboard()
            )
            return

        text = ADMIN["webhook_test_header"] + "\n\n"
        for wh in webhooks:
            success, detail = await webhook_service.test_webhook(wh.id)
            status = "✅" if success else "❌"
            text += f"{status} {wh.name}: {detail}\n"

        await callback.message.edit_text(text, reply_markup=get_webhook_keyboard())


# ===========================
# SETTINGS & BACK
# ===========================

@router.message(F.text == ADMIN_BUTTONS["settings"])
@admin_only
@log_errors
async def settings_menu(message: Message):
    """Show settings"""
    text = (
        ADMIN["settings_header"] + "\n\n"
        + ADMIN["settings_token"].format(token='...' + config.BOT_TOKEN[-10:] if config.BOT_TOKEN else ADMIN["settings_token_not_set"]) + "\n"
        + ADMIN["settings_admins"].format(count=len(config.ADMIN_USER_IDS)) + "\n"
        + ADMIN["settings_db"].format(host=f"{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}") + "\n"
        + ADMIN["settings_reminder_days"].format(days=config.REMINDER_DAYS) + "\n"
        + ADMIN["settings_broadcast_rate"].format(rate=config.BROADCAST_RATE_LIMIT) + "\n"
        + ADMIN["settings_log_level"].format(level=config.LOG_LEVEL) + "\n"
    )
    await message.answer(text)


@router.callback_query(F.data == "admin:back")
async def go_back(callback: CallbackQuery, state: FSMContext):
    """Go back to admin main menu"""
    await state.clear()
    await callback.answer()
    await callback.message.answer(
        ADMIN["panel_header"],
        reply_markup=get_admin_main_menu()
    )


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    """No operation - for pagination indicator"""
    await callback.answer()
