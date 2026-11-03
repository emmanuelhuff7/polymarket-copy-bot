"""In-memory signal aggregation with time-based windowing."""

import structlog
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from src.monitoring.activity_poller import TradeSignal
from src.config import get_settings

logger = structlog.get_logger(__name__)


class AggregatedSignal:
    """Represents aggregated signals for a specific market+side+outcome."""

    def __init__(self, market_id: str, outcome_id: str, side: str):
        self.market_id = market_id
        self.outcome_id = outcome_id
        self.side = side
        self.signals: List[TradeSignal] = []
        self.first_seen_at = None
        self.last_updated_at = None

    def add_signal(self, signal: TradeSignal) -> None:
        """Add a signal to this aggregation."""
        self.signals.append(signal)
        now = datetime.utcnow()
        if not self.first_seen_at:
            self.first_seen_at = now
        self.last_updated_at = now

    @property
    def trader_count(self) -> int:
        """Number of unique traders contributing to this signal."""
        return len(set(s.wallet_address for s in self.signals))

    @property
    def average_price(self) -> float:
        """Average price across all signals."""
        if not self.signals:
            return 0.0
        return sum(s.price for s in self.signals) / len(self.signals)

    @property
    def total_size(self) -> float:
        """Total aggregate size."""
        return sum(s.size for s in self.signals)

    def is_stale(self, window_seconds: int) -> bool:
        """Check if signal is older than the window."""
        if not self.last_updated_at:
            return True
        age = datetime.utcnow() - self.last_updated_at
        return age.total_seconds() > window_seconds

    def to_dict(self) -> dict:
        """Convert to dict for serialization."""
        return {
            "market_id": self.market_id,
            "outcome_id": self.outcome_id,
            "side": self.side,
            "trader_count": self.trader_count,
            "average_price": self.average_price,
            "total_size": self.total_size,
            "signals": [s.to_dict() for s in self.signals],
            "first_seen_at": self.first_seen_at.isoformat() if self.first_seen_at else None,
        }


class SignalAggregator:
    """Maintains in-memory window of trade signals for consensus evaluation."""

    def __init__(self):
        self.settings = get_settings()
        # Key: (market_id, outcome_id, side), Value: AggregatedSignal
        self.signals: Dict[Tuple[str, str, str], AggregatedSignal] = defaultdict(
            lambda: None
        )

    def ingest_signals(self, signals: List[TradeSignal]) -> None:
        """Add new signals to aggregation.

        Args:
            signals: list of TradeSignal objects
        """
        for signal in signals:
            key = (signal.market_id, signal.outcome_id, signal.side)

            # Create aggregation if doesn't exist
            if key not in self.signals or self.signals[key] is None:
                self.signals[key] = AggregatedSignal(
                    market_id=signal.market_id,
                    outcome_id=signal.outcome_id,
                    side=signal.side,
                )

            self.signals[key].add_signal(signal)
            logger.debug(
                "signal_ingested",
                market=signal.market_id,
                outcome=signal.outcome_id,
                side=signal.side,
                traders=self.signals[key].trader_count,
            )

    def get_pending_signals(self) -> List[AggregatedSignal]:
        """Get all non-stale aggregated signals.

        Returns:
            List of AggregatedSignal with signals still in the window
        """
        pending = []
        stale_keys = []

        for key, aggregated in self.signals.items():
            if aggregated is None:
                continue

            if aggregated.is_stale(self.settings.signal_window_seconds):
                stale_keys.append(key)
                logger.debug("signal_expired", market=aggregated.market_id)
            else:
                pending.append(aggregated)

        # Clean up stale signals
        for key in stale_keys:
            del self.signals[key]

        logger.debug("pending_signals", count=len(pending))
        return pending

    def clear_signal(self, market_id: str, outcome_id: str, side: str) -> None:
        """Remove a specific aggregated signal (after execution).

        Args:
            market_id: market identifier
            outcome_id: outcome identifier
            side: BUY or SELL
        """
        key = (market_id, outcome_id, side)
        if key in self.signals:
            del self.signals[key]
            logger.debug("signal_cleared", market=market_id)

    def get_signal_count(self) -> int:
        """Get total number of pending signals."""
        return len([s for s in self.signals.values() if s is not None])

    def get_trader_exposure(self, wallet_address: str) -> Dict[str, int]:
        """Get markets this trader is active in (aggregated view).

        Args:
            wallet_address: wallet to look up

        Returns:
            Dict mapping market_id to count of signals
        """
        exposure = defaultdict(int)
        for aggregated in self.signals.values():
            if aggregated is None:
                continue
            for signal in aggregated.signals:
                if signal.wallet_address == wallet_address:
                    exposure[aggregated.market_id] += 1
        return dict(exposure)
