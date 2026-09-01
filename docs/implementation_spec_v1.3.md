# Stock Radar Implementation Specification v1.3
（v1.2レビュー結果を反映した、Claude Code実装用の最終ドラフト。**本ドキュメント自体はコード実装を含まない。**）

---

## 1. v1.2 総合評価

v1.2は「材料50／需給30／テーマ20」という骨格、3時刻モデルの着想、SQLiteスキーマの分離設計として妥当な出発点だった。しかし実装可能レベルには未達で、以下4点が致命的だった。

1. **`available_at`が「市場が知り得た時刻」と「システムが検知した時刻」を混同**しており、バックテストの意味が曖昧だった。
2. **場中開示に当日の未確定データを混入させるリスク**（look-ahead bias）が構造的に防がれていなかった。
3. **ネガティブキーワード一致で開示全体を強制0点にする**ため、複合材料（減損＋上方修正など）の情報が失われていた。
4. **Survivorship bias（上場廃止銘柄の欠落）**への対応が設計に存在しなかった。

これらはSTEP 2〜4で構造的に解消済み（本ドキュメントに統合）。v1.3は「ランキング用ヒューリスティック」として100点スコアを再定義し、統計的検証を後段のバックテストフェーズに委ねる設計に改めた。

---

## 2. Critical Issues（実装前に必ず解決すべき事項）

| # | Issue | 影響 | v1.3での対応 |
|---|---|---|---|
| C1 | `available_at`の概念混同 | バックテストの意味が破綻する | `market_available_at` / `system_available_at` に分離（§8.1） |
| C2 | 場中開示の未来データ混入 | Look-ahead biasによりバックテスト成績が過大評価される | `market_snapshot_at`とセッション判定ロジックで物理的に遮断（§8.2） |
| C3 | ネガティブ強制ゼロによる情報損失 | 複合材料が誤って0点評価される | `HARD_BLOCK` / `SOFT_NEGATIVE`分離（§8.3） |
| C4 | Survivorship bias未対応 | バックテストの成功率が過大評価される | `companies.listing_status`/`delisted_at`導入 |
| C5 | TDnetのリアルタイム取得手段が未確定 | システムの心臓部が「取得できない」可能性 | §4で無料手段を整理し、非公式スクレイピングの前提条件を明記 |
| C6 | 4銘柄ケーススタディとの過学習リスク | 辞書がその4銘柄に最適化され汎化しない | ケーススタディ用データと統計検証用データセットをDB上で論理分離（§10） |
| C7 | 重み（50/30/20）の最適化に伴うLook-ahead | 未来データで最適化した重みを過去に適用してしまう | ウォークフォワード方式＋`weight_set`バージョン管理（§9） |

---

## 3. 修正すべき設計（v1.2 → v1.3 差分サマリ）

### 3.1 時刻モデル

| v1.2 | v1.3 |
|---|---|
| `disclosed_at` | 変更なし（TDnet提出時刻） |
| `available_at`（曖昧） | `market_available_at`（≒disclosed_at）＋`system_available_at`（自システムの検知時刻）に分離 |
| `fetched_at` | 変更なし（ログ用） |
| なし | `availability_confidence`（HIGH/MEDIUM/LOW/UNKNOWN）新設 |

### 3.2 スコアリング

| v1.2 | v1.3 |
|---|---|
| ネガティブ一致で強制0点 | `HARD_BLOCK`（存続性リスクのみ強制0点）／`SOFT_NEGATIVE`（減点のみ、ポジティブと共存） |
| カテゴリEのみ規模比較（受注額÷売上高） | 全カテゴリで「会社規模との比較」「過去実績との比較」を可能な範囲で導入（§7） |
| 固定配点（材料50/需給30/テーマ20） | 同じ配点だが「仮説」として明記。ランキング用の暫定重みであり、確率的意味は持たせない（§9） |

### 3.3 データ・DB

| v1.2 | v1.3 |
|---|---|
| `price_data`にセッション区分なし | `market_snapshot_at`/`session_type`追加、場中データの誤用を物理的に防止 |
| `companies`に上場ステータスなし | `listing_status`/`delisted_at`追加 |
| バックテスト実行のバージョン管理なし | `backtest_runs`テーブル新設（confidence_mode等を記録） |
| 重みのバージョン管理なし | `weight_sets`テーブル新設（§9） |
| 4銘柄と統計検証データの区別なし | `disclosures`/`scores`に`dataset_tag`（'case_study' / 'statistical'）を追加 |

