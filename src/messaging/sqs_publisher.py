"""SQS FIFO queue publishing for trade signals."""

import boto3
import structlog
import json
import uuid
from src.config import constants
from src.consensus.signal_aggregator import AggregatedSignal

logger = structlog.get_logger(__name__)


class BasketSignal:
    """Message sent to SQS for execution."""

    def __init__(
        self,
        signal_id: str,
        market_id: str,
        outcome_id: str,
        side: str,
        trader_count: int,
        average_price: float,
        total_size: float,
        trader_signals: list[dict],
    ):
        self.signal_id = signal_id
        self.market_id = market_id
        self.outcome_id = outcome_id
        self.side = side
        self.trader_count = trader_count
        self.average_price = average_price
        self.total_size = total_size
        self.trader_signals = trader_signals

    def to_json(self) -> str:
        """Serialize to JSON for SQS."""
        return json.dumps({
            "signal_id": self.signal_id,
            "market_id": self.market_id,
            "outcome_id": self.outcome_id,
            "side": self.side,
            "trader_count": self.trader_count,
            "average_price": self.average_price,
            "total_size": self.total_size,
            "trader_signals": self.trader_signals,
        })

    @staticmethod
    def from_json(json_str: str) -> "BasketSignal":
        """Deserialize from JSON."""
        data = json.loads(json_str)
        return BasketSignal(
            signal_id=data["signal_id"],
            market_id=data["market_id"],
            outcome_id=data["outcome_id"],
            side=data["side"],
            trader_count=data["trader_count"],
            average_price=data["average_price"],
            total_size=data["total_size"],
            trader_signals=data["trader_signals"],
        )


class SQSPublisher:
    """Publishes basket signals to SQS FIFO queue."""

    def __init__(self, queue_url: str, region: str = "us-east-1"):
        self.queue_url = queue_url
        self.sqs_client = boto3.client("sqs", region_name=region)

    def publish_signal(self, aggregated_signal: AggregatedSignal) -> bool:
        """Publish an aggregated signal to SQS.

        Args:
            aggregated_signal: AggregatedSignal to publish

        Returns:
            True if successful
        """
        try:
            # Create BasketSignal message
            signal_id = str(uuid.uuid4())
            basket_signal = BasketSignal(
                signal_id=signal_id,
                market_id=aggregated_signal.market_id,
                outcome_id=aggregated_signal.outcome_id,
                side=aggregated_signal.side,
                trader_count=aggregated_signal.trader_count,
                average_price=aggregated_signal.average_price,
                total_size=aggregated_signal.total_size,
                trader_signals=[s.to_dict() for s in aggregated_signal.signals],
            )

            # Send to SQS FIFO
            message_body = basket_signal.to_json()
            message_group_id = constants.SQS_MESSAGE_GROUP_ID

            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=message_body,
                MessageGroupId=message_group_id,
                MessageDeduplicationId=signal_id,  # FIFO deduplication
            )

            message_id = response.get("MessageId", "unknown")
            logger.info(
                "signal_published",
                signal_id=signal_id,
                market=aggregated_signal.market_id,
                traders=aggregated_signal.trader_count,
                message_id=message_id,
            )
            return True

        except Exception as e:
            logger.error("publish_signal_failed", error=str(e))
            return False

    def publish_batch(self, aggregated_signals: list[AggregatedSignal]) -> int:
        """Publish multiple signals in batch.

        Args:
            aggregated_signals: list of AggregatedSignal

        Returns:
            Number of successfully published signals
        """
        success_count = 0
        for signal in aggregated_signals:
            if self.publish_signal(signal):
                success_count += 1
        logger.info("batch_published", total=len(aggregated_signals), successful=success_count)
        return success_count
