"""
Media Library API — CRUD for media files uploaded via bot.
"""
import os
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, delete

from database import async_session_maker
from database.models import MediaFile
from web.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

PLATFORM = os.getenv("PLATFORM", "telegram").lower()


@router.get("")
async def list_media(
    file_type: str = None,
    search: str = None,
    limit: int = 100,
    offset: int = 0,
    _=Depends(get_current_user),
):
    """List media files for current platform"""
    async with async_session_maker() as session:
        query = select(MediaFile).where(MediaFile.platform == PLATFORM)

        if file_type:
            query = query.where(MediaFile.file_type == file_type)
        if search:
            query = query.where(MediaFile.name.ilike(f"%{search}%"))

        # Count total
        count_q = select(func.count()).select_from(
            query.subquery()
        )
        total = (await session.execute(count_q)).scalar() or 0

        # Get items
        query = query.order_by(MediaFile.created_at.desc()).offset(offset).limit(limit)
        result = await session.execute(query)
        files = result.scalars().all()

        return {
            "items": [
                {
                    "id": f.id,
                    "name": f.name,
                    "file_type": f.file_type,
                    "file_id": f.file_id,
                    "platform": f.platform,
                    "file_size": f.file_size,
                    "mime_type": f.mime_type,
                    "duration": f.duration,
                    "uploaded_by": f.uploaded_by,
                    "created_at": f.created_at.isoformat() if f.created_at else None,
                }
                for f in files
            ],
            "total": total,
        }


@router.get("/{media_id}")
async def get_media(media_id: int, _=Depends(get_current_user)):
    """Get a single media file"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(MediaFile).where(MediaFile.id == media_id)
        )
        f = result.scalar_one_or_none()
        if not f:
            raise HTTPException(status_code=404, detail="فایل یافت نشد")
        return {
            "id": f.id,
            "name": f.name,
            "file_type": f.file_type,
            "file_id": f.file_id,
            "platform": f.platform,
            "file_size": f.file_size,
            "mime_type": f.mime_type,
            "duration": f.duration,
            "uploaded_by": f.uploaded_by,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }


@router.delete("/{media_id}")
async def delete_media(media_id: int, _=Depends(get_current_user)):
    """Delete a media file from library"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(MediaFile).where(MediaFile.id == media_id)
        )
        f = result.scalar_one_or_none()
        if not f:
            raise HTTPException(status_code=404, detail="فایل یافت نشد")

        name = f.name
        await session.execute(
            delete(MediaFile).where(MediaFile.id == media_id)
        )
        await session.commit()
        return {"detail": f"فایل «{name}» حذف شد"}
