import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import MessageFeedback, User, UserRoleCode
from app.database.models.enums import KarmaReactionType
from app.database.repositories import (
    ApplicationRepository,
    KarmaStatisticsRepository,
    KarmaVoteRepository,
    MessageFeedbackRepository,
)

logger = logging.getLogger(__name__)

NEGATIVE_VOTES_ALERT_THRESHOLD = 5
_ELIGIBLE_AUTHOR_ROLES = {
    UserRoleCode.STUDENT.value,
    UserRoleCode.PSYCHOLOGIST_STARTER.value,
    UserRoleCode.PSYCHOLOGIST.value,
    UserRoleCode.SUPERVISOR.value,
}
_MAX_TAG_LENGTH = 16  # Telegram member-tag hard limit, no emoji allowed


def build_member_tag(role_label: str, karma_points: int) -> str:
    """Member tag shown next to the user's name: "<role> <karma points>".

    No emoji allowed in tags (Bot API constraint), so the karma indicator is
    just the plain number, truncated to fit Telegram's 16-char tag limit.
    """
    return f"{role_label} {karma_points}"[:_MAX_TAG_LENGTH]


@dataclass(frozen=True)
class ReactionChangeResult:
    crossed_threshold: bool
    karma_changed: bool
    karma_points: int | None = None


class KarmaService:
    """Owns the 👍/👎 karma logic: message tracking, vote transitions, and the
    negative-feedback admin alert threshold. See app/handlers/karma.py for the
    Telegram-facing side (message + message_reaction handlers)."""

    def __init__(self, session: AsyncSession) -> None:
        self._application_repo = ApplicationRepository(session)
        self._karma_vote_repo = KarmaVoteRepository(session)
        self._karma_stats_repo = KarmaStatisticsRepository(session)
        self._message_feedback_repo = MessageFeedbackRepository(session)

    async def is_verified(self, user: User | None) -> bool:
        """"Успішно пройшов верифікацію" == has at least one approved application."""
        if user is None:
            return False
        return await self._application_repo.has_approved_application(user.id)

    async def is_eligible_author(self, user: User | None) -> bool:
        if user is None or user.role is None:
            return False
        if user.role.code not in _ELIGIBLE_AUTHOR_ROLES:
            return False
        return await self.is_verified(user)

    async def ensure_message_tracked(
        self, chat_id: int, message_id: int, author_user_id: int
    ) -> MessageFeedback:
        return await self._message_feedback_repo.ensure_tracked(chat_id, message_id, author_user_id)

    async def get_message_feedback(self, chat_id: int, message_id: int) -> MessageFeedback | None:
        return await self._message_feedback_repo.get(chat_id, message_id)

    async def get_karma_points(self, user_id: int) -> int:
        stats = await self._karma_stats_repo.get_by_id(user_id)
        return stats.karma_points if stats is not None else 0

    async def apply_reaction_change(
        self,
        chat_id: int,
        message_id: int,
        author_user_id: int,
        voter_user_id: int,
        old_reaction: KarmaReactionType | None,
        new_reaction: KarmaReactionType | None,
    ) -> ReactionChangeResult:
        """Apply a 👍/👎 reaction transition for one voter on one message."""
        if old_reaction == new_reaction:
            return ReactionChangeResult(crossed_threshold=False, karma_changed=False)

        if new_reaction is not None:
            await self._karma_vote_repo.upsert(
                message_id, chat_id, author_user_id, voter_user_id, new_reaction
            )
        else:
            await self._karma_vote_repo.delete(message_id, voter_user_id)

        crossed_threshold = False
        karma_changed = False

        if old_reaction == KarmaReactionType.HELPED:
            await self._adjust_positive(author_user_id, chat_id, message_id, -1)
            karma_changed = True
        if new_reaction == KarmaReactionType.HELPED:
            await self._adjust_positive(author_user_id, chat_id, message_id, 1)
            karma_changed = True

        if old_reaction == KarmaReactionType.NOT_HELPED:
            await self._adjust_negative(author_user_id, chat_id, message_id, -1)
        if new_reaction == KarmaReactionType.NOT_HELPED:
            crossed_threshold = await self._adjust_negative(author_user_id, chat_id, message_id, 1)

        karma_points = await self.get_karma_points(author_user_id) if karma_changed else None
        return ReactionChangeResult(
            crossed_threshold=crossed_threshold,
            karma_changed=karma_changed,
            karma_points=karma_points,
        )

    async def _adjust_positive(
        self, author_user_id: int, chat_id: int, message_id: int, sign: int
    ) -> None:
        await self._karma_stats_repo.adjust(author_user_id, karma_delta=sign, positive_delta=sign)
        await self._message_feedback_repo.adjust_counts(chat_id, message_id, positive_delta=sign)

    async def _adjust_negative(
        self, author_user_id: int, chat_id: int, message_id: int, sign: int
    ) -> bool:
        await self._karma_stats_repo.adjust(author_user_id, negative_delta=sign)
        feedback = await self._message_feedback_repo.adjust_counts(
            chat_id, message_id, negative_delta=sign
        )
        return (
            sign > 0
            and feedback is not None
            and feedback.negative_count == NEGATIVE_VOTES_ALERT_THRESHOLD + 1
        )
