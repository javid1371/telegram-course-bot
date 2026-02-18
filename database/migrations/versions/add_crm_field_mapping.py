"""add crm_field to registration_fields

Revision ID: add_crm_field_mapping
Revises: add_lesson_number
Create Date: 2026-02-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_crm_field_mapping'
down_revision = 'add_lesson_number'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'registration_fields',
        sa.Column('crm_field', sa.String(200), nullable=True),
    )

    # Set default CRM mappings for common field names
    op.execute("""
        UPDATE registration_fields SET crm_field = 'person.phone'
        WHERE field_name IN ('phone', 'mobile') AND crm_field IS NULL
    """)
    op.execute("""
        UPDATE registration_fields SET crm_field = 'person.name'
        WHERE field_name IN ('name', 'full_name') AND crm_field IS NULL
    """)
    op.execute("""
        UPDATE registration_fields SET crm_field = 'person.email'
        WHERE field_name IN ('email') AND crm_field IS NULL
    """)


def downgrade() -> None:
    op.drop_column('registration_fields', 'crm_field')
