"""
Enhanced Analytics Service - statistics, reporting, and funnel analysis
with course-aware metrics.
"""
import logging
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    User, Lesson, UserProgress, DailyStat, Campaign,
    Course, QuizAttempt, FormResponse,
)

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

        # Completed (all courses done)
        completed_all = (await self.session.execute(
            select(func.count(User.id)).where(User.is_completed == True)
        )).scalar() or 0

        # Total lessons
        total_lessons = (await self.session.execute(
            select(func.count(Lesson.id)).where(Lesson.is_active == True)
        )).scalar() or 0

        # Total active courses
        total_courses = (await self.session.execute(
            select(func.count(Course.id)).where(Course.is_active == True)
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
        completion_rate = round((completed_all / total_users * 100) if total_users > 0 else 0, 1)

        # Total lesson completions today
        today_completions = (await self.session.execute(
            select(func.count(UserProgress.id)).where(
                UserProgress.completed_at >= today_start,
                UserProgress.completed_at.isnot(None)
            )
        )).scalar() or 0

        # Active in last 24h
        day_ago = datetime.utcnow() - timedelta(hours=24)
        active_24h = (await self.session.execute(
            select(func.count(User.id)).where(User.last_activity_at >= day_ago)
        )).scalar() or 0

        # Active in last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        active_7d = (await self.session.execute(
            select(func.count(User.id)).where(User.last_activity_at >= week_ago)
        )).scalar() or 0

        return {
            "total_users": total_users,
            "active_users": active_users,
            "completed_all": completed_all,
            "total_lessons": total_lessons,
            "total_courses": total_courses,
            "today_new_users": today_new,
            "week_new_users": week_new,
            "completion_rate": completion_rate,
            "today_completions": today_completions,
            "active_24h": active_24h,
            "active_7d": active_7d,
        }

    async def get_course_analytics(self, course_id: int) -> dict:
        """Get detailed analytics for a specific course"""
        # Course lesson count
        total_lessons = (await self.session.execute(
            select(func.count(Lesson.id)).where(
                Lesson.course_id == course_id,
                Lesson.is_active == True
            )
        )).scalar() or 0

        # Users enrolled in this course
        enrolled = (await self.session.execute(
            select(func.count(User.id)).where(User.current_course_id == course_id)
        )).scalar() or 0

        # Users who completed at least 1 lesson in this course
        lesson_ids_q = select(Lesson.id).where(Lesson.course_id == course_id)
        started_users = (await self.session.execute(
            select(func.count(func.distinct(UserProgress.user_id))).where(
                UserProgress.lesson_id.in_(lesson_ids_q)
            )
        )).scalar() or 0

        # Users who completed all lessons in this course
        completed_users = (await self.session.execute(
            select(func.count(func.distinct(UserProgress.user_id))).where(
                UserProgress.lesson_id.in_(lesson_ids_q),
                UserProgress.completed_at.isnot(None)
            )
        )).scalar() or 0

        # Quiz stats for this course
        quiz_count = (await self.session.execute(
            select(func.count(QuizAttempt.id)).where(
                QuizAttempt.lesson_id.in_(lesson_ids_q)
            )
        )).scalar() or 0

        quiz_pass_rate = 0
        if quiz_count > 0:
            passed = (await self.session.execute(
                select(func.count(QuizAttempt.id)).where(
                    QuizAttempt.lesson_id.in_(lesson_ids_q),
                    QuizAttempt.passed == True
                )
            )).scalar() or 0
            quiz_pass_rate = round(passed / quiz_count * 100, 1)

        avg_quiz_score = (await self.session.execute(
            select(func.avg(QuizAttempt.score)).where(
                QuizAttempt.lesson_id.in_(lesson_ids_q)
            )
        )).scalar()
        avg_quiz_score = round(avg_quiz_score, 1) if avg_quiz_score else 0

        return {
            "total_lessons": total_lessons,
            "enrolled": enrolled,
            "started_users": started_users,
            "completed_users": completed_users,
            "completion_rate": round(completed_users / started_users * 100 if started_users > 0 else 0, 1),
            "quiz_attempts": quiz_count,
            "quiz_pass_rate": quiz_pass_rate,
            "avg_quiz_score": avg_quiz_score,
        }

    async def get_funnel_analysis(self, course_id: int = None) -> List[dict]:
        """Get lesson-by-lesson funnel analysis (drop-off rates)"""
        query = select(Lesson).where(Lesson.is_active == True)
        if course_id:
            query = query.where(Lesson.course_id == course_id)
        query = query.order_by(Lesson.order)

        lessons = (await self.session.execute(query)).scalars().all()

        funnel = []
        prev_completed = None

        for lesson in lessons:
            started = (await self.session.execute(
                select(func.count(UserProgress.id)).where(
                    UserProgress.lesson_id == lesson.id
                )
            )).scalar() or 0

            completed = (await self.session.execute(
                select(func.count(UserProgress.id)).where(
                    UserProgress.lesson_id == lesson.id,
                    UserProgress.completed_at.isnot(None)
                )
            )).scalar() or 0

            # Drop-off from previous lesson
            if prev_completed is not None and prev_completed > 0:
                drop_off = round((1 - started / prev_completed) * 100, 1)
            else:
                drop_off = 0

            funnel.append({
                "lesson_id": lesson.id,
                "title": lesson.title,
                "order": lesson.order,
                "started": started,
                "completed": completed,
                "completion_rate": round(completed / started * 100 if started > 0 else 0, 1),
                "drop_off_rate": max(0, drop_off),
            })

            prev_completed = completed

        return funnel

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

        # Quiz stats for period
        quiz_attempts = (await self.session.execute(
            select(func.count(QuizAttempt.id)).where(
                QuizAttempt.created_at >= start_date
            )
        )).scalar() or 0

        quiz_passed = (await self.session.execute(
            select(func.count(QuizAttempt.id)).where(
                QuizAttempt.created_at >= start_date,
                QuizAttempt.passed == True
            )
        )).scalar() or 0

        return {
            "period_days": days,
            "new_users": new_users,
            "completions": completions,
            "active_users": active_users,
            "quiz_attempts": quiz_attempts,
            "quiz_pass_rate": round(quiz_passed / quiz_attempts * 100 if quiz_attempts > 0 else 0, 1),
        }

    async def get_lesson_completion_stats(self, course_id: int = None) -> List[dict]:
        """Get completion stats per lesson, optionally filtered by course"""
        query = select(Lesson).where(Lesson.is_active == True)
        if course_id:
            query = query.where(Lesson.course_id == course_id)
        query = query.order_by(Lesson.order)

        lessons = (await self.session.execute(query)).scalars().all()

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

            # Average quiz score for this lesson
            avg_score = None
            quiz_attempts = (await self.session.execute(
                select(func.count(QuizAttempt.id)).where(
                    QuizAttempt.lesson_id == lesson.id
                )
            )).scalar() or 0

            if quiz_attempts > 0:
                avg_score = (await self.session.execute(
                    select(func.avg(QuizAttempt.score)).where(
                        QuizAttempt.lesson_id == lesson.id
                    )
                )).scalar()
                avg_score = round(avg_score, 1) if avg_score else None

            stats.append({
                "lesson_id": lesson.id,
                "title": lesson.title,
                "order": lesson.order,
                "started": started,
                "completed": completed,
                "completion_rate": round((completed / started * 100) if started > 0 else 0, 1),
                "quiz_attempts": quiz_attempts,
                "avg_quiz_score": avg_score,
            })

        return stats

    async def save_daily_stats(self):
        """Save daily statistics snapshot"""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        existing = (await self.session.execute(
            select(DailyStat).where(DailyStat.date == today)
        )).scalar_one_or_none()

        stats = await self.get_dashboard_stats()

        if existing:
            existing.new_users = stats["today_new_users"]
            existing.active_users = stats["active_users"]
            existing.completed_lessons = stats["today_completions"]
            existing.completed_courses = stats["completed_all"]
        else:
            daily = DailyStat(
                date=today,
                new_users=stats["today_new_users"],
                active_users=stats["active_users"],
                completed_lessons=stats["today_completions"],
                completed_courses=stats["completed_all"],
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
