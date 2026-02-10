"""
Database models for Telegram Course Bot
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    BigInteger, String, Boolean, Integer, Text, DateTime,
    ForeignKey, JSON, ARRAY, Float, Enum as SQLEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import enum

from database import Base


class ContentType(enum.Enum):
    """Lesson content types"""
    TEXT = "text"
    VIDEO = "video"
    AUDIO = "audio"
    VOICE = "voice"
    DOCUMENT = "document"
    PHOTO = "photo"


class FieldType(enum.Enum):
    """Registration field types"""
    TEXT = "text"
    NUMBER = "number"
    EMAIL = "email"
    PHONE = "phone"
    DATE = "date"
    SELECT = "select"


class MessageStatus(enum.Enum):
    """Scheduled message status"""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ===========================
# ADMIN MODEL
# ===========================
class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Admin {self.telegram_user_id} - {self.full_name}>"


# ===========================
# REGISTRATION FIELDS MODEL
# ===========================
class RegistrationField(Base):
    __tablename__ = "registration_fields"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_label: Mapped[str] = mapped_column(String(255), nullable=False)
    field_type: Mapped[FieldType] = mapped_column(SQLEnum(FieldType), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    order: Mapped[int] = mapped_column(Integer, default=0)
    validation_rule: Mapped[Optional[str]] = mapped_column(String(500))
    options: Mapped[Optional[dict]] = mapped_column(JSON)  # For SELECT type
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<RegistrationField {self.field_name} - {self.field_type.value}>"


# ===========================
# USER MODEL
# ===========================
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    first_name: Mapped[Optional[str]] = mapped_column(String(255))
    last_name: Mapped[Optional[str]] = mapped_column(String(255))

    # Dynamic registration data (JSONB for flexible storage)
    registration_data: Mapped[Optional[dict]] = mapped_column(JSON)

    # Course progress
    current_lesson_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("lessons.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Marketing & Analytics
    tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))
    lead_score: Mapped[int] = mapped_column(Integer, default=0)
    referral_code: Mapped[Optional[str]] = mapped_column(String(50), unique=True)
    referred_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    source_campaign: Mapped[Optional[str]] = mapped_column(String(100))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    progress_records: Mapped[List["UserProgress"]] = relationship("UserProgress", back_populates="user", cascade="all, delete-orphan")
    current_lesson: Mapped[Optional["Lesson"]] = relationship("Lesson", foreign_keys=[current_lesson_id])

    def __repr__(self):
        return f"<User {self.telegram_user_id} - {self.first_name}>"


# ===========================
# LESSON MODEL
# ===========================
class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Content
    content_type: Mapped[ContentType] = mapped_column(SQLEnum(ContentType), nullable=False)
    file_id: Mapped[Optional[str]] = mapped_column(String(500))  # Telegram file_id
    text_content: Mapped[Optional[str]] = mapped_column(Text)

    # Display settings
    order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Delay before sending next lesson (in hours, 0 = instant)
    delay_hours: Mapped[int] = mapped_column(Integer, default=0)

    # Call to Action
    cta_text: Mapped[Optional[str]] = mapped_column(String(255))
    cta_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    progress_records: Mapped[List["UserProgress"]] = relationship("UserProgress", back_populates="lesson")

    def __repr__(self):
        return f"<Lesson {self.order} - {self.title}>"


# ===========================
# USER PROGRESS MODEL
# ===========================
class UserProgress(Base):
    __tablename__ = "user_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    lesson_id: Mapped[int] = mapped_column(Integer, ForeignKey("lessons.id"), nullable=False, index=True)

    # Progress tracking
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    confirmation_count: Mapped[int] = mapped_column(Integer, default=0)
    time_spent: Mapped[Optional[int]] = mapped_column(Integer)  # in seconds

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="progress_records")
    lesson: Mapped["Lesson"] = relationship("Lesson", back_populates="progress_records")

    def __repr__(self):
        return f"<UserProgress user={self.user_id} lesson={self.lesson_id}>"


# ===========================
# WEBHOOK SETTINGS MODEL
# ===========================
class WebhookSetting(Base):
    __tablename__ = "webhook_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    method: Mapped[str] = mapped_column(String(10), default="POST")  # GET, POST

    # Payload configuration (JSON template with variables)
    payload_template: Mapped[Optional[dict]] = mapped_column(JSON)

    # Headers
    headers: Mapped[Optional[dict]] = mapped_column(JSON)

    # Settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=3)
    timeout: Mapped[int] = mapped_column(Integer, default=10)  # seconds

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<WebhookSetting {self.name} - {self.url}>"


# ===========================
# CAMPAIGN MODEL
# ===========================
class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    tracking_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Stats
    users_count: Mapped[int] = mapped_column(Integer, default=0)
    conversion_count: Mapped[int] = mapped_column(Integer, default=0)
    conversion_rate: Mapped[float] = mapped_column(Float, default=0.0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Campaign {self.name} - {self.tracking_code}>"


# ===========================
# SCHEDULED MESSAGE MODEL
# ===========================
class ScheduledMessage(Base):
    __tablename__ = "scheduled_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))  # None for broadcast
    message: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(50), default="reminder")  # reminder, promotional, etc.

    send_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[MessageStatus] = mapped_column(SQLEnum(MessageStatus), default=MessageStatus.PENDING)

    # Metadata
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<ScheduledMessage {self.id} - {self.status.value}>"


# ===========================
# BROADCAST LOG MODEL
# ===========================
class BroadcastLog(Base):
    __tablename__ = "broadcast_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(Integer, ForeignKey("admins.id"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Target
    target_filter: Mapped[Optional[dict]] = mapped_column(JSON)  # Tags, campaigns, etc.

    # Stats
    total_users: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self):
        return f"<BroadcastLog {self.id} - {self.success_count}/{self.total_users}>"


# ===========================
# DAILY STATS MODEL
# ===========================
class DailyStat(Base):
    __tablename__ = "daily_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), unique=True, nullable=False, index=True)

    new_users: Mapped[int] = mapped_column(Integer, default=0)
    active_users: Mapped[int] = mapped_column(Integer, default=0)
    completed_lessons: Mapped[int] = mapped_column(Integer, default=0)
    completed_courses: Mapped[int] = mapped_column(Integer, default=0)
    avg_completion_time: Mapped[Optional[float]] = mapped_column(Float)  # in hours

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<DailyStat {self.date.date()} - {self.new_users} new users>"
