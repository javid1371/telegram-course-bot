"""
Analytics service - handles statistics and reporting
"""
import logging
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Lesson, UserProgress, DailyStat, Campaign

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for analytics and statistics"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_dashboard_stats(self) -> dict:
        """Get overall dashboard stats"""
        # Total users
        total_users = (await self.session.execute(
            select(func.count(User.id))
        )).scalar() or 0

        # Active users
        active_users = (await self.session.execute(
            select(func.count(User.id)).where(User.is_active == True)
        )).scalar() or 0

        # Completed courses
        completed_courses = (await self.session.execute(
            select(func.count(User.id)).where(User.is_completed == True)
        )).scalar() or 0

        # Total lessons
        total_lessons = (await self.session.execute(
            select(func.count(Lesson.id)).where(Lesson.is_active == True)
        )).scalar() or 0

        # Today's new users
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_new = (await self.session.execute(
            select(func.count(User.id)).where(User.created_at >= today_start)
        )).scalar() or 0

        # This week's new users
        week_start = today_start - timedelta(days=today_start.weekday())
        week_new = (await self.session.execute(
            select(func.count(User.id)).where(User.created_at >= week_start)
        )).scalar() or 0

        # Completion rate
        completion_rate = round((completed_courses / total_users * 100) if total_users > 0 else 0, 1)

        # Total lesson completions today
        today_completions = (await self.session.execute(
            select(func.count(UserProgress.id)).where(
                UserProgress.completed_at >= today_start,
                UserProgress.completed_at.isnot(None)
            )
        )).scalar() or 0

        return {
            "total_users": total_users,
            "active_users": active_users,
            "completed_courses": completed_courses,
            "total_lessons": total_lessons,
            "today_new_users": today_new,
            "week_new_users": week_new,
            "completion_rate": completion_rate,
            "today_completions": today_completions,
        }

    async def get_period_stats(self, days: int = 7) -> dict:
        """Get statistics for a specific period"""
        start_date = datetime.utcnow() - timedelta(days=days)

        new_users = (await self.session.execute(
            select(func.count(User.id)).where(User.created_at >= start_date)
        )).scalar() or 0

        completions = (await self.session.execute(
            select(func.count(UserProgress.id)).where(
                UserProgress.completed_at >= start_date,
                UserProgress.completed_at.isnot(None)
            )
        )).scalar() or 0

        active_users = (await self.session.execute(
            select(func.count(User.id)).where(User.last_activity_at >= start_date)
        )).scalar() or 0

        return {
            "period_days": days,
            "new_users": new_users,
            "completions": completions,
            "active_users": active_users,
        }

    async def get_lesson_completion_stats(self) -> List[dict]:
        """Get completion stats per lesson"""
        lessons = (await self.session.execute(
            select(Lesson).where(Lesson.is_active == True).order_by(Lesson.order)
        )).scalars().all()

        stats = []
        for lesson in lessons:
            completed = (await self.session.execute(
                select(func.count(UserProgress.id)).where(
                    UserProgress.lesson_id == lesson.id,
                    UserProgress.completed_at.isnot(None)
                )
            )).scalar() or 0

            started = (await self.session.execute(
                select(func.count(UserProgress.id)).where(
                    UserProgress.lesson_id == lesson.id
                )
            )).scalar() or 0

            stats.append({
                "lesson_id": lesson.id,
                "title": lesson.title,
                "order": lesson.order,
                "started": started,
                "completed": completed,
                "completion_rate": round((completed / started * 100) if started > 0 else 0, 1),
            })

        return stats

    async def save_daily_stats(self):
        """Save daily statistics snapshot"""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        # Check if already saved today
        existing = (await self.session.execute(
            select(DailyStat).where(DailyStat.date == today)
        )).scalar_one_or_none()

        stats = await self.get_dashboard_stats()

        if existing:
            existing.new_users = stats["today_new_users"]
            existing.active_users = stats["active_users"]
            existing.completed_lessons = stats["today_completions"]
            existing.completed_courses = stats["completed_courses"]
        else:
            daily = DailyStat(
                date=today,
                new_users=stats["today_new_users"],
                active_users=stats["active_users"],
                completed_lessons=stats["today_completions"],
                completed_courses=stats["completed_courses"],
            )
            self.session.add(daily)

        await self.session.commit()

    async def get_campaign_stats(self) -> List[dict]:
        """Get campaign statistics"""
        campaigns = (await self.session.execute(
            select(Campaign).order_by(Campaign.created_at.desc())
        )).scalars().all()

        stats = []
        for campaign in campaigns:
            users_count = (await self.session.execute(
                select(func.count(User.id)).where(
                    User.source_campaign == campaign.tracking_code
                )
            )).scalar() or 0

            completed_count = (await self.session.execute(
                select(func.count(User.id)).where(
                    User.source_campaign == campaign.tracking_code,
                    User.is_completed == True,
                )
            )).scalar() or 0

            stats.append({
                "name": campaign.name,
                "code": campaign.tracking_code,
                "users": users_count,
                "completed": completed_count,
                "conversion_rate": round((completed_count / users_count * 100) if users_count > 0 else 0, 1),
            })

        return stats
