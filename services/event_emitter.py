"""
Event Emitter — Rich webhook system for CRM / n8n integration.

Emits standardised JSON events to all active webhook endpoints
with HMAC-SHA256 signing, idempotency keys, exponential backoff,
and a failed-event queue for reliable delivery.

Events
------
lead.register        New user signed up
lead.update          User profile updated
lesson.open          Lesson delivered to user
lesson.confirm       User confirmed a lesson
lesson.complete      Lesson completed
form.submit          User submitted a form
quiz.start           User started a quiz
quiz.pass            User passed a quiz
quiz.fail            User failed a quiz
course.complete      User completed a course
course.select        User selected a course
reminder.sent        Reminder sent to user
inactivity.timeout   User inactive for 48 h+
speed.change         Speed mode toggled
"""
import asyncio
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

import aiohttp
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session_maker
from database.models import WebhookSetting, WebhookFailedEvent, User
import config

logger = logging.getLogger(__name__)

# ───────────────────────── constants ─────────────────────────
BOT_USERNAME = getattr(config, "BOT_USERNAME", "course_bot")
WEBHOOK_SECRET = getattr(config, "WEBHOOK_SECRET", "")
FIELD_MAPPING = getattr(config, "FIELD_MAPPING", {})

MAX_IMMEDIATE_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds


# ───────────────────────── helpers ───────────────────────────

def _sign_payload(payload_bytes: bytes) -> str:
    """Generate HMAC-SHA256 signature for webhook verification."""
    if not WEBHOOK_SECRET:
        return ""
    return hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()


def _build_fields_mapping(user: User) -> tuple:
    """
    Split user registration_data into CRM fields vs notes
    based on FIELD_MAPPING config.

    Returns ``(fields_to_update, note_to_create)``.
    """
    fields_to_update: dict = {}
    note_parts: list = []

    reg_data = user.registration_data or {}
    for key, value in reg_data.items():
        mapping = FIELD_MAPPING.get(key)
        if mapping and mapping != "note":
            fields_to_update[mapping] = value
        else:
            note_parts.append(f"{key}: {value}")

    # Always include core user data as CRM fields
    fields_to_update["person.telegram_id"] = user.telegram_user_id
    fields_to_update["person.platform"] = getattr(user, "platform", config.PLATFORM)
    if user.username:
        fields_to_update["person.telegram_username"] = user.username
    if user.first_name:
        fields_to_update["person.first_name"] = user.first_name
    if user.last_name:
        fields_to_update["person.last_name"] = user.last_name

    note_text = "\n".join(note_parts) if note_parts else ""
    return fields_to_update, note_text


def _build_user_block(user: User) -> dict:
    """Build the ``user`` section of the event payload."""
    return {
        "telegram_id": user.telegram_user_id,
        "platform": getattr(user, "platform", config.PLATFORM),
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "registration_data": user.registration_data or {},
        "tags": user.tags or [],
        "referral_code": user.referral_code,
        "referred_by": user.referred_by,
        "is_active": user.is_active,
        "is_completed": user.is_completed,
        "created_at": (
            user.created_at.isoformat() if user.created_at else None
        ),
        "last_activity_at": (
            user.last_activity_at.isoformat() if user.last_activity_at else None
        ),
    }


# ───────────────────────── payload builder ───────────────────

def build_event_payload(
    event_type: str,
    action: str,
    user: User,
    status: str = "success",
    course: dict = None,
    lesson: dict = None,
    progress: dict = None,
    extra_payload: dict = None,
) -> dict:
    """
    Build the standardised event payload.

    Schema::

        {
            "event_id":   "uuid4",
            "event_time": "ISO-8601Z",
            "source":     "bot_username",
            "event":      {"type", "action", "status"},
            "user":       { … },
            "course":     { … } | null,
            "lesson":     { … } | null,
            "progress":   { … } | null,
            "payload":    {
                "fields_to_update": { … },
                "note_to_create":   "…",
                …extra
            },
            "security":   {"signature", "idempotency_key"}
        }
    """
    event_id = str(uuid.uuid4())

    fields_to_update, note_text = _build_fields_mapping(user)

    payload_block: dict = {
        "fields_to_update": fields_to_update,
        "note_to_create": note_text,
    }
    if extra_payload:
        payload_block.update(extra_payload)

    body: dict = {
        "event_id": event_id,
        "event_time": datetime.utcnow().isoformat() + "Z",
        "source": f"{BOT_USERNAME}@{config.PLATFORM}",
        "platform": config.PLATFORM,
        "event": {
            "type": event_type,
            "action": action,
            "status": status,
        },
        "user": _build_user_block(user),
        "course": course,
        "lesson": lesson,
        "progress": progress,
        "payload": payload_block,
    }

    # Sign the body (before adding security block)
    body_bytes = json.dumps(
        body, ensure_ascii=False, default=str,
    ).encode("utf-8")
    signature = _sign_payload(body_bytes)

    body["security"] = {
        "signature": signature,
        "idempotency_key": event_id,
    }

    return body


