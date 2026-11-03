"""Activity polling from Polymarket Data API."""

import structlog
import requests
from typing import Optional
from datetime import datetime
from .cursor_store import CursorStore
from .deduplicator import Deduplicator
from src.config import get_settings

logger = structlog.get_logger(__name__)


class TradeSignal:
    """Represents a single trade signal from a monitored trader."""

    def __init__(
        self,
        wallet_address: str,
        activity_id: str,
        market_id: str,
        outcome_id: str,
        side: str,
        size: float,
        price: float,
        timestamp: str,
    ):
        self.wallet_address = wallet_address
        self.activity_id = activity_id
        self.market_id = market_id
        self.outcome_id = outcome_id
        self.side = side
        self.size = size
        self.price = price
        self.timestamp = timestamp

    def to_dict(self) -> dict:
        """Convert to dict for serialization."""
        return {
            "wallet_address": self.wallet_address,
            "activity_id": self.activity_id,
            "market_id": self.market_id,
            "outcome_id": self.outcome_id,
            "side": self.side,
            "size": self.size,
            "price": self.price,
            "timestamp": self.timestamp,
        }


class ActivityPoller:
    """Polls Polymarket Data API for trader activity."""

    def __init__(self, cursor_store: CursorStore, deduplicator: Deduplicator):
        self.settings = get_settings()
        self.cursor_store = cursor_store
        self.deduplicator = deduplicator
        self.data_api_base = self.settings.data_api_base

    def poll_trader_activity(self, wallet_address: str, limit: int = 100) -> list[TradeSignal]:
        """Poll activity for a single trader since last cursor.

        Args:
            wallet_address: proxy wallet address to monitor
            limit: max activities to fetch per request

        Returns:
            List of new TradeSignal objects
        """
        try:
            # Get last cursor
            cursor = self.cursor_store.get_cursor(wallet_address)

            # Build query URL
            url = f"{self.data_api_base}/activity"
            params = {"user": wallet_address, "limit": limit}
            if cursor:
                params["after"] = cursor

            logger.debug("polling_activity", wallet=wallet_address, cursor=cursor)

            # Fetch activities
            response = requests.get(url, params=params, timeout=self.settings.poll_interval_seconds)
            response.raise_for_status()

            raw_activities = response.json()
            if not isinstance(raw_activities, list):
                logger.warning("unexpected_api_response", response_type=type(raw_activities))
                return []

            # Filter duplicates
            activities = self.deduplicator.filter_duplicates(raw_activities)

            # Convert to TradeSignal objects
            signals = []
            latest_timestamp = cursor  # fallback to existing cursor

            for activity in activities:
                signal = self._parse_activity_to_signal(wallet_address, activity)
                if signal:
                    signals.append(signal)
                    # Track latest timestamp for cursor update
                    if activity.get("timestamp"):
                        latest_timestamp = activity["timestamp"]

            # Update cursor to latest timestamp
            if latest_timestamp and signals:
                self.cursor_store.set_cursor(wallet_address, latest_timestamp)
                logger.debug(
                    "cursor_advanced",
                    wallet=wallet_address,
                    timestamp=latest_timestamp,
                    signals=len(signals),
                )

            return signals

        except requests.RequestException as e:
            logger.error("activity_poll_request_failed", wallet=wallet_address, error=str(e))
            return []
        except Exception as e:
            logger.error("poll_trader_activity_failed", wallet=wallet_address, error=str(e))
            return []

    def poll_all_traders(self, wallet_addresses: list[str]) -> list[TradeSignal]:
        """Poll activity for multiple traders.

        Args:
            wallet_addresses: list of proxy wallet addresses

        Returns:
            List of all new TradeSignal objects across all traders
        """
        all_signals = []

        for wallet in wallet_addresses:
            try:
                signals = self.poll_trader_activity(wallet)
                all_signals.extend(signals)
            except Exception as e:
                logger.error("poll_all_traders_failed_for_wallet", wallet=wallet, error=str(e))
                continue

        logger.info("poll_complete", wallets=len(wallet_addresses), total_signals=len(all_signals))
        return all_signals

    def _parse_activity_to_signal(
        self, wallet_address: str, activity: dict
    ) -> Optional[TradeSignal]:
        """Parse raw API activity into TradeSignal.

        Args:
            wallet_address: wallet being polled
            activity: raw activity dict from API

        Returns:
            TradeSignal or None if parsing fails
        """
        try:
            # Extract required fields
            activity_id = activity.get("id")
            market_id = activity.get("market")
            outcome_id = activity.get("asset_id")
            side = activity.get("side")
            size = activity.get("size")
            price = activity.get("price")
            timestamp = activity.get("timestamp")

            # Validate
            if not all([activity_id, market_id, outcome_id, side, size, price, timestamp]):
                logger.warning(
                    "activity_missing_fields",
                    wallet=wallet_address,
                    activity_id=activity_id,
                    has_market=bool(market_id),
                    has_outcome=bool(outcome_id),
                    has_side=bool(side),
                )
                return None

            signal = TradeSignal(
                wallet_address=wallet_address,
                activity_id=activity_id,
                market_id=market_id,
                outcome_id=outcome_id,
                side=side,
                size=float(size),
                price=float(price),
                timestamp=timestamp,
            )

            logger.debug("signal_parsed", wallet=wallet_address, market=market_id)
            return signal

        except (ValueError, KeyError) as e:
            logger.warning("activity_parsing_failed", wallet=wallet_address, error=str(e))
            return None
