"""Portfolio-level risk guards and limits."""

import structlog
from datetime import datetime, date
from src.config import get_settings
from src.state import PositionStore, TradeStore

logger = structlog.get_logger(__name__)


class RiskDecision:
    """Result of risk check."""

    def __init__(self, should_execute: bool, reason: str, breach_type: str = ""):
        self.should_execute = should_execute
        self.reason = reason
        self.breach_type = breach_type  # "daily_loss", "max_positions", "duplicate", "ok"

    def to_dict(self) -> dict:
        """Convert to dict."""
        return {
            "should_execute": self.should_execute,
            "reason": self.reason,
            "breach_type": self.breach_type,
        }


class PortfolioGuard:
    """Guards against dangerous portfolio-level risks."""

    def __init__(self, position_store: PositionStore, trade_store: TradeStore):
        self.settings = get_settings()
        self.position_store = position_store
        self.trade_store = trade_store

    def check(
        self,
        market_id: str,
        is_duplicate: bool = False,
    ) -> RiskDecision:
        """Comprehensive risk check before trade execution.

        Args:
            market_id: market being traded
            is_duplicate: whether this trade was already executed

        Returns:
            RiskDecision with pass/fail and reason
        """
        # Check for duplicate
        if is_duplicate:
            reason = "Trade already executed (duplicate signal)"
            logger.warning("risk_check_duplicate", market=market_id)
            return RiskDecision(False, reason, "duplicate")

        # Check daily loss limit
        if self.is_daily_loss_limit_breached():
            reason = f"Daily loss limit (${self.settings.daily_loss_limit_usd}) breached"
            logger.error("risk_check_daily_loss_breached")
            return RiskDecision(False, reason, "daily_loss")

        # Check max open positions
        open_count = self.count_open_positions()
        if open_count >= self.settings.max_open_positions:
            reason = f"Max open positions ({self.settings.max_open_positions}) reached (current: {open_count})"
            logger.warning("risk_check_max_positions", count=open_count)
            return RiskDecision(False, reason, "max_positions")

        # All checks passed
        reason = "Risk checks passed"
        logger.debug("risk_checks_passed", market=market_id)
        return RiskDecision(True, reason, "ok")

    def is_daily_loss_limit_breached(self) -> bool:
        """Check if today's P&L has exceeded the loss limit.

        Returns:
            True if daily loss limit is breached
        """
        try:
            today = date.today().isoformat()
            daily_pnl_item = self.position_store.get_daily_pnl(today)

            if not daily_pnl_item:
                # No trades today yet
                return False

            realized_pnl = float(daily_pnl_item.get("realized_pnl", 0))

            # If realized loss > loss limit, breach
            if realized_pnl < -self.settings.daily_loss_limit_usd:
                logger.error(
                    "daily_loss_breached",
                    loss=realized_pnl,
                    limit=-self.settings.daily_loss_limit_usd,
                )
                return True

            return False

        except Exception as e:
            logger.error("daily_loss_check_failed", error=str(e))
            # Conservative: return True (block trade) on error
            return True

    def count_open_positions(self) -> int:
        """Count currently open positions.

        Returns:
            Number of open positions
        """
        try:
            count = self.position_store.count_open_positions()
            logger.debug("open_positions_counted", count=count)
            return count
        except Exception as e:
            logger.error("count_open_positions_failed", error=str(e))
            return self.settings.max_open_positions  # Conservative: assume full

    def record_daily_loss(self, loss_amount: float) -> bool:
        """Record a loss for today's P&L.

        Args:
            loss_amount: loss amount (negative value)

        Returns:
            True if recorded
        """
        try:
            today = date.today().isoformat()
            current = self.position_store.get_daily_pnl(today)

            if current:
                existing_loss = float(current.get("realized_pnl", 0))
                new_loss = existing_loss + loss_amount
            else:
                new_loss = loss_amount

            self.position_store.record_daily_pnl(new_loss, 0)
            logger.info("daily_loss_recorded", date=today, loss=new_loss)
            return True
        except Exception as e:
            logger.error("record_daily_loss_failed", error=str(e))
            return False

    def can_trade_market(self, market_id: str) -> bool:
        """Quick check if market can be traded (not already max positions).

        Args:
            market_id: market identifier

        Returns:
            True if safe to trade
        """
        decision = self.check(market_id)
        return decision.should_execute