---

## 4. 無料で実現可能な範囲（Stock Radar ZEROの土台）

### 4.1 データソース比較表

要確認の項目は推測せず明記する。

| データソース | 用途 | 無料か | API有無 | 取得頻度/遅延 | 過去データ | 個人利用可否 | 規約リスク | 安定性 |
|---|---|---|---|---|---|---|---|---|
| **JPX公式 TDnet APIサービス** | 適時開示（本文・PDF） | ❌ 有料（基本料+従量課金、目安月額数万〜24万円規模） | ○（公式REST） | リアルタイム | 提供可（契約次第） | ○ | 低（正式契約） | 高 |
| **J-Quants API（JPX公式・無料プラン）** | 株価・財務・上場情報 | ✅ 無料プランあり | ○ | **無料プランは提供データが約12週間（3ヶ月弱）遅延**、過去2年分に限定 | 限定的 | 個人の私的利用のみ可、第三者配信・アプリ提供は禁止 | 低（規約明記） | 高 |
| **J-Quants TDnetアドオン** | 適時開示（数分〜数十分遅延で取得） | ❌ 有料アドオン（Lightプラン以上が前提） | ○ | 遅延数分〜1時間程度 | 過去5年分 | 契約次第 | 低 | 中〜高 |
| **TDnet適時開示情報閲覧サービス（公式Webページ）** | 適時開示一覧・PDF | ✅ 閲覧自体は無料 | ✕（非公式スクレイピング前提） | 直接アクセスならリアルタイム | 原則1ヶ月間のみ公開 | 個人の情報収集目的の範囲かは**要確認**（利用規約に自動取得の可否の明記があるか未確認） | **中〜高（要確認）**。過度なアクセスは負荷とみなされる可能性、再配布は不可が原則 | 中（サイト構造変更リスク） |
| **個人運営の非公式TDnet API（例: やのしん氏提供）** | 適時開示の簡易JSON化 | ✅ 無料 | ○（非公式） | ほぼリアルタイム | 一部 | 個人利用前提、常識的な利用が条件 | **高**：個人運営のため予告なく停止し得る。公式のお墨付きなし | **低**（単一障害点） |
| **yfinance（Yahoo Financeの非公式ラッパー）** | 日足OHLCV・出来高 | ✅ 無料・キー不要 | ○（非公式ライブラリ） | 日足は概ね当日反映、リアルタイムは15分程度遅延 | 豊富（長期） | 個人の分析用途は広く使われているが、**Yahoo Finance自体の利用規約上の位置付けは要確認**（大量・自動取得への制限がある可能性） | 中（要確認） | 中（Yahoo側の仕様変更で頻繁に不具合報告あり） |
| **EDINET API（金融庁）** | 有価証券報告書等（適時開示より低頻度） | ✅ 無料・公式 | ○ | 提出後速やかに公開 | 豊富 | ○ | 低 | 高 |
| **証券会社の無料ツール（SBI証券サイト等）** | 株価確認・最終判断 | ✅ 無料（口座保有前提） | ✕（自動化禁止） | リアルタイム（画面上） | - | 人間の手動確認のみ、自動ログイン・スクレイピングは規約違反 | 高（自動化した場合） | - |

### 4.2 結論：0円でどこまでできるか

- **適時開示のほぼリアルタイム取得**：公式の無料APIでは不可能（J-Quants無料プランは約3ヶ月遅延のため翌営業日シグナル検出には使えない）。実現するには、①TDnet公式Webページの直接ポーリング（非公式スクレイピング、規約要確認）、または②個人運営の非公式APIの利用（安定性リスクあり）のいずれかが必要。**この2つのいずれも「0円だが規約・安定性のグレーゾーン」であることをユーザーに明示した上で採用する。**
- **株価・出来高（日足、大引け後）**：yfinanceで概ね無料実現可能。ただし利用規約上のリスクは要確認とし、個人の非営利分析用途に限定して利用する。
- **企業規模（時価総額・売上高等）との比較**：J-Quants無料プラン（財務情報部分）またはEDINETから取得可能。
- **PTS・リアルタイム板情報**：無料かつ規約順守で安定的に取得する手段が確認できず、v1.3でもTier 3（人間確認）のまま据え置く。

