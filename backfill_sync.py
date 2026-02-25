"""
One-time backfill script: sync all existing users to the peer platform.

Reads all non-shadow users with phone numbers from the LOCAL database,
then pushes them as events to the PEER server's /api/sync/receive endpoint.
The peer will create shadow users + snapshots for each.

Usage (inside Docker container):
    python backfill_sync.py

Environment variables used:
    SYNC_PEER_URL  — peer server URL (e.g. http://195.177.255.133:8080)
    SYNC_SECRET    — shared sync secret
"""

import asyncio
import logging
import json
from datetime import datetime, timezone

import aiohttp
from sqlalchemy import select, text

import config
from database import async_session_maker
from database.models import User, UserProgress, QuizAttempt, FormResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 20  # Events per HTTP request


def _extract_phone(user: User) -> str | None:
    rd = user.registration_data
    if not rd or not isinstance(rd, dict):
        return None
    return rd.get("mobile") or rd.get("phone")


async def _build_user_events(session, user: User) -> list[dict]:
    """Build a list of sync events for one user (register + progress)."""
    phone = _extract_phone(user)
    if not phone:
        return []

    events = []

    # Base payload
    base = {
        "user_id": user.id,
        "telegram_user_id": user.telegram_user_id,
        "platform": user.platform or config.PLATFORM,
        "phone": phone,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "registration_data": user.registration_data,
        "current_course_id": user.current_course_id,
        "current_lesson_id": user.current_lesson_id,
        "completed_courses": user.completed_courses,
        "is_completed": user.is_completed,
        "lead_score": user.lead_score,
        "tags": user.tags,
    }

    # 1) Registration event
    events.append({**base, "event": "lead.register"})

    # 2) Completed lessons
    progress_result = await session.execute(
        select(UserProgress).where(
            UserProgress.user_id == user.id,
            UserProgress.completed_at.isnot(None),
        )
    )
    for p in progress_result.scalars().all():
        events.append({
            **base,
            "event": "lesson.complete",
            "lesson": {
                "id": p.lesson_id,
                "order": None,
            },
        })

    # 3) Quiz attempts
    quiz_result = await session.execute(
        select(QuizAttempt).where(QuizAttempt.user_id == user.id)
    )
    for q in quiz_result.scalars().all():
        event_type = "quiz.pass" if q.passed else "quiz.fail"
        events.append({
            **base,
            "event": event_type,
            "lesson": {"id": q.lesson_id},
            "score": q.score,
            "passed": q.passed,
            "answers": q.answers,
        })

    # 4) Form responses
    form_result = await session.execute(
        select(FormResponse).where(FormResponse.user_id == user.id)
    )
    for f in form_result.scalars().all():
        events.append({
            **base,
            "event": "form.submit",
            "lesson": {"id": f.lesson_id},
            "form_responses": f.response_data,
        })

    return events


async def _push_batch(http: aiohttp.ClientSession, events: list[dict]) -> bool:
    """Push a batch of events to the peer."""
    url = f"{config.SYNC_PEER_URL}/api/sync/receive"
    headers = {
        "Content-Type": "application/json",
        "X-Sync-Secret": config.SYNC_SECRET,
    }
    try:
        async with http.post(
            url,
            json={"events": events},
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status < 400:
                body = await resp.json()
                logger.info(f"  Batch OK ({len(events)} events): {body}")
                return True
            else:
                body = await resp.text()
                logger.error(f"  Batch FAILED HTTP {resp.status}: {body[:200]}")
                return False
    except Exception as e:
        logger.error(f"  Batch ERROR: {e}")
        return False


async def main():
    if not config.SYNC_PEER_URL or not config.SYNC_SECRET:
        logger.error("SYNC_PEER_URL or SYNC_SECRET not configured!")
        return

    logger.info(f"Platform: {config.PLATFORM}")
    logger.info(f"Peer URL: {config.SYNC_PEER_URL}")

    # Gather all events
    all_events = []
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.is_shadow == False)
        )
        users = result.scalars().all()

        logger.info(f"Found {len(users)} real users to backfill")

        for user in users:
            events = await _build_user_events(session, user)
            if events:
                all_events.extend(events)

    logger.info(f"Total events to push: {len(all_events)}")

    # Push in batches
    pushed = 0
    failed = 0
    async with aiohttp.ClientSession() as http:
        for i in range(0, len(all_events), BATCH_SIZE):
            batch = all_events[i:i + BATCH_SIZE]
            ok = await _push_batch(http, batch)
            if ok:
                pushed += len(batch)
            else:
                failed += len(batch)
            # Small delay to avoid overwhelming peer
            await asyncio.sleep(0.5)

    logger.info(f"Done! Pushed: {pushed}, Failed: {failed}")


if __name__ == "__main__":
    asyncio.run(main())
