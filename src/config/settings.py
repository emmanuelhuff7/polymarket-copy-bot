"""Settings and configuration management using Pydantic."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Main configuration settings for the Polymarket copy trading bot."""

    # ── Trading Logic ──────────────────────────────────────────────
    consensus_threshold: int = 2
    """Minimum number of tracked traders that must agree for a copy trade."""

    tracked_trader_count: int = 5
    """Number of top traders to track."""

    position_size_usd: float = 27.50
    """Target position size per trade in USD."""

    account_capital_usd: float = 1500.00
    """Total account capital in USD."""

    max_open_positions: int = 10
    """Maximum number of concurrent open positions."""

    daily_loss_limit_usd: float = 75.00
    """Daily loss limit in USD (5% of capital by default)."""

    min_market_volume_usd: float = 50_000.00
    """Minimum market daily volume to trade in USD."""

    signal_window_seconds: int = 300
    """Time window for accumulating trade signals (in-memory aggregation)."""

    markets_skip_list: str = ""
    """Comma-separated list of market IDs to skip."""

    # ── Polling ─────────────────────────────────────────────────────
    poll_interval_seconds: int = 30
    """How often to poll for new trader activity."""

    leaderboard_refresh_cron: str = "rate(6 hours)"
    """EventBridge cron expression for leaderboard refresh."""

    # ── Polymarket APIs ────────────────────────────────────────────
    polymarket_host: str = "https://clob.polymarket.com"
    """Polymarket CLOB API host."""

    data_api_base: str = "https://data-api.polymarket.com"
    """Polymarket Data API base URL."""

    gamma_api_base: str = "https://gamma-api.polymarket.com"
    """Polymarket Gamma API base URL."""

    polygon_rpc_url: str = "https://polygon-rpc.com"
    """Polygon RPC endpoint URL."""

    # ── AWS Configuration ──────────────────────────────────────────
    aws_region: str = "us-east-1"
    """AWS region for all resources."""

    sqs_queue_url: str = ""
    """SQS FIFO queue URL for trade signals."""

    sns_topic_arn: str = ""
    """SNS topic ARN for alerts."""

    dynamo_table_prefix: str = "polymarket-bot"
    """DynamoDB table name prefix."""

    secrets_manager_key_arn: str = ""
    """Secrets Manager ARN for EOA private key."""

    secrets_manager_creds_arn: str = ""
    """Secrets Manager ARN for API credentials."""

    # ── Alerts ────────────────────────────────────────────────────
    alert_email: str = ""
    """Email address for alerts."""

    alert_phone: str = ""
    """Phone number for SMS alerts (E.164 format)."""

    # ── Logging ───────────────────────────────────────────────────
    log_level: str = "INFO"
    """Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)."""

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    # ── Computed properties ────────────────────────────────────────

    @property
    def skip_market_ids(self) -> set[str]:
        """Parse the comma-separated skip list into a set."""
        if not self.markets_skip_list:
            return set()
        return {m.strip() for m in self.markets_skip_list.split(",") if m.strip()}

    @property
    def daily_loss_limit_reached_percentage(self) -> float:
        """Daily loss limit as percentage of account capital."""
        return (self.daily_loss_limit_usd / self.account_capital_usd) * 100


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the global Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