### 4.3 有料化を検討する条件（無料版で不足した場合のみ）

| 不足する事態 | 導入候補 | 条件 |
|---|---|---|
| 非公式TDnet取得元が停止し、適時開示が取得できなくなった | J-Quants TDnetアドオン（有料） | 無料の代替手段（他の非公式ソース含む）が3ヶ月以上見つからない場合 |
| yfinanceの日本株データが不安定・欠損が頻発する | J-Quants有料プラン（財務・株価） | 無料プランの遅延（3ヶ月）がバックテスト用途にすら支障をきたす場合 |
| バックテスト件数が増え、正規表現辞書だけでは精度が頭打ちになる | LLM API（分類補助） | ルールベースの適合率が一定水準（要合意）を下回り続けた場合のみ、Phase 8として検討 |

---

## 5. Stock Radar ZERO 構成（最小構成の定義）

- 言語・実行環境：Python（ローカル実行、Windows PC）
- DB：SQLite3
- データ取得：TDnet（非公式手段、Interval厳守）＋yfinance（日足）
- 分類：正規表現・辞書ベース（LLM APIは必須にしない）
- 通知：メール／デスクトップ通知等、ローカルで完結する手段（外部有料サービス不要）
- パイプライン：

```
収集（TDnet+yfinance）
  ↓
正規化（NFKC正規化、3時刻モデルの記録）
  ↓
材料分類（正規表現辞書、カテゴリA〜F判定）
  ↓
スコアリング（材料/需給/テーマ、HARD_BLOCK/SOFT_NEGATIVE適用）
  ↓
ランキング（S/A/B/記録のみ）
  ↓
通知（S/Aランクのみ）
  ↓
バックテスト（outcome_tracking、統計検証データセットのみ対象）
```

---

## 6. v1.3 仕様（統合DDL・ロジック要点）

### 6.1 DDL（v1.2からの差分を統合した最終形）

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE companies (
    ticker                    TEXT PRIMARY KEY,
    company_name               TEXT NOT NULL,
    market_segment              TEXT,
    sector                      TEXT,
    market_cap_yen               INTEGER,
    float_shares_ratio           REAL,
    latest_annual_sales_yen       INTEGER,
    listing_status                TEXT NOT NULL DEFAULT 'active',  -- 'active'/'delisted'/'suspended'
    delisted_at                    TEXT,
    updated_at                     TEXT NOT NULL
);

CREATE TABLE disclosures (
    disclosure_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker                        TEXT NOT NULL REFERENCES companies(ticker),
    title                         TEXT NOT NULL,
    raw_text                      TEXT NOT NULL,
    pdf_url                       TEXT,
    disclosed_at                   TEXT NOT NULL,               -- 企業がTDnetに提出した時刻
    market_available_at             TEXT NOT NULL,               -- 市場参加者一般が知り得た時刻（≒disclosed_at）
    system_available_at              TEXT NOT NULL,               -- Stock Radarが検知した時刻（バックテスト基準）
    fetched_at                        TEXT NOT NULL,               -- 実取得時刻（ログ用）
    availability_confidence            TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK(availability_confidence IN ('HIGH','MEDIUM','LOW','UNKNOWN')),
    category                            TEXT,                       -- A〜F、カンマ区切り（初期実装）
    positive_material_raw                INTEGER NOT NULL DEFAULT 0,
    negative_penalty_raw                  INTEGER NOT NULL DEFAULT 0,
    is_hard_block                          INTEGER NOT NULL DEFAULT 0, -- 存続性リスク等による強制0点
    dataset_tag                             TEXT NOT NULL DEFAULT 'statistical' CHECK(dataset_tag IN ('case_study','statistical'))
);

CREATE INDEX idx_disclosures_ticker_time ON disclosures(ticker, disclosed_at);
CREATE INDEX idx_disclosures_system_available_at ON disclosures(system_available_at);