# ───────────────────────── transport ─────────────────────────

async def _send_to_endpoint(
    webhook: WebhookSetting,
    payload: dict,
    signature: str,
) -> bool:
    """Send payload to a single webhook endpoint with retries + backoff."""
    headers = dict(webhook.headers or {})
    headers.setdefault("Content-Type", "application/json")

    if signature:
        headers["X-Webhook-Signature"] = signature
        headers["X-Idempotency-Key"] = payload.get("security", {}).get(
            "idempotency_key", "",
        )

    for attempt in range(MAX_IMMEDIATE_RETRIES):
        try:
            async with aiohttp.ClientSession() as http_session:
                async with http_session.post(
                    webhook.url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=webhook.timeout),
                ) as response:
                    if response.status < 400:
                        ev = payload.get("event", {})
                        event_key = f"{ev.get('type')}.{ev.get('action')}"
                        logger.info(
                            f"[EventEmitter] [{webhook.name}] {event_key} "
                            f"sent (HTTP {response.status})"
                        )
                        return True
                    else:
                        logger.warning(
                            f"[EventEmitter] [{webhook.name}] HTTP {response.status} "
                            f"(attempt {attempt + 1}/{MAX_IMMEDIATE_RETRIES})"
                        )
        except Exception as e:
            logger.warning(
                f"[EventEmitter] [{webhook.name}] error "
                f"(attempt {attempt + 1}/{MAX_IMMEDIATE_RETRIES}): {e}"
            )

        # Exponential back-off between retries
        if attempt < MAX_IMMEDIATE_RETRIES - 1:
            await asyncio.sleep(RETRY_BASE_DELAY * (2 ** attempt))

    return False


# ───────────────────────── failed event queue ────────────────

async def _store_failed_event(
    webhook_id: int,
    webhook_name: str,
    event_type: str,
    payload: dict,
    error_msg: str,
):
    """Store a failed event in DB for later retry (own session)."""
    try:
        async with async_session_maker() as session:
            failed = WebhookFailedEvent(
                event_id=payload.get("event_id", str(uuid.uuid4())),
                webhook_id=webhook_id,
                webhook_name=webhook_name,
                event_type=event_type,
                payload=payload,
                error_message=error_msg,
                retry_count=0,
                next_retry_at=datetime.utcnow() + timedelta(minutes=5),
            )
            session.add(failed)
            await session.commit()
            logger.info(
                f"[EventEmitter] Stored failed event {event_type} "
                f"for retry (webhook: {webhook_name})"
            )
    except Exception as e:
        logger.error(f"[EventEmitter] Failed to store failed event: {e}")


# ───────────────────────── public API ────────────────────────

