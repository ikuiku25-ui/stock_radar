"""Tests for get_or_init_connection (spec §12 Phase 7: a fresh GitHub
Actions runner has no prior cache on its very first run)."""

from __future__ import annotations

from stock_radar.db.connection import get_or_init_connection


def test_creates_schema_on_fresh_database():
    conn = get_or_init_connection(":memory:")
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'companies'"
    ).fetchone()
    assert row is not None


def test_does_not_raise_on_already_initialized_database(tmp_path):
    db_path = str(tmp_path / "test.db3")
    get_or_init_connection(db_path).close()

    conn = get_or_init_connection(db_path)  # must not raise "table already exists"
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'companies'").fetchone()
    assert row is not None


def test_preserves_existing_data(tmp_path):
    db_path = str(tmp_path / "test.db3")
    conn = get_or_init_connection(db_path)
    conn.execute(
        "INSERT INTO companies (ticker, company_name, listing_status, updated_at) "
        "VALUES ('4840', 'Test Co', 'active', '2026-08-28T00:00:00+09:00')"
    )
    conn.commit()
    conn.close()

    conn2 = get_or_init_connection(db_path)
    row = conn2.execute("SELECT company_name FROM companies WHERE ticker = '4840'").fetchone()
    assert row["company_name"] == "Test Co"