CREATE TABLE price_data (
    ticker              TEXT NOT NULL REFERENCES companies(ticker),
    trade_date          TEXT NOT NULL,
    open                REAL, high REAL, low REAL, close REAL,
    volume              INTEGER,
    avg_volume_20d       REAL,
    market_snapshot_at    TEXT NOT NULL,      -- そのデータが確定した時刻
    session_type          TEXT NOT NULL DEFAULT 'close' CHECK(session_type IN ('close','pts_reference')),
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
    trade_date       TEXT NOT NULL,
    theme_id          INTEGER NOT NULL REFERENCES theme_keywords(theme_id),
    theme_as_of_time    TEXT NOT NULL,   -- 値上がり率ランキング算出に使った基準時刻（大引け確定値のみ使用）
    hot_flag            INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (trade_date, theme_id)
);

CREATE TABLE weight_sets (
    weight_set_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    weight_material      INTEGER NOT NULL DEFAULT 50,
    weight_supply_demand   INTEGER NOT NULL DEFAULT 30,
    weight_theme            INTEGER NOT NULL DEFAULT 20,
    training_period_start    TEXT,        -- ウォークフォワードの学習期間（重み最適化を行う場合のみ使用）
    training_period_end       TEXT,
    evaluation_period_start    TEXT,       -- 適用対象（未来）期間
    evaluation_period_end       TEXT,
    created_at                   TEXT NOT NULL,
    notes                          TEXT
);

CREATE TABLE scores (
    score_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    disclosure_id          INTEGER NOT NULL REFERENCES disclosures(disclosure_id),
    ticker                   TEXT NOT NULL REFERENCES companies(ticker),
    weight_set_id             INTEGER NOT NULL REFERENCES weight_sets(weight_set_id),
    material_score              INTEGER NOT NULL,
    supply_demand_score           INTEGER NOT NULL,
    theme_score                     INTEGER NOT NULL,
    total_score                       INTEGER NOT NULL,
    notification_rank                  TEXT NOT NULL,   -- 'S'/'A'/'B'/'none'
    scored_at                            TEXT NOT NULL,
    scoring_basis_time                     TEXT NOT NULL, -- system_available_atと一致させる
    dataset_tag                              TEXT NOT NULL DEFAULT 'statistical'
);

CREATE INDEX idx_scores_ticker ON scores(ticker);
CREATE INDEX idx_scores_rank ON scores(notification_rank, scored_at);

CREATE TABLE watchlist (
    watchlist_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker           TEXT NOT NULL REFERENCES companies(ticker),
    score_id           INTEGER NOT NULL REFERENCES scores(score_id),
    added_at             TEXT NOT NULL,
    note                   TEXT
);

-- バックテスト専用。予測ロジックからは物理的に不可視（アプリケーション層で参照禁止を徹底）
CREATE TABLE outcome_tracking (
    outcome_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    score_id                 INTEGER NOT NULL REFERENCES scores(score_id),
    ticker                     TEXT NOT NULL REFERENCES companies(ticker),
    next_day_open               REAL, next_day_high REAL, next_day_low REAL, next_day_close REAL,
    prev_close                    REAL,
    gap_up_pct                      REAL,
    max_intraday_gain_pct             REAL,
    max_intraday_loss_pct               REAL,
    hit_plus5pct                          INTEGER NOT NULL DEFAULT 0,
    hit_plus10pct                          INTEGER NOT NULL DEFAULT 0,
    hit_upper_limit                          INTEGER NOT NULL DEFAULT 0,
    recorded_at                                TEXT NOT NULL
);

