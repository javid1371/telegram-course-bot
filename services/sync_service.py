"""
Cross-Platform Sync Service — Full Bidirectional Sync

Captures user-progress events, pushes them to the peer server in real-time,
and processes incoming events to maintain "shadow profiles" (SyncUserSnapshot).

When a user registers on this platform and their phone matches a snapshot,
their progress is restored automatically — even if the inter-server link
is currently down (because the snapshot was pre-cached while it was up).

Architecture
------------
1. Bot event → emit() → log_sync_event() → save to sync_events + try push
2. If push fails → stays 'pending' → scheduler retries every 30s
3. Peer receives event → updates SyncUserSnapshot for that phone
4. User /start on peer → phone match → apply snapshot → progress restored

This module is called from event_emitter.emit() as a fire-and-forget
side listener.  It opens its own DB session so it never interferes
with the caller's transaction.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import aiohttp
import sqlalchemy as sa

import config
from database import async_session_maker
from database.models import SyncEvent, SyncUserSnapshot, User, UserProgress, QuizAttempt, FormResponse

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

SYNC_PEER_URL = config.SYNC_PEER_URL  # e.g. "http://195.177.255.133:8080"
SYNC_SECRET = config.SYNC_SECRET


def _extract_phone(user: User) -> Optional[str]:
    """Extract phone number from user's registration_data."""
    rd = user.registration_data
    if not rd or not isinstance(rd, dict):
        return None
    phone = rd.get("mobile") or rd.get("phone")
    if phone and isinstance(phone, str):
        return phone.strip()
    return None


