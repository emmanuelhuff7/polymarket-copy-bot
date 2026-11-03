"""Constants and API endpoints."""

# ── DynamoDB Table Names ────────────────────────────────────────
DYNAMO_TABLES = {
    "tracked_traders": "{prefix}-tracked-traders",
    "polling_cursors": "{prefix}-polling-cursors",
    "seen_trades": "{prefix}-seen-trades",
    "copied_trades": "{prefix}-copied-trades",
    "open_positions": "{prefix}-open-positions",
    "daily_pnl": "{prefix}-daily-pnl",
}

# ── Polymarket Chain Config ────────────────────────────────────
POLYGON_CHAIN_ID = 137
POLYMARKET_CTFEXCHANGE_ADDRESS = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"

# ── Signature Types ───────────────────────────────────────────
SIGNATURE_TYPE_EOA = 0
SIGNATURE_TYPE_MAGIC = 1
SIGNATURE_TYPE_GNOSIS = 2

# ── Order Sides ───────────────────────────────────────────────
ORDER_SIDE_BUY = "BUY"
ORDER_SIDE_SELL = "SELL"

# ── Order Types ───────────────────────────────────────────────
ORDER_TYPE_LIMIT = "LIMIT"
ORDER_TYPE_MARKET = "MARKET"

# ── SQS Configuration ────────────────────────────────────────
SQS_MESSAGE_GROUP_ID = "polymarket-trades"
SQS_MAX_RECEIVE_COUNT = 3

# ── Leaderboard Configuration ───────────────────────────────
LEADERBOARD_URL = "https://polymarket.com/leaderboard"
LEADERBOARD_REFRESH_INTERVAL_HOURS = 6

# ── HTTP Configuration ──────────────────────────────────────
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_RETRY_MAX_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_FACTOR = 2

# ── Rate Limiting ───────────────────────────────────────────
POLYMARKET_API_RATE_LIMIT_PER_SECOND = 10
ACTIVITY_POLL_MIN_INTERVAL_SECONDS = 5

# ── Trade Signal Configuration ─────────────────────────────
SIGNAL_AGGREGATION_WINDOW_SECONDS = 300  # 5 minutes
SIGNAL_DEDUPLICATION_TTL_DAYS = 30

# ── Position Configuration ──────────────────────────────────
POSITION_SIZE_MIN_USD = 25.0
POSITION_SIZE_MAX_USD = 30.0
POSITION_SCALING_TOLERANCE_PERCENT = 10  # +/- 10% acceptable variance

# ── Lambda Configuration ────────────────────────────────────
LAMBDA_EXECUTE_TRADE_TIMEOUT_SECONDS = 300  # 5 minutes
LAMBDA_REFRESH_LEADERBOARD_TIMEOUT_SECONDS = 900  # 15 minutes
LAMBDA_DAILY_REPORT_TIMEOUT_SECONDS = 300  # 5 minutes

# ── ECS Configuration ──────────────────────────────────────
ECS_HEALTH_CHECK_PORT = 8080
ECS_HEALTH_CHECK_PATH = "/health"
ECS_LOG_GROUP_PREFIX = "/ecs/polymarket-bot"

# ── CloudWatch Configuration ────────────────────────────────
CLOUDWATCH_METRIC_NAMESPACE = "PolymarketCopyBot"
CLOUDWATCH_LOG_RETENTION_DAYS = 30

# ── Monitoring Windows ──────────────────────────────────────
MONITORING_STARTUP_WAIT_SECONDS = 5
MONITORING_SHUTDOWN_WAIT_SECONDS = 10