CREATE TABLE backtest_runs (
    run_id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_name                 TEXT NOT NULL,
    confidence_mode           TEXT NOT NULL CHECK(confidence_mode IN ('HIGH_ONLY','HIGH_MEDIUM')),
    weight_set_id               INTEGER NOT NULL REFERENCES weight_sets(weight_set_id),
    dataset_tag                   TEXT NOT NULL DEFAULT 'statistical',
    started_at                      TEXT NOT NULL,
    finished_at                       TEXT,
    notes                               TEXT
);
```

### 6.2 スコアリング要点（統合版）

- **材料**（0〜50点）: カテゴリA〜Fの基礎配点＋規模・過去実績比較による加点（§7）。`HARD_BLOCK`該当時は`material_score=0`固定。それ以外は`positive_material_raw + negative_penalty_raw`（下限0）。
- **需給**（0〜30点）: `volume_ratio`は必ず「開示日を含まない過去20営業日平均」を分母とし、分子は開示日の**確定済み**出来高（大引け後開示が前提のため当日確定値を使用可）。小型株ボーナスは「仮説」であり、バックテストで検証すべき対象として明示する（§7.3）。
- **テーマ**（0〜20点）: `theme_as_of_time`は必ずその日の大引け確定値の時点とし、開示評価時点で未確定な情報（翌日の値動き等）を混入させない。

---

## 7. 材料型スコアの妥当性検証方針（STEP5対応）

各カテゴリについて「翌営業日の株価変動との関係」を単なる仮説ではなく検証可能な設計にする。

| カテゴリ | 見出し一致 | 本文の数値抽出 | 規模比較 | 過去実績との比較 |
|---|---|---|---|---|
| 上方修正 | ✓ | 修正率(%) | 時価総額 | 過去の修正履歴（サプライズ頻度） |
| 増配 | ✓ | 増配率 | 配当性向 | 過去の配当推移 |
| 自社株買い | ✓ | 取得予定比率(%) | 発行済株式数比 | 過去の自社株買い実施有無 |
| 大型受注・契約 | ✓ | 契約金額 | 直近期売上高比 | 過去の受注規模との比較 |
| M&A・資本業務提携 | ✓ | 出資比率・取得額 | 自社時価総額比 | 相手企業の知名度（テーマ加点と連動） |
| 新製品・特許・承認 | ✓ | （定性情報が中心） | 業界内シェア（取得困難な場合は除外） | 「世界初/業界初」等の訴求表現の有無 |
| 株式分割 | ✓ | 分割比率 | - | 同時発表の有無（増配等） |

**方針**: v1.3では「見出し＋数値＋規模比較」までを実装対象とし、「過去実績との比較」は`companies`テーブルの財務データ拡充が前提となるため、**Phase 4以降で段階的に追加する拡張項目**として明記する（初期実装の必須要件にはしない）。

---

## 8. Look-ahead bias 対策（統合）

### 8.1 3時刻モデルの最終定義

- `disclosed_at`: TDnet提出時刻（企業視点）
- `market_available_at`: 市場参加者一般が知り得た時刻（≒`disclosed_at`、TDnetは即時掲載のため）
- `system_available_at`: Stock Radarのポーリングが実際にその開示を検知した時刻（**バックテストは必ずこれを基準にする**）
- `fetched_at`: 実際のHTTPリクエスト実行時刻（ログ専用）
- `availability_confidence`: `HIGH`/`MEDIUM`/`LOW`/`UNKNOWN`。バックテストは`HIGH_ONLY`と`HIGH_MEDIUM`のモード切り替えを可能にする。

### 8.2 市場データの時点管理

- 開示が場中（15:00より前）の場合、当日の`price_data`（未確定）は一切参照しない。前営業日までの確定データのみ使用。
- 開示が大引け後（15:00〜）の場合（Stock Radarの主対象）、当日確定の`close`/`volume`を使用可。
- `volume_ratio`の分母（過去20営業日平均）は常に開示日を含めない。
- PTSデータは`session_type='pts_reference'`として物理的に分離し、スコアリングクエリからは常に除外する。

### 8.3 ネガティブ材料判定の再設計

```
HARD_BLOCK（強制0点、最優先） … 民事再生・破産手続・上場廃止・不適切会計・有報訂正等、存続性・信頼性に関わるもののみ
SOFT_NEGATIVE（減点、ポジティブと共存） … 下方修正・減額・減損・特別損失等
material_score = HARD_BLOCK該当なら0、そうでなければ max(0, positive_material_raw + negative_penalty_raw)
```

### 8.4 重み最適化のLook-ahead防止（STEP9対応）

- `weight_sets`テーブルで`training_period`（重み最適化に使った期間）と`evaluation_period`（その重みを適用する対象期間）を分離管理する。
- **ウォークフォワード原則**: `evaluation_period_start`は必ず`training_period_end`より後でなければならない（アプリケーション層でバリデーション必須）。
- ある時点の重みを、その学習期間より前の過去データに逆適用することを禁止する（`backtest_runs`は使用した`weight_set_id`を必ず記録し、期間の整合性をチェックするクエリを用意する）。

---

## 9. 100点スコアの意味の再定義（STEP8対応）

- v1.3時点でのスコアは**「候補銘柄の優先順位を決めるためのランキングヒューリスティック」**であり、「Score 90 = 90%の確率で上昇」という統計的意味は一切持たない。
- 材料50/需給30/テーマ20の配点比率は**未検証の仮説**として明記し、実運用データが蓄積された段階で以下の分析を行う。

```sql
-- スコア帯ごとの実績集計クエリ例（Phase 6以降）
SELECT
  CASE
    WHEN s.total_score >= 90 THEN '90+'
    WHEN s.total_score >= 80 THEN '80-89'
    WHEN s.total_score >= 70 THEN '70-79'
    ELSE '<70'
  END AS score_band,
  COUNT(*) AS n,
  AVG(o.max_intraday_gain_pct) AS avg_max_gain,
  AVG(CASE WHEN o.hit_plus5pct THEN 1.0 ELSE 0 END) AS hit_rate_5pct,
  AVG(CASE WHEN o.hit_upper_limit THEN 1.0 ELSE 0 END) AS hit_rate_stop_high
