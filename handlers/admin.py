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

logger = logging.getLogger(__name__)
router = Router()


def _format_delay(minutes: int) -> str:
    """Format delay minutes into human-readable Persian text"""
    if minutes <= 0:
        return "فوری"
    if minutes < 60:
        return f"{minutes} دقیقه"
    hours = minutes // 60
    remaining_min = minutes % 60
    if hours < 24:
        if remaining_min > 0:
            return f"{hours} ساعت و {remaining_min} دقیقه"
        return f"{hours} ساعت"
    days = hours // 24
    remaining_hours = hours % 24
    parts = [f"{days} روز"]
    if remaining_hours > 0:
        parts.append(f"{remaining_hours} ساعت")
    if remaining_min > 0:
        parts.append(f"{remaining_min} دقیقه")
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
        "🔧 <b>پنل مدیریت</b>\n\n"
        "از منوی زیر گزینه مورد نظر را انتخاب کنید:",
        reply_markup=get_admin_main_menu()
    )


# ===========================
# DASHBOARD
# ===========================

@router.message(F.text == "📊 داشبورد")
@admin_only
@log_errors
async def show_dashboard(message: Message):
    """Show admin dashboard with enhanced analytics"""
    async with async_session_maker() as session:
        analytics = AnalyticsService(session)
        stats = await analytics.get_dashboard_stats()

        text = (
            "📊 <b>داشبورد</b>\n\n"
            f"👥 کل کاربران: {format_number(stats['total_users'])}\n"
            f"✅ کاربران فعال: {format_number(stats['active_users'])}\n"
            f"🎓 تکمیل کننده‌ها: {format_number(stats['completed_all'])}\n"
            f"📈 نرخ تکمیل: {stats['completion_rate']}%\n\n"
            f"📖 دوره‌ها: {format_number(stats['total_courses'])}\n"
            f"📚 درس‌ها: {format_number(stats['total_lessons'])}\n\n"
            f"🕐 <b>فعالیت:</b>\n"
            f"  🔥 ۲۴ ساعت اخیر: {format_number(stats['active_24h'])}\n"
            f"  📅 ۷ روز اخیر: {format_number(stats['active_7d'])}\n\n"
            f"📅 <b>امروز:</b>\n"
            f"  🆕 کاربران جدید: {format_number(stats['today_new_users'])}\n"
            f"  ✅ درس‌های تکمیل شده: {format_number(stats['today_completions'])}\n\n"
            f"📅 <b>این هفته:</b>\n"
            f"  🆕 کاربران جدید: {format_number(stats['week_new_users'])}"
        )

        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="📊 فانل تحلیل", callback_data="admin:analytics:funnel"),
            InlineKeyboardButton(text="📈 آمار دوره‌ها", callback_data="admin:analytics:courses")
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
            await callback.message.answer("📭 داده‌ای برای تحلیل وجود ندارد.")
            return

        text = "📊 <b>تحلیل فانل (ریزش درس به درس)</b>\n\n"
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

        text += "\n⚠️ = ریزش بالا (>30%)  ⚡ = ریزش متوسط (>15%)"

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

        text = "📈 <b>آمار دوره‌ها</b>\n\n"
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

@router.message(F.text == "📚 درس‌ها")
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
            InlineKeyboardButton(text="➕ ساخت دوره جدید", callback_data="admin:course:add")
        )
        builder.row(
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:back")
        )

        await message.answer(
            "📚 <b>مدیریت دوره‌ها و درس‌ها</b>\n\n"
            "یک دوره را انتخاب کنید یا دوره جدید بسازید:",
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
            InlineKeyboardButton(text="➕ ساخت دوره جدید", callback_data="admin:course:add")
        )
        builder.row(
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:back")
        )

        try:
            await callback.message.edit_text(
                "📚 <b>مدیریت دوره‌ها و درس‌ها</b>\n\n"
                "یک دوره را انتخاب کنید یا دوره جدید بسازید:",
                reply_markup=builder.as_markup()
            )
        except TelegramBadRequest:
            await callback.message.answer(
                "📚 <b>مدیریت دوره‌ها و درس‌ها</b>\n\n"
                "یک دوره را انتخاب کنید یا دوره جدید بسازید:",
                reply_markup=builder.as_markup()
            )


