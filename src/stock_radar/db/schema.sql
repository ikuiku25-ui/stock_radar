-- Stock Radar DB schema (v1.3, Phase 1)
-- Source of truth: docs/implementation_spec_v1.3.md §6.1
--
-- Deviations from the spec's literal DDL text (approved by user, Phase 0):
--   1. companies.listing_status:      added CHECK(...) — the spec's comment
--      names 'active'/'delisted'/'suspended' but the original DDL had no
--      constraint enforcing it.
--   2. scores.notification_rank:      added CHECK(...) — same gap, spec
--      comment names 'S'/'A'/'B'/'none'.
--   3. outcome_tracking.score_id:     added UNIQUE — spec §10.2 states the
--      scores<->outcome_tracking relationship is 1:0 or 1:1; the original
--      DDL allowed 1:many.
-- No table/column was renamed, removed, or retyped.

PRAGMA foreign_keys = ON;

CREATE TABLE companies (
    ticker                    TEXT PRIMARY KEY,
    company_name              TEXT NOT NULL,
    market_segment            TEXT,
    sector                    TEXT,
    market_cap_yen            INTEGER,
    float_shares_ratio        REAL,
    latest_annual_sales_yen   INTEGER,
    listing_status            TEXT NOT NULL DEFAULT 'active'
                              CHECK(listing_status IN ('active','delisted','suspended')),
    delisted_at               TEXT,
    updated_at                TEXT NOT NULL
);

CREATE TABLE disclosures (
    disclosure_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker                    TEXT NOT NULL REFERENCES companies(ticker),
    title                     TEXT NOT NULL,
    raw_text                  TEXT NOT NULL,
    pdf_url                   TEXT,
    disclosed_at              TEXT NOT NULL,               -- 企業がTDnetに提出した時刻
    market_available_at       TEXT NOT NULL,               -- 市場参加者一般が知り得た時刻（≒disclosed_at）
    system_available_at       TEXT NOT NULL,               -- Stock Radarが検知した時刻（バックテスト基準）
    fetched_at                TEXT NOT NULL,               -- 実取得時刻（ログ用）
    availability_confidence   TEXT NOT NULL DEFAULT 'UNKNOWN'
                              CHECK(availability_confidence IN ('HIGH','MEDIUM','LOW','UNKNOWN')),
    category                  TEXT,                        -- A〜F、カンマ区切り（初期実装）
    positive_material_raw     INTEGER NOT NULL DEFAULT 0,
    negative_penalty_raw      INTEGER NOT NULL DEFAULT 0,
    is_hard_block             INTEGER NOT NULL DEFAULT 0,  -- 存続性リスク等による強制0点
    dataset_tag               TEXT NOT NULL DEFAULT 'statistical'
                              CHECK(dataset_tag IN ('case_study','statistical'))
);

CREATE INDEX idx_disclosures_ticker_time ON disclosures(ticker, disclosed_at);
CREATE INDEX idx_disclosures_system_available_at ON disclosures(system_available_at);

CREATE TABLE price_data (
    ticker              TEXT NOT NULL REFERENCES companies(ticker),
    trade_date          TEXT NOT NULL,
    open                REAL,
    high                REAL,
    low                 REAL,
    close               REAL,
    volume              INTEGER,
    avg_volume_20d      REAL,
    market_snapshot_at  TEXT NOT NULL,      -- そのデータが確定した時刻
    session_type        TEXT NOT NULL DEFAULT 'close'
                        CHECK(session_type IN ('close','pts_reference')),
    PRIMARY KEY (ticker, trade_date, session_type)
);

CREATE TABLE theme_keywords (
    theme_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    theme_name     TEXT NOT NULL,
    keyword_regex  TEXT NOT NULL,
    is_active      INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT NOT NULL
);

CREATE TABLE theme_hot_status (
    trade_date        TEXT NOT NULL,
    theme_id          INTEGER NOT NULL REFERENCES theme_keywords(theme_id),
    theme_as_of_time  TEXT NOT NULL,   -- 値上がり率ランキング算出に使った基準時刻（大引け確定値のみ使用）
    hot_flag          INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (trade_date, theme_id)
);

CREATE TABLE weight_sets (
    weight_set_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    weight_material         INTEGER NOT NULL DEFAULT 50,
    weight_supply_demand    INTEGER NOT NULL DEFAULT 30,
    weight_theme            INTEGER NOT NULL DEFAULT 20,
    training_period_start   TEXT,        -- ウォークフォワードの学習期間（重み最適化を行う場合のみ使用）
    training_period_end     TEXT,
    evaluation_period_start TEXT,        -- 適用対象（未来）期間
    evaluation_period_end   TEXT,
    created_at              TEXT NOT NULL,
    notes                   TEXT
);

CREATE TABLE scores (
    score_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    disclosure_id        INTEGER NOT NULL REFERENCES disclosures(disclosure_id),
    ticker               TEXT NOT NULL REFERENCES companies(ticker),
    weight_set_id        INTEGER NOT NULL REFERENCES weight_sets(weight_set_id),
    material_score       INTEGER NOT NULL,
    supply_demand_score  INTEGER NOT NULL,
    theme_score          INTEGER NOT NULL,
    total_score          INTEGER NOT NULL,
    notification_rank    TEXT NOT NULL CHECK(notification_rank IN ('S','A','B','none')),
    scored_at            TEXT NOT NULL,
    scoring_basis_time   TEXT NOT NULL, -- system_available_atと一致させる
    dataset_tag          TEXT NOT NULL DEFAULT 'statistical'
                         CHECK(dataset_tag IN ('case_study','statistical'))
);

CREATE INDEX idx_scores_ticker ON scores(ticker);
CREATE INDEX idx_scores_rank ON scores(notification_rank, scored_at);

CREATE TABLE watchlist (
    watchlist_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker         TEXT NOT NULL REFERENCES companies(ticker),
    score_id       INTEGER NOT NULL REFERENCES scores(score_id),
    added_at       TEXT NOT NULL,
    note           TEXT
);

-- バックテスト専用。予測ロジックからは物理的に不可視（アプリケーション層で参照禁止を徹底）
CREATE TABLE outcome_tracking (
    outcome_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    score_id               INTEGER NOT NULL UNIQUE REFERENCES scores(score_id),
    ticker                 TEXT NOT NULL REFERENCES companies(ticker),
    next_day_open          REAL,
    next_day_high          REAL,
    next_day_low           REAL,
    next_day_close         REAL,
    prev_close             REAL,
    gap_up_pct             REAL,
    max_intraday_gain_pct  REAL,
    max_intraday_loss_pct  REAL,
    hit_plus5pct           INTEGER NOT NULL DEFAULT 0,
    hit_plus10pct          INTEGER NOT NULL DEFAULT 0,
    hit_upper_limit        INTEGER NOT NULL DEFAULT 0,
    recorded_at            TEXT NOT NULL
);

CREATE TABLE backtest_runs (
    run_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_name         TEXT NOT NULL,
    confidence_mode  TEXT NOT NULL CHECK(confidence_mode IN ('HIGH_ONLY','HIGH_MEDIUM')),
    weight_set_id    INTEGER NOT NULL REFERENCES weight_sets(weight_set_id),
    dataset_tag      TEXT NOT NULL DEFAULT 'statistical',
    started_at       TEXT NOT NULL,
    finished_at      TEXT,
    notes            TEXT
);
