"""
Utility functions and helpers
"""
import re
from typing import Optional
from datetime import datetime, timedelta


def validate_email(email: str) -> bool:
    """Validate email address"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """Validate Iranian phone number"""
    # Remove spaces and dashes
    phone = phone.replace(" ", "").replace("-", "")

    # Check Iranian mobile format
    pattern = r'^(\+98|0)?9\d{9}$'
    return bool(re.match(pattern, phone))


def normalize_phone(phone: str) -> str:
    """Normalize phone number to standard format"""
    phone = phone.replace(" ", "").replace("-", "")
    if phone.startswith("+98"):
        phone = "0" + phone[3:]
    elif phone.startswith("98"):
        phone = "0" + phone[2:]
    return phone


def calculate_progress(completed: int, total: int) -> float:
    """Calculate progress percentage"""
    if total == 0:
        return 0.0
    return round((completed / total) * 100, 2)


def format_duration(seconds: int) -> str:
    """Format duration in human readable format"""
    if seconds < 60:
        return f"{seconds} ثانیه"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} دقیقه"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes > 0:
            return f"{hours} ساعت و {minutes} دقیقه"
        return f"{hours} ساعت"


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to max length"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


def generate_referral_code(user_id: int) -> str:
    """Generate unique referral code"""
    import hashlib
    hash_input = f"{user_id}{datetime.now().timestamp()}"
    return hashlib.md5(hash_input.encode()).hexdigest()[:8].upper()


def parse_tracking_link(start_param: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Parse start parameter to extract campaign and referral info
    Format: camp_CAMPAIGN_CODE or ref_REFERRAL_CODE
    """
    if not start_param:
        return None, None

    if start_param.startswith("camp_"):
        return start_param[5:], None
    elif start_param.startswith("ref_"):
        return None, start_param[4:]

    return None, None


def escape_markdown(text: str) -> str:
    """Escape markdown special characters"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def format_datetime(dt: datetime, include_time: bool = True) -> str:
    """Format datetime in Persian format"""
    from datetime import datetime

    # Convert to Jalali if needed (optional - for Persian calendar)
    # For now, using Gregorian

    if include_time:
        return dt.strftime("%Y/%m/%d - %H:%M")
    return dt.strftime("%Y/%m/%d")


def chunk_list(lst: list, chunk_size: int) -> list:
    """Split list into chunks"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def is_within_rate_limit(last_action: Optional[datetime], limit_seconds: int = 60) -> bool:
    """Check if action is within rate limit"""
    if not last_action:
        return True

    time_diff = (datetime.now() - last_action).total_seconds()
    return time_diff < limit_seconds


def format_number(number: int) -> str:
    """Format number with thousand separators"""
    return f"{number:,}".replace(",", "٬")


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    # Remove or replace unsafe characters
    unsafe_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    return filename


def get_week_range() -> tuple[datetime, datetime]:
    """Get start and end of current week"""
    today = datetime.now()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start.replace(hour=0, minute=0, second=0), end.replace(hour=23, minute=59, second=59)


def get_month_range() -> tuple[datetime, datetime]:
    """Get start and end of current month"""
    today = datetime.now()
    start = today.replace(day=1, hour=0, minute=0, second=0)

    # Get last day of month
    if today.month == 12:
        end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

    end = end.replace(hour=23, minute=59, second=59)
    return start, end
