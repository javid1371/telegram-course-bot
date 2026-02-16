"""
Lead scoring service — configurable scoring rules + score calculation.

Admin can edit points per event type from the panel.
The event emitter calls ``update_user_score`` on every webhook event
to keep the running ``user.lead_score`` up to date.
"""
import logging
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import LeadScoringRule, User

logger = logging.getLogger(__name__)

# Map webhook event keys → scoring event_type
EVENT_TYPE_MAP: Dict[str, str] = {
    "lead.register": "register",
    "lesson.complete": "lesson_complete",
    "quiz.pass": "quiz_pass",
    "quiz.fail": "quiz_fail",
    "form.submit": "form_submit",
    "speed.change": "speed_2x",
    "course.complete": "course_complete",
}


class ScoringService:
    """Service for lead scoring rule CRUD + score calculation."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Rules CRUD ──────────────────────────────────────────

    async def get_all_rules(self) -> List[LeadScoringRule]:
        """Get all scoring rules ordered by id."""
        result = await self.session.execute(
            select(LeadScoringRule).order_by(LeadScoringRule.id)
        )
        return list(result.scalars().all())

    async def get_rule(self, event_type: str) -> Optional[LeadScoringRule]:
        """Get a single rule by event_type."""
        result = await self.session.execute(
            select(LeadScoringRule).where(
                LeadScoringRule.event_type == event_type
            )
        )
        return result.scalar_one_or_none()

    async def update_rule_points(self, event_type: str, points: int) -> bool:
        """Update the points for a scoring rule."""
        rule = await self.get_rule(event_type)
        if not rule:
            return False
        rule.points = points
        await self.session.commit()
        return True

    async def toggle_rule(self, event_type: str) -> Optional[bool]:
        """Toggle rule active/inactive. Returns new state or None."""
        rule = await self.get_rule(event_type)
        if not rule:
            return None
        rule.is_active = not rule.is_active
        await self.session.commit()
        return rule.is_active

    # ── Score Calculation ───────────────────────────────────

    async def get_active_points(self, event_type: str) -> int:
        """Get points for an event_type (0 if inactive or missing)."""
        result = await self.session.execute(
            select(LeadScoringRule).where(
                LeadScoringRule.event_type == event_type,
                LeadScoringRule.is_active == True,
            )
        )
        rule = result.scalar_one_or_none()
        return rule.points if rule else 0

    async def update_user_score(
        self, user: User, webhook_event_key: str
    ) -> int:
        """
        Add delta points to user's lead_score based on the webhook event.

        Parameters
        ----------
        user : User
            The user whose score to update.
        webhook_event_key : str
            Webhook event key like ``"lesson.complete"``.

        Returns
        -------
        int
            The user's new lead_score.
        """
        scoring_type = EVENT_TYPE_MAP.get(webhook_event_key)
        if not scoring_type:
            return user.lead_score or 0

        points = await self.get_active_points(scoring_type)
        if points != 0:
            user.lead_score = (user.lead_score or 0) + points
            logger.info(
                f"[Scoring] user {user.telegram_user_id}: "
                f"{webhook_event_key} → {points:+d} pts "
                f"(total: {user.lead_score})"
            )
        return user.lead_score or 0
