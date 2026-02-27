"""
One-time backfill script: calculate streaks and award badges to existing users
based on their historical lesson completion data.

Usage:
    python backfill_engagement.py              # dry-run (show what would change)
    python backfill_engagement.py --backfill   # actually update DB
    python backfill_engagement.py --send       # backfill + send broadcast
"""
import asyncio
import argparse
import logging
import sys
from datetime import datetime, date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

# ── Bootstrap the app ──
from database import async_session_maker
from database.models import User, UserProgress
from services.lesson_service import LessonService
from services.engagement_service import EngagementService, BADGES
import config


# ═══════════════════════════════════════════
# HISTORICAL STREAK CALCULATION
# ═══════════════════════════════════════════

async def compute_streak_for_user(session: AsyncSession, user_id: int) -> dict:
    """Calculate streak from historical completion dates.
    Returns {"streak_days": N, "best_streak": N, "last_streak_date": date|None}
    """
    result = await session.execute(
        select(UserProgress.completed_at)
        .where(UserProgress.user_id == user_id,
               UserProgress.completed_at.isnot(None))
        .order_by(UserProgress.completed_at)
    )
    completion_dates = set()
    for row in result.scalars().all():
        if row:
            completion_dates.add(row.date())

    if not completion_dates:
        return {"streak_days": 0, "best_streak": 0, "last_streak_date": None}

    sorted_dates = sorted(completion_dates)
    today = date.today()

    # Calculate best streak ever
    best_streak = 1
    current_streak = 1
    streaks = []  # list of (streak_length, last_date)

    for i in range(1, len(sorted_dates)):
        diff = (sorted_dates[i] - sorted_dates[i-1]).days
        if diff == 1:
            current_streak += 1
        elif diff > 1:
            streaks.append((current_streak, sorted_dates[i-1]))
            best_streak = max(best_streak, current_streak)
            current_streak = 1
        # diff == 0: same day, skip

    # Don't forget the last streak
    streaks.append((current_streak, sorted_dates[-1]))
    best_streak = max(best_streak, current_streak)

    # Calculate current active streak (must include today or yesterday)
    last_date = sorted_dates[-1]
    if last_date == today or (today - last_date).days == 1:
        # Active streak — count backwards from last_date
        active_streak = 1
        for i in range(len(sorted_dates) - 2, -1, -1):
            diff = (sorted_dates[i+1] - sorted_dates[i]).days
            if diff == 1:
                active_streak += 1
            else:
                break
        streak_days = active_streak
    else:
        # Streak is broken
        streak_days = 0

    return {
        "streak_days": streak_days,
        "best_streak": best_streak,
        "last_streak_date": last_date,
    }


# ═══════════════════════════════════════════
# BADGE COMPUTATION
# ═══════════════════════════════════════════

async def compute_badges_for_user(
    session: AsyncSession, user: User,
    streak_days: int = 0, best_streak: int = 0
) -> list:
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

    # Streak-based badges (can now be retroactive!)
    effective_streak = max(streak_days, best_streak)
    if effective_streak >= 5:
        badges.add("streak_5")
    if effective_streak >= 10:
        badges.add("streak_10")

    # fast_learner: check if any lesson was completed in < 1 hour
    result = await session.execute(
        select(UserProgress)
        .where(
            UserProgress.user_id == user.id,
            UserProgress.completed_at.isnot(None),
            UserProgress.started_at.isnot(None),
        )
    )
    for up in result.scalars().all():
        if up.started_at and up.completed_at:
            duration = (up.completed_at - up.started_at).total_seconds()
            if 0 < duration < 3600:
                badges.add("fast_learner")
                break

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
        # Fetch all active users
        result = await session.execute(
            select(User).where(User.is_active == True)
        )
        users = list(result.scalars().all())
        logger.info(f"Found {len(users)} active users to process")

        lesson_service = LessonService(session)
        stats = {
            "streak_updated": 0,
            "badges_updated": 0,
            "broadcast_sent": 0,
            "broadcast_failed": 0,
            "skipped": 0,
        }

        bot = None
        if send_broadcast and not backfill_only:
            from aiogram import Bot
            bot = Bot(token=config.BOT_TOKEN)

        for user in users:
            try:
                changed = False

                # 1) Compute historical streak
                streak_data = await compute_streak_for_user(session, user.id)
                if (streak_data["streak_days"] != (user.streak_days or 0) or
                    streak_data["best_streak"] != (user.best_streak or 0) or
                    streak_data["last_streak_date"] != user.last_streak_date):
                    user.streak_days = streak_data["streak_days"]
                    user.best_streak = streak_data["best_streak"]
                    user.last_streak_date = streak_data["last_streak_date"]
                    stats["streak_updated"] += 1
                    changed = True
                    logger.info(
                        f"  User {user.telegram_user_id} ({user.first_name}): "
                        f"streak={streak_data['streak_days']} "
                        f"best={streak_data['best_streak']} "
                        f"last={streak_data['last_streak_date']}"
                    )

                # 2) Compute badges (including streak-based)
                badges = await compute_badges_for_user(
                    session, user,
                    streak_days=streak_data["streak_days"],
                    best_streak=streak_data["best_streak"],
                )
                existing = set(user.badges or [])
                merged = sorted(existing | set(badges))
                if merged != sorted(existing):
                    user.badges = merged
                    stats["badges_updated"] += 1
                    changed = True
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
                if bot and not backfill_only and changed:
                    msg = build_announcement(user, merged, overall_pct)
                    try:
                        await bot.send_message(
                            chat_id=user.telegram_user_id,
                            text=msg,
                        )
                        stats["broadcast_sent"] += 1
                        await asyncio.sleep(0.05)
                    except Exception as e:
                        stats["broadcast_failed"] += 1
                        logger.warning(f"  Broadcast failed for {user.telegram_user_id}: {e}")
                elif not send_broadcast and changed:
                    # Dry-run: show what would be sent
                    logger.info(
                        f"  [DRY-RUN] User {user.telegram_user_id}: "
                        f"streak={streak_data['streak_days']}, "
                        f"best={streak_data['best_streak']}, "
                        f"badges={merged}"
                    )

            except Exception as e:
                stats["skipped"] += 1
                logger.error(f"  Error processing user {user.id}: {e}")

        await session.commit()

        if bot:
            await bot.session.close()

        logger.info(
            f"\n{'='*50}\n"
            f"RESULTS:\n"
            f"  Streaks updated:   {stats['streak_updated']}\n"
            f"  Badges updated:    {stats['badges_updated']}\n"
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
