"""
File Upload API — uploads file via Telegram Bot API and returns file_id
"""
import os
import aiohttp
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

from web.auth import get_current_user

router = APIRouter()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_USER_IDS = [
    int(uid.strip())
    for uid in os.getenv("ADMIN_USER_IDS", "").split(",")
    if uid.strip()
]
PLATFORM = os.getenv("PLATFORM", "telegram").lower()

API_URLS = {
    "telegram": "https://api.telegram.org",
    "bale": "https://tapi.bale.ai",
}
API_BASE = API_URLS.get(PLATFORM, API_URLS["telegram"])

# Mapping of content types to Telegram Bot API methods and response keys
UPLOAD_MAP = {
    "video": ("sendVideo", "video"),
    "audio": ("sendAudio", "audio"),
    "voice": ("sendVoice", "voice"),
    "photo": ("sendPhoto", "photo"),
    "document": ("sendDocument", "document"),
}


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    content_type: str = Form("document"),
    caption: str = Form(""),
    _=Depends(get_current_user),
):
    """
    Upload a file via the Telegram Bot API.
    Sends it to the first admin user as a silent message,
    then extracts the file_id from the response.
    """
    if not BOT_TOKEN:
        raise HTTPException(status_code=500, detail="BOT_TOKEN not configured")
    if not ADMIN_USER_IDS:
        raise HTTPException(status_code=500, detail="No admin users configured")

    if content_type not in UPLOAD_MAP:
        raise HTTPException(status_code=400, detail=f"Unsupported content type: {content_type}")

    method, response_key = UPLOAD_MAP[content_type]
    url = f"{API_BASE}/bot{BOT_TOKEN}/{method}"

    chat_id = ADMIN_USER_IDS[0]

    # Read file content
    file_data = await file.read()

    # Build form data for Telegram API
    form = aiohttp.FormData()
    form.add_field("chat_id", str(chat_id))
    form.add_field(response_key, file_data, filename=file.filename, content_type=file.content_type)
    form.add_field("disable_notification", "true")
    if caption:
        form.add_field("caption", caption)

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=form) as resp:
            result = await resp.json()

    if not result.get("ok"):
        raise HTTPException(
            status_code=500,
            detail=f"Telegram API error: {result.get('description', 'Unknown error')}"
        )

    # Extract file_id from response
    msg = result.get("result", {})
    file_obj = msg.get(response_key)

    if not file_obj:
        raise HTTPException(status_code=500, detail="Could not extract file_id from response")

    # For photo, Telegram returns an array — use the largest one
    if isinstance(file_obj, list):
        file_obj = file_obj[-1]

    file_id = file_obj.get("file_id", "")
    if not file_id:
        raise HTTPException(status_code=500, detail="Empty file_id in response")

    return {
        "file_id": file_id,
        "type": content_type,
        "filename": file.filename,
    }
