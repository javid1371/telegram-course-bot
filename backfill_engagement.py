"""
One-time backfill script: award badges to existing users based on their
current progress, then broadcast an announcement showing their achievements.

Usage:
    python backfill_engagement.py              # dry-run (no messages sent)
    python backfill_engagement.py --send       # actually send broadcast
    python backfill_engagement.py --backfill   # only backfill, no broadcast
    python backfill_engagement.py --send --backfill  # both
"""
import asyncio
import argparse
import logging
import sys
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

# ── Bootstrap the app ──
from database import async_session_maker
from database.models import User
from services.lesson_service import LessonService
from services.engagement_service import EngagementService, BADGES
import config


# ═══════════════════════════════════════════
# BADGE DEFINITIONS (same logic as EngagementService)
# ═══════════════════════════════════════════

async def compute_badges_for_user(session: AsyncSession, user: User) -> list:
    """Compute which badges a user should have based on current data."""
    lesson_service = LessonService(session)
    badges = set()

    # Get progress per course + overall
    courses = await lesson_service.get_all_courses(active_only=True)
    total_completed = 0
    total_lessons = 0

    for course in courses:
        progress = await lesson_service.get_user_progress(user.id, course_id=course.id)
        c = progress.get("completed", 0)
        t = progress.get("total", 1)
        pct = progress.get("progress_percent", 0)
        total_completed += c
        total_lessons += t

        if c >= 1:
            badges.add("starter")
        if c >= 3:
            badges.add("motivated")
        if pct >= 50:
            badges.add("halfway")
        if pct >= 90:
            badges.add("almost")
        if progress.get("remaining", 1) == 0:
            badges.add("graduate")

    # If no courses, use overall
    if not courses:
        progress = await lesson_service.get_user_progress(user.id)
        c = progress.get("completed", 0)
        pct = progress.get("progress_percent", 0)
        total_completed = c

        if c >= 1:
            badges.add("starter")
        if c >= 3:
            badges.add("motivated")
        if pct >= 50:
            badges.add("halfway")
        if pct >= 90:
            badges.add("almost")
        if progress.get("remaining", 1) == 0:
            badges.add("graduate")

    # Streak badges can't be retroactive (no historical day-by-day data)
    # fast_learner can't be retroactive (no time data for past lessons)

    return sorted(badges)


def build_announcement(user: User, badges: list, overall_pct: int) -> str:
    """Build personal announcement message."""
    name = user.first_name or "دوست عزیز"

    text = (
        f"🎉 {name}، قابلیت‌های جدید اضافه شدن!\n\n"
        "از الان بعد از هر درس، یه <b>کارت پیشرفت</b> میبینی که شامل:\n"
        "🔥 <b>استریک</b> — چند روز متوالی فعالی\n"
        "🏆 <b>بج‌ها</b> — دستاوردهات\n"
        "🌟 <b>مقایسه</b> — جزو چند درصد برتری\n"
        "📖 <b>پیش‌نمایش</b> — عنوان درس بعدی\n\n"
    )

    if badges:
        text += "بر اساس پیشرفت فعلیت، این بج‌ها رو کسب کردی:\n"
        for bk in badges:
            info = BADGES.get(bk, {})
            label = info.get("label", bk)
            desc = info.get("description", "")
            text += f"  ✅ <b>{label}</b> — {desc}\n"
        text += "\n"
    else:
        text += "هنوز بجی نداری — شروع کن تا اولین بجت رو بگیری! 🌱\n\n"

    text += (
        f"📈 پیشرفت فعلی: <b>{overall_pct}%</b>\n\n"
        "از منوی «📊 پیشرفت من» میتونی همه دستاوردهات رو ببینی. 🎯"
    )

    return text


async def run_backfill(send_broadcast: bool = False, backfill_only: bool = False):
    """Main backfill + broadcast logic."""
    async with async_session_maker() as session:
        # Fetch all active, non-completed users + completed users
        result = await session.execute(
            select(User).where(User.is_active == True)
        )
        users = list(result.scalars().all())
        logger.info(f"Found {len(users)} active users to process")

        lesson_service = LessonService(session)
        stats = {"backfilled": 0, "broadcast_sent": 0, "broadcast_failed": 0, "skipped": 0}

        bot = None
        if send_broadcast and not backfill_only:
            from aiogram import Bot
            bot = Bot(token=config.BOT_TOKEN)

        for user in users:
            try:
                # 1) Compute badges
                badges = await compute_badges_for_user(session, user)

                # 2) Backfill: update user.badges
                existing = set(user.badges or [])
                merged = sorted(existing | set(badges))
                if merged != sorted(existing):
                    user.badges = merged
                    stats["backfilled"] += 1
                    logger.info(
                        f"  User {user.telegram_user_id}: "
                        f"badges {sorted(existing)} → {merged}"
                    )

                # 3) Compute overall progress for announcement
                courses = await lesson_service.get_all_courses(active_only=True)
                total_c = 0
                total_t = 0
                for course in courses:
                    p = await lesson_service.get_user_progress(user.id, course_id=course.id)
                    total_c += p["completed"]
                    total_t += p["total"]
                if not courses:
                    p = await lesson_service.get_user_progress(user.id)
                    total_c = p["completed"]
                    total_t = p["total"]
                overall_pct = round(total_c / total_t * 100) if total_t > 0 else 0

                # 4) Send broadcast
                if bot and not backfill_only:
                    msg = build_announcement(user, merged, overall_pct)
                    try:
                        await bot.send_message(
                            chat_id=user.telegram_user_id,
                            text=msg,
                        )
                        stats["broadcast_sent"] += 1
                        # Rate limiting
                        await asyncio.sleep(0.05)
                    except Exception as e:
                        stats["broadcast_failed"] += 1
                        logger.warning(f"  Broadcast failed for {user.telegram_user_id}: {e}")
                elif not send_broadcast:
                    # Dry-run: show what would be sent
                    if badges:
                        msg = build_announcement(user, merged, overall_pct)
                        logger.info(f"  [DRY-RUN] Would send to {user.telegram_user_id}:\n{msg[:120]}...")

            except Exception as e:
                stats["skipped"] += 1
                logger.error(f"  Error processing user {user.id}: {e}")

        await session.commit()

        if bot:
            await bot.session.close()

        logger.info(
            f"\n{'='*50}\n"
            f"RESULTS:\n"
            f"  Badges backfilled: {stats['backfilled']}\n"
            f"  Broadcast sent:    {stats['broadcast_sent']}\n"
            f"  Broadcast failed:  {stats['broadcast_failed']}\n"
            f"  Skipped/errors:    {stats['skipped']}\n"
            f"{'='*50}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill engagement badges & broadcast announcement")
    parser.add_argument("--send", action="store_true", help="Actually send broadcast messages")
    parser.add_argument("--backfill", action="store_true", help="Only backfill badges, no broadcast")
    args = parser.parse_args()

    if not args.send and not args.backfill:
        logger.info("🔍 DRY-RUN mode — use --send to broadcast, --backfill for badges only")

    asyncio.run(run_backfill(send_broadcast=args.send, backfill_only=args.backfill))
