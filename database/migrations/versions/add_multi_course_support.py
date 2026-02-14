"""add multi course support

Revision ID: multicourse001
Revises:
Create Date: 2026-02-11

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'multicourse001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create courses table
    op.create_table(
        'courses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('order', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Add course_id to lessons
    op.add_column('lessons', sa.Column('course_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_lessons_course_id'), 'lessons', ['course_id'], unique=False)
    op.create_foreign_key('fk_lessons_course_id', 'lessons', 'courses', ['course_id'], ['id'])

    # Add current_course_id and completed_courses to users
    op.add_column('users', sa.Column('current_course_id', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('completed_courses', sa.JSON(), nullable=True, server_default='{}'))
    op.create_foreign_key('fk_users_current_course_id', 'users', 'courses', ['current_course_id'], ['id'])

    # Create a default course and assign all existing lessons to it
    op.execute("""
        INSERT INTO courses (title, description, is_active, "order")
        VALUES ('دوره پیش‌فرض', 'دوره اصلی', true, 1)
    """)
    op.execute("""
        UPDATE lessons SET course_id = (SELECT id FROM courses LIMIT 1)
    """)
    op.execute("""
        UPDATE users SET current_course_id = (SELECT id FROM courses LIMIT 1) WHERE is_active = true
    """)


def downgrade() -> None:
    op.drop_constraint('fk_users_current_course_id', 'users', type_='foreignkey')
    op.drop_column('users', 'completed_courses')
    op.drop_column('users', 'current_course_id')
    op.drop_constraint('fk_lessons_course_id', 'lessons', type_='foreignkey')
    op.drop_index(op.f('ix_lessons_course_id'), table_name='lessons')
    op.drop_column('lessons', 'course_id')
    op.drop_table('courses')
