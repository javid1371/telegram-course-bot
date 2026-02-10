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

from database import async_session_maker
from database.models import ContentType, FieldType, Admin
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
    get_webhook_keyboard, get_cancel_keyboard,
    get_back_keyboard, get_pagination_keyboard,
    get_confirm_keyboard,
)
from utils.decorators import admin_only, log_errors
from utils.helpers import format_number, format_duration, truncate_text
import config

logger = logging.getLogger(__name__)
router = Router()


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
    """Show admin dashboard"""
    async with async_session_maker() as session:
        analytics = AnalyticsService(session)
        stats = await analytics.get_dashboard_stats()

        text = (
            "📊 <b>داشبورد</b>\n\n"
            f"👥 کل کاربران: {format_number(stats['total_users'])}\n"
            f"✅ کاربران فعال: {format_number(stats['active_users'])}\n"
            f"🎓 تکمیل کننده‌ها: {format_number(stats['completed_courses'])}\n"
            f"📈 نرخ تکمیل: {stats['completion_rate']}%\n\n"
            f"📚 تعداد درس‌ها: {format_number(stats['total_lessons'])}\n\n"
            f"📅 <b>امروز:</b>\n"
            f"  🆕 کاربران جدید: {format_number(stats['today_new_users'])}\n"
            f"  ✅ درس‌های تکمیل شده: {format_number(stats['today_completions'])}\n\n"
            f"📅 <b>این هفته:</b>\n"
            f"  🆕 کاربران جدید: {format_number(stats['week_new_users'])}"
        )

        await message.answer(text)


# ===========================
# LESSON MANAGEMENT
# ===========================

@router.message(F.text == "📚 درس‌ها")
@admin_only
@log_errors
async def lesson_management_menu(message: Message):
    """Show lesson management menu"""
    await message.answer(
        "📚 <b>مدیریت درس‌ها</b>\n\nیک گزینه را انتخاب کنید:",
        reply_markup=get_lesson_management_keyboard()
    )


@router.callback_query(F.data == "admin:lessons")
@admin_only
@log_errors
async def lesson_menu_callback(callback: CallbackQuery):
    """Show lesson management menu via callback"""
    await callback.answer()
    await callback.message.edit_text(
        "📚 <b>مدیریت درس‌ها</b>\n\nیک گزینه را انتخاب کنید:",
        reply_markup=get_lesson_management_keyboard()
    )


