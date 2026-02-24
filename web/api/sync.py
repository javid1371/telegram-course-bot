"""
Cross-Platform Sync API — Export / Import course content between Telegram & Bale.

Design:
  • Export endpoint on the SOURCE server (e.g. Telegram) dumps all course
    structure (courses, lessons, registration fields, bot texts, company info,
    webhook settings, lead scoring rules) **except** platform-specific file_ids.
  • Import endpoint on the TARGET server (e.g. Bale) upserts everything.
  • Media file_ids are NOT synced — they must be re-uploaded on the target
    platform via the admin panel (Telegram and Bale have different file_id spaces).
  • Protected by SYNC_SECRET (shared between the two servers), or by admin JWT.
"""
import os
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select, delete

from database import async_session_maker
from sqlalchemy import func as sa_func

from database.models import (
    Course, Lesson, RegistrationField, BotText, CompanyInfo,
    WebhookSetting, LeadScoringRule, ContentType,
    User, UserProgress, QuizAttempt, FormResponse, PlatformFileId,
    SyncEvent,
)
from web.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

SYNC_SECRET = os.getenv("SYNC_SECRET", "")
PLATFORM = os.getenv("PLATFORM", "telegram").lower()


# ── Auth helper ──────────────────────────────────────────────
def _verify_sync_secret(x_sync_secret: Optional[str] = Header(None)):
    """Allow access if valid admin JWT OR valid SYNC_SECRET header."""
    # If SYNC_SECRET is configured, require it via header
    if SYNC_SECRET and x_sync_secret == SYNC_SECRET:
        return True
    return None  # Fall through to JWT check


# ── EXPORT ───────────────────────────────────────────────────
@router.get("/export")
async def export_all(_=Depends(get_current_user)):
    """
    Export all course content and settings as JSON.
    File_ids in lesson contents are included but marked — the target
    platform must re-upload files and replace them.
    """
    async with async_session_maker() as session:
        # Courses
        courses_result = await session.execute(
            select(Course).order_by(Course.order, Course.id)
        )
        courses = courses_result.scalars().all()

        courses_data = []
        for c in courses:
            courses_data.append({
                "id": c.id,
                "title": c.title,
                "description": c.description,
                "is_active": c.is_active,
                "order": c.order,
                "allow_2x": c.allow_2x,
                "allow_fast_track": c.allow_fast_track,
                "fast_track_delay": c.fast_track_delay,
            })

        # Lessons
        lessons_result = await session.execute(
            select(Lesson).order_by(Lesson.course_id, Lesson.order, Lesson.id)
        )
        lessons = lessons_result.scalars().all()

        lessons_data = []
        for l in lessons:
            lessons_data.append({
                "id": l.id,
                "course_id": l.course_id,
                "title": l.title,
                "description": l.description,
                "content_type": l.content_type.value if l.content_type else "TEXT",
                "file_id": l.file_id,
                "text_content": l.text_content,
                "order": l.order,
                "lesson_number": l.lesson_number,
                "is_active": l.is_active,
                "delay_hours": l.delay_hours,
                "view_deadline_hours": l.view_deadline_hours,
                "cta_text": l.cta_text,
                "cta_url": l.cta_url,
                "contents": l.contents,
                "quiz_data": l.quiz_data,
                "form_data": l.form_data,
            })

        # Registration Fields
        regfields_result = await session.execute(
            select(RegistrationField).order_by(RegistrationField.order)
        )
        regfields = regfields_result.scalars().all()
        regfields_data = []
        for f in regfields:
            regfields_data.append({
                "id": f.id,
                "field_name": f.field_name,
                "field_label": f.field_label,
                "field_type": f.field_type.value if f.field_type else "text",
                "is_required": f.is_required,
                "order": f.order,
                "validation_rule": f.validation_rule,
                "options": f.options,
                "is_active": f.is_active,
                "crm_field": f.crm_field,
            })

        # Bot Texts
        bot_texts_result = await session.execute(select(BotText))
        bot_texts = bot_texts_result.scalars().all()
        bot_texts_data = [
            {"category": t.category, "key": t.key, "value": t.value}
            for t in bot_texts
        ]

        # Company Info
        company_result = await session.execute(select(CompanyInfo))
        company_info = company_result.scalars().all()
        company_data = [
            {"key": c.key, "value": c.value}
            for c in company_info
        ]

        # Lead Scoring Rules
        scoring_result = await session.execute(select(LeadScoringRule))
        scoring_rules = scoring_result.scalars().all()
        scoring_data = [
            {
                "event_type": r.event_type,
                "points": r.points,
                "label": r.label,
                "is_active": r.is_active,
            }
            for r in scoring_rules
        ]

        # Webhook Settings
        webhook_result = await session.execute(select(WebhookSetting))
        webhooks = webhook_result.scalars().all()
        webhook_data = [
            {
                "name": w.name,
                "url": w.url,
                "method": w.method,
                "payload_template": w.payload_template,
                "headers": w.headers,
                "is_active": w.is_active,
                "retry_count": w.retry_count,
                "timeout": w.timeout,
                "events": w.events,
            }
            for w in webhooks
        ]

        return {
            "exported_at": datetime.utcnow().isoformat(),
            "source_platform": PLATFORM,
            "courses": courses_data,
            "lessons": lessons_data,
            "registration_fields": regfields_data,
            "bot_texts": bot_texts_data,
            "company_info": company_data,
            "lead_scoring_rules": scoring_data,
            "webhook_settings": webhook_data,
        }


