"""Mock data for the Phase 1 case-study tickers (spec §10.3, §12 Phase 1/2/3).

These four tickers are the fixed case-study set (dataset_tag='case_study')
used to verify that materials are fetched/classified/scored correctly.
They must never be used for statistical validation (spec §10.3) — that is
enforced at the query level (dataset_tag = 'statistical'), not here.

All values below are illustrative placeholders for exercising the schema,
not real market data.
"""

from __future__ import annotations

import sqlite3

CASE_STUDY_TICKERS = ["4840", "7743", "3987", "3907"]


def insert_mock_data(conn: sqlite3.Connection) -> None:
    """Insert a self-consistent mock dataset covering every table.

    Safe to call once on a freshly initialized database (relies on
    AUTOINCREMENT ids starting at 1). Does not commit; the caller decides
    when to commit.
    """
    _insert_companies(conn)
    disclosure_ids = _insert_disclosures(conn)
    _insert_price_data(conn)
    theme_ids = _insert_theme_keywords(conn)
    _insert_theme_hot_status(conn, theme_ids)
    weight_set_id = _insert_weight_set(conn)
    score_ids = _insert_scores(conn, disclosure_ids, weight_set_id)
    _insert_watchlist(conn, score_ids)
    _insert_outcome_tracking(conn, score_ids)
    _insert_backtest_run(conn, weight_set_id)


