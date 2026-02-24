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
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session_maker
from database.models import WebhookSetting, WebhookFailedEvent, User, CompanyInfo, ScheduledMessage, MessageStatus, RegistrationField
import config

logger = logging.getLogger(__name__)

# ───────────────────────── constants ─────────────────────────
BOT_USERNAME = getattr(config, "BOT_USERNAME", "course_bot")
WEBHOOK_SECRET = getattr(config, "WEBHOOK_SECRET", "")

# Fallback mapping used when DB has no crm_field configured
_FALLBACK_FIELD_MAPPING = {
    "name": "person.name",
    "full_name": "person.name",
    "last_name": "person.last_name",
    "family": "person.last_name",
    "phone": "person.phone",
    "mobile": "person.phone",
    "email": "person.email",
}

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


def _build_fields_mapping(user: User, field_mappings: dict = None) -> tuple:
    """
    Split user registration_data into CRM fields vs notes
    using dynamic field_mappings from DB (with fallback to defaults).

    Parameters
    ----------
    user : User
    field_mappings : dict
        ``{field_name: crm_field}`` from RegistrationField table.
        If None, uses ``_FALLBACK_FIELD_MAPPING``.

    Returns ``(fields_to_update, note_to_create)``.
    """
    mapping = field_mappings if field_mappings is not None else _FALLBACK_FIELD_MAPPING

    fields_to_update: dict = {}
    note_parts: list = []

    reg_data = user.registration_data or {}
    for key, value in reg_data.items():
        crm_field = mapping.get(key)
        if crm_field and crm_field != "note":
            fields_to_update[crm_field] = value
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


def _build_crm_fields_json(data: dict, field_mappings: dict, lead_score: int = 0) -> str:
    """
    Build a ready-to-use JSON string of ``{didar_field_id: value}``
    that n8n can pass directly to Didar API ``Fields`` parameter.

    Only includes fields whose ``crm_field`` looks like a Didar custom
    field ID (starts with ``Field_`` or is a single-letter like ``J``).

    Parameters
    ----------
    data : dict
        Key/value pairs (e.g. form_responses or registration_data).
    field_mappings : dict
        ``{field_name: crm_field}`` from RegistrationField table.
    lead_score : int
        If > 0, also includes lead_score in the JSON (using the
        ``lead_score`` key from field_mappings if available).

    Returns
    -------
    str
        JSON string like ``'{"Field_996_0_26": "5000000"}'``.
    """
    crm_fields = {}
    for key, value in data.items():
        crm_field = field_mappings.get(key, "")
        if crm_field and crm_field != "note" and not crm_field.startswith("person."):
            # This is a custom field ID (e.g. Field_996_0_26, J)
            crm_fields[crm_field] = str(value)

    # Add lead_score if mapping exists
    lead_score_field = field_mappings.get("lead_score", "")
    if lead_score_field and lead_score > 0:
        crm_fields[lead_score_field] = str(lead_score)

    return json.dumps(crm_fields) if crm_fields else "{}"


