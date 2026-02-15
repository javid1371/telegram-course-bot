"""
Platform utilities — HTML-to-Markdown conversion and helpers for
running the same codebase on Telegram *and* Bale.

Bale only supports Markdown formatting (bold **…**, italic _…_, links [t](url)),
while our messages database stores HTML (<b>, <i>, <a>, <code>).
This module transparently converts when PLATFORM == "bale".
"""
import re
import html as _html
from typing import Optional

import config

# ──────────────────── HTML → Markdown conversions ────────────────────


def html_to_markdown(text: str) -> str:
    """
    Convert common HTML tags used in Telegram to Bale-compatible
    Markdown.  Handles:
        <b>…</b>  →  *…*      (bold — Bale uses * with space around)
        <i>…</i>  →  _…_      (italic)
        <code>…</code>  →  `…`
        <pre>…</pre>   →  ```…```
        <a href="url">text</a>  →  [text](url)
        <br>, <br/>  →  \\n
    All remaining tags are stripped.
    """
    if not text:
        return text

    # <br> → newline
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)

    # <a href="url">text</a> → [text](url)
    text = re.sub(
        r'<a\s+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        r"[\2](\1)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # <b> / <strong> → *…*
    text = re.sub(
        r"<(?:b|strong)>(.*?)</(?:b|strong)>",
        r" *\1* ",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # <i> / <em> → _…_
    text = re.sub(
        r"<(?:i|em)>(.*?)</(?:i|em)>",
        r" _\1_ ",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # <pre> → ```…```
    text = re.sub(
        r"<pre>(.*?)</pre>",
        r"```\1```",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # <code> → `…`
    text = re.sub(
        r"<code>(.*?)</code>",
        r"`\1`",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Unescape HTML entities (&amp; → &, etc.)
    text = _html.unescape(text)

    # Clean up multi-spaces introduced by bold/italic wrappers
    text = re.sub(r"  +", " ", text)

    return text.strip()


def adapt_text(text: Optional[str]) -> Optional[str]:
    """
    Return *text* unchanged on Telegram, or convert to Markdown on Bale.
    Safe to call with ``None``.
    """
    if text is None:
        return None
    if config.PLATFORM == "bale":
        return html_to_markdown(text)
    return text


def platform_label() -> str:
    """Human-readable platform name (for logs / messages)."""
    return "بله" if config.PLATFORM == "bale" else "تلگرام"


def is_bale() -> bool:
    return config.PLATFORM == "bale"


def is_telegram() -> bool:
    return config.PLATFORM == "telegram"
