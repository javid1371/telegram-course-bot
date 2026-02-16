"""add lead scoring rules and sales trigger setting

Revision ID: leadscore001
Revises: salesowners001
Create Date: 2026-02-16

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'leadscore001'
down_revision = 'salesowners001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Lead Scoring Rules table ──
    op.create_table(
        'lead_scoring_rules',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('event_type', sa.String(50), unique=True, nullable=False),
        sa.Column('points', sa.Integer, default=0, nullable=False),
        sa.Column('label', sa.String(100), nullable=False),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Seed default scoring rules ──
    op.execute("""
        INSERT INTO lead_scoring_rules (event_type, points, label, is_active) VALUES
        ('register', 10, 'ثبت‌نام', true),
        ('lesson_complete', 5, 'تکمیل درس', true),
        ('quiz_pass', 10, 'قبولی کوییز', true),
        ('quiz_fail', -3, 'عدم قبولی کوییز', true),
        ('form_submit', 15, 'ارسال فرم', true),
        ('speed_2x', 5, 'فعال‌سازی سرعت ۲x', true),
        ('course_complete', 20, 'تکمیل دوره', true)
        ON CONFLICT (event_type) DO NOTHING;
    """)

    # ── Add sales_trigger_lesson to company_info ──
    op.execute("""
        INSERT INTO company_info (key, value)
        VALUES ('sales_trigger_lesson', '')
        ON CONFLICT (key) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DELETE FROM company_info WHERE key = 'sales_trigger_lesson'")
    op.drop_table('lead_scoring_rules')