def _insert_companies(conn: sqlite3.Connection) -> None:
    companies = [
        ("4840", "サンプル銘柄A", "グロース", "情報・通信業", 8_500_000_000, 0.62, 3_200_000_000, "active", None, "2026-08-28T00:00:00+09:00"),
        ("7743", "サンプル銘柄B", "プライム", "精密機器", 210_000_000_000, 0.45, 95_000_000_000, "active", None, "2026-08-28T00:00:00+09:00"),
        ("3987", "サンプル銘柄C", "スタンダード", "サービス業", 4_100_000_000, 0.71, 2_800_000_000, "active", None, "2026-08-28T00:00:00+09:00"),
        ("3907", "サンプル銘柄D", "グロース", "情報・通信業", 6_300_000_000, 0.58, 1_900_000_000, "active", None, "2026-08-28T00:00:00+09:00"),
    ]
    conn.executemany(
        """
        INSERT INTO companies
            (ticker, company_name, market_segment, sector, market_cap_yen,
             float_shares_ratio, latest_annual_sales_yen, listing_status,
             delisted_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        companies,
    )


def _insert_disclosures(conn: sqlite3.Connection) -> list[int]:
    # (ticker, title, raw_text, disclosed_at, category, positive_raw,
    #  negative_raw, is_hard_block)
    rows = [
        (
            "4840", "業績予想の上方修正に関するお知らせ",
            "当社は本日、通期業績予想の上方修正を決議いたしました。修正率は営業利益で+35%です。",
            "2026-08-20T15:05:00+09:00", "A", 30, 0, 0,
        ),
        (
            "7743", "自己株式取得に関するお知らせ",
            "発行済株式総数の3.2%を上限として自己株式を取得することを決議しました。",
            "2026-08-21T15:30:00+09:00", "C", 18, 0, 0,
        ),
        (
            "3987", "特別損失の計上及び業績予想の下方修正に関するお知らせ",
            "一部資産について減損損失を計上し、通期業績予想を下方修正いたします。なお、主力製品が世界初の認証を取得しました。",
            "2026-08-22T15:10:00+09:00", "F,E", 15, -10, 0,
        ),
        (
            "3907", "民事再生法の適用申請に関するお知らせ",
            "当社は本日、東京地方裁判所に民事再生法の適用を申請いたしました。",
            "2026-08-25T16:00:00+09:00", "F", 0, -50, 1,
        ),
    ]

    disclosure_ids: list[int] = []
    for ticker, title, raw_text, disclosed_at, category, pos_raw, neg_raw, hard_block in rows:
        cur = conn.execute(
            """
            INSERT INTO disclosures
                (ticker, title, raw_text, pdf_url, disclosed_at,
                 market_available_at, system_available_at, fetched_at,
                 availability_confidence, category, positive_material_raw,
                 negative_penalty_raw, is_hard_block, dataset_tag)
            VALUES (?, ?, ?, NULL, ?, ?, ?, ?, 'HIGH', ?, ?, ?, ?, 'case_study')
            """,
            (
                ticker, title, raw_text, disclosed_at,
                disclosed_at,  # market_available_at ≒ disclosed_at
                disclosed_at,  # system_available_at: assume immediate detection in mock data
                disclosed_at,  # fetched_at
                category, pos_raw, neg_raw, hard_block,
            ),
        )
        disclosure_ids.append(cur.lastrowid)
    return disclosure_ids


def _insert_price_data(conn: sqlite3.Connection) -> None:
    rows = []
    for ticker, base_close, base_volume in [
        ("4840", 1250.0, 320_000),
        ("7743", 4870.0, 540_000),
        ("3987", 640.0, 210_000),
        ("3907", 88.0, 1_800_000),
    ]:
        for i, trade_date in enumerate(
            ["2026-08-17", "2026-08-18", "2026-08-19", "2026-08-20", "2026-08-21"]
        ):
            close = base_close * (1 + 0.01 * i)
            rows.append(
                (
                    ticker, trade_date,
                    close * 0.99, close * 1.02, close * 0.98, close,
                    base_volume + i * 5_000, base_volume,
                    f"{trade_date}T15:00:00+09:00", "close",
                )
            )
    conn.executemany(
        """
        INSERT INTO price_data
            (ticker, trade_date, open, high, low, close, volume,
             avg_volume_20d, market_snapshot_at, session_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    # One PTS reference row, kept physically separate from 'close' rows
    # per spec §8.2 (must never be joined into scoring queries).
    conn.execute(
        """
        INSERT INTO price_data
            (ticker, trade_date, open, high, low, close, volume,
             avg_volume_20d, market_snapshot_at, session_type)
        VALUES ('3907', '2026-08-25', 85.0, 90.0, 83.0, 87.0, 950000, NULL,
                '2026-08-25T19:30:00+09:00', 'pts_reference')
        """
    )


def _insert_theme_keywords(conn: sqlite3.Connection) -> list[int]:
    rows = [
        ("生成AI", r"生成AI|LLM|大規模言語モデル", "2026-01-01T00:00:00+09:00"),
        ("半導体", r"半導体|ウエハ|ファウンドリ", "2026-01-01T00:00:00+09:00"),
        ("再生医療", r"再生医療|iPS細胞|細胞治療", "2026-01-01T00:00:00+09:00"),
    ]
    theme_ids = []
    for theme_name, keyword_regex, created_at in rows:
        cur = conn.execute(
            """
            INSERT INTO theme_keywords (theme_name, keyword_regex, is_active, created_at)
            VALUES (?, ?, 1, ?)
            """,
            (theme_name, keyword_regex, created_at),
        )
        theme_ids.append(cur.lastrowid)
    return theme_ids


def _insert_theme_hot_status(conn: sqlite3.Connection, theme_ids: list[int]) -> None:
    trade_date = "2026-08-21"
    rows = [
        (trade_date, theme_ids[0], f"{trade_date}T15:00:00+09:00", 1),
        (trade_date, theme_ids[1], f"{trade_date}T15:00:00+09:00", 0),
        (trade_date, theme_ids[2], f"{trade_date}T15:00:00+09:00", 0),
    ]
    conn.executemany(
        """
        INSERT INTO theme_hot_status (trade_date, theme_id, theme_as_of_time, hot_flag)
        VALUES (?, ?, ?, ?)
        """,
        rows,
    )


def _insert_weight_set(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        """
        INSERT INTO weight_sets
            (weight_material, weight_supply_demand, weight_theme,
             training_period_start, training_period_end,
             evaluation_period_start, evaluation_period_end,
             created_at, notes)
        VALUES (50, 30, 20, NULL, NULL, NULL, NULL, ?, ?)
        """,
        (
            "2026-08-28T00:00:00+09:00",
            "Baseline weight set per spec §6.2 (unoptimized hypothesis weights).",
        ),
    )
    return cur.lastrowid


def _insert_scores(
    conn: sqlite3.Connection, disclosure_ids: list[int], weight_set_id: int
) -> list[int]:
    # material_score = 0 if is_hard_block else max(0, positive_raw + negative_raw)
    # (spec §8.3). Values chosen to line up with _insert_disclosures rows.
    rows = [
        # (ticker, disclosure_id, material, supply_demand, theme, rank, scored_at)
        ("4840", disclosure_ids[0], 30, 22, 8, "S", "2026-08-20T15:10:00+09:00"),
        ("7743", disclosure_ids[1], 18, 15, 4, "A", "2026-08-21T15:35:00+09:00"),
        ("3987", disclosure_ids[2], 5, 10, 2, "B", "2026-08-22T15:15:00+09:00"),
        ("3907", disclosure_ids[3], 0, 3, 0, "none", "2026-08-25T16:05:00+09:00"),
    ]
    score_ids = []
    for ticker, disclosure_id, material, supply, theme, rank, scored_at in rows:
        total = material + supply + theme
        cur = conn.execute(
            """
            INSERT INTO scores
                (disclosure_id, ticker, weight_set_id, material_score,
                 supply_demand_score, theme_score, total_score,
                 notification_rank, scored_at, scoring_basis_time, dataset_tag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'case_study')
            """,
            (
                disclosure_id, ticker, weight_set_id, material, supply,
                theme, total, rank, scored_at, scored_at,
            ),
        )
        score_ids.append(cur.lastrowid)
    return score_ids


def _insert_watchlist(conn: sqlite3.Connection, score_ids: list[int]) -> None:
    # Only S/A ranked scores (4840, 7743) get watchlisted, per spec §5 pipeline.
    rows = [
        ("4840", score_ids[0], "2026-08-20T15:10:00+09:00", "上方修正、規模比較で加点大"),
        ("7743", score_ids[1], "2026-08-21T15:35:00+09:00", "自社株買い、上限比率3.2%"),
    ]
    conn.executemany(
        "INSERT INTO watchlist (ticker, score_id, added_at, note) VALUES (?, ?, ?, ?)",
        rows,
    )


def _insert_outcome_tracking(conn: sqlite3.Connection, score_ids: list[int]) -> None:
    # One row per score (1:1, enforced by UNIQUE(score_id) — see schema.sql).
    rows = [
        ("4840", score_ids[0], 1290.0, 1340.0, 1275.0, 1310.0, 1262.5, 3.20, 6.20, 1.0, 1, 1, 0),
        ("7743", score_ids[1], 4900.0, 4950.0, 4860.0, 4920.0, 4918.7, 0.35, 1.65, -0.6, 0, 0, 0),
        ("3987", score_ids[2], 610.0, 615.0, 590.0, 598.0, 652.8, -6.55, -1.20, -9.60, 0, 0, 0),
        ("3907", score_ids[3], 40.0, 42.0, 35.0, 36.0, 89.0, -55.06, -52.81, -60.67, 0, 0, 0),
    ]
    conn.executemany(
        """
        INSERT INTO outcome_tracking
            (ticker, score_id, next_day_open, next_day_high, next_day_low,
             next_day_close, prev_close, gap_up_pct, max_intraday_gain_pct,
             max_intraday_loss_pct, hit_plus5pct, hit_plus10pct,
             hit_upper_limit, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [row + ("2026-08-26T15:00:00+09:00",) for row in rows],
    )


def _insert_backtest_run(conn: sqlite3.Connection, weight_set_id: int) -> int:
    cur = conn.execute(
        """
        INSERT INTO backtest_runs
            (run_name, confidence_mode, weight_set_id, dataset_tag,
             started_at, finished_at, notes)
        VALUES (?, 'HIGH_ONLY', ?, 'case_study', ?, ?, ?)
        """,
        (
            "phase1-case-study-smoke-run",
            weight_set_id,
            "2026-08-28T00:00:00+09:00",
            "2026-08-28T00:05:00+09:00",
            "Phase 1 mock-data sanity run, not a statistical backtest.",
        ),
    )
    return cur.lastrowid
