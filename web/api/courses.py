"""
Course CRUD API Routes
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func

from database import async_session_maker
from database.models import Course, Lesson, User
from web.auth import get_current_user

router = APIRouter()


class CourseCreate(BaseModel):
    title: str
    description: Optional[str] = None
    is_active: bool = True
    order: int = 0
    allow_2x: bool = False
    allow_fast_track: bool = False
    fast_track_delay: int = 5


class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    order: Optional[int] = None
    allow_2x: Optional[bool] = None
    allow_fast_track: Optional[bool] = None
    fast_track_delay: Optional[int] = None


@router.get("")
async def list_courses(_=Depends(get_current_user)):
    async with async_session_maker() as session:
        result = await session.execute(
            select(Course).order_by(Course.order, Course.id)
        )
        courses = result.scalars().all()
        items = []
        for c in courses:
            # Count lessons
            lesson_count = await session.execute(
                select(func.count(Lesson.id)).where(Lesson.course_id == c.id)
            )
            # Count enrolled users
            user_count = await session.execute(
                select(func.count(User.id)).where(User.current_course_id == c.id)
            )
            items.append({
                "id": c.id,
                "title": c.title,
                "description": c.description,
                "is_active": c.is_active,
                "order": c.order,
                "allow_2x": c.allow_2x,
                "allow_fast_track": c.allow_fast_track,
                "fast_track_delay": c.fast_track_delay,
                "lesson_count": lesson_count.scalar() or 0,
                "user_count": user_count.scalar() or 0,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            })
        return items


@router.get("/{course_id}")
async def get_course(course_id: int, _=Depends(get_current_user)):
    async with async_session_maker() as session:
        course = await session.get(Course, course_id)
        if not course:
            raise HTTPException(status_code=404, detail="دوره یافت نشد")
        return {
            "id": course.id,
            "title": course.title,
            "description": course.description,
            "is_active": course.is_active,
            "order": course.order,
            "allow_2x": course.allow_2x,
            "allow_fast_track": course.allow_fast_track,
            "fast_track_delay": course.fast_track_delay,
            "created_at": course.created_at.isoformat() if course.created_at else None,
            "updated_at": course.updated_at.isoformat() if course.updated_at else None,
        }


@router.post("")
async def create_course(data: CourseCreate, _=Depends(get_current_user)):
    async with async_session_maker() as session:
        course = Course(
            title=data.title,
            description=data.description,
            is_active=data.is_active,
            order=data.order,
            allow_2x=data.allow_2x,
            allow_fast_track=data.allow_fast_track,
            fast_track_delay=data.fast_track_delay,
        )
        session.add(course)
        await session.commit()
        await session.refresh(course)
        return {"id": course.id, "title": course.title}


@router.put("/{course_id}")
async def update_course(course_id: int, data: CourseUpdate, _=Depends(get_current_user)):
    async with async_session_maker() as session:
        course = await session.get(Course, course_id)
        if not course:
            raise HTTPException(status_code=404, detail="دوره یافت نشد")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(course, field, value)
        await session.commit()
        return {"ok": True}


@router.delete("/{course_id}")
async def delete_course(course_id: int, _=Depends(get_current_user)):
    async with async_session_maker() as session:
        course = await session.get(Course, course_id)
        if not course:
            raise HTTPException(status_code=404, detail="دوره یافت نشد")
        await session.delete(course)
        await session.commit()
        return {"ok": True}


@router.get("/{course_id}/lessons")
async def list_lessons_for_course(course_id: int, _=Depends(get_current_user)):
    """List all lessons for a course, ordered."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Lesson)
            .where(Lesson.course_id == course_id)
            .order_by(Lesson.order, Lesson.id)
        )
        lessons = result.scalars().all()
        return [
            {
                "id": l.id,
                "title": l.title,
                "order": l.order,
                "content_type": l.content_type.value if l.content_type else None,
                "is_active": l.is_active,
                "delay_hours": l.delay_hours,
                "view_deadline_hours": l.view_deadline_hours,
                "has_quiz": bool(l.quiz_data),
                "has_form": bool(l.form_data),
                "content_count": len(l.contents) if l.contents else (1 if l.file_id or l.text_content else 0),
            }
            for l in lessons
        ]
