"""
Registration handler - Dynamic user registration with FSM
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import CommandStart, Command

from database import async_session_maker
from database.models import RegistrationField, FieldType
from services.user_service import UserService
from services.lesson_service import LessonService
from services.event_emitter import emit
from utils.keyboards import get_main_menu_keyboard, get_cancel_keyboard
from utils.validators import validate_field_value, ValidationError
from utils.helpers import parse_tracking_link
import config
from messages import REGISTRATION, ADMIN, USER_BUTTONS, GENERAL


async def _send_cross_platform_hint(message: Message):
    """Send cross-platform bot link if configured."""
    cross_link = config.CROSS_PLATFORM_BOT_LINK
    if not cross_link:
        return
    from messages import CROSS_PLATFORM
    if config.PLATFORM == "telegram":
        text = CROSS_PLATFORM["telegram_to_bale"].format(link=cross_link)
    else:
        text = CROSS_PLATFORM["bale_to_telegram"].format(link=cross_link)
    text += "\n" + CROSS_PLATFORM["migrate_hint"]
    try:
        await message.answer(text)
    except Exception:
        pass

logger = logging.getLogger(__name__)
router = Router()


class RegistrationStates(StatesGroup):
    """FSM states for registration process"""
    waiting_for_field = State()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command - check if user registered or start registration"""
    async with async_session_maker() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(message.from_user.id)

        if user:
            # User already registered
            if message.from_user.id in config.ADMIN_USER_IDS:
                await message.answer(
                    ADMIN["welcome"],
                    reply_markup=get_main_menu_keyboard()
                )
            else:
                await message.answer(
                    REGISTRATION["welcome_back"].format(name=user.first_name or ''),
                    reply_markup=get_main_menu_keyboard()
                )
            return

        # Parse tracking info from start parameter
        start_param = message.text.split(" ", 1)[1] if " " in message.text else None
        campaign, referral = parse_tracking_link(start_param)

        # Get registration fields
        reg_fields = await user_service.get_active_registration_fields()

        if not reg_fields:
            # No registration fields configured - auto register
            # Find referred_by user
            referred_by = None
            if referral:
                from sqlalchemy import select as sa_select
                from database.models import User
                ref_result = await session.execute(
                    sa_select(User).where(User.referral_code == referral)
                )
                ref_user = ref_result.scalar_one_or_none()
                if ref_user:
                    referred_by = ref_user.id

            new_user = await user_service.create_user(
                telegram_user_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                source_campaign=campaign,
                referred_by=referred_by,
            )

            # Notify referral welcome
            if referred_by and ref_user:
                inviter_name = ref_user.first_name or ref_user.username or ""
                from messages import USER as USER_MSG
                try:
                    await message.answer(
                        USER_MSG["referral_welcome_bonus"].format(inviter_name=inviter_name)
                    )
                except Exception:
                    pass

            # Send webhook
            await emit("lead", "register", new_user, session)

            await message.answer(
                REGISTRATION["registration_complete"],
                reply_markup=get_main_menu_keyboard()
            )

            # Cross-platform hint
            await _send_cross_platform_hint(message)

            # Onboarding + auto-deliver first lesson
            await message.answer(REGISTRATION["onboarding"])
            await _auto_send_first_lesson(message, message.from_user.id)
            return

        # Start registration process
        fields_data = [{
                "id": f.id,
                "field_name": f.field_name,
                "field_label": f.field_label,
                "field_type": f.field_type.value,
                "is_required": f.is_required,
                "validation_rule": f.validation_rule,
                "options": f.options,
            } for f in reg_fields]

        await state.update_data(
            reg_fields=fields_data,
            current_field_index=0,
            registration_data={},
            campaign=campaign,
            referral=referral,
        )

        await message.answer(REGISTRATION["welcome"])

        # Send first field prompt (use dict version, not ORM object)
        first_field = fields_data[0]
        prompt = _get_field_prompt(first_field)
        keyboard = _get_field_keyboard(first_field)

        if keyboard:
            await message.answer(prompt, reply_markup=keyboard)
        else:
            await message.answer(prompt, reply_markup=get_cancel_keyboard())

        await state.set_state(RegistrationStates.waiting_for_field)


@router.message(RegistrationStates.waiting_for_field, F.text == USER_BUTTONS["cancel"])
async def cancel_registration(message: Message, state: FSMContext):
    """Cancel registration"""
    await state.clear()
    await message.answer(
        REGISTRATION["registration_cancelled"],
        reply_markup=get_main_menu_keyboard()
    )


