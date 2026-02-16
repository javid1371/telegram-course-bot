"""add sales owners and company info support

Revision ID: salesowners001
Revises: dualplatform001
Create Date: 2026-02-20

Adds:
- company_info table (key-value store for company details)
- sales_owners table (sales team with weighted assignment)
- users.assigned_owner_id FK → sales_owners
- users.assigned_owner_name (denormalized for display)
- users.assigned_at timestamp
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'salesowners001'
down_revision = 'dualplatform001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── company_info (key-value) ────────────────────────────────
    op.create_table(
        'company_info',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('key', sa.String(100), nullable=False, unique=True),
        sa.Column('value', sa.Text, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Seed default company info
    company_info = sa.table(
        'company_info',
        sa.column('key', sa.String),
        sa.column('value', sa.Text),
    )
    op.bulk_insert(company_info, [
        {'key': 'name', 'value': 'شرکت آموزشی'},
        {'key': 'phone', 'value': '021-12345678'},
        {'key': 'working_hours', 'value': 'شنبه تا چهارشنبه ۹ تا ۱۸'},
        {'key': 'address', 'value': ''},
        {'key': 'website', 'value': ''},
        {'key': 'extra_info', 'value': ''},
    ])

    # ── sales_owners ────────────────────────────────────────────
    op.create_table(
        'sales_owners',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('didar_owner_id', sa.String(100), nullable=True, unique=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('internal_number', sa.String(20), nullable=True),
        sa.Column('telegram_username', sa.String(255), nullable=True),
        sa.Column('bale_username', sa.String(255), nullable=True),
        sa.Column('weight', sa.Integer, default=1, nullable=False),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),
        sa.Column('total_assignments', sa.Integer, default=0, nullable=False),
        sa.Column('last_assignment_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── users — owner assignment columns ────────────────────────
    op.add_column('users', sa.Column('assigned_owner_id', sa.Integer, nullable=True))
    op.add_column('users', sa.Column('assigned_owner_name', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        'fk_users_assigned_owner',
        'users', 'sales_owners',
        ['assigned_owner_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_users_assigned_owner', 'users', type_='foreignkey')
    op.drop_column('users', 'assigned_at')
    op.drop_column('users', 'assigned_owner_name')
    op.drop_column('users', 'assigned_owner_id')
    op.drop_table('sales_owners')
    op.drop_table('company_info')
