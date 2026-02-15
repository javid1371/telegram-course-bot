"""
Migration handler — cross-platform user migration (Telegram ↔ Bale).

Flow:
1. User on platform A sends /migrate
   → Bot generates a one-time 8-character code (valid 24 h)
   → Code + user snapshot stored in DB
2. User on platform B sends /migrate <code>
   → Bot looks up the code, applies the snapshot (registration data,
     course progress, completed courses, etc.)
   → User continues where they left off on the new platform

This works even when each platform has its own independent database,
as long as the code is transferred manually by the user (copy-paste).
For automatic sync when both servers can reach each other, see
services/sync_service.py.
"""
import logging
import secrets
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from database import async_session_maker
from database.models import User, MigrationCode, UserProgress
from services.user_service import UserService
from utils.platform import platform_label, adapt_text
import config

logger = logging.getLogger(__name__)
router = Router()

# ─────────────────── messages ────────────────────────────────

MSG_GENERATE_OK = (
    "🔄 <b>کد انتقال شما:</b>\n\n"
    "<code>{code}</code>\n\n"
    "این کد تا <b>۲۴ ساعت</b> معتبر است.\n"
    "در پیام‌رسان مقصد ({target}) دستور زیر را ارسال کنید:\n\n"
    "<code>/migrate {code}</code>"
)
MSG_NOT_REGISTERED = "⚠️ شما هنوز ثبت‌نام نکرده‌اید. ابتدا /start بزنید."
MSG_CODE_INVALID = "❌ کد وارد شده نامعتبر یا منقضی شده است."
MSG_CODE_USED = "❌ این کد قبلاً استفاده شده است."
MSG_SAME_PLATFORM = "⚠️ این کد متعلق به همین پلتفرم ({platform}) است. باید در پلتفرم مقصد وارد شود."
MSG_MIGRATE_OK = (
    "✅ <b>انتقال با موفقیت انجام شد!</b>\n\n"
    "اطلاعات دوره و پیشرفت شما از {source} منتقل شد.\n"
    "اکنون می‌توانید با /start ادامه دهید."
)
MSG_ALREADY_MIGRATED = (
    "ℹ️ شما قبلاً در {platform} ثبت‌نام کرده‌اید.\n"
    "اگر می‌خواهید پیشرفت را بازنشانی و دوباره منتقل کنید، ابتدا /reset بزنید."
)
MSG_USAGE = (
    "🔄 <b>انتقال حساب بین پلتفرم‌ها</b>\n\n"
    "• برای <b>دریافت کد انتقال</b> ارسال کنید: /migrate\n"
    "• برای <b>وارد کردن کد</b> ارسال کنید: /migrate XXXXXXXX"
)


def _generate_code() -> str:
    """Generate a short uppercase alphanumeric code."""
    return secrets.token_hex(4).upper()  # 8 chars, e.g. "A3F1B09C"


async def _build_snapshot(user: User, session) -> dict:
    """Create a full snapshot of user data for transfer."""
    from sqlalchemy import select

    # Gather progress records
    result = await session.execute(
        select(UserProgress).where(UserProgress.user_id == user.id)
    )
    progress_list = []
    for p in result.scalars().all():
        progress_list.append({
            "lesson_id": p.lesson_id,
            "started_at": p.started_at.isoformat() if p.started_at else None,
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
            "confirmation_count": p.confirmation_count,
            "time_spent": p.time_spent,
        })

    return {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
        "registration_data": user.registration_data,
        "current_lesson_id": user.current_lesson_id,
        "current_course_id": user.current_course_id,
        "is_completed": user.is_completed,
        "completed_courses": user.completed_courses,
        "double_speed_courses": user.double_speed_courses,
        "fast_track_courses": user.fast_track_courses,
        "tags": user.tags,
        "lead_score": user.lead_score,
        "source_campaign": user.source_campaign,
        "progress": progress_list,
    }


