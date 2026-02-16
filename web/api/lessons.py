"""
Lesson CRUD + Content Management API Routes
"""
import copy
from typing import Optional, List, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from database import async_session_maker
from database.models import Lesson, ContentType
from web.auth import get_current_user

router = APIRouter()


# ── Pydantic Models ──────────────────────────────────────

class LessonCreate(BaseModel):
    course_id: int
    title: str
    description: Optional[str] = None
    content_type: str = "text"
    is_active: bool = True
    order: int = 0
    delay_hours: int = 0
    view_deadline_hours: Optional[int] = None
    cta_text: Optional[str] = None
    cta_url: Optional[str] = None
    text_content: Optional[str] = None
    file_id: Optional[str] = None


class LessonUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    order: Optional[int] = None
    delay_hours: Optional[int] = None
    view_deadline_hours: Optional[int] = None
    cta_text: Optional[str] = None
    cta_url: Optional[str] = None


class ContentItem(BaseModel):
    type: str  # text, video, audio, voice, document, photo, form
    text: Optional[str] = None
    file_id: Optional[str] = None
    caption: Optional[str] = None


class FormField(BaseModel):
    name: str
    label: str
    type: str  # text, number, select
    options: Optional[List[str]] = None


class FormData(BaseModel):
    fields: List[FormField]


class ContentReorder(BaseModel):
    """Full list of content items in new order."""
    contents: List[ContentItem]


# ── Helpers ──────────────────────────────────────────────

def _get_lesson_contents(lesson: Lesson) -> list[dict]:
    """Build the content list from lesson, same logic as admin handler."""
    if lesson.contents:
        return copy.deepcopy(lesson.contents)

    contents = []
    if lesson.file_id:
        item = {"type": lesson.content_type.value if lesson.content_type else "text", "file_id": lesson.file_id}
        if lesson.text_content:
            item["caption"] = lesson.text_content
        contents.append(item)
    elif lesson.text_content:
        contents.append({"type": "text", "text": lesson.text_content})

    if not contents and lesson.form_data:
        contents.append({"type": "form", "form_data": lesson.form_data})

    return contents


def _sync_primary_fields(lesson: Lesson, contents: list[dict]):
    """Sync content_type/file_id/text_content from first content block."""
    if not contents:
        lesson.content_type = ContentType.TEXT
        lesson.file_id = None
        lesson.text_content = None
        return

    first = contents[0]
    ctype = first.get("type", "text")
    try:
        lesson.content_type = ContentType(ctype)
    except ValueError:
        lesson.content_type = ContentType.TEXT

    if ctype == "text":
        lesson.file_id = None
        lesson.text_content = first.get("text", "")
    elif ctype == "form":
        lesson.content_type = ContentType.FORM
        lesson.file_id = None
        lesson.text_content = None
    else:
        lesson.file_id = first.get("file_id", "")
        lesson.text_content = first.get("caption", "")


# ── Routes ───────────────────────────────────────────────

@router.get("/{lesson_id}")
async def get_lesson(lesson_id: int, _=Depends(get_current_user)):
    async with async_session_maker() as session:
        lesson = await session.get(Lesson, lesson_id)
        if not lesson:
            raise HTTPException(status_code=404, detail="درس یافت نشد")
        contents = _get_lesson_contents(lesson)
        return {
            "id": lesson.id,
            "course_id": lesson.course_id,
            "title": lesson.title,
            "description": lesson.description,
            "content_type": lesson.content_type.value if lesson.content_type else "text",
            "is_active": lesson.is_active,
            "order": lesson.order,
            "delay_hours": lesson.delay_hours,
            "view_deadline_hours": lesson.view_deadline_hours,
            "cta_text": lesson.cta_text,
            "cta_url": lesson.cta_url,
            "has_quiz": bool(lesson.quiz_data),
            "has_form": bool(lesson.form_data),
            "contents": contents,
            "quiz_data": lesson.quiz_data,
            "form_data": lesson.form_data,
            "created_at": lesson.created_at.isoformat() if lesson.created_at else None,
            "updated_at": lesson.updated_at.isoformat() if lesson.updated_at else None,
        }


