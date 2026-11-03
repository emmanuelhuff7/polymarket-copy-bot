"""Trade history and deduplication store."""

import structlog
from datetime import datetime
from typing import Optional
from .dynamo_client import DynamoClient

logger = structlog.get_logger(__name__)


class TradeStore:
    """Manages seen trades, copied trades, and trade history."""

    def __init__(self, dynamo: DynamoClient):
        self.dynamo = dynamo
        self.seen_trades_table = "{prefix}-seen-trades"
        self.copied_trades_table = "{prefix}-copied-trades"

    def mark_seen(self, activity_id: str) -> bool:
        """Mark a trade activity as seen (for deduplication)."""
        try:
            self.dynamo.put_item(
                self.seen_trades_table,
                {"activity_id": activity_id, "seen_at": datetime.utcnow().isoformat()},
                ttl_hours=720,  # 30 days TTL
            )
            return True
        except Exception as e:
            logger.error("mark_seen_failed", activity_id=activity_id, error=str(e))
            return False

    def is_seen(self, activity_id: str) -> bool:
        """Check if a trade activity has been seen before."""
        try:
            item = self.dynamo.get_item(self.seen_trades_table, {"activity_id": activity_id})
            return item is not None
        except Exception as e:
            logger.error("is_seen_failed", activity_id=activity_id, error=str(e))
            return False

    def record_copied_trade(
        self,
        basket_signal_id: str,
        market_id: str,
        side: str,
        size_usd: float,
        order_id: str,
        fill_price: Optional[float] = None,
        pnl: Optional[float] = None,
        status: str = "PENDING",
    ) -> bool:
        """Record a copied trade in history."""
        try:
            timestamp = datetime.utcnow().isoformat()
            item = {
                "basket_signal_id": basket_signal_id,
                "timestamp": timestamp,
                "market_id": market_id,
                "side": side,
                "size_usd": DynamoClient.to_decimal(size_usd),
                "order_id": order_id,
                "fill_price": DynamoClient.to_decimal(fill_price) if fill_price else None,
                "pnl": DynamoClient.to_decimal(pnl) if pnl else None,
                "status": status,
                "created_at": timestamp,
            }
            self.dynamo.put_item(self.copied_trades_table, item)
            logger.info("trade_recorded", basket_signal_id=basket_signal_id, order_id=order_id)
            return True
        except Exception as e:
            logger.error("record_copied_trade_failed", basket_signal_id=basket_signal_id, error=str(e))
            return False

    def get_copied_trades(self, since_hours: int = 24) -> list[dict]:
        """Get recent copied trades."""
        try:
            # Scan all copied trades (in production, could filter by date)
            trades = self.dynamo.scan(self.copied_trades_table, limit=1000)
            logger.debug("get_copied_trades", count=len(trades))
            return trades
        except Exception as e:
            logger.error("get_copied_trades_failed", error=str(e))
            return []

    def update_trade_fill(
        self,
        basket_signal_id: str,
        timestamp: str,
        fill_price: float,
        pnl: float,
        status: str = "FILLED",
    ) -> bool:
        """Update a trade with fill information."""
        try:
            self.dynamo.update_item(
                self.copied_trades_table,
                {"basket_signal_id": basket_signal_id, "timestamp": timestamp},
                "SET fill_price = :fp, pnl = :pnl, #status = :st",
                {
                    ":fp": DynamoClient.to_decimal(fill_price),
                    ":pnl": DynamoClient.to_decimal(pnl),
                    ":st": status,
                },
            )
            logger.info("trade_fill_updated", basket_signal_id=basket_signal_id, status=status)
            return True
        except Exception as e:
            logger.error("update_trade_fill_failed", basket_signal_id=basket_signal_id, error=str(e))
            return False
