"""
Lesson service - handles lesson CRUD and delivery (multi-course)
"""
import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Lesson, UserProgress, User, ContentType, Course

logger = logging.getLogger(__name__)


class LessonService:
    """Service for lesson-related operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ===========================
    # Course Methods
    # ===========================

    async def get_all_courses(self, active_only: bool = True) -> List[Course]:
        """Get all courses ordered by order field"""
        query = select(Course).order_by(Course.order)
        if active_only:
            query = query.where(Course.is_active == True)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_course_by_id(self, course_id: int) -> Optional[Course]:
        """Get course by ID"""
        result = await self.session.execute(
            select(Course).where(Course.id == course_id)
        )
        return result.scalar_one_or_none()

    async def create_course(self, title: str, description: Optional[str] = None) -> Course:
        """Create a new course"""
        max_order_result = await self.session.execute(
            select(func.max(Course.order))
        )
        max_order = max_order_result.scalar() or 0

        course = Course(
            title=title,
            description=description,
            order=max_order + 1,
        )
        self.session.add(course)
        await self.session.commit()
        await self.session.refresh(course)
        logger.info(f"Created course: {course.title}")
        return course

    async def update_course(self, course_id: int, **kwargs) -> Optional[Course]:
        """Update course fields"""
        course = await self.get_course_by_id(course_id)
        if not course:
            return None
        for key, value in kwargs.items():
            if hasattr(course, key):
                setattr(course, key, value)
        await self.session.commit()
        await self.session.refresh(course)
        return course

    async def delete_course(self, course_id: int) -> bool:
        """Delete a course and its lessons"""
        course = await self.get_course_by_id(course_id)
        if course:
            await self.session.delete(course)
            await self.session.commit()
            return True
        return False

    async def toggle_course(self, course_id: int) -> Optional[Course]:
        """Toggle course active status"""
        course = await self.get_course_by_id(course_id)
        if course:
            course.is_active = not course.is_active
            await self.session.commit()
            await self.session.refresh(course)
            return course
        return None

    async def get_course_lesson_count(self, course_id: int) -> int:
        """Get number of active lessons in a course"""
        result = await self.session.execute(
            select(func.count(Lesson.id)).where(
                Lesson.course_id == course_id,
                Lesson.is_active == True
            )
        )
        return result.scalar() or 0

    async def get_course_stats(self, course_id: int) -> dict:
        """Get stats for a specific course"""
        total_lessons = await self.get_course_lesson_count(course_id)

        # Users enrolled
        enrolled_result = await self.session.execute(
            select(func.count(func.distinct(UserProgress.user_id))).join(
                Lesson, UserProgress.lesson_id == Lesson.id
            ).where(Lesson.course_id == course_id)
        )
        enrolled = enrolled_result.scalar() or 0

        # Users who completed ALL lessons of this course
        if total_lessons > 0 and enrolled > 0:
            completed_sub = (
                select(UserProgress.user_id)
                .join(Lesson, UserProgress.lesson_id == Lesson.id)
                .where(
                    Lesson.course_id == course_id,
                    Lesson.is_active == True,
                    UserProgress.completed_at.isnot(None)
                )
                .group_by(UserProgress.user_id)
                .having(func.count(func.distinct(UserProgress.lesson_id)) >= total_lessons)
            )
            completed_result = await self.session.execute(
                select(func.count()).select_from(completed_sub.subquery())
            )
            completed = completed_result.scalar() or 0
        else:
            completed = 0

        return {
            "total_lessons": total_lessons,
            "enrolled": enrolled,
            "completed": completed,
            "completion_rate": round((completed / enrolled * 100) if enrolled > 0 else 0, 1),
        }

    # ===========================
    # Lesson Methods
    # ===========================

    async def get_lesson_by_id(self, lesson_id: int) -> Optional[Lesson]:
        """Get lesson by ID with course relationship"""
        from sqlalchemy.orm import selectinload
        result = await self.session.execute(
            select(Lesson).where(Lesson.id == lesson_id).options(selectinload(Lesson.course))
        )
        return result.scalar_one_or_none()

    async def get_all_lessons(self, active_only: bool = True, course_id: Optional[int] = None) -> List[Lesson]:
        """Get all lessons ordered by order field, optionally filtered by course"""
        query = select(Lesson).order_by(Lesson.order)
        if active_only:
            query = query.where(Lesson.is_active == True)
        if course_id is not None:
            query = query.where(Lesson.course_id == course_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_lessons_paginated(
        self, offset: int = 0, limit: int = 10, active_only: bool = False, course_id: Optional[int] = None
    ) -> tuple[List[Lesson], int]:
        """Get lessons with pagination"""
        query = select(Lesson).order_by(Lesson.order)
        count_query = select(func.count(Lesson.id))

        if active_only:
            query = query.where(Lesson.is_active == True)
            count_query = count_query.where(Lesson.is_active == True)

        if course_id is not None:
            query = query.where(Lesson.course_id == course_id)
            count_query = count_query.where(Lesson.course_id == course_id)

        total = (await self.session.execute(count_query)).scalar() or 0
        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        lessons = list(result.scalars().all())

        return lessons, total

    async def create_lesson(
        self,
        title: str,
        content_type: ContentType,
        course_id: Optional[int] = None,
        description: Optional[str] = None,
        file_id: Optional[str] = None,
        text_content: Optional[str] = None,
        cta_text: Optional[str] = None,
        cta_url: Optional[str] = None,
        delay_hours: int = 0,
    ) -> Lesson:
        """Create a new lesson"""
        order_query = select(func.max(Lesson.order))
        if course_id:
            order_query = order_query.where(Lesson.course_id == course_id)
        max_order_result = await self.session.execute(order_query)
        max_order = max_order_result.scalar() or 0

        lesson = Lesson(
            title=title,
            description=description,
            content_type=content_type,
            course_id=course_id,
            file_id=file_id,
            text_content=text_content,
            order=max_order + 1,
            delay_hours=delay_hours,
            cta_text=cta_text,
            cta_url=cta_url,
        )
        self.session.add(lesson)
        await self.session.commit()
        await self.session.refresh(lesson)
        logger.info(f"Created lesson: {lesson.title} (order: {lesson.order}, course: {course_id})")
        return lesson

    async def update_lesson(self, lesson_id: int, **kwargs) -> Optional[Lesson]:
        """Update lesson fields"""
        lesson = await self.get_lesson_by_id(lesson_id)
        if not lesson:
            return None
        for key, value in kwargs.items():
            if hasattr(lesson, key):
                setattr(lesson, key, value)
        await self.session.commit()
        await self.session.refresh(lesson)
        return lesson

    async def delete_lesson(self, lesson_id: int) -> bool:
        """Delete a lesson"""
        lesson = await self.get_lesson_by_id(lesson_id)
        if lesson:
            await self.session.delete(lesson)
            await self.session.commit()
            return True
        return False

    async def toggle_lesson(self, lesson_id: int) -> Optional[Lesson]:
        """Toggle lesson active status"""
        lesson = await self.get_lesson_by_id(lesson_id)
        if lesson:
            lesson.is_active = not lesson.is_active
            await self.session.commit()
            await self.session.refresh(lesson)
            return lesson
        return None

    async def reorder_lessons(self, lesson_ids: List[int]) -> bool:
        """Reorder lessons based on provided ID list"""
        for order, lesson_id in enumerate(lesson_ids, 1):
            await self.session.execute(
                update(Lesson).where(Lesson.id == lesson_id).values(order=order)
            )
        await self.session.commit()
        return True

    # ===========================
    # User Progress Methods (course-aware)
    # ===========================

    async def get_next_lesson_for_user(self, user_id: int, course_id: Optional[int] = None) -> Optional[Lesson]:
        """Get the next uncompleted lesson for a user in a specific course"""
        completed_result = await self.session.execute(
            select(UserProgress.lesson_id).where(
                UserProgress.user_id == user_id,
                UserProgress.completed_at.isnot(None)
            )
        )
        completed_ids = [r for r in completed_result.scalars().all()]

        query = select(Lesson).where(
            Lesson.is_active == True,
        ).order_by(Lesson.order)

        if course_id is not None:
            query = query.where(Lesson.course_id == course_id)

        if completed_ids:
            query = query.where(Lesson.id.notin_(completed_ids))

        result = await self.session.execute(query)
        return result.scalars().first()

    async def mark_lesson_started(self, user_id: int, lesson_id: int) -> UserProgress:
        """Mark lesson as started for user"""
        result = await self.session.execute(
            select(UserProgress).where(
                UserProgress.user_id == user_id,
                UserProgress.lesson_id == lesson_id,
            )
        )
        progress = result.scalar_one_or_none()

        if not progress:
            progress = UserProgress(
                user_id=user_id,
                lesson_id=lesson_id,
            )
            self.session.add(progress)
            await self.session.commit()
            await self.session.refresh(progress)

        return progress

    async def mark_lesson_completed(self, user_id: int, lesson_id: int) -> UserProgress:
        """Mark lesson as completed for user"""
        result = await self.session.execute(
            select(UserProgress).where(
                UserProgress.user_id == user_id,
                UserProgress.lesson_id == lesson_id,
            )
        )
        progress = result.scalar_one_or_none()

        if not progress:
            progress = UserProgress(
                user_id=user_id,
                lesson_id=lesson_id,
            )
            self.session.add(progress)

        progress.completed_at = datetime.utcnow()
        progress.confirmation_count += 1
        await self.session.commit()
        await self.session.refresh(progress)

        # Get lesson's course_id
        lesson = await self.get_lesson_by_id(lesson_id)
        course_id = lesson.course_id if lesson else None

        # Update user's current lesson within this course
        next_lesson = await self.get_next_lesson_for_user(user_id, course_id=course_id)
        user_result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if user:
            if next_lesson:
                user.current_lesson_id = next_lesson.id
            else:
                # This course completed
                if course_id:
                    completed = user.completed_courses or {}
                    completed[str(course_id)] = True
                    user.completed_courses = completed
                user.current_lesson_id = None
                # Check if ALL active courses are completed
                all_courses = await self.get_all_courses(active_only=True)
                all_done = all(
                    (user.completed_courses or {}).get(str(c.id))
                    for c in all_courses
                )
                if all_done:
                    user.is_completed = True
            await self.session.commit()

        return progress

    async def get_user_progress(self, user_id: int, course_id: Optional[int] = None) -> dict:
        """Get progress summary for a user, optionally for a specific course"""
        total_query = select(func.count(Lesson.id)).where(Lesson.is_active == True)
        if course_id is not None:
            total_query = total_query.where(Lesson.course_id == course_id)
        total_result = await self.session.execute(total_query)
        total = total_result.scalar() or 0

        completed_query = select(func.count(UserProgress.id)).where(
            UserProgress.user_id == user_id,
            UserProgress.completed_at.isnot(None)
        )
        if course_id is not None:
            completed_query = completed_query.join(
                Lesson, UserProgress.lesson_id == Lesson.id
            ).where(Lesson.course_id == course_id)

        completed_result = await self.session.execute(completed_query)
        completed = completed_result.scalar() or 0

        progress_percent = round((completed / total * 100) if total > 0 else 0, 1)

        return {
            "total": total,
            "completed": completed,
            "remaining": total - completed,
            "progress_percent": progress_percent,
        }

    async def get_lesson_stats(self, lesson_id: int) -> dict:
        """Get statistics for a specific lesson"""
        started_result = await self.session.execute(
            select(func.count(UserProgress.id)).where(
                UserProgress.lesson_id == lesson_id
            )
        )
        started = started_result.scalar() or 0

        completed_result = await self.session.execute(
            select(func.count(UserProgress.id)).where(
                UserProgress.lesson_id == lesson_id,
                UserProgress.completed_at.isnot(None)
            )
        )
        completed = completed_result.scalar() or 0

        avg_time_result = await self.session.execute(
            select(func.avg(UserProgress.time_spent)).where(
                UserProgress.lesson_id == lesson_id,
                UserProgress.time_spent.isnot(None)
            )
        )
        avg_time = avg_time_result.scalar()

        return {
            "started": started,
            "completed": completed,
            "completion_rate": round((completed / started * 100) if started > 0 else 0, 1),
            "avg_time_spent": round(avg_time) if avg_time else None,
        }

    async def get_total_lessons_count(self, active_only: bool = True, course_id: Optional[int] = None) -> int:
        """Get total number of lessons"""
        query = select(func.count(Lesson.id))
        if active_only:
            query = query.where(Lesson.is_active == True)
        if course_id is not None:
            query = query.where(Lesson.course_id == course_id)
        result = await self.session.execute(query)
        return result.scalar() or 0
