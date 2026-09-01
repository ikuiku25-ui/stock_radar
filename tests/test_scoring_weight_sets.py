from __future__ import annotations

from stock_radar.scoring.weight_sets import ensure_baseline_weight_set


def test_creates_baseline_weight_set_when_none_exists(empty_conn):
    weight_set_id = ensure_baseline_weight_set(empty_conn)
    row = empty_conn.execute(
        "SELECT weight_material, weight_supply_demand, weight_theme, "
        "training_period_start, evaluation_period_start "
        "FROM weight_sets WHERE weight_set_id = ?",
        (weight_set_id,),
    ).fetchone()
    assert row["weight_material"] == 50
    assert row["weight_supply_demand"] == 30
    assert row["weight_theme"] == 20
    assert row["training_period_start"] is None
    assert row["evaluation_period_start"] is None


def test_reuses_existing_baseline_weight_set(empty_conn):
    first_id = ensure_baseline_weight_set(empty_conn)
    second_id = ensure_baseline_weight_set(empty_conn)
    assert first_id == second_id
    count = empty_conn.execute("SELECT COUNT(*) AS n FROM weight_sets").fetchone()["n"]
    assert count == 1


def test_ignores_non_baseline_weight_sets(empty_conn):
    """A weight_set with a training/evaluation window (walk-forward,
    spec §8.4) is not a baseline and must not be reused as one."""
    conn = empty_conn
    conn.execute(
        """
        INSERT INTO weight_sets
            (weight_material, weight_supply_demand, weight_theme,
             training_period_start, training_period_end,
             evaluation_period_start, evaluation_period_end, created_at)
        VALUES (60, 25, 15, '2026-01-01', '2026-06-30', '2026-07-01', '2026-12-31', '2026-01-01T00:00:00+09:00')
        """
    )
    baseline_id = ensure_baseline_weight_set(conn)
    row = conn.execute(
        "SELECT weight_material FROM weight_sets WHERE weight_set_id = ?", (baseline_id,)
    ).fetchone()
    assert row["weight_material"] == 50
    count = empty_conn.execute("SELECT COUNT(*) AS n FROM weight_sets").fetchone()["n"]
    assert count == 2
