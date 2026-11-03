#!/usr/bin/env python3
"""Seed the trader database with known top traders."""

import sys
import os
import argparse

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import structlog
from src.config import get_settings
from src.state import DynamoClient, TraderStore

logger = structlog.get_logger(__name__)


def main():
    """Seed initial traders into the database."""
    parser = argparse.ArgumentParser(description="Seed trader list")
    parser.add_argument(
        "--wallets",
        required=True,
        help="Comma-separated list of wallet addresses to track",
    )
    args = parser.parse_args()

    settings = get_settings()
    wallets = [w.strip() for w in args.wallets.split(",")]

    logger.info("seeding_traders", count=len(wallets))

    try:
        dynamo = DynamoClient(
            region=settings.aws_region,
            table_prefix=settings.dynamo_table_prefix,
        )
        trader_store = TraderStore(dynamo)

        traders = [
            {
                "wallet_address": wallet,
                "score": 1000.0,  # Default score, will be updated by ranker
                "username": wallet[:10] + "...",
            }
            for wallet in wallets
        ]

        if trader_store.update_traders(traders):
            logger.info("traders_seeded", count=len(traders))
            print(f"✓ Seeded {len(traders)} traders")
            for wallet in wallets:
                print(f"  - {wallet}")
            return True
        else:
            logger.error("failed_to_seed_traders")
            return False

    except Exception as e:
        logger.error("seed_traders_error", error=str(e))
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error("script_error", error=str(e))
        sys.exit(1)
