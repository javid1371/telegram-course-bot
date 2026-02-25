"""
Database models for Telegram Course Bot
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    BigInteger, String, Boolean, Integer, Text, DateTime,
    ForeignKey, JSON, ARRAY, Float, Enum as SQLEnum, UniqueConstraint
)
import sqlalchemy as sa
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
    FORM = "form"


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

    # CRM field mapping — maps this registration field to a CRM (Didar) field.
    # Conventions:
    #   null / ""       → included as a note (default)
    #   "note"          → explicitly a note
    #   "person.phone"  → standard CRM person field (FirstName, LastName, MobilePhone)
    #   "Field_996_0_26" → Didar custom field ID
    crm_field: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    def __repr__(self):
        return f"<RegistrationField {self.field_name} - {self.field_type.value}>"


# ===========================
# COURSE MODEL
# ===========================
class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    order: Mapped[int] = mapped_column(Integer, default=0)

    # Allow users to activate 2x speed (get 2 lessons per delivery)
    allow_2x: Mapped[bool] = mapped_column(Boolean, default=False)

    # Allow users to activate fast track (reduced delay)
    allow_fast_track: Mapped[bool] = mapped_column(Boolean, default=False)
    fast_track_delay: Mapped[int] = mapped_column(Integer, default=5)  # minutes

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    lessons: Mapped[List["Lesson"]] = relationship("Lesson", back_populates="course", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Course {self.id} - {self.title}>"


# ===========================
# USER MODEL
# ===========================
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    first_name: Mapped[Optional[str]] = mapped_column(String(255))
    last_name: Mapped[Optional[str]] = mapped_column(String(255))

    # Platform — "telegram" or "bale" (each deploy only writes its own)
    platform: Mapped[str] = mapped_column(String(20), default="telegram", nullable=False, index=True)

    # Shadow user — created by cross-platform sync before user /start's on this platform.
    # When the user actually /start's, is_shadow is flipped to False and telegram_user_id is updated.
    is_shadow: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa.text("false"), index=True)

    # Dynamic registration data (JSONB for flexible storage)
    registration_data: Mapped[Optional[dict]] = mapped_column(JSON)

    # Course progress
    current_lesson_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("lessons.id"))
    current_course_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("courses.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Per-course completion tracking {course_id: true/false}
    completed_courses: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # 2x speed: {"course_id": {"active": true, "bonus_delivered": false}}
    double_speed_courses: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # Fast track: {"course_id": true}
    fast_track_courses: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # Marketing & Analytics
    tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))
    lead_score: Mapped[int] = mapped_column(Integer, default=0)
    referral_code: Mapped[Optional[str]] = mapped_column(String(50), unique=True)
    referred_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    source_campaign: Mapped[Optional[str]] = mapped_column(String(100))

    # Assigned sales owner (set from webhook response)
    assigned_owner_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("sales_owners.id", ondelete="SET NULL"))
    assigned_owner_name: Mapped[Optional[str]] = mapped_column(String(255))
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    progress_records: Mapped[List["UserProgress"]] = relationship("UserProgress", back_populates="user", cascade="all, delete-orphan")
    current_lesson: Mapped[Optional["Lesson"]] = relationship("Lesson", foreign_keys=[current_lesson_id])
    current_course_rel: Mapped[Optional["Course"]] = relationship("Course", foreign_keys=[current_course_id])
    assigned_owner: Mapped[Optional["SalesOwner"]] = relationship("SalesOwner", back_populates="assigned_users")

    # Unique constraint: same messenger user ID can exist on both platforms
    # Shadow users (telegram_user_id=0) are excluded from the constraint
    __table_args__ = (
        sa.Index(
            'uq_user_platform_active',
            'telegram_user_id', 'platform',
            unique=True,
            postgresql_where=sa.text("is_shadow = false"),
        ),
    )

    def __repr__(self):
        return f"<User {self.telegram_user_id}@{self.platform} - {self.first_name}>"


# ===========================
# LESSON MODEL
# ===========================
class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Course association
    course_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("courses.id"), index=True)

    # Content
    content_type: Mapped[ContentType] = mapped_column(SQLEnum(ContentType), nullable=False)
    file_id: Mapped[Optional[str]] = mapped_column(String(500))  # Telegram file_id
    text_content: Mapped[Optional[str]] = mapped_column(Text)

    # Display settings
    order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    lesson_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Delay before sending next lesson (in minutes, 0 = instant)
    delay_hours: Mapped[int] = mapped_column(Integer, default=0)

    # Deadline for viewing this lesson (in hours, None = no deadline)
    view_deadline_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Call to Action
    cta_text: Mapped[Optional[str]] = mapped_column(String(255))
    cta_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Multi-content blocks (JSON array)
    # [{"type": "text", "text": "..."}, {"type": "video", "file_id": "..."}, ...]
    contents: Mapped[Optional[list]] = mapped_column(JSON)

    # Quiz attached to this lesson (JSON)
    quiz_data: Mapped[Optional[dict]] = mapped_column(JSON)
    # Form definition for FORM type lessons (JSON)
    form_data: Mapped[Optional[dict]] = mapped_column(JSON)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    course: Mapped[Optional["Course"]] = relationship("Course", back_populates="lessons")
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

    # Event filtering (JSON list of event keys, e.g. ["lead.register", "lesson.complete"])
    # When NULL or empty → all events are sent to this webhook
    events: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<WebhookSetting {self.name} - {self.url}>"


# ===========================
# WEBHOOK FAILED EVENT MODEL
# ===========================
class WebhookFailedEvent(Base):
    """Queue for webhook events that failed delivery — retried by scheduler"""
    __tablename__ = "webhook_failed_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    webhook_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    webhook_name: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self):
        return f"<WebhookFailedEvent {self.event_id} - {self.event_type}>"


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


# ===========================
# QUIZ ATTEMPT MODEL
# ===========================
class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    lesson_id: Mapped[int] = mapped_column(Integer, ForeignKey("lessons.id"), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    answers: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<QuizAttempt user={self.user_id} lesson={self.lesson_id} score={self.score}>"


# ===========================
# FORM RESPONSE MODEL
# ===========================
class FormResponse(Base):
    __tablename__ = "form_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    lesson_id: Mapped[int] = mapped_column(Integer, ForeignKey("lessons.id"), nullable=False, index=True)
    response_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<FormResponse user={self.user_id} lesson={self.lesson_id}>"


# ===========================
# BOT TEXT OVERRIDE MODEL
# ===========================
# ===========================
# MIGRATION CODE MODEL
# ===========================
class MigrationCode(Base):
    """One-time code for migrating a user's progress across platforms.
    Generated on the *source* platform, claimed on the *target* platform."""
    __tablename__ = "migration_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    source_platform: Mapped[str] = mapped_column(String(20), nullable=False)  # "telegram" / "bale"
    source_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Snapshot of data to transfer
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)  # full user + progress dump

    # Status
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_by_user_id: Mapped[Optional[int]] = mapped_column(Integer)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<MigrationCode {self.code} from={self.source_platform}>"


# ===========================
# PLATFORM FILE ID MODEL
# ===========================
class PlatformFileId(Base):
    """Cache of file_id per platform.
    When a lesson is created on Telegram, its file_id only works on Telegram.
    On first delivery in Bale the file is re-uploaded and the Bale file_id is stored."""
    __tablename__ = "platform_file_ids"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lesson_id: Mapped[int] = mapped_column(Integer, ForeignKey("lessons.id"), nullable=False, index=True)
    block_index: Mapped[int] = mapped_column(Integer, default=0)  # 0 for single-content, N for multi-content
    platform: Mapped[str] = mapped_column(String(20), nullable=False)  # "telegram" / "bale"
    file_id: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)  # video / photo / audio / etc.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('lesson_id', 'block_index', 'platform', name='uq_platform_file'),
    )

    def __repr__(self):
        return f"<PlatformFileId lesson={self.lesson_id} block={self.block_index} {self.platform}>"


# ===========================
# BOT TEXT OVERRIDE MODEL
# ===========================
class BotText(Base):
    __tablename__ = "bot_texts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Unique constraint on category+key
    __table_args__ = (
        UniqueConstraint('category', 'key', name='uq_bot_texts_category_key'),
    )

    def __repr__(self):
        return f"<BotText {self.category}.{self.key}>"

# ===========================
# COMPANY INFO MODEL
# ===========================
class CompanyInfo(Base):
    """Key-value store for company contact information (admin-editable)."""
    __tablename__ = "company_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<CompanyInfo {self.key}={self.value[:30]}>"


# ===========================
# SALES OWNER MODEL
# ===========================
class SalesOwner(Base):
    """Sales team member for weighted assignment via CRM workflow."""
    __tablename__ = "sales_owners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    didar_owner_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    internal_number: Mapped[Optional[str]] = mapped_column(String(20))
    telegram_username: Mapped[Optional[str]] = mapped_column(String(255))
    bale_username: Mapped[Optional[str]] = mapped_column(String(255))
    weight: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    total_assignments: Mapped[int] = mapped_column(Integer, default=0)
    last_assignment_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    assigned_users: Mapped[List["User"]] = relationship("User", back_populates="assigned_owner")

    def __repr__(self):
        return f"<SalesOwner {self.name} w={self.weight}>"


# ===========================
# LEAD SCORING RULE MODEL
# ===========================
class LeadScoringRule(Base):
    """Configurable scoring rule — admin can edit points per event type."""
    __tablename__ = "lead_scoring_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<LeadScoringRule {self.event_type}={self.points}>"


# ===========================
# MEDIA LIBRARY MODEL
# ===========================
class MediaFile(Base):
    """
    Media Library — files uploaded by admin via bot chat.
    Stores file_id per platform so they can be reused in lessons.
    """
    __tablename__ = "media_library"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)  # file name / label
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)  # video, audio, document, photo, voice
    file_id: Mapped[str] = mapped_column(String(500), nullable=False)  # platform file_id
    platform: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # telegram / bale
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # bytes
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # seconds (audio/video)
    uploaded_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # admin telegram_user_id
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<MediaFile {self.id} - {self.name} ({self.file_type}@{self.platform})>"


# ===========================
# SYNC EVENT QUEUE MODEL
# ===========================
class SyncEvent(Base):
    """
    Queue of user-progress events destined for the peer platform.

    Events are saved with status='pending', pushed to the peer server immediately,
    and marked 'synced' on success.  Failed pushes stay 'pending' and are retried
    by the scheduler every 30 seconds.
    """
    __tablename__ = "sync_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # e.g. "lesson.complete", "quiz.pass", "form.submit", "course.complete", "lead.register"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    # Phone extracted from registration_data.mobile — used for cross-platform user matching

    # Snapshot of relevant data at event time
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Delivery status
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    # pending = queued for push (immediate attempt + scheduler retry)
    # synced  = successfully delivered to peer
    # failed  = delivery failed (will retry)
    # skipped = no phone → can't match across platforms

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<SyncEvent {self.id} {self.event_type} user={self.user_id} status={self.status}>"


# ===========================
# SYNC USER SNAPSHOT MODEL
# ===========================
class SyncUserSnapshot(Base):
    """
    Shadow profile of a user from the peer platform.

    Created/updated when sync events arrive from the other server.
    When a user registers on *this* platform and their phone matches,
    the snapshot is applied to restore their progress instantly —
    even if the inter-server link is currently down.
    """
    __tablename__ = "sync_user_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    source_platform: Mapped[str] = mapped_column(String(20), nullable=False)  # where the data came from

    # Registration info (snapshot from the peer)
    registration_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Course progress pointers
    current_course_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    current_lesson_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completed_courses: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # {course_id: true}
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Lesson-level progress: [{lesson_id, started_at, completed_at}]
    progress_records: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Quiz attempts: [{lesson_id, score, passed, answers}]
    quiz_attempts: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Form responses: [{lesson_id, response_data}]
    form_responses: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Metadata
    lead_score: Mapped[int] = mapped_column(Integer, default=0)
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Tracking
    events_applied: Mapped[int] = mapped_column(Integer, default=0)  # how many events processed
    applied_to_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # set when snapshot is consumed
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<SyncUserSnapshot phone={self.phone} from={self.source_platform} events={self.events_applied}>"
