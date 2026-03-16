from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from crypto_sim.dashboard import _normalize_closed_position, _trader_payload_from_repository
from crypto_sim.repository import Repository


def _repository() -> Repository:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE tokens (
            token_address TEXT PRIMARY KEY,
            chain_id TEXT NOT NULL,
            symbol TEXT,
            name TEXT,
            pair_address TEXT,
            dex_id TEXT,
            first_seen_at INTEGER NOT NULL,
            last_seen_at INTEGER NOT NULL,
            first_market_cap REAL,
            latest_market_cap REAL,
            latest_price_usd REAL,
            latest_liquidity_usd REAL,
            latest_volume_h24 REAL,
            latest_checked_at INTEGER,
            pair_created_at INTEGER,
            pair_url TEXT
        );

        CREATE TABLE market_cap_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_address TEXT NOT NULL,
            observed_at INTEGER NOT NULL,
            market_cap REAL,
            price_usd REAL,
            liquidity_usd REAL,
            volume_h24 REAL,
            UNIQUE(token_address, observed_at)
        );

        CREATE TABLE trader_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trader_name TEXT NOT NULL,
            token_address TEXT NOT NULL,
            opened_at INTEGER NOT NULL,
            opened_market_cap REAL NOT NULL,
            amount_usd REAL NOT NULL,
            status TEXT NOT NULL,
            closed_at INTEGER,
            closed_market_cap REAL,
            proceeds_usd REAL,
            pnl_usd REAL,
            close_reason TEXT,
            UNIQUE(trader_name, token_address)
        );
        """
    )
    return Repository(connection)


class DashboardPayloadTests(unittest.TestCase):
    def test_trader_payload_only_lists_profitable_closed_positions(self) -> None:
        repository = _repository()
        repository.connection.execute(
            """
            INSERT INTO tokens (
                token_address, chain_id, symbol, name, first_seen_at, last_seen_at, latest_market_cap,
                latest_price_usd, latest_liquidity_usd, latest_volume_h24, latest_checked_at
            ) VALUES
                ('good', 'solana', 'GOOD', 'Good Token', 1000, 1200, 120000, 0.00012, 22000, 0, 1200),
                ('bad', 'solana', 'BAD', 'Bad Token', 1000, 1200, 50000, 0.00005, 15000, 0, 1200)
            """
        )
        repository.connection.executemany(
            """
            INSERT INTO market_cap_history (
                token_address, observed_at, market_cap, price_usd, liquidity_usd, volume_h24
            ) VALUES (?, ?, ?, ?, ?, 0)
            """,
            [
                ("good", 1000, 100000, 0.0001, 20000),
                ("good", 1100, 10000000, 0.01, 3000000),
                ("good", 1200, 120000, 0.00012, 22000),
                ("bad", 1000, 100000, 0.0001, 20000),
                ("bad", 1200, 50000, 0.00005, 15000),
            ],
        )
        repository.connection.executemany(
            """
            INSERT INTO trader_positions (
                trader_name, token_address, opened_at, opened_market_cap, amount_usd, status,
                closed_at, closed_market_cap, proceeds_usd, pnl_usd, close_reason
            ) VALUES (?, ?, ?, ?, ?, 'CLOSED', ?, ?, ?, ?, ?)
            """,
            [
                ("Direct_1.5x", "good", 1000, 100000, 10.0, 1100, 10000000, 1000.0, 990.0, "target_1.50x"),
                ("Direct_1.5x", "bad", 1000, 100000, 10.0, 1200, 50000, 5.0, -5.0, "max_age_exit"),
            ],
        )

        payload = _trader_payload_from_repository(repository, "Direct_1.5x")

        self.assertEqual(payload["summary"]["closed_positions_count"], 2)
        self.assertEqual(payload["summary"]["total_trades"], 1)
        self.assertEqual(len(payload["closed_positions"]), 1)
        row = payload["closed_positions"][0]
        self.assertEqual(row["token_address"], "good")
        self.assertAlmostEqual(row["closed_market_cap"], 120000.0)
        self.assertAlmostEqual(row["proceeds_usd"], 12.0)
        self.assertAlmostEqual(payload["summary"]["realized_pnl"], -3.0)

    def test_closed_position_is_normalized_when_spike_lasts_multiple_ticks(self) -> None:
        repository = _repository()
        repository.connection.execute(
            """
            INSERT INTO tokens (
                token_address, chain_id, symbol, name, first_seen_at, last_seen_at, latest_market_cap,
                latest_price_usd, latest_liquidity_usd, latest_volume_h24, latest_checked_at
            ) VALUES ('cluster', 'solana', 'CL', 'Cluster Token', 1000, 1300, 3800, 0.0000038, 5000, 0, 1300)
            """
        )
        repository.connection.executemany(
            """
            INSERT INTO market_cap_history (
                token_address, observed_at, market_cap, price_usd, liquidity_usd, volume_h24
            ) VALUES (?, ?, ?, ?, ?, 0)
            """,
            [
                ("cluster", 1000, 40_000, 0.00004, 16_000),
                ("cluster", 1100, 3_800, 0.0000038, 5_000),
                ("cluster", 1200, 183_840_000, 0.1838, 121_439_050.8),
                ("cluster", 1250, 183_840_000, 0.1838, 121_439_050.8),
                ("cluster", 1300, 3_900, 0.0000039, 5_100),
            ],
        )
        position = {
            "token_address": "cluster",
            "amount_usd": 10.0,
            "opened_market_cap": 40_000.0,
            "closed_at": 1250,
            "closed_market_cap": 183_840_000.0,
            "proceeds_usd": 45_960.0,
            "pnl_usd": 45_950.0,
        }

        normalized = _normalize_closed_position(repository, position)

        self.assertTrue(normalized["adjusted_for_outlier"])
        self.assertAlmostEqual(normalized["closed_market_cap"], 3_900.0)
        self.assertAlmostEqual(normalized["proceeds_usd"], 0.975)
        self.assertAlmostEqual(normalized["pnl_usd"], -9.025)


if __name__ == "__main__":
    unittest.main()
