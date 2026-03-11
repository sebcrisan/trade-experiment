from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS tokens (
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

CREATE TABLE IF NOT EXISTS market_cap_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_address TEXT NOT NULL,
    observed_at INTEGER NOT NULL,
    market_cap REAL,
    price_usd REAL,
    liquidity_usd REAL,
    volume_h24 REAL,
    UNIQUE(token_address, observed_at),
    FOREIGN KEY(token_address) REFERENCES tokens(token_address)
);

CREATE TABLE IF NOT EXISTS trader_positions (
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


def initialize_database(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.executescript(SCHEMA)
        connection.commit()


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()
