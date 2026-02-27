"""
Engagement Service — streak tracking, badges, peer comparison,
lesson preview, progress card builder.
"""
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, UserProgress, Lesson
from services.lesson_service import LessonService
from messages import USER

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# BADGE DEFINITIONS
# ═══════════════════════════════════════════

BADGES = {
    "starter": {"label": "شروع‌کننده 🌱", "description": "اولین درس تکمیل شد"},
    "motivated": {"label": "با‌انگیزه 🔥", "description": "۳ درس متوالی بدون وقفه"},
    "streak_5": {"label": "پنج‌ستاره ⭐", "description": "۵ روز متوالی فعال"},
    "halfway": {"label": "نیمه‌راه 🏔", "description": "۵۰% دوره تکمیل شد"},
    "fast_learner": {"label": "سریع‌خوان ⚡", "description": "تکمیل درس در کمتر از ۱ ساعت"},
    "streak_10": {"label": "ده‌ستاره 🌟", "description": "۱۰ روز متوالی فعال"},
    "almost": {"label": "یک قدم مونده 🏁", "description": "۹۰% دوره تکمیل شد"},
    "graduate": {"label": "فارغ‌التحصیل 🎓", "description": "دوره کامل تکمیل شد"},
}


class EngagementService:
    """Handles streak, badges, peer comparison, lesson preview, progress card"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ═══════════════════════════════════════
    # STREAK
    # ═══════════════════════════════════════

    async def update_streak(self, user: User) -> dict:
        """Update user's streak after completing a lesson.
        Returns {"streak": N, "best": N, "is_new_best": bool}
        """
        today = date.today()
        last = user.last_streak_date

        if last == today:
            # Already counted today
            return {
                "streak": user.streak_days,
                "best": user.best_streak,
                "is_new_best": False,
            }

        if last and (today - last).days == 1:
            # Consecutive day
            user.streak_days = (user.streak_days or 0) + 1
        elif last and (today - last).days == 0:
            pass  # same day (shouldn't reach here but safe guard)
        else:
            # Streak broken (or first time)
            user.streak_days = 1

        user.last_streak_date = today
        is_new_best = user.streak_days > (user.best_streak or 0)
        if is_new_best:
            user.best_streak = user.streak_days

        return {
            "streak": user.streak_days,
            "best": user.best_streak,
            "is_new_best": is_new_best,
        }

    # ═══════════════════════════════════════
    # BADGES
    # ═══════════════════════════════════════

    async def check_and_award_badges(
        self, user: User, progress: dict, streak: int, lesson_time_seconds: Optional[int] = None
    ) -> list:
        """Check all badge conditions, award new ones.
        Returns list of newly earned badge keys.
        """
        current_badges = set(user.badges or [])
        new_badges = []

        completed = progress.get("completed", 0)
        total = progress.get("total", 1)
        percent = progress.get("progress_percent", 0)
        remaining = progress.get("remaining", total)

        # starter: first lesson completed
        if completed >= 1 and "starter" not in current_badges:
            new_badges.append("starter")

        # motivated: 3+ lessons completed
        if completed >= 3 and "motivated" not in current_badges:
            new_badges.append("motivated")

        # streak_5
        if streak >= 5 and "streak_5" not in current_badges:
            new_badges.append("streak_5")

        # streak_10
        if streak >= 10 and "streak_10" not in current_badges:
            new_badges.append("streak_10")

        # halfway: 50%+
        if percent >= 50 and "halfway" not in current_badges:
            new_badges.append("halfway")

        # almost: 90%+
        if percent >= 90 and "almost" not in current_badges:
            new_badges.append("almost")

        # fast_learner: completed a lesson in < 1 hour
        if lesson_time_seconds and lesson_time_seconds < 3600 and "fast_learner" not in current_badges:
            new_badges.append("fast_learner")

        # graduate: 100%
        if remaining == 0 and "graduate" not in current_badges:
            new_badges.append("graduate")

        if new_badges:
            updated = list(current_badges | set(new_badges))
            user.badges = updated

        return new_badges

    # ═══════════════════════════════════════
    # PEER COMPARISON
    # ═══════════════════════════════════════

    async def get_peer_percentile(self, completed_lessons: int, course_id: Optional[int] = None) -> int:
        """Calculate what top X% this user is in.
        Returns e.g. 30 meaning "top 30%".
        """
        # Count total active users (who started at least 1 lesson)
        base_query = (
            select(func.count(func.distinct(UserProgress.user_id)))
            .join(User, User.id == UserProgress.user_id)
            .where(User.is_active == True)
        )
        if course_id:
            base_query = base_query.join(Lesson, Lesson.id == UserProgress.lesson_id).where(
                Lesson.course_id == course_id
            )
        total_result = await self.session.execute(base_query)
        total_users = total_result.scalar() or 1

        # Count users who completed >= this many lessons
        ahead_query = (
            select(func.count())
            .select_from(
                select(UserProgress.user_id)
                .where(UserProgress.completed_at.isnot(None))
                .join(User, User.id == UserProgress.user_id)
                .where(User.is_active == True)
            )
        )
        if course_id:
            # Users with at least `completed_lessons` completed in this course
            sub = (
                select(UserProgress.user_id, func.count().label("cnt"))
                .where(UserProgress.completed_at.isnot(None))
                .join(Lesson, Lesson.id == UserProgress.lesson_id)
                .where(Lesson.course_id == course_id)
                .group_by(UserProgress.user_id)
                .having(func.count() >= completed_lessons)
                .subquery()
            )
        else:
            sub = (
                select(UserProgress.user_id, func.count().label("cnt"))
                .where(UserProgress.completed_at.isnot(None))
                .group_by(UserProgress.user_id)
                .having(func.count() >= completed_lessons)
                .subquery()
            )
        ahead_result = await self.session.execute(select(func.count()).select_from(sub))
        users_at_or_ahead = ahead_result.scalar() or 1

        percentile = max(1, round((users_at_or_ahead / total_users) * 100))
        return percentile

    # ═══════════════════════════════════════
    # LESSON PREVIEW
    # ═══════════════════════════════════════

    async def get_next_lesson_preview(self, user_id: int, course_id: Optional[int] = None) -> Optional[str]:
        """Get the title of the next lesson (for teaser after completion)."""
        lesson_service = LessonService(self.session)
        next_lesson = await lesson_service.get_next_lesson_for_user(user_id, course_id=course_id)
        if next_lesson:
            return next_lesson.title
        return None

    # ═══════════════════════════════════════
    # PROGRESS BAR BUILDER
    # ═══════════════════════════════════════

    @staticmethod
    def build_progress_bar(percent: int, length: int = 10) -> str:
        """Build a visual progress bar: ████████░░"""
        filled = int(percent / (100 / length))
        filled = min(filled, length)
        return "█" * filled + "░" * (length - filled)

    # ═══════════════════════════════════════
    # FULL PROGRESS CARD (after lesson complete)
    # ═══════════════════════════════════════

    async def build_lesson_complete_card(
        self,
        user: User,
        lesson_num: int,
        progress: dict,
        streak_info: dict,
        new_badges: list,
        course_id: Optional[int] = None,
        delay_minutes: int = 0,
    ) -> str:
        """Build the rich completion card shown after confirming a lesson."""

        completed = progress.get("completed", 0)
        total = progress.get("total", 1)
        percent = progress.get("progress_percent", 0)
        remaining = progress.get("remaining", 0)

        # Streak line
        streak = streak_info.get("streak", 0)
        best = streak_info.get("best", 0)
        if streak > 0:
            streak_line = USER["streak_line"].format(streak=streak)
            if best > streak:
                streak_line += USER["streak_best"].format(best=best)
        else:
            streak_line = USER["streak_broken"]

        # Progress bar
        progress_bar = self.build_progress_bar(percent)

        # Remaining text
        if remaining == 1:
            remaining_text = USER["remaining_one"]
        elif remaining > 1 and remaining <= 5:
            remaining_text = USER["remaining_lessons"].format(remaining=remaining)
        else:
            remaining_text = ""

        # Badge text
        badge_text = ""
        if new_badges:
            for bk in new_badges:
                badge_info = BADGES.get(bk, {})
                badge_text += USER["badge_unlocked"].format(badge_label=badge_info.get("label", bk))

        # Peer comparison (only show if > 1 lesson completed)
        peer_text = ""
        if completed >= 2:
            top_pct = await self.get_peer_percentile(completed, course_id)
            if top_pct <= 70:  # Only show if in top 70%
                peer_text = USER["peer_comparison"].format(top_percent=top_pct)

        # Lesson preview
        preview_text = ""
        if remaining > 0:
            next_title = await self.get_next_lesson_preview(user.id, course_id)
            if next_title:
                preview_text = USER["next_lesson_preview"].format(next_title=next_title)
                if delay_minutes > 0:
                    from utils.helpers import format_duration
                    delivery_info = format_duration(delay_minutes * 60)
                    preview_text += USER["next_lesson_preview_timed"].format(delivery_info=delivery_info)

        card = USER["lesson_complete_card"].format(
            lesson_num=lesson_num,
            streak_line=streak_line,
            progress_bar=progress_bar,
            percent=percent,
            completed=completed,
            total=total,
            remaining_text=remaining_text,
            badge_text=badge_text,
            peer_text=peer_text,
            preview_text=preview_text,
        )

        return card

    # ═══════════════════════════════════════
    # PROGRESS PAGE CARD (for "📊 پیشرفت من")
    # ═══════════════════════════════════════

    def build_progress_page(
        self,
        user: User,
        courses_progress: list,
        total_completed: int,
        total_all: int,
        overall_pct: int,
    ) -> str:
        """Build the rich progress page with streak + badges."""

        text = USER["progress_header"]

        # Streak section
        streak = user.streak_days or 0
        best = user.best_streak or 0
        if streak > 0:
            text += USER["streak_line"].format(streak=streak)
            if best > streak:
                text += USER["streak_best"].format(best=best)
            text += "\n\n"
        else:
            text += USER["streak_broken"] + "\n\n"

        # Courses
        for cp in courses_progress:
            bar = self.build_progress_bar(cp["percent"])
            status = USER["progress_course_status"] if cp["is_done"] else f"{cp['percent']}%"
            text += (
                f"📚 <b>{cp['title']}</b> — {status}\n"
                f"{bar}\n"
                f"✅ {cp['completed']}/{cp['total']} درس\n\n"
            )

        text += USER["progress_summary"].format(
            completed=total_completed, total=total_all, percent=overall_pct
        )

        # Badges section
        earned = set(user.badges or [])
        badge_text = USER["badge_header"]
        has_any = False
        for key, info in BADGES.items():
            if key in earned:
                badge_text += USER["badge_earned"].format(label=info["label"]) + "  "
                has_any = True
            else:
                badge_text += USER["badge_locked"].format(label=info["label"]) + "  "
        if has_any or earned:
            text += badge_text

        if user.is_completed:
            text += "\n\n" + USER["progress_all_done"]

        return text