# ═════════════════════════════════════════════════════════════
# EVENT LOGGING + IMMEDIATE PUSH
# ═════════════════════════════════════════════════════════════

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
    Log a sync-relevant event and attempt immediate push to peer.

    Called as fire-and-forget from event_emitter.emit().
    Uses its own DB session to avoid interfering with the caller.
    """
    event_key = f"{event_type}.{action}"

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
            "first_name": user.first_name,
            "last_name": user.last_name,
            "registration_data": user.registration_data,
            "current_course_id": user.current_course_id,
            "current_lesson_id": user.current_lesson_id,
            "completed_courses": user.completed_courses,
            "is_completed": user.is_completed if hasattr(user, "is_completed") else False,
            "lead_score": user.lead_score if hasattr(user, "lead_score") else 0,
            "tags": user.tags if hasattr(user, "tags") else None,
        }
        if course:
            payload["course"] = course
        if lesson:
            payload["lesson"] = lesson
        if progress:
            payload["progress"] = progress
        if extra:
            for key in ("score", "passed", "answers", "form_responses", "quiz_passing_score"):
                if key in extra:
                    payload[key] = extra[key]

        # Determine initial status
        if not phone:
            status = "skipped"
        elif SYNC_PEER_URL:
            status = "pending"
        else:
            status = "logged"  # No peer configured → just log

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
            event_id = event.id

        logger.info(
            f"[SyncService] Logged {event_key} for user {user.telegram_user_id} "
            f"(phone={'yes' if phone else 'NO'}, status={status})"
        )

        # Attempt immediate push if peer is configured and we have a phone
        if status == "pending" and SYNC_PEER_URL:
            asyncio.create_task(_push_single_event(event_id, payload))

    except Exception as e:
        logger.error(f"[SyncService] Failed to log {event_key}: {e}")


async def _push_single_event(event_id: int, payload: dict) -> bool:
    """Push a single event to the peer server. Update status on success/failure."""
    try:
        url = f"{SYNC_PEER_URL}/api/sync/receive"
        headers = {
            "Content-Type": "application/json",
            "X-Sync-Secret": SYNC_SECRET,
        }

        async with aiohttp.ClientSession() as http:
            async with http.post(
                url,
                json={"events": [payload]},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status < 400:
                    async with async_session_maker() as session:
                        from sqlalchemy import update
                        await session.execute(
                            update(SyncEvent)
                            .where(SyncEvent.id == event_id)
                            .values(
                                status="synced",
                                synced_at=datetime.now(timezone.utc),
                            )
                        )
                        await session.commit()
                    logger.info(f"[SyncService] Pushed event {event_id} to peer ✓")
                    return True
                else:
                    body = await resp.text()
                    logger.warning(
                        f"[SyncService] Push event {event_id} failed: HTTP {resp.status} — {body[:200]}"
                    )
                    return False

    except Exception as e:
        logger.warning(f"[SyncService] Push event {event_id} error: {e}")
        return False


# ═════════════════════════════════════════════════════════════
# SCHEDULER: FLUSH PENDING EVENTS
# ═════════════════════════════════════════════════════════════

async def flush_pending_events() -> dict:
    """
    Push all pending sync events to the peer server.
    Called by the scheduler every 30 seconds as a safety net.
    Returns stats dict.
    """
    if not SYNC_PEER_URL or not SYNC_SECRET:
        return {"flushed": 0, "failed": 0, "skipped": "no peer configured"}

    from sqlalchemy import select

    try:
        async with async_session_maker() as session:
            result = await session.execute(
                select(SyncEvent)
                .where(SyncEvent.status == "pending")
                .order_by(SyncEvent.id)
                .limit(50)
            )
            events = list(result.scalars().all())

        if not events:
            return {"flushed": 0, "failed": 0}

        # Batch push
        payloads = [e.payload for e in events]
        event_ids = [e.id for e in events]

        try:
            url = f"{SYNC_PEER_URL}/api/sync/receive"
            headers = {
                "Content-Type": "application/json",
                "X-Sync-Secret": SYNC_SECRET,
            }

            async with aiohttp.ClientSession() as http:
                async with http.post(
                    url,
                    json={"events": payloads},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status < 400:
                        # Mark all as synced
                        async with async_session_maker() as session:
                            from sqlalchemy import update
                            await session.execute(
                                update(SyncEvent)
                                .where(SyncEvent.id.in_(event_ids))
                                .values(
                                    status="synced",
                                    synced_at=datetime.now(timezone.utc),
                                )
                            )
                            await session.commit()
                        logger.info(f"[SyncService] Flushed {len(events)} events to peer ✓")
                        return {"flushed": len(events), "failed": 0}
                    else:
                        # Increment retry count
                        async with async_session_maker() as session:
                            from sqlalchemy import update
                            await session.execute(
                                update(SyncEvent)
                                .where(SyncEvent.id.in_(event_ids))
                                .values(retry_count=SyncEvent.retry_count + 1)
                            )
                            await session.commit()
                        logger.warning(
                            f"[SyncService] Flush failed: HTTP {resp.status}"
                        )
                        return {"flushed": 0, "failed": len(events)}

        except Exception as e:
            logger.warning(f"[SyncService] Flush error: {e}")
            return {"flushed": 0, "failed": len(events)}

    except Exception as e:
        logger.error(f"[SyncService] flush_pending_events error: {e}")
        return {"flushed": 0, "failed": 0, "error": str(e)}


# ═════════════════════════════════════════════════════════════
# RECEIVE: PROCESS INCOMING EVENTS FROM PEER
# ═════════════════════════════════════════════════════════════

async def process_received_events(events: list) -> dict:
    """
    Process a batch of events received from the peer server.
    Updates SyncUserSnapshot AND creates/updates shadow User + Progress records.

    Returns {"processed": N, "skipped": N, "errors": N}
    """
    processed = 0
    skipped = 0
    errors = 0

    for event_data in events:
        try:
            phone = event_data.get("phone")
            if not phone:
                skipped += 1
                continue

            await _update_snapshot(phone, event_data)
            await _upsert_shadow_user(phone, event_data)
            processed += 1

        except Exception as e:
            logger.error(f"[SyncService] Error processing event: {e}")
            errors += 1

    logger.info(
        f"[SyncService] Received batch: {processed} processed, "
        f"{skipped} skipped (no phone), {errors} errors"
    )
    return {"processed": processed, "skipped": skipped, "errors": errors}


async def _update_snapshot(phone: str, event_data: dict) -> None:
    """Create or update a SyncUserSnapshot for the given phone."""
    from sqlalchemy import select

    event_key = event_data.get("event", "")

    async with async_session_maker() as session:
        result = await session.execute(
            select(SyncUserSnapshot).where(SyncUserSnapshot.phone == phone)
        )
        snapshot = result.scalar_one_or_none()

        if not snapshot:
            snapshot = SyncUserSnapshot(
                phone=phone,
                source_platform=event_data.get("platform", "unknown"),
                registration_data=event_data.get("registration_data"),
                first_name=event_data.get("first_name"),
                last_name=event_data.get("last_name"),
                progress_records=[],
                quiz_attempts=[],
                form_responses=[],
                events_applied=0,
            )
            session.add(snapshot)

        # Always update these from the latest event
        snapshot.source_platform = event_data.get("platform", snapshot.source_platform)
        if event_data.get("registration_data"):
            snapshot.registration_data = event_data["registration_data"]
        if event_data.get("first_name"):
            snapshot.first_name = event_data["first_name"]
        if event_data.get("last_name"):
            snapshot.last_name = event_data["last_name"]
        if event_data.get("current_course_id") is not None:
            snapshot.current_course_id = event_data["current_course_id"]
        if event_data.get("current_lesson_id") is not None:
            snapshot.current_lesson_id = event_data["current_lesson_id"]
        if event_data.get("completed_courses") is not None:
            snapshot.completed_courses = event_data["completed_courses"]
        if event_data.get("is_completed"):
            snapshot.is_completed = event_data["is_completed"]
        if event_data.get("lead_score"):
            snapshot.lead_score = event_data["lead_score"]
        if event_data.get("tags"):
            snapshot.tags = event_data["tags"]

        # Append to progress records
        if event_key == "lesson.complete":
            records = snapshot.progress_records or []
            lesson_info = event_data.get("lesson", {})
            lesson_id = lesson_info.get("id")
            if lesson_id and not any(r.get("lesson_id") == lesson_id for r in records):
                records.append({
                    "lesson_id": lesson_id,
                    "lesson_order": lesson_info.get("order"),
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                })
                snapshot.progress_records = records

        # Append quiz attempt
        if event_key in ("quiz.pass", "quiz.fail"):
            attempts = snapshot.quiz_attempts or []
            lesson_info = event_data.get("lesson", {})
            attempts.append({
                "lesson_id": lesson_info.get("id"),
                "score": event_data.get("score"),
                "passed": event_data.get("passed"),
                "answers": event_data.get("answers"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            snapshot.quiz_attempts = attempts

        # Append form response
        if event_key == "form.submit":
            responses = snapshot.form_responses or []
            lesson_info = event_data.get("lesson", {})
            responses.append({
                "lesson_id": lesson_info.get("id"),
                "form_responses": event_data.get("form_responses"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            snapshot.form_responses = responses

        snapshot.events_applied = (snapshot.events_applied or 0) + 1
        await session.commit()

    logger.debug(f"[SyncService] Updated snapshot for phone={phone} event={event_key}")


# ═════════════════════════════════════════════════════════════
# SHADOW USER: CREATE/UPDATE REAL DB RECORDS FROM PEER EVENTS
# ═════════════════════════════════════════════════════════════

async def _find_shadow_user_by_phone(session, phone: str) -> Optional[User]:
    """Find a shadow user by phone in registration_data (current platform only)."""
    from sqlalchemy import select, cast, String as SAString
    import config as cfg

    # Search in registration_data JSONB for 'mobile' or 'phone' keys
    result = await session.execute(
        select(User).where(
            User.platform == cfg.PLATFORM,
            User.is_shadow == True,
            sa.or_(
                User.registration_data['mobile'].astext == phone,
                User.registration_data['phone'].astext == phone,
            ),
        )
    )
    return result.scalar_one_or_none()


async def _upsert_shadow_user(phone: str, event_data: dict) -> None:
    """
    Create or update a shadow User + UserProgress from a peer event.

    Shadow users have:
      - telegram_user_id = 0 (placeholder, updated on /start)
      - is_shadow = True
      - platform = current platform (the receiving side)
      - Real UserProgress / QuizAttempt / FormResponse records

    When the user actually /start's on this platform, the shadow user is
    activated: is_shadow → False, telegram_user_id → real ID.
    """
    import config as cfg
    from sqlalchemy import select

    event_key = event_data.get("event", "")

    try:
        async with async_session_maker() as session:
            # Find existing shadow user by phone
            shadow = await _find_shadow_user_by_phone(session, phone)

            if not shadow:
                # Only create shadow on registration or first event
                reg_data = event_data.get("registration_data") or {}
                # Ensure phone is in registration_data
                if not reg_data.get("mobile") and not reg_data.get("phone"):
                    reg_data["mobile"] = phone

                shadow = User(
                    telegram_user_id=0,  # Placeholder — updated on /start
                    username=None,
                    first_name=event_data.get("first_name"),
                    last_name=event_data.get("last_name"),
                    platform=cfg.PLATFORM,
                    is_shadow=True,
                    registration_data=reg_data,
                    current_course_id=event_data.get("current_course_id"),
                    current_lesson_id=event_data.get("current_lesson_id"),
                    completed_courses=event_data.get("completed_courses"),
                    is_completed=event_data.get("is_completed", False),
                    lead_score=event_data.get("lead_score", 0),
                    tags=event_data.get("tags"),
                )
                session.add(shadow)
                await session.flush()  # Get shadow.id
                logger.info(
                    f"[SyncService] Created shadow user id={shadow.id} "
                    f"for phone={phone} on {cfg.PLATFORM}"
                )
            else:
                # Update existing shadow fields
                if event_data.get("first_name"):
                    shadow.first_name = event_data["first_name"]
                if event_data.get("last_name"):
                    shadow.last_name = event_data["last_name"]
                if event_data.get("registration_data"):
                    rd = shadow.registration_data or {}
                    rd.update(event_data["registration_data"])
                    shadow.registration_data = rd
                if event_data.get("current_course_id") is not None:
                    shadow.current_course_id = event_data["current_course_id"]
                if event_data.get("current_lesson_id") is not None:
                    shadow.current_lesson_id = event_data["current_lesson_id"]
                if event_data.get("completed_courses") is not None:
                    shadow.completed_courses = event_data["completed_courses"]
                if event_data.get("is_completed"):
                    shadow.is_completed = event_data["is_completed"]
                if event_data.get("lead_score"):
                    shadow.lead_score = event_data["lead_score"]
                if event_data.get("tags"):
                    shadow.tags = event_data["tags"]

            # ── Create real progress records ──
            if event_key == "lesson.complete":
                lesson_info = event_data.get("lesson", {})
                lesson_id = lesson_info.get("id")
                if lesson_id:
                    existing = await session.execute(
                        select(UserProgress).where(
                            UserProgress.user_id == shadow.id,
                            UserProgress.lesson_id == lesson_id,
                        )
                    )
                    if not existing.scalar_one_or_none():
                        session.add(UserProgress(
                            user_id=shadow.id,
                            lesson_id=lesson_id,
                            completed_at=datetime.now(timezone.utc),
                        ))

            # ── Create real quiz attempt records ──
            if event_key in ("quiz.pass", "quiz.fail"):
                lesson_info = event_data.get("lesson", {})
                lesson_id = lesson_info.get("id")
                if lesson_id:
                    session.add(QuizAttempt(
                        user_id=shadow.id,
                        lesson_id=lesson_id,
                        score=event_data.get("score", 0),
                        passed=event_data.get("passed", False),
                        answers=event_data.get("answers"),
                    ))

            # ── Create real form response records ──
            if event_key == "form.submit":
                lesson_info = event_data.get("lesson", {})
                lesson_id = lesson_info.get("id")
                if lesson_id:
                    session.add(FormResponse(
                        user_id=shadow.id,
                        lesson_id=lesson_id,
                        response_data=event_data.get("form_responses") or {},
                    ))

            await session.commit()
            logger.debug(
                f"[SyncService] Shadow user {shadow.id} updated for "
                f"phone={phone} event={event_key}"
            )

    except Exception as e:
        logger.error(f"[SyncService] _upsert_shadow_user error: {e}")


# ═════════════════════════════════════════════════════════════
# APPLY SNAPSHOT: RESTORE PROGRESS WHEN USER REGISTERS
# ═════════════════════════════════════════════════════════════

async def find_snapshot_by_phone(phone: str) -> Optional[SyncUserSnapshot]:
    """Look up a SyncUserSnapshot by phone number."""
    from sqlalchemy import select

    async with async_session_maker() as session:
        result = await session.execute(
            select(SyncUserSnapshot).where(
                SyncUserSnapshot.phone == phone,
                SyncUserSnapshot.applied_to_user_id.is_(None),  # not yet consumed
            )
        )
        return result.scalar_one_or_none()


async def apply_snapshot_to_user(user_id: int, snapshot_id: int) -> dict:
    """
    Apply a SyncUserSnapshot to a newly registered user.
    Restores: current_course_id, current_lesson_id, completed_courses,
    UserProgress records, QuizAttempts, FormResponses.

    Returns summary of what was restored.
    """
    from sqlalchemy import select

    async with async_session_maker() as session:
        # Load snapshot
        snap = await session.get(SyncUserSnapshot, snapshot_id)
        if not snap:
            return {"error": "Snapshot not found"}

        # Load user
        user = await session.get(User, user_id)
        if not user:
            return {"error": "User not found"}

        restored = {
            "course_id": None,
            "lesson_id": None,
            "progress_records": 0,
            "quiz_attempts": 0,
            "form_responses": 0,
        }

        # Restore course progress pointers
        if snap.current_course_id:
            user.current_course_id = snap.current_course_id
            restored["course_id"] = snap.current_course_id
        if snap.current_lesson_id:
            user.current_lesson_id = snap.current_lesson_id
            restored["lesson_id"] = snap.current_lesson_id
        if snap.completed_courses:
            user.completed_courses = snap.completed_courses
        if snap.is_completed:
            user.is_completed = snap.is_completed
        if snap.lead_score:
            user.lead_score = snap.lead_score
        if snap.tags:
            user.tags = snap.tags

        # Restore UserProgress records
        if snap.progress_records:
            for pr in snap.progress_records:
                lesson_id = pr.get("lesson_id")
                if not lesson_id:
                    continue
                # Check if progress already exists
                existing = await session.execute(
                    select(UserProgress).where(
                        UserProgress.user_id == user_id,
                        UserProgress.lesson_id == lesson_id,
                    )
                )
                if existing.scalar_one_or_none():
                    continue  # Already exists

                progress = UserProgress(
                    user_id=user_id,
                    lesson_id=lesson_id,
                    completed_at=datetime.now(timezone.utc),
                )
                session.add(progress)
                restored["progress_records"] += 1

        # Restore QuizAttempts
        if snap.quiz_attempts:
            for qa in snap.quiz_attempts:
                lesson_id = qa.get("lesson_id")
                if not lesson_id:
                    continue
                attempt = QuizAttempt(
                    user_id=user_id,
                    lesson_id=lesson_id,
                    score=qa.get("score", 0),
                    passed=qa.get("passed", False),
                    answers=qa.get("answers"),
                )
                session.add(attempt)
                restored["quiz_attempts"] += 1

        # Restore FormResponses
        if snap.form_responses:
            for fr in snap.form_responses:
                lesson_id = fr.get("lesson_id")
                if not lesson_id:
                    continue
                response = FormResponse(
                    user_id=user_id,
                    lesson_id=lesson_id,
                    response_data=fr.get("form_responses") or {},
                )
                session.add(response)
                restored["form_responses"] += 1

        # Mark snapshot as consumed
        snap.applied_to_user_id = user_id
        snap.applied_at = datetime.now(timezone.utc)

        await session.commit()

    logger.info(
        f"[SyncService] Applied snapshot {snapshot_id} to user {user_id}: "
        f"{restored['progress_records']} lessons, {restored['quiz_attempts']} quizzes, "
        f"{restored['form_responses']} forms"
    )
    return restored


# ═════════════════════════════════════════════════════════════
# SHADOW USER ACTIVATION: WHEN USER /start's ON THIS PLATFORM
# ═════════════════════════════════════════════════════════════

async def find_shadow_user_by_phone(phone: str) -> Optional[User]:
    """Find a shadow user by phone on the current platform."""
    import config as cfg
    from sqlalchemy import select

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(
                User.platform == cfg.PLATFORM,
                User.is_shadow == True,
                sa.or_(
                    User.registration_data['mobile'].astext == phone,
                    User.registration_data['phone'].astext == phone,
                ),
            )
        )
        return result.scalar_one_or_none()


async def activate_shadow_user(
    shadow_user_id: int,
    telegram_user_id: int,
    username: Optional[str] = None,
) -> Optional[User]:
    """
    Activate a shadow user when they actually /start on this platform.

    Updates:
      - telegram_user_id → real messenger user ID
      - is_shadow → False
      - username → from the /start message

    Returns the activated User, or None on error.
    """
    from sqlalchemy import select

    try:
        async with async_session_maker() as session:
            user = await session.get(User, shadow_user_id)
            if not user:
                logger.warning(f"[SyncService] Shadow user {shadow_user_id} not found")
                return None

            if not user.is_shadow:
                logger.warning(f"[SyncService] User {shadow_user_id} is not a shadow user")
                return user  # Already activated

            user.telegram_user_id = telegram_user_id
            user.is_shadow = False
            if username:
                user.username = username

            await session.commit()
            await session.refresh(user)

            logger.info(
                f"[SyncService] Activated shadow user {shadow_user_id} → "
                f"telegram_user_id={telegram_user_id}, progress records intact"
            )

            # Mark snapshot as consumed (if any)
            phone = None
            if user.registration_data:
                phone = (
                    user.registration_data.get("mobile")
                    or user.registration_data.get("phone")
                )
            if phone:
                result = await session.execute(
                    select(SyncUserSnapshot).where(
                        SyncUserSnapshot.phone == phone,
                        SyncUserSnapshot.applied_to_user_id.is_(None),
                    )
                )
                snap = result.scalar_one_or_none()
                if snap:
                    snap.applied_to_user_id = user.id
                    snap.applied_at = datetime.now(timezone.utc)
                    await session.commit()

            return user

    except Exception as e:
        logger.error(f"[SyncService] activate_shadow_user error: {e}")
        return None
