"""
Input validation utilities
"""
import re
from typing import Any, Optional
from datetime import datetime


class ValidationError(Exception):
    """Custom validation error"""
    pass


def validate_text(value: str, min_length: int = 1, max_length: int = 500) -> str:
    """Validate text input"""
    if not value or not value.strip():
        raise ValidationError("متن نمی‌تواند خالی باشد")
    
    value = value.strip()
    
    if len(value) < min_length:
        raise ValidationError(f"متن باید حداقل {min_length} کاراکتر داشته باشد")
    
    if len(value) > max_length:
        raise ValidationError(f"متن نباید بیشتر از {max_length} کاراکتر داشته باشد")
    
    return value


def validate_number(value: str, min_value: Optional[float] = None, max_value: Optional[float] = None) -> float:
    """Validate number input"""
    try:
        # Replace Persian digits
        value = value.replace('۰', '0').replace('۱', '1').replace('۲', '2')
        value = value.replace('۳', '3').replace('۴', '4').replace('۵', '5')
        value = value.replace('۶', '6').replace('۷', '7').replace('۸', '8')
        value = value.replace('۹', '9')
        
        number = float(value)
        
        if min_value is not None and number < min_value:
            raise ValidationError(f"عدد باید حداقل {min_value} باشد")
        
        if max_value is not None and number > max_value:
            raise ValidationError(f"عدد نباید بیشتر از {max_value} باشد")
        
        return number
    except ValueError:
        raise ValidationError("لطفاً یک عدد معتبر وارد کنید")


def validate_email(value: str) -> str:
    """Validate email address"""
    value = value.strip().lower()
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, value):
        raise ValidationError("فرمت ایمیل صحیح نیست")
    
    return value


def validate_phone(value: str) -> str:
    """Validate Iranian phone number"""
    # Remove spaces and dashes
    value = value.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    
    # Replace Persian digits
    persian_to_english = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
    value = value.translate(persian_to_english)
    
    # Check Iranian mobile format
    pattern = r'^(\+98|0)?9\d{9}$'
    if not re.match(pattern, value):
        raise ValidationError("شماره موبایل صحیح نیست. فرمت صحیح: 09123456789")
    
    # Normalize to 09XXXXXXXXX format
    if value.startswith("+98"):
        value = "0" + value[3:]
    elif value.startswith("98"):
        value = "0" + value[2:]
    elif value.startswith("9"):
        value = "0" + value
    
    return value


def validate_date(value: str, date_format: str = "%Y/%m/%d") -> datetime:
    """Validate date input"""
    # Replace Persian digits
    persian_to_english = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
    value = value.translate(persian_to_english)
    
    try:
        date_obj = datetime.strptime(value, date_format)
        
        # Check if date is reasonable (not too far in past or future)
        now = datetime.now()
        if date_obj.year < 1900 or date_obj.year > now.year + 100:
            raise ValidationError("تاریخ وارد شده نامعتبر است")
        
        return date_obj
    except ValueError:
        raise ValidationError(f"فرمت تاریخ صحیح نیست. فرمت صحیح: {date_format}")


def validate_url(value: str) -> str:
    """Validate URL"""
    value = value.strip()
    
    pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    if not re.match(pattern, value):
        raise ValidationError("آدرس URL صحیح نیست")
    
    return value


def validate_telegram_username(value: str) -> str:
    """Validate Telegram username"""
    value = value.strip().lstrip('@')
    
    pattern = r'^[a-zA-Z0-9_]{5,32}$'
    if not re.match(pattern, value):
        raise ValidationError("یوزرنیم تلگرام صحیح نیست")
    
    return value


def validate_field_value(field_type: str, value: str, validation_rule: Optional[str] = None) -> Any:
    """
    Validate field value based on field type
    
    Args:
        field_type: Type of field (text, number, email, phone, date, select)
        value: Value to validate
        validation_rule: Optional custom validation rule (regex pattern)
    
    Returns:
        Validated and formatted value
    
    Raises:
        ValidationError: If validation fails
    """
    if field_type == "text":
        validated = validate_text(value)
    elif field_type == "number":
        validated = validate_number(value)
    elif field_type == "email":
        validated = validate_email(value)
    elif field_type == "phone":
        validated = validate_phone(value)
    elif field_type == "date":
        validated = validate_date(value)
    elif field_type == "select":
        validated = validate_text(value)
    else:
        validated = validate_text(value)
    
    # Apply custom validation rule if provided
    if validation_rule:
        try:
            if not re.match(validation_rule, str(validated)):
                raise ValidationError("مقدار وارد شده با قوانین مطابقت ندارد")
        except re.error:
            # Invalid regex pattern, skip
            pass
    
    return validated
