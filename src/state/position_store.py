"""Current position and P&L tracking store."""

import structlog
from datetime import datetime
from typing import Optional
from .dynamo_client import DynamoClient

logger = structlog.get_logger(__name__)


class PositionStore:
    """Manages current open positions and P&L tracking."""

    def __init__(self, dynamo: DynamoClient):
        self.dynamo = dynamo
        self.positions_table = "{prefix}-open-positions"
        self.daily_pnl_table = "{prefix}-daily-pnl"

    def add_position(
        self,
        market_id: str,
        outcome_id: str,
        side: str,
        size_usd: float,
        entry_price: float,
        basket_signal_id: str,
    ) -> bool:
        """Record a new open position."""
        try:
            item = {
                "market_id": market_id,
                "outcome_id": outcome_id,
                "side": side,
                "size_usd": DynamoClient.to_decimal(size_usd),
                "entry_price": DynamoClient.to_decimal(entry_price),
                "opened_at": datetime.utcnow().isoformat(),
                "basket_signal_id": basket_signal_id,
                "status": "OPEN",
            }
            self.dynamo.put_item(self.positions_table, item)
            logger.info("position_opened", market_id=market_id, size_usd=size_usd)
            return True
        except Exception as e:
            logger.error("add_position_failed", market_id=market_id, error=str(e))
            return False

    def get_open_positions(self) -> list[dict]:
        """Get all currently open positions."""
        try:
            positions = self.dynamo.scan(self.positions_table, limit=1000)
            logger.debug("get_open_positions", count=len(positions))
            return positions
        except Exception as e:
            logger.error("get_open_positions_failed", error=str(e))
            return []

    def count_open_positions(self) -> int:
        """Count the number of open positions."""
        positions = self.get_open_positions()
        count = sum(1 for p in positions if p.get("status") == "OPEN")
        logger.debug("open_position_count", count=count)
        return count

    def close_position(self, market_id: str, exit_price: float, pnl: float) -> bool:
        """Close a position and record exit price/P&L."""
        try:
            self.dynamo.update_item(
                self.positions_table,
                {"market_id": market_id},
                "SET exit_price = :ep, pnl = :pnl, #status = :st, closed_at = :ca",
                {
                    ":ep": DynamoClient.to_decimal(exit_price),
                    ":pnl": DynamoClient.to_decimal(pnl),
                    ":st": "CLOSED",
                    ":ca": datetime.utcnow().isoformat(),
                },
            )
            logger.info("position_closed", market_id=market_id, pnl=pnl)
            return True
        except Exception as e:
            logger.error("close_position_failed", market_id=market_id, error=str(e))
            return False

    def record_daily_pnl(self, realized_pnl: float, trade_count: int) -> bool:
        """Record daily P&L summary."""
        try:
            today = datetime.utcnow().date().isoformat()
            item = {
                "date": today,
                "realized_pnl": DynamoClient.to_decimal(realized_pnl),
                "trade_count": trade_count,
                "last_updated": datetime.utcnow().isoformat(),
            }
            self.dynamo.put_item(self.daily_pnl_table, item)
            logger.info("daily_pnl_recorded", date=today, pnl=realized_pnl, trades=trade_count)
            return True
        except Exception as e:
            logger.error("record_daily_pnl_failed", error=str(e))
            return False

    def get_daily_pnl(self, date: str) -> Optional[dict]:
        """Get daily P&L for a specific date."""
        try:
            item = self.dynamo.get_item(self.daily_pnl_table, {"date": date})
            return item
        except Exception as e:
            logger.error("get_daily_pnl_failed", date=date, error=str(e))
            return None

    def get_total_realized_pnl(self, days: int = 30) -> float:
        """Get total realized P&L for the last N days."""
        try:
            # In production, would scan and sum daily_pnl entries
            all_pnls = self.dynamo.scan(self.daily_pnl_table, limit=days)
            total = sum(DynamoClient.from_decimal(p.get("realized_pnl", 0)) for p in all_pnls)
            logger.debug("total_realized_pnl", days=days, total=total)
            return total
        except Exception as e:
            logger.error("get_total_realized_pnl_failed", error=str(e))
            return 0.0