def _build_user_block(user: User) -> dict:
    """Build the ``user`` section of the event payload."""
    reg = user.registration_data or {}
    # Phone field may be stored as "phone" or "mobile" depending on registration_fields config
    phone = reg.get("phone") or reg.get("mobile") or ""
    # Also check any field with PHONE-like key names
    if not phone:
        for k, v in reg.items():
            if isinstance(v, str) and v.startswith("09") and len(v) >= 10:
                phone = v
                break
    return {
        "telegram_id": user.telegram_user_id,
        "platform": getattr(user, "platform", config.PLATFORM),
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "registration_data": reg,
        "tags": user.tags or [],
        "referral_code": user.referral_code,
        "referred_by": user.referred_by,
        "is_active": user.is_active,
        "is_completed": user.is_completed,
        "lead_score": user.lead_score or 0,
        "phone": phone,
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
    field_mappings: dict = None,
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
                "crm_field_mapping": { … },
                …extra
            },
            "security":   {"signature", "idempotency_key"}
        }
    """
    event_id = str(uuid.uuid4())

    fields_to_update, note_text = _build_fields_mapping(user, field_mappings)

    payload_block: dict = {
        "fields_to_update": fields_to_update,
        "note_to_create": note_text,
    }

    # Include dynamic CRM field mapping so n8n can use it
    if field_mappings:
        payload_block["crm_field_mapping"] = field_mappings

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
) -> tuple:
    """
    Send payload to a single webhook endpoint with retries + backoff.

    Returns (success: bool, response_data: dict | None)
    """
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
                        # Try to parse JSON response body
                        response_data = None
                        try:
                            response_data = await response.json()
                        except Exception:
                            pass
                        return True, response_data
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

    return False, None


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


# ───────────────────────── owner assignment ──────────────────

async def _process_owner_assignment(user, response_data: dict, session):
    """
    Parse owner info from webhook response and assign to user.

    Expected response format from n8n::

        {
            "status": "ok",
            "owner": {
                "id": "didar-owner-id",
                "name": "Owner Name"
            }
        }
    """
    try:
        owner_block = response_data.get("owner")
        if not owner_block:
            return

        owner_id = owner_block.get("id")
        owner_name = owner_block.get("name")

        if not owner_name and not owner_id:
            return

        from services.support_service import SupportService
        support_service = SupportService(session)
        await support_service.assign_owner_to_user(
            user=user,
            didar_owner_id=owner_id,
            owner_name=owner_name,
        )
        logger.info(
            f"[EventEmitter] Owner assigned from webhook response: "
            f"{owner_name} (didar_id={owner_id}) → user {user.telegram_user_id}"
        )
    except Exception as e:
        logger.error(f"[EventEmitter] _process_owner_assignment error: {e}")


# ───────────────────────── sales trigger check ──────────────

async def _check_sales_trigger(lesson_order: int, session: AsyncSession) -> bool:
    """
    Check if this lesson_order matches the admin-configured
    ``sales_trigger_lesson`` value.
    """
    try:
        result = await session.execute(
            select(CompanyInfo).where(CompanyInfo.key == 'sales_trigger_lesson')
        )
        row = result.scalar_one_or_none()
        if not row or not row.value:
            return False
        trigger_lesson = int(row.value)
        return trigger_lesson > 0 and lesson_order == trigger_lesson
    except (ValueError, TypeError):
        return False


# ───────────────────────── webhook snapshot helper ───────────

class _WebhookSnapshot:
    """Lightweight stand-in for WebhookSetting ORM objects used after session closes."""
    __slots__ = ("id", "name", "url", "headers", "timeout", "events")

    def __init__(self, id, name, url, headers, timeout, events):
        self.id = id
        self.name = name
        self.url = url
        self.headers = headers
        self.timeout = timeout
        self.events = events


def _snap_to_webhook_obj(snap: dict) -> _WebhookSnapshot:
    return _WebhookSnapshot(
        id=snap["id"],
        name=snap["name"],
        url=snap["url"],
        headers=snap["headers"],
        timeout=snap["timeout"],
        events=snap.get("events"),
    )


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
    # ── Cross-platform sync: log event (fire-and-forget) ──
    try:
        from services.sync_service import log_sync_event
        asyncio.create_task(
            log_sync_event(
                event_type=event_type,
                action=action,
                user=user,
                course=course,
                lesson=lesson,
                progress=progress,
                extra=extra_payload,
            )
        )
    except Exception:
        pass  # Never break main flow for sync logging

    try:
        event_key = f"{event_type}.{action}"

        # ── Lead scoring: update user score in its own session to avoid greenlet issues ──
        try:
            from services.scoring_service import ScoringService
            async with async_session_maker() as scoring_session:
                scoring_svc = ScoringService(scoring_session)
                # Re-load user in scoring session to safely update lead_score
                from sqlalchemy import select as _sel
                _u = (await scoring_session.execute(
                    _sel(User).where(User.id == user.id)
                )).scalar_one_or_none()
                if _u:
                    new_score = await scoring_svc.update_user_score(_u, event_key)
                    # Sync score back to caller's user object (in-memory only)
                    user.lead_score = new_score
        except Exception as e:
            logger.warning(f"[EventEmitter] scoring error: {e}")

        # ── Sales trigger & webhook query in own session ──
        # Re-load user in a fresh session to avoid greenlet_spawn errors
        # when accessing lazy-loaded attributes outside the caller's session.
        trigger_sales = False
        webhook_snapshots = []
        fresh_user = None
        field_mappings = {}
        async with async_session_maker() as emit_session:
            # Re-load user to safely access all attributes
            from sqlalchemy import select as _sel2
            fresh_user = (await emit_session.execute(
                _sel2(User).where(User.id == user.id)
            )).scalar_one_or_none()
            if not fresh_user:
                fresh_user = user  # fallback

            # ── Load dynamic CRM field mappings from DB ──
            try:
                reg_fields_result = await emit_session.execute(
                    select(RegistrationField).where(RegistrationField.is_active == True)
                )
                for rf in reg_fields_result.scalars().all():
                    if rf.crm_field:
                        field_mappings[rf.field_name] = rf.crm_field
            except Exception as e:
                logger.warning(f"[EventEmitter] Failed to load field mappings: {e}")

            # Merge with fallback for unmapped fields
            merged_mappings = dict(_FALLBACK_FIELD_MAPPING)
            merged_mappings.update(field_mappings)

            if event_key == "lesson.complete" and lesson:
                lesson_order = lesson.get("order", 0)
                if lesson_order:
                    trigger_sales = await _check_sales_trigger(lesson_order, emit_session)

            # Query active webhooks (read-only)
            result = await emit_session.execute(
                select(WebhookSetting).where(WebhookSetting.is_active == True)
            )
            webhooks = list(result.scalars().all())

            if not webhooks:
                logger.debug(f"[EventEmitter] No active webhooks for {event_key}")
                return

            # Filter by events list
            for webhook in webhooks:
                if webhook.events:
                    try:
                        allowed = webhook.events if isinstance(webhook.events, list) else json.loads(webhook.events)
                        if event_key not in allowed:
                            logger.debug(
                                f"[EventEmitter] [{webhook.name}] skipping {event_key} (not in events filter)"
                            )
                            continue
                    except (json.JSONDecodeError, TypeError):
                        pass  # malformed → send anyway
                webhook_snapshots.append({
                    "id": webhook.id,
                    "name": webhook.name,
                    "url": webhook.url,
                    "headers": dict(webhook.headers or {}),
                    "timeout": webhook.timeout,
                    "events": webhook.events,
                })

            # Build payload INSIDE session so user attributes are accessible
            if trigger_sales:
                extra_payload = extra_payload or {}
                extra_payload["trigger_sales"] = True

            extra_payload = extra_payload or {}
            lead_score = fresh_user.lead_score or 0
            extra_payload["lead_score"] = lead_score

            # ── Build ready-to-use CRM field JSON strings for n8n ──
            # lead_score_field_json: used by Prep Register/Lesson/Complete
            lead_score_field = merged_mappings.get("lead_score", "")
            if lead_score_field and lead_score > 0:
                extra_payload["lead_score_field_json"] = json.dumps(
                    {lead_score_field: str(lead_score)}
                )
            else:
                extra_payload["lead_score_field_json"] = "{}"

            # crm_form_fields_json: for form.submit — form_responses mapped to CRM field IDs
            if event_key == "form.submit" and extra_payload.get("form_responses"):
                extra_payload["crm_form_fields_json"] = _build_crm_fields_json(
                    extra_payload["form_responses"],
                    merged_mappings,
                    lead_score=lead_score,
                )

            payload = build_event_payload(
                event_type=event_type,
                action=action,
                user=fresh_user,
                status=status,
                course=course,
                lesson=lesson,
                progress=progress,
                extra_payload=extra_payload,
                field_mappings=merged_mappings,
            )

        signature = payload.get("security", {}).get("signature", "")

        if not webhook_snapshots:
            return

        # Fire webhook deliveries as a background task so bot responses aren't blocked.
        # The only exception: lead.register needs the response for owner assignment,
        # so that one is awaited inline.
        if event_key == "lead.register":
            for wh_snap in webhook_snapshots:
                wh_obj = _snap_to_webhook_obj(wh_snap)
                success, response_data = await _send_to_endpoint(wh_obj, payload, signature)
                if not success:
                    await _store_failed_event(
                        wh_snap["id"], wh_snap["name"], event_key, payload,
                        f"Failed after {MAX_IMMEDIATE_RETRIES} immediate retries",
                    )
                elif response_data:
                    await _process_owner_assignment(user, response_data, session)
        else:
            wh_objs = [_snap_to_webhook_obj(s) for s in webhook_snapshots]
            asyncio.create_task(
                _deliver_webhooks_background(wh_objs, event_key, payload, signature)
            )

    except Exception as e:
        logger.error(f"[EventEmitter] emit({event_type}.{action}) error: {e}")


async def _deliver_webhooks_background(webhooks, event_key, payload, signature):
    """Background task: deliver payload to webhook endpoints without blocking the caller."""
    for webhook in webhooks:
        try:
            success, _ = await _send_to_endpoint(webhook, payload, signature)
            if not success:
                await _store_failed_event(
                    webhook.id, webhook.name, event_key, payload,
                    f"Failed after {MAX_IMMEDIATE_RETRIES} immediate retries",
                )
        except Exception as e:
            logger.error(f"[EventEmitter] background delivery error [{webhook.name}]: {e}")


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

        success, _ = await _send_to_endpoint(webhook, event.payload, signature)

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

    Called by scheduler.  Deduplicates using ScheduledMessage table so
    each user only gets the event once per 7 days.
    """
    cutoff = datetime.utcnow() - timedelta(hours=48)
    dedup_window = datetime.utcnow() - timedelta(days=7)

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
        # ── Dedup: skip if already emitted within the last 7 days ──
        existing = await session.execute(
            select(func.count(ScheduledMessage.id)).where(
                ScheduledMessage.user_id == user.id,
                ScheduledMessage.message_type == "inactivity_timeout",
                ScheduledMessage.sent_at > dedup_window,
            )
        )
        if (existing.scalar() or 0) > 0:
            continue

        days_inactive = (
            (datetime.utcnow() - user.last_activity_at).days
            if user.last_activity_at
            else 0
        )
        await emit(
            "inactivity", "timeout", user, session,
            extra_payload={"days_inactive": days_inactive},
        )

        # Record emission for dedup
        now = datetime.utcnow()
        session.add(ScheduledMessage(
            user_id=user.id,
            message=f"inactivity.timeout emitted (inactive {days_inactive}d)",
            message_type="inactivity_timeout",
            send_at=now,
            status=MessageStatus.SENT,
            sent_at=now,
        ))

        emitted += 1

    if emitted:
        await session.commit()
        logger.info(
            f"[EventEmitter] Emitted inactivity.timeout for {emitted} users"
        )
    return {"emitted": emitted}
