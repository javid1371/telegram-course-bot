"""
Keyboard layouts for bot interface
"""
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


# ===========================
# USER KEYBOARDS
# ===========================

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Main menu for users"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📚 ادامه دوره"),
        KeyboardButton(text="📊 پیشرفت من")
    )
    builder.row(
        KeyboardButton(text="ℹ️ درباره دوره"),
        KeyboardButton(text="📞 پشتیبانی")
    )
    return builder.as_markup(resize_keyboard=True)


def get_lesson_keyboard(lesson_id: int, cta_text: str = None, cta_url: str = None) -> InlineKeyboardMarkup:
    """Keyboard for lesson confirmation"""
    builder = InlineKeyboardBuilder()

    # Confirmation button
    builder.row(
        InlineKeyboardButton(
            text="✅ درس رو دیدم",
            callback_data=f"confirm_lesson:{lesson_id}"
        )
    )

    # CTA button if provided
    if cta_text and cta_url:
        builder.row(
            InlineKeyboardButton(text=cta_text, url=cta_url)
        )

    return builder.as_markup()


def get_confirm_keyboard(action: str, data: str = "") -> InlineKeyboardMarkup:
    """Generic confirmation keyboard"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ بله", callback_data=f"confirm:{action}:{data}"),
        InlineKeyboardButton(text="❌ خیر", callback_data=f"cancel:{action}:{data}")
    )
    return builder.as_markup()


# ===========================
# ADMIN KEYBOARDS
# ===========================

def get_admin_main_menu() -> ReplyKeyboardMarkup:
    """Admin panel main menu"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📊 داشبورد"),
        KeyboardButton(text="👥 کاربران")
    )
    builder.row(
        KeyboardButton(text="📚 درس‌ها"),
        KeyboardButton(text="📝 فیلدهای ثبت‌نام")
    )
    builder.row(
        KeyboardButton(text="📢 ارسال پیام"),
        KeyboardButton(text="📈 گزارش‌ها")
    )
    builder.row(
        KeyboardButton(text="🔗 وبهوک"),
        KeyboardButton(text="⚙️ تنظیمات")
    )
    return builder.as_markup(resize_keyboard=True)


def get_lesson_management_keyboard() -> InlineKeyboardMarkup:
    """Lesson management menu"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ افزودن درس", callback_data="admin:lesson:add")
    )
    builder.row(
        InlineKeyboardButton(text="📋 لیست درس‌ها", callback_data="admin:lesson:list")
    )
    builder.row(
        InlineKeyboardButton(text="🔄 ترتیب درس‌ها", callback_data="admin:lesson:reorder")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:back")
    )
    return builder.as_markup()


def get_lesson_list_keyboard(lessons: list) -> InlineKeyboardMarkup:
    """List of lessons for management"""
    builder = InlineKeyboardBuilder()

    for lesson in lessons:
        status = "✅" if lesson.is_active else "❌"
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {lesson.order}. {lesson.title}",
                callback_data=f"admin:lesson:view:{lesson.id}"
            )
        )

    builder.row(
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:lessons")
    )
    return builder.as_markup()


def get_lesson_actions_keyboard(lesson_id: int) -> InlineKeyboardMarkup:
    """Actions for a specific lesson"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ ویرایش", callback_data=f"admin:lesson:edit:{lesson_id}"),
        InlineKeyboardButton(text="🔄 تغییر وضعیت", callback_data=f"admin:lesson:toggle:{lesson_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🗑 حذف", callback_data=f"admin:lesson:delete:{lesson_id}"),
        InlineKeyboardButton(text="📊 آمار", callback_data=f"admin:lesson:stats:{lesson_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:lesson:list")
    )
    return builder.as_markup()


