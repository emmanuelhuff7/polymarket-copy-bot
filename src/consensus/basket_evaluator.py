"""Basket consensus evaluation logic."""

import structlog
from enum import Enum
from typing import Optional
from .signal_aggregator import AggregatedSignal
from src.config import get_settings

logger = structlog.get_logger(__name__)


class ConsensusDecision(Enum):
    """Consensus evaluation result."""

    EXECUTE = "EXECUTE"  # Consensus met, should execute
    WAIT = "WAIT"  # Not enough signals yet, keep waiting
    SKIP = "SKIP"  # Should not execute (insufficient confidence, market skip-listed, etc)


class ConsensusResult:
    """Result of consensus evaluation."""

    def __init__(
        self,
        decision: ConsensusDecision,
        reason: str,
        aggregated_signal: Optional[AggregatedSignal] = None,
    ):
        self.decision = decision
        self.reason = reason
        self.aggregated_signal = aggregated_signal

    def to_dict(self) -> dict:
        """Convert to dict."""
        return {
            "decision": self.decision.value,
            "reason": self.reason,
            "signal": self.aggregated_signal.to_dict() if self.aggregated_signal else None,
        }


class BasketEvaluator:
    """Evaluates if basket consensus is met for copy trading."""

    def __init__(self):
        self.settings = get_settings()
        self.skip_market_ids = self.settings.skip_market_ids

    def evaluate(self, aggregated_signal: AggregatedSignal) -> ConsensusResult:
        """Evaluate if a signal meets consensus threshold for execution.

        Args:
            aggregated_signal: AggregatedSignal to evaluate

        Returns:
            ConsensusResult with decision and reason
        """
        # Check if market should be skipped
        if self.should_skip_market(aggregated_signal.market_id):
            reason = f"Market {aggregated_signal.market_id} is in skip list"
            logger.info("consensus_skip_market", market=aggregated_signal.market_id)
            return ConsensusResult(ConsensusDecision.SKIP, reason, aggregated_signal)

        # Check if consensus threshold is met
        trader_count = aggregated_signal.trader_count
        threshold = self.settings.consensus_threshold

        if trader_count >= threshold:
            reason = f"{trader_count} traders agreed (threshold: {threshold})"
            logger.info(
                "consensus_met",
                market=aggregated_signal.market_id,
                traders=trader_count,
                threshold=threshold,
            )
            return ConsensusResult(
                ConsensusDecision.EXECUTE, reason, aggregated_signal
            )
        else:
            reason = f"{trader_count} traders (need {threshold})"
            logger.debug(
                "consensus_not_met",
                market=aggregated_signal.market_id,
                traders=trader_count,
                threshold=threshold,
            )
            return ConsensusResult(ConsensusDecision.WAIT, reason, aggregated_signal)

    def should_skip_market(self, market_id: str) -> bool:
        """Check if a market should never be traded.

        Args:
            market_id: market identifier

        Returns:
            True if market is in skip list
        """
        is_skipped = market_id in self.skip_market_ids
        if is_skipped:
            logger.debug("market_skipped", market=market_id)
        return is_skipped

    def evaluate_batch(self, signals: list[AggregatedSignal]) -> tuple[list[ConsensusResult], list[ConsensusResult]]:
        """Evaluate multiple signals, separating executable from wait/skip.

        Args:
            signals: list of AggregatedSignal

        Returns:
            Tuple of (executable_results, non_executable_results)
        """
        executable = []
        non_executable = []

        for signal in signals:
            result = self.evaluate(signal)
            if result.decision == ConsensusDecision.EXECUTE:
                executable.append(result)
            else:
                non_executable.append(result)

        logger.info(
            "evaluate_batch_complete",
            total=len(signals),
            executable=len(executable),
            skipped=len(non_executable),
        )
        return executable, non_executable
