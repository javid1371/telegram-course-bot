"""Manual migration script for multi-course support"""
from sqlalchemy import create_engine, text
import os

db_url = os.environ.get("DATABASE_URL", "postgresql://bot_user:changeme@postgres:5432/course_bot")
engine = create_engine(db_url)

alterations = [
    ("ALTER TABLE lessons ADD COLUMN course_id INTEGER REFERENCES courses(id)", "Added course_id to lessons"),
    ("CREATE INDEX ix_lessons_course_id ON lessons(course_id)", "Created index on lessons.course_id"),
    ("ALTER TABLE users ADD COLUMN current_course_id INTEGER REFERENCES courses(id)", "Added current_course_id to users"),
    ("ALTER TABLE users ADD COLUMN completed_courses JSON DEFAULT '{}'", "Added completed_courses to users"),
]

for sql, msg in alterations:
    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
            print(msg)
    except Exception as e:
        if "already exists" in str(e):
            print(f"SKIP (already exists): {msg}")
        else:
            print(f"ERROR: {msg}: {e}")

with engine.begin() as conn:
    # Create default course
    result = conn.execute(text("SELECT id FROM courses LIMIT 1"))
    existing = result.fetchone()
    if not existing:
        conn.execute(text("INSERT INTO courses (title, description, is_active, \"order\") VALUES ('دوره پیش‌فرض', 'دوره اصلی', true, 1)"))
        r = conn.execute(text("SELECT id FROM courses ORDER BY id DESC LIMIT 1"))
        course_id = r.fetchone()[0]
        print(f"Created default course id={course_id}")
        conn.execute(text(f"UPDATE lessons SET course_id = {course_id}"))
        print("Assigned all lessons to default course")
        conn.execute(text(f"UPDATE users SET current_course_id = {course_id} WHERE is_active = true"))
        print("Set current_course_id for active users")
    else:
        print(f"Course already exists: {existing}")

print("Migration complete!")