# ── IMPORT ───────────────────────────────────────────────────
from pydantic import BaseModel
from typing import List, Any


class SyncPayload(BaseModel):
    """Payload from the export endpoint."""
    source_platform: str = ""
    courses: list = []
    lessons: list = []
    registration_fields: list = []
    bot_texts: list = []
    company_info: list = []
    lead_scoring_rules: list = []
    webhook_settings: list = []
    # Options
    skip_file_ids: bool = True          # Don't import file_ids (different per platform)
    clear_before_import: bool = True    # Truncate target tables before insert


@router.post("/import")
async def import_all(data: SyncPayload, _=Depends(get_current_user)):
    """
    Import course content and settings from export payload.
    By default, clears existing data and re-creates everything.
    File_ids are skipped (set to None) because they're platform-specific.
    """
    stats = {}

    async with async_session_maker() as session:
        # ── 1. Courses ──
        if data.courses:
            if data.clear_before_import:
                # Clear FK references from users before deleting lessons/courses
                from sqlalchemy import update
                await session.execute(
                    update(User).where(User.current_lesson_id.isnot(None))
                    .values(current_lesson_id=None)
                )
                await session.execute(
                    update(User).where(User.current_course_id.isnot(None))
                    .values(current_course_id=None)
                )
                # Clear dependent tables
                await session.execute(delete(QuizAttempt))
                await session.execute(delete(FormResponse))
                await session.execute(delete(UserProgress))
                await session.execute(delete(PlatformFileId))
                await session.execute(delete(Lesson))
                await session.execute(delete(Course))
                await session.flush()

            id_map = {}  # old course_id -> new course_id
            for c in data.courses:
                course = Course(
                    title=c["title"],
                    description=c.get("description"),
                    is_active=c.get("is_active", True),
                    order=c.get("order", 0),
                    allow_2x=c.get("allow_2x", False),
                    allow_fast_track=c.get("allow_fast_track", False),
                    fast_track_delay=c.get("fast_track_delay", 5),
                )
                session.add(course)
                await session.flush()
                id_map[c["id"]] = course.id

            stats["courses"] = len(data.courses)

            # ── 2. Lessons ──
            for l_data in data.lessons:
                old_course_id = l_data.get("course_id")
                new_course_id = id_map.get(old_course_id, old_course_id)

                # Content type
                try:
                    ct = ContentType(l_data.get("content_type", "TEXT"))
                except ValueError:
                    ct = ContentType.TEXT

                # Strip file_ids from contents if skip_file_ids
                contents = l_data.get("contents")
                file_id = l_data.get("file_id")
                if data.skip_file_ids:
                    file_id = None
                    if contents:
                        for block in contents:
                            if block.get("file_id"):
                                block["file_id"] = None

                lesson = Lesson(
                    course_id=new_course_id,
                    title=l_data["title"],
                    description=l_data.get("description"),
                    content_type=ct,
                    file_id=file_id,
                    text_content=l_data.get("text_content"),
                    order=l_data.get("order", 0),
                    lesson_number=l_data.get("lesson_number"),
                    is_active=l_data.get("is_active", True),
                    delay_hours=l_data.get("delay_hours", 0),
                    view_deadline_hours=l_data.get("view_deadline_hours"),
                    cta_text=l_data.get("cta_text"),
                    cta_url=l_data.get("cta_url"),
                    contents=contents,
                    quiz_data=l_data.get("quiz_data"),
                    form_data=l_data.get("form_data"),
                )
                session.add(lesson)

            stats["lessons"] = len(data.lessons)

        # ── 3. Registration Fields ──
        if data.registration_fields:
            if data.clear_before_import:
                await session.execute(delete(RegistrationField))
                await session.flush()

            for f in data.registration_fields:
                from database.models import FieldType
                try:
                    ft = FieldType(f.get("field_type", "text"))
                except ValueError:
                    ft = FieldType.TEXT

                field = RegistrationField(
                    field_name=f["field_name"],
                    field_label=f["field_label"],
                    field_type=ft,
                    is_required=f.get("is_required", True),
                    order=f.get("order", 0),
                    validation_rule=f.get("validation_rule"),
                    options=f.get("options"),
                    is_active=f.get("is_active", True),
                    crm_field=f.get("crm_field"),
                )
                session.add(field)
            stats["registration_fields"] = len(data.registration_fields)

        # ── 4. Bot Texts ──
        if data.bot_texts:
            if data.clear_before_import:
                await session.execute(delete(BotText))
                await session.flush()

            for t in data.bot_texts:
                text = BotText(
                    category=t["category"],
                    key=t["key"],
                    value=t["value"],
                )
                session.add(text)
            stats["bot_texts"] = len(data.bot_texts)

        # ── 5. Company Info ──
        if data.company_info:
            if data.clear_before_import:
                await session.execute(delete(CompanyInfo))
                await session.flush()

            for c in data.company_info:
                info = CompanyInfo(
                    key=c["key"],
                    value=c["value"],
                )
                session.add(info)
            stats["company_info"] = len(data.company_info)

        # ── 6. Lead Scoring Rules ──
        if data.lead_scoring_rules:
            if data.clear_before_import:
                await session.execute(delete(LeadScoringRule))
                await session.flush()

            for r in data.lead_scoring_rules:
                rule = LeadScoringRule(
                    event_type=r["event_type"],
                    points=r.get("points", 0),
                    label=r.get("label", r["event_type"]),
                    is_active=r.get("is_active", True),
                )
                session.add(rule)
            stats["lead_scoring_rules"] = len(data.lead_scoring_rules)

        # ── 7. Webhook Settings ──
        if data.webhook_settings:
            if data.clear_before_import:
                await session.execute(delete(WebhookSetting))
                await session.flush()

            for w in data.webhook_settings:
                wh = WebhookSetting(
                    name=w["name"],
                    url=w["url"],
                    method=w.get("method", "POST"),
                    payload_template=w.get("payload_template"),
                    headers=w.get("headers"),
                    is_active=w.get("is_active", True),
                    retry_count=w.get("retry_count", 3),
                    timeout=w.get("timeout", 10),
                    events=w.get("events"),
                )
                session.add(wh)
            stats["webhook_settings"] = len(data.webhook_settings)

        await session.commit()

    logger.info(f"Sync import completed: {stats}")
    return {
        "ok": True,
        "imported": stats,
        "target_platform": PLATFORM,
        "file_ids_skipped": data.skip_file_ids,
    }


