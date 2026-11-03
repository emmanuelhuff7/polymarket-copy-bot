"""Lambda handler for executing trades from SQS messages."""

import structlog
import os
from src.config import get_settings
from src.account import CredManager
from src.state import DynamoClient, TradeStore, PositionStore
from src.risk import PortfolioGuard, PositionSizer, LiquidityChecker
from src.execution import OrderExecutor
from src.messaging import SQSConsumer, SNSNotifier
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON

logger = structlog.get_logger(__name__)


def handler(event, context):
    """Lambda handler for SQS-triggered trade execution.

    Args:
        event: SQS event with BasketSignal
        context: Lambda context

    Returns:
        Lambda response
    """
    try:
        settings = get_settings()

        # Parse SQS message
        consumer = SQSConsumer(settings.sqs_queue_url)
        basket_signal = consumer.extract_signal_from_event(event)

        if not basket_signal:
            logger.error("failed_to_extract_signal")
            return {"statusCode": 400, "body": "Invalid signal"}

        logger.info("trade_execution_started", signal_id=basket_signal.signal_id)

        # Load credentials
        cred_manager = CredManager()
        api_creds = cred_manager.load_api_creds(settings.secrets_manager_creds_arn)

        if not api_creds:
            logger.error("failed_to_load_api_creds")
            return {"statusCode": 500, "body": "Failed to load credentials"}

        # Initialize clients
        dynamo = DynamoClient(region=settings.aws_region, table_prefix=settings.dynamo_table_prefix)
        clob_client = ClobClient(
            host=settings.polymarket_host,
            chain_id=POLYGON,
            signature_type=0,
        )
        clob_client.set_api_creds(api_creds)

        # Initialize business logic
        trade_store = TradeStore(dynamo)
        position_store = PositionStore(dynamo)
        portfolio_guard = PortfolioGuard(position_store, trade_store)
        position_sizer = PositionSizer()
        liquidity_checker = LiquidityChecker()
        order_executor = OrderExecutor(clob_client)
        sns_notifier = SNSNotifier(settings.sns_topic_arn)

        # Risk checks
        risk_decision = portfolio_guard.check(basket_signal.market_id)
        if not risk_decision.should_execute:
            logger.warning("trade_blocked_by_risk", reason=risk_decision.reason)
            sns_notifier.send_alert(
                "Trade Blocked",
                f"Market: {basket_signal.market_id}\nReason: {risk_decision.reason}",
            )
            return {"statusCode": 200, "body": "Trade blocked by risk checks"}

        # Liquidity check
        liquidity_result = liquidity_checker.check_market_liquidity(basket_signal.market_id)
        if not liquidity_result.is_liquid:
            logger.warning("market_illiquid", reason=liquidity_result.reason)
            return {"statusCode": 200, "body": f"Market illiquid: {liquidity_result.reason}"}

        # Position sizing
        size_result = position_sizer.compute_size(
            trader_trade_size=basket_signal.total_size,
            trader_portfolio_value=5_000_000,  # Assume $5M avg trader portfolio
        )

        if size_result.size_usd <= 0:
            logger.warning("invalid_position_size", size=size_result.size_usd)
            return {"statusCode": 200, "body": "Invalid position size"}

        logger.info("position_sized", size_usd=size_result.size_usd, method=size_result.method)

        # Execute trade
        order_result = order_executor.execute_market_order(
            token_id=basket_signal.outcome_id,
            side=basket_signal.side,
            amount=size_result.size_usd,
        )

        if not order_result.success:
            logger.error("order_execution_failed", error=order_result.error)
            sns_notifier.send_trade_failed(
                basket_signal.market_id,
                order_result.error,
            )
            return {"statusCode": 500, "body": f"Order execution failed: {order_result.error}"}

        # Record trade
        trade_store.record_copied_trade(
            basket_signal_id=basket_signal.signal_id,
            market_id=basket_signal.market_id,
            side=basket_signal.side,
            size_usd=size_result.size_usd,
            order_id=order_result.order_id,
            fill_price=order_result.fill_price,
            status="EXECUTED",
        )

        # Send notification
        sns_notifier.send_trade_executed(
            market_id=basket_signal.market_id,
            side=basket_signal.side,
            size_usd=size_result.size_usd,
            order_id=order_result.order_id,
            traders_count=basket_signal.trader_count,
        )

        logger.info("trade_execution_complete", order_id=order_result.order_id)
        return {
            "statusCode": 200,
            "body": f"Trade executed: {order_result.order_id}",
            "orderId": order_result.order_id,
        }

    except Exception as e:
        logger.error("lambda_handler_error", error=str(e))
        return {"statusCode": 500, "body": f"Error: {str(e)}"}
