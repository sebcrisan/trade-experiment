from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote
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
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.commit()


@contextmanager
def connect(db_path: Path, *, read_only: bool = False) -> Iterator[sqlite3.Connection]:
    if not db_path.exists() and not read_only:
        initialize_database(db_path)
    if read_only:
        uri = f"file:{quote(str(db_path.resolve()).replace('\\', '/'))}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=30.0, isolation_level=None)
        _configure_connection(connection, read_only=True)
    else:
        connection = sqlite3.connect(db_path, timeout=30.0)
        _configure_connection(connection, read_only=False)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        if not read_only:
            connection.commit()
    finally:
        connection.close()


def _configure_connection(connection: sqlite3.Connection, *, read_only: bool) -> None:
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute("PRAGMA foreign_keys=ON")
    if read_only:
        connection.execute("PRAGMA query_only=ON")
    else:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