@router.post("")
async def create_lesson(data: LessonCreate, _=Depends(get_current_user)):
    async with async_session_maker() as session:
        try:
            ct = ContentType(data.content_type)
        except ValueError:
            ct = ContentType.TEXT

        # Build initial contents array
        contents = []
        if data.text_content and data.content_type == "text":
            contents = [{"type": "text", "text": data.text_content}]
        elif data.file_id:
            item = {"type": data.content_type, "file_id": data.file_id}
            if data.text_content:
                item["caption"] = data.text_content
            contents = [item]

        lesson = Lesson(
            course_id=data.course_id,
            title=data.title,
            description=data.description,
            content_type=ct,
            is_active=data.is_active,
            order=data.order,
            delay_hours=data.delay_hours,
            view_deadline_hours=data.view_deadline_hours,
            cta_text=data.cta_text,
            cta_url=data.cta_url,
            text_content=data.text_content,
            file_id=data.file_id,
            contents=contents if contents else None,
        )
        session.add(lesson)
        await session.commit()
        await session.refresh(lesson)
        return {"id": lesson.id, "title": lesson.title}


@router.put("/{lesson_id}")
async def update_lesson(lesson_id: int, data: LessonUpdate, _=Depends(get_current_user)):
    async with async_session_maker() as session:
        lesson = await session.get(Lesson, lesson_id)
        if not lesson:
            raise HTTPException(status_code=404, detail="درس یافت نشد")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(lesson, field, value)
        await session.commit()
        return {"ok": True}


@router.delete("/{lesson_id}")
async def delete_lesson(lesson_id: int, _=Depends(get_current_user)):
    async with async_session_maker() as session:
        lesson = await session.get(Lesson, lesson_id)
        if not lesson:
            raise HTTPException(status_code=404, detail="درس یافت نشد")
        await session.delete(lesson)
        await session.commit()
        return {"ok": True}


# ── Content Management ───────────────────────────────────

@router.get("/{lesson_id}/contents")
async def get_contents(lesson_id: int, _=Depends(get_current_user)):
    async with async_session_maker() as session:
        lesson = await session.get(Lesson, lesson_id)
        if not lesson:
            raise HTTPException(status_code=404, detail="درس یافت نشد")
        return _get_lesson_contents(lesson)


@router.put("/{lesson_id}/contents")
async def update_all_contents(lesson_id: int, data: ContentReorder, _=Depends(get_current_user)):
    """Replace all contents (used for reorder or bulk update)."""
    async with async_session_maker() as session:
        lesson = await session.get(Lesson, lesson_id)
        if not lesson:
            raise HTTPException(status_code=404, detail="درس یافت نشد")

        new_contents = [item.model_dump(exclude_none=True) for item in data.contents]
        lesson.contents = copy.deepcopy(new_contents)
        flag_modified(lesson, "contents")
        _sync_primary_fields(lesson, new_contents)
        await session.commit()
        return {"ok": True, "count": len(new_contents)}


@router.post("/{lesson_id}/contents")
async def add_content(lesson_id: int, item: ContentItem, _=Depends(get_current_user)):
    """Add a new content block at the end."""
    async with async_session_maker() as session:
        lesson = await session.get(Lesson, lesson_id)
        if not lesson:
            raise HTTPException(status_code=404, detail="درس یافت نشد")

        contents = _get_lesson_contents(lesson)
        contents.append(item.model_dump(exclude_none=True))
        lesson.contents = copy.deepcopy(contents)
        flag_modified(lesson, "contents")
        _sync_primary_fields(lesson, contents)
        await session.commit()
        return {"ok": True, "index": len(contents) - 1}


