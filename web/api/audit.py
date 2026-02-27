"""
CRM Audit API — Provides bot user data for comparison with Didar CRM.
Used by the n8n audit workflow to verify sync completeness.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from database import async_session_maker
from database.models import User, Lesson, UserProgress, Course
from web.auth import get_current_user

router = APIRouter()


def _extract_phone(registration_data: Optional[dict]) -> Optional[str]:
    """Extract phone number from registration_data, normalised to digits."""
    if not registration_data:
        return None
    for key in ("phone", "mobile", "شماره تماس", "شماره موبایل", "تلفن"):
        val = registration_data.get(key)
        if val:
            # Strip spaces, dashes, convert Persian/Arabic digits
            digits = ""
            for ch in str(val):
                if ch.isdigit():
                    digits += ch
                elif ch in "۰۱۲۳۴۵۶۷۸۹":
                    digits += str("۰۱۲۳۴۵۶۷۸۹".index(ch))
                elif ch in "٠١٢٣٤٥٦٧٨٩":
                    digits += str("٠١٢٣٤٥٦٧٨٩".index(ch))
            if digits:
                return digits
    return None


@router.get("/users")
async def audit_users(_=Depends(get_current_user)):
    """
    Return all bot users with essential data for CRM audit comparison.

    For each user returns:
    - id, telegram_user_id, platform
    - phone (extracted from registration_data)
    - first_name, last_name
    - current_lesson_number (from Lesson join)
    - total lessons in course
    - completed_lessons_count
    - is_completed, is_active
    - lead_score
    - assigned_owner_name
    - registration_data (full, for field-level comparison)
    - tags
    - created_at
    """
    async with async_session_maker() as session:
        # Get all non-shadow users with their current lesson info
        query = (
            select(User)
            .where(User.is_shadow == False)
            .options(
                selectinload(User.current_lesson),
                selectinload(User.current_course_rel),
            )
            .order_by(User.id)
        )
        users = (await session.execute(query)).scalars().all()
        user_ids = [u.id for u in users]

        # Get completed lesson counts per user
        completed_counts = {}
        if user_ids:
            prog_q = (
                select(
                    UserProgress.user_id,
                    func.count(UserProgress.id).label("completed"),
                )
                .where(
                    UserProgress.user_id.in_(user_ids),
                    UserProgress.completed_at.isnot(None),
                )
                .group_by(UserProgress.user_id)
            )
            for row in (await session.execute(prog_q)).all():
                completed_counts[row.user_id] = row.completed

        # Get total lesson count per course
        course_lesson_counts = {}
        lesson_count_q = (
            select(
                Lesson.course_id,
                func.count(Lesson.id).label("total"),
            )
            .where(Lesson.is_active == True)
            .group_by(Lesson.course_id)
        )
        for row in (await session.execute(lesson_count_q)).all():
            course_lesson_counts[row.course_id] = row.total

        items = []
        for u in users:
            phone = _extract_phone(u.registration_data)
            lesson_number = None
            if u.current_lesson:
                lesson_number = u.current_lesson.lesson_number

            total_lessons = course_lesson_counts.get(u.current_course_id, 0)
            completed_count = completed_counts.get(u.id, 0)

            # Calculate progress percentage
            progress_pct = 0
            if total_lessons > 0:
                progress_pct = round((completed_count / total_lessons) * 100, 1)

            items.append({
                "id": u.id,
                "telegram_user_id": u.telegram_user_id,
                "platform": u.platform,
                "phone": phone,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "current_lesson_number": lesson_number,
                "current_course_id": u.current_course_id,
                "total_lessons": total_lessons,
                "completed_lessons": completed_count,
                "progress_pct": progress_pct,
                "is_completed": u.is_completed,
                "is_active": u.is_active,
                "lead_score": u.lead_score,
                "assigned_owner_name": u.assigned_owner_name,
                "registration_data": u.registration_data,
                "tags": u.tags or [],
                "created_at": u.created_at.isoformat() if u.created_at else None,
            })

        return {
            "total": len(items),
            "users_with_phone": sum(1 for i in items if i["phone"]),
            "users_without_phone": sum(1 for i in items if not i["phone"]),
            "items": items,
        }
