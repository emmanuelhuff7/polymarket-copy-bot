"""Position sizing logic with proportional scaling."""

import structlog
from src.config import get_settings, constants

logger = structlog.get_logger(__name__)


class PositionSizeResult:
    """Result of position sizing calculation."""

    def __init__(self, size_usd: float, method: str, reason: str = ""):
        self.size_usd = size_usd
        self.method = method  # "proportional", "fixed", "capped"
        self.reason = reason

    def to_dict(self) -> dict:
        """Convert to dict."""
        return {
            "size_usd": self.size_usd,
            "method": self.method,
            "reason": self.reason,
        }


class PositionSizer:
    """Computes appropriate position sizes for copy trades."""

    def __init__(self):
        self.settings = get_settings()

    def compute_size(
        self,
        trader_trade_size: float,
        trader_portfolio_value: float,
    ) -> PositionSizeResult:
        """Calculate position size for a copy trade.

        Uses proportional scaling: if a trader uses 2% of their portfolio,
        we use 2% of ours. Then clamps to the configured range [$25, $30].

        Args:
            trader_trade_size: size of original trader's position (USD)
            trader_portfolio_value: original trader's total portfolio value (USD)

        Returns:
            PositionSizeResult with calculated size
        """
        try:
            # Calculate trader's position as % of portfolio
            if trader_portfolio_value <= 0:
                logger.warning("invalid_trader_portfolio", value=trader_portfolio_value)
                # Fall back to fixed size
                return PositionSizeResult(
                    size_usd=self.settings.position_size_usd,
                    method="fixed",
                    reason="trader portfolio invalid, using fixed size",
                )

            trader_ratio = trader_trade_size / trader_portfolio_value

            # Apply same ratio to our account
            proportional_size = trader_ratio * self.settings.account_capital_usd

            logger.debug(
                "proportional_size_calculated",
                trader_ratio=trader_ratio,
                proportional=proportional_size,
            )

            # Clamp to configured range
            min_size = constants.POSITION_SIZE_MIN_USD
            max_size = constants.POSITION_SIZE_MAX_USD
            clamped_size = max(min_size, min(max_size, proportional_size))

            # Determine if clamping occurred
            if clamped_size != proportional_size:
                method = "capped"
                reason = f"proportional {proportional_size:.2f} → {clamped_size:.2f}"
                logger.info("position_size_capped", proportional=proportional_size, clamped=clamped_size)
            else:
                method = "proportional"
                reason = f"trader ratio {trader_ratio:.4f}"

            return PositionSizeResult(size_usd=clamped_size, method=method, reason=reason)

        except Exception as e:
            logger.error("compute_size_failed", error=str(e))
            # Fallback to fixed size
            return PositionSizeResult(
                size_usd=self.settings.position_size_usd,
                method="fixed",
                reason=f"error in calculation: {str(e)}",
            )

    def scale_to_budget(self, size: float) -> float:
        """Scale a size to ensure it doesn't exceed available budget.

        Args:
            size: requested size in USD

        Returns:
            Adjusted size that fits within budget
        """
        # Could add check against available balance here
        return min(size, self.settings.account_capital_usd * 0.5)  # Never use more than 50%
