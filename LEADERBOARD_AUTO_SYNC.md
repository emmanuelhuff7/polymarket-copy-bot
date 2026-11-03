# ✨ Automatic Leaderboard Sync

Good news! The bot now **automatically discovers and tracks the top 5 monthly traders** from Polymarket without manual seeding.

## What Changed

Previously: `python scripts/seed_traders.py --wallets "0xabc,0xdef,..."`
Now: The bot fetches top traders automatically!

## How It Works

1. **On startup**: Bot fetches the top 5 monthly traders from Polymarket leaderboard
2. **Every 6 hours**: Bot refreshes the list (in case rankings change)
3. **Real-time**: Monitors their activity and copies trades

## Two Ways to Trigger Sync

### Option 1: Automatic (Recommended)

Just run the bot normally:
```bash
python -m src.entrypoints.monitor
```

The bot will:
1. Automatically fetch top 5 traders on startup
2. Refresh every 6 hours
3. Start monitoring immediately

### Option 2: Manual Sync (One-time)

To immediately sync without running the full monitor:
```bash
python scripts/sync_top_traders.py
```

This is useful if you want to:
- See which traders will be tracked
- Verify the sync works
- Update traders without running the monitor

## Example Output

```bash
$ python scripts/sync_top_traders.py

================================================================================
SYNCING TOP TRADERS FROM POLYMARKET LEADERBOARD
================================================================================

Connecting to Polymarket API...
Fetching top traders (monthly, by profit)...
✓ Fetched 5 top traders

Top Traders (Monthly by Profit):
--------------------------------------------------------------------------------
 #1 | trader_username_1          | PnL: $    523,456 | 0x1234...5678
 #2 | trader_username_2          | PnL: $    412,789 | 0xabcd...ef01
 #3 | trader_username_3          | PnL: $    289,123 | 0x5678...9abc
 #4 | trader_username_4          | PnL: $    176,543 | 0xdef0...1234
 #5 | trader_username_5          | PnL: $     98,765 | 0x2468...ace0
--------------------------------------------------------------------------------

Saving to database...
✓ Traders saved successfully

================================================================================
SYNC COMPLETE
================================================================================

Tracking 5 top traders:
  • trader_username_1 (0x1234...5678)
  • trader_username_2 (0xabcd...ef01)
  • trader_username_3 (0x5678...9abc)
  • trader_username_4 (0xdef0...1234)
  • trader_username_5 (0x2468...ace0)

You can now run the monitor:
  python -m src.entrypoints.monitor
```

## Configuration

The leaderboard syncing is controlled by these settings in `src/config/settings.py`:

```python
TRACKED_TRADER_COUNT=5              # How many top traders to track
# (No other settings needed - it always uses monthly profit rankings)
```

To change the number of tracked traders:
```bash
# Edit .env or set environment variable
export TRACKED_TRADER_COUNT=10

# Then run
python scripts/sync_top_traders.py
```

## What Gets Tracked

The bot fetches traders from: **Polymarket Leaderboard → Overall Category → Monthly → Sorted by Profit**

This means:
- ✅ Across all markets (OVERALL, not specific category)
- ✅ Monthly period (30-day rolling window)
- ✅ Ranked by PnL (profit/loss)
- ✅ Only profitable traders (filters out negative PnL)

## How Refreshing Works

**In the monitor loop** (runs automatically):
```
Startup:
  ↓
Fetch top 5 monthly traders
  ↓
Start monitoring & polling every 30 seconds
  ↓
Every 6 hours:
  ↓
Refresh trader list from leaderboard
  ↓
Continue monitoring (old signals cleared)
```

This means the bot is **always tracking the current top traders** without manual intervention.

## Switching Back to Manual

If you prefer to manually specify traders:

```bash
# Use the old manual seeding
python scripts/seed_traders.py --wallets "0xabc,0xdef,0xghi,0xjkl,0xmno"
```

This will **override** the automatic leaderboard sync. The monitor won't refresh the list automatically.

## Troubleshooting

### Script says "Failed to fetch traders"
- Check internet connection
- Check Polymarket API is responding: `curl https://data-api.polymarket.com/v1/leaderboard?limit=5`
- Check your terminal output for specific error message

### Bot started but no traders appear
- Run `python scripts/sync_top_traders.py` to see detailed logs
- Check DynamoDB: `aws dynamodb scan --table-name polymarket-bot-tracked-traders`
- Check monitor logs: look for "leaderboard_refreshed" message

### Want to use different ranking criteria
The API supports:
- `timePeriod`: DAY, WEEK, MONTH (default), ALL
- `orderBy`: PNL (default), VOL (volume)
- `category`: OVERALL (default), POLITICS, SPORTS, CRYPTO, etc.

To change, edit `src/entrypoints/monitor.py` line 76-80 in the `_refresh_leaderboard()` function.

## Example: Track Top 10 by Weekly Volume

Edit `src/entrypoints/monitor.py`:
```python
traders = leaderboard_fetcher.get_top_n_traders(
    n=10,                    # Changed from 5
    time_period="WEEK",      # Changed from MONTH
    order_by="VOL",         # Changed from PNL
)
```

Then restart the monitor.

---

**That's it!** The bot now tracks the best traders automatically. No more manual seeding needed. 🚀
