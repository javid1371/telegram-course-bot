"""
Support Chat API — Conversations list, messages, admin replies
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, desc, update, and_
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from database import async_session_maker
from database.models import SupportMessage, User
from web.auth import get_current_user
import config

logger = logging.getLogger(__name__)
router = APIRouter()


def _create_bot() -> Bot:
    """Create a Bot instance compatible with the current platform."""
    session = None
    if config.PLATFORM == "bale":
        bale_api = TelegramAPIServer(
            base=f"{config.API_BASE_URL}/bot{{token}}/{{method}}",
            file=f"{config.API_BASE_URL}/file/bot{{token}}/{{path}}",
        )
        session = AiohttpSession(api=bale_api)
    return Bot(token=config.BOT_TOKEN, session=session)


# ── Schemas ──

class ReplyRequest(BaseModel):
    message: str


# ── Conversations List ──

@router.get("/conversations")
async def list_conversations(
    page: int = 1,
    per_page: int = 50,
    _=Depends(get_current_user),
):
    """
    List users who have support messages, ordered by most recent message.
    Returns user info + last message preview + unread count.
    """
    async with async_session_maker() as session:
        # Subquery: per-user aggregates
        sub = (
            select(
                SupportMessage.user_id,
                func.count(SupportMessage.id).label("total_messages"),
                func.count(
                    SupportMessage.id
                ).filter(
                    SupportMessage.is_read == False,
                    SupportMessage.sender_type == "user",
                ).label("unread_count"),
                func.max(SupportMessage.created_at).label("last_message_at"),
            )
            .group_by(SupportMessage.user_id)
            .subquery()
        )

        # Join with users
        query = (
            select(User, sub.c.total_messages, sub.c.unread_count, sub.c.last_message_at)
            .join(sub, User.id == sub.c.user_id)
            .order_by(desc(sub.c.last_message_at))
        )

        # Count
        count_q = select(func.count()).select_from(query.subquery())
        total = (await session.execute(count_q)).scalar() or 0

        # Paginate
        rows = (await session.execute(
            query.offset((page - 1) * per_page).limit(per_page)
        )).all()

        conversations = []
        for user, total_msgs, unread, last_at in rows:
            # Get last message text preview
            last_msg_q = (
                select(SupportMessage)
                .where(SupportMessage.user_id == user.id)
                .order_by(desc(SupportMessage.created_at))
                .limit(1)
            )
            last_msg = (await session.execute(last_msg_q)).scalar_one_or_none()

            conversations.append({
                "user_id": user.id,
                "telegram_user_id": user.telegram_user_id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
                "platform": user.platform,
                "total_messages": total_msgs,
                "unread_count": unread,
                "last_message_at": last_at.isoformat() if last_at else None,
                "last_message_preview": (
                    last_msg.message_text[:80] if last_msg and last_msg.message_text
                    else f"[{last_msg.file_type}]" if last_msg and last_msg.file_type
                    else ""
                ),
                "last_sender": last_msg.sender_type if last_msg else None,
            })

        return {
            "conversations": conversations,
            "total": total,
            "page": page,
            "per_page": per_page,
        }


# ── Unread Count (for badge) ──

@router.get("/unread-count")
async def get_unread_count(_=Depends(get_current_user)):
    """Total unread support messages across all users."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(func.count(SupportMessage.id)).where(
                SupportMessage.is_read == False,
                SupportMessage.sender_type == "user",
            )
        )
        return {"unread_count": result.scalar() or 0}


# ── Messages for a User ──

@router.get("/messages/{user_id}")
async def get_messages(
    user_id: int,
    limit: int = 100,
    before_id: Optional[int] = None,
    _=Depends(get_current_user),
):
    """Get support messages for a specific user, newest first."""
    async with async_session_maker() as session:
        query = (
            select(SupportMessage)
            .where(SupportMessage.user_id == user_id)
            .order_by(desc(SupportMessage.created_at))
            .limit(limit)
        )
        if before_id:
            query = query.where(SupportMessage.id < before_id)

        result = await session.execute(query)
        messages = result.scalars().all()

        # Mark user messages as read
        await session.execute(
            update(SupportMessage)
            .where(
                SupportMessage.user_id == user_id,
                SupportMessage.sender_type == "user",
                SupportMessage.is_read == False,
            )
            .values(is_read=True)
        )
        await session.commit()

        return {
            "messages": [
                {
                    "id": m.id,
                    "sender_type": m.sender_type,
                    "message_text": m.message_text,
                    "file_id": m.file_id,
                    "file_type": m.file_type,
                    "platform": m.platform,
                    "is_read": m.is_read,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in reversed(messages)  # chronological order
            ],
            "user_id": user_id,
        }


# ── Admin Reply ──

@router.post("/messages/{user_id}/reply")
async def reply_to_user(
    user_id: int,
    data: ReplyRequest,
    _=Depends(get_current_user),
):
    """
    Admin replies to a user — saves message in DB and sends via bot.
    """
    async with async_session_maker() as session:
        # Find user
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="کاربر پیدا نشد")

        # Save admin message in DB
        admin_msg = SupportMessage(
            user_id=user_id,
            sender_type="admin",
            message_text=data.message,
            platform=config.PLATFORM,
            is_read=True,  # admin's own messages are "read"
        )
        session.add(admin_msg)
        await session.commit()
        await session.refresh(admin_msg)

        # Send via bot to user
        bot = _create_bot()
        try:
            # Format reply text
            reply_text = f"💬 <b>پاسخ پشتیبانی:</b>\n\n{data.message}"
            parse_mode = config.PARSE_MODE

            # Add inline "reply" button so user can respond without
            # navigating back through the support menu
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            reply_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="📩 پاسخ به پشتیبانی",
                    callback_data="support:start_chat",
                )]
            ])

            await bot.send_message(
                chat_id=user.telegram_user_id,
                text=reply_text,
                parse_mode=parse_mode,
                reply_markup=reply_kb,
            )
            logger.info(f"Support reply sent to user {user_id} (tg:{user.telegram_user_id})")
        except Exception as e:
            logger.error(f"Failed to send support reply to user {user_id}: {e}")
            # Message is saved in DB even if bot delivery fails
            return {
                "success": True,
                "delivered": False,
                "detail": f"پیام ذخیره شد اما ارسال به کاربر ناموفق بود: {str(e)}",
                "message": {
                    "id": admin_msg.id,
                    "sender_type": "admin",
                    "message_text": admin_msg.message_text,
                    "created_at": admin_msg.created_at.isoformat(),
                },
            }
        finally:
            await bot.session.close()

        return {
            "success": True,
            "delivered": True,
            "detail": "پیام ارسال شد",
            "message": {
                "id": admin_msg.id,
                "sender_type": "admin",
                "message_text": admin_msg.message_text,
                "created_at": admin_msg.created_at.isoformat(),
            },
        }
