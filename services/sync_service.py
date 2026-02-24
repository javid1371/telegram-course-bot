"""
Cross-Platform Sync Service — Phase 1 (Monitor Only)

Captures user-progress events into the ``sync_events`` table so we can
measure volume, verify correctness, and prepare for Phase 3 (actual push).

This module is called from ``event_emitter.emit()`` as a fire-and-forget
side listener.  It opens its **own** DB session so it never interferes
with the caller's transaction.

Events captured
---------------
* lesson.complete  — user finished viewing / confirming a lesson
* quiz.pass / quiz.fail — quiz result
* form.submit — form response submitted
* course.complete — all lessons in a course done
* lead.register — new user registered (phone captured)

Phone extraction
----------------
The user's phone is read from ``registration_data.mobile`` (or
``registration_data.phone`` as fallback).  If no phone is found the event
is still logged with ``status='skipped'`` — it can't be matched on the
peer platform but we keep it for auditing.
"""

import logging
from typing import Optional

from database import async_session_maker
from database.models import SyncEvent, User

logger = logging.getLogger(__name__)

# Event types we care about for cross-platform sync
SYNC_EVENT_TYPES = frozenset({
    "lesson.complete",
    "lesson.open",
    "quiz.pass",
    "quiz.fail",
    "form.submit",
    "course.complete",
    "lead.register",
})


def _extract_phone(user: User) -> Optional[str]:
    """Extract phone number from user's registration_data."""
    rd = user.registration_data
    if not rd or not isinstance(rd, dict):
        return None
    # Try 'mobile' first (that's the actual field name), then 'phone' as fallback
    phone = rd.get("mobile") or rd.get("phone")
    if phone and isinstance(phone, str):
        return phone.strip()
    return None


async def log_sync_event(
    event_type: str,
    action: str,
    user: User,
    course: dict = None,
    lesson: dict = None,
    progress: dict = None,
    extra: dict = None,
) -> None:
    """
    Log a sync-relevant event to the sync_events table.

    This is called as fire-and-forget from event_emitter.emit().
    Uses its own DB session to avoid interfering with the caller.

    Parameters
    ----------
    event_type : str  – e.g. "lesson"
    action     : str  – e.g. "complete"
    user       : User – SQLAlchemy user object (attributes are read)
    course     : dict – {"id": …, "title": …} or None
    lesson     : dict – {"id": …, "title": …, "order": …} or None
    progress   : dict – {"percent": …, "completed": …, "total": …} or None
    extra      : dict – extra payload (quiz answers, form responses, etc.)
    """
    event_key = f"{event_type}.{action}"

    # Only capture events relevant to cross-platform sync
    if event_key not in SYNC_EVENT_TYPES:
        return

    try:
        phone = _extract_phone(user)

        payload = {
            "event": event_key,
            "user_id": user.id,
            "telegram_user_id": user.telegram_user_id,
            "platform": user.platform if hasattr(user, "platform") else "unknown",
            "phone": phone,
        }
        if course:
            payload["course"] = course
        if lesson:
            payload["lesson"] = lesson
        if progress:
            payload["progress"] = progress
        if extra:
            # Don't store huge blobs — cherry-pick useful fields
            for key in ("score", "passed", "answers", "form_responses", "quiz_passing_score"):
                if key in extra:
                    payload[key] = extra[key]

        status = "logged"   # Phase 1: monitor only
        if not phone:
            status = "skipped"  # Can't match across platforms without phone

        async with async_session_maker() as session:
            event = SyncEvent(
                event_type=event_key,
                user_id=user.id,
                phone=phone,
                payload=payload,
                status=status,
            )
            session.add(event)
            await session.commit()

        logger.info(
            f"[SyncService] Logged {event_key} for user {user.telegram_user_id} "
            f"(phone={'yes' if phone else 'NO'}, status={status})"
        )

    except Exception as e:
        # Fire-and-forget — never crash the main bot flow
        logger.error(f"[SyncService] Failed to log {event_key}: {e}")