FROM scores s
JOIN outcome_tracking o ON o.score_id = s.score_id
WHERE s.dataset_tag = 'statistical'   -- 4銘柄ケーススタディは除外
GROUP BY score_band;
```

---

## 10. バックテスト設計（Outcome設計含む、STEP10・STEP11対応）

### 10.1 outcome_tracking収録項目（確定）

翌営業日: 始値・高値・安値・終値／ギャップアップ率／最大上昇率／最大下落率／+5%到達／+10%到達／S高到達（`hit_upper_limit`）。§6.1のDDLに反映済み。

### 10.2 論理的・物理的分離

- 予測ロジック（材料分類・スコアリング）は`outcome_tracking`テーブルを**参照するコードパスを持たない**ことをコードレビュー時のチェック項目とする（実装規約として明文化）。
- `scores`テーブルと`outcome_tracking`テーブルは1対0または1対1の関係とし、スコア算出処理と結果記録処理は別モジュール・別実行タイミングとする。

### 10.3 4銘柄ケーススタディの扱い（STEP11）

- `disclosures.dataset_tag`/`scores.dataset_tag`により`'case_study'`（4840, 7743, 3987, 3907）と`'statistical'`（それ以外の全銘柄）を分離。
- 統計的な有効性評価（§9のクエリ等）は**必ず`dataset_tag = 'statistical'`のみを対象とする**。4銘柄は「材料が正しく取得・分類・スコア化できるかの動作確認」のみに用途を限定し、「モデルが当たった／外れた」の判断材料にはしない。

---

## 11. PTS・SBI証券の扱い（STEP13・STEP14）

- **PTS**: v1.3でもスコアに組み込まない。無料・合法・安定して取得できる手段が確認できるまでは実装しない。取得できた場合も`session_type='pts_reference'`で参考表示のみとし、スコアリングクエリから除外する（§8.2）。将来組み込む場合は、実際にリアルタイムで蓄積したデータで別途検証してから判断する。
- **SBI証券**: 自動ログイン・自動注文・スクレイピングは一切実装しない。Stock Radarの通知には「銘柄コード」「会社名」「検知した材料の要約」「SBIで確認すべき項目（現在値・気配値・投資可能額等、人間が見る項目名のみ）」を表示するにとどめる。

---

## 12. Phase別開発計画（STEP16対応）

| Phase | 目的 | 実装対象 | テスト | 完了条件 | 次Phaseへ進む条件 |
|---|---|---|---|---|---|
| **0** | 仕様確定 | 本ドキュメント（v1.3）の合意 | - | ユーザーレビュー完了 | ユーザー承認 |
| **1** | SQLite + Mock Data + テスト基盤 | §6.1のDDL作成、モックデータ投入スクリプト、pytest等のテスト基盤 | 全テーブルへのCRUDが単体テストでPASS | スキーマが確定し、モックデータでCRUDが動く | ユーザー確認後 |
| **2** | 無料データ収集 | TDnet取得モジュール（非公式手段、Interval設定込み）、yfinance連携モジュール | 実際のTDnet/yfinanceへの疎通テスト（1銘柄のみ） | 4銘柄分の実データが3時刻モデル込みで保存できる | 疎通確認＋ユーザー承認 |
| **3** | 材料分類 | §1（v1.2辞書）のカテゴリA〜F実装、HARD_BLOCK/SOFT_NEGATIVE判定 | 4銘柄の過去開示での分類精度確認（適合率・再現率を手動確認） | 4銘柄の開示が正しくカテゴリ分類される | 誤分類が許容範囲内 |
| **4** | スコアリング | 材料/需給/テーマスコア計算ロジック、`weight_sets`初期値投入 | 4銘柄でスコアが期待レンジ内に収まるか確認 | S/A/B判定が期待通りに動く | ユーザー承認 |
| **5** | 通知 | S/Aランクのローカル通知（メール等） | 通知が正しいタイミング・内容で届くか確認 | 手動トリガーで通知確認完了 | ユーザー承認 |
| **6** | バックテスト | `outcome_tracking`収集、§9の集計クエリ実装 | 統計検証データセットでの集計が動く | スコア帯別実績レポートが出力できる | 結果をユーザーと確認 |
| **7** | 実運用 | 定期実行（スケジューラ）、エラー監視 | 数営業日の実運用モニタリング | 安定稼働（クラッシュなし）を一定期間確認 | ユーザー判断 |
| **8** | 必要なら有料データ導入 | §4.3の条件を満たした場合のみ | 導入対象APIの疎通テスト | 導入条件（§4.3）に該当することの確認 | - |

各Phase共通ルール: **前Phaseが完了条件を満たし、ユーザーが明示的に承認するまで次Phaseに進まない。**

---

## 13. Claude Codeへの実装開始プロンプト（STEP18対応）

以下はそのままClaude Codeに貼り付け可能なプロンプトです。

```
あなたはStock Radar（日本株の適時開示分析システム）の実装を担当します。
仕様書は「Stock Radar Implementation Specification v1.3」（本ドキュメント）です。

