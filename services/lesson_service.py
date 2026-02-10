"""
Lesson service - handles lesson CRUD and delivery
"""
import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Lesson, UserProgress, User, ContentType

logger = logging.getLogger(__name__)


class LessonService:
    """Service for lesson-related operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_lesson_by_id(self, lesson_id: int) -> Optional[Lesson]:
        """Get lesson by ID"""
        result = await self.session.execute(
            select(Lesson).where(Lesson.id == lesson_id)
        )
        return result.scalar_one_or_none()

    async def get_all_lessons(self, active_only: bool = True) -> List[Lesson]:
        """Get all lessons ordered by order field"""
        query = select(Lesson).order_by(Lesson.order)
        if active_only:
            query = query.where(Lesson.is_active == True)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_lessons_paginated(
        self, offset: int = 0, limit: int = 10, active_only: bool = False
    ) -> tuple[List[Lesson], int]:
        """Get lessons with pagination"""
        query = select(Lesson).order_by(Lesson.order)
        count_query = select(func.count(Lesson.id))

        if active_only:
            query = query.where(Lesson.is_active == True)
            count_query = count_query.where(Lesson.is_active == True)

        total = (await self.session.execute(count_query)).scalar() or 0
        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        lessons = list(result.scalars().all())

        return lessons, total

    async def create_lesson(
        self,
        title: str,
        content_type: ContentType,
        description: Optional[str] = None,
        file_id: Optional[str] = None,
        text_content: Optional[str] = None,
        cta_text: Optional[str] = None,
        cta_url: Optional[str] = None,
        delay_hours: int = 0,
    ) -> Lesson:
        """Create a new lesson"""
        # Get next order
        max_order_result = await self.session.execute(
            select(func.max(Lesson.order))
        )
        max_order = max_order_result.scalar() or 0

        lesson = Lesson(
            title=title,
            description=description,
            content_type=content_type,
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
        logger.info(f"Created lesson: {lesson.title} (order: {lesson.order})")
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
    # User Progress Methods
    # ===========================

    async def get_next_lesson_for_user(self, user_id: int) -> Optional[Lesson]:
        """Get the next uncompleted lesson for a user"""
        # Get completed lesson IDs
        completed_result = await self.session.execute(
            select(UserProgress.lesson_id).where(
                UserProgress.user_id == user_id,
                UserProgress.completed_at.isnot(None)
            )
        )
        completed_ids = [r for r in completed_result.scalars().all()]

        # Get next active lesson not completed
        query = select(Lesson).where(
            Lesson.is_active == True,
        ).order_by(Lesson.order)

        if completed_ids:
            query = query.where(Lesson.id.notin_(completed_ids))

        result = await self.session.execute(query)
        return result.scalars().first()

    async def mark_lesson_started(self, user_id: int, lesson_id: int) -> UserProgress:
        """Mark lesson as started for user"""
        # Check if progress already exists
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

        # Update user's current lesson
        next_lesson = await self.get_next_lesson_for_user(user_id)
        user_result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if user:
            if next_lesson:
                user.current_lesson_id = next_lesson.id
            else:
                user.is_completed = True
                user.current_lesson_id = None
            await self.session.commit()

        return progress

    async def get_user_progress(self, user_id: int) -> dict:
        """Get progress summary for a user"""
        total_result = await self.session.execute(
            select(func.count(Lesson.id)).where(Lesson.is_active == True)
        )
        total = total_result.scalar() or 0

        completed_result = await self.session.execute(
            select(func.count(UserProgress.id)).where(
                UserProgress.user_id == user_id,
                UserProgress.completed_at.isnot(None)
            )
        )
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
        # Users who started
        started_result = await self.session.execute(
            select(func.count(UserProgress.id)).where(
                UserProgress.lesson_id == lesson_id
            )
        )
        started = started_result.scalar() or 0

        # Users who completed
        completed_result = await self.session.execute(
            select(func.count(UserProgress.id)).where(
                UserProgress.lesson_id == lesson_id,
                UserProgress.completed_at.isnot(None)
            )
        )
        completed = completed_result.scalar() or 0

        # Average time spent
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

    async def get_total_lessons_count(self, active_only: bool = True) -> int:
        """Get total number of lessons"""
        query = select(func.count(Lesson.id))
        if active_only:
            query = query.where(Lesson.is_active == True)
        result = await self.session.execute(query)
        return result.scalar() or 0
