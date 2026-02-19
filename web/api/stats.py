"""
Dashboard Statistics API Routes
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func

from database import async_session_maker
from database.models import User, Course, Lesson, UserProgress
from web.auth import get_current_user

router = APIRouter()


@router.get("")
async def get_stats(_=Depends(get_current_user)):
    async with async_session_maker() as session:
        # Total users
        total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0

        # Active users (last 7 days)
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        active_users = (await session.execute(
            select(func.count(User.id)).where(User.last_activity_at >= week_ago)
        )).scalar() or 0

        # Total courses
        total_courses = (await session.execute(select(func.count(Course.id)))).scalar() or 0

        # Total lessons
        total_lessons = (await session.execute(select(func.count(Lesson.id)))).scalar() or 0

        # Completed users
        completed_users = (await session.execute(
            select(func.count(User.id)).where(User.is_completed == True)
        )).scalar() or 0

        # New users today
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        new_today = (await session.execute(
            select(func.count(User.id)).where(User.created_at >= today_start)
        )).scalar() or 0

        # New users this week
        new_week = (await session.execute(
            select(func.count(User.id)).where(User.created_at >= week_ago)
        )).scalar() or 0

        # Users per platform
        platform_stats = (await session.execute(
            select(User.platform, func.count(User.id)).group_by(User.platform)
        )).all()

        # Lessons completed today
        lessons_today = (await session.execute(
            select(func.count(UserProgress.id)).where(
                UserProgress.completed_at >= today_start
            )
        )).scalar() or 0

        # Daily registrations (last 14 days)
        two_weeks_ago = datetime.now(timezone.utc) - timedelta(days=14)
        daily_regs = (await session.execute(
            select(
                func.date_trunc('day', User.created_at).label('day'),
                func.count(User.id).label('count')
            )
            .where(User.created_at >= two_weeks_ago)
            .group_by('day')
            .order_by('day')
        )).all()

        return {
            "total_users": total_users,
            "active_users_7d": active_users,
            "total_courses": total_courses,
            "total_lessons": total_lessons,
            "completed_users": completed_users,
            "new_today": new_today,
            "new_this_week": new_week,
            "lessons_completed_today": lessons_today,
            "platforms": {row[0]: row[1] for row in platform_stats},
            "daily_registrations": [
                {"date": row[0].isoformat() if row[0] else None, "count": row[1]}
                for row in daily_regs
            ],
        }


@router.get("/funnel")
async def get_funnel(
    course_id: Optional[int] = Query(None),
    _=Depends(get_current_user),
):
    """Lesson-by-lesson funnel analysis (drop-off rates)."""
    from services.analytics_service import AnalyticsService

    async with async_session_maker() as session:
        analytics = AnalyticsService(session)
        funnel = await analytics.get_funnel_analysis(course_id=course_id)

        # Also get list of courses for the filter dropdown
        courses_q = await session.execute(
            select(Course.id, Course.title).order_by(Course.id)
        )
        courses_list = [{"id": row[0], "title": row[1]} for row in courses_q.all()]

        return {"funnel": funnel, "courses": courses_list}
