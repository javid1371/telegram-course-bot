"""add webhook events filter column

Revision ID: webhookevents001
Revises: leadscore001
Create Date: 2026-02-17

Adds an optional JSON 'events' column to webhook_settings so admins
can restrict which event types a webhook receives (e.g. ["lead.register"]).
NULL = receive all events (backward-compatible default).
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'webhookevents001'
down_revision = 'leadscore001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'webhook_settings',
        sa.Column('events', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('webhook_settings', 'events')
