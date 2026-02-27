"""
User Management API Routes — Enhanced with full activity detail
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, desc, case, String
from sqlalchemy.orm import selectinload

from database import async_session_maker
from database.models import (
    User, UserProgress, Lesson, Course, QuizAttempt,
    FormResponse, ScheduledMessage,
)
from web.auth import get_current_user

router = APIRouter()


# ── Pydantic Schemas ──

class TagsUpdate(BaseModel):
    tags: List[str]

class BlockUpdate(BaseModel):
    blocked: bool


@router.get("")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    course_id: Optional[int] = None,
    platform: Optional[str] = None,
    lesson_id: Optional[int] = None,
    status: Optional[str] = None,
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
                | (User.telegram_user_id.cast(String).ilike(f"%{search}%"))
            )
        if course_id:
            query = query.where(User.current_course_id == course_id)
        if platform:
            query = query.where(User.platform == platform)
        if lesson_id:
            query = query.where(User.current_lesson_id == lesson_id)
        if status == "completed":
            query = query.where(User.is_completed == True)
        elif status == "active":
            query = query.where(User.is_active == True, User.is_completed == False)
        elif status == "inactive":
            query = query.where(User.is_active == False)

        # Total count
        count_q = select(func.count()).select_from(query.subquery())
        total = (await session.execute(count_q)).scalar() or 0

        # Paginate
        query = query.order_by(desc(User.created_at)).offset((page - 1) * per_page).limit(per_page)
        result = await session.execute(query)
        users = result.scalars().all()

        # Get progress counts for all users in this page
        user_ids = [u.id for u in users]
        progress_counts = {}
        if user_ids:
            prog_q = (
                select(
                    UserProgress.user_id,
                    func.count(UserProgress.id).label("total"),
                    func.count(UserProgress.completed_at).label("completed"),
                )
                .where(UserProgress.user_id.in_(user_ids))
                .group_by(UserProgress.user_id)
            )
            for row in (await session.execute(prog_q)).all():
                progress_counts[row.user_id] = {
                    "total": row.total,
                    "completed": row.completed,
                }

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
                    "is_shadow": u.is_shadow if hasattr(u, 'is_shadow') else False,
                    "current_course_id": u.current_course_id,
                    "current_lesson_id": u.current_lesson_id,
                    "lead_score": u.lead_score,
                    "registration_data": u.registration_data,
                    "assigned_owner_name": u.assigned_owner_name,
                    "progress_summary": progress_counts.get(u.id, {"total": 0, "completed": 0}),
                    "streak_days": u.streak_days if hasattr(u, 'streak_days') else 0,
                    "badges": u.badges if hasattr(u, 'badges') else [],
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                    "last_activity_at": u.last_activity_at.isoformat() if u.last_activity_at else None,
                }
                for u in users
            ],
        }


@router.get("/by-lesson")
async def users_by_lesson(
    course_id: Optional[int] = None,
    _=Depends(get_current_user),
):
    """Get lesson-based overview: how many users are at each lesson."""
    async with async_session_maker() as session:
        # Get all lessons (optionally filtered by course)
        lesson_q = select(Lesson).order_by(Lesson.course_id, Lesson.order)
        if course_id:
            lesson_q = lesson_q.where(Lesson.course_id == course_id)
        lessons = (await session.execute(lesson_q)).scalars().all()

        # Get courses for labels
        courses_result = (await session.execute(select(Course))).scalars().all()
        course_map = {c.id: c.title for c in courses_result}

        # Count users currently at each lesson
        current_q = (
            select(User.current_lesson_id, func.count(User.id))
            .where(User.current_lesson_id.isnot(None))
            .group_by(User.current_lesson_id)
        )
        if course_id:
            current_q = current_q.where(User.current_course_id == course_id)
        current_counts = dict((await session.execute(current_q)).all())

        # Count users who started each lesson
        started_q = (
            select(UserProgress.lesson_id, func.count(UserProgress.id))
            .group_by(UserProgress.lesson_id)
        )
        started_counts = dict((await session.execute(started_q)).all())

        # Count users who completed each lesson
        completed_q = (
            select(UserProgress.lesson_id, func.count(UserProgress.id))
            .where(UserProgress.completed_at.isnot(None))
            .group_by(UserProgress.lesson_id)
        )
        completed_counts = dict((await session.execute(completed_q)).all())

        # Quiz pass/fail counts per lesson
        quiz_q = (
            select(
                QuizAttempt.lesson_id,
                func.count(QuizAttempt.id).label("attempts"),
                func.sum(case((QuizAttempt.passed == True, 1), else_=0)).label("passed"),
            )
            .group_by(QuizAttempt.lesson_id)
        )
        quiz_stats = {}
        for row in (await session.execute(quiz_q)).all():
            quiz_stats[row.lesson_id] = {
                "attempts": row.attempts,
                "passed": int(row.passed or 0),
            }

        return {
            "courses": [{"id": c.id, "title": c.title} for c in courses_result],
            "lessons": [
                {
                    "id": l.id,
                    "title": l.title,
                    "lesson_number": l.lesson_number,
                    "course_id": l.course_id,
                    "course_title": course_map.get(l.course_id, "—"),
                    "has_quiz": l.quiz_data is not None,
                    "has_form": l.form_data is not None,
                    "current_users": current_counts.get(l.id, 0),
                    "started_users": started_counts.get(l.id, 0),
                    "completed_users": completed_counts.get(l.id, 0),
                    "quiz_stats": quiz_stats.get(l.id),
                }
                for l in lessons
            ],
        }


@router.get("/by-lesson/{lesson_id}")
async def users_at_lesson(
    lesson_id: int,
    _=Depends(get_current_user),
):
    """Get all users who have interacted with a specific lesson."""
    async with async_session_maker() as session:
        lesson = await session.get(Lesson, lesson_id)
        if not lesson:
            raise HTTPException(status_code=404, detail="درس یافت نشد")

        # Users currently at this lesson
        current_q = select(User).where(User.current_lesson_id == lesson_id)
        current_users = (await session.execute(current_q)).scalars().all()

        # Users who have progress for this lesson
        prog_q = (
            select(UserProgress)
            .where(UserProgress.lesson_id == lesson_id)
            .options(selectinload(UserProgress.user))
        )
        progress_records = (await session.execute(prog_q)).scalars().all()

        # Quiz attempts for this lesson
        quiz_q = select(QuizAttempt).where(QuizAttempt.lesson_id == lesson_id)
        quiz_attempts = (await session.execute(quiz_q)).scalars().all()
        quiz_by_user = {}
        for qa in quiz_attempts:
            quiz_by_user[qa.user_id] = {
                "score": qa.score,
                "passed": qa.passed,
                "answers": qa.answers,
                "created_at": qa.created_at.isoformat() if qa.created_at else None,
            }

        # Form responses for this lesson
        form_q = select(FormResponse).where(FormResponse.lesson_id == lesson_id)
        form_responses = (await session.execute(form_q)).scalars().all()
        form_by_user = {}
        for fr in form_responses:
            form_by_user[fr.user_id] = {
                "response_data": fr.response_data,
                "created_at": fr.created_at.isoformat() if fr.created_at else None,
            }

        # Build unique user set
        seen_user_ids = set()
        users_data = []

        for p in progress_records:
            u = p.user
            if u.id in seen_user_ids:
                continue
            seen_user_ids.add(u.id)
            users_data.append({
                "id": u.id,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "username": u.username,
                "platform": u.platform,
                "is_current": u.current_lesson_id == lesson_id,
                "started_at": p.started_at.isoformat() if p.started_at else None,
                "completed_at": p.completed_at.isoformat() if p.completed_at else None,
                "quiz": quiz_by_user.get(u.id),
                "form": form_by_user.get(u.id),
            })

        return {
            "lesson": {
                "id": lesson.id,
                "title": lesson.title,
                "lesson_number": lesson.lesson_number,
                "has_quiz": lesson.quiz_data is not None,
                "has_form": lesson.form_data is not None,
                "quiz_data": lesson.quiz_data,
                "form_data": lesson.form_data,
            },
            "users": users_data,
        }


@router.get("/{user_id}")
async def get_user(user_id: int, _=Depends(get_current_user)):
    async with async_session_maker() as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="کاربر یافت نشد")

        # Get progress records with lesson info
        prog_q = (
            select(UserProgress)
            .where(UserProgress.user_id == user_id)
            .options(selectinload(UserProgress.lesson))
            .order_by(UserProgress.started_at)
        )
        progress = (await session.execute(prog_q)).scalars().all()

        # Get quiz attempts
        quiz_q = (
            select(QuizAttempt)
            .where(QuizAttempt.user_id == user_id)
            .order_by(QuizAttempt.created_at)
        )
        quizzes = (await session.execute(quiz_q)).scalars().all()

        # Get quiz lesson titles
        quiz_lesson_ids = list(set(q.lesson_id for q in quizzes))
        quiz_lessons = {}
        if quiz_lesson_ids:
            lq = select(Lesson).where(Lesson.id.in_(quiz_lesson_ids))
            for les in (await session.execute(lq)).scalars().all():
                quiz_lessons[les.id] = {
                    "title": les.title,
                    "lesson_number": les.lesson_number,
                    "quiz_data": les.quiz_data,
                }

        # Get form responses
        form_q = (
            select(FormResponse)
            .where(FormResponse.user_id == user_id)
            .order_by(FormResponse.created_at)
        )
        forms = (await session.execute(form_q)).scalars().all()

        # Get form lesson titles + form_data
        form_lesson_ids = list(set(f.lesson_id for f in forms))
        form_lessons = {}
        if form_lesson_ids:
            flq = select(Lesson).where(Lesson.id.in_(form_lesson_ids))
            for les in (await session.execute(flq)).scalars().all():
                form_lessons[les.id] = {
                    "title": les.title,
                    "lesson_number": les.lesson_number,
                    "form_data": les.form_data,
                }

        # Get scheduled messages for this user (recent 50)
        msg_q = (
            select(ScheduledMessage)
            .where(ScheduledMessage.user_id == user_id)
            .order_by(desc(ScheduledMessage.created_at))
            .limit(50)
        )
        messages = (await session.execute(msg_q)).scalars().all()

        # Get course titles
        course_ids = list(set(
            [user.current_course_id] +
            [p.lesson.course_id for p in progress if p.lesson and p.lesson.course_id]
        ))
        course_map = {}
        if course_ids:
            cq = select(Course).where(Course.id.in_([c for c in course_ids if c]))
            for c in (await session.execute(cq)).scalars().all():
                course_map[c.id] = c.title

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
            "current_course_title": course_map.get(user.current_course_id, "—"),
            "current_lesson_id": user.current_lesson_id,
            "lead_score": user.lead_score,
            "tags": user.tags,
            "registration_data": user.registration_data,
            "completed_courses": user.completed_courses,
            "double_speed_courses": user.double_speed_courses,
            "fast_track_courses": user.fast_track_courses,
            "assigned_owner_name": user.assigned_owner_name,
            # Engagement
            "streak_days": user.streak_days if hasattr(user, 'streak_days') else 0,
            "best_streak": user.best_streak if hasattr(user, 'best_streak') else 0,
            "last_streak_date": user.last_streak_date.isoformat() if hasattr(user, 'last_streak_date') and user.last_streak_date else None,
            "badges": user.badges if hasattr(user, 'badges') else [],
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_activity_at": user.last_activity_at.isoformat() if user.last_activity_at else None,
            "progress": [
                {
                    "lesson_id": p.lesson_id,
                    "lesson_title": p.lesson.title if p.lesson else "—",
                    "lesson_number": p.lesson.lesson_number if p.lesson else None,
                    "course_id": p.lesson.course_id if p.lesson else None,
                    "course_title": course_map.get(p.lesson.course_id) if p.lesson else None,
                    "has_quiz": bool(p.lesson.quiz_data) if p.lesson else False,
                    "has_form": bool(p.lesson.form_data) if p.lesson else False,
                    "started_at": p.started_at.isoformat() if p.started_at else None,
                    "completed_at": p.completed_at.isoformat() if p.completed_at else None,
                    "confirmation_count": p.confirmation_count,
                    "time_spent": p.time_spent,
                }
                for p in progress
            ],
            "quizzes": [
                {
                    "lesson_id": q.lesson_id,
                    "lesson_title": quiz_lessons.get(q.lesson_id, {}).get("title", "—"),
                    "lesson_number": quiz_lessons.get(q.lesson_id, {}).get("lesson_number"),
                    "quiz_data": quiz_lessons.get(q.lesson_id, {}).get("quiz_data"),
                    "score": q.score,
                    "passed": q.passed,
                    "answers": q.answers,
                    "created_at": q.created_at.isoformat() if q.created_at else None,
                }
                for q in quizzes
            ],
            "forms": [
                {
                    "lesson_id": f.lesson_id,
                    "lesson_title": form_lessons.get(f.lesson_id, {}).get("title", "—"),
                    "lesson_number": form_lessons.get(f.lesson_id, {}).get("lesson_number"),
                    "form_data": form_lessons.get(f.lesson_id, {}).get("form_data"),
                    "response_data": f.response_data,
                    "created_at": f.created_at.isoformat() if f.created_at else None,
                }
                for f in forms
            ],
            "messages": [
                {
                    "id": m.id,
                    "message_type": m.message_type,
                    "message": m.message[:100] + "..." if len(m.message) > 100 else m.message,
                    "status": m.status.value,
                    "send_at": m.send_at.isoformat() if m.send_at else None,
                    "sent_at": m.sent_at.isoformat() if m.sent_at else None,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in messages
            ],
        }


# ── User Action Endpoints ──

@router.put("/{user_id}/tags")
async def update_user_tags(
    user_id: int,
    data: TagsUpdate,
    _=Depends(get_current_user),
):
    """Update user tags."""
    async with async_session_maker() as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="کاربر پیدا نشد")
        user.tags = data.tags
        await session.commit()
        return {"success": True, "tags": user.tags}


@router.put("/{user_id}/block")
async def block_unblock_user(
    user_id: int,
    data: BlockUpdate,
    _=Depends(get_current_user),
):
    """Block or unblock a user."""
    async with async_session_maker() as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="کاربر پیدا نشد")
        user.is_active = not data.blocked
        await session.commit()
        return {
            "success": True,
            "is_active": user.is_active,
            "detail": "کاربر مسدود شد" if data.blocked else "کاربر فعال شد",
        }


@router.post("/{user_id}/reset")
async def reset_user_progress(
    user_id: int,
    _=Depends(get_current_user),
):
    """Reset user progress — deletes all progress, quiz attempts, and form responses."""
    async with async_session_maker() as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="کاربر پیدا نشد")

        # Delete progress records
        prog_q = select(UserProgress).where(UserProgress.user_id == user_id)
        progress = (await session.execute(prog_q)).scalars().all()
        for p in progress:
            await session.delete(p)

        # Delete quiz attempts
        quiz_q = select(QuizAttempt).where(QuizAttempt.user_id == user_id)
        quizzes = (await session.execute(quiz_q)).scalars().all()
        for q in quizzes:
            await session.delete(q)

        # Delete form responses
        form_q = select(FormResponse).where(FormResponse.user_id == user_id)
        forms = (await session.execute(form_q)).scalars().all()
        for f in forms:
            await session.delete(f)

        # Reset user state
        user.current_lesson_id = None
        user.is_completed = False
        user.is_active = True
        user.lead_score = 0
        user.streak_days = 0
        user.best_streak = 0
        user.badges = []
        user.completed_courses = []
        user.double_speed_courses = []
        user.fast_track_courses = []

        await session.commit()
        return {"success": True, "detail": "پیشرفت کاربر ریست شد"}


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    _=Depends(get_current_user),
):
    """Delete a user and all related data."""
    async with async_session_maker() as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="کاربر پیدا نشد")

        # Delete all related records
        for model in [UserProgress, QuizAttempt, FormResponse, ScheduledMessage]:
            q = select(model).where(model.user_id == user_id)
            records = (await session.execute(q)).scalars().all()
            for r in records:
                await session.delete(r)

        await session.delete(user)
        await session.commit()
        return {"success": True, "detail": "کاربر حذف شد"}
