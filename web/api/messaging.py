"""
Messaging API — Broadcast, direct messaging, and export
"""
import asyncio
import logging
from io import BytesIO
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from database import async_session_maker
from database.models import User, BroadcastLog, Admin
from web.auth import get_current_user
import config

logger = logging.getLogger(__name__)
router = APIRouter()


def _create_bot() -> Bot:
    """Create a Bot instance compatible with the current platform (Telegram or Bale)."""
    session = None
    if config.PLATFORM == "bale":
        bale_api = TelegramAPIServer(
            base=f"{config.API_BASE_URL}/bot{{token}}/{{method}}",
            file=f"{config.API_BASE_URL}/file/bot{{token}}/{{path}}",
        )
        session = AiohttpSession(api=bale_api)
    return Bot(token=config.BOT_TOKEN, session=session)


# ── Pydantic Schemas ──

class BroadcastRequest(BaseModel):
    message: str
    target: str = "all"  # all | active | inactive | completed
    tags: Optional[List[str]] = None

class DirectMessageRequest(BaseModel):
    message: str


# ── Broadcast ──

async def _run_broadcast(broadcast_id: int, user_ids: list, message: str):
    """Background task to send broadcast messages."""
    bot = _create_bot()
    success = 0
    failed = 0

    try:
        for uid in user_ids:
            try:
                await bot.send_message(chat_id=uid, text=message, parse_mode=config.PARSE_MODE)
                success += 1
            except Exception as e:
                logger.warning(f"Broadcast failed for {uid}: {e}")
                failed += 1
            await asyncio.sleep(config.BROADCAST_SLEEP_SECONDS)
    finally:
        await bot.session.close()

    # Update broadcast log
    from datetime import datetime
    async with async_session_maker() as session:
        result = await session.execute(
            select(BroadcastLog).where(BroadcastLog.id == broadcast_id)
        )
        log = result.scalar_one_or_none()
        if log:
            log.success_count = success
            log.failed_count = failed
            log.completed_at = datetime.utcnow()
            await session.commit()

    logger.info(f"Broadcast #{broadcast_id} done: {success} sent, {failed} failed")


@router.post("/broadcast")
async def send_broadcast(
    data: BroadcastRequest,
    background_tasks: BackgroundTasks,
    _=Depends(get_current_user),
):
    """Send broadcast message to filtered users."""
    async with async_session_maker() as session:
        query = select(User)
        if data.target == "active":
            query = query.where(User.is_active == True)
        elif data.target == "inactive":
            query = query.where(User.is_active == False)
        elif data.target == "completed":
            query = query.where(User.is_completed == True)

        if data.tags:
            for tag in data.tags:
                query = query.where(User.tags.contains([tag]))

        result = await session.execute(query)
        users = list(result.scalars().all())

        if not users:
            raise HTTPException(status_code=400, detail="هیچ کاربری با این فیلتر پیدا نشد")

        user_ids = [u.telegram_user_id for u in users]

        # Get or create an admin record for web panel
        admin_result = await session.execute(select(Admin).limit(1))
        admin = admin_result.scalar_one_or_none()
        if not admin:
            admin = Admin(telegram_user_id=0, username="web_admin", full_name="Web Admin")
            session.add(admin)
            await session.flush()

        # Create broadcast log
        log = BroadcastLog(
            admin_id=admin.id,
            message=data.message,
            target_filter={"target": data.target, "tags": data.tags},
            total_users=len(users),
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)

        broadcast_id = log.id

    # Run in background
    background_tasks.add_task(_run_broadcast, broadcast_id, user_ids, data.message)

    return {
        "broadcast_id": broadcast_id,
        "total_users": len(user_ids),
        "status": "در حال ارسال...",
    }


@router.get("/broadcast/history")
async def get_broadcast_history(
    page: int = 1,
    per_page: int = 10,
    _=Depends(get_current_user),
):
    """Get broadcast history."""
    async with async_session_maker() as session:
        total = (await session.execute(
            select(func.count(BroadcastLog.id))
        )).scalar() or 0

        result = await session.execute(
            select(BroadcastLog)
            .order_by(desc(BroadcastLog.started_at))
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        logs = result.scalars().all()

        return {
            "total": total,
            "items": [
                {
                    "id": log.id,
                    "message": log.message[:100] + ("..." if len(log.message) > 100 else ""),
                    "full_message": log.message,
                    "target": log.target_filter.get("target", "all") if log.target_filter else "all",
                    "tags": log.target_filter.get("tags") if log.target_filter else None,
                    "total_users": log.total_users,
                    "success_count": log.success_count,
                    "failed_count": log.failed_count,
                    "started_at": log.started_at.isoformat() if log.started_at else None,
                    "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                    "is_done": log.completed_at is not None,
                }
                for log in logs
            ],
        }


@router.get("/broadcast/preview")
async def preview_broadcast(
    target: str = "all",
    tags: Optional[str] = None,
    _=Depends(get_current_user),
):
    """Preview how many users a broadcast would reach."""
    async with async_session_maker() as session:
        query = select(func.count(User.id))
        if target == "active":
            query = query.where(User.is_active == True)
        elif target == "inactive":
            query = query.where(User.is_active == False)
        elif target == "completed":
            query = query.where(User.is_completed == True)

        if tags:
            for tag in tags.split(","):
                tag = tag.strip()
                if tag:
                    query = query.where(User.tags.contains([tag]))

        count = (await session.execute(query)).scalar() or 0
        return {"count": count}


# ── Direct Message ──

@router.post("/send/{user_id}")
async def send_direct_message(
    user_id: int,
    data: DirectMessageRequest,
    _=Depends(get_current_user),
):
    """Send a direct message to a specific user via bot."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="کاربر پیدا نشد")

        bot = _create_bot()
        try:
            await bot.send_message(
                chat_id=user.telegram_user_id,
                text=data.message,
                parse_mode=config.PARSE_MODE,
            )
            return {"success": True, "detail": "پیام ارسال شد"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"خطا در ارسال: {str(e)}")
        finally:
            await bot.session.close()


# ── Export ──

@router.get("/export/users")
async def export_users_excel(
    status: Optional[str] = None,
    _=Depends(get_current_user),
):
    """Export users to Excel file."""
    from services.export_service import ExportService

    async with async_session_maker() as session:
        service = ExportService(session)

        is_active = None
        is_completed = None
        if status == "active":
            is_active = True
        elif status == "inactive":
            is_active = False
        elif status == "completed":
            is_completed = True

        output = await service.export_users_to_excel(
            is_active=is_active,
            is_completed=is_completed,
        )

        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=users_export.xlsx"},
        )


@router.get("/export/progress")
async def export_progress_excel(_=Depends(get_current_user)):
    """Export progress data to Excel file."""
    from services.export_service import ExportService

    async with async_session_maker() as session:
        service = ExportService(session)
        output = await service.export_progress_to_excel()

        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=progress_export.xlsx"},
        )


@router.get("/export/analytics")
async def export_analytics_excel(_=Depends(get_current_user)):
    """Export analytics to Excel file."""
    from services.export_service import ExportService

    async with async_session_maker() as session:
        service = ExportService(session)
        output = await service.export_analytics_to_excel()

        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=analytics_export.xlsx"},
        )
