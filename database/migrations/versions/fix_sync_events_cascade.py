"""fix sync_events FK cascade

Revision ID: fixsyncfk001
Revises: supportchat001
Create Date: 2026-03-15
"""
from alembic import op

revision = "fixsyncfk001"
down_revision = "supportchat001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old FK and re-create with ON DELETE CASCADE
    op.drop_constraint("sync_events_user_id_fkey", "sync_events", type_="foreignkey")
    op.create_foreign_key(
        "sync_events_user_id_fkey",
        "sync_events",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("sync_events_user_id_fkey", "sync_events", type_="foreignkey")
    op.create_foreign_key(
        "sync_events_user_id_fkey",
        "sync_events",
        "users",
        ["user_id"],
        ["id"],
    )
