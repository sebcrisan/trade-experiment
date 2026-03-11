# Crypto Sim

Tracks newly surfaced Solana tokens from Dexscreener, stores periodic market-cap snapshots in SQLite, and simulates fixed-rule traders.

## What it does

- Polls Dexscreener's `token-profiles/latest/v1` feed and filters to `solana`
- Enriches those token addresses through `tokens/v1/solana/{addresses}`
- Stores token metadata and minute-by-minute market-cap snapshots in SQLite
- Simulates four traders with fixed buy/sell rules
- Forces a sale for any open position once the token has been in the database for more than 24 hours

## Important limitation

Dexscreener does not expose a documented "newest Solana pairs" endpoint. This project uses the official latest token profiles feed as the discovery source, then resolves pair and market-cap data from the token endpoints and filters discovery by `pair_created_at` so only genuinely recent pairs are eligible.

## Traders

- `TraderA`: buy on first observation with market cap >= 20k, sell at 1.5x
- `TraderB`: once a token has been observed at >= 20k, buy on first observation with market cap >= 40k, sell at 1.5x
- `TraderC`: buy on first observation with market cap >= 20k, sell at 2.0x
- `TraderD`: once a token has been observed at >= 20k, buy on first observation with market cap >= 40k, sell at 2.0x

Each buy is simulated as a `$10` position. Position value scales with market-cap ratio from entry to exit.

## Usage

Initialize the database:

```bash
python main.py init-db
```

Run one cycle:

```bash
python main.py tick
```

Run continuously every minute:

```bash
python main.py run --interval-seconds 60
```

Run continuously and only admit pairs created in the last 30 minutes:

```bash
python main.py run --interval-seconds 60 --max-pair-age-seconds 1800
```

Show trader performance:

```bash
python main.py report
```

Run the local dashboard:

```bash
python main.py dashboard --host 127.0.0.1 --port 8000
```

Use a custom database path:

```bash
python main.py --db-path data/sim.db run
```
