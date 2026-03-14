"""Media Library API — CRUD for media files uploaded via bot.
Also supports direct file upload from web panel."""
import os
import logging
import aiohttp
import asyncio
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select, func, delete, or_

from database import async_session_maker
from database.models import MediaFile
from web.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_USER_IDS = [
    int(uid.strip())
    for uid in os.getenv("ADMIN_USER_IDS", "").split(",")
    if uid.strip()
]
PLATFORM = os.getenv("PLATFORM", "telegram").lower()
PLATFORM_LABEL = "تلگرام" if PLATFORM == "telegram" else "بله"

API_URLS = {
    "telegram": "https://api.telegram.org",
    "bale": "https://tapi.bale.ai",
}
API_BASE = API_URLS.get(PLATFORM, API_URLS["telegram"])


@router.get("/platform")
async def get_platform(_=Depends(get_current_user)):
    """Return current platform info"""
    return {"platform": PLATFORM, "label": PLATFORM_LABEL}


@router.get("")
@router.get("/")
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
            # On Bale, audio/voice files may be stored as "document" with audio/* mime_type
            # Include those when filtering for audio or voice
            if file_type in ("audio", "voice"):
                query = query.where(
                    or_(
                        MediaFile.file_type == file_type,
                        MediaFile.mime_type.ilike("audio/%"),
                    )
                )
            else:
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


@router.post("/upload")
async def upload_media(
    file: UploadFile = File(...),
    content_type: str = Form("document"),
    _=Depends(get_current_user),
):
    """Upload a file to media library directly from the web panel.
    Sends via Bot API to get a file_id, then saves to media_library table."""
    if not BOT_TOKEN:
        raise HTTPException(status_code=500, detail="BOT_TOKEN not configured")
    if not ADMIN_USER_IDS:
        raise HTTPException(status_code=500, detail="No admin users configured")

    chat_id = ADMIN_USER_IDS[0]
    file_data = await file.read()
    file_size = len(file_data)

    # On Bale, audio/voice must be sent as document
    effective_type = content_type
    if PLATFORM == "bale" and content_type in ("audio", "voice"):
        effective_type = "document"

    UPLOAD_MAP = {
        "video": ("sendVideo", "video"),
        "audio": ("sendAudio", "audio"),
        "voice": ("sendVoice", "voice"),
        "photo": ("sendPhoto", "photo"),
        "document": ("sendDocument", "document"),
    }

    # Try effective type, then fallback to document
    attempts = [effective_type]
    if effective_type != "document":
        attempts.append("document")

    file_id = None
    for attempt_type in attempts:
        method, response_key = UPLOAD_MAP.get(attempt_type, UPLOAD_MAP["document"])
        url = f"{API_BASE}/bot{BOT_TOKEN}/{method}"

        form = aiohttp.FormData()
        form.add_field("chat_id", str(chat_id))
        form.add_field(response_key, file_data, filename=file.filename, content_type=file.content_type)
        form.add_field("disable_notification", "true")

        timeout_seconds = max(120, int(60 + file_size / (1024 * 1024) * 1.5))

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, data=form, timeout=aiohttp.ClientTimeout(total=timeout_seconds)) as resp:
                    result = await resp.json()
            except asyncio.TimeoutError:
                raise HTTPException(status_code=504, detail="تایم‌اوت آپلود — سرور پاسخ نداد")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"خطا در اتصال: {e}")

        if result.get("ok"):
            msg = result.get("result", {})
            file_obj = msg.get(response_key)
            if isinstance(file_obj, list):
                file_obj = file_obj[-1]
            if file_obj:
                file_id = file_obj.get("file_id")
            if file_id:
                break
        else:
            error_code = result.get("error_code", "?")
            error_desc = result.get("description", "Unknown")
            logger.warning(f"Media upload [{error_code}]: {error_desc} ({method}, {file.filename})")
            # Try next attempt (fallback to document)
            continue

    if not file_id:
        raise HTTPException(status_code=500, detail="آپلود ناموفق — سرور file_id برنگرداند")

    # Detect actual file type from mime_type
    actual_type = content_type
    mime = file.content_type or ""
    if actual_type == "document" and mime.startswith("audio/"):
        actual_type = "audio"
    elif actual_type == "document" and mime.startswith("video/"):
        actual_type = "video"

    # Save to media library
    async with async_session_maker() as db:
        media_file = MediaFile(
            name=file.filename or f"file_{file_id[:10]}",
            file_type=actual_type,
            file_id=file_id,
            platform=PLATFORM,
            file_size=file_size,
            mime_type=mime or None,
            uploaded_by=0,  # web panel upload
        )
        db.add(media_file)
        await db.commit()
        await db.refresh(media_file)

    return {
        "id": media_file.id,
        "name": media_file.name,
        "file_type": media_file.file_type,
        "file_id": file_id,
        "file_size": file_size,
    }
