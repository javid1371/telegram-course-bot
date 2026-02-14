"""
📝 Text Manager - Runtime text override system
Provides SmartDict that checks DB overrides before falling back to defaults.
Admin can edit texts from Telegram UI, changes apply instantly.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# In-memory override cache: {"CATEGORY.key": "value"}
_overrides: dict = {}


class SmartDict(dict):
    """
    A dict subclass that checks DB overrides before returning defaults.
    Supports format() on returned strings seamlessly.
    Nested dict values are NOT overridable (returned as-is from defaults).
    """

    def __init__(self, category: str, defaults: dict):
        super().__init__(defaults)
        self._category = category

    def __getitem__(self, key):
        full_key = f"{self._category}.{key}"
        if full_key in _overrides:
            return _overrides[full_key]
        return super().__getitem__(key)

    def get(self, key, default=None):
        full_key = f"{self._category}.{key}"
        if full_key in _overrides:
            return _overrides[full_key]
        return super().get(key, default)

    def get_default(self, key):
        """Get the original default value (ignoring overrides)"""
        return super().__getitem__(key)

    def is_overridden(self, key) -> bool:
        """Check if a key has a DB override"""
        return f"{self._category}.{key}" in _overrides

    def get_editable_keys(self) -> list:
        """Get list of keys that have string values (editable via admin)"""
        return [k for k, v in super().items() if isinstance(v, str)]


async def load_overrides():
    """Load all text overrides from database into memory cache"""
    global _overrides
    try:
        from database import async_session_maker
        from database.models import BotText
        from sqlalchemy import select

        async with async_session_maker() as session:
            result = await session.execute(select(BotText))
            texts = result.scalars().all()
            _overrides = {f"{t.category}.{t.key}": t.value for t in texts}
            logger.info(f"Loaded {len(_overrides)} text overrides from database")
    except Exception as e:
        logger.warning(f"Could not load text overrides: {e}")
        _overrides = {}


async def set_override(category: str, key: str, value: str):
    """Set a text override in DB and update cache immediately"""
    global _overrides
    from database import async_session_maker
    from database.models import BotText
    from sqlalchemy import select

    full_key = f"{category}.{key}"

    async with async_session_maker() as session:
        result = await session.execute(
            select(BotText).where(BotText.category == category, BotText.key == key)
        )
        text = result.scalar_one_or_none()
        if text:
            text.value = value
        else:
            text = BotText(category=category, key=key, value=value)
            session.add(text)
        await session.commit()

    _overrides[full_key] = value
    logger.info(f"Text override set: {full_key}")


async def delete_override(category: str, key: str):
    """Delete an override and revert to default"""
    global _overrides
    from database import async_session_maker
    from database.models import BotText
    from sqlalchemy import select, delete

    full_key = f"{category}.{key}"

    async with async_session_maker() as session:
        await session.execute(
            delete(BotText).where(BotText.category == category, BotText.key == key)
        )
        await session.commit()

    _overrides.pop(full_key, None)
    logger.info(f"Text override deleted: {full_key}")


def get_overrides_count() -> int:
    """Get number of active overrides"""
    return len(_overrides)


# Category display names for admin UI
CATEGORY_LABELS = {
    "GENERAL": "🔧 عمومی / خطاها",
    "USER_BUTTONS": "🔘 دکمه‌های کاربر",
    "ADMIN_BUTTONS": "🔘 دکمه‌های ادمین",
    "REGISTRATION": "📝 ثبت‌نام",
    "USER": "👤 پیام‌های کاربر",
    "ADMIN": "🔧 پیام‌های ادمین",
    "DELAY": "⏱ فاصله زمانی",
    "CONTENT_TYPES": "📦 انواع محتوا",
    "REMINDERS": "🔔 یادآوری",
    "EXPORT": "📥 اکسپورت",
}