async def emit(
    event_type: str,
    action: str,
    user: User,
    session: AsyncSession,
    status: str = "success",
    course: dict = None,
    lesson: dict = None,
    progress: dict = None,
    extra_payload: dict = None,
):
    """
    Emit an event to **all** active webhook endpoints.

    Parameters
    ----------
    event_type : str   – e.g. ``"lead"``, ``"lesson"``, ``"quiz"``
    action     : str   – e.g. ``"register"``, ``"open"``, ``"pass"``
    user       : User  – SQLAlchemy user object (attributes read, no lazy loads)
    session    : AsyncSession – used **read-only** to query active webhooks
    status     : str   – ``"success"`` (default) or a custom status
    course     : dict  – ``{"id": …, "title": …}`` or ``None``
    lesson     : dict  – ``{"id": …, "title": …, "order": …}`` or ``None``
    progress   : dict  – ``{"percent": …, "completed": …, "total": …}`` or ``None``
    extra_payload : dict – merged into ``payload`` block

    Usage::

        await emit("lead", "register", user, session)
        await emit("lesson", "complete", user, session,
                   course={"id": 1, "title": "…"},
                   lesson={"id": 5, "title": "…", "order": 5},
                   progress={"percent": 60, "completed": 3, "total": 5})
    """
    try:
        payload = build_event_payload(
            event_type=event_type,
            action=action,
            user=user,
            status=status,
            course=course,
            lesson=lesson,
            progress=progress,
            extra_payload=extra_payload,
        )

        signature = payload.get("security", {}).get("signature", "")
        event_key = f"{event_type}.{action}"

        # Query active webhooks (read-only)
        result = await session.execute(
            select(WebhookSetting).where(WebhookSetting.is_active == True)
        )
        webhooks = list(result.scalars().all())

        if not webhooks:
            logger.debug(f"[EventEmitter] No active webhooks for {event_key}")
            return

        for webhook in webhooks:
            success = await _send_to_endpoint(webhook, payload, signature)
            if not success:
                await _store_failed_event(
                    webhook.id,
                    webhook.name,
                    event_key,
                    payload,
                    f"Failed after {MAX_IMMEDIATE_RETRIES} immediate retries",
                )
    except Exception as e:
        logger.error(f"[EventEmitter] emit({event_type}.{action}) error: {e}")


# ───────────────────────── scheduler helpers ─────────────────

async def retry_failed_events(session: AsyncSession):
    """
    Retry failed webhook events.  Called by scheduler.

    Back-off: 5 min → 15 min → 45 min → 2 h 15 min → 6 h 45 min → abandon
    """
    MAX_RETRIES = 5
    now = datetime.utcnow()

    result = await session.execute(
        select(WebhookFailedEvent).where(
            and_(
                WebhookFailedEvent.resolved_at.is_(None),
                WebhookFailedEvent.retry_count < MAX_RETRIES,
                WebhookFailedEvent.next_retry_at <= now,
            )
        ).limit(50)
    )
    events = list(result.scalars().all())

    if not events:
        return {"retried": 0, "resolved": 0, "abandoned": 0}

    resolved = 0
    abandoned = 0

    for event in events:
        wh_result = await session.execute(
            select(WebhookSetting).where(
                and_(
                    WebhookSetting.id == event.webhook_id,
                    WebhookSetting.is_active == True,
                )
            )
        )
        webhook = wh_result.scalar_one_or_none()

        if not webhook:
            event.resolved_at = now
            event.error_message = "Webhook no longer active"
            resolved += 1
            continue

        signature = ""
        if event.payload:
            signature = event.payload.get("security", {}).get("signature", "")

        success = await _send_to_endpoint(webhook, event.payload, signature)

        if success:
            event.resolved_at = now
            resolved += 1
        else:
            event.retry_count += 1
            if event.retry_count >= MAX_RETRIES:
                event.resolved_at = now
                event.error_message = f"Abandoned after {MAX_RETRIES} retries"
                abandoned += 1
            else:
                delay = 5 * (3 ** event.retry_count)
                event.next_retry_at = now + timedelta(minutes=delay)

    await session.commit()

    logger.info(
        f"[EventEmitter] Retry: {len(events)} processed, "
        f"{resolved} resolved, {abandoned} abandoned"
    )
    return {"retried": len(events), "resolved": resolved, "abandoned": abandoned}


async def check_inactive_users(session: AsyncSession):
    """
    Emit ``inactivity.timeout`` for users inactive 48 h+.

    Called by scheduler.  Emits for *all* qualifying users each run;
    n8n should deduplicate by ``user.telegram_id`` if needed.
    """
    cutoff = datetime.utcnow() - timedelta(hours=48)

    result = await session.execute(
        select(User).where(
            and_(
                User.is_active == True,
                User.is_completed == False,
                User.last_activity_at < cutoff,
            )
        )
    )
    users = list(result.scalars().all())

    emitted = 0
    for user in users:
        days_inactive = (
            (datetime.utcnow() - user.last_activity_at).days
            if user.last_activity_at
            else 0
        )
        await emit(
            "inactivity", "timeout", user, session,
            extra_payload={"days_inactive": days_inactive},
        )
        emitted += 1

    if emitted:
        logger.info(
            f"[EventEmitter] Emitted inactivity.timeout for {emitted} users"
        )
    return {"emitted": emitted}
