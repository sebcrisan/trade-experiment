from __future__ import annotations

import argparse
from pathlib import Path

from crypto_sim.config import DEFAULT_DB_PATH, Settings
from crypto_sim.dashboard import DashboardServer
from crypto_sim.db import connect, initialize_database
from crypto_sim.repository import Repository
from crypto_sim.service import SimulationService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dexscreener-backed token tracker and simulator.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Initialize the SQLite database.")
    subparsers.add_parser("tick", help="Run one polling and simulation cycle.")

    run_parser = subparsers.add_parser("run", help="Run continuously.")
    run_parser.add_argument("--interval-seconds", type=int, default=60)
    run_parser.add_argument("--max-pair-age-seconds", type=int, default=30 * 60)

    dashboard_parser = subparsers.add_parser("dashboard", help="Run the local dashboard.")
    dashboard_parser.add_argument("--host", default="127.0.0.1")
    dashboard_parser.add_argument("--port", type=int, default=8000)

    subparsers.add_parser("report", help="Show trader performance.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init-db":
        initialize_database(args.db_path)
        print(f"Initialized database at {args.db_path}")
        return 0

    if args.command == "report":
        with connect(args.db_path) as connection:
            repository = Repository(connection)
            rows = repository.trader_report_rows()
        if not rows:
            print("No closed trades yet.")
            return 0
        for row in rows:
            print(
                f"{row['trader_name']}: trades={row['total_trades']} "
                f"spent=${row['total_spent']:.2f} proceeds=${row['total_proceeds']:.2f} "
                f"pnl=${row['total_pnl']:.2f}"
            )
        return 0

    if args.command == "dashboard":
        initialize_database(args.db_path)
        DashboardServer(args.db_path, host=args.host, port=args.port).serve()
        return 0

    settings = Settings(
        db_path=args.db_path,
        poll_interval_seconds=getattr(args, "interval_seconds", 60),
        max_pair_age_seconds=getattr(args, "max_pair_age_seconds", 30 * 60),
    )
    service = SimulationService(settings)

    if args.command == "tick":
        result = service.run_once()
        print(
            f"Cycle complete: tokens={result['tokens']} "
            f"snapshots={result['snapshots']} new_snapshots={result['new_snapshots']} "
            f"refreshed_snapshots={result['refreshed_snapshots']}"
        )
        return 0

    if args.command == "run":
        service.run_forever()
        return 0

    parser.error(f"Unknown command {args.command}")
    return 1
