from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from crypto_sim.repository import Repository
from crypto_sim.simulator import evaluate_traders


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


class SimulatorTests(unittest.TestCase):
    def test_trader_a_and_c_buy_at_20k_and_exit_on_targets(self) -> None:
        repository = _repository()
        repository.connection.execute(
            """
            INSERT INTO tokens (
                token_address, chain_id, first_seen_at, last_seen_at, latest_market_cap, latest_checked_at
            ) VALUES ('token1', 'solana', 1000, 1000, 20000, 1000)
            """
        )
        repository.connection.execute(
            """
            INSERT INTO market_cap_history (
                token_address, observed_at, market_cap, price_usd, liquidity_usd, volume_h24
            ) VALUES ('token1', 1000, 20000, NULL, NULL, NULL)
            """
        )

        states = repository.token_states()
        evaluate_traders(repository, states, observed_at=1000, position_size_usd=10.0, max_token_age_seconds=86400)

        open_rows = repository.connection.execute(
            "SELECT trader_name FROM trader_positions WHERE status = 'OPEN' ORDER BY trader_name"
        ).fetchall()
        trader_names = [row["trader_name"] for row in open_rows]
        self.assertIn("Direct_1.5x", trader_names)
        self.assertIn("Direct_2.0x", trader_names)

        repository.connection.execute(
            "UPDATE tokens SET latest_market_cap = 40000, latest_checked_at = 1100 WHERE token_address = 'token1'"
        )
        repository.connection.execute(
            """
            INSERT INTO market_cap_history (
                token_address, observed_at, market_cap, price_usd, liquidity_usd, volume_h24
            ) VALUES ('token1', 1100, 40000, NULL, NULL, NULL)
            """
        )
        states = repository.token_states()
        evaluate_traders(repository, states, observed_at=1100, position_size_usd=10.0, max_token_age_seconds=86400)

        closed = repository.connection.execute(
            """
            SELECT trader_name, proceeds_usd, close_reason
            FROM trader_positions
            WHERE status = 'CLOSED'
            ORDER BY trader_name
            """
        ).fetchall()
        closed_map = {
            row["trader_name"]: (row["proceeds_usd"], row["close_reason"])
            for row in closed
        }
        self.assertEqual(closed_map["Direct_1.5x"], (20.0, "target_1.50x"))
        self.assertEqual(closed_map["Direct_2.0x"], (20.0, "target_2.00x"))

    def test_trader_b_and_d_buy_after_40k_once_20k_seen(self) -> None:
        repository = _repository()
        repository.connection.execute(
            """
            INSERT INTO tokens (
                token_address, chain_id, first_seen_at, last_seen_at, latest_market_cap, latest_checked_at
            ) VALUES ('token2', 'solana', 1000, 1000, 20000, 1000)
            """
        )
        repository.connection.execute(
            """
            INSERT INTO market_cap_history (
                token_address, observed_at, market_cap, price_usd, liquidity_usd, volume_h24
            ) VALUES ('token2', 1000, 20000, NULL, NULL, NULL)
            """
        )
        states = repository.token_states()
        evaluate_traders(repository, states, observed_at=1000, position_size_usd=10.0, max_token_age_seconds=86400)

        repository.connection.execute(
            "UPDATE tokens SET latest_market_cap = 40000, latest_checked_at = 1100 WHERE token_address = 'token2'"
        )
        repository.connection.execute(
            """
            INSERT INTO market_cap_history (
                token_address, observed_at, market_cap, price_usd, liquidity_usd, volume_h24
            ) VALUES ('token2', 1100, 40000, NULL, NULL, NULL)
            """
        )
        states = repository.token_states()
        evaluate_traders(repository, states, observed_at=1100, position_size_usd=10.0, max_token_age_seconds=86400)

        open_rows = repository.connection.execute(
            "SELECT trader_name FROM trader_positions WHERE status = 'OPEN' ORDER BY trader_name"
        ).fetchall()
        trader_names = [row["trader_name"] for row in open_rows]
        self.assertIn("Confirmed_1.5x", trader_names)
        self.assertIn("Confirmed_2.0x", trader_names)

    def test_open_positions_are_force_closed_after_one_day(self) -> None:
        repository = _repository()
        repository.connection.execute(
            """
            INSERT INTO tokens (
                token_address, chain_id, first_seen_at, last_seen_at, latest_market_cap, latest_checked_at
            ) VALUES ('token3', 'solana', 1000, 1000, 20000, 1000)
            """
        )
        repository.connection.execute(
            """
            INSERT INTO market_cap_history (
                token_address, observed_at, market_cap, price_usd, liquidity_usd, volume_h24
            ) VALUES ('token3', 1000, 20000, NULL, NULL, NULL)
            """
        )
        states = repository.token_states()
        evaluate_traders(repository, states, observed_at=1000, position_size_usd=10.0, max_token_age_seconds=86400)

        repository.connection.execute(
            "UPDATE tokens SET latest_market_cap = 10000, latest_checked_at = 90000 WHERE token_address = 'token3'"
        )
        repository.connection.execute(
            """
            INSERT INTO market_cap_history (
                token_address, observed_at, market_cap, price_usd, liquidity_usd, volume_h24
            ) VALUES ('token3', 90000, 10000, NULL, NULL, NULL)
            """
        )
        states = repository.token_states()
        evaluate_traders(repository, states, observed_at=90000, position_size_usd=10.0, max_token_age_seconds=86400)

        closed = repository.connection.execute(
            """
            SELECT trader_name, proceeds_usd, close_reason
            FROM trader_positions
            WHERE status = 'CLOSED'
            ORDER BY trader_name
            """
        ).fetchall()
        closed_map = {
            row["trader_name"]: (row["proceeds_usd"], row["close_reason"])
            for row in closed
        }
        self.assertEqual(closed_map["Direct_1.5x"], (5.0, "max_age_exit"))
        self.assertEqual(closed_map["Direct_2.0x"], (5.0, "max_age_exit"))


if __name__ == "__main__":
    unittest.main()
