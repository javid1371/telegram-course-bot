"""
Webhook service - handles outgoing webhook calls
Unified event system: all events go to all active webhook endpoints
Standard payload format optimized for n8n / CRM integration
"""
import logging
from typing import Optional
from datetime import datetime
import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import WebhookSetting, User
import config

logger = logging.getLogger(__name__)

# Bot identifier for multi-bot setups
BOT_USERNAME = getattr(config, "BOT_USERNAME", "course_bot")


class WebhookService:
    """Service for sending webhook notifications to all active endpoints"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ===========================
    # CRUD
    # ===========================

    async def get_active_webhooks(self):
        """Get all active webhooks"""
        result = await self.session.execute(
            select(WebhookSetting).where(WebhookSetting.is_active == True)
        )
        return list(result.scalars().all())

    async def get_all_webhooks(self):
        """Get all webhooks (active and inactive)"""
        result = await self.session.execute(select(WebhookSetting))
        return list(result.scalars().all())

    async def get_webhook_by_name(self, name: str) -> Optional[WebhookSetting]:
        """Get webhook by name"""
        result = await self.session.execute(
            select(WebhookSetting).where(WebhookSetting.name == name)
        )
        return result.scalar_one_or_none()

    async def get_webhook_by_id(self, webhook_id: int) -> Optional[WebhookSetting]:
        """Get webhook by ID"""
        result = await self.session.execute(
            select(WebhookSetting).where(WebhookSetting.id == webhook_id)
        )
        return result.scalar_one_or_none()

    async def create_webhook(
        self,
        name: str,
        url: str,
        method: str = "POST",
        payload_template: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> WebhookSetting:
        """Create a new webhook endpoint"""
        webhook = WebhookSetting(
            name=name,
            url=url,
            method=method,
            payload_template=payload_template,
            headers=headers,
        )
        self.session.add(webhook)
        await self.session.commit()
        await self.session.refresh(webhook)
        return webhook

    async def delete_webhook(self, webhook_id: int) -> bool:
        """Delete a webhook"""
        webhook = await self.get_webhook_by_id(webhook_id)
        if webhook:
            await self.session.delete(webhook)
            await self.session.commit()
            return True
        return False

    async def toggle_webhook(self, webhook_id: int) -> Optional[WebhookSetting]:
        """Toggle webhook active status"""
        webhook = await self.get_webhook_by_id(webhook_id)
        if webhook:
            webhook.is_active = not webhook.is_active
            await self.session.commit()
            await self.session.refresh(webhook)
            return webhook
        return None

    # ===========================
    # PAYLOAD BUILDING
    # ===========================

    def _build_user_payload(self, user: User) -> dict:
        """Build standardized user object for webhook payload"""
        return {
            "telegram_id": user.telegram_user_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "registration_data": user.registration_data or {},
            "tags": user.tags or [],
            "referral_code": user.referral_code,
            "is_completed": user.is_completed,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }

    def _build_event_payload(self, event: str, user: User, extra_data: dict = None) -> dict:
        """
        Build standardized webhook payload.
        
        Structure:
        {
            "event": "user_registered",
            "bot": "jmgdmdorebot",
            "timestamp": "2026-02-10T13:00:00Z",
            "user": { ... full user object ... },
            "data": { ... event-specific data ... }
        }
        """
        return {
            "event": event,
            "bot": BOT_USERNAME,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user": self._build_user_payload(user),
            "data": extra_data or {},
        }

    # ===========================
    # SENDING
    # ===========================

    async def send_webhook(
        self,
        event: str,
        user: User,
        extra_data: dict = None,
    ) -> bool:
        """
        Send event to ALL active webhook endpoints.
        
        Events:
        - user_registered: New user signed up
        - lesson_sent: Lesson delivered to user
        - lesson_completed: User confirmed a lesson
        - quiz_passed: User passed a quiz
        - quiz_failed: User failed a quiz
        - form_submitted: User filled a form lesson
        - course_completed: User finished all lessons
        """
        webhooks = await self.get_active_webhooks()
        if not webhooks:
            return False

        payload = self._build_event_payload(event, user, extra_data)
        any_success = False

        for webhook in webhooks:
            success = await self._send_to_endpoint(webhook, payload, event)
            if success:
                any_success = True

        return any_success

    async def _send_to_endpoint(self, webhook: WebhookSetting, payload: dict, event: str) -> bool:
        """Send payload to a single webhook endpoint with retry"""
        headers = webhook.headers or {"Content-Type": "application/json"}

        for attempt in range(webhook.retry_count):
            try:
                async with aiohttp.ClientSession() as http_session:
                    if webhook.method.upper() == "POST":
                        async with http_session.post(
                            webhook.url,
                            json=payload,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=webhook.timeout),
                        ) as response:
                            if response.status < 400:
                                logger.info(
                                    f"Webhook [{webhook.name}] event '{event}' sent "
                                    f"(status: {response.status})"
                                )
                                return True
                            else:
                                logger.warning(
                                    f"Webhook [{webhook.name}] event '{event}' returned {response.status} "
                                    f"(attempt {attempt + 1}/{webhook.retry_count})"
                                )
                    elif webhook.method.upper() == "GET":
                        async with http_session.get(
                            webhook.url,
                            params={"payload": str(payload)},
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=webhook.timeout),
                        ) as response:
                            if response.status < 400:
                                logger.info(f"Webhook [{webhook.name}] event '{event}' sent")
                                return True

            except Exception as e:
                logger.error(
                    f"Webhook [{webhook.name}] event '{event}' error "
                    f"(attempt {attempt + 1}/{webhook.retry_count}): {e}"
                )

        logger.error(f"Webhook [{webhook.name}] event '{event}' failed after {webhook.retry_count} attempts")
        return False

    async def test_webhook(self, webhook_id: int) -> tuple[bool, str]:
        """Test a single webhook endpoint with sample data"""
        webhook = await self.get_webhook_by_id(webhook_id)
        if not webhook:
            return False, "Webhook not found"

        test_payload = {
            "event": "test",
            "bot": BOT_USERNAME,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user": {
                "telegram_id": 0,
                "username": "test_user",
                "first_name": "Test",
                "last_name": "User",
                "registration_data": {"name": "Test User"},
                "tags": ["test"],
                "referral_code": None,
                "is_completed": False,
                "is_active": True,
                "created_at": datetime.utcnow().isoformat(),
            },
            "data": {
                "message": "This is a test webhook from Telegram Course Bot",
            },
        }

        headers = webhook.headers or {"Content-Type": "application/json"}

        try:
            async with aiohttp.ClientSession() as http_session:
                if webhook.method.upper() == "POST":
                    async with http_session.post(
                        webhook.url,
                        json=test_payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=webhook.timeout),
                    ) as response:
                        return response.status < 400, f"Status: {response.status}"
                else:
                    async with http_session.get(
                        webhook.url,
                        params={"payload": str(test_payload)},
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=webhook.timeout),
                    ) as response:
                        return response.status < 400, f"Status: {response.status}"

        except Exception as e:
            return False, str(e)