# ── STATUS ───────────────────────────────────────────────────
@router.get("/status")
async def sync_status(_=Depends(get_current_user)):
    """Quick summary of content on this platform."""
    async with async_session_maker() as session:
        from sqlalchemy import func

        course_count = (await session.execute(
            select(func.count(Course.id))
        )).scalar() or 0

        lesson_count = (await session.execute(
            select(func.count(Lesson.id))
        )).scalar() or 0

        # Count lessons with file_id
        lessons_with_files = (await session.execute(
            select(func.count(Lesson.id)).where(Lesson.file_id.isnot(None))
        )).scalar() or 0

        # Count lessons with quiz/form
        lessons_with_quiz = (await session.execute(
            select(func.count(Lesson.id)).where(Lesson.quiz_data.isnot(None))
        )).scalar() or 0

        lessons_with_form = (await session.execute(
            select(func.count(Lesson.id)).where(Lesson.form_data.isnot(None))
        )).scalar() or 0

        # Count file_id references in contents JSON
        file_id_blocks = 0
        all_lessons = (await session.execute(select(Lesson))).scalars().all()
        for l in all_lessons:
            if l.contents:
                for block in l.contents:
                    if block.get("file_id"):
                        file_id_blocks += 1

        return {
            "platform": PLATFORM,
            "courses": course_count,
            "lessons": lesson_count,
            "lessons_with_files": lessons_with_files,
            "lessons_with_quiz": lessons_with_quiz,
            "lessons_with_form": lessons_with_form,
            "file_id_blocks_in_contents": file_id_blocks,
            "needs_file_upload": file_id_blocks > 0 or lessons_with_files > 0,
        }