def get_user_management_keyboard() -> InlineKeyboardMarkup:
    """User management menu"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👥 همه کاربران", callback_data="admin:users:all")
    )
    builder.row(
        InlineKeyboardButton(text="✅ فعال‌ها", callback_data="admin:users:active"),
        InlineKeyboardButton(text="❌ غیرفعال‌ها", callback_data="admin:users:inactive")
    )
    builder.row(
        InlineKeyboardButton(text="🎓 تکمیل کننده‌ها", callback_data="admin:users:completed")
    )
    builder.row(
        InlineKeyboardButton(text="🔍 جستجو", callback_data="admin:users:search"),
        InlineKeyboardButton(text="📥 اکسپورت Excel", callback_data="admin:users:export")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:back")
    )
    return builder.as_markup()


def get_user_actions_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Actions for a specific user"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💬 ارسال پیام", callback_data=f"admin:user:message:{user_id}"),
        InlineKeyboardButton(text="📊 آمار", callback_data=f"admin:user:stats:{user_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🏷 مدیریت تگ‌ها", callback_data=f"admin:user:tags:{user_id}"),
        InlineKeyboardButton(text="🔄 ریست پیشرفت", callback_data=f"admin:user:reset:{user_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🚫 بلاک", callback_data=f"admin:user:block:{user_id}"),
        InlineKeyboardButton(text="🗑 حذف", callback_data=f"admin:user:delete:{user_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:users:all")
    )
    return builder.as_markup()


def get_broadcast_keyboard() -> InlineKeyboardMarkup:
    """Broadcast message options"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📢 همه کاربران", callback_data="admin:broadcast:all")
    )
    builder.row(
        InlineKeyboardButton(text="✅ فقط فعال‌ها", callback_data="admin:broadcast:active"),
        InlineKeyboardButton(text="❌ فقط غیرفعال‌ها", callback_data="admin:broadcast:inactive")
    )
    builder.row(
        InlineKeyboardButton(text="🏷 بر اساس تگ", callback_data="admin:broadcast:bytag")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:back")
    )
    return builder.as_markup()


def get_registration_fields_keyboard() -> InlineKeyboardMarkup:
    """Registration fields management"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ افزودن فیلد", callback_data="admin:field:add")
    )
    builder.row(
        InlineKeyboardButton(text="📋 لیست فیلدها", callback_data="admin:field:list")
    )
    builder.row(
        InlineKeyboardButton(text="🔄 ترتیب فیلدها", callback_data="admin:field:reorder")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:back")
    )
    return builder.as_markup()


def get_field_type_keyboard() -> InlineKeyboardMarkup:
    """Field type selection"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📝 متن", callback_data="admin:field:type:text"),
        InlineKeyboardButton(text="🔢 عدد", callback_data="admin:field:type:number")
    )
    builder.row(
        InlineKeyboardButton(text="📧 ایمیل", callback_data="admin:field:type:email"),
        InlineKeyboardButton(text="📱 شماره تلفن", callback_data="admin:field:type:phone")
    )
    builder.row(
        InlineKeyboardButton(text="📅 تاریخ", callback_data="admin:field:type:date"),
        InlineKeyboardButton(text="☑️ انتخابی", callback_data="admin:field:type:select")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 انصراف", callback_data="admin:field:cancel")
    )
    return builder.as_markup()


def get_webhook_keyboard() -> InlineKeyboardMarkup:
    """Webhook settings menu"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ افزودن وبهوک", callback_data="admin:webhook:add")
    )
    builder.row(
        InlineKeyboardButton(text="📋 لیست وبهوک‌ها", callback_data="admin:webhook:list")
    )
    builder.row(
        InlineKeyboardButton(text="🧪 تست وبهوک", callback_data="admin:webhook:test")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:back")
    )
    return builder.as_markup()


def get_stats_keyboard() -> InlineKeyboardMarkup:
    """Statistics menu"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 امروز", callback_data="admin:stats:today"),
        InlineKeyboardButton(text="📅 هفته", callback_data="admin:stats:week")
    )
    builder.row(
        InlineKeyboardButton(text="📆 ماه", callback_data="admin:stats:month"),
        InlineKeyboardButton(text="📈 کل", callback_data="admin:stats:all")
    )
    builder.row(
        InlineKeyboardButton(text="📥 اکسپورت داده", callback_data="admin:stats:export")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:back")
    )
    return builder.as_markup()


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Cancel operation keyboard"""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="❌ انصراف"))
    return builder.as_markup(resize_keyboard=True)


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Simple back button"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:back"))
    return builder.as_markup()


def get_pagination_keyboard(
    page: int,
    total_pages: int,
    callback_prefix: str
) -> InlineKeyboardMarkup:
    """Generic pagination keyboard"""
    builder = InlineKeyboardBuilder()

    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"{callback_prefix}:{page-1}"))

    buttons.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="noop"))

    if page < total_pages:
        buttons.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"{callback_prefix}:{page+1}"))

    builder.row(*buttons)
    builder.row(InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:back"))

    return builder.as_markup()
