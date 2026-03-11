from __future__ import annotations

import time
from typing import Iterable

from crypto_sim.config import Settings
from crypto_sim.db import connect
from crypto_sim.dexscreener import DexscreenerClient, PairSnapshot
from crypto_sim.repository import Repository
from crypto_sim.simulator import evaluate_traders


class SimulationService:
    def __init__(self, settings: Settings, client: DexscreenerClient | None = None) -> None:
        self.settings = settings
        self.client = client or DexscreenerClient()

    def run_forever(self) -> None:
        while True:
            self.run_once()
            time.sleep(self.settings.poll_interval_seconds)

    def run_once(self) -> dict[str, int]:
        observed_at = int(time.time())
        discovered = self._discover_solana_tokens(observed_at)

        with connect(self.settings.db_path) as connection:
            repository = Repository(connection)
            existing_addresses = repository.all_token_addresses()
            self._persist_snapshots(repository, discovered, observed_at)

            refreshed = self._refresh_existing(existing_addresses)
            self._persist_snapshots(repository, refreshed, observed_at)

            token_states = repository.token_states()
            evaluate_traders(
                repository=repository,
                token_states=token_states,
                observed_at=observed_at,
                position_size_usd=self.settings.position_size_usd,
                max_token_age_seconds=self.settings.max_token_age_seconds,
            )

            return {
                "tokens": repository.total_token_count(),
                "snapshots": repository.total_snapshot_count(),
                "new_snapshots": len(discovered),
                "refreshed_snapshots": len(refreshed),
            }

    def _discover_solana_tokens(self, observed_at: int) -> list[PairSnapshot]:
        profiles = self.client.latest_token_profiles()
        addresses = []
        for profile in profiles:
            if profile.chain_id != self.settings.chain_id:
                continue
            if profile.token_address not in addresses:
                addresses.append(profile.token_address)
        pairs = self._fetch_best_pairs(addresses)
        return [pair for pair in pairs if _is_recent_pair(pair, observed_at, self.settings.max_pair_age_seconds)]

    def _refresh_existing(self, token_addresses: Iterable[str]) -> list[PairSnapshot]:
        return self._fetch_best_pairs(token_addresses)

    def _fetch_best_pairs(self, token_addresses: Iterable[str]) -> list[PairSnapshot]:
        snapshots: list[PairSnapshot] = []
        batch: list[str] = []

        for address in token_addresses:
            batch.append(address)
            if len(batch) == 30:
                snapshots.extend(self._best_pairs_for_batch(batch))
                batch = []
        if batch:
            snapshots.extend(self._best_pairs_for_batch(batch))
        return snapshots

    def _best_pairs_for_batch(self, token_addresses: list[str]) -> list[PairSnapshot]:
        pair_rows = self.client.token_pairs(self.settings.chain_id, token_addresses)
        best_by_token: dict[str, PairSnapshot] = {}
        for pair in pair_rows:
            if pair.token_address not in token_addresses:
                continue
            current = best_by_token.get(pair.token_address)
            if current is None or _pair_sort_key(pair) > _pair_sort_key(current):
                best_by_token[pair.token_address] = pair
        return list(best_by_token.values())

    @staticmethod
    def _persist_snapshots(repository: Repository, snapshots: Iterable[PairSnapshot], observed_at: int) -> None:
        for snapshot in snapshots:
            if not snapshot.token_address:
                continue
            repository.upsert_token_snapshot(snapshot, observed_at)


def _pair_sort_key(snapshot: PairSnapshot) -> tuple[float, float, float]:
    return (
        snapshot.market_cap or -1.0,
        snapshot.liquidity_usd or -1.0,
        snapshot.volume_h24 or -1.0,
    )


def _is_recent_pair(snapshot: PairSnapshot, observed_at: int, max_pair_age_seconds: int) -> bool:
    if snapshot.pair_created_at is None:
        return False
    created_at = snapshot.pair_created_at
    if created_at > 10_000_000_000:
        created_at //= 1000
    age_seconds = observed_at - created_at
    return 0 <= age_seconds <= max_pair_age_seconds