@router.delete("/{lesson_id}/contents/{index}")
async def delete_content(lesson_id: int, index: int, _=Depends(get_current_user)):
    """Delete content block at given index."""
    async with async_session_maker() as session:
        lesson = await session.get(Lesson, lesson_id)
        if not lesson:
            raise HTTPException(status_code=404, detail="درس یافت نشد")

        contents = _get_lesson_contents(lesson)
        if index < 0 or index >= len(contents):
            raise HTTPException(status_code=400, detail="ایندکس نامعتبر")
        contents.pop(index)

        lesson.contents = copy.deepcopy(contents) if contents else None
        flag_modified(lesson, "contents")
        _sync_primary_fields(lesson, contents)
        await session.commit()
        return {"ok": True}


@router.put("/{lesson_id}/contents/{index}")
async def replace_content(lesson_id: int, index: int, item: ContentItem, _=Depends(get_current_user)):
    """Replace content block at given index."""
    async with async_session_maker() as session:
        lesson = await session.get(Lesson, lesson_id)
        if not lesson:
            raise HTTPException(status_code=404, detail="درس یافت نشد")

        contents = _get_lesson_contents(lesson)
        if index < 0 or index >= len(contents):
            raise HTTPException(status_code=400, detail="ایندکس نامعتبر")
        contents[index] = item.model_dump(exclude_none=True)

        lesson.contents = copy.deepcopy(contents)
        flag_modified(lesson, "contents")
        _sync_primary_fields(lesson, contents)
        await session.commit()
        return {"ok": True}


@router.post("/{lesson_id}/contents/reorder")
async def reorder_content(lesson_id: int, old_index: int, new_index: int, _=Depends(get_current_user)):
    """Move a content block from old_index to new_index."""
    async with async_session_maker() as session:
        lesson = await session.get(Lesson, lesson_id)
        if not lesson:
            raise HTTPException(status_code=404, detail="درس یافت نشد")

        contents = _get_lesson_contents(lesson)
        if old_index < 0 or old_index >= len(contents) or new_index < 0 or new_index >= len(contents):
            raise HTTPException(status_code=400, detail="ایندکس نامعتبر")

        item = contents.pop(old_index)
        contents.insert(new_index, item)

        lesson.contents = copy.deepcopy(contents)
        flag_modified(lesson, "contents")
        _sync_primary_fields(lesson, contents)
        await session.commit()
        return {"ok": True}


# ── Form Data Management ─────────────────────────────────

@router.put("/{lesson_id}/form")
async def save_form(lesson_id: int, data: FormData, _=Depends(get_current_user)):
    """Create or update form data for a lesson."""
    async with async_session_maker() as session:
        lesson = await session.get(Lesson, lesson_id)
        if not lesson:
            raise HTTPException(status_code=404, detail="درس یافت نشد")

        form_dict = {"fields": [f.model_dump(exclude_none=True) for f in data.fields]}
        lesson.form_data = form_dict
        flag_modified(lesson, "form_data")

        # Ensure form appears in contents
        contents = _get_lesson_contents(lesson)
        # Check if form block already exists
        has_form = any(c.get("type") == "form" for c in contents)
        if not has_form:
            contents.append({"type": "form", "form_data": form_dict})
        else:
            # Update existing form block
            for c in contents:
                if c.get("type") == "form":
                    c["form_data"] = form_dict
                    break

        lesson.contents = copy.deepcopy(contents)
        flag_modified(lesson, "contents")

        # Set content_type to FORM if it's the only/first content
        if contents and contents[0].get("type") == "form":
            lesson.content_type = ContentType.FORM

        await session.commit()
        return {"ok": True, "field_count": len(data.fields)}


@router.delete("/{lesson_id}/form")
async def delete_form(lesson_id: int, _=Depends(get_current_user)):
    """Delete form data from a lesson."""
    async with async_session_maker() as session:
        lesson = await session.get(Lesson, lesson_id)
        if not lesson:
            raise HTTPException(status_code=404, detail="درس یافت نشد")

        lesson.form_data = None
        flag_modified(lesson, "form_data")

        # Remove form block from contents
        contents = _get_lesson_contents(lesson)
        contents = [c for c in contents if c.get("type") != "form"]
        lesson.contents = copy.deepcopy(contents) if contents else None
        flag_modified(lesson, "contents")
        _sync_primary_fields(lesson, contents)

        await session.commit()
        return {"ok": True}
