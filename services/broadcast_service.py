"""
Broadcast service - handles mass messaging to users
"""
import asyncio
import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot

from database.models import User, BroadcastLog, Admin
import config

logger = logging.getLogger(__name__)


class BroadcastService:
    """Service for broadcasting messages to users"""

    def __init__(self, session: AsyncSession, bot: Bot):
        self.session = session
        self.bot = bot

    async def broadcast_message(
        self,
        admin_id: int,
        message: str,
        target: str = "all",
        tags: Optional[List[str]] = None,
    ) -> BroadcastLog:
        """Send broadcast message to users"""
        # Build user query
        query = select(User)

        if target == "active":
            query = query.where(User.is_active == True)
        elif target == "inactive":
            query = query.where(User.is_active == False)
        elif target == "completed":
            query = query.where(User.is_completed == True)

        if tags:
            for tag in tags:
                query = query.where(User.tags.contains([tag]))

        result = await self.session.execute(query)
        users = list(result.scalars().all())

        # Get admin record
        admin_result = await self.session.execute(
            select(Admin).where(Admin.telegram_user_id == admin_id)
        )
        admin = admin_result.scalar_one_or_none()

        # Create broadcast log
        broadcast_log = BroadcastLog(
            admin_id=admin.id if admin else 1,
            message=message,
            target_filter={"target": target, "tags": tags},
            total_users=len(users),
        )
        self.session.add(broadcast_log)
        await self.session.commit()
        await self.session.refresh(broadcast_log)

        success = 0
        failed = 0

        for user in users:
            try:
                await self.bot.send_message(
                    chat_id=user.telegram_user_id,
                    text=message,
                )
                success += 1
            except Exception as e:
                logger.warning(f"Failed to send broadcast to {user.telegram_user_id}: {e}")
                failed += 1

            # Rate limiting
            await asyncio.sleep(config.BROADCAST_SLEEP_SECONDS)

        # Update broadcast log
        broadcast_log.success_count = success
        broadcast_log.failed_count = failed
        broadcast_log.completed_at = datetime.utcnow()
        await self.session.commit()

        logger.info(f"Broadcast completed: {success}/{len(users)} sent, {failed} failed")
        return broadcast_log

    async def send_private_message(self, user_telegram_id: int, message: str) -> bool:
        """Send private message to a specific user"""
        try:
            await self.bot.send_message(
                chat_id=user_telegram_id,
                text=message,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send private message to {user_telegram_id}: {e}")
            return False

    async def get_broadcast_history(
        self, offset: int = 0, limit: int = 10
    ) -> tuple[List[BroadcastLog], int]:
        """Get broadcast history with pagination"""
        count_query = select(func.count(BroadcastLog.id))
        total = (await self.session.execute(count_query)).scalar() or 0

        query = (
            select(BroadcastLog)
            .order_by(BroadcastLog.started_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(query)
        logs = list(result.scalars().all())

        return logs, total
