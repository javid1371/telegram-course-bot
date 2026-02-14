"""
Export service - handles Excel export functionality
"""
import logging
from io import BytesIO
from datetime import datetime
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Lesson, UserProgress, RegistrationField
import config
from messages import EXPORT

logger = logging.getLogger(__name__)


class ExportService:
    """Service for exporting data to Excel"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def export_users_to_excel(
        self,
        is_active: Optional[bool] = None,
        is_completed: Optional[bool] = None,
        tags: Optional[List[str]] = None,
    ) -> BytesIO:
        """Export users list to Excel"""
        import pandas as pd

        query = select(User)
        if is_active is not None:
            query = query.where(User.is_active == is_active)
        if is_completed is not None:
            query = query.where(User.is_completed == is_completed)
        if tags:
            for tag in tags:
                query = query.where(User.tags.contains([tag]))

        query = query.order_by(User.created_at.desc())
        result = await self.session.execute(query)
        users = list(result.scalars().all())

        # Get registration fields for column headers
        fields_result = await self.session.execute(
            select(RegistrationField)
            .where(RegistrationField.is_active == True)
            .order_by(RegistrationField.order)
        )
        reg_fields = list(fields_result.scalars().all())

        # Build data
        data = []
        for user in users:
            row = {
                EXPORT["col_id"]: user.id,
                EXPORT["col_telegram_id"]: user.telegram_user_id,
                EXPORT["col_username"]: user.username or "-",
                EXPORT["col_first_name"]: user.first_name or "-",
                EXPORT["col_last_name"]: user.last_name or "-",
                EXPORT["col_status"]: EXPORT["val_active"] if user.is_active else EXPORT["val_inactive"],
                EXPORT["col_completed"]: EXPORT["val_yes"] if user.is_completed else EXPORT["val_no"],
                EXPORT["col_tags"]: ", ".join(user.tags) if user.tags else "-",
                EXPORT["col_campaign"]: user.source_campaign or "-",
                EXPORT["col_reg_date"]: user.created_at.strftime("%Y/%m/%d %H:%M") if user.created_at else "-",
                EXPORT["col_last_activity"]: user.last_activity_at.strftime("%Y/%m/%d %H:%M") if user.last_activity_at else "-",
            }

            # Add registration data fields
            if user.registration_data and reg_fields:
                for field in reg_fields:
                    row[field.field_label] = user.registration_data.get(field.field_name, "-")

            data.append(row)

        df = pd.DataFrame(data)

        # Write to BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=EXPORT["sheet_users"])
        output.seek(0)

        return output

    async def export_progress_to_excel(self) -> BytesIO:
        """Export progress data to Excel"""
        import pandas as pd

        # Get all users with progress
        users_result = await self.session.execute(
            select(User).order_by(User.created_at.desc())
        )
        users = list(users_result.scalars().all())

        # Get all lessons
        lessons_result = await self.session.execute(
            select(Lesson).where(Lesson.is_active == True).order_by(Lesson.order)
        )
        lessons = list(lessons_result.scalars().all())

        data = []
        for user in users:
            row = {
                EXPORT["col_telegram_id"]: user.telegram_user_id,
                EXPORT["col_name"]: f"{user.first_name or ''} {user.last_name or ''}".strip() or "-",
            }

            # Get progress for each lesson
            for lesson in lessons:
                progress_result = await self.session.execute(
                    select(UserProgress).where(
                        UserProgress.user_id == user.id,
                        UserProgress.lesson_id == lesson.id,
                    )
                )
                progress = progress_result.scalar_one_or_none()

                if progress and progress.completed_at:
                    row[f"درس {lesson.order}: {lesson.title}"] = EXPORT["val_completed"]
                elif progress:
                    row[f"درس {lesson.order}: {lesson.title}"] = EXPORT["val_in_progress"]
                else:
                    row[f"درس {lesson.order}: {lesson.title}"] = EXPORT["val_not_started"]

            data.append(row)

        df = pd.DataFrame(data)

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=EXPORT["sheet_progress"])
        output.seek(0)

        return output

    async def export_analytics_to_excel(self) -> BytesIO:
        """Export analytics summary to Excel"""
        import pandas as pd
        from services.analytics_service import AnalyticsService

        analytics = AnalyticsService(self.session)

        # Dashboard stats
        dashboard = await analytics.get_dashboard_stats()
        dashboard_data = [
            {EXPORT["col_indicator"]: EXPORT["ind_total_users"], EXPORT["col_value"]: dashboard["total_users"]},
            {EXPORT["col_indicator"]: EXPORT["ind_active_users"], EXPORT["col_value"]: dashboard["active_users"]},
            {EXPORT["col_indicator"]: EXPORT["ind_completed_users"], EXPORT["col_value"]: dashboard["completed_courses"]},
            {EXPORT["col_indicator"]: EXPORT["ind_completion_rate"], EXPORT["col_value"]: dashboard["completion_rate"]},
            {EXPORT["col_indicator"]: EXPORT["ind_today_new"], EXPORT["col_value"]: dashboard["today_new_users"]},
            {EXPORT["col_indicator"]: EXPORT["ind_week_new"], EXPORT["col_value"]: dashboard["week_new_users"]},
        ]

        # Lesson stats
        lesson_stats = await analytics.get_lesson_completion_stats()
        lesson_data = [
            {
                EXPORT["col_lesson"]: f"{s['order']}. {s['title']}",
                EXPORT["col_started"]: s["started"],
                EXPORT["col_lesson_completed"]: s["completed"],
                EXPORT["col_completion_rate"]: s["completion_rate"],
            }
            for s in lesson_stats
        ]

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            pd.DataFrame(dashboard_data).to_excel(writer, index=False, sheet_name=EXPORT["sheet_dashboard"])
            if lesson_data:
                pd.DataFrame(lesson_data).to_excel(writer, index=False, sheet_name=EXPORT["sheet_lessons"])
        output.seek(0)

        return output
