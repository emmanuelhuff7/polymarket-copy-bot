"""SNS notifications for alerts and summaries."""

import boto3
import structlog
from enum import Enum
from datetime import datetime

logger = structlog.get_logger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class SNSNotifier:
    """Sends alerts and notifications via SNS."""

    def __init__(self, topic_arn: str, region: str = "us-east-1"):
        self.topic_arn = topic_arn
        self.sns_client = boto3.client("sns", region_name=region)

    def send_alert(
        self,
        subject: str,
        message: str,
        severity: AlertSeverity = AlertSeverity.INFO,
    ) -> bool:
        """Send an alert message via SNS.

        Args:
            subject: email subject / alert title
            message: alert message body
            severity: alert severity level

        Returns:
            True if sent successfully
        """
        try:
            # Prefix subject with severity
            full_subject = f"[{severity.value}] {subject}"

            self.sns_client.publish(
                TopicArn=self.topic_arn,
                Subject=full_subject,
                Message=message,
            )

            logger.info("alert_sent", severity=severity.value, subject=subject)
            return True

        except Exception as e:
            logger.error("send_alert_failed", error=str(e))
            return False

    def send_trade_executed(
        self,
        market_id: str,
        side: str,
        size_usd: float,
        order_id: str,
        traders_count: int,
    ) -> bool:
        """Send notification when trade is executed.

        Args:
            market_id: market traded
            side: BUY or SELL
            size_usd: position size
            order_id: order identifier
            traders_count: number of traders in consensus

        Returns:
            True if sent
        """
        subject = f"Trade Executed: {side} {market_id}"
        message = f"""
Trade Executed Successfully

Market: {market_id}
Side: {side}
Size: ${size_usd:.2f}
Order ID: {order_id}
Consensus: {traders_count} traders

Timestamp: {datetime.utcnow().isoformat()}
"""
        return self.send_alert(subject, message, AlertSeverity.INFO)

    def send_trade_failed(self, market_id: str, reason: str, order_id: str = "") -> bool:
        """Send notification when trade execution fails.

        Args:
            market_id: market that failed
            reason: reason for failure
            order_id: order ID if applicable

        Returns:
            True if sent
        """
        subject = f"Trade Failed: {market_id}"
        message = f"""
Trade Execution Failed

Market: {market_id}
Order ID: {order_id}
Reason: {reason}

Timestamp: {datetime.utcnow().isoformat()}

Please investigate and potentially restart the monitor.
"""
        return self.send_alert(subject, message, AlertSeverity.ERROR)

    def send_daily_summary(
        self,
        date: str,
        trade_count: int,
        realized_pnl: float,
        open_positions: int,
    ) -> bool:
        """Send daily summary report.

        Args:
            date: date of summary (YYYY-MM-DD)
            trade_count: number of trades executed
            realized_pnl: realized P&L in USD
            open_positions: number of currently open positions

        Returns:
            True if sent
        """
        subject = f"Daily Summary: {date}"
        pnl_status = "✓ PROFIT" if realized_pnl >= 0 else "✗ LOSS"
        message = f"""
Daily Trading Summary

Date: {date}
Trades Executed: {trade_count}
Realized P&L: ${realized_pnl:+.2f} {pnl_status}
Open Positions: {open_positions}

All systems operating normally.
"""
        return self.send_alert(subject, message, AlertSeverity.INFO)

    def send_daily_loss_limit_breached(self, loss_amount: float, limit: float) -> bool:
        """Send alert when daily loss limit is breached.

        Args:
            loss_amount: actual loss in USD
            limit: daily loss limit in USD

        Returns:
            True if sent
        """
        subject = "ALERT: Daily Loss Limit Breached"
        message = f"""
Daily Loss Limit Breached - Trading Halted

Loss: ${abs(loss_amount):.2f}
Limit: ${limit:.2f}
Remaining: ${limit - abs(loss_amount):.2f}

The bot will NOT execute any more trades until tomorrow.
Please review positions and investigate.
"""
        return self.send_alert(subject, message, AlertSeverity.CRITICAL)

    def send_health_check(self, status: str, last_sync: str = "") -> bool:
        """Send health check confirmation.

        Args:
            status: "healthy" or error description
            last_sync: timestamp of last successful sync

        Returns:
            True if sent
        """
        subject = f"Health Check: {status}"
        message = f"""
Health Status Report

Status: {status}
Last Sync: {last_sync}
Timestamp: {datetime.utcnow().isoformat()}

Monitor is running and operational.
"""
        return self.send_alert(subject, message, AlertSeverity.INFO)
