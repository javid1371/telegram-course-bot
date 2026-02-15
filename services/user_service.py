"""
User service - handles user CRUD operations and registration
"""
import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, RegistrationField, UserProgress, Lesson
import config

logger = logging.getLogger(__name__)


class UserService:
    """Service for user-related operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_telegram_id(self, telegram_user_id: int) -> Optional[User]:
        """Get user by Telegram/Bale user ID on the current platform"""
        result = await self.session.execute(
            select(User).where(
                User.telegram_user_id == telegram_user_id,
                User.platform == config.PLATFORM,
            )
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by internal ID"""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_user(
        self,
        telegram_user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        registration_data: Optional[dict] = None,
        source_campaign: Optional[str] = None,
        referred_by: Optional[int] = None,
    ) -> User:
        """Create a new user"""
        from utils.helpers import generate_referral_code

        user = User(
            telegram_user_id=telegram_user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            registration_data=registration_data or {},
            source_campaign=source_campaign,
            referred_by=referred_by,
            referral_code=generate_referral_code(telegram_user_id),
            platform=config.PLATFORM,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        logger.info(f"Created user: {telegram_user_id}")
        return user

    async def update_user(self, user: User, **kwargs) -> User:
        """Update user fields"""
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update_registration_data(self, user: User, data: dict) -> User:
        """Update user registration data"""
        current = user.registration_data or {}
        current.update(data)
        user.registration_data = current
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get_all_users(
        self,
        is_active: Optional[bool] = None,
        is_completed: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[List[User], int]:
        """Get users with filters and pagination"""
        query = select(User)
        count_query = select(func.count(User.id))

        if is_active is not None:
            query = query.where(User.is_active == is_active)
            count_query = count_query.where(User.is_active == is_active)

        if is_completed is not None:
            query = query.where(User.is_completed == is_completed)
            count_query = count_query.where(User.is_completed == is_completed)

        if tags:
            for tag in tags:
                query = query.where(User.tags.contains([tag]))
                count_query = count_query.where(User.tags.contains([tag]))

        total = (await self.session.execute(count_query)).scalar() or 0
        query = query.order_by(User.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        users = list(result.scalars().all())

        return users, total

    async def search_users(self, search_term: str, offset: int = 0, limit: int = 20) -> tuple[List[User], int]:
        """Search users by name, username or phone"""
        search = f"%{search_term}%"
        query = select(User).where(
            (User.first_name.ilike(search)) |
            (User.last_name.ilike(search)) |
            (User.username.ilike(search))
        )
        count_query = select(func.count(User.id)).where(
            (User.first_name.ilike(search)) |
            (User.last_name.ilike(search)) |
            (User.username.ilike(search))
        )

        total = (await self.session.execute(count_query)).scalar() or 0
        query = query.order_by(User.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        users = list(result.scalars().all())

        return users, total

    async def block_user(self, user_id: int) -> bool:
        """Block/deactivate a user"""
        user = await self.get_user_by_id(user_id)
        if user:
            user.is_active = False
            await self.session.commit()
            return True
        return False

    async def unblock_user(self, user_id: int) -> bool:
        """Unblock/activate a user"""
        user = await self.get_user_by_id(user_id)
        if user:
            user.is_active = True
            await self.session.commit()
            return True
        return False

    async def delete_user(self, user_id: int) -> bool:
        """Delete a user"""
        user = await self.get_user_by_id(user_id)
        if user:
            await self.session.delete(user)
            await self.session.commit()
            return True
        return False

    async def add_tag(self, user_id: int, tag: str) -> bool:
        """Add tag to user"""
        user = await self.get_user_by_id(user_id)
        if user:
            tags = user.tags or []
            if tag not in tags:
                tags.append(tag)
                user.tags = tags
                await self.session.commit()
            return True
        return False

    async def remove_tag(self, user_id: int, tag: str) -> bool:
        """Remove tag from user"""
        user = await self.get_user_by_id(user_id)
        if user:
            tags = user.tags or []
            if tag in tags:
                tags.remove(tag)
                user.tags = tags
                await self.session.commit()
            return True
        return False

    async def get_user_stats(self, user_id: int) -> dict:
        """Get statistics for a specific user"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return {}

        # Count completed lessons
        completed_result = await self.session.execute(
            select(func.count(UserProgress.id)).where(
                UserProgress.user_id == user_id,
                UserProgress.completed_at.isnot(None)
            )
        )
        completed_count = completed_result.scalar() or 0

        # Total lessons
        total_result = await self.session.execute(
            select(func.count(Lesson.id)).where(Lesson.is_active == True)
        )
        total_count = total_result.scalar() or 0

        # Total time spent
        time_result = await self.session.execute(
            select(func.sum(UserProgress.time_spent)).where(
                UserProgress.user_id == user_id
            )
        )
        total_time = time_result.scalar() or 0

        return {
            "user": user,
            "completed_lessons": completed_count,
            "total_lessons": total_count,
            "progress_percent": round((completed_count / total_count * 100) if total_count > 0 else 0, 1),
            "total_time_spent": total_time,
            "tags": user.tags or [],
            "registered_at": user.created_at,
            "last_activity": user.last_activity_at,
        }

    async def get_active_registration_fields(self) -> List[RegistrationField]:
        """Get active registration fields sorted by order"""
        result = await self.session.execute(
            select(RegistrationField)
            .where(RegistrationField.is_active == True)
            .order_by(RegistrationField.order)
        )
        return list(result.scalars().all())

    async def reorder_registration_fields(self, field_ids: List[int]) -> bool:
        """Reorder registration fields based on provided ID list"""
        for order, field_id in enumerate(field_ids, 1):
            await self.session.execute(
                update(RegistrationField)
                .where(RegistrationField.id == field_id)
                .values(order=order)
            )
        await self.session.commit()
        return True

    async def get_total_users_count(self) -> int:
        """Get total number of users"""
        result = await self.session.execute(select(func.count(User.id)))
        return result.scalar() or 0

    async def get_active_users_count(self) -> int:
        """Get number of active users"""
        result = await self.session.execute(
            select(func.count(User.id)).where(User.is_active == True)
        )
        return result.scalar() or 0

    async def reset_user_progress(self, user_id: int) -> bool:
        """Reset all progress for a user (lessons, quizzes, forms, courses)"""
        from database.models import QuizAttempt, FormResponse
        await self.session.execute(
            delete(UserProgress).where(UserProgress.user_id == user_id)
        )
        await self.session.execute(
            delete(QuizAttempt).where(QuizAttempt.user_id == user_id)
        )
        await self.session.execute(
            delete(FormResponse).where(FormResponse.user_id == user_id)
        )
        user = await self.get_user_by_id(user_id)
        if user:
            user.current_lesson_id = None
            user.current_course_id = None
            user.is_completed = False
            user.completed_courses = {}
            await self.session.commit()
            return True
        return False

    async def get_referral_count(self, user_id: int) -> int:
        """Get number of users referred by this user"""
        result = await self.session.execute(
            select(func.count(User.id)).where(User.referred_by == user_id)
        )
        return result.scalar() or 0

    async def get_referred_users(self, user_id: int, limit: int = 20) -> list:
        """Get list of users referred by this user"""
        result = await self.session.execute(
            select(User)
            .where(User.referred_by == user_id)
            .order_by(User.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_referrer(self, user_id: int):
        """Get the user who referred this user"""
        user = await self.get_user_by_id(user_id)
        if user and user.referred_by:
            return await self.get_user_by_id(user.referred_by)
        return None
