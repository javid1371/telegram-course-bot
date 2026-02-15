"""add dual platform support

Revision ID: dualplatform001
Revises: webhookqueue001
Create Date: 2026-02-16

Adds:
- users.platform column  (default 'telegram')
- Unique constraint (telegram_user_id, platform)
- migration_codes table
- platform_file_ids table
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'dualplatform001'
down_revision = 'webhookqueue001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users.platform ──────────────────────────────────────────
    op.add_column('users', sa.Column('platform', sa.String(20), nullable=True))
    op.execute("UPDATE users SET platform = 'telegram' WHERE platform IS NULL")
    op.alter_column('users', 'platform', nullable=False, server_default='telegram')

    # Drop old unique constraint on telegram_user_id only
    # (it might be a unique index — try both)
    try:
        op.drop_constraint('users_telegram_user_id_key', 'users', type_='unique')
    except Exception:
        try:
            op.drop_index('ix_users_telegram_user_id', table_name='users')
        except Exception:
            pass

    # New composite unique + index
    op.create_unique_constraint('uq_user_platform', 'users', ['telegram_user_id', 'platform'])
    op.create_index('ix_users_platform', 'users', ['platform'])

    # ── migration_codes ─────────────────────────────────────────
    op.create_table(
        'migration_codes',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('code', sa.String(20), unique=True, nullable=False, index=True),
        sa.Column('source_platform', sa.String(20), nullable=False),
        sa.Column('source_user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('snapshot', sa.JSON, nullable=False),
        sa.Column('is_used', sa.Boolean, default=False),
        sa.Column('used_by_user_id', sa.Integer),
        sa.Column('used_at', sa.DateTime(timezone=True)),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── platform_file_ids ───────────────────────────────────────
    op.create_table(
        'platform_file_ids',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('lesson_id', sa.Integer, sa.ForeignKey('lessons.id'), nullable=False, index=True),
        sa.Column('block_index', sa.Integer, default=0),
        sa.Column('platform', sa.String(20), nullable=False),
        sa.Column('file_id', sa.String(500), nullable=False),
        sa.Column('content_type', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('lesson_id', 'block_index', 'platform', name='uq_platform_file'),
    )


def downgrade() -> None:
    op.drop_table('platform_file_ids')
    op.drop_table('migration_codes')
    op.drop_index('ix_users_platform', table_name='users')
    op.drop_constraint('uq_user_platform', 'users', type_='unique')
    op.create_unique_constraint('users_telegram_user_id_key', 'users', ['telegram_user_id'])
    op.drop_column('users', 'platform')
