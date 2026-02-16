"""
Registration Fields CRUD API Routes
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from database import async_session_maker
from database.models import RegistrationField, FieldType
from web.auth import get_current_user

router = APIRouter()


class FieldCreate(BaseModel):
    field_name: str
    field_label: str
    field_type: str = "text"  # text, number, email, phone, date, select
    is_required: bool = True
    order: int = 0
    validation_rule: Optional[str] = None
    options: Optional[dict] = None  # for select type: {"choices": ["opt1", "opt2"]}
    is_active: bool = True


class FieldUpdate(BaseModel):
    field_name: Optional[str] = None
    field_label: Optional[str] = None
    field_type: Optional[str] = None
    is_required: Optional[bool] = None
    order: Optional[int] = None
    validation_rule: Optional[str] = None
    options: Optional[dict] = None
    is_active: Optional[bool] = None


class ReorderItem(BaseModel):
    id: int
    order: int


class ReorderRequest(BaseModel):
    items: List[ReorderItem]


def field_to_dict(f: RegistrationField) -> dict:
    return {
        "id": f.id,
        "field_name": f.field_name,
        "field_label": f.field_label,
        "field_type": f.field_type.value if f.field_type else "text",
        "is_required": f.is_required,
        "order": f.order,
        "validation_rule": f.validation_rule,
        "options": f.options,
        "is_active": f.is_active,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


@router.get("")
async def list_fields(_=Depends(get_current_user)):
    async with async_session_maker() as session:
        result = await session.execute(
            select(RegistrationField).order_by(RegistrationField.order, RegistrationField.id)
        )
        fields = result.scalars().all()
        return [field_to_dict(f) for f in fields]


@router.put("/reorder")
async def reorder_fields(data: ReorderRequest, _=Depends(get_current_user)):
    async with async_session_maker() as session:
        for item in data.items:
            field = await session.get(RegistrationField, item.id)
            if field:
                field.order = item.order
        await session.commit()
        return {"ok": True}


@router.get("/{field_id}")
async def get_field(field_id: int, _=Depends(get_current_user)):
    async with async_session_maker() as session:
        field = await session.get(RegistrationField, field_id)
        if not field:
            raise HTTPException(status_code=404, detail="فیلد یافت نشد")
        return field_to_dict(field)


@router.post("")
async def create_field(data: FieldCreate, _=Depends(get_current_user)):
    async with async_session_maker() as session:
        # Validate field_type
        try:
            ft = FieldType(data.field_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"نوع فیلد نامعتبر: {data.field_type}")

        field = RegistrationField(
            field_name=data.field_name,
            field_label=data.field_label,
            field_type=ft,
            is_required=data.is_required,
            order=data.order,
            validation_rule=data.validation_rule,
            options=data.options,
            is_active=data.is_active,
        )
        session.add(field)
        await session.commit()
        await session.refresh(field)
        return field_to_dict(field)


@router.put("/{field_id}")
async def update_field(field_id: int, data: FieldUpdate, _=Depends(get_current_user)):
    async with async_session_maker() as session:
        field = await session.get(RegistrationField, field_id)
        if not field:
            raise HTTPException(status_code=404, detail="فیلد یافت نشد")

        updates = data.model_dump(exclude_unset=True)

        # Handle field_type enum conversion
        if "field_type" in updates:
            try:
                updates["field_type"] = FieldType(updates["field_type"])
            except ValueError:
                raise HTTPException(status_code=400, detail=f"نوع فیلد نامعتبر: {updates['field_type']}")

        for key, value in updates.items():
            setattr(field, key, value)

        await session.commit()
        return {"ok": True}


@router.delete("/{field_id}")
async def delete_field(field_id: int, _=Depends(get_current_user)):
    async with async_session_maker() as session:
        field = await session.get(RegistrationField, field_id)
        if not field:
            raise HTTPException(status_code=404, detail="فیلد یافت نشد")
        await session.delete(field)
        await session.commit()
        return {"ok": True}
