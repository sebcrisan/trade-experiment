from __future__ import annotations

from dataclasses import dataclass

from crypto_sim.repository import FirstSnapshot, LatestSnapshot, Repository, TokenState


@dataclass(frozen=True)
class TraderConfig:
    name: str
    family: str
    buy_market_cap: float
    requires_prior_threshold: float | None
    sell_multiple: float
    label: str
    description: str
    entry_rule: str


ENTRY_MARKET_CAP_MIN = 20_000.0
ENTRY_MARKET_CAP_MAX = 100_000.0
ENTRY_LIQUIDITY_MIN = 15_000.0
ENTRY_VOLUME_MIN = 25_000.0
DIRECT_TARGETS = (3.0, 3.5, 4.0, 4.5)
CONFIRMED_TARGETS = (1.5, 2.0, 2.5)


def _build_traders() -> tuple[TraderConfig, ...]:
    traders: list[TraderConfig] = []
    strategy_specs = (
        {
            "family": "Direct Entry",
            "prefix": "Direct",
            "buy_market_cap": ENTRY_MARKET_CAP_MIN,
            "requires_prior_threshold": None,
            "description_template": (
                "Enters only for tokens first detected between 20k and 100k market cap with at least 15k liquidity "
                "and 25k 24h volume. It buys on the first qualifying live snapshot at or above 20k market cap. "
                "After entry, it exits on the first snapshot that reaches {multiple:.1f}x of the entry market cap."
            ),
            "label_template": "Direct {multiple:.1f}x",
            "entry_rule": "threshold",
            "targets": DIRECT_TARGETS,
        },
        {
            "family": "2x Confirmation",
            "prefix": "Confirmed",
            "buy_market_cap": ENTRY_MARKET_CAP_MIN,
            "requires_prior_threshold": ENTRY_MARKET_CAP_MIN,
            "description_template": (
                "Uses only tokens first detected between 20k and 100k market cap with at least 15k liquidity "
                "and 25k 24h volume. It takes the first 20k-plus snapshot as a baseline. "
                "It only enters later, once market cap reaches 2x that baseline, and then exits on the first "
                "snapshot that reaches {multiple:.1f}x of its actual entry market cap."
            ),
            "label_template": "Confirmed {multiple:.1f}x",
            "entry_rule": "double_from_baseline",
            "targets": CONFIRMED_TARGETS,
        },
    )

    for spec in strategy_specs:
        for multiple in spec["targets"]:
            traders.append(
                TraderConfig(
                    name=f"{spec['prefix']}_{multiple:.1f}x",
                    family=spec["family"],
                    buy_market_cap=spec["buy_market_cap"],
                    requires_prior_threshold=spec["requires_prior_threshold"],
                    sell_multiple=multiple,
                    label=spec["label_template"].format(multiple=multiple),
                    description=spec["description_template"].format(multiple=multiple),
                    entry_rule=spec["entry_rule"],
                )
            )

    return tuple(traders)


TRADERS = _build_traders()


def evaluate_traders(
    repository: Repository,
    token_states: dict[str, TokenState],
    observed_at: int,
    position_size_usd: float,
    max_token_age_seconds: int,
) -> None:
    latest_snapshots = repository.latest_snapshots_for_tokens(token_states.keys())
    first_snapshots = repository.first_snapshots_for_tokens(token_states.keys())
    suspicious_tokens = {
        token_address: _latest_snapshot_looks_suspicious(repository, snapshot)
        for token_address, snapshot in latest_snapshots.items()
    }
    for config in TRADERS:
        for token_address in token_states:
            snapshot = latest_snapshots.get(token_address)
            market_cap = snapshot.market_cap if snapshot is not None else None
            if market_cap is None or market_cap <= 0:
                continue
            if suspicious_tokens.get(token_address):
                continue
            if repository.has_ever_position(config.name, token_address):
                continue
            first_snapshot = first_snapshots.get(token_address)
            if _should_open_position(repository, config, token_address, market_cap, first_snapshot):
                repository.open_position(
                    trader_name=config.name,
                    token_address=token_address,
                    opened_at=observed_at,
                    opened_market_cap=market_cap,
                    amount_usd=position_size_usd,
                )

    for position in repository.open_positions():
        state = token_states.get(position.token_address)
        if state is None:
            continue
        snapshot = latest_snapshots.get(position.token_address)
        current_market_cap = snapshot.market_cap if snapshot is not None else None
        if current_market_cap is None or current_market_cap <= 0:
            continue
        if suspicious_tokens.get(position.token_address):
            continue
        trader = _trader_config(position.trader_name)
        age_seconds = observed_at - state.first_seen_at
        multiple = current_market_cap / position.opened_market_cap

        if multiple >= trader.sell_multiple:
            proceeds = _position_value(position.amount_usd, position.opened_market_cap, snapshot)
            repository.close_position(
                position_id=position.id,
                closed_at=observed_at,
                closed_market_cap=current_market_cap,
                proceeds_usd=proceeds,
                pnl_usd=proceeds - position.amount_usd,
                close_reason=f"target_{trader.sell_multiple:.2f}x",
            )
        elif age_seconds >= max_token_age_seconds:
            proceeds = _position_value(position.amount_usd, position.opened_market_cap, snapshot)
            repository.close_position(
                position_id=position.id,
                closed_at=observed_at,
                closed_market_cap=current_market_cap,
                proceeds_usd=proceeds,
                pnl_usd=proceeds - position.amount_usd,
                close_reason="max_age_exit",
            )


