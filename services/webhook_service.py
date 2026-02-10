"""
Webhook service - handles outgoing webhook calls
"""
import logging
import json
from typing import Optional
from datetime import datetime
import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import WebhookSetting, User

logger = logging.getLogger(__name__)


class WebhookService:
    """Service for sending webhook notifications"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_webhooks(self):
        """Get all active webhooks"""
        result = await self.session.execute(
            select(WebhookSetting).where(WebhookSetting.is_active == True)
        )
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
        """Create a new webhook setting"""
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

    def _build_payload(self, template: dict, user: User, extra_data: dict = None) -> dict:
        """Build webhook payload from template and user data"""
        payload = {}
        data = extra_data or {}

        for key, value in template.items():
            if isinstance(value, str):
                # Replace variables
                value = value.replace("{user_id}", str(user.telegram_user_id))
                value = value.replace("{username}", user.username or "")
                value = value.replace("{first_name}", user.first_name or "")
                value = value.replace("{last_name}", user.last_name or "")
                value = value.replace("{referral_code}", user.referral_code or "")

                # Replace registration data variables
                if user.registration_data:
                    for field, fval in user.registration_data.items():
                        value = value.replace(f"{{{field}}}", str(fval))

                # Replace extra data variables
                for dkey, dval in data.items():
                    value = value.replace(f"{{{dkey}}}", str(dval))

            payload[key] = value
        return payload

    async def send_webhook(
        self,
        webhook_name: str,
        user: User,
        extra_data: dict = None,
    ) -> bool:
        """Send webhook notification"""
        webhook = await self.get_webhook_by_name(webhook_name)
        if not webhook or not webhook.is_active:
            return False

        payload = {}
        if webhook.payload_template:
            payload = self._build_payload(webhook.payload_template, user, extra_data)
        else:
            # Default payload
            payload = {
                "event": webhook_name,
                "user_id": user.telegram_user_id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "registration_data": user.registration_data,
                "timestamp": datetime.utcnow().isoformat(),
            }
            if extra_data:
                payload.update(extra_data)

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
                                logger.info(f"Webhook '{webhook_name}' sent successfully (status: {response.status})")
                                return True
                            else:
                                logger.warning(
                                    f"Webhook '{webhook_name}' returned {response.status} "
                                    f"(attempt {attempt + 1}/{webhook.retry_count})"
                                )
                    elif webhook.method.upper() == "GET":
                        async with http_session.get(
                            webhook.url,
                            params=payload,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=webhook.timeout),
                        ) as response:
                            if response.status < 400:
                                logger.info(f"Webhook '{webhook_name}' sent successfully")
                                return True

            except Exception as e:
                logger.error(
                    f"Webhook '{webhook_name}' error (attempt {attempt + 1}/{webhook.retry_count}): {e}"
                )

        logger.error(f"Webhook '{webhook_name}' failed after {webhook.retry_count} attempts")
        return False

    async def send_all_active_webhooks(self, event: str, user: User, extra_data: dict = None):
        """Send event to all active webhooks"""
        webhooks = await self.get_active_webhooks()
        for webhook in webhooks:
            await self.send_webhook(webhook.name, user, extra_data={"event": event, **(extra_data or {})})

    async def test_webhook(self, webhook_id: int) -> tuple[bool, str]:
        """Test a webhook with sample data"""
        webhook = await self.get_webhook_by_id(webhook_id)
        if not webhook:
            return False, "Webhook not found"

        test_payload = {
            "event": "test",
            "message": "This is a test webhook from Telegram Course Bot",
            "timestamp": datetime.utcnow().isoformat(),
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
                        params=test_payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=webhook.timeout),
                    ) as response:
                        return response.status < 400, f"Status: {response.status}"

        except Exception as e:
            return False, str(e)
