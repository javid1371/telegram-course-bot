"""add cross-platform sync tables

Revision ID: crosssync001
Revises: webhookevents001, add_crm_field_mapping
Create Date: 2026-02-25

Merge migration that also creates the sync_events and sync_user_snapshots
tables required for bidirectional cross-platform sync (Telegram ↔ Bale).

Phase 3 of 3 — sync event queue + shadow profile tables.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers — merge two heads into one
revision = 'crosssync001'
down_revision = ('webhookevents001', 'add_crm_field_mapping')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── sync_events — queue of progress events for cross-platform push ──
    op.create_table(
        'sync_events',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), server_default='0'),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_sync_events_event_type', 'sync_events', ['event_type'])
    op.create_index('ix_sync_events_user_id', 'sync_events', ['user_id'])
    op.create_index('ix_sync_events_phone', 'sync_events', ['phone'])
    op.create_index('ix_sync_events_status', 'sync_events', ['status'])

    # ── sync_user_snapshots — shadow profiles from the peer platform ──
    op.create_table(
        'sync_user_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('phone', sa.String(50), nullable=False, unique=True),
        sa.Column('source_platform', sa.String(20), nullable=False),

        # Registration snapshot
        sa.Column('registration_data', sa.JSON(), nullable=True),
        sa.Column('first_name', sa.String(255), nullable=True),
        sa.Column('last_name', sa.String(255), nullable=True),

        # Course progress pointers
        sa.Column('current_course_id', sa.Integer(), nullable=True),
        sa.Column('current_lesson_id', sa.Integer(), nullable=True),
        sa.Column('completed_courses', sa.JSON(), nullable=True),
        sa.Column('is_completed', sa.Boolean(), server_default='false'),

        # Detailed progress (JSON arrays)
        sa.Column('progress_records', sa.JSON(), nullable=True),
        sa.Column('quiz_attempts', sa.JSON(), nullable=True),
        sa.Column('form_responses', sa.JSON(), nullable=True),

        # Metadata
        sa.Column('lead_score', sa.Integer(), server_default='0'),
        sa.Column('tags', sa.JSON(), nullable=True),

        # Tracking
        sa.Column('events_applied', sa.Integer(), server_default='0'),
        sa.Column('applied_to_user_id', sa.Integer(), nullable=True),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_sync_user_snapshots_phone', 'sync_user_snapshots', ['phone'])


def downgrade() -> None:
    op.drop_index('ix_sync_user_snapshots_phone', table_name='sync_user_snapshots')
    op.drop_table('sync_user_snapshots')
    op.drop_index('ix_sync_events_status', table_name='sync_events')
    op.drop_index('ix_sync_events_phone', table_name='sync_events')
    op.drop_index('ix_sync_events_user_id', table_name='sync_events')
    op.drop_index('ix_sync_events_event_type', table_name='sync_events')
    op.drop_table('sync_events')
