#!/usr/bin/env python3
"""Local monitor - no AWS needed. Great for testing before deployment."""

import sys
import os
import json
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import structlog
from src.leaderboard.fetcher import LeaderboardFetcher
from src.monitoring import ActivityPoller, CursorStore, Deduplicator
from src.consensus import SignalAggregator, BasketEvaluator
from src.config import get_settings

logger = structlog.get_logger(__name__)

# In-memory storage (replaces DynamoDB for local testing)
_traders = {}
_cursors = {}
_seen_trades = {}


class LocalTraderStore:
    """In-memory trader store for local testing."""

    def get_tracked_traders(self):
        return list(_traders.values())

    def update_traders(self, traders):
        global _traders
        _traders = {t["wallet_address"]: t for t in traders}
        return True


class LocalCursorStore:
    """In-memory cursor store for local testing."""

    def get_cursor(self, wallet_address):
        return _cursors.get(wallet_address)

    def set_cursor(self, wallet_address, timestamp):
        _cursors[wallet_address] = timestamp
        return True


class LocalTradeStore:
    """In-memory trade store for local testing."""

    def is_seen(self, activity_id):
        return activity_id in _seen_trades

    def mark_seen(self, activity_id):
        _seen_trades[activity_id] = True
        return True


class LocalSQSPublisher:
    """Mock SQS - just prints to console."""

    def publish_signal(self, aggregated_signal):
        print(f"\n{'='*80}")
        print(f"📢 SIGNAL WOULD BE PUBLISHED TO SQS")
        print(f"{'='*80}")
        print(f"Market: {aggregated_signal.market_id}")
        print(f"Side: {aggregated_signal.side}")
        print(f"Traders: {aggregated_signal.trader_count}")
        print(f"Avg Price: {aggregated_signal.average_price:.2f}")
        print(f"Total Size: {aggregated_signal.total_size:.2f}")
        print(f"{'='*80}\n")
        return True


def main():
    """Local monitoring loop - no AWS required."""
    settings = get_settings()

    print("\n" + "="*80)
    print("POLYMARKET COPY TRADING BOT - LOCAL MONITOR (NO AWS)")
    print("="*80)
    print(f"Consensus Threshold: {settings.consensus_threshold}")
    print(f"Tracked Traders: {settings.tracked_trader_count}")
    print(f"Poll Interval: {settings.poll_interval_seconds}s")
    print(f"Signal Window: {settings.signal_window_seconds}s")
    print("="*80 + "\n")

    # Initialize
    leaderboard_fetcher = LeaderboardFetcher()
    trader_store = LocalTraderStore()
    cursor_store = LocalCursorStore()
    trade_store = LocalTradeStore()
    deduplicator = Deduplicator(trade_store)
    activity_poller = ActivityPoller(cursor_store, deduplicator)
    signal_aggregator = SignalAggregator()
    basket_evaluator = BasketEvaluator()
    sqs_publisher = LocalSQSPublisher()

    # Fetch traders
    print("Fetching top traders from leaderboard...")
    traders = leaderboard_fetcher.get_top_n_traders(
        n=settings.tracked_trader_count,
        time_period="MONTH",
        order_by="PNL",
    )

    if not traders:
        print("❌ Failed to fetch traders")
        return False

    print(f"✅ Fetched {len(traders)} traders:\n")
    trader_store.update_traders([t.to_dict() for t in traders])

    for trader in traders:
        print(f"  #{trader.rank} - {trader.user_name}")
        print(f"       Wallet: {trader.proxy_wallet}")
        print(f"       PnL: ${trader.pnl:,.0f}\n")

    # Main loop
    print("="*80)
    print("MONITORING STARTED")
    print(f"Time: {datetime.now().isoformat()}")
    print("Polling every 30 seconds... (Press Ctrl+C to stop)")
    print("="*80 + "\n")

    iteration = 0
    last_leaderboard_refresh = datetime.utcnow()

    try:
        while True:
            iteration += 1
            try:
                # Refresh leaderboard every 6 hours
                if (datetime.utcnow() - last_leaderboard_refresh) > timedelta(hours=6):
                    print("\n[LEADERBOARD REFRESH]")
                    traders = leaderboard_fetcher.get_top_n_traders(
                        n=settings.tracked_trader_count,
                        time_period="MONTH",
                        order_by="PNL",
                    )
                    trader_store.update_traders([t.to_dict() for t in traders])
                    last_leaderboard_refresh = datetime.utcnow()

                # Poll traders
                tracked = trader_store.get_tracked_traders()
                if not tracked:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  No tracked traders")
                    time.sleep(settings.poll_interval_seconds)
                    continue

                trader_addresses = [t["wallet_address"] for t in tracked]
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Iteration #{iteration}: Polling {len(trader_addresses)} traders...", end="")

                signals = activity_poller.poll_all_traders(trader_addresses)
                print(f" {len(signals)} signals")

                if signals:
                    signal_aggregator.ingest_signals(signals)
                    print(f"           Aggregated signals: {signal_aggregator.get_signal_count()}")

                # Evaluate
                pending = signal_aggregator.get_pending_signals()
                if pending:
                    executable, non_executable = basket_evaluator.evaluate_batch(pending)

                    if executable:
                        print(f"           ✅ CONSENSUS MET: {len(executable)} signal(s)")
                        for result in executable:
                            if result.aggregated_signal:
                                sqs_publisher.publish_signal(result.aggregated_signal)
                                signal_aggregator.clear_signal(
                                    result.aggregated_signal.market_id,
                                    result.aggregated_signal.outcome_id,
                                    result.aggregated_signal.side,
                                )

                time.sleep(settings.poll_interval_seconds)

            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error: {e}")
                time.sleep(settings.poll_interval_seconds)

    except KeyboardInterrupt:
        print("\n" + "="*80)
        print("Monitor stopped by user")
        print("="*80)
        return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
