import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from stock_radar.db.connection import init_db
from stock_radar.mock_data import insert_mock_data


@pytest.fixture
def empty_conn():
    """A freshly initialized in-memory DB with no data rows."""
    conn = init_db(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def seeded_conn(empty_conn):
    """An in-memory DB pre-populated with the Phase 1 mock dataset."""
    insert_mock_data(empty_conn)
    empty_conn.commit()
    return empty_conn