@router.message(RegistrationStates.waiting_for_field)
async def process_registration_field(message: Message, state: FSMContext):
    """Process each registration field"""
    data = await state.get_data()
    fields = data["reg_fields"]
    current_index = data["current_field_index"]
    reg_data = data["registration_data"]

    if current_index >= len(fields):
        await state.clear()
        return

    current_field = fields[current_index]

    # Validate input
    try:
        validated_value = validate_field_value(
            current_field["field_type"],
            message.text,
            current_field.get("validation_rule"),
        )
        # Convert datetime to string for JSON storage
        if hasattr(validated_value, 'strftime'):
            validated_value = validated_value.strftime("%Y/%m/%d")
        elif isinstance(validated_value, float):
            validated_value = str(validated_value)

        reg_data[current_field["field_name"]] = validated_value

    except ValidationError as e:
        # Validation failed - ask again
        await message.answer(
            REGISTRATION["validation_error"].format(error=str(e))
        )
        return

    # Move to next field
    next_index = current_index + 1

    if next_index < len(fields):
        # More fields to fill
        next_field = fields[next_index]
        prompt = _get_field_prompt(next_field)
        keyboard = _get_field_keyboard(next_field)

        await state.update_data(
            current_field_index=next_index,
            registration_data=reg_data,
        )

        if keyboard:
            await message.answer(prompt, reply_markup=keyboard)
        else:
            await message.answer(prompt, reply_markup=get_cancel_keyboard())

    else:
        # Registration complete
        await state.clear()

        async with async_session_maker() as session:
            user_service = UserService(session)

            # Find referred_by user
            referred_by = None
            if data.get("referral"):
                from sqlalchemy import select
                from database.models import User
                ref_result = await session.execute(
                    select(User).where(User.referral_code == data["referral"])
                )
                ref_user = ref_result.scalar_one_or_none()
                if ref_user:
                    referred_by = ref_user.id

            new_user = await user_service.create_user(
                telegram_user_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                registration_data=reg_data,
                source_campaign=data.get("campaign"),
                referred_by=referred_by,
            )

            # Send webhook
            await emit("lead", "register", new_user, session)

        # Notify referral welcome
        if referred_by:
            from messages import USER as USER_MSG
            inviter_name = ref_user.first_name or ref_user.username or "" if ref_user else ""
            try:
                await message.answer(
                    USER_MSG["referral_welcome_bonus"].format(inviter_name=inviter_name)
                )
            except Exception:
                pass

        await message.answer(
            REGISTRATION["registration_complete"],
            reply_markup=get_main_menu_keyboard()
        )

        # Cross-platform hint
        await _send_cross_platform_hint(message)

        # Onboarding + auto-deliver first lesson
        await message.answer(REGISTRATION["onboarding"])
        await _auto_send_first_lesson(message, message.from_user.id)


@router.callback_query(F.data.startswith("reg_select:"))
async def process_select_field(callback: CallbackQuery, state: FSMContext):
    """Handle select field option selection"""
    selected_value = callback.data.split(":", 1)[1]
    await callback.answer()

    # Create a fake message-like processing
    data = await state.get_data()
    fields = data["reg_fields"]
    current_index = data["current_field_index"]
    reg_data = data["registration_data"]

    if current_index >= len(fields):
        await state.clear()
        return

    current_field = fields[current_index]
    reg_data[current_field["field_name"]] = selected_value

    next_index = current_index + 1

    if next_index < len(fields):
        next_field = fields[next_index]
        prompt = _get_field_prompt(next_field)
        keyboard = _get_field_keyboard(next_field)

        await state.update_data(
            current_field_index=next_index,
            registration_data=reg_data,
        )

        if keyboard:
            await callback.message.answer(prompt, reply_markup=keyboard)
        else:
            await callback.message.answer(prompt, reply_markup=get_cancel_keyboard())

    else:
        await state.clear()

        async with async_session_maker() as session:
            user_service = UserService(session)

            new_user = await user_service.create_user(
                telegram_user_id=callback.from_user.id,
                username=callback.from_user.username,
                first_name=callback.from_user.first_name,
                last_name=callback.from_user.last_name,
                registration_data=reg_data,
                source_campaign=data.get("campaign"),
            )

            await emit("lead", "register", new_user, session)

        await callback.message.answer(
            REGISTRATION["registration_complete"],
            reply_markup=get_main_menu_keyboard()
        )

        # Cross-platform hint
        await _send_cross_platform_hint(callback.message)

        # Onboarding + auto-deliver first lesson
        await callback.message.answer(REGISTRATION["onboarding"])
        await _auto_send_first_lesson(callback.message, callback.from_user.id)


def _get_field_prompt(field: dict) -> str:
    """Generate prompt text for a registration field"""
    required = REGISTRATION["field_required"] if field["is_required"] else REGISTRATION["field_optional"]
    hints = REGISTRATION["field_hints"]
    hint = hints.get(field["field_type"], hints["default"])
    return REGISTRATION["field_prompt"].format(
        label=field['field_label'],
        required=required,
        hint=hint,
    )


def _get_field_keyboard(field: dict):
    """Generate inline keyboard for select fields"""
    if field["field_type"] != "select" or not field.get("options"):
        return None

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    options = field["options"]

    if isinstance(options, dict) and "choices" in options:
        choices = options["choices"]
    elif isinstance(options, list):
        choices = options
    else:
        return None

    for choice in choices:
        if isinstance(choice, dict):
            label = choice.get("label", str(choice))
            value = choice.get("value", label)
        else:
            label = str(choice)
            value = label

        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=f"reg_select:{value}"
            )
        )

    return builder.as_markup()


async def _auto_send_first_lesson(message: Message, telegram_user_id: int):
    """Auto-deliver first lesson after registration (onboarding)"""
    try:
        async with async_session_maker() as session:
            user_service = UserService(session)
            lesson_service = LessonService(session)

            user = await user_service.get_user_by_telegram_id(telegram_user_id)
            if not user:
                return

            courses = await lesson_service.get_all_courses(active_only=True)
            if not courses:
                return

            # Auto-select first course
            course = courses[0]
            user.current_course_id = course.id

            first_lesson = await lesson_service.get_next_lesson_for_user(user.id, course_id=course.id)
            if not first_lesson:
                return

            await lesson_service.mark_lesson_started(user.id, first_lesson.id)
            user.current_lesson_id = first_lesson.id
            await session.commit()

            # Send lesson content
            from handlers.user import _send_lesson
            await _send_lesson(message, first_lesson)
    except Exception as e:
        logger.error(f"Error auto-sending first lesson: {e}")
