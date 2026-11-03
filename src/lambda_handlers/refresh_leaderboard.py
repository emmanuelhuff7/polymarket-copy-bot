"""Lambda handler for refreshing the leaderboard (EventBridge trigger)."""

import structlog
from src.config import get_settings
from src.state import DynamoClient, TraderStore
from src.leaderboard.fetcher import LeaderboardFetcher

logger = structlog.get_logger(__name__)


def handler(event, context):
    """Lambda handler for EventBridge-triggered leaderboard refresh.

    Runs on schedule (e.g., every 6 hours) to update the list of tracked traders.

    Args:
        event: EventBridge event
        context: Lambda context

    Returns:
        Lambda response
    """
    try:
        settings = get_settings()
        logger.info("leaderboard_refresh_started")

        # Initialize clients
        dynamo = DynamoClient(
            region=settings.aws_region,
            table_prefix=settings.dynamo_table_prefix,
        )
        trader_store = TraderStore(dynamo)
        leaderboard_fetcher = LeaderboardFetcher()

        # Fetch top traders from Polymarket leaderboard (monthly, by profit)
        traders = leaderboard_fetcher.get_top_n_traders(
            n=settings.tracked_trader_count,
            time_period="MONTH",  # Monthly rankings
            order_by="PNL",  # By profit
        )

        if not traders:
            logger.error("no_traders_fetched_from_leaderboard")
            return {
                "statusCode": 500,
                "body": "Failed to fetch traders from leaderboard",
            }

        # Convert to storage format
        trader_dicts = [t.to_dict() for t in traders]

        # Update DynamoDB with new traders
        success = trader_store.update_traders(trader_dicts)

        if not success:
            logger.error("failed_to_update_traders")
            return {"statusCode": 500, "body": "Failed to update trader list"}

        # Log the updated traders
        logger.info("leaderboard_updated", count=len(traders))
        for trader in traders:
            logger.info(
                "tracked_trader",
                rank=trader.rank,
                wallet=trader.proxy_wallet,
                username=trader.user_name,
                pnl=trader.pnl,
            )

        return {
            "statusCode": 200,
            "body": f"Updated {len(traders)} top traders",
            "traders": [
                {
                    "rank": t.rank,
                    "wallet": t.proxy_wallet,
                    "username": t.user_name,
                    "pnl": t.pnl,
                }
                for t in traders
            ],
        }

    except Exception as e:
        logger.error("lambda_handler_error", error=str(e))
        return {"statusCode": 500, "body": f"Error: {str(e)}"}