@router.callback_query(F.data == "admin:course:add")
@admin_only
@log_errors
async def add_course_start(callback: CallbackQuery, state: FSMContext):
    """Start creating a new course"""
    await callback.answer()
    await callback.message.answer(
        "📝 <b>ساخت دوره جدید</b>\n\nعنوان دوره را وارد کنید:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_course_title)


@router.message(AdminStates.waiting_course_title)
async def process_course_title(message: Message, state: FSMContext):
    """Process course title"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("❌ لغو شد.", reply_markup=get_admin_main_menu())
        return

    await state.update_data(course_title=message.text)
    await message.answer(
        "📝 توضیحات دوره را وارد کنید (یا /skip):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_course_description)


@router.message(AdminStates.waiting_course_description)
async def process_course_description(message: Message, state: FSMContext):
    """Process course description and save"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("❌ لغو شد.", reply_markup=get_admin_main_menu())
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
            f"✅ دوره «{course.title}» با موفقیت ساخته شد!\n\n"
            "حالا می‌توانید درس‌ها را به این دوره اضافه کنید.",
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
            await callback.message.answer("❌ دوره یافت نشد.")
            return

        lessons = await lesson_service.get_all_lessons(active_only=False, course_id=course_id)
        stats = await lesson_service.get_course_stats(course_id)

        status = "✅ فعال" if course.is_active else "❌ غیرفعال"
        text = (
            f"📚 <b>{course.title}</b>\n"
            f"📝 {course.description or '---'}\n"
            f"📊 وضعیت: {status}\n\n"
            f"📈 <b>آمار:</b>\n"
            f"  📖 تعداد درس: {stats['total_lessons']}\n"
            f"  👥 ثبت‌نام شده: {stats['enrolled']}\n"
            f"  🎓 تکمیل کرده: {stats['completed']}\n"
            f"  📊 نرخ تکمیل: {stats['completion_rate']}%\n\n"
        )

        if lessons:
            text += "<b>درس‌ها:</b>\n"
            for l in lessons[:15]:
                ls = "✅" if l.is_active else "❌"
                text += f"  {ls} {l.order}. {l.title}\n"
            if len(lessons) > 15:
                text += f"  ... و {len(lessons) - 15} درس دیگر\n"

        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="➕ افزودن درس", callback_data=f"admin:lesson:add:{course_id}"),
            InlineKeyboardButton(text="📋 لیست درس‌ها", callback_data=f"admin:lesson:list:{course_id}")
        )
        builder.row(
            InlineKeyboardButton(text="✏️ ویرایش عنوان", callback_data=f"admin:course:edit_title:{course_id}"),
            InlineKeyboardButton(text="🔄 تغییر وضعیت", callback_data=f"admin:course:toggle:{course_id}")
        )
        builder.row(
            InlineKeyboardButton(text="🗑 حذف دوره", callback_data=f"admin:course:delete:{course_id}")
        )
        builder.row(
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:courses")
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
            status = "فعال ✅" if course.is_active else "غیرفعال ❌"
            await callback.message.answer(
                f"🔄 دوره «{course.title}» {status} شد.",
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
            InlineKeyboardButton(text="✅ بله، حذف شود", callback_data=f"admin:course:dodel:{course_id}"),
            InlineKeyboardButton(text="❌ خیر", callback_data=f"admin:course:view:{course_id}")
        )

        await callback.message.edit_text(
            f"⚠️ آیا مطمئنید که می‌خواهید دوره «{course.title}» و تمام درس‌هایش را حذف کنید؟",
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
        await callback.message.answer("✅ دوره حذف شد.", reply_markup=get_admin_main_menu())


@router.callback_query(F.data.startswith("admin:course:edit_title:"))
@admin_only
@log_errors
async def edit_course_title_start(callback: CallbackQuery, state: FSMContext):
    """Start editing course title"""
    course_id = int(callback.data.split(":")[3])
    await callback.answer()
    await state.update_data(editing_course_id=course_id)
    await callback.message.answer(
        "✏️ عنوان جدید دوره را وارد کنید:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_course_edit_title)


@router.message(AdminStates.waiting_course_edit_title)
async def process_course_edit_title(message: Message, state: FSMContext):
    """Process course title edit"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("❌ لغو شد.", reply_markup=get_admin_main_menu())
        return

    data = await state.get_data()
    await state.clear()

    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        course = await lesson_service.update_course(data["editing_course_id"], title=message.text)
        if course:
            await message.answer(f"✅ عنوان دوره به «{course.title}» تغییر یافت.", reply_markup=get_admin_main_menu())


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
            InlineKeyboardButton(text="➕ ساخت دوره جدید", callback_data="admin:course:add")
        )
        builder.row(
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:back")
        )

        try:
            await callback.message.edit_text(
                "📚 <b>مدیریت دوره‌ها و درس‌ها</b>\n\nیک دوره انتخاب کنید:",
                reply_markup=builder.as_markup()
            )
        except TelegramBadRequest:
            await callback.message.answer(
                "📚 <b>مدیریت دوره‌ها و درس‌ها</b>\n\nیک دوره انتخاب کنید:",
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
        "📝 <b>افزودن درس جدید</b>\n\nعنوان درس را وارد کنید:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_lesson_title)


@router.message(AdminStates.waiting_lesson_title)
async def process_lesson_title(message: Message, state: FSMContext):
    """Process lesson title"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("❌ لغو شد.", reply_markup=get_admin_main_menu())
        return

    await state.update_data(lesson_title=message.text)

    # Ask for content type
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📝 متن", callback_data="lesson_type:text"),
        InlineKeyboardButton(text="🎥 ویدیو", callback_data="lesson_type:video"),
    )
    builder.row(
        InlineKeyboardButton(text="🎵 صوت", callback_data="lesson_type:audio"),
        InlineKeyboardButton(text="🎤 ویس", callback_data="lesson_type:voice"),
    )
    builder.row(
        InlineKeyboardButton(text="📄 فایل", callback_data="lesson_type:document"),
        InlineKeyboardButton(text="🖼 تصویر", callback_data="lesson_type:photo"),
    )
    builder.row(
        InlineKeyboardButton(text="📋 فرم", callback_data="lesson_type:form"),
    )

    await message.answer(
        "نوع محتوای درس را انتخاب کنید:",
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
            "📋 <b>ساخت فرم</b>\n\n"
            "عنوان فیلد اول را وارد کنید:\n"
            "مثال: نام و نام خانوادگی، شهر، نظر شما",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(AdminStates.waiting_form_field_label)
        return

    type_prompts = {
        "text": "📝 متن درس را ارسال کنید:",
        "video": "🎥 ویدیو درس را ارسال کنید (فایل ویدیو):",
        "audio": "🎵 فایل صوتی یا ویس درس را ارسال کنید:",
        "voice": "🎤 ویس درس را ضبط و ارسال کنید (یا فایل صوتی بفرستید):",
        "document": "📄 فایل درس را ارسال کنید:",
        "photo": "🖼 تصویر درس را ارسال کنید:",
    }

    await callback.message.answer(
        type_prompts.get(content_type, "محتوای درس را ارسال کنید:"),
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_lesson_content)


@router.message(AdminStates.waiting_lesson_content)
async def process_lesson_content(message: Message, state: FSMContext):
    """Process lesson content"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("❌ لغو شد.", reply_markup=get_admin_main_menu())
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
            await message.answer("⚠️ لطفاً فایل صوتی یا ویس ارسال کنید.")
            return
    elif content_type == "voice":
        if message.voice:
            file_id = message.voice.file_id
        elif message.audio:
            file_id = message.audio.file_id
            content_type = "audio"
        else:
            await message.answer("⚠️ لطفاً ویس ضبط کنید یا فایل صوتی ارسال کنید.")
            return
    elif content_type == "document" and message.document:
        file_id = message.document.file_id
    elif content_type == "photo" and message.photo:
        file_id = message.photo[-1].file_id  # Largest photo
    else:
        await message.answer("⚠️ لطفاً نوع محتوای صحیح ارسال کنید.")
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
        InlineKeyboardButton(text="➕ اضافه کردن محتوای دیگر", callback_data="lesson_content:more")
    )
    builder.row(
        InlineKeyboardButton(text="✅ ادامه", callback_data="lesson_content:done")
    )

    await message.answer(
        f"✅ محتوا اضافه شد!\n\n{summary}\n"
        "آیا می‌خواهید محتوای دیگری اضافه کنید؟",
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
        InlineKeyboardButton(text="📝 متن", callback_data="lesson_type:text"),
        InlineKeyboardButton(text="🎥 ویدیو", callback_data="lesson_type:video"),
    )
    builder.row(
        InlineKeyboardButton(text="🎵 صوت", callback_data="lesson_type:audio"),
        InlineKeyboardButton(text="🎤 ویس", callback_data="lesson_type:voice"),
    )
    builder.row(
        InlineKeyboardButton(text="📄 فایل", callback_data="lesson_type:document"),
        InlineKeyboardButton(text="🖼 تصویر", callback_data="lesson_type:photo"),
    )

    await callback.message.answer(
        "نوع محتوای بعدی را انتخاب کنید:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(AdminStates.waiting_lesson_content_type)


@router.callback_query(F.data == "lesson_content:done")
@admin_only
async def lesson_content_done(callback: CallbackQuery, state: FSMContext):
    """Done adding content, proceed to description"""
    await callback.answer()

    await callback.message.answer(
        "📝 توضیحات درس را وارد کنید (یا /skip برای رد شدن):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_lesson_description)


@router.message(AdminStates.waiting_lesson_description)
async def process_lesson_description(message: Message, state: FSMContext):
    """Process lesson description"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("❌ لغو شد.", reply_markup=get_admin_main_menu())
        return

    description = None if message.text == "/skip" else message.text
    await state.update_data(lesson_description=description)

    await message.answer(
        "⏱ <b>فاصله زمانی تا درس بعدی</b>\n\n"
        "بعد از تایید این درس، چند دقیقه بعد درس بعدی ارسال شود؟\n"
        "عدد را به دقیقه وارد کنید (مثلاً: 60 برای یک ساعت، 1440 برای یک روز)\n"
        "یا 0 برای ارسال فوری:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_lesson_delay)


@router.message(AdminStates.waiting_lesson_delay)
async def process_lesson_delay(message: Message, state: FSMContext):
    """Process lesson delay in minutes"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("❌ لغو شد.", reply_markup=get_admin_main_menu())
        return

    try:
        delay_minutes = int(message.text)
        if delay_minutes < 0:
            raise ValueError
    except (ValueError, TypeError):
        await message.answer("⚠️ لطفاً یک عدد صحیح مثبت وارد کنید (مثلاً: 0، 30، 60، 1440):")
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
            InlineKeyboardButton(text="📝 افزودن آزمون", callback_data=f"admin:quiz:new:{lesson.id}")
        )
        builder.row(
            InlineKeyboardButton(text="✅ بازگشت به پنل", callback_data="admin:back")
        )

        await message.answer(
            f"✅ درس «{lesson.title}» با موفقیت اضافه شد!\n"
            f"📋 شماره: {lesson.order}\n"
            f"{content_info}\n"
            f"⏱ فاصله: {delay_text}\n\n"
            "اگر می‌خواهید آزمون هم اضافه کنید:",
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
                InlineKeyboardButton(text="➕ افزودن درس", callback_data=f"admin:lesson:add:{course_id}")
            )
            builder.row(
                InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"admin:course:view:{course_id}")
            )
            await callback.message.edit_text(
                f"📭 دوره «{course_title}» هنوز درسی ندارد.",
                reply_markup=builder.as_markup()
            )
            return

        await callback.message.edit_text(
            f"📚 <b>درس‌های دوره «{course_title}»</b> ({len(lessons)} درس)\n\n"
            "برای مدیریت روی هر درس کلیک کنید:",
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
            await callback.message.edit_text("❌ درس یافت نشد.")
            return

        stats = await lesson_service.get_lesson_stats(lesson_id)

        status = "✅ فعال" if lesson.is_active else "❌ غیرفعال"
        delay_text = _format_delay(lesson.delay_hours)

        # Content info
        if lesson.contents and len(lesson.contents) > 1:
            type_labels = {
                "text": "متن", "video": "ویدیو", "audio": "صوت",
                "voice": "ویس", "document": "فایل", "photo": "تصویر",
            }
            parts = [type_labels.get(b.get("type", ""), b.get("type", "")) for b in lesson.contents]
            content_info = f"{len(lesson.contents)} بخش ({', '.join(parts)})"
        else:
            content_info = lesson.content_type.value

        text = (
            f"📚 <b>درس {lesson.order}: {lesson.title}</b>\n\n"
            f"📦 محتوا: {content_info}\n"
            f"📌 وضعیت: {status}\n"
            f"⏱ فاصله تا درس بعد: {delay_text}\n"
            f"📝 توضیحات: {truncate_text(lesson.description or 'ندارد', 200)}\n\n"
            f"📊 <b>آمار:</b>\n"
            f"  👁 شروع شده: {stats['started']}\n"
            f"  ✅ تکمیل شده: {stats['completed']}\n"
            f"  📈 نرخ تکمیل: {stats['completion_rate']}%"
        )

        if lesson.cta_text:
            text += f"\n\n🔗 CTA: {lesson.cta_text} → {lesson.cta_url or '-'}"

        if lesson.quiz_data and lesson.quiz_data.get("questions"):
            text += f"\n\n📝 آزمون: {len(lesson.quiz_data['questions'])} سوال (حداقل {lesson.quiz_data.get('passing_score', 100)}%)"

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
        InlineKeyboardButton(text="📝 عنوان", callback_data=f"admin:lesson:editf:title:{lesson_id}"),
        InlineKeyboardButton(text="📄 توضیحات", callback_data=f"admin:lesson:editf:description:{lesson_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="⏱ فاصله زمانی", callback_data=f"admin:lesson:editf:delay_hours:{lesson_id}"),
        InlineKeyboardButton(text="🔄 محتوا", callback_data=f"admin:lesson:editf:content:{lesson_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🔗 متن CTA", callback_data=f"admin:lesson:editf:cta_text:{lesson_id}"),
        InlineKeyboardButton(text="🌐 لینک CTA", callback_data=f"admin:lesson:editf:cta_url:{lesson_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"admin:lesson:view:{lesson_id}")
    )

    await callback.message.edit_text(
        "✏️ <b>ویرایش درس</b>\n\nکدام فیلد را می‌خواهید ویرایش کنید؟",
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
            InlineKeyboardButton(text="📝 متن", callback_data="edit_ctype:text"),
            InlineKeyboardButton(text="🎥 ویدیو", callback_data="edit_ctype:video"),
        )
        builder.row(
            InlineKeyboardButton(text="🎵 صوت", callback_data="edit_ctype:audio"),
            InlineKeyboardButton(text="🎤 ویس", callback_data="edit_ctype:voice"),
        )
        builder.row(
            InlineKeyboardButton(text="📄 فایل", callback_data="edit_ctype:document"),
            InlineKeyboardButton(text="🖼 تصویر", callback_data="edit_ctype:photo"),
        )

        await callback.message.edit_text(
            "🔄 <b>ویرایش محتوای درس</b>\n\n"
            "محتوای قبلی جایگزین خواهد شد.\n"
            "نوع اولین محتوا را انتخاب کنید:",
            reply_markup=builder.as_markup()
        )
        return

    field_prompts = {
        "title": "📝 عنوان جدید درس را وارد کنید:",
        "description": "📄 توضیحات جدید را وارد کنید (یا /skip برای حذف):",
        "delay_hours": "⏱ فاصله زمانی جدید (به دقیقه) را وارد کنید (مثلاً: 0، 30، 60، 1440):",
        "cta_text": "🔗 متن دکمه CTA جدید را وارد کنید (یا /skip برای حذف):",
        "cta_url": "🌐 لینک CTA جدید را وارد کنید (یا /skip برای حذف):",
    }

    await callback.message.edit_text(
        field_prompts.get(field_name, "مقدار جدید را وارد کنید:"),
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
                f"✅ درس «{lesson.title}» با موفقیت ویرایش شد.",
                reply_markup=get_admin_main_menu()
            )
        else:
            await message.answer("❌ خطا در ویرایش درس.", reply_markup=get_admin_main_menu())


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

    type_prompts = {
        "text": "📝 متن را ارسال کنید:",
        "video": "🎥 ویدیو را ارسال کنید:",
        "audio": "🎵 فایل صوتی را ارسال کنید:",
        "voice": "🎤 ویس را ضبط و ارسال کنید:",
        "document": "📄 فایل را ارسال کنید:",
        "photo": "🖼 تصویر را ارسال کنید:",
    }

    await callback.message.answer(
        type_prompts.get(content_type, "محتوا را ارسال کنید:"),
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_lesson_edit_content)


@router.message(AdminStates.waiting_lesson_edit_content)
async def process_edit_content(message: Message, state: FSMContext):
    """Process content block during edit"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("❌ لغو شد.", reply_markup=get_admin_main_menu())
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
            await message.answer("⚠️ لطفاً فایل صوتی ارسال کنید.")
            return
    elif content_type == "voice":
        if message.voice:
            file_id = message.voice.file_id
        elif message.audio:
            file_id = message.audio.file_id
            content_type = "audio"
        else:
            await message.answer("⚠️ لطفاً ویس ارسال کنید.")
            return
    elif content_type == "document" and message.document:
        file_id = message.document.file_id
    elif content_type == "photo" and message.photo:
        file_id = message.photo[-1].file_id
    else:
        await message.answer("⚠️ لطفاً محتوای صحیح ارسال کنید.")
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
        InlineKeyboardButton(text="➕ اضافه کردن محتوای دیگر", callback_data="edit_content:more")
    )
    builder.row(
        InlineKeyboardButton(text="✅ ذخیره", callback_data="edit_content:done")
    )

    await message.answer(
        f"✅ محتوا اضافه شد!\n\n{summary}\n"
        "آیا می‌خواهید محتوای دیگری اضافه کنید؟",
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
        InlineKeyboardButton(text="📝 متن", callback_data="edit_ctype:text"),
        InlineKeyboardButton(text="🎥 ویدیو", callback_data="edit_ctype:video"),
    )
    builder.row(
        InlineKeyboardButton(text="🎵 صوت", callback_data="edit_ctype:audio"),
        InlineKeyboardButton(text="🎤 ویس", callback_data="edit_ctype:voice"),
    )
    builder.row(
        InlineKeyboardButton(text="📄 فایل", callback_data="edit_ctype:document"),
        InlineKeyboardButton(text="🖼 تصویر", callback_data="edit_ctype:photo"),
    )

    await callback.message.answer(
        "نوع محتوای بعدی را انتخاب کنید:",
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
        await callback.message.answer("⚠️ هیچ محتوایی اضافه نشد.", reply_markup=get_admin_main_menu())
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
            await callback.message.answer("❌ درس یافت نشد.", reply_markup=get_admin_main_menu())
            return

        # Update lesson
        lesson.content_type = primary_type
        lesson.file_id = first_block.get("file_id")
        lesson.text_content = first_block.get("text")
        lesson.contents = lesson_contents
        await session.commit()

        await callback.message.answer(
            f"✅ محتوای درس «{lesson.title}» با {len(lesson_contents)} بخش ویرایش شد.",
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
                "⚠️ حداقل ۲ درس برای تغییر ترتیب نیاز است.",
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
            "🔄 <b>تغییر ترتیب درس‌ها</b>\n\nبا دکمه‌های ⬆️ و ⬇️ ترتیب را تغییر دهید:",
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
            status = "فعال ✅" if lesson.is_active else "غیرفعال ❌"
            await callback.answer(f"وضعیت درس: {status}")
            # Refresh view
            await view_lesson(callback, lesson_id=lesson_id)
        else:
            await callback.answer("❌ خطا در تغییر وضعیت")


@router.callback_query(F.data.startswith("admin:lesson:delete:"))
@admin_only
@log_errors
async def delete_lesson_confirm(callback: CallbackQuery):
    """Confirm lesson deletion"""
    lesson_id = callback.data.split(":")[3]
    await callback.answer()
    await callback.message.edit_text(
        "⚠️ آیا از حذف این درس اطمینان دارید؟\n"
        "این عمل غیرقابل بازگشت است.",
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
                "✅ درس با موفقیت حذف شد.",
                reply_markup=get_back_keyboard()
            )
        else:
            await callback.message.edit_text("❌ خطا در حذف درس.")


@router.callback_query(F.data.startswith("cancel:delete_lesson:"))
@admin_only
@log_errors
async def cancel_delete_lesson(callback: CallbackQuery):
    """Cancel lesson deletion"""
    await callback.answer("لغو شد")
    lesson_id = int(callback.data.split(":")[2])
    # Go back to lesson view
    await view_lesson(callback, lesson_id=lesson_id)


# ===========================
# USER MANAGEMENT
# ===========================

@router.message(F.text == "👥 کاربران")
@admin_only
@log_errors
async def user_management_menu(message: Message):
    """Show user management menu"""
    await message.answer(
        "👥 <b>مدیریت کاربران</b>\n\nیک گزینه را انتخاب کنید:",
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
                "📭 کاربری یافت نشد.",
                reply_markup=get_user_management_keyboard()
            )
            return

        total_pages = (total + page_size - 1) // page_size
        text = f"👥 <b>کاربران</b> ({format_number(total)} نفر)\n\n"

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
            InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="noop")
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
            await callback.message.edit_text("❌ کاربر یافت نشد.")
            return

        user = stats["user"]
        status = "✅ فعال" if user.is_active else "❌ غیرفعال"
        name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "-"

        text = (
            f"👤 <b>اطلاعات کاربر</b>\n\n"
            f"📛 نام: {name}\n"
            f"👤 یوزرنیم: @{user.username or '-'}\n"
            f"🆔 آیدی: <code>{user.telegram_user_id}</code>\n"
            f"📌 وضعیت: {status}\n"
            f"🎓 تکمیل دوره: {'بله ✅' if user.is_completed else 'خیر ❌'}\n\n"
            f"📊 <b>آمار:</b>\n"
            f"  ✅ درس‌های تکمیل شده: {stats['completed_lessons']}/{stats['total_lessons']}\n"
            f"  📈 پیشرفت: {stats['progress_percent']}%\n"
            f"  ⏱ زمان صرف شده: {format_duration(stats['total_time_spent'])}\n\n"
            f"🏷 تگ‌ها: {', '.join(stats['tags']) if stats['tags'] else '-'}\n"
            f"📅 تاریخ ثبت‌نام: {stats['registered_at'].strftime('%Y/%m/%d') if stats['registered_at'] else '-'}\n"
        )

        # Show registration data
        if user.registration_data:
            text += "\n📝 <b>اطلاعات ثبت‌نام:</b>\n"
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
        "💬 پیام خود را ارسال کنید:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_private_message)


@router.message(AdminStates.waiting_private_message)
async def send_private_message(message: Message, state: FSMContext, bot: Bot):
    """Send private message to user"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("❌ لغو شد.", reply_markup=get_admin_main_menu())
        return

    data = await state.get_data()
    user_id = data["target_user_id"]
    await state.clear()

    async with async_session_maker() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_id(user_id)

        if not user:
            await message.answer("❌ کاربر یافت نشد.", reply_markup=get_admin_main_menu())
            return

        broadcast_service = BroadcastService(session, bot)
        success = await broadcast_service.send_private_message(
            user.telegram_user_id, message.text
        )

        if success:
            await message.answer("✅ پیام با موفقیت ارسال شد.", reply_markup=get_admin_main_menu())
        else:
            await message.answer("❌ خطا در ارسال پیام.", reply_markup=get_admin_main_menu())


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
            await callback.message.edit_text("🚫 کاربر بلاک شد.", reply_markup=get_back_keyboard())
        elif user:
            await user_service.unblock_user(user_id)
            await callback.message.edit_text("✅ کاربر آنبلاک شد.", reply_markup=get_back_keyboard())


@router.callback_query(F.data.startswith("admin:user:delete:"))
@admin_only
@log_errors
async def delete_user_confirm(callback: CallbackQuery):
    """Confirm user deletion"""
    user_id = callback.data.split(":")[3]
    await callback.answer()
    await callback.message.edit_text(
        "⚠️ آیا از حذف این کاربر اطمینان دارید؟",
        reply_markup=get_confirm_keyboard("delete_user", user_id)
    )


@router.callback_query(F.data.startswith("cancel:delete_user:"))
@admin_only
@log_errors
async def cancel_delete_user(callback: CallbackQuery):
    """Cancel user deletion"""
    await callback.answer("لغو شد")
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
            await callback.message.edit_text("✅ کاربر حذف شد.", reply_markup=get_back_keyboard())
        else:
            await callback.message.edit_text("❌ خطا در حذف کاربر.")


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
            await callback.message.edit_text("✅ پیشرفت کاربر ریست شد.", reply_markup=get_back_keyboard())
        else:
            await callback.message.edit_text("❌ خطا در ریست پیشرفت.")


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
        f"🏷 <b>مدیریت تگ‌ها</b>\n\n"
        f"تگ‌های فعلی: {', '.join(current_tags) if current_tags else 'ندارد'}\n\n"
        "تگ‌ها را با کاما جدا کرده و ارسال کنید:\n"
        "مثال: vip, active, campaign1\n\n"
        "برای حذف همه تگ‌ها عبارت 'clear' را ارسال کنید.",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_tag_input)


@router.message(AdminStates.waiting_tag_input)
async def process_tags(message: Message, state: FSMContext):
    """Process tag input"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("❌ لغو شد.", reply_markup=get_admin_main_menu())
        return

    data = await state.get_data()
    user_id = data["target_user_id"]
    await state.clear()

    async with async_session_maker() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_id(user_id)

        if not user:
            await message.answer("❌ کاربر یافت نشد.", reply_markup=get_admin_main_menu())
            return

        if message.text.strip().lower() == "clear":
            user.tags = []
        else:
            tags = [t.strip() for t in message.text.split(",") if t.strip()]
            user.tags = tags

        await session.commit()
        await message.answer(
            f"✅ تگ‌ها با موفقیت ب‌روزرسانی شد.\n"
            f"🏷 تگ‌ها: {', '.join(user.tags) if user.tags else 'ندارد'}",
            reply_markup=get_admin_main_menu()
        )


@router.callback_query(F.data == "admin:users:search")
@admin_only
@log_errors
async def start_user_search(callback: CallbackQuery, state: FSMContext):
    """Start user search"""
    await callback.answer()
    await callback.message.answer(
        "🔍 نام، یوزرنیم یا شماره کاربر را وارد کنید:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_user_search)


@router.message(AdminStates.waiting_user_search)
async def process_user_search(message: Message, state: FSMContext):
    """Process user search"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("❌ لغو شد.", reply_markup=get_admin_main_menu())
        return

    await state.clear()

    async with async_session_maker() as session:
        user_service = UserService(session)
        users, total = await user_service.search_users(message.text)

        if not users:
            await message.answer("📭 کاربری یافت نشد.", reply_markup=get_admin_main_menu())
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
            f"🔍 نتایج جستجو ({total} نفر):",
            reply_markup=builder.as_markup()
        )


@router.callback_query(F.data == "admin:users:export")
@admin_only
@log_errors
async def export_users(callback: CallbackQuery):
    """Export users to Excel"""
    await callback.answer("در حال آماده‌سازی فایل...")

    async with async_session_maker() as session:
        export_service = ExportService(session)
        excel_file = await export_service.export_users_to_excel()

        await callback.message.answer_document(
            document=BufferedInputFile(
                excel_file.read(),
                filename=f"users_export.xlsx"
            ),
            caption="📥 فایل اکسپورت کاربران"
        )


# ===========================
# BROADCAST
# ===========================

@router.message(F.text == "📢 ارسال پیام")
@admin_only
@log_errors
async def broadcast_menu(message: Message):
    """Show broadcast menu"""
    await message.answer(
        "📢 <b>ارسال پیام</b>\n\nمخاطبان را انتخاب کنید:",
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
        "📝 پیام خود را ارسال کنید:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_broadcast_message)


@router.message(AdminStates.waiting_broadcast_message)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
    """Process and send broadcast"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("❌ لغو شد.", reply_markup=get_admin_main_menu())
        return

    data = await state.get_data()
    target = data["broadcast_target"]
    await state.clear()

    await message.answer("📡 در حال ارسال پیام...")

    async with async_session_maker() as session:
        broadcast_service = BroadcastService(session, bot)
        result = await broadcast_service.broadcast_message(
            admin_id=message.from_user.id,
            message=message.text,
            target=target,
        )

        await message.answer(
            f"📢 <b>نتیجه ارسال پیام</b>\n\n"
            f"👥 کل: {format_number(result.total_users)}\n"
            f"✅ موفق: {format_number(result.success_count)}\n"
            f"❌ ناموفق: {format_number(result.failed_count)}",
            reply_markup=get_admin_main_menu()
        )


# ===========================
# REGISTRATION FIELDS
# ===========================

@router.message(F.text == "📝 فیلدهای ثبت‌نام")
@admin_only
@log_errors
async def registration_fields_menu(message: Message):
    """Show registration fields menu"""
    await message.answer(
        "📝 <b>مدیریت فیلدهای ثبت‌نام</b>\n\nیک گزینه را انتخاب کنید:",
        reply_markup=get_registration_fields_keyboard()
    )


@router.callback_query(F.data == "admin:field:add")
@admin_only
@log_errors
async def add_field_start(callback: CallbackQuery, state: FSMContext):
    """Start adding a registration field"""
    await callback.answer()
    await callback.message.answer(
        "📝 نام فیلد (شناسه انگلیسی) را وارد کنید:\nمثال: phone, city, age",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_field_name)


@router.message(AdminStates.waiting_field_name)
async def process_field_name(message: Message, state: FSMContext):
    """Process field name"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("❌ لغو شد.", reply_markup=get_admin_main_menu())
        return

    await state.update_data(field_name=message.text.strip().lower().replace(" ", "_"))
    await message.answer(
        "📝 عنوان فیلد (فارسی) را وارد کنید:\nمثال: شماره تلفن، شهر، سن"
    )
    await state.set_state(AdminStates.waiting_field_label)


@router.message(AdminStates.waiting_field_label)
async def process_field_label(message: Message, state: FSMContext):
    """Process field label"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("❌ لغو شد.", reply_markup=get_admin_main_menu())
        return

    await state.update_data(field_label=message.text.strip())
    await message.answer(
        "نوع فیلد را انتخاب کنید:",
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
            "گزینه‌ها را با کاما جدا کنید:\nمثال: تهران، اصفهان، شیراز",
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
        await message.answer("❌ لغو شد.", reply_markup=get_admin_main_menu())
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
            f"✅ فیلد «{field.field_label}» با موفقیت اضافه شد!\n"
            f"📦 نوع: {data['field_type']}\n"
            f"📋 ترتیب: {field.order}",
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
                "📭 هنوز فیلدی اضافه نشده.",
                reply_markup=get_registration_fields_keyboard()
            )
            return

        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder

        text = "📝 <b>فیلدهای ثبت‌نام</b>\n\nبرای مدیریت روی هر فیلد کلیک کنید:"
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
                "⚠️ حداقل ۲ فیلد برای تغییر ترتیب نیاز است.",
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
            "🔄 <b>تغییر ترتیب فیلدها</b>\n\nبا دکمه‌های ⬆️ و ⬇️ ترتیب را تغییر دهید:",
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
    await callback.answer("لغو شد")
    await callback.message.edit_text(
        "📝 <b>مدیریت فیلدهای ثبت‌نام</b>",
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
            await callback.message.edit_text("❌ فیلد یافت نشد.")
            return

        required = "✅ بله" if field.is_required else "❌ خیر"
        active = "✅ فعال" if field.is_active else "❌ غیرفعال"
        options_text = ""
        if field.options and field.options.get("choices"):
            options_text = f"\n📋 گزینه‌ها: {', '.join(field.options['choices'])}"

        text = (
            f"📝 <b>جزئیات فیلد</b>\n\n"
            f"📛 شناسه: {field.field_name}\n"
            f"🏷 عنوان: {field.field_label}\n"
            f"📦 نوع: {field.field_type.value}\n"
            f"📌 اجباری: {required}\n"
            f"🔄 وضعیت: {active}\n"
            f"📋 ترتیب: {field.order}"
            f"{options_text}"
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
            status = "اجباری ✅" if field.is_required else "اختیاری ❌"
            await callback.answer(f"وضعیت: {status}")

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
            status = "فعال ✅" if field.is_active else "غیرفعال ❌"
            await callback.answer(f"وضعیت: {status}")

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
                "✅ فیلد حذف شد.",
                reply_markup=get_registration_fields_keyboard()
            )
        else:
            await callback.message.edit_text("❌ فیلد یافت نشد.")


@router.callback_query(F.data.startswith("admin:field:editlbl:"))
@admin_only
@log_errors
async def edit_field_label_start(callback: CallbackQuery, state: FSMContext):
    """Start editing field label"""
    field_id = int(callback.data.split(":")[3])
    await callback.answer()
    await state.update_data(edit_field_id=field_id)
    await callback.message.answer(
        "📝 عنوان جدید فیلد را وارد کنید:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_field_edit_label)


@router.message(AdminStates.waiting_field_edit_label)
async def process_field_edit_label(message: Message, state: FSMContext):
    """Process new field label"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("❌ لغو شد.", reply_markup=get_admin_main_menu())
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
                f"✅ عنوان فیلد به «{field.field_label}» تغییر کرد.",
                reply_markup=get_admin_main_menu()
            )
        else:
            await message.answer("❌ فیلد یافت نشد.", reply_markup=get_admin_main_menu())


# ===========================
# FORM BUILDER (for FORM lesson type)
# ===========================

@router.message(AdminStates.waiting_form_field_label)
async def form_builder_field_label(message: Message, state: FSMContext):
    """Process form field label in form builder"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("❌ لغو شد.", reply_markup=get_admin_main_menu())
        return

    await state.update_data(current_form_field_label=message.text.strip())

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📝 متن", callback_data="formft:text"),
        InlineKeyboardButton(text="🔢 عدد", callback_data="formft:number"),
    )
    builder.row(
        InlineKeyboardButton(text="☑️ انتخابی", callback_data="formft:select"),
    )

    await message.answer("نوع فیلد را انتخاب کنید:", reply_markup=builder.as_markup())
    await state.set_state(AdminStates.waiting_form_field_type)


@router.callback_query(F.data.startswith("formft:"), AdminStates.waiting_form_field_type)
async def form_builder_field_type(callback: CallbackQuery, state: FSMContext):
    """Process form field type"""
    field_type = callback.data.split(":")[1]
    await callback.answer()
    await state.update_data(current_form_field_type=field_type)

    if field_type == "select":
        await callback.message.answer(
            "📋 گزینه‌ها را با کاما جدا کرده وارد کنید:\nمثال: تهران، اصفهان، شیراز",
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
        await message.answer("❌ لغو شد.", reply_markup=get_admin_main_menu())
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
        InlineKeyboardButton(text="➕ افزودن فیلد دیگر", callback_data="form_add_more"),
        InlineKeyboardButton(text="✅ اتمام فرم", callback_data="form_done"),
    )

    fields_text = "\n".join([f"  {i+1}. {f['label']} ({f['type']})" for i, f in enumerate(fields)])
    await message.answer(
        f"✅ فیلد «{field['label']}» اضافه شد.\n\n"
        f"📋 فیلدهای فرم:\n{fields_text}\n\n"
        "آیا فیلد دیگری اضافه می‌کنید؟",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "form_add_more")
async def form_add_more_field(callback: CallbackQuery, state: FSMContext):
    """Add another form field"""
    await callback.answer()
    await callback.message.answer(
        "📝 عنوان فیلد بعدی را وارد کنید:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_form_field_label)


@router.callback_query(F.data == "form_done")
async def form_builder_done(callback: CallbackQuery, state: FSMContext):
    """Form building complete, continue to description"""
    await callback.answer()
    await callback.message.answer(
        "📝 توضیحات فرم را وارد کنید (یا /skip برای رد شدن):",
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
            await callback.message.edit_text("❌ درس یافت نشد.")
            return

        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder

        if lesson.quiz_data and lesson.quiz_data.get("questions"):
            # Show existing quiz
            questions = lesson.quiz_data["questions"]
            passing = lesson.quiz_data.get("passing_score", 100)
            text = (
                f"📝 <b>آزمون درس «{lesson.title}»</b>\n\n"
                f"✅ تعداد سوالات: {len(questions)}\n"
                f"📊 حداقل نمره قبولی: {passing}%\n\n"
            )
            for i, q in enumerate(questions, 1):
                correct_opt = q["options"][q["correct"]] if q["correct"] < len(q["options"]) else "?"
                text += f"<b>{i}.</b> {q['text']}\n   ✅ جواب: {correct_opt}\n"

            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="🗑 حذف آزمون", callback_data=f"admin:quiz:del:{lesson_id}"),
                InlineKeyboardButton(text="✏️ ساخت مجدد", callback_data=f"admin:quiz:new:{lesson_id}"),
            )
            builder.row(
                InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"admin:lesson:view:{lesson_id}")
            )
            await callback.message.edit_text(text, reply_markup=builder.as_markup())
        else:
            # No quiz - offer to create
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="➕ ساخت آزمون", callback_data=f"admin:quiz:new:{lesson_id}"),
            )
            builder.row(
                InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"admin:lesson:view:{lesson_id}")
            )
            await callback.message.edit_text(
                f"📝 درس «{lesson.title}» آزمون ندارد.\n\n"
                "آزمون باعث می‌شود کاربر بعد از مشاهده درس به سوالات پاسخ دهد.\n"
                "اگر نمره کافی بگیرد، درس تایید می‌شود.",
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
        "✅ آزمون حذف شد.",
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
        "📝 <b>ساخت آزمون</b>\n\n"
        "حداقل درصد قبولی را وارد کنید (مثلاً: 70 یا 100):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_quiz_passing_score)


@router.message(AdminStates.waiting_quiz_passing_score)
async def process_quiz_passing_score(message: Message, state: FSMContext):
    """Process quiz passing score"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("❌ لغو شد.", reply_markup=get_admin_main_menu())
        return

    try:
        score = int(message.text)
        if score < 1 or score > 100:
            raise ValueError
    except (ValueError, TypeError):
        await message.answer("⚠️ لطفاً عددی بین 1 تا 100 وارد کنید:")
        return

    await state.update_data(quiz_passing_score=score)
    await message.answer(
        "📝 متن سوال اول را وارد کنید:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_quiz_question_text)


@router.message(AdminStates.waiting_quiz_question_text)
async def process_quiz_question_text(message: Message, state: FSMContext):
    """Process quiz question text"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("❌ لغو شد.", reply_markup=get_admin_main_menu())
        return

    await state.update_data(current_q_text=message.text.strip())
    await message.answer(
        "📋 گزینه‌ها را هر کدام در یک خط بنویسید (حداقل ۲ گزینه):\n\n"
        "مثال:\nتهران\nاصفهان\nشیراز",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_quiz_options)


@router.message(AdminStates.waiting_quiz_options)
async def process_quiz_options(message: Message, state: FSMContext):
    """Process quiz question options"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("❌ لغو شد.", reply_markup=get_admin_main_menu())
        return

    options = [line.strip() for line in message.text.strip().split("\n") if line.strip()]
    if len(options) < 2:
        await message.answer("⚠️ حداقل ۲ گزینه وارد کنید (هر کدام در یک خط):")
        return

    await state.update_data(current_q_options=options)

    # Show options as buttons to select correct answer
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for i, opt in enumerate(options):
        builder.row(InlineKeyboardButton(text=f"✅ {opt}", callback_data=f"quizc:{i}"))

    await message.answer(
        "✅ <b>گزینه صحیح را انتخاب کنید:</b>",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("quizc:"))
async def select_correct_answer(callback: CallbackQuery, state: FSMContext):
    """Select correct answer for quiz question"""
    correct_idx = int(callback.data.split(":")[1])
    await callback.answer("✅ ثبت شد")

    data = await state.get_data()
    questions = data.get("quiz_questions", [])
    questions.append({
        "text": data["current_q_text"],
        "options": data["current_q_options"],
        "correct": correct_idx,
    })
    await state.update_data(
        quiz_questions=questions,
        current_q_text=None,
        current_q_options=None,
    )

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ سوال بعدی", callback_data="quiz_more"),
        InlineKeyboardButton(text="✅ ذخیره آزمون", callback_data="quiz_save"),
    )

    await callback.message.answer(
        f"✅ سوال {len(questions)} اضافه شد.\n"
        f"📊 تعداد سوالات: {len(questions)}\n\n"
        "آیا سوال دیگری اضافه می‌کنید؟",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "quiz_more")
async def quiz_add_more(callback: CallbackQuery, state: FSMContext):
    """Add more quiz questions"""
    await callback.answer()
    data = await state.get_data()
    q_num = len(data.get("quiz_questions", [])) + 1
    await callback.message.answer(
        f"📝 متن سوال {q_num} را وارد کنید:",
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
        await callback.message.answer("❌ آزمون بدون سوال ذخیره نشد.", reply_markup=get_admin_main_menu())
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
                f"✅ آزمون با {len(questions)} سوال و حداقل نمره {passing_score}% ذخیره شد.",
                reply_markup=get_admin_main_menu()
            )
        else:
            await callback.message.answer("❌ درس یافت نشد.", reply_markup=get_admin_main_menu())


# ===========================
# REPORTS & ANALYTICS
# ===========================

@router.message(F.text == "📈 گزارش‌ها")
@admin_only
@log_errors
async def reports_menu(message: Message):
    """Show reports menu"""
    await message.answer(
        "📈 <b>گزارش‌ها و آمار</b>\n\nدوره زمانی را انتخاب کنید:",
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

        period_labels = {"today": "امروز", "week": "هفته", "month": "ماه", "all": "کل"}

        text = (
            f"📈 <b>گزارش {period_labels.get(period, period)}</b>\n\n"
            f"🆕 کاربران جدید: {format_number(period_stats['new_users'])}\n"
            f"✅ درس‌های تکمیل شده: {format_number(period_stats['completions'])}\n"
            f"👥 کاربران فعال: {format_number(period_stats['active_users'])}\n"
        )

        if lesson_stats:
            text += "\n📚 <b>آمار درس‌ها:</b>\n"
            for ls in lesson_stats[:10]:
                text += f"  {ls['order']}. {ls['title']}: {ls['completed']} تکمیل ({ls['completion_rate']}%)\n"

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
            caption="📥 فایل اکسپورت گزارش‌ها"
        )


# ===========================
# WEBHOOK MANAGEMENT
# ===========================

@router.message(F.text == "🔗 وبهوک")
@admin_only
@log_errors
async def webhook_menu(message: Message):
    """Show webhook management menu"""
    async with async_session_maker() as session:
        webhook_service = WebhookService(session)
        webhooks = await webhook_service.get_all_webhooks()

        text = "🔗 <b>مدیریت وبهوک‌ها</b>\n\n"

        if webhooks:
            for wh in webhooks:
                status = "✅" if wh.is_active else "❌"
                text += f"{status} <b>{wh.name}</b>\n  🌐 {wh.url}\n\n"
        else:
            text += "📭 هنوز وبهوکی تعریف نشده.\n\n"

        text += (
            "📋 <b>ساختار استاندارد وبهوک:</b>\n"
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
            "<b>رویدادها:</b>\n"
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
        "🔗 <b>افزودن وبهوک جدید</b>\n\n"
        "نام وبهوک را وارد کنید (مثل: n8n, crm, zapier):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_webhook_name)


@router.message(AdminStates.waiting_webhook_name)
async def process_webhook_name(message: Message, state: FSMContext):
    """Process webhook name"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("❌ لغو شد.", reply_markup=get_admin_main_menu())
        return

    await state.update_data(webhook_name=message.text.strip())
    await message.answer("🌐 URL وبهوک را وارد کنید:")
    await state.set_state(AdminStates.waiting_webhook_url)


@router.message(AdminStates.waiting_webhook_url)
async def process_webhook_url(message: Message, state: FSMContext):
    """Process webhook URL"""
    if message.text == "❌ انصراف":
        await state.clear()
        await message.answer("❌ لغو شد.", reply_markup=get_admin_main_menu())
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
            f"✅ وبهوک «{webhook.name}» با موفقیت اضافه شد!\n"
            f"🌐 URL: {webhook.url}",
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
                "📭 هنوز وبهوکی اضافه نشده.",
                reply_markup=get_webhook_keyboard()
            )
            return

        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder

        builder = InlineKeyboardBuilder()
        text = "🔗 <b>لیست وبهوک‌ها</b>\n\n"
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
            status = "فعال ✅" if webhook.is_active else "غیرفعال ❌"
            await callback.message.answer(f"🔄 وبهوک «{webhook.name}» {status} شد.")

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

    await callback.message.answer("🗑 وبهوک حذف شد.")
    await list_webhooks(callback)


@router.callback_query(F.data == "admin:webhook:test")
@admin_only
@log_errors
async def test_webhooks(callback: CallbackQuery):
    """Test all webhooks"""
    await callback.answer("در حال تست...")

    async with async_session_maker() as session:
        webhook_service = WebhookService(session)
        webhooks = await webhook_service.get_active_webhooks()

        if not webhooks:
            await callback.message.edit_text(
                "📭 هنوز وبهوکی اضافه نشده.",
                reply_markup=get_webhook_keyboard()
            )
            return

        text = "🧪 <b>نتایج تست وبهوک‌ها</b>\n\n"
        for wh in webhooks:
            success, detail = await webhook_service.test_webhook(wh.id)
            status = "✅" if success else "❌"
            text += f"{status} {wh.name}: {detail}\n"

        await callback.message.edit_text(text, reply_markup=get_webhook_keyboard())


# ===========================
# SETTINGS & BACK
# ===========================

@router.message(F.text == "⚙️ تنظیمات")
@admin_only
@log_errors
async def settings_menu(message: Message):
    """Show settings"""
    text = (
        "⚙️ <b>تنظیمات</b>\n\n"
        f"🤖 توکن: ...{config.BOT_TOKEN[-10:] if config.BOT_TOKEN else 'تنظیم نشده'}\n"
        f"👥 ادمین‌ها: {len(config.ADMIN_USER_IDS)} نفر\n"
        f"🗄 دیتابیس: {config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}\n"
        f"💤 روز یادآوری: {config.REMINDER_DAYS} روز\n"
        f"📢 سرعت ارسال: {config.BROADCAST_RATE_LIMIT} پیام/ثانیه\n"
        f"📝 لاگ: {config.LOG_LEVEL}\n"
    )
    await message.answer(text)


@router.callback_query(F.data == "admin:back")
async def go_back(callback: CallbackQuery, state: FSMContext):
    """Go back to admin main menu"""
    await state.clear()
    await callback.answer()
    await callback.message.answer(
        "🔧 <b>پنل مدیریت</b>",
        reply_markup=get_admin_main_menu()
    )


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    """No operation - for pagination indicator"""
    await callback.answer()
