"""
File Upload API — uploads file via Telegram Bot API and returns file_id
Supports splitting large files (>50MB) into parts using ffmpeg.
"""
import os
import glob
import json
import shutil
import asyncio
import logging
import tempfile
import aiohttp
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

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


@router.get("/config")
async def upload_config(_=Depends(get_current_user)):
    """Return upload configuration (platform, max size, etc.)"""
    # Both Telegram and Bale Bot API have a 50MB upload limit for multipart uploads
    return {
        "platform": PLATFORM,
        "max_file_size": 50 * 1024 * 1024,
        "split_enabled": True,
        "split_threshold": 50 * 1024 * 1024,
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
    Falls back to 'document' type if the original type fails.
    """
    if not BOT_TOKEN:
        raise HTTPException(status_code=500, detail="BOT_TOKEN not configured")
    if not ADMIN_USER_IDS:
        raise HTTPException(status_code=500, detail="No admin users configured")

    if content_type not in UPLOAD_MAP:
        raise HTTPException(status_code=400, detail=f"Unsupported content type: {content_type}")

    chat_id = ADMIN_USER_IDS[0]

    # Read file content once
    file_data = await file.read()

    # Bale does not support sendAudio (MP3) — force audio/voice to document
    effective_type = content_type
    if PLATFORM == "bale" and content_type in ("audio", "voice"):
        logger.info(f"Bale platform: converting {content_type} → document for {file.filename}")
        effective_type = "document"

    # Try original type first, fallback to document
    attempts = [effective_type]
    if effective_type != "document":
        attempts.append("document")

    last_error = ""
    for attempt_type in attempts:
        method, response_key = UPLOAD_MAP[attempt_type]
        url = f"{API_BASE}/bot{BOT_TOKEN}/{method}"

        # Build form data for Telegram API
        form = aiohttp.FormData()
        form.add_field("chat_id", str(chat_id))
        form.add_field(response_key, file_data, filename=file.filename, content_type=file.content_type)
        form.add_field("disable_notification", "true")
        if caption:
            form.add_field("caption", caption)

        # Dynamic timeout: min 120s, +60s per 50MB of file data
        file_size_mb = len(file_data) / (1024 * 1024)
        timeout_seconds = max(120, int(60 + file_size_mb * 1.5))
        logger.info(f"Uploading {file.filename} ({file_size_mb:.1f}MB) via {method}, timeout={timeout_seconds}s")

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, data=form, timeout=aiohttp.ClientTimeout(total=timeout_seconds)) as resp:
                    result = await resp.json()
            except asyncio.TimeoutError:
                logger.error(f"Upload timed out after {timeout_seconds}s for {file.filename} ({file_size_mb:.1f}MB)")
                raise HTTPException(status_code=504, detail=f"تایم‌اوت آپلود — فایل {file_size_mb:.0f}MB خیلی بزرگ است یا سرور پاسخ نداد")
            except Exception as e:
                logger.error(f"Upload request failed: {e}")
                raise HTTPException(status_code=500, detail=f"خطا در اتصال به سرور: {str(e)}")

        if result.get("ok"):
            # Extract file_id from response
            msg = result.get("result", {})
            file_obj = msg.get(response_key)

            if not file_obj:
                last_error = "Could not extract file_id from response"
                continue

            # For photo, Telegram returns an array — use the largest one
            if isinstance(file_obj, list):
                file_obj = file_obj[-1]

            file_id = file_obj.get("file_id", "")
            if not file_id:
                last_error = "Empty file_id in response"
                continue

            actual_type = attempt_type
            if attempt_type != content_type:
                logger.info(f"Upload fallback: {content_type} -> {attempt_type} for {file.filename}")

            # Return original content_type so lesson delivery uses correct method
            # (on Bale, audio is uploaded as document but stored as "document")
            return {
                "file_id": file_id,
                "type": actual_type,
                "filename": file.filename,
            }
        else:
            error_desc = result.get('description', 'Unknown error')
            error_code = result.get('error_code', '?')
            last_error = f"({error_code}): {error_desc}"
            logger.warning(f"Bot API error [{error_code}]: {error_desc} (method={method}, file={file.filename}, size={len(file_data)})")
            if error_code == 413:
                file_mb = len(file_data) / (1024 * 1024)
                # If we have more attempts (fallback to document), try those first
                if attempt_type != effective_type or len(attempts) > attempts.index(attempt_type) + 1:
                    logger.info(f"413 on {method}, will try next fallback for {file.filename}")
                    continue
                raise HTTPException(
                    status_code=413,
                    detail=f"سرور فایل {file_mb:.0f}MB را نپذیرفت (خطای {error_code}). لطفاً فایل را کوچکتر کنید یا از قابلیت تقسیم خودکار استفاده کنید."
                )
            if attempt_type != content_type:
                # Already tried fallback
                pass
            elif "bad request" in error_desc.lower() or "malformed" in error_desc.lower():
                logger.info(f"Retrying upload as document (original type: {content_type})")
                continue
            else:
                # Non-format error, don't retry
                break

    raise HTTPException(
        status_code=500,
        detail=f"خطای آپلود {last_error}"
    )


# ── Helpers for splitting ────────────────────────────

MAX_PART_SIZE = 45 * 1024 * 1024  # 45MB to stay under Bale's 50MB limit


async def _get_video_duration(filepath: str) -> float:
    """Get video duration in seconds using ffprobe"""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        filepath,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    if proc.returncode != 0:
        return 0.0
    try:
        info = json.loads(stdout.decode())
        return float(info.get("format", {}).get("duration", 0))
    except (json.JSONDecodeError, ValueError):
        return 0.0


async def _split_video(filepath: str, output_dir: str, max_size: int = MAX_PART_SIZE) -> list[str]:
    """Split a video file into chunks using ffmpeg segment muxer."""
    file_size = os.path.getsize(filepath)
    duration = await _get_video_duration(filepath)

    if duration <= 0:
        # Can't determine duration — fall back to single-part document upload
        return [filepath]

    # Calculate segment time based on avg bitrate
    num_parts = max(2, int(file_size / max_size) + 1)
    segment_time = int(duration / num_parts) + 1  # +1 for safety

    ext = os.path.splitext(filepath)[1] or ".mp4"
    output_pattern = os.path.join(output_dir, f"part_%03d{ext}")

    cmd = [
        "ffmpeg", "-i", filepath,
        "-c", "copy",
        "-map", "0",
        "-segment_time", str(segment_time),
        "-f", "segment",
        "-reset_timestamps", "1",
        output_pattern,
    ]
    logger.info(f"Splitting video: {num_parts} parts, segment_time={segment_time}s, duration={duration:.1f}s")

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        logger.error(f"ffmpeg split failed: {stderr.decode()[:500]}")
        raise HTTPException(status_code=500, detail="خطا در تقسیم ویدیو با ffmpeg")

    # Collect generated parts, sorted
    parts = sorted(glob.glob(os.path.join(output_dir, f"part_*{ext}")))
    if not parts:
        raise HTTPException(status_code=500, detail="ffmpeg هیچ فایلی تولید نکرد")

    logger.info(f"Split into {len(parts)} parts: {[os.path.getsize(p) for p in parts]}")
    return parts


async def _upload_single_file(file_data: bytes, filename: str, content_type: str, chat_id: int) -> dict:
    """Upload a single file to Bot API and return result dict."""
    method, response_key = UPLOAD_MAP.get(content_type, UPLOAD_MAP["document"])
    url = f"{API_BASE}/bot{BOT_TOKEN}/{method}"

    form = aiohttp.FormData()
    form.add_field("chat_id", str(chat_id))
    form.add_field(response_key, file_data, filename=filename, content_type="application/octet-stream")
    form.add_field("disable_notification", "true")

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=form, timeout=aiohttp.ClientTimeout(total=180)) as resp:
            result = await resp.json()

    if not result.get("ok"):
        error_desc = result.get("description", "Unknown")
        raise HTTPException(status_code=500, detail=f"خطای آپلود قطعه: {error_desc}")

    msg = result.get("result", {})
    file_obj = msg.get(response_key)
    if isinstance(file_obj, list):
        file_obj = file_obj[-1]
    if not file_obj:
        raise HTTPException(status_code=500, detail="عدم دریافت file_id از سرور")

    return {
        "file_id": file_obj.get("file_id", ""),
        "type": content_type,
        "filename": filename,
    }


@router.post("/split")
async def upload_split(
    file: UploadFile = File(...),
    content_type: str = Form("video"),
    caption: str = Form(""),
    _=Depends(get_current_user),
):
    """
    Upload a large file by splitting it into parts.
    For video files: uses ffmpeg to split into playable segments.
    For other files: splits into raw byte chunks (sent as document).
    Returns an array of content blocks ready to be added to lesson contents.
    """
    if not BOT_TOKEN:
        raise HTTPException(status_code=500, detail="BOT_TOKEN not configured")
    if not ADMIN_USER_IDS:
        raise HTTPException(status_code=500, detail="No admin users configured")

    chat_id = ADMIN_USER_IDS[0]
    tmpdir = tempfile.mkdtemp(prefix="split_")

    try:
        # Save uploaded file to disk
        original_name = file.filename or "file"
        ext = os.path.splitext(original_name)[1] or ".mp4"
        input_path = os.path.join(tmpdir, f"original{ext}")

        file_data = await file.read()
        file_size = len(file_data)

        with open(input_path, "wb") as f:
            f.write(file_data)
        del file_data  # Free memory

        logger.info(f"Split upload: {original_name}, size={file_size}, type={content_type}")

        # If file is small enough, just upload normally
        if file_size <= MAX_PART_SIZE:
            with open(input_path, "rb") as f:
                data = f.read()

            result = await _upload_single_file(data, original_name, content_type, chat_id)
            part_item = {"type": result["type"], "file_id": result["file_id"]}
            if caption:
                part_item["caption"] = caption
            return {"parts": [part_item], "total_parts": 1}

        # Split the file
        is_video = content_type in ("video", "audio")
        parts_dir = os.path.join(tmpdir, "parts")
        os.makedirs(parts_dir, exist_ok=True)

        if is_video:
            # Video: split with ffmpeg (each part is playable)
            part_files = await _split_video(input_path, parts_dir)
            upload_type = "video"
        else:
            # Non-video: byte-split and upload as document
            part_files = []
            part_num = 0
            with open(input_path, "rb") as f:
                while True:
                    chunk = f.read(MAX_PART_SIZE)
                    if not chunk:
                        break
                    part_num += 1
                    part_path = os.path.join(parts_dir, f"part_{part_num:03d}{ext}")
                    with open(part_path, "wb") as pf:
                        pf.write(chunk)
                    part_files.append(part_path)
            upload_type = "document"

        total_parts = len(part_files)
        logger.info(f"Uploading {total_parts} parts...")

        # Upload each part
        results = []
        for i, part_path in enumerate(part_files):
            part_num = i + 1
            base_name = os.path.splitext(original_name)[0]
            part_name = f"{base_name}_part{part_num}of{total_parts}{ext}"

            with open(part_path, "rb") as f:
                part_data = f.read()

            part_size = len(part_data)

            # If a video part is still too big, upload as document
            actual_type = upload_type
            if part_size > MAX_PART_SIZE and actual_type == "video":
                actual_type = "document"
                logger.warning(f"Part {part_num} too large ({part_size}), uploading as document")

            try:
                result = await _upload_single_file(part_data, part_name, actual_type, chat_id)
            except HTTPException:
                # Fallback to document if video upload fails
                if actual_type != "document":
                    logger.info(f"Part {part_num}: fallback to document")
                    result = await _upload_single_file(part_data, part_name, "document", chat_id)
                else:
                    raise

            part_item = {"type": result["type"], "file_id": result["file_id"]}
            # Caption only on first part
            if i == 0 and caption:
                part_item["caption"] = caption
            results.append(part_item)

            logger.info(f"Part {part_num}/{total_parts} uploaded: {part_name} ({part_size} bytes)")

        return {"parts": results, "total_parts": total_parts}

    finally:
        # Cleanup temp files
        shutil.rmtree(tmpdir, ignore_errors=True)

