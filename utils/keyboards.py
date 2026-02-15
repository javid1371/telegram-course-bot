"""
Keyboard layouts for bot interface
"""
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

from messages import USER_BUTTONS, ADMIN_BUTTONS, GENERAL


# ===========================
# USER KEYBOARDS
# ===========================

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Main menu for users - simplified 3-button layout"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text=USER_BUTTONS["continue_course"])
    )
    builder.row(
        KeyboardButton(text=USER_BUTTONS["my_progress"]),
        KeyboardButton(text=USER_BUTTONS["support"])
    )
    return builder.as_markup(resize_keyboard=True)


def get_lesson_keyboard(lesson_id: int, cta_text: str = None, cta_url: str = None, has_quiz: bool = False, has_delay: bool = True) -> InlineKeyboardMarkup:
    """Keyboard for lesson confirmation with context-aware button text"""
    builder = InlineKeyboardBuilder()

    # Context-aware confirmation button
    if has_quiz:
        btn_text = USER_BUTTONS["lesson_seen_quiz"]
    elif not has_delay:
        btn_text = USER_BUTTONS["lesson_seen_next"]
    else:
        btn_text = USER_BUTTONS["lesson_seen"]

    # Confirmation button
    builder.row(
        InlineKeyboardButton(
            text=btn_text,
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
        InlineKeyboardButton(text=GENERAL["confirm_yes"], callback_data=f"confirm:{action}:{data}"),
        InlineKeyboardButton(text=GENERAL["confirm_no"], callback_data=f"cancel:{action}:{data}")
    )
    return builder.as_markup()


# ===========================
# ADMIN KEYBOARDS
# ===========================

def get_admin_main_menu() -> ReplyKeyboardMarkup:
    """Admin panel main menu"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text=ADMIN_BUTTONS["dashboard"]),
        KeyboardButton(text=ADMIN_BUTTONS["users"])
    )
    builder.row(
        KeyboardButton(text=ADMIN_BUTTONS["lessons"]),
        KeyboardButton(text=ADMIN_BUTTONS["reg_fields"])
    )
    builder.row(
        KeyboardButton(text=ADMIN_BUTTONS["broadcast"]),
        KeyboardButton(text=ADMIN_BUTTONS["reports"])
    )
    builder.row(
        KeyboardButton(text=ADMIN_BUTTONS["webhook"]),
        KeyboardButton(text=ADMIN_BUTTONS["settings"])
    )
    return builder.as_markup(resize_keyboard=True)


def get_lesson_management_keyboard() -> InlineKeyboardMarkup:
    """Lesson management menu"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["add_lesson"], callback_data="admin:lesson:add")
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["lesson_list"], callback_data="admin:lesson:list")
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["reorder_lessons"], callback_data="admin:lesson:reorder")
    )
    builder.row(
        InlineKeyboardButton(text=GENERAL["back"], callback_data="admin:back")
    )
    return builder.as_markup()


def get_lesson_list_keyboard(lessons: list, course_id: int = None) -> InlineKeyboardMarkup:
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

    if course_id:
        builder.row(
            InlineKeyboardButton(text=ADMIN_BUTTONS["back_to_course"], callback_data=f"admin:course:view:{course_id}")
        )
    else:
        builder.row(
            InlineKeyboardButton(text=GENERAL["back"], callback_data="admin:courses")
        )
    return builder.as_markup()


def get_lesson_actions_keyboard(lesson_id: int, course_id: int = None) -> InlineKeyboardMarkup:
    """Actions for a specific lesson"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["edit_lesson"], callback_data=f"admin:lesson:edit:{lesson_id}"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["toggle_status"], callback_data=f"admin:lesson:toggle:{lesson_id}")
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["quiz"], callback_data=f"admin:lesson:quiz:{lesson_id}"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["stats"], callback_data=f"admin:lesson:stats:{lesson_id}")
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["delete"], callback_data=f"admin:lesson:delete:{lesson_id}")
    )
    if course_id:
        builder.row(
            InlineKeyboardButton(text=ADMIN_BUTTONS["back_to_lessons"], callback_data=f"admin:lesson:list:{course_id}")
        )
    else:
        builder.row(
            InlineKeyboardButton(text=GENERAL["back"], callback_data="admin:courses")
        )
    return builder.as_markup()


def get_user_management_keyboard() -> InlineKeyboardMarkup:
    """User management menu"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["all_users"], callback_data="admin:users:all")
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["active_users"], callback_data="admin:users:active"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["inactive_users"], callback_data="admin:users:inactive")
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["completed_users"], callback_data="admin:users:completed")
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["search_users"], callback_data="admin:users:search"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["export_excel"], callback_data="admin:users:export")
    )
    builder.row(
        InlineKeyboardButton(text=GENERAL["back"], callback_data="admin:back")
    )
    return builder.as_markup()


