# ✅ Running the Bot Locally (No AWS Needed)

The bot **works without AWS**! Use the local monitor for testing before deployment.

## Quick Start

```bash
cd ~/Code/polymarket-copy-bot
python scripts/monitor_local.py
```

That's it! The bot will:
1. ✅ Fetch top 5 monthly traders from Polymarket
2. ✅ Poll their activity every 30 seconds
3. ✅ Aggregate trade signals
4. ✅ Show when consensus is met
5. ✅ Print "SIGNAL WOULD BE PUBLISHED" (instead of actually executing)

## What to Expect

```
================================================================================
POLYMARKET COPY TRADING BOT - LOCAL MONITOR (NO AWS)
================================================================================
Consensus Threshold: 2
Tracked Traders: 5
Poll Interval: 30s
Signal Window: 300s
================================================================================

Fetching top traders from leaderboard...
✅ Fetched 5 traders:

  #1 - HorizonSplendidView
       Wallet: 0x02227b8f5a9636e895607edd3185ed6ee5598ff7
       PnL: $4,016,108

  #2 - majorexploiter
       Wallet: 0x019782cab5d844f02bafb71f512758be78579f3c
       PnL: $2,416,975

  ... (3 more traders)

================================================================================
MONITORING STARTED
Time: 2026-03-13T11:36:49.123456
Polling every 30 seconds... (Press Ctrl+C to stop)
================================================================================

[11:36:49] Iteration #1: Polling 5 traders... 0 signals
[11:37:19] Iteration #2: Polling 5 traders... 2 signals
           Aggregated signals: 2
[11:37:49] Iteration #3: Polling 5 traders... 1 signals
           Aggregated signals: 3
[11:38:19] Iteration #4: Polling 5 traders... 0 signals
[11:38:49] Iteration #5: Polling 5 traders... 0 signals

```

## When You See Consensus

When 2+ traders agree on the same trade, you'll see:

```
[11:39:19] Iteration #10: Polling 5 traders... 3 signals
           Aggregated signals: 5
           ✅ CONSENSUS MET: 1 signal(s)

================================================================================
📢 SIGNAL WOULD BE PUBLISHED TO SQS
================================================================================
Market: 0x1234567890abcdef...
Side: BUY
Traders: 2
Avg Price: 0.62
Total Size: 125.50
================================================================================

```

This means "if you had AWS set up, this trade would execute!"

## Differences vs. Production

| Feature | Local Monitor | Production (AWS) |
|---------|--------------|------------------|
| Fetch traders | ✅ Yes | ✅ Yes |
| Poll activity | ✅ Yes | ✅ Yes |
| Check consensus | ✅ Yes | ✅ Yes |
| Store in DB | ❌ In-memory | ✅ DynamoDB |
| Send alerts | ❌ Console | ✅ Email/SMS |
| Execute trades | ❌ Simulated | ✅ Real orders |

## Configuration

All settings in `src/config/settings.py` work the same way:

```bash
# Change number of traders
export TRACKED_TRADER_COUNT=10
python scripts/monitor_local.py

# Change poll interval
export POLL_INTERVAL_SECONDS=60
python scripts/monitor_local.py

# Change consensus threshold
export CONSENSUS_THRESHOLD=3
python scripts/monitor_local.py
```

## How to Deploy to Production

Once you're confident the monitor works:

1. **Set up AWS**:
   ```bash
   aws configure
   # Enter your AWS access key and secret
   ```

2. **Run production monitor**:
   ```bash
   python -m src.entrypoints.monitor
   ```

3. **Or deploy to ECS**:
   ```bash
   cd infra
   cdk deploy --all
   ```

## Troubleshooting

### "Unable to locate credentials" error
You ran the production monitor without AWS. Use the local monitor instead:
```bash
python scripts/monitor_local.py
```

### No signals appearing
This is normal! Signals only appear when traders actually trade. Monitor for a few minutes:
- 0 signals = no recent activity (expected)
- Consensus met = 2+ traders agreed (rare, depends on activity)

### Want to see it work faster?
Change the poll interval to 5 seconds:
```bash
export POLL_INTERVAL_SECONDS=5
python scripts/monitor_local.py
```

## Next Steps

1. **Run locally for a few minutes** to validate everything works
2. **Fund wallet** with $100 USDC + MATIC
3. **Configure AWS** if you want to deploy
4. **Run production** monitor when ready

---

**The local monitor is fully functional and shows exactly what would happen in production!**
