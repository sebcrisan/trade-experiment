from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Iterable

from crypto_sim.dexscreener import PairSnapshot


@dataclass(frozen=True)
class TokenState:
    token_address: str
    first_seen_at: int
    latest_market_cap: float | None
    latest_checked_at: int | None


@dataclass(frozen=True)
class OpenPosition:
    id: int
    trader_name: str
    token_address: str
    opened_at: int
    opened_market_cap: float
    amount_usd: float


@dataclass(frozen=True)
class LatestSnapshot:
    token_address: str
    observed_at: int
    market_cap: float | None
    liquidity_usd: float | None
    price_usd: float | None


@dataclass(frozen=True)
class FirstSnapshot:
    token_address: str
    observed_at: int
    market_cap: float | None
    liquidity_usd: float | None
    volume_h24: float | None


class Repository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def upsert_token_snapshot(self, snapshot: PairSnapshot, observed_at: int) -> None:
        current = self.connection.execute(
            "SELECT token_address FROM tokens WHERE token_address = ?",
            (snapshot.token_address,),
        ).fetchone()

        if current is None:
            self.connection.execute(
                """
                INSERT INTO tokens (
                    token_address, chain_id, symbol, name, pair_address, dex_id, first_seen_at,
                    last_seen_at, first_market_cap, latest_market_cap, latest_price_usd,
                    latest_liquidity_usd, latest_volume_h24, latest_checked_at, pair_created_at, pair_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.token_address,
                    snapshot.chain_id,
                    snapshot.symbol,
                    snapshot.name,
                    snapshot.pair_address,
                    snapshot.dex_id,
                    observed_at,
                    observed_at,
                    snapshot.market_cap,
                    snapshot.market_cap,
                    snapshot.price_usd,
                    snapshot.liquidity_usd,
                    snapshot.volume_h24,
                    observed_at,
                    snapshot.pair_created_at,
                    snapshot.pair_url,
                ),
            )
        else:
            self.connection.execute(
                """
                UPDATE tokens
                SET symbol = COALESCE(?, symbol),
                    name = COALESCE(?, name),
                    pair_address = COALESCE(?, pair_address),
                    dex_id = COALESCE(?, dex_id),
                    last_seen_at = ?,
                    latest_market_cap = ?,
                    latest_price_usd = ?,
                    latest_liquidity_usd = ?,
                    latest_volume_h24 = ?,
                    latest_checked_at = ?,
                    pair_created_at = COALESCE(?, pair_created_at),
                    pair_url = COALESCE(?, pair_url)
                WHERE token_address = ?
                """,
                (
                    snapshot.symbol,
                    snapshot.name,
                    snapshot.pair_address,
                    snapshot.dex_id,
                    observed_at,
                    snapshot.market_cap,
                    snapshot.price_usd,
                    snapshot.liquidity_usd,
                    snapshot.volume_h24,
                    observed_at,
                    snapshot.pair_created_at,
                    snapshot.pair_url,
                    snapshot.token_address,
                ),
            )

        self.connection.execute(
            """
            INSERT OR REPLACE INTO market_cap_history (
                token_address, observed_at, market_cap, price_usd, liquidity_usd, volume_h24
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.token_address,
                observed_at,
                snapshot.market_cap,
                snapshot.price_usd,
                snapshot.liquidity_usd,
                snapshot.volume_h24,
            ),
        )

    def all_token_addresses(self) -> list[str]:
        rows = self.connection.execute("SELECT token_address FROM tokens ORDER BY first_seen_at ASC").fetchall()
        return [row["token_address"] for row in rows]

    def token_states(self) -> dict[str, TokenState]:
        rows = self.connection.execute(
            """
            SELECT token_address, first_seen_at, latest_market_cap, latest_checked_at
            FROM tokens
            """
        ).fetchall()
        return {
            row["token_address"]: TokenState(
                token_address=row["token_address"],
                first_seen_at=row["first_seen_at"],
                latest_market_cap=row["latest_market_cap"],
                latest_checked_at=row["latest_checked_at"],
            )
            for row in rows
        }

    def open_positions(self) -> list[OpenPosition]:
        rows = self.connection.execute(
            """
            SELECT id, trader_name, token_address, opened_at, opened_market_cap, amount_usd
            FROM trader_positions
            WHERE status = 'OPEN'
            """
        ).fetchall()
        return [
            OpenPosition(
                id=row["id"],
                trader_name=row["trader_name"],
                token_address=row["token_address"],
                opened_at=row["opened_at"],
                opened_market_cap=row["opened_market_cap"],
                amount_usd=row["amount_usd"],
            )
            for row in rows
        ]

    def has_position(self, trader_name: str, token_address: str) -> bool:
        row = self.connection.execute(
            """
            SELECT 1
            FROM trader_positions
            WHERE trader_name = ? AND token_address = ? AND status = 'OPEN'
            """,
            (trader_name, token_address),
        ).fetchone()
        return row is not None

    def has_ever_position(self, trader_name: str, token_address: str) -> bool:
        row = self.connection.execute(
            """
            SELECT 1
            FROM trader_positions
            WHERE trader_name = ? AND token_address = ?
            """,
            (trader_name, token_address),
        ).fetchone()
        return row is not None

    def open_position(
        self,
        trader_name: str,
        token_address: str,
        opened_at: int,
        opened_market_cap: float,
        amount_usd: float,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO trader_positions (
                trader_name, token_address, opened_at, opened_market_cap, amount_usd, status
            ) VALUES (?, ?, ?, ?, ?, 'OPEN')
            """,
            (trader_name, token_address, opened_at, opened_market_cap, amount_usd),
        )

    def close_position(
        self,
        position_id: int,
        closed_at: int,
        closed_market_cap: float,
        proceeds_usd: float,
        pnl_usd: float,
        close_reason: str,
    ) -> None:
        self.connection.execute(
            """
            UPDATE trader_positions
            SET status = 'CLOSED',
                closed_at = ?,
                closed_market_cap = ?,
                proceeds_usd = ?,
                pnl_usd = ?,
                close_reason = ?
            WHERE id = ?
            """,
            (closed_at, closed_market_cap, proceeds_usd, pnl_usd, close_reason, position_id),
        )

    def trader_report_rows(self) -> list[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT
                trader_name,
                COUNT(*) AS total_trades,
                COALESCE(SUM(amount_usd), 0) AS total_spent,
                COALESCE(SUM(proceeds_usd), 0) AS total_proceeds,
                COALESCE(SUM(pnl_usd), 0) AS total_pnl
            FROM trader_positions
            WHERE status = 'CLOSED'
            GROUP BY trader_name
            ORDER BY trader_name
            """
        ).fetchall()

    def open_position_report_rows(self) -> list[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT
                p.trader_name,
                p.token_address,
                p.opened_at,
                p.opened_market_cap,
                p.amount_usd,
                t.symbol,
                t.name,
                t.latest_market_cap,
                t.latest_liquidity_usd,
                t.pair_url
            FROM trader_positions p
            LEFT JOIN tokens t ON t.token_address = p.token_address
            WHERE p.status = 'OPEN'
            ORDER BY trader_name, opened_at DESC
            """
        ).fetchall()

    def trader_names(self) -> list[str]:
        rows = self.connection.execute(
            """
            SELECT trader_name
            FROM trader_positions
            GROUP BY trader_name
            ORDER BY trader_name
            """
        ).fetchall()
        return [row["trader_name"] for row in rows]

    def trader_closed_summary(self, trader_name: str) -> sqlite3.Row:
        row = self.connection.execute(
            """
            SELECT
                ? AS trader_name,
                COUNT(*) AS total_trades,
                COALESCE(SUM(amount_usd), 0) AS total_spent,
                COALESCE(SUM(proceeds_usd), 0) AS total_proceeds,
                COALESCE(SUM(pnl_usd), 0) AS total_pnl
            FROM trader_positions
            WHERE trader_name = ? AND status = 'CLOSED'
            """,
            (trader_name, trader_name),
        ).fetchone()
        return row

    def trader_open_summary(self, trader_name: str) -> sqlite3.Row:
        row = self.connection.execute(
            """
            SELECT
                ? AS trader_name,
                COUNT(*) AS open_trades,
                COALESCE(SUM(amount_usd), 0) AS open_spent
            FROM trader_positions
            WHERE trader_name = ? AND status = 'OPEN'
            """,
            (trader_name, trader_name),
        ).fetchone()
        return row

    def trader_open_positions(self, trader_name: str) -> list[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT
                p.id,
                p.trader_name,
                p.token_address,
                p.opened_at,
                p.opened_market_cap,
                p.amount_usd,
                t.symbol,
                t.name,
                t.latest_market_cap,
                t.latest_price_usd,
                t.latest_liquidity_usd,
                t.pair_url
            FROM trader_positions p
            LEFT JOIN tokens t ON t.token_address = p.token_address
            WHERE p.trader_name = ? AND p.status = 'OPEN'
            ORDER BY p.opened_at DESC
            """,
            (trader_name,),
        ).fetchall()

    def trader_closed_positions(self, trader_name: str, limit: int = 100) -> list[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT
                p.id,
                p.trader_name,
                p.token_address,
                p.opened_at,
                p.opened_market_cap,
                p.amount_usd,
                p.closed_at,
                p.closed_market_cap,
                p.proceeds_usd,
                p.pnl_usd,
                p.close_reason,
                t.symbol,
                t.name,
                t.pair_url
            FROM trader_positions p
            LEFT JOIN tokens t ON t.token_address = p.token_address
            WHERE p.trader_name = ? AND p.status = 'CLOSED'
            ORDER BY p.closed_at DESC
            LIMIT ?
            """,
            (trader_name, limit),
        ).fetchall()

    def latest_tokens(self, limit: int = 50) -> list[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT
                token_address,
                symbol,
                name,
                pair_address,
                dex_id,
                first_seen_at,
                last_seen_at,
                latest_market_cap,
                latest_price_usd,
                latest_liquidity_usd,
                latest_volume_h24,
                pair_url
            FROM tokens
            ORDER BY first_seen_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    def token_detail(self, token_address: str) -> sqlite3.Row | None:
        return self.connection.execute(
            """
            SELECT
                token_address,
                chain_id,
                symbol,
                name,
                pair_address,
                dex_id,
                first_seen_at,
                last_seen_at,
                latest_market_cap,
                latest_price_usd,
                latest_liquidity_usd,
                latest_volume_h24,
                pair_url
            FROM tokens
            WHERE token_address = ?
            """,
            (token_address,),
        ).fetchone()

    def token_history(self, token_address: str, limit: int = 1440) -> list[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT
                observed_at,
                market_cap,
                price_usd,
                liquidity_usd,
                volume_h24
            FROM market_cap_history
            WHERE token_address = ?
            ORDER BY observed_at ASC
            LIMIT ?
            """,
            (token_address, limit),
        ).fetchall()

    def positions_for_token(self, token_address: str) -> list[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT
                token_address,
                trader_name,
                opened_at,
                opened_market_cap,
                amount_usd,
                status,
                closed_at,
                closed_market_cap,
                proceeds_usd,
                pnl_usd,
                close_reason
            FROM trader_positions
            WHERE token_address = ?
            ORDER BY opened_at ASC
            """,
            (token_address,),
        ).fetchall()

    def top_token_performance(self, limit: int = 10) -> list[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT
                t.token_address,
                t.symbol,
                t.name,
                t.pair_url,
                t.latest_market_cap,
                COUNT(*) AS total_positions,
                COALESCE(SUM(p.amount_usd), 0) AS total_invested,
                COALESCE(SUM(CASE WHEN p.status = 'CLOSED' THEN p.pnl_usd ELSE 0 END), 0) AS realized_pnl,
                COALESCE(SUM(
                    CASE
                        WHEN p.status = 'OPEN' AND t.latest_market_cap IS NOT NULL AND p.opened_market_cap > 0
                        THEN MIN(
                            p.amount_usd * (t.latest_market_cap / p.opened_market_cap),
                            COALESCE(t.latest_liquidity_usd, p.amount_usd * (t.latest_market_cap / p.opened_market_cap))
                        ) - p.amount_usd
                        ELSE 0
                    END
                ), 0) AS unrealized_pnl,
                COALESCE(SUM(
                    CASE
                        WHEN p.status = 'OPEN' AND t.latest_market_cap IS NOT NULL AND p.opened_market_cap > 0
                        THEN MIN(
                            p.amount_usd * (t.latest_market_cap / p.opened_market_cap),
                            COALESCE(t.latest_liquidity_usd, p.amount_usd * (t.latest_market_cap / p.opened_market_cap))
                        )
                        ELSE 0
                    END
                ), 0) AS current_open_value
            FROM trader_positions p
            LEFT JOIN tokens t ON t.token_address = p.token_address
            GROUP BY t.token_address, t.symbol, t.name, t.pair_url, t.latest_market_cap
            ORDER BY (realized_pnl + unrealized_pnl) DESC, total_positions DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    def total_token_count(self) -> int:
        row = self.connection.execute("SELECT COUNT(*) AS count FROM tokens").fetchone()
        return int(row["count"])

    def total_snapshot_count(self) -> int:
        row = self.connection.execute("SELECT COUNT(*) AS count FROM market_cap_history").fetchone()
        return int(row["count"])

    def latest_snapshots_for_tokens(self, token_addresses: Iterable[str]) -> dict[str, LatestSnapshot]:
        addresses = list(token_addresses)
        if not addresses:
            return {}
        placeholders = ",".join("?" for _ in addresses)
        rows = self.connection.execute(
            f"""
            SELECT token_address, observed_at, market_cap, liquidity_usd, price_usd
            FROM market_cap_history
            WHERE (token_address, observed_at) IN (
                SELECT token_address, MAX(observed_at)
                FROM market_cap_history
                WHERE token_address IN ({placeholders})
                GROUP BY token_address
            )
            """,
            addresses,
        ).fetchall()
        return {
            row["token_address"]: LatestSnapshot(
                token_address=row["token_address"],
                observed_at=row["observed_at"],
                market_cap=row["market_cap"],
                liquidity_usd=row["liquidity_usd"],
                price_usd=row["price_usd"],
            )
            for row in rows
        }

    def snapshot_at(self, token_address: str, observed_at: int) -> LatestSnapshot | None:
        row = self.connection.execute(
            """
            SELECT token_address, observed_at, market_cap, liquidity_usd, price_usd
            FROM market_cap_history
            WHERE token_address = ? AND observed_at = ?
            """,
            (token_address, observed_at),
        ).fetchone()
        if row is None:
            return None
        return LatestSnapshot(
            token_address=row["token_address"],
            observed_at=row["observed_at"],
            market_cap=row["market_cap"],
            liquidity_usd=row["liquidity_usd"],
            price_usd=row["price_usd"],
        )

    def previous_snapshot_for_token(self, token_address: str, observed_at: int) -> LatestSnapshot | None:
        row = self.connection.execute(
            """
            SELECT token_address, observed_at, market_cap, liquidity_usd, price_usd
            FROM market_cap_history
            WHERE token_address = ? AND observed_at < ?
            ORDER BY observed_at DESC
            LIMIT 1
            """,
            (token_address, observed_at),
        ).fetchone()
        if row is None:
            return None
        return LatestSnapshot(
            token_address=row["token_address"],
            observed_at=row["observed_at"],
            market_cap=row["market_cap"],
            liquidity_usd=row["liquidity_usd"],
            price_usd=row["price_usd"],
        )

    def next_snapshot_for_token(self, token_address: str, observed_at: int) -> LatestSnapshot | None:
        row = self.connection.execute(
            """
            SELECT token_address, observed_at, market_cap, liquidity_usd, price_usd
            FROM market_cap_history
            WHERE token_address = ? AND observed_at > ?
            ORDER BY observed_at ASC
            LIMIT 1
            """,
            (token_address, observed_at),
        ).fetchone()
        if row is None:
            return None
        return LatestSnapshot(
            token_address=row["token_address"],
            observed_at=row["observed_at"],
            market_cap=row["market_cap"],
            liquidity_usd=row["liquidity_usd"],
            price_usd=row["price_usd"],
        )

    def first_snapshots_for_tokens(self, token_addresses: Iterable[str]) -> dict[str, FirstSnapshot]:
        addresses = list(token_addresses)
        if not addresses:
            return {}
        placeholders = ",".join("?" for _ in addresses)
        rows = self.connection.execute(
            f"""
            SELECT token_address, observed_at, market_cap, liquidity_usd, volume_h24
            FROM market_cap_history
            WHERE (token_address, observed_at) IN (
                SELECT token_address, MIN(observed_at)
                FROM market_cap_history
                WHERE token_address IN ({placeholders})
                GROUP BY token_address
            )
            """,
            addresses,
        ).fetchall()
        return {
            row["token_address"]: FirstSnapshot(
                token_address=row["token_address"],
                observed_at=row["observed_at"],
                market_cap=row["market_cap"],
                liquidity_usd=row["liquidity_usd"],
                volume_h24=row["volume_h24"],
            )
            for row in rows
        }
