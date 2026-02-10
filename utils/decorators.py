"""
Decorators for bot handlers
"""
from functools import wraps
from typing import Callable, Any
from aiogram.types import Message, CallbackQuery
import config


def admin_only(func: Callable) -> Callable:
    """Decorator to restrict access to admin users only"""
    @wraps(func)
    async def wrapper(event: Message | CallbackQuery, *args, **kwargs) -> Any:
        # Get user_id from event
        if isinstance(event, Message):
            user_id = event.from_user.id
            reply_method = event.answer
        else:  # CallbackQuery
            user_id = event.from_user.id
            reply_method = event.message.answer

        # Check if user is admin
        if user_id not in config.ADMIN_USER_IDS:
            await reply_method(config.MESSAGES["unauthorized"])
            return

        # Execute the handler
        return await func(event, *args, **kwargs)

    return wrapper


def registered_only(func: Callable) -> Callable:
    """Decorator to restrict access to registered users only"""
    @wraps(func)
    async def wrapper(message: Message, *args, **kwargs) -> Any:
        from database import async_session_maker
        from database.models import User
        from sqlalchemy import select

        user_id = message.from_user.id

        # Check if user is registered
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.telegram_user_id == user_id)
            )
            user = result.scalar_one_or_none()

        if not user:
            await message.answer(
                "⚠️ لطفاً ابتدا ثبت‌نام کنید.\n\n"
                "برای ثبت‌نام دستور /start را ارسال کنید."
            )
            return

        # Execute the handler
        return await func(message, *args, **kwargs)

    return wrapper


def rate_limit(limit_seconds: int = 1):
    """Simple rate limiting decorator"""
    from datetime import datetime, timedelta

    last_call = {}

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(event: Message | CallbackQuery, *args, **kwargs) -> Any:
            # Get user_id
            if isinstance(event, Message):
                user_id = event.from_user.id
            else:
                user_id = event.from_user.id

            # Check last call time
            now = datetime.now()
            if user_id in last_call:
                time_diff = (now - last_call[user_id]).total_seconds()
                if time_diff < limit_seconds:
                    # Rate limited
                    if isinstance(event, CallbackQuery):
                        await event.answer("⏳ لطفاً کمی صبر کنید...", show_alert=False)
                    return

            # Update last call time
            last_call[user_id] = now

            # Execute the handler
            return await func(event, *args, **kwargs)

        return wrapper
    return decorator


def log_errors(func: Callable) -> Callable:
    """Decorator to log errors"""
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)

            # Try to send error message to user
            event = args[0] if args else None
            if isinstance(event, Message):
                try:
                    await event.answer(config.MESSAGES["error"])
                except:
                    pass
            elif isinstance(event, CallbackQuery):
                try:
                    await event.message.answer(config.MESSAGES["error"])
                    await event.answer()
                except:
                    pass

            raise

    return wrapper
