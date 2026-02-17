"""
Settings API — Company info, webhook settings, bot texts, lead scoring rules
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete
from database import async_session_maker
from database.models import CompanyInfo, WebhookSetting, BotText, LeadScoringRule
from web.auth import get_current_user

router = APIRouter()


# ── Pydantic Schemas ─────────────────────────────────────

class CompanyInfoItem(BaseModel):
    key: str
    value: str

class WebhookSettingCreate(BaseModel):
    name: str
    url: str
    is_active: bool = True
    timeout: int = 10
    retry_count: int = 3
    events: Optional[list] = None
    headers: Optional[dict] = None

class WebhookSettingUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    is_active: Optional[bool] = None
    timeout: Optional[int] = None
    retry_count: Optional[int] = None
    events: Optional[list] = None
    headers: Optional[dict] = None

class BotTextUpdate(BaseModel):
    value: str

class ScoringRuleUpdate(BaseModel):
    points: Optional[int] = None
    is_active: Optional[bool] = None


# ── Company Info ─────────────────────────────────────────

COMPANY_KEY_LABELS = {
    'name': '🏢 نام شرکت',
    'phone': '📞 تلفن',
    'working_hours': '🕐 ساعت کاری',
    'address': '📍 آدرس',
    'website': '🌐 وبسایت',
    'extra_info': '📝 اطلاعات بیشتر',
    'sales_trigger_lesson': '🎯 تریگر فروش (شماره درس)',
}

@router.get("/company")
async def get_company_info(_=Depends(get_current_user)):
    """Get all company info settings"""
    async with async_session_maker() as session:
        result = await session.execute(select(CompanyInfo))
        rows = result.scalars().all()
        data = {r.key: r.value for r in rows}
        return {
            "settings": data,
            "labels": COMPANY_KEY_LABELS,
        }

@router.put("/company")
async def update_company_info(items: List[CompanyInfoItem], _=Depends(get_current_user)):
    """Update company info settings (upsert)"""
    async with async_session_maker() as session:
        for item in items:
            result = await session.execute(
                select(CompanyInfo).where(CompanyInfo.key == item.key)
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.value = item.value
            else:
                session.add(CompanyInfo(key=item.key, value=item.value))
        await session.commit()
        return {"status": "ok", "updated": len(items)}


# ── Webhook Settings ─────────────────────────────────────

@router.get("/webhooks")
async def get_webhooks(_=Depends(get_current_user)):
    """Get all webhook endpoints"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(WebhookSetting).order_by(WebhookSetting.id)
        )
        webhooks = result.scalars().all()
        return [
            {
                "id": w.id,
                "name": w.name,
                "url": w.url,
                "is_active": w.is_active,
                "timeout": w.timeout,
                "retry_count": w.retry_count,
                "events": w.events,
                "headers": w.headers,
                "created_at": w.created_at.isoformat() if w.created_at else None,
                "updated_at": w.updated_at.isoformat() if w.updated_at else None,
            }
            for w in webhooks
        ]

@router.post("/webhooks")
async def create_webhook(data: WebhookSettingCreate, _=Depends(get_current_user)):
    """Create a new webhook endpoint"""
    async with async_session_maker() as session:
        webhook = WebhookSetting(
            name=data.name,
            url=data.url,
            is_active=data.is_active,
            timeout=data.timeout,
            retry_count=data.retry_count,
            events=data.events,
            headers=data.headers,
        )
        session.add(webhook)
        await session.commit()
        await session.refresh(webhook)
        return {"id": webhook.id, "name": webhook.name}

@router.put("/webhooks/{webhook_id}")
async def update_webhook(webhook_id: int, data: WebhookSettingUpdate, _=Depends(get_current_user)):
    """Update a webhook endpoint"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(WebhookSetting).where(WebhookSetting.id == webhook_id)
        )
        webhook = result.scalar_one_or_none()
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(webhook, key, value)
        await session.commit()
        return {"status": "ok"}

@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: int, _=Depends(get_current_user)):
    """Delete a webhook endpoint"""
    async with async_session_maker() as session:
        await session.execute(
            delete(WebhookSetting).where(WebhookSetting.id == webhook_id)
        )
        await session.commit()
        return {"status": "ok"}


# ── Bot Texts ────────────────────────────────────────────

@router.get("/bot-texts")
async def get_bot_texts(_=Depends(get_current_user)):
    """Get all bot text overrides"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(BotText).order_by(BotText.category, BotText.key)
        )
        texts = result.scalars().all()
        return [
            {
                "id": t.id,
                "category": t.category,
                "key": t.key,
                "value": t.value,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
            for t in texts
        ]

@router.put("/bot-texts/{text_id}")
async def update_bot_text(text_id: int, data: BotTextUpdate, _=Depends(get_current_user)):
    """Update a bot text override"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(BotText).where(BotText.id == text_id)
        )
        text = result.scalar_one_or_none()
        if not text:
            raise HTTPException(status_code=404, detail="Text not found")
        text.value = data.value
        await session.commit()
        return {"status": "ok"}


# ── Lead Scoring Rules ───────────────────────────────────

@router.get("/scoring-rules")
async def get_scoring_rules(_=Depends(get_current_user)):
    """Get all lead scoring rules"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(LeadScoringRule).order_by(LeadScoringRule.event_type)
        )
        rules = result.scalars().all()
        return [
            {
                "id": r.id,
                "event_type": r.event_type,
                "label": r.label,
                "points": r.points,
                "is_active": r.is_active,
            }
            for r in rules
        ]

@router.put("/scoring-rules/{rule_id}")
async def update_scoring_rule(rule_id: int, data: ScoringRuleUpdate, _=Depends(get_current_user)):
    """Update a lead scoring rule"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(LeadScoringRule).where(LeadScoringRule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(rule, key, value)
        await session.commit()
        return {"status": "ok"}