# ═══════════════════════════════════════════════════════════════
# SYNC EVENT MONITORING (Phase 1)
# ═══════════════════════════════════════════════════════════════

@router.get("/events/stats")
async def sync_event_stats(user=Depends(get_current_user)):
    """
    Summary of sync events captured (Phase 1 monitoring).

    Returns event counts by type and status, plus recent events.
    """
    async with async_session_maker() as session:
        # Count by event_type
        type_counts = await session.execute(
            select(
                SyncEvent.event_type,
                sa_func.count(SyncEvent.id),
            ).group_by(SyncEvent.event_type)
        )
        by_type = {row[0]: row[1] for row in type_counts.all()}

        # Count by status
        status_counts = await session.execute(
            select(
                SyncEvent.status,
                sa_func.count(SyncEvent.id),
            ).group_by(SyncEvent.status)
        )
        by_status = {row[0]: row[1] for row in status_counts.all()}

        # Total
        total = sum(by_type.values())

        # Unique phones (users that can be matched cross-platform)
        phone_count = await session.execute(
            select(sa_func.count(sa_func.distinct(SyncEvent.phone))).where(
                SyncEvent.phone.isnot(None)
            )
        )
        unique_phones = phone_count.scalar() or 0

        # Last 20 events
        recent = await session.execute(
            select(SyncEvent)
            .order_by(SyncEvent.id.desc())
            .limit(20)
        )
        recent_events = [
            {
                "id": e.id,
                "event_type": e.event_type,
                "user_id": e.user_id,
                "phone": e.phone,
                "status": e.status,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "payload": e.payload,
            }
            for e in recent.scalars().all()
        ]

    return {
        "platform": PLATFORM,
        "total_events": total,
        "by_type": by_type,
        "by_status": by_status,
        "unique_phones": unique_phones,
        "recent_events": recent_events,
    }
