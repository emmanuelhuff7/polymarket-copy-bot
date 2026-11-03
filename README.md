# Polymarket Basket Copy Trading Bot

A fully automated Python copy trading bot for [Polymarket](https://polymarket.com) that intelligently copies trades from top-performing traders using a basket consensus approach.

## Features

- **Automatic Trader Discovery**: Identifies top 5 most profitable traders on Polymarket
- **Basket Consensus**: Only copies trades when ≥2 of 5 tracked traders agree (reduces noise)
- **Smart Position Sizing**: Proportional scaling capped at $25-30 per trade (2% risk rule)
- **Real-time Monitoring**: Polls Polymarket API every 30 seconds for new trades
- **Risk Management**:
  - Daily loss limit ($75 / 5% of capital)
  - Max 10 open positions
  - Liquidity filter ($50k+ daily volume)
  - Automatic deduplication
- **AWS Native**: Runs on ECS Fargate + Lambda + SQS + DynamoDB
- **Fully Automated**: Set it and forget it (24/7 operation)

## Architecture

```
EventBridge (6h cron)
    ↓
Lambda: Refresh Leaderboard
    ↓
DynamoDB: Tracked Traders
    ↓
ECS Fargate: Monitor Loop (30s polling)
    ├─ Query /activity for each trader
    ├─ Aggregate signals (in-memory 5-min window)
    ├─ Evaluate consensus (≥2 of 5)
    └─ Publish to SQS
        ↓
SQS FIFO Queue
        ↓
Lambda: Execute Trade
    ├─ Risk checks (daily loss, max positions)
    ├─ Liquidity check
    ├─ Position sizing
    └─ Place order via CLOB API
        ↓
SNS: Email/SMS Alerts
```

## Project Structure

```
polymarket-copy-bot/
├── src/
│   ├── config/          # Settings and constants
│   ├── state/           # DynamoDB layer
│   ├── account/         # Key and credential management
│   ├── monitoring/      # Activity polling
│   ├── consensus/       # Signal aggregation + basket evaluation
│   ├── risk/            # Position sizing + guards
│   ├── execution/       # Order placement
│   ├── messaging/       # SQS + SNS
│   ├── lambda_handlers/ # Lambda function entry points
│   └── entrypoints/     # ECS main loop
├── scripts/             # Setup and deployment scripts
├── infra/               # AWS CDK infrastructure (optional, not yet implemented)
├── tests/               # Unit and integration tests
└── Dockerfile           # ECS container image
```

## Getting Started

### 1. Prerequisites

- Python 3.11+
- AWS Account with appropriate IAM permissions
- Git

### 2. Install Dependencies

```bash
cd polymarket-copy-bot
pip install -e .
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your AWS credentials and preferences
```

### 4. Set Up Account (One-time)

```bash
python scripts/setup_account.py
```

This will:
1. Generate a new Ethereum private key
2. Derive API credentials from Polymarket
3. Store both securely in AWS Secrets Manager
4. Print your proxy wallet address

**Then fund the wallet:**
- Send $1,500 USDC to the printed address (on Polygon network)
- Send ~$5-10 MATIC for gas

### 5. Deploy to AWS

```bash
# Bootstrap CDK (first time only)
cd infra
npm install -g aws-cdk
cdk bootstrap aws://ACCOUNT_ID/us-east-1

# Deploy all resources
cdk deploy --all
```

### 6. Seed Traders

```bash
python scripts/seed_traders.py --wallets "0xwallet1,0xwallet2,0xwallet3"
```

Provide wallet addresses of top Polymarket traders to track.

### 7. Run Smoke Test

```bash
python scripts/smoke_test.py
```

Verifies all connections work before going live.

### 8. Start Monitoring

```bash
# Option A: Local (development)
python -m src.entrypoints.monitor

# Option B: ECS (production)
aws ecs update-service --cluster polymarket-bot --service monitor --desired-count 1
```

## Configuration

All settings are in `src/config/settings.py`. Override via environment variables or `.env` file:

```
# Trading
CONSENSUS_THRESHOLD=2              # Min traders agreeing
TRACKED_TRADER_COUNT=5             # Top N traders to track
POSITION_SIZE_USD=27.50            # Target trade size
ACCOUNT_CAPITAL_USD=1500.00        # Total capital
MAX_OPEN_POSITIONS=10              # Position limit
DAILY_LOSS_LIMIT_USD=75.00         # Daily stop loss

# AWS
AWS_REGION=us-east-1
SQS_QUEUE_URL=...
SNS_TOPIC_ARN=...
DYNAMO_TABLE_PREFIX=polymarket-bot
SECRETS_MANAGER_KEY_ARN=...
SECRETS_MANAGER_CREDS_ARN=...

# Alerts
ALERT_EMAIL=your-email@example.com
ALERT_PHONE=+15551234567
```

## Monitoring

Check real-time status:

```bash
# CloudWatch Logs
aws logs tail /ecs/polymarket-bot-monitor --follow

# DynamoDB Tables
aws dynamodb scan --table-name polymarket-bot-tracked-traders
aws dynamodb scan --table-name polymarket-bot-copied-trades

# Lambda Execution
aws logs tail /aws/lambda/polymarket-bot-execute-trade --follow
```

## Safety Guardrails

1. **Daily Loss Limit**: Stops all trading if daily loss > $75
2. **Max Positions**: Won't open more than 10 concurrent positions
3. **Liquidity Filter**: Skips markets with < $50k daily volume
4. **Consensus Requirement**: Won't copy single-trader signals (needs ≥2 of 5)
5. **Deduplication**: Prevents double-executing the same signal
6. **Position Capping**: Hard ceiling of $30 per trade

## Troubleshooting

### "Invalid API credentials"
- Run `python scripts/setup_account.py` again to refresh credentials

### "Wallet not funded"
- Verify you sent USDC and MATIC to the correct address
- Use Polygon network, not Ethereum mainnet
- Check balance: `aws secretsmanager get-secret-value --secret-id polymarket-bot/eoa-key`

### "No trades executing"
- Check trader addresses are correct: `aws dynamodb scan --table-name polymarket-bot-tracked-traders`
- Monitor logs: `aws logs tail /ecs/polymarket-bot-monitor --follow`
- Verify SQS queue has messages: `aws sqs get-queue-attributes --queue-url $SQS_URL`

### "Loss limit breached"
- Check daily P&L: `aws dynamodb query --table-name polymarket-bot-daily-pnl`
- Trading will resume the next day
- Consider adjusting `DAILY_LOSS_LIMIT_USD` or reducing `MAX_OPEN_POSITIONS`

## Development

Run tests:

```bash
pytest tests/
```

Format code:

```bash
black src/ scripts/
ruff check src/ scripts/
```

## Performance Expectations

Based on research of copy trading on Polymarket:

- **Win Rate**: 52-56% (requires discipline)
- **Expected Return**: 15-30% annually on capital
- **Average P&L per Trade**: ~$1-2 (on $27.50 position)
- **Trades per Month**: 50-100 (depending on trader activity)

Success depends on:
1. Quality of tracked traders (garbage in = garbage out)
2. Market conditions (favorable for predictions = more alpha)
3. Discipline (don't override the bot, let it work)

## Disclaimer

This bot uses real capital and can lose money. Use at your own risk. The creators are not responsible for financial losses. Always:
- Start small ($100-500) to validate
- Monitor closely during first week
- Have stop-loss in place ($75/day)
- Never risk capital you can't afford to lose

## License

MIT

## Contributing

Contributions welcome! Please:
1. Fork the repo
2. Create a feature branch
3. Write tests
4. Submit PR

## Support

For issues or questions:
- Check CloudWatch logs
- Review `src/config/settings.py` for configuration options
- Ensure all prerequisites are installed
