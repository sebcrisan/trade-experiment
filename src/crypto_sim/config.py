from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_DB_PATH = Path("data") / "crypto_sim.db"


@dataclass(frozen=True)
class Settings:
    db_path: Path = DEFAULT_DB_PATH
    poll_interval_seconds: int = 60
    chain_id: str = "solana"
    position_size_usd: float = 10.0
    max_token_age_seconds: int = 24 * 60 * 60
    max_pair_age_seconds: int = 30 * 60
