"""SQS FIFO queue consumption for Lambda handlers."""

import boto3
import structlog
from typing import Optional, Callable
from .sqs_publisher import BasketSignal

logger = structlog.get_logger(__name__)


class SQSConsumer:
    """Consumes messages from SQS FIFO queue."""

    def __init__(self, queue_url: str, region: str = "us-east-1"):
        self.queue_url = queue_url
        self.sqs_client = boto3.client("sqs", region_name=region)

    @staticmethod
    def extract_signal_from_event(event: dict) -> Optional[BasketSignal]:
        """Extract BasketSignal from Lambda SQS event.

        This is called from Lambda handler when message arrives from SQS.

        Args:
            event: Lambda SQS event (Records array)

        Returns:
            BasketSignal or None if parsing fails
        """
        try:
            records = event.get("Records", [])
            if not records:
                logger.warning("no_records_in_event")
                return None

            # Take first record (typically only one in test, batch in prod)
            record = records[0]
            message_body = record.get("body", "")

            if not message_body:
                logger.warning("empty_message_body")
                return None

            signal = BasketSignal.from_json(message_body)
            logger.info("signal_extracted", signal_id=signal.signal_id)
            return signal

        except Exception as e:
            logger.error("extract_signal_failed", error=str(e))
            return None

    def delete_message(self, receipt_handle: str) -> bool:
        """Delete a message from queue (after successful processing).

        Args:
            receipt_handle: message receipt handle from event

        Returns:
            True if successful
        """
        try:
            self.sqs_client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle,
            )
            logger.debug("message_deleted", receipt=receipt_handle)
            return True
        except Exception as e:
            logger.error("delete_message_failed", error=str(e))
            return False

    def get_receipt_handle_from_event(self, event: dict) -> Optional[str]:
        """Extract receipt handle from Lambda event for message deletion.

        Args:
            event: Lambda SQS event

        Returns:
            Receipt handle or None
        """
        try:
            records = event.get("Records", [])
            if records:
                return records[0].get("receiptHandle")
            return None
        except Exception as e:
            logger.error("get_receipt_handle_failed", error=str(e))
            return None
