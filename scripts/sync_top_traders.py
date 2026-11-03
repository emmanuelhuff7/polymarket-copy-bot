#!/usr/bin/env python3
"""Immediately sync top traders from Polymarket leaderboard.

This script fetches the top 5 monthly traders and seeds them into the database,
without needing to manually provide wallet addresses.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import structlog

logger = structlog.get_logger(__name__)


def main():
    """Fetch and sync top traders."""
    try:
        # Import after adding to path
        from src.config import get_settings
        from src.state import DynamoClient, TraderStore
        from src.leaderboard.fetcher import LeaderboardFetcher

        settings = get_settings()

        print("\n" + "="*80)
        print("SYNCING TOP TRADERS FROM POLYMARKET LEADERBOARD")
        print("="*80 + "\n")

        # Initialize
        print("Connecting to Polymarket API...")
        leaderboard_fetcher = LeaderboardFetcher()

        print("Fetching top traders (monthly, by profit)...")
        traders = leaderboard_fetcher.get_top_n_traders(
            n=settings.tracked_trader_count,
            time_period="MONTH",
            order_by="PNL",
        )

        if not traders:
            print("❌ FAILED: Could not fetch traders from leaderboard")
            print("Make sure you have internet connection and requests library installed")
            return False

        print(f"✓ Fetched {len(traders)} top traders\n")

        # Display fetched traders
        print("Top Traders (Monthly by Profit):")
        print("-" * 80)
        for trader in traders:
            print(f"#{trader.rank:2d} | {trader.user_name:30s} | PnL: ${trader.pnl:>12,.0f} | {trader.proxy_wallet}")
        print("-" * 80 + "\n")

        # Save to database
        print("Saving to database...")
        dynamo = DynamoClient(
            region=settings.aws_region,
            table_prefix=settings.dynamo_table_prefix,
        )
        trader_store = TraderStore(dynamo)

        trader_dicts = [t.to_dict() for t in traders]
        success = trader_store.update_traders(trader_dicts)

        if success:
            print("✓ Traders saved successfully\n")
            print("="*80)
            print("SYNC COMPLETE")
            print("="*80)
            print(f"\nTracking {len(traders)} top traders:")
            for trader in traders:
                print(f"  • {trader.user_name} ({trader.proxy_wallet})")
            print("\nYou can now run the monitor:")
            print("  python -m src.entrypoints.monitor")
            return True
        else:
            print("❌ FAILED: Could not save traders to database")
            print("Make sure AWS credentials are configured and DynamoDB tables exist")
            return False

    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("Make sure dependencies are installed: pip install -e .")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