def _position_value(amount_usd: float, opened_market_cap: float, snapshot: LatestSnapshot | None) -> float:
    if snapshot is None or snapshot.market_cap is None or opened_market_cap <= 0:
        return amount_usd
    current_value = amount_usd * (snapshot.market_cap / opened_market_cap)
    if snapshot.liquidity_usd is None:
        return current_value
    return min(current_value, max(float(snapshot.liquidity_usd), 0.0))


def _latest_snapshot_looks_suspicious(repository: Repository, snapshot: LatestSnapshot | None) -> bool:
    if snapshot is None:
        return False
    previous = repository.previous_snapshot_for_token(snapshot.token_address, snapshot.observed_at)
    return _is_extreme_snapshot_jump(previous, snapshot)


def _is_extreme_snapshot_jump(previous: LatestSnapshot | None, current: LatestSnapshot | None) -> bool:
    if previous is None or current is None:
        return False
    previous_market_cap = float(previous.market_cap or 0.0)
    current_market_cap = float(current.market_cap or 0.0)
    if previous_market_cap <= 0 or current_market_cap <= 0:
        return False

    market_cap_jump = current_market_cap / previous_market_cap
    if market_cap_jump < 100.0:
        return False

    price_jump = _positive_ratio(current.price_usd, previous.price_usd)
    liquidity_jump = _positive_ratio(current.liquidity_usd, previous.liquidity_usd)
    return (price_jump is not None and price_jump >= 100.0) or (
        liquidity_jump is not None and liquidity_jump >= 100.0
    )


def _positive_ratio(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous <= 0:
        return None
    return float(current) / float(previous)


def _trader_config(trader_name: str) -> TraderConfig:
    for trader in TRADERS:
        if trader.name == trader_name:
            return trader
    raise KeyError(f"Unknown trader {trader_name}")


def trader_configs() -> tuple[TraderConfig, ...]:
    return TRADERS


def _token_has_ever_reached(repository: Repository, token_address: str, market_cap_threshold: float) -> bool:
    row = repository.connection.execute(
        """
        SELECT 1
        FROM market_cap_history
        WHERE token_address = ? AND market_cap >= ?
        LIMIT 1
        """,
        (token_address, market_cap_threshold),
    ).fetchone()
    return row is not None


def _should_open_position(
    repository: Repository,
    config: TraderConfig,
    token_address: str,
    current_market_cap: float,
    first_snapshot: FirstSnapshot | None,
) -> bool:
    if not _passes_quality_filters(first_snapshot):
        return False
    if config.entry_rule == "threshold":
        return current_market_cap >= config.buy_market_cap

    if config.entry_rule == "double_from_baseline":
        baseline = _first_market_cap_at_or_above(repository, token_address, config.buy_market_cap)
        if baseline is None:
            return False
        return current_market_cap >= baseline * 2.0

    raise KeyError(f"Unknown entry rule {config.entry_rule}")


def _passes_quality_filters(first_snapshot: FirstSnapshot | None) -> bool:
    if first_snapshot is None or first_snapshot.market_cap is None:
        return False
    market_cap = float(first_snapshot.market_cap)
    liquidity = float(first_snapshot.liquidity_usd or 0.0)
    volume = float(first_snapshot.volume_h24 or 0.0)
    return (
        ENTRY_MARKET_CAP_MIN <= market_cap <= ENTRY_MARKET_CAP_MAX
        and liquidity >= ENTRY_LIQUIDITY_MIN
        and volume >= ENTRY_VOLUME_MIN
    )


def _first_market_cap_at_or_above(
    repository: Repository,
    token_address: str,
    market_cap_threshold: float,
) -> float | None:
    row = repository.connection.execute(
        """
        SELECT market_cap
        FROM market_cap_history
        WHERE token_address = ? AND market_cap >= ?
        ORDER BY observed_at ASC
        LIMIT 1
        """,
        (token_address, market_cap_threshold),
    ).fetchone()
    if row is None:
        return None
    return float(row["market_cap"])
