"""Trade activity deduplication logic."""

import structlog
from src.state import TradeStore

logger = structlog.get_logger(__name__)


class Deduplicator:
    """Prevents reprocessing the same trade activity."""

    def __init__(self, trade_store: TradeStore):
        self.trade_store = trade_store

    def is_duplicate(self, activity_id: str) -> bool:
        """Check if activity has already been seen.

        Args:
            activity_id: unique identifier for the activity

        Returns:
            True if already processed
        """
        is_seen = self.trade_store.is_seen(activity_id)
        if is_seen:
            logger.debug("duplicate_activity_detected", activity_id=activity_id)
        return is_seen

    def mark_as_seen(self, activity_id: str) -> bool:
        """Mark an activity as processed.

        Args:
            activity_id: unique identifier for the activity

        Returns:
            True if successful
        """
        success = self.trade_store.mark_seen(activity_id)
        if success:
            logger.debug("activity_marked_as_seen", activity_id=activity_id)
        return success

    def filter_duplicates(self, activities: list[dict]) -> list[dict]:
        """Filter out activities we've already seen.

        Args:
            activities: list of activity dicts (must have 'id' field)

        Returns:
            List of activities we haven't seen before
        """
        new_activities = []
        for activity in activities:
            activity_id = activity.get("id")
            if not activity_id:
                logger.warning("activity_missing_id", activity=activity)
                continue

            if not self.is_duplicate(activity_id):
                new_activities.append(activity)
                self.mark_as_seen(activity_id)
            else:
                logger.debug("skipping_duplicate", activity_id=activity_id)

        logger.debug("duplicates_filtered", total=len(activities), new=len(new_activities))
        return new_activities
