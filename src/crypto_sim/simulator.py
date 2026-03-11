from __future__ import annotations

from dataclasses import dataclass

from crypto_sim.repository import Repository, TokenState


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


MAX_TARGET_MARKET_CAP = 989_000.0
MULTIPLE_STEP = 0.5
MIN_SELL_MULTIPLE = 1.5


def _build_traders() -> tuple[TraderConfig, ...]:
    traders: list[TraderConfig] = []
    strategy_specs = (
        {
            "family": "Direct Entry",
            "prefix": "Direct",
            "buy_market_cap": 20_000.0,
            "requires_prior_threshold": None,
            "description_template": (
                "Buys immediately when a token is first observed at or above 20k market cap, "
                "then sells on the first {multiple:.1f}x move."
            ),
            "label_template": "Direct {multiple:.1f}x",
            "entry_rule": "threshold",
        },
        {
            "family": "2x Confirmation",
            "prefix": "Confirmed",
            "buy_market_cap": 20_000.0,
            "requires_prior_threshold": 20_000.0,
            "description_template": (
                "Waits for the first observed snapshot at or above 20k market cap, then buys only after "
                "the token later doubles from that observed level. After entry, it sells on the first "
                "{multiple:.1f}x move."
            ),
            "label_template": "Confirmed {multiple:.1f}x",
            "entry_rule": "double_from_baseline",
        },
    )

    for spec in strategy_specs:
        max_multiple = MAX_TARGET_MARKET_CAP / spec["buy_market_cap"]
        multiple = MIN_SELL_MULTIPLE
        while multiple <= max_multiple + 1e-9:
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
            multiple += MULTIPLE_STEP

    return tuple(traders)


TRADERS = _build_traders()


def evaluate_traders(
    repository: Repository,
    token_states: dict[str, TokenState],
    observed_at: int,
    position_size_usd: float,
    max_token_age_seconds: int,
) -> None:
    history_caps = repository.latest_history_for_tokens(token_states.keys())
    for config in TRADERS:
        for token_address in token_states:
            market_cap = history_caps.get(token_address)
            if market_cap is None or market_cap <= 0:
                continue
            if repository.has_ever_position(config.name, token_address):
                continue
            if _should_open_position(repository, config, token_address, market_cap):
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
        current_market_cap = history_caps.get(position.token_address)
        if current_market_cap is None or current_market_cap <= 0:
            continue
        trader = _trader_config(position.trader_name)
        age_seconds = observed_at - state.first_seen_at
        multiple = current_market_cap / position.opened_market_cap

        if multiple >= trader.sell_multiple:
            proceeds = position.amount_usd * multiple
            repository.close_position(
                position_id=position.id,
                closed_at=observed_at,
                closed_market_cap=current_market_cap,
                proceeds_usd=proceeds,
                pnl_usd=proceeds - position.amount_usd,
                close_reason=f"target_{trader.sell_multiple:.2f}x",
            )
        elif age_seconds >= max_token_age_seconds:
            proceeds = position.amount_usd * multiple
            repository.close_position(
                position_id=position.id,
                closed_at=observed_at,
                closed_market_cap=current_market_cap,
                proceeds_usd=proceeds,
                pnl_usd=proceeds - position.amount_usd,
                close_reason="max_age_exit",
            )


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
) -> bool:
    if config.entry_rule == "threshold":
        return current_market_cap >= config.buy_market_cap

    if config.entry_rule == "double_from_baseline":
        baseline = _first_market_cap_at_or_above(repository, token_address, config.buy_market_cap)
        if baseline is None:
            return False
        return current_market_cap >= baseline * 2.0

    raise KeyError(f"Unknown entry rule {config.entry_rule}")


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
