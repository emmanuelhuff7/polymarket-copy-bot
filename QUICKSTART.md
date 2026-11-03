# ⚡ Quick Start Guide

Get the bot running in 5 minutes.

## Prerequisites

- Python 3.11+
- AWS account with CLI configured
- $1,500+ to trade with

## Step 1: Install (1 min)

```bash
cd ~/Code/polymarket-copy-bot
pip install -e .
```

## Step 2: Generate Account (1 min)

```bash
python scripts/setup_account.py
```

**Output will show:**
```
Wallet Address (PROXY): 0x1234567890abcdef...

NEXT STEPS:
1. Fund this wallet with:
   - $1,500 USDC
   - $5-10 MATIC
   (on Polygon network, not Ethereum!)
```

## Step 3: Fund Wallet (Online, use Polygon Bridge or Coinbase)

Go to [Polygon Bridge](https://bridge.polygon.technology) or buy directly on Coinbase.

Send USDC to the address from Step 2 on **Polygon network**.

## Step 4: Seed Traders (1 min)

Get wallet addresses of 5 top Polymarket traders. Find them at:
- [Polymarket Leaderboard](https://polymarket.com/leaderboard)

Example (replace with real addresses):
```bash
python scripts/seed_traders.py \
  --wallets "0xabc123,0xdef456,0xghi789,0xjkl012,0xmno345"
```

## Step 5: Run Bot (Prod)

### Option A: Local Testing
```bash
python -m src.entrypoints.monitor
```

You should see logs like:
```
poll_iteration=1 iteration=1
polling_traders count=5
activity_polled signals=0
pending_signals count=0
```

Let it run for 5 minutes to test.

### Option B: Deploy to AWS (Production)

First-time setup only:

```bash
# Install CDK
npm install -g aws-cdk

# Bootstrap AWS
cdk bootstrap aws://YOUR_ACCOUNT_ID/us-east-1

# Deploy
cd infra
cdk deploy --all
```

Then start the service:
```bash
aws ecs update-service \
  --cluster polymarket-bot \
  --service monitor \
  --desired-count 1
```

## What to Expect

1. **First hour**: Bot discovers trader addresses, starts monitoring
2. **First day**: No trades yet (consensus filtering)
3. **First week**: 5-10 trades (learning market)
4. **Steady state**: 10-20 trades/week, P&L +/-$50-100/week

## Monitoring

### View Logs Locally
```bash
# Running bot outputs logs to console
# Search for "signal_published" to see copy trades
```

### View Logs on AWS
```bash
# Trade execution
aws logs tail /aws/lambda/polymarket-bot-execute-trade --follow

# Main monitoring
aws logs tail /ecs/polymarket-bot-monitor --follow
```

### Check Trades
```bash
# See all copied trades
aws dynamodb scan --table-name polymarket-bot-copied-trades --limit 10
```

## Troubleshooting

**No trades after 1 hour?**
1. Check traders are active: Visit [Polymarket Leaderboard](https://polymarket.com/leaderboard)
2. Check wallet funded:
   ```bash
   aws secretsmanager get-secret-value \
     --secret-id polymarket-bot/eoa-key
   # Copy address and check on Polygonscan
   ```
3. View logs to see errors:
   ```bash
   python -m src.entrypoints.monitor  # Run locally to see errors
   ```

**Trades executing but losing money?**
1. Reduce `CONSENSUS_THRESHOLD` to `2` (stricter filtering)
2. Reduce `POSITION_SIZE_USD` to `15` (smaller bets)
3. Increase `DAILY_LOSS_LIMIT_USD` if limit is too tight
4. Check you're following profitable traders

**Wallet shows $0 balance?**
1. Make sure you sent to **Polygon** network, not Ethereum
2. Check address on [Polygonscan](https://polygonscan.com)
3. Wait for transaction to confirm (5-10 seconds)
4. Try restarting the bot

## Settings

Edit `.env` to change behavior:

```bash
# Copy template
cp .env.example .env

# Edit
nano .env

# Key settings:
CONSENSUS_THRESHOLD=2              # Stricter = fewer trades
POSITION_SIZE_USD=27.50            # Smaller = less risk
DAILY_LOSS_LIMIT_USD=75.00         # Hard stop-loss
MAX_OPEN_POSITIONS=10              # Position limit
POLL_INTERVAL_SECONDS=30           # How often to check
```

## Safety Checklist

✅ Consensus threshold set to ≥2 (don't copy single traders)
✅ Position size in range $25-$30
✅ Daily loss limit $75 (5% of capital)
✅ Max positions limited to 10
✅ Only tracking verified, profitable traders
✅ Email/SMS alerts configured for major events

## Production Checklist

Before running 24/7:

- [ ] Ran bot locally for 1 hour without errors
- [ ] Wallet funded with $1,500 USDC + $5 MATIC
- [ ] Traders seeded and verified active
- [ ] Daily loss limit alerts configured in SNS
- [ ] CloudWatch logs visible
- [ ] SNS email subscriptions confirmed

## Next Steps

1. **This hour**: Run locally and confirm it works
2. **This day**: Deploy to AWS if satisfied
3. **This week**: Monitor and adjust settings
4. **Ongoing**: Let it trade 24/7

---

**Need help?** See `README.md` for full documentation.
