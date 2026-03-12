# Crypto Sim

Tracks newly surfaced Solana tokens from Dexscreener, stores periodic snapshots in SQLite, and simulates a large matrix of fixed-rule trading strategies against those snapshots.

## Overview

The service does three things on each cycle:

- discovers recently surfaced Solana tokens from Dexscreener's `token-profiles/latest/v1` feed
- resolves the best pair for each token through Dexscreener's token pair endpoint
- stores the latest market data and evaluates simulated trader entries and exits

Snapshot data is written to SQLite under `data/crypto_sim.db` by default. The dashboard reads directly from that database and shows traders, open positions, token history, and aggregate PnL.

## Discovery Model

- only `solana` profiles are considered
- token discovery comes from the latest token profiles feed, then pair details are fetched in batches
- only pairs created within the configured age window are admitted as new discoveries
- previously seen tokens are refreshed on each cycle even after the discovery window has passed
- when a token has multiple pairs, the simulator keeps the best one ranked by market cap, then liquidity, then 24h volume

## Strategy Model

Strategies are generated programmatically, not hard-coded as four traders anymore.

There are two strategy families:

- `Direct_*`: buy immediately on the first snapshot with market cap at or above `20,000`
- `Confirmed_*`: wait until the token has first been seen at or above `20,000`, then buy only once market cap reaches `2x` that first qualifying level

For each family, sell targets are generated from `1.5x` up to `49.0x` in `0.5x` increments. That produces 192 trader variants in total.

Common rules:

- each position size is fixed at `$10`
- each trader can take at most one position per token
- open positions are force-closed once the token has been tracked for 24 hours
- exit triggers still use market-cap multiples
- realizable value is capped by the latest observed `liquidity_usd`, so liquidity rugs cannot create fake profits

## Defaults

- database path: `data/crypto_sim.db`
- poll interval: `60` seconds
- chain: `solana`
- position size: `$10`
- max token age before forced exit: `86400` seconds
- max pair age for new discoveries: `1800` seconds

## Commands

Initialize the database:

```bash
python main.py init-db
```

Run one discovery and simulation cycle:

```bash
python main.py tick
```

Run continuously with the default 60-second interval:

```bash
python main.py run
```

Run continuously with an explicit interval:

```bash
python main.py run --interval-seconds 60
```

Run continuously and only admit pairs created in the last 30 minutes:

```bash
python main.py run --max-pair-age-seconds 1800
```

Print the closed-trade summary for each trader:

```bash
python main.py report
```

Run the local dashboard:

```bash
python main.py dashboard --host 127.0.0.1 --port 8000
```

Use a custom database path:

```bash
python main.py --db-path data/my-sim.db run
```

## Notes

Dexscreener does not expose a documented "newest Solana pairs" endpoint. This project uses the latest token profiles feed as the discovery source and filters pair freshness via `pair_created_at`.

If liquidity disappears while market cap spikes, reported value can fall sharply because exits and unrealized valuation are bounded by available liquidity rather than by headline market cap alone.