# 進め方の絶対ルール
1. Phase 0から順番に実装すること。複数Phaseを同時に進めない。
2. 各Phase終了時には必ず以下の手順を踏むこと：
   (1) そのPhaseに関するテストを実行する
   (2) テスト結果を報告する
   (3) 失敗があれば修正する
   (4) 全テストがPASSすることを確認する
   (5) 実装内容を簡潔に要約する
   (6) 「次のPhaseに進んでよいか」をユーザーに確認し、明示的な承認を得るまで次に進まない
3. 仕様書のDDL（第6.1節）を基準とし、変更が必要な場合は理由を説明してからユーザーに確認を取ること。
4. Look-ahead biasに関わる設計（3時刻モデル、market_snapshot_at、HARD_BLOCK/SOFT_NEGATIVE分離、weight_setsのウォークフォワード制約）は変更・簡略化しないこと。
5. TDnetのスクレイピングを実装する際は、Interval設定（サーバー負荷軽減）を必ず組み込み、利用規約上のリスクをコード内コメントで明記すること。
6. SBI証券への自動ログイン・自動注文・スクレイピングは絶対に実装しないこと。
7. PTSはスコアリングに組み込まないこと（参考表示のみ許可）。
8. 4銘柄（4840, 7743, 3987, 3907）は動作確認用のケーススタディとして扱い、統計的検証には使わないこと（dataset_tagで区別）。

まずPhase 0として、本仕様書の内容に不明点・矛盾点がないか確認し、あれば質問してください。
問題なければ、Phase 1（SQLite + Mock Data + テスト基盤）の実装計画を提示し、
実装に着手する前にユーザーの承認を求めてください。
```

---

## 補足：不確実性の一覧（推測を事実として扱わないための明示）

- TDnet公式Webページ（適時開示情報閲覧サービス）への自動アクセスが利用規約上どこまで許容されるか：**要確認**
- yfinance（Yahoo Finance非公式ラッパー）の日本株データに対する、Yahoo側の利用規約上の制限範囲：**要確認**
- 個人運営の非公式TDnet API（やのしん氏提供等）の現在の稼働状況・継続性：**要確認**（実装着手時に再確認必須）
- J-Quants無料プランの財務データが、材料スコアの「規模比較」ロジックに十分な粒度・更新頻度を持つか：**要確認**（Phase 3〜4で実データ確認）
