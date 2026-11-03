"""Fetch top traders from Polymarket leaderboard API."""

import structlog
import requests
from typing import Optional
from src.config import get_settings

logger = structlog.get_logger(__name__)


class LeaderboardTrader:
    """Represents a trader on the leaderboard."""

    def __init__(
        self,
        rank: int,
        proxy_wallet: str,
        user_name: str,
        pnl: float,
        volume: float,
    ):
        self.rank = rank
        self.proxy_wallet = proxy_wallet
        self.user_name = user_name
        self.pnl = pnl
        self.volume = volume

    def to_dict(self) -> dict:
        """Convert to dict for storage."""
        return {
            "wallet_address": self.proxy_wallet,
            "rank": self.rank,
            "score": self.pnl,  # Use PnL as score
            "username": self.user_name,
            "pnl": self.pnl,
            "volume": self.volume,
        }

    def __repr__(self):
        return f"LeaderboardTrader(rank={self.rank}, wallet={self.proxy_wallet[:10]}..., pnl=${self.pnl:,.0f})"


class LeaderboardFetcher:
    """Fetches top traders from Polymarket leaderboard API."""

    def __init__(self):
        self.settings = get_settings()
        self.data_api_base = self.settings.data_api_base

    def fetch_top_traders(
        self,
        time_period: str = "MONTH",  # DAY, WEEK, MONTH, ALL
        order_by: str = "PNL",  # PNL, VOL
        limit: int = 100,  # Get more than we need to filter for active traders
        category: str = "OVERALL",  # OVERALL, POLITICS, SPORTS, CRYPTO, etc.
    ) -> list[LeaderboardTrader]:
        """Fetch top traders from the leaderboard API.

        Args:
            time_period: DAY, WEEK, MONTH, or ALL
            order_by: PNL (profit) or VOL (volume)
            limit: max traders to fetch
            category: market category to filter by

        Returns:
            List of LeaderboardTrader objects
        """
        try:
            url = f"{self.data_api_base}/v1/leaderboard"
            params = {
                "timePeriod": time_period,
                "orderBy": order_by,
                "limit": limit,
                "category": category,
            }

            logger.info(
                "fetching_leaderboard",
                time_period=time_period,
                order_by=order_by,
                limit=limit,
            )

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Handle both list and dict responses
            if isinstance(data, dict):
                traders_data = data.get("data", []) or data.get("traders", []) or []
            else:
                traders_data = data

            if not isinstance(traders_data, list):
                logger.warning("unexpected_response_format", data_type=type(traders_data))
                return []

            traders = []
            for item in traders_data:
                try:
                    trader = self._parse_trader(item)
                    if trader:
                        traders.append(trader)
                except Exception as e:
                    logger.warning("failed_to_parse_trader", error=str(e), item=item)
                    continue

            logger.info("leaderboard_fetched", count=len(traders))
            return traders

        except requests.RequestException as e:
            logger.error("leaderboard_fetch_failed", error=str(e))
            return []
        except Exception as e:
            logger.error("fetch_top_traders_error", error=str(e))
            return []

    def _parse_trader(self, item: dict) -> Optional[LeaderboardTrader]:
        """Parse a trader item from API response.

        Args:
            item: trader dict from API

        Returns:
            LeaderboardTrader or None
        """
        try:
            # Extract fields (case-insensitive since API might vary)
            proxy_wallet = None
            for key in ["proxyWallet", "proxy_wallet", "wallet", "address"]:
                if key in item:
                    proxy_wallet = item[key]
                    break

            if not proxy_wallet:
                logger.debug("trader_missing_wallet", item=item)
                return None

            # Validate wallet format
            if not isinstance(proxy_wallet, str) or not proxy_wallet.startswith("0x"):
                logger.debug("invalid_wallet_format", wallet=proxy_wallet)
                return None

            rank = int(item.get("rank", 0)) if isinstance(item.get("rank"), (int, str)) else 0
            user_name = item.get("userName", item.get("user_name", proxy_wallet[:10]))
            pnl = float(item.get("pnl", 0))
            volume = float(item.get("vol", item.get("volume", 0)))

            trader = LeaderboardTrader(
                rank=rank,
                proxy_wallet=proxy_wallet,
                user_name=user_name,
                pnl=pnl,
                volume=volume,
            )

            logger.debug("trader_parsed", trader=trader)
            return trader

        except (ValueError, KeyError, TypeError) as e:
            logger.warning("trader_parse_error", error=str(e))
            return None

    def get_top_n_traders(
        self,
        n: int = 5,
        time_period: str = "MONTH",
        order_by: str = "PNL",
    ) -> list[LeaderboardTrader]:
        """Get top N traders conveniently.

        Args:
            n: number of top traders to return
            time_period: DAY, WEEK, MONTH, or ALL
            order_by: PNL or VOL

        Returns:
            List of top N traders
        """
        traders = self.fetch_top_traders(
            time_period=time_period,
            order_by=order_by,
            limit=max(n * 2, 50),  # Fetch extra in case some are filtered out
        )

        # Filter: only return traders with positive PnL
        profitable_traders = [t for t in traders if t.pnl > 0]

        result = profitable_traders[:n]
        logger.info(
            "top_traders_selected",
            count=len(result),
            requested=n,
            profitable=len(profitable_traders),
        )

        return result
