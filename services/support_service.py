"""
Support service — company info + sales owner management
"""
import logging
from typing import Optional, List, Dict
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import CompanyInfo, SalesOwner, User
import config

logger = logging.getLogger(__name__)

# Keys used in company_info table
COMPANY_KEYS = ['name', 'phone', 'working_hours', 'address', 'website', 'extra_info']

COMPANY_KEY_LABELS = {
    'name': '🏢 نام شرکت',
    'phone': '📞 تلفن',
    'working_hours': '🕐 ساعت کاری',
    'address': '📍 آدرس',
    'website': '🌐 وبسایت',
    'extra_info': '📝 اطلاعات بیشتر',
}


class SupportService:
    """Service for company info and sales owner operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Company Info ────────────────────────────────────────
    async def get_company_info(self) -> Dict[str, str]:
        """Get all company info as a dict"""
        result = await self.session.execute(select(CompanyInfo))
        rows = result.scalars().all()
        return {row.key: row.value for row in rows}

    async def set_company_info(self, key: str, value: str) -> None:
        """Set a company info value (upsert)"""
        result = await self.session.execute(
            select(CompanyInfo).where(CompanyInfo.key == key)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.value = value
            existing.updated_at = datetime.utcnow()
        else:
            self.session.add(CompanyInfo(key=key, value=value))
        await self.session.commit()

    # ── Sales Owners ────────────────────────────────────────
    async def get_all_owners(self) -> List[SalesOwner]:
        """Get all sales owners"""
        result = await self.session.execute(
            select(SalesOwner).order_by(SalesOwner.name)
        )
        return list(result.scalars().all())

    async def get_active_owners(self) -> List[SalesOwner]:
        """Get active sales owners"""
        result = await self.session.execute(
            select(SalesOwner).where(SalesOwner.is_active == True).order_by(SalesOwner.name)
        )
        return list(result.scalars().all())

    async def get_owner_by_id(self, owner_id: int) -> Optional[SalesOwner]:
        """Get owner by ID"""
        result = await self.session.execute(
            select(SalesOwner).where(SalesOwner.id == owner_id)
        )
        return result.scalar_one_or_none()

    async def get_owner_by_didar_id(self, didar_id: str) -> Optional[SalesOwner]:
        """Get owner by Didar CRM owner ID"""
        result = await self.session.execute(
            select(SalesOwner).where(SalesOwner.didar_owner_id == didar_id)
        )
        return result.scalar_one_or_none()

    async def create_owner(
        self,
        name: str,
        didar_owner_id: Optional[str] = None,
        phone: Optional[str] = None,
        internal_number: Optional[str] = None,
        telegram_username: Optional[str] = None,
        bale_username: Optional[str] = None,
        weight: int = 1,
    ) -> SalesOwner:
        """Create a new sales owner"""
        owner = SalesOwner(
            name=name,
            didar_owner_id=didar_owner_id,
            phone=phone,
            internal_number=internal_number,
            telegram_username=telegram_username,
            bale_username=bale_username,
            weight=weight,
        )
        self.session.add(owner)
        await self.session.commit()
        await self.session.refresh(owner)
        return owner

    async def update_owner(self, owner_id: int, **kwargs) -> Optional[SalesOwner]:
        """Update a sales owner"""
        owner = await self.get_owner_by_id(owner_id)
        if not owner:
            return None
        for key, val in kwargs.items():
            if hasattr(owner, key):
                setattr(owner, key, val)
        owner.updated_at = datetime.utcnow()
        await self.session.commit()
        return owner

    async def toggle_owner(self, owner_id: int) -> Optional[SalesOwner]:
        """Toggle owner active status"""
        owner = await self.get_owner_by_id(owner_id)
        if not owner:
            return None
        owner.is_active = not owner.is_active
        owner.updated_at = datetime.utcnow()
        await self.session.commit()
        return owner

    async def delete_owner(self, owner_id: int) -> bool:
        """Delete a sales owner"""
        owner = await self.get_owner_by_id(owner_id)
        if not owner:
            return False
        await self.session.delete(owner)
        await self.session.commit()
        return True

    # ── Assignment ──────────────────────────────────────────
    async def assign_owner_to_user(
        self,
        user: User,
        didar_owner_id: Optional[str] = None,
        owner_name: Optional[str] = None,
    ) -> Optional[SalesOwner]:
        """
        Assign an owner to a user based on webhook response.
        Matches by didar_owner_id first, falls back to name.
        """
        owner = None
        if didar_owner_id:
            owner = await self.get_owner_by_didar_id(didar_owner_id)
        if not owner and owner_name:
            # Try to match by name
            result = await self.session.execute(
                select(SalesOwner).where(SalesOwner.name == owner_name)
            )
            owner = result.scalar_one_or_none()

        if owner:
            user.assigned_owner_id = owner.id
            user.assigned_owner_name = owner.name
            user.assigned_at = datetime.utcnow()
            owner.total_assignments += 1
            owner.last_assignment_at = datetime.utcnow()
            await self.session.commit()
            logger.info(
                f"[SupportService] Assigned owner {owner.name} to user {user.telegram_user_id}"
            )
        elif owner_name:
            # Owner not in our DB yet — just store the name
            user.assigned_owner_name = owner_name
            user.assigned_at = datetime.utcnow()
            await self.session.commit()
            logger.info(
                f"[SupportService] Stored owner name '{owner_name}' for user {user.telegram_user_id} (owner not in DB)"
            )

        return owner

    # ── Support Display ─────────────────────────────────────
    def build_support_text(
        self,
        company_info: Dict[str, str],
        user: Optional[User] = None,
    ) -> str:
        """Build the support message text for a user"""
        parts = ["📞 <b>پشتیبانی</b>\n"]

        name = company_info.get('name', '')
        if name:
            parts.append(f"🏢 {name}")

        phone = company_info.get('phone', '')
        if phone:
            parts.append(f"📞 تلفن: {phone}")

        hours = company_info.get('working_hours', '')
        if hours:
            parts.append(f"🕐 ساعت کاری: {hours}")

        address = company_info.get('address', '')
        if address:
            parts.append(f"📍 آدرس: {address}")

        website = company_info.get('website', '')
        if website:
            parts.append(f"🌐 وبسایت: {website}")

        extra = company_info.get('extra_info', '')
        if extra:
            parts.append(f"\n{extra}")

        # Show assigned owner info if available
        if user and user.assigned_owner_name:
            parts.append(f"\n👤 <b>کارشناس اختصاصی شما:</b> {user.assigned_owner_name}")

            # Build platform-aware direct chat link
            owner = None
            if user.assigned_owner_id:
                # We have a linked SalesOwner — pull username
                # (caller should eagerly load or pass owner object)
                pass  # will be handled via inline button

        parts.append("\n📩 برای ارتباط مستقیم از دکمه زیر استفاده کنید.")

        return "\n".join(parts)

    def get_owner_chat_link(self, owner: Optional[SalesOwner], platform: str = None) -> Optional[str]:
        """Get direct chat link to the assigned owner for the current platform"""
        if not owner:
            return None
        platform = platform or config.PLATFORM
        if platform == "bale":
            username = owner.bale_username
            if username:
                username = username.lstrip('@')
                return f"https://ble.ir/{username}"
        else:
            username = owner.telegram_username
            if username:
                username = username.lstrip('@')
                return f"https://t.me/{username}"
        return None
