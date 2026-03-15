from __future__ import annotations

import sqlite3
import shutil
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from crypto_sim.db import connect, initialize_database


class DatabaseConnectionTests(unittest.TestCase):
    def test_connect_uses_existing_database_without_reinitializing(self) -> None:
        tmpdir = ROOT / "tests" / ".tmp" / f"db-{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        try:
            db_path = tmpdir / "crypto_sim.db"
            initialize_database(db_path)

            with sqlite3.connect(db_path) as connection:
                connection.execute("CREATE TABLE sentinel (value TEXT NOT NULL)")
                connection.execute("INSERT INTO sentinel (value) VALUES ('ok')")
                connection.commit()

            with connect(db_path) as connection:
                row = connection.execute("SELECT value FROM sentinel").fetchone()

            self.assertEqual(row["value"], "ok")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_read_only_connect_can_read_existing_database(self) -> None:
        tmpdir = ROOT / "tests" / ".tmp" / f"db-{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        try:
            db_path = tmpdir / "crypto_sim.db"
            initialize_database(db_path)

            with sqlite3.connect(db_path) as connection:
                connection.execute("CREATE TABLE sentinel (value TEXT NOT NULL)")
                connection.execute("INSERT INTO sentinel (value) VALUES ('ro')")
                connection.commit()

            with connect(db_path, read_only=True) as connection:
                row = connection.execute("SELECT value FROM sentinel").fetchone()

            self.assertEqual(row["value"], "ro")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
