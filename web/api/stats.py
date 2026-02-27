"""
Dashboard Statistics API Routes
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func

from database import async_session_maker
from database.models import User, Course, Lesson, UserProgress, ScheduledMessage
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

        # ── Engagement stats ──
        # Average streak
        avg_streak = (await session.execute(
            select(func.avg(User.streak_days)).where(User.streak_days > 0)
        )).scalar() or 0

        # Users with active streaks (streak > 0)
        active_streaks = (await session.execute(
            select(func.count(User.id)).where(User.streak_days > 0)
        )).scalar() or 0

        # Best streak across all users
        max_streak = (await session.execute(
            select(func.max(User.best_streak))
        )).scalar() or 0

        # Badge distribution
        badge_holders = (await session.execute(
            select(func.count(User.id)).where(
                User.badges.isnot(None),
                func.json_array_length(User.badges) > 0
            )
        )).scalar() or 0

        # SMS stats (from scheduled messages with type 'sms_nudge')
        sms_sent = (await session.execute(
            select(func.count(ScheduledMessage.id)).where(
                ScheduledMessage.message_type == 'sms_nudge'
            )
        )).scalar() or 0

        # Top streaks leaderboard (top 10)
        top_streaks_q = (
            select(
                User.first_name, User.last_name,
                User.streak_days, User.best_streak, User.badges
            )
            .where(User.best_streak > 0)
            .order_by(User.best_streak.desc(), User.streak_days.desc())
            .limit(10)
        )
        top_streaks = []
        for row in (await session.execute(top_streaks_q)).all():
            top_streaks.append({
                "name": f"{row.first_name or ''} {row.last_name or ''}".strip() or "—",
                "streak_days": row.streak_days or 0,
                "best_streak": row.best_streak or 0,
                "badges_count": len(row.badges) if row.badges else 0,
            })

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
            "engagement": {
                "avg_streak": round(float(avg_streak), 1),
                "active_streaks": active_streaks,
                "max_streak": max_streak,
                "badge_holders": badge_holders,
                "sms_sent": sms_sent,
                "top_streaks": top_streaks,
            },
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
