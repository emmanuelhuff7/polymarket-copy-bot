"""Trade execution via Polymarket CLOB API."""

import structlog
import time
from typing import Optional
from py_clob_client.client import ClobClient
from py_clob_client.order_builder.constants import OrderType

logger = structlog.get_logger(__name__)


class OrderResult:
    """Result of order execution."""

    def __init__(
        self,
        success: bool,
        order_id: Optional[str] = None,
        fill_price: Optional[float] = None,
        fill_size: Optional[float] = None,
        error: str = "",
    ):
        self.success = success
        self.order_id = order_id
        self.fill_price = fill_price
        self.fill_size = fill_size
        self.error = error

    def to_dict(self) -> dict:
        """Convert to dict."""
        return {
            "success": self.success,
            "order_id": self.order_id,
            "fill_price": self.fill_price,
            "fill_size": self.fill_size,
            "error": self.error,
        }


class OrderExecutor:
    """Executes orders on Polymarket CLOB API."""

    def __init__(self, clob_client: ClobClient, max_retries: int = 3):
        self.client = clob_client
        self.max_retries = max_retries

    def execute_market_order(
        self,
        token_id: str,
        side: str,  # "BUY" or "SELL"
        amount: float,  # Amount in USDC
    ) -> OrderResult:
        """Execute a market order.

        Args:
            token_id: outcome token ID
            side: BUY or SELL
            amount: order amount in USDC

        Returns:
            OrderResult with success/failure info
        """
        try:
            logger.info("executing_market_order", token=token_id, side=side, amount=amount)

            # Create market order
            order = self.client.create_market_order(
                token_id=token_id,
                amount=amount,
                side=side,
                order_type=OrderType.FOK,  # Fill or Kill
            )

            if not order:
                return OrderResult(False, error="Failed to create market order")

            # Post the order
            response = self.client.post_order(order, post_only=False)

            order_id = response.get("id") or response.get("order_id")
            if not order_id:
                logger.error("no_order_id_returned", response=response)
                return OrderResult(False, error="No order ID returned from API")

            logger.info("market_order_executed", order_id=order_id, token=token_id)
            return OrderResult(success=True, order_id=order_id)

        except Exception as e:
            logger.error("execute_market_order_failed", error=str(e))
            return OrderResult(False, error=str(e))

    def execute_limit_order(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str,
        expires_in_seconds: int = 3600,
    ) -> OrderResult:
        """Execute a limit order.

        Args:
            token_id: outcome token ID
            price: limit price (0.0-1.0)
            size: order size in tokens
            side: BUY or SELL
            expires_in_seconds: order expiration time

        Returns:
            OrderResult with success/failure info
        """
        try:
            logger.info(
                "executing_limit_order",
                token=token_id,
                price=price,
                size=size,
                side=side,
            )

            # Create limit order
            order = self.client.create_order(
                token_id=token_id,
                price=price,
                size=size,
                side=side,
                fee_rate_bps=0,  # 0% fee (Polymarket often has 0 fees)
            )

            if not order:
                return OrderResult(False, error="Failed to create limit order")

            # Post the order
            response = self.client.post_order(order, post_only=False)

            order_id = response.get("id") or response.get("order_id")
            if not order_id:
                logger.error("no_order_id_returned", response=response)
                return OrderResult(False, error="No order ID returned from API")

            logger.info("limit_order_executed", order_id=order_id, token=token_id)
            return OrderResult(success=True, order_id=order_id)

        except Exception as e:
            logger.error("execute_limit_order_failed", error=str(e))
            return OrderResult(False, error=str(e))

    def check_order_status(self, order_id: str) -> Optional[dict]:
        """Check status of a previously placed order.

        Args:
            order_id: order identifier

        Returns:
            Order status dict or None if not found
        """
        try:
            order = self.client.get_order(order_id)
            logger.debug("order_status_checked", order_id=order_id, status=order.get("status"))
            return order
        except Exception as e:
            logger.error("check_order_status_failed", order_id=order_id, error=str(e))
            return None

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order.

        Args:
            order_id: order to cancel

        Returns:
            True if cancelled successfully
        """
        try:
            self.client.cancel(order_id)
            logger.info("order_cancelled", order_id=order_id)
            return True
        except Exception as e:
            logger.error("cancel_order_failed", order_id=order_id, error=str(e))
            return False

    def wait_for_fill(
        self,
        order_id: str,
        max_wait_seconds: int = 300,
        poll_interval: int = 5,
    ) -> Optional[dict]:
        """Wait for an order to be filled.

        Args:
            order_id: order to monitor
            max_wait_seconds: max time to wait
            poll_interval: polling interval in seconds

        Returns:
            Filled order info or None if timeout/error
        """
        try:
            elapsed = 0
            while elapsed < max_wait_seconds:
                order = self.check_order_status(order_id)
                if not order:
                    return None

                status = order.get("status", "").upper()
                if status == "FILLED":
                    logger.info("order_filled", order_id=order_id)
                    return order
                elif status == "CANCELLED":
                    logger.warning("order_was_cancelled", order_id=order_id)
                    return None

                # Still pending, wait and retry
                time.sleep(poll_interval)
                elapsed += poll_interval
                logger.debug("waiting_for_fill", order_id=order_id, elapsed=elapsed)

            logger.warning("order_fill_timeout", order_id=order_id)
            return None

        except Exception as e:
            logger.error("wait_for_fill_failed", order_id=order_id, error=str(e))
            return None
