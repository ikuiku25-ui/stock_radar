#!/usr/bin/env python3
"""CLI: create a Stock Radar SQLite DB and populate it with mock data.

Usage:
    python scripts/seed_mock_data.py [--db-path data/stock_radar_mock.db3] [--force]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stock_radar.db.connection import init_db  # noqa: E402
from stock_radar.mock_data import insert_mock_data  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        default="data/stock_radar_mock.db3",
        help="Path to the SQLite file to create (default: data/stock_radar_mock.db3)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the DB file if it already exists",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path)
    if db_path.exists():
        if not args.force:
            print(f"Error: {db_path} already exists. Use --force to overwrite.", file=sys.stderr)
            sys.exit(1)
        db_path.unlink()

    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = init_db(str(db_path))
    insert_mock_data(conn)
    conn.commit()
    conn.close()
    print(f"Mock data inserted into {db_path}")


if __name__ == "__main__":
    main()