@router.callback_query(F.data == "admin:lesson:add")
@admin_only
@log_errors
async def add_lesson_start(callback: CallbackQuery, state: FSMContext):
    """Start adding a new lesson"""
    await callback.answer()
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
        InlineKeyboardButton(text="📄 فایل", callback_data="lesson_type:document"),
    )
    builder.row(
        InlineKeyboardButton(text="🖼 تصویر", callback_data="lesson_type:photo"),
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

    type_prompts = {
        "text": "📝 متن درس را ارسال کنید:",
        "video": "🎥 ویدیو درس را ارسال کنید (فایل ویدیو):",
        "audio": "🎵 فایل صوتی درس را ارسال کنید:",
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
    elif content_type == "audio" and message.audio:
        file_id = message.audio.file_id
    elif content_type == "document" and message.document:
        file_id = message.document.file_id
    elif content_type == "photo" and message.photo:
        file_id = message.photo[-1].file_id  # Largest photo
    else:
        await message.answer("⚠️ لطفاً نوع محتوای صحیح ارسال کنید.")
        return

    await state.update_data(
        lesson_file_id=file_id,
        lesson_text_content=text_content,
    )

    await message.answer(
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

    # Save lesson
    data = await state.get_data()
    await state.clear()

    content_type_map = {
        "text": ContentType.TEXT,
        "video": ContentType.VIDEO,
        "audio": ContentType.AUDIO,
        "document": ContentType.DOCUMENT,
        "photo": ContentType.PHOTO,
    }

    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        lesson = await lesson_service.create_lesson(
            title=data["lesson_title"],
            content_type=content_type_map[data["lesson_content_type"]],
            description=description,
            file_id=data.get("lesson_file_id"),
            text_content=data.get("lesson_text_content"),
        )

        await message.answer(
            f"✅ درس «{lesson.title}» با موفقیت اضافه شد!\n"
            f"📋 شماره: {lesson.order}\n"
            f"📦 نوع: {data['lesson_content_type']}",
            reply_markup=get_admin_main_menu()
        )


@router.callback_query(F.data == "admin:lesson:list")
@admin_only
@log_errors
async def list_lessons(callback: CallbackQuery):
    """List all lessons"""
    await callback.answer()

    async with async_session_maker() as session:
        lesson_service = LessonService(session)
        lessons = await lesson_service.get_all_lessons(active_only=False)

        if not lessons:
            await callback.message.edit_text(
                "📭 هنوز درسی اضافه نشده.",
                reply_markup=get_lesson_management_keyboard()
            )
            return

        await callback.message.edit_text(
            f"📚 <b>لیست درس‌ها</b> ({len(lessons)} درس)\n\n"
            "برای مدیریت روی هر درس کلیک کنید:",
            reply_markup=get_lesson_list_keyboard(lessons)
        )


@router.callback_query(F.data.startswith("admin:lesson:view:"))
@admin_only
@log_errors
async def view_lesson(callback: CallbackQuery):
    """View lesson details"""
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
        text = (
            f"📚 <b>درس {lesson.order}: {lesson.title}</b>\n\n"
            f"📦 نوع: {lesson.content_type.value}\n"
            f"📌 وضعیت: {status}\n"
            f"📝 توضیحات: {truncate_text(lesson.description or 'ندارد', 200)}\n\n"
            f"📊 <b>آمار:</b>\n"
            f"  👁 شروع شده: {stats['started']}\n"
            f"  ✅ تکمیل شده: {stats['completed']}\n"
            f"  📈 نرخ تکمیل: {stats['completion_rate']}%"
        )

        if lesson.cta_text:
            text += f"\n\n🔗 CTA: {lesson.cta_text} → {lesson.cta_url or '-'}"

        await callback.message.edit_text(
            text, reply_markup=get_lesson_actions_keyboard(lesson_id)
        )


@router.callback_query(F.data.startswith("admin:lesson:stats:"))
@admin_only
@log_errors
async def lesson_stats(callback: CallbackQuery):
    """Show lesson stats - redirects to lesson view which includes stats"""
    lesson_id = int(callback.data.split(":")[3])
    callback.data = f"admin:lesson:view:{lesson_id}"
    await view_lesson(callback)


@router.callback_query(F.data.startswith("admin:lesson:edit:"))
@admin_only
@log_errors
async def edit_lesson(callback: CallbackQuery):
    """Edit lesson - placeholder for future implementation"""
    await callback.answer("⚠️ این قابلیت در نسخه بعدی اضافه می‌شود.", show_alert=True)


@router.callback_query(F.data == "admin:lesson:reorder")
@admin_only
@log_errors
async def reorder_lessons(callback: CallbackQuery):
    """Reorder lessons - placeholder for future implementation"""
    await callback.answer("⚠️ این قابلیت در نسخه بعدی اضافه می‌شود.", show_alert=True)


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
            await view_lesson(callback)
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
    callback.data = f"admin:lesson:view:{lesson_id}"
    await view_lesson(callback)


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
async def view_user(callback: CallbackQuery):
    """View user details"""
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

        await callback.message.edit_text(
            text, reply_markup=get_user_actions_keyboard(user_id)
        )


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
    callback.data = f"admin:user:view:{user_id}"
    await view_user(callback)


@router.callback_query(F.data.startswith("admin:user:stats:"))
@admin_only
@log_errors
async def user_stats(callback: CallbackQuery):
    """Show user stats - redirects to user view which includes stats"""
    user_id = int(callback.data.split(":")[3])
    callback.data = f"admin:user:view:{user_id}"
    await view_user(callback)


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
    """List all registration fields"""
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

        text = "📝 <b>فیلدهای ثبت‌نام</b>\n\n"
        for f in fields:
            required = "✅" if f.is_required else "❌"
            text += f"{f.order}. {f.field_label} ({f.field_type.value}) - اجباری: {required}\n"

        await callback.message.edit_text(
            text,
            reply_markup=get_registration_fields_keyboard()
        )


@router.callback_query(F.data == "admin:field:reorder")
@admin_only
@log_errors
async def reorder_fields(callback: CallbackQuery):
    """Reorder registration fields - placeholder for future implementation"""
    await callback.answer("⚠️ این قابلیت در نسخه بعدی اضافه می‌شود.", show_alert=True)


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
    await message.answer(
        "🔗 <b>مدیریت وبهوک‌ها</b>\n\nیک گزینه را انتخاب کنید:",
        reply_markup=get_webhook_keyboard()
    )


@router.callback_query(F.data == "admin:webhook:add")
@admin_only
@log_errors
async def add_webhook_start(callback: CallbackQuery, state: FSMContext):
    """Start adding a webhook"""
    await callback.answer()
    await callback.message.answer(
        "🔗 نام وبهوک را وارد کنید:\nمثال: user_registered, lesson_completed",
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
    """List all webhooks"""
    await callback.answer()

    async with async_session_maker() as session:
        webhook_service = WebhookService(session)
        webhooks = await webhook_service.get_active_webhooks()

        if not webhooks:
            await callback.message.edit_text(
                "📭 هنوز وبهوکی اضافه نشده.",
                reply_markup=get_webhook_keyboard()
            )
            return

        text = "🔗 <b>لیست وبهوک‌ها</b>\n\n"
        for wh in webhooks:
            status = "✅" if wh.is_active else "❌"
            text += f"{status} <b>{wh.name}</b>\n  🌐 {wh.url}\n  📋 {wh.method}\n\n"

        await callback.message.edit_text(text, reply_markup=get_webhook_keyboard())


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
