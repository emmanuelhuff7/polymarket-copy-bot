"""Tracked trader list management."""

import structlog
from datetime import datetime
from typing import Optional
from .dynamo_client import DynamoClient

logger = structlog.get_logger(__name__)


class TraderStore:
    """Manages the list of tracked top traders."""

    def __init__(self, dynamo: DynamoClient):
        self.dynamo = dynamo
        self.table = "{prefix}-tracked-traders"

    def add_trader(
        self,
        wallet_address: str,
        rank: int,
        score: float,
        username: Optional[str] = None,
        is_active: bool = True,
    ) -> bool:
        """Add or update a tracked trader."""
        try:
            item = {
                "wallet_address": wallet_address,
                "rank": rank,
                "score": DynamoClient.to_decimal(score),
                "username": username or wallet_address,
                "is_active": is_active,
                "last_updated": datetime.utcnow().isoformat(),
            }
            self.dynamo.put_item(self.table, item)
            logger.info("trader_added", wallet=wallet_address, rank=rank, score=score)
            return True
        except Exception as e:
            logger.error("add_trader_failed", wallet=wallet_address, error=str(e))
            return False

    def get_tracked_traders(self) -> list[dict]:
        """Get all currently tracked traders."""
        try:
            traders = self.dynamo.scan(self.table, limit=100)
            active_traders = [t for t in traders if t.get("is_active", True)]
            logger.debug("get_tracked_traders", count=len(active_traders))
            return sorted(active_traders, key=lambda x: x.get("rank", 999))
        except Exception as e:
            logger.error("get_tracked_traders_failed", error=str(e))
            return []

    def get_trader(self, wallet_address: str) -> Optional[dict]:
        """Get a specific trader by wallet address."""
        try:
            item = self.dynamo.get_item(self.table, {"wallet_address": wallet_address})
            if item:
                logger.debug("get_trader", wallet=wallet_address)
            return item
        except Exception as e:
            logger.error("get_trader_failed", wallet=wallet_address, error=str(e))
            return None

    def update_traders(self, traders: list[dict]) -> bool:
        """Bulk update the trader list (typically from leaderboard refresh)."""
        try:
            # First, deactivate all existing traders
            existing = self.get_tracked_traders()
            for trader in existing:
                try:
                    self.dynamo.update_item(
                        self.table,
                        {"wallet_address": trader["wallet_address"]},
                        "SET is_active = :active",
                        {":active": False},
                    )
                except Exception as e:
                    logger.warning("failed_to_deactivate_trader", wallet=trader.get("wallet_address"), error=str(e))

            # Then, add new traders
            for idx, trader in enumerate(traders, 1):
                self.add_trader(
                    wallet_address=trader["wallet_address"],
                    rank=idx,
                    score=trader.get("score", 0.0),
                    username=trader.get("username"),
                    is_active=True,
                )

            logger.info("traders_updated", count=len(traders))
            return True
        except Exception as e:
            logger.error("update_traders_failed", error=str(e))
            return False

    def deactivate_trader(self, wallet_address: str) -> bool:
        """Deactivate a trader (remove from tracking)."""
        try:
            self.dynamo.update_item(
                self.table,
                {"wallet_address": wallet_address},
                "SET is_active = :active",
                {":active": False},
            )
            logger.info("trader_deactivated", wallet=wallet_address)
            return True
        except Exception as e:
            logger.error("deactivate_trader_failed", wallet=wallet_address, error=str(e))
            return False