async def _apply_snapshot(user: User, snapshot: dict, session) -> None:
    """Apply a migration snapshot to an existing (or fresh) user."""
    user.registration_data = snapshot.get("registration_data") or user.registration_data
    user.current_lesson_id = snapshot.get("current_lesson_id")
    user.current_course_id = snapshot.get("current_course_id")
    user.is_completed = snapshot.get("is_completed", False)
    user.completed_courses = snapshot.get("completed_courses") or {}
    user.double_speed_courses = snapshot.get("double_speed_courses") or {}
    user.fast_track_courses = snapshot.get("fast_track_courses") or {}
    user.tags = snapshot.get("tags") or user.tags
    user.lead_score = snapshot.get("lead_score", user.lead_score)

    # Restore progress records
    for p_data in snapshot.get("progress", []):
        progress = UserProgress(
            user_id=user.id,
            lesson_id=p_data["lesson_id"],
            confirmation_count=p_data.get("confirmation_count", 0),
            time_spent=p_data.get("time_spent"),
        )
        if p_data.get("completed_at"):
            progress.completed_at = datetime.fromisoformat(p_data["completed_at"])
        session.add(progress)

    await session.commit()
    await session.refresh(user)


# ─────────────────── /migrate command ────────────────────────

@router.message(Command("migrate"))
async def cmd_migrate(message: Message):
    """
    /migrate          → generate a migration code (source platform)
    /migrate CODE     → claim a migration code (target platform)
    """
    parts = message.text.strip().split(maxsplit=1)
    code_arg = parts[1].strip() if len(parts) > 1 else None

    if code_arg:
        await _claim_code(message, code_arg)
    else:
        await _generate_migration_code(message)


async def _generate_migration_code(message: Message):
    """Generate a migration code for the current user."""
    async with async_session_maker() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(message.from_user.id)

        if not user:
            await message.answer(adapt_text(MSG_NOT_REGISTERED))
            return

        code = _generate_code()
        snapshot = await _build_snapshot(user, session)

        target = "بله" if config.PLATFORM == "telegram" else "تلگرام"

        migration = MigrationCode(
            code=code,
            source_platform=config.PLATFORM,
            source_user_id=user.id,
            snapshot=snapshot,
            expires_at=datetime.utcnow() + timedelta(seconds=config.MIGRATION_CODE_TTL),
        )
        session.add(migration)
        await session.commit()

        await message.answer(
            adapt_text(MSG_GENERATE_OK.format(code=code, target=target))
        )
        logger.info(
            f"[Migration] Code {code} generated for user {user.telegram_user_id} "
            f"on {config.PLATFORM}"
        )


async def _claim_code(message: Message, code: str):
    """Claim a migration code received from the other platform."""
    from sqlalchemy import select

    async with async_session_maker() as session:
        # Look up code
        result = await session.execute(
            select(MigrationCode).where(MigrationCode.code == code.upper())
        )
        migration = result.scalar_one_or_none()

        if not migration:
            await message.answer(adapt_text(MSG_CODE_INVALID))
            return

        if migration.is_used:
            await message.answer(adapt_text(MSG_CODE_USED))
            return

        if migration.expires_at < datetime.utcnow():
            await message.answer(adapt_text(MSG_CODE_INVALID))
            return

        if migration.source_platform == config.PLATFORM:
            await message.answer(
                adapt_text(MSG_SAME_PLATFORM.format(platform=platform_label()))
            )
            return

        # Check if user already exists on this platform
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(message.from_user.id)

        if user and user.current_lesson_id:
            # User already has progress — don't overwrite
            await message.answer(
                adapt_text(MSG_ALREADY_MIGRATED.format(platform=platform_label()))
            )
            return

        # Create or update user on this platform
        snapshot = migration.snapshot
        if not user:
            user = await user_service.create_user(
                telegram_user_id=message.from_user.id,
                username=message.from_user.username,
                first_name=snapshot.get("first_name") or message.from_user.first_name,
                last_name=snapshot.get("last_name") or message.from_user.last_name,
                registration_data=snapshot.get("registration_data"),
                source_campaign=snapshot.get("source_campaign"),
            )

        # Apply snapshot
        await _apply_snapshot(user, snapshot, session)

        # Mark code as used
        migration.is_used = True
        migration.used_by_user_id = user.id
        migration.used_at = datetime.utcnow()
        await session.commit()

        source_name = "بله" if migration.source_platform == "bale" else "تلگرام"
        await message.answer(
            adapt_text(MSG_MIGRATE_OK.format(source=source_name))
        )
        logger.info(
            f"[Migration] Code {code} claimed by user {message.from_user.id} "
            f"on {config.PLATFORM} (from {migration.source_platform})"
        )
