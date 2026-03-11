from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


BASE_URL = "https://api.dexscreener.com"


@dataclass(frozen=True)
class TokenProfile:
    chain_id: str
    token_address: str
    url: str | None


@dataclass(frozen=True)
class PairSnapshot:
    chain_id: str
    token_address: str
    pair_address: str
    dex_id: str | None
    symbol: str | None
    name: str | None
    price_usd: float | None
    market_cap: float | None
    fdv: float | None
    liquidity_usd: float | None
    volume_h24: float | None
    pair_created_at: int | None
    pair_url: str | None


class DexscreenerClient:
    def __init__(self, timeout_seconds: int = 20, pause_seconds: float = 0.25) -> None:
        self.timeout_seconds = timeout_seconds
        self.pause_seconds = pause_seconds

    def _get_json(self, path: str) -> object:
        request = Request(
            f"{BASE_URL}{path}",
            headers={
                "Accept": "application/json",
                "User-Agent": "crypto-sim/0.1",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.load(response)
        except HTTPError as exc:
            raise RuntimeError(f"Dexscreener HTTP error {exc.code} for {path}") from exc
        except URLError as exc:
            raise RuntimeError(f"Dexscreener network error for {path}: {exc.reason}") from exc

    def latest_token_profiles(self) -> list[TokenProfile]:
        payload = self._get_json("/token-profiles/latest/v1")
        profiles: list[TokenProfile] = []
        for item in payload:
            profiles.append(
                TokenProfile(
                    chain_id=item.get("chainId", ""),
                    token_address=item.get("tokenAddress", ""),
                    url=item.get("url"),
                )
            )
        return profiles

    def token_pairs(self, chain_id: str, token_addresses: Iterable[str]) -> list[PairSnapshot]:
        addresses = [address for address in token_addresses if address]
        if not addresses:
            return []
        path = f"/tokens/v1/{quote(chain_id)}/{quote(','.join(addresses))}"
        payload = self._get_json(path)
        snapshots: list[PairSnapshot] = []
        for item in payload:
            base_token = item.get("baseToken") or {}
            liquidity = item.get("liquidity") or {}
            volume = item.get("volume") or {}
            snapshots.append(
                PairSnapshot(
                    chain_id=item.get("chainId", chain_id),
                    token_address=base_token.get("address", ""),
                    pair_address=item.get("pairAddress", ""),
                    dex_id=item.get("dexId"),
                    symbol=base_token.get("symbol"),
                    name=base_token.get("name"),
                    price_usd=_to_float(item.get("priceUsd")),
                    market_cap=_to_float(item.get("marketCap")),
                    fdv=_to_float(item.get("fdv")),
                    liquidity_usd=_to_float(liquidity.get("usd")),
                    volume_h24=_to_float(volume.get("h24")),
                    pair_created_at=item.get("pairCreatedAt"),
                    pair_url=item.get("url"),
                )
            )
        if self.pause_seconds:
            time.sleep(self.pause_seconds)
        return snapshots


def _to_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
