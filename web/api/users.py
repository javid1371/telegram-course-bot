"""
User Management API Routes
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc

from database import async_session_maker
from database.models import User, UserProgress
from web.auth import get_current_user

router = APIRouter()


@router.get("")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    course_id: Optional[int] = None,
    platform: Optional[str] = None,
    _=Depends(get_current_user),
):
    async with async_session_maker() as session:
        query = select(User)

        # Filters
        if search:
            query = query.where(
                (User.first_name.ilike(f"%{search}%"))
                | (User.last_name.ilike(f"%{search}%"))
                | (User.username.ilike(f"%{search}%"))
            )
        if course_id:
            query = query.where(User.current_course_id == course_id)
        if platform:
            query = query.where(User.platform == platform)

        # Total count
        count_q = select(func.count()).select_from(query.subquery())
        total = (await session.execute(count_q)).scalar() or 0

        # Paginate
        query = query.order_by(desc(User.created_at)).offset((page - 1) * per_page).limit(per_page)
        result = await session.execute(query)
        users = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
            "items": [
                {
                    "id": u.id,
                    "telegram_user_id": u.telegram_user_id,
                    "username": u.username,
                    "first_name": u.first_name,
                    "last_name": u.last_name,
                    "platform": u.platform,
                    "is_active": u.is_active,
                    "is_completed": u.is_completed,
                    "current_course_id": u.current_course_id,
                    "current_lesson_id": u.current_lesson_id,
                    "lead_score": u.lead_score,
                    "registration_data": u.registration_data,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                    "last_activity_at": u.last_activity_at.isoformat() if u.last_activity_at else None,
                }
                for u in users
            ],
        }


@router.get("/{user_id}")
async def get_user(user_id: int, _=Depends(get_current_user)):
    async with async_session_maker() as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="کاربر یافت نشد")

        # Get progress records
        result = await session.execute(
            select(UserProgress).where(UserProgress.user_id == user_id)
        )
        progress = result.scalars().all()

        return {
            "id": user.id,
            "telegram_user_id": user.telegram_user_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "platform": user.platform,
            "is_active": user.is_active,
            "is_completed": user.is_completed,
            "current_course_id": user.current_course_id,
            "current_lesson_id": user.current_lesson_id,
            "lead_score": user.lead_score,
            "tags": user.tags,
            "registration_data": user.registration_data,
            "completed_courses": user.completed_courses,
            "double_speed_courses": user.double_speed_courses,
            "fast_track_courses": user.fast_track_courses,
            "assigned_owner_name": user.assigned_owner_name,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_activity_at": user.last_activity_at.isoformat() if user.last_activity_at else None,
            "progress": [
                {
                    "lesson_id": p.lesson_id,
                    "started_at": p.started_at.isoformat() if p.started_at else None,
                    "completed_at": p.completed_at.isoformat() if p.completed_at else None,
                }
                for p in progress
            ],
        }
