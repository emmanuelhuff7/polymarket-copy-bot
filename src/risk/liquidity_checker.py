"""Market liquidity validation."""

import structlog
import requests
from src.config import get_settings

logger = structlog.get_logger(__name__)


class LiquidityCheckResult:
    """Result of liquidity check."""

    def __init__(self, is_liquid: bool, volume_usd: float, reason: str = ""):
        self.is_liquid = is_liquid
        self.volume_usd = volume_usd
        self.reason = reason

    def to_dict(self) -> dict:
        """Convert to dict."""
        return {
            "is_liquid": self.is_liquid,
            "volume_usd": self.volume_usd,
            "reason": self.reason,
        }


class LiquidityChecker:
    """Validates market liquidity before copying trades."""

    def __init__(self):
        self.settings = get_settings()
        self.gamma_api_base = self.settings.gamma_api_base

    def check_market_liquidity(self, market_id: str) -> LiquidityCheckResult:
        """Check if a market has sufficient liquidity.

        Args:
            market_id: market identifier (condition_id)

        Returns:
            LiquidityCheckResult with volume and pass/fail decision
        """
        try:
            # Query Gamma API for market metadata including volume
            url = f"{self.gamma_api_base}/markets/{market_id}"
            response = requests.get(url, timeout=self.settings.poll_interval_seconds)
            response.raise_for_status()

            market_data = response.json()

            # Extract 24h volume (field names may vary, try common ones)
            volume_usd = 0.0
            for volume_field in ["volume_24h", "volume24h", "dailyVolume", "volume"]:
                if volume_field in market_data:
                    try:
                        volume_usd = float(market_data[volume_field])
                        break
                    except (ValueError, TypeError):
                        continue

            # Check against threshold
            min_volume = self.settings.min_market_volume_usd
            is_liquid = volume_usd >= min_volume

            reason = f"Volume: ${volume_usd:,.0f} (min: ${min_volume:,.0f})"

            if is_liquid:
                logger.info("market_liquid", market=market_id, volume=volume_usd)
            else:
                logger.warning("market_illiquid", market=market_id, volume=volume_usd)

            return LiquidityCheckResult(is_liquid, volume_usd, reason)

        except requests.RequestException as e:
            logger.error("liquidity_check_request_failed", market=market_id, error=str(e))
            # Default to illiquid if we can't check
            return LiquidityCheckResult(
                is_liquid=False,
                volume_usd=0.0,
                reason=f"Could not verify liquidity: {str(e)}",
            )
        except Exception as e:
            logger.error("check_market_liquidity_failed", market=market_id, error=str(e))
            return LiquidityCheckResult(
                is_liquid=False,
                volume_usd=0.0,
                reason=f"Error checking liquidity: {str(e)}",
            )

    def is_liquid(self, market_id: str) -> bool:
        """Quick liquidity check (boolean only).

        Args:
            market_id: market identifier

        Returns:
            True if market is liquid enough for trading
        """
        result = self.check_market_liquidity(market_id)
        return result.is_liquid
