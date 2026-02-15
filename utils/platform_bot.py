"""
PlatformBot — a thin wrapper around aiogram.Bot that transparently
converts HTML formatting to Bale-compatible Markdown when PLATFORM == "bale".

Usage in bot.py:
    from utils.platform_bot import PlatformBot
    bot = PlatformBot(token=..., session=..., default=...)

All handler code (message.answer, callback.message.edit_text, etc.)
works unchanged — the conversion happens at the API call level.
"""
from typing import Optional, Union

from aiogram import Bot
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    ForceReply,
)

import config
from utils.platform import html_to_markdown

ReplyMarkup = Optional[
    Union[InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, ForceReply]
]


def _adapt(text: Optional[str]) -> Optional[str]:
    """Convert HTML → Markdown only when running on Bale."""
    if text is None or config.PLATFORM != "bale":
        return text
    return html_to_markdown(text)


class PlatformBot(Bot):
    """Bot subclass that auto-converts HTML to Markdown for Bale."""

    # ── Text messages ────────────────────────────────────────
    async def send_message(self, chat_id, text, **kwargs):
        return await super().send_message(chat_id, _adapt(text), **kwargs)

    # ── Media with captions ─────────────────────────────────
    async def send_photo(self, chat_id, photo, caption=None, **kwargs):
        return await super().send_photo(chat_id, photo, caption=_adapt(caption), **kwargs)

    async def send_video(self, chat_id, video, caption=None, **kwargs):
        return await super().send_video(chat_id, video, caption=_adapt(caption), **kwargs)

    async def send_audio(self, chat_id, audio, caption=None, **kwargs):
        return await super().send_audio(chat_id, audio, caption=_adapt(caption), **kwargs)

    async def send_voice(self, chat_id, voice, caption=None, **kwargs):
        return await super().send_voice(chat_id, voice, caption=_adapt(caption), **kwargs)

    async def send_document(self, chat_id, document, caption=None, **kwargs):
        return await super().send_document(chat_id, document, caption=_adapt(caption), **kwargs)

    async def send_animation(self, chat_id, animation, caption=None, **kwargs):
        return await super().send_animation(chat_id, animation, caption=_adapt(caption), **kwargs)

    # ── Edits ────────────────────────────────────────────────
    async def edit_message_text(self, text, **kwargs):
        return await super().edit_message_text(_adapt(text), **kwargs)

    async def edit_message_caption(self, caption=None, **kwargs):
        return await super().edit_message_caption(caption=_adapt(caption), **kwargs)