def get_user_actions_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Actions for a specific user"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["send_message"], callback_data=f"admin:user:message:{user_id}"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["stats"], callback_data=f"admin:user:stats:{user_id}")
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["manage_tags"], callback_data=f"admin:user:tags:{user_id}"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["reset_progress"], callback_data=f"admin:user:reset:{user_id}")
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["block_user"], callback_data=f"admin:user:block:{user_id}"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["delete_user"], callback_data=f"admin:user:delete:{user_id}")
    )
    builder.row(
        InlineKeyboardButton(text=GENERAL["back"], callback_data="admin:users:all")
    )
    return builder.as_markup()


def get_broadcast_keyboard() -> InlineKeyboardMarkup:
    """Broadcast message options"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["broadcast_all"], callback_data="admin:broadcast:all")
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["broadcast_active"], callback_data="admin:broadcast:active"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["broadcast_inactive"], callback_data="admin:broadcast:inactive")
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["broadcast_bytag"], callback_data="admin:broadcast:bytag")
    )
    builder.row(
        InlineKeyboardButton(text=GENERAL["back"], callback_data="admin:back")
    )
    return builder.as_markup()


def get_registration_fields_keyboard() -> InlineKeyboardMarkup:
    """Registration fields management"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["add_field"], callback_data="admin:field:add")
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["field_list"], callback_data="admin:field:list")
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["reorder_fields"], callback_data="admin:field:reorder")
    )
    builder.row(
        InlineKeyboardButton(text=GENERAL["back"], callback_data="admin:back")
    )
    return builder.as_markup()


def get_field_actions_keyboard(field_id: int) -> InlineKeyboardMarkup:
    """Actions for a specific registration field"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["edit_field_label"], callback_data=f"admin:field:editlbl:{field_id}"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["toggle_required"], callback_data=f"admin:field:togglereq:{field_id}")
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["toggle_active"], callback_data=f"admin:field:toggle:{field_id}"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["delete_field"], callback_data=f"admin:field:del:{field_id}")
    )
    builder.row(
        InlineKeyboardButton(text=GENERAL["back"], callback_data="admin:field:list")
    )
    return builder.as_markup()


def get_field_type_keyboard() -> InlineKeyboardMarkup:
    """Field type selection"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["field_text"], callback_data="admin:field:type:text"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["field_number"], callback_data="admin:field:type:number")
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["field_email"], callback_data="admin:field:type:email"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["field_phone"], callback_data="admin:field:type:phone")
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["field_date"], callback_data="admin:field:type:date"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["field_select"], callback_data="admin:field:type:select")
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["field_cancel"], callback_data="admin:field:cancel")
    )
    return builder.as_markup()


def get_webhook_keyboard() -> InlineKeyboardMarkup:
    """Webhook settings menu"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["add_webhook"], callback_data="admin:webhook:add")
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["webhook_list"], callback_data="admin:webhook:list")
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["test_webhook"], callback_data="admin:webhook:test")
    )
    builder.row(
        InlineKeyboardButton(text=GENERAL["back"], callback_data="admin:back")
    )
    return builder.as_markup()


def get_stats_keyboard() -> InlineKeyboardMarkup:
    """Statistics menu"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["stats_today"], callback_data="admin:stats:today"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["stats_week"], callback_data="admin:stats:week")
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["stats_month"], callback_data="admin:stats:month"),
        InlineKeyboardButton(text=ADMIN_BUTTONS["stats_all"], callback_data="admin:stats:all")
    )
    builder.row(
        InlineKeyboardButton(text=ADMIN_BUTTONS["export_data"], callback_data="admin:stats:export")
    )
    builder.row(
        InlineKeyboardButton(text=GENERAL["back"], callback_data="admin:back")
    )
    return builder.as_markup()


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Cancel operation keyboard"""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=USER_BUTTONS["cancel"]))
    return builder.as_markup(resize_keyboard=True)


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Simple back button"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=GENERAL["back"], callback_data="admin:back"))
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
        buttons.append(InlineKeyboardButton(text=ADMIN_BUTTONS["prev_page"], callback_data=f"{callback_prefix}:{page-1}"))

    buttons.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="noop"))

    if page < total_pages:
        buttons.append(InlineKeyboardButton(text=ADMIN_BUTTONS["next_page"], callback_data=f"{callback_prefix}:{page+1}"))

    builder.row(*buttons)
    builder.row(InlineKeyboardButton(text=GENERAL["back"], callback_data="admin:back"))

    return builder.as_markup()
