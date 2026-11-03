"""ECS Fargate main monitoring loop."""

import structlog
import time
import signal
import sys
from datetime import datetime, timedelta
from src.config import get_settings
from src.state import DynamoClient, TraderStore
from src.monitoring import ActivityPoller, CursorStore, Deduplicator
from src.consensus import SignalAggregator, BasketEvaluator
from src.messaging import SQSPublisher
from src.state import TradeStore
from src.leaderboard.fetcher import LeaderboardFetcher

logger = structlog.get_logger(__name__)

# Global shutdown flag
_shutdown = False
_last_leaderboard_refresh = None


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    global _shutdown
    logger.info("shutdown_signal_received", signal=sig)
    _shutdown = True


def main():
    """Main monitoring loop for ECS Fargate."""
    global _shutdown

    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    settings = get_settings()
    logger.info(
        "monitor_starting",
        consensus_threshold=settings.consensus_threshold,
        poll_interval=settings.poll_interval_seconds,
    )

    try:
        global _last_leaderboard_refresh

        # Initialize AWS clients
        dynamo = DynamoClient(
            region=settings.aws_region,
            table_prefix=settings.dynamo_table_prefix,
        )

        # Initialize stores
        trader_store = TraderStore(dynamo)
        trade_store = TradeStore(dynamo)
        cursor_store = CursorStore(dynamo)

        # Initialize monitoring
        deduplicator = Deduplicator(trade_store)
        activity_poller = ActivityPoller(cursor_store, deduplicator)

        # Initialize consensus
        signal_aggregator = SignalAggregator()
        basket_evaluator = BasketEvaluator()

        # Initialize messaging
        sqs_publisher = SQSPublisher(settings.sqs_queue_url)

        # Initialize leaderboard fetcher
        leaderboard_fetcher = LeaderboardFetcher()

        # Refresh leaderboard on startup
        logger.info("refreshing_leaderboard_on_startup")
        _refresh_leaderboard(trader_store, leaderboard_fetcher, settings)
        _last_leaderboard_refresh = datetime.utcnow()

        # Main loop
        iteration = 0
        while not _shutdown:
            iteration += 1
            try:
                logger.debug("poll_iteration", iteration=iteration)

                # Periodically refresh leaderboard (every 6 hours)
                if _last_leaderboard_refresh is None or \
                   (datetime.utcnow() - _last_leaderboard_refresh) > timedelta(hours=6):
                    logger.info("periodic_leaderboard_refresh")
                    _refresh_leaderboard(trader_store, leaderboard_fetcher, settings)
                    _last_leaderboard_refresh = datetime.utcnow()

                # Get tracked traders
                traders = trader_store.get_tracked_traders()
                if not traders:
                    logger.warning("no_tracked_traders")
                    time.sleep(settings.poll_interval_seconds)
                    continue

                trader_addresses = [t["wallet_address"] for t in traders]
                logger.debug("polling_traders", count=len(trader_addresses))

                # Poll all traders for new activity
                signals = activity_poller.poll_all_traders(trader_addresses)
                logger.info("activity_polled", signals=len(signals))

                if signals:
                    # Aggregate signals
                    signal_aggregator.ingest_signals(signals)
                    logger.debug("signals_ingested", aggregated_count=signal_aggregator.get_signal_count())

                # Get pending aggregated signals
                pending_signals = signal_aggregator.get_pending_signals()
                logger.debug("pending_signals", count=len(pending_signals))

                # Evaluate each signal
                if pending_signals:
                    executable, non_executable = basket_evaluator.evaluate_batch(pending_signals)
                    logger.info("signals_evaluated", executable=len(executable), skipped=len(non_executable))

                    # Publish executable signals to SQS
                    for result in executable:
                        if result.aggregated_signal:
                            success = sqs_publisher.publish_signal(result.aggregated_signal)
                            if success:
                                # Clear from in-memory after publishing
                                signal_aggregator.clear_signal(
                                    result.aggregated_signal.market_id,
                                    result.aggregated_signal.outcome_id,
                                    result.aggregated_signal.side,
                                )
                                logger.info(
                                    "signal_published",
                                    market=result.aggregated_signal.market_id,
                                    traders=result.aggregated_signal.trader_count,
                                )

                # Sleep before next poll
                time.sleep(settings.poll_interval_seconds)

            except Exception as e:
                logger.error("poll_iteration_error", iteration=iteration, error=str(e))
                time.sleep(settings.poll_interval_seconds)
                continue

        logger.info("monitor_shutdown_complete")

    except Exception as e:
        logger.error("monitor_fatal_error", error=str(e))
        sys.exit(1)


def _refresh_leaderboard(trader_store, leaderboard_fetcher, settings):
    """Refresh the list of top traders from leaderboard.

    Args:
        trader_store: TraderStore instance
        leaderboard_fetcher: LeaderboardFetcher instance
        settings: Settings instance
    """
    try:
        traders = leaderboard_fetcher.get_top_n_traders(
            n=settings.tracked_trader_count,
            time_period="MONTH",
            order_by="PNL",
        )

        if not traders:
            logger.warning("failed_to_refresh_leaderboard")
            return

        trader_dicts = [t.to_dict() for t in traders]
        if trader_store.update_traders(trader_dicts):
            logger.info("leaderboard_refreshed", count=len(traders))
            for trader in traders:
                logger.info(
                    "tracked_trader",
                    rank=trader.rank,
                    wallet=trader.proxy_wallet,
                    username=trader.user_name,
                    pnl=trader.pnl,
                )
        else:
            logger.error("failed_to_update_trader_store")

    except Exception as e:
        logger.error("leaderboard_refresh_error", error=str(e))


if __name__ == "__main__":
    main()
