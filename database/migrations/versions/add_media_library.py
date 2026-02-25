"""add media library table

Revision ID: medialibrary001
Revises: lead_scoring_001
Create Date: 2026-02-17

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'medialibrary001'
down_revision = 'leadscore001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'media_library',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=500), nullable=False),
        sa.Column('file_type', sa.String(length=50), nullable=False),
        sa.Column('file_id', sa.String(length=500), nullable=False),
        sa.Column('platform', sa.String(length=20), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=True),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('uploaded_by', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_media_library_platform'), 'media_library', ['platform'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_media_library_platform'), table_name='media_library')
    op.drop_table('media_library')
