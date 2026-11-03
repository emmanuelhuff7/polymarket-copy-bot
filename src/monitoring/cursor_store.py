"""Polling cursor persistence for activity tracking."""

import structlog
from datetime import datetime
from typing import Optional
from src.state import DynamoClient

logger = structlog.get_logger(__name__)


class CursorStore:
    """Manages polling cursors to track where we left off per trader."""

    def __init__(self, dynamo: DynamoClient):
        self.dynamo = dynamo
        self.table = "{prefix}-polling-cursors"

    def get_cursor(self, wallet_address: str) -> Optional[str]:
        """Get the last-seen activity timestamp for a wallet.

        Args:
            wallet_address: proxy wallet address

        Returns:
            ISO timestamp string or None if no prior cursor
        """
        try:
            item = self.dynamo.get_item(self.table, {"wallet_address": wallet_address})
            if item:
                cursor = item.get("last_activity_timestamp")
                logger.debug("cursor_retrieved", wallet=wallet_address, cursor=cursor)
                return cursor
            return None
        except Exception as e:
            logger.error("get_cursor_failed", wallet=wallet_address, error=str(e))
            return None

    def set_cursor(self, wallet_address: str, timestamp: str) -> bool:
        """Update the cursor for a wallet.

        Args:
            wallet_address: proxy wallet address
            timestamp: ISO timestamp to save as cursor

        Returns:
            True if successful
        """
        try:
            item = {
                "wallet_address": wallet_address,
                "last_activity_timestamp": timestamp,
                "last_poll_time": datetime.utcnow().isoformat(),
            }
            self.dynamo.put_item(self.table, item)
            logger.debug("cursor_updated", wallet=wallet_address, timestamp=timestamp)
            return True
        except Exception as e:
            logger.error("set_cursor_failed", wallet=wallet_address, error=str(e))
            return False

    def initialize_cursor(self, wallet_address: str) -> bool:
        """Initialize a cursor for a new trader (set to current time).

        Args:
            wallet_address: proxy wallet address

        Returns:
            True if successful
        """
        try:
            now = datetime.utcnow().isoformat()
            return self.set_cursor(wallet_address, now)
        except Exception as e:
            logger.error("initialize_cursor_failed", wallet=wallet_address, error=str(e))
            return False

    def reset_cursor(self, wallet_address: str) -> bool:
        """Reset cursor to fetch all historical trades (for backfill/recovery).

        Args:
            wallet_address: proxy wallet address

        Returns:
            True if successful
        """
        try:
            # Set to epoch/very old time
            return self.set_cursor(wallet_address, "1970-01-01T00:00:00")
        except Exception as e:
            logger.error("reset_cursor_failed", wallet=wallet_address, error=str(e))
            return False
