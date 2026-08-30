# stock_radar

日本株の適時開示（TDnet）を分析し、材料・需給・テーマの観点でランキングする個人用ツール。
仕様は [`docs/implementation_spec_v1.3.md`](docs/implementation_spec_v1.3.md) を参照（Phase制で段階実装、各Phase完了後にユーザー承認を得て次に進む）。

## 現在のステータス: Phase 5（通知）

### Phase 1（SQLite + モックデータ + テスト基盤）

- `src/stock_radar/db/schema.sql`: DDL（仕様書§6.1 + Phase 0で承認した整合性用CHECK/UNIQUE制約3件、詳細はファイル冒頭コメント参照）
- `src/stock_radar/db/connection.py`: DB接続・初期化
- `src/stock_radar/mock_data.py`: 4銘柄（4840, 7743, 3987, 3907）のケーススタディ用モックデータ（`dataset_tag='case_study'`）
- `scripts/seed_mock_data.py`: モックデータ入りDBファイルを作成するCLI

### Phase 2（TDnet取得・yfinance連携）

- `src/stock_radar/collectors/tdnet.py`: TDnet適時開示の収集クライアント。**非公式の個人運営API**「TDnet WEB-API（非公式）by Yanoshin」(https://webapi.yanoshin.jp/webapi/tdnet/) を利用（仕様書§4.1で「0円だが規約・安定性のグレーゾーン」と明記された手段）。URL形式・`pubdate`日付形式・`company_code`の5桁形式は、いずれも実サービスへの疎通確認で確認・修正済み（当初の推測とは異なっていた）。Interval設定（デフォルト30秒間隔）を組み込み済み。
- `src/stock_radar/collectors/yfinance_client.py`: yfinance経由の日足OHLCV取得。`avg_volume_20d`は当日を含まない過去20営業日平均として計算（Look-ahead bias対策、§6.2/§8.2）。
- `src/stock_radar/collectors/repository.py`: 収集結果のDB保存＋`get_available_price_asof()` — 場中開示（15:00より前）が当日未確定データを参照できないようにする、§8.2のLook-ahead bias防止ロジックの唯一の入口。
- `scripts/tdnet_connectivity_probe.py` / `scripts/yfinance_connectivity_probe.py`: 実サービスへの1銘柄疎通テスト用CLI。
- `scripts/collect_case_study_data.py`: 4銘柄分の実データを3時刻モデル込みでDBに保存する（Phase 2完了条件）。

**重要**: このサンドボックス環境はネットワークポリシーによりTDnet/Yahoo Financeへの外部アクセスがブロックされているため、実際の疎通テストは実行できていません。単体テストは全てHTTPをモックして検証済みです。実際の疎通確認・4銘柄データ収集は、**ネットワークアクセス可能なローカルPC等で**以下を実行してください。

```bash
pip install -r requirements.txt
python3 scripts/tdnet_connectivity_probe.py --ticker 7203 --limit 5
python3 scripts/yfinance_connectivity_probe.py --ticker 7203 --period 5d
# 上記で応答形式に問題がなければ:
python3 scripts/collect_case_study_data.py --db-path data/stock_radar.db3
```

**Phase 2は実データでの動作確認済み**（4銘柄分の開示・株価データを3時刻モデル込みでDB保存できることを確認済み）。

### Phase 3（材料分類）

- `src/stock_radar/classification/keywords.py`: カテゴリA〜G（上方修正/増配/自社株買い/大型受注・契約/M&A・資本業務提携/新製品・特許・承認/株式分割）＋HARD_BLOCK（民事再生・上場廃止等、存続性リスクのみ）＋SOFT_NEGATIVE（下方修正・減損等、ポジティブと共存）のキーワード辞書。**v1.2の実辞書は現存せず、v1.3仕様書にも本体が含まれていなかったため新規設計**（詳細はファイル冒頭のPROVENANCE NOTICE参照）。
- `src/stock_radar/classification/classifier.py`: `classify_disclosure(title, raw_text)` — NFKC正規化後にキーワード辞書と照合し、`category`/`positive_material_raw`/`negative_penalty_raw`/`is_hard_block`を算出。HARD_BLOCKによるスコアのゼロ化はここでは行わない（disclosuresの生の値はそのまま記録し、ゼロ化はPhase 4のスコアリング時に適用、仕様書§8.3）。
- `src/stock_radar/classification/repository.py`: 分類結果を`disclosures`テーブルに書き戻す。
- `scripts/classify_disclosures.py`: DB内の全開示を分類（辞書修正後の再実行にも対応、毎回全件再分類）。
- `scripts/review_classifications.py`: 開示タイトルと分類結果を並べて表示する手動レビュー用CLI。

**実データでの手動精度確認は実施済み**（仕様書§12 Phase 3の完了条件）。実際の4銘柄・80件の開示に対して分類を実行し、レビューの結果、以下を修正:
- 誤検出: 「受注損失引当金繰入額の計上」（悪材料）が「受注」に一致し誤って好材料判定されていた問題を修正
- 重大な見逃し: 実際のTOB（公開買付け）開示が辞書の表記違いで検出できていなかった問題を修正
- その他、特別利益の発生・自己株式消却・株式取得（M&A文脈）・事業譲受・会社分割・戦略的提携のキーワードを追加

**既知の限界**（ユーザー承認済み、対応は先送り）: `raw_text`は現状タイトルのみ（Phase 2でPDF本文抽出を先送りしたため）。「業績予想の修正に関するお知らせ」のように、本文を見なければ上方/下方が判別できないタイトルは分類不能（実データ80件中約5件に影響）。`keywords.py`冒頭のKNOWN LIMITATIONコメント参照。

```bash
python3 scripts/classify_disclosures.py --db-path data/stock_radar.db3
python3 scripts/review_classifications.py --db-path data/stock_radar.db3
```

### Phase 4（スコアリング）

- `src/stock_radar/scoring/material.py`: `material_score = 0 if HARD_BLOCK else min(weight_material, max(0, positive+negative))`（仕様書§8.3の式そのまま＋weight_materialでの上限キャップ）。
- `src/stock_radar/scoring/supply_demand.py`: `volume_ratio`（開示日を含まない過去20営業日平均が分母、Phase 2で計算済みの`avg_volume_20d`をそのまま利用）に応じた加点＋小型株ボーナス。**両方とも仕様書に具体的な数値がないため、このプロジェクト独自の仮説として設計**（ファイル冒頭のHYPOTHESIS NOTICE参照、Phase 6のバックテストで検証・調整する前提）。
- `src/stock_radar/scoring/theme.py`: `theme_keywords`と照合し、該当テーマがその日「アツい」（`theme_hot_status.hot_flag`）かで加点。場中開示は前営業日のhot_flagを参照するLook-ahead bias対策込み。**`theme_hot_status`を実際に埋めるパイプライン（値上がり率ランキング等）はまだ存在しないため、実データでは現状ほぼ常に0点**。
- `src/stock_radar/scoring/rank.py`: `total_score`（0〜100）からS/A/B/noneを判定。**閾値（S:80以上/A:60以上/B:40以上）も仕様書に記載がないため独自の仮説**。
- `src/stock_radar/scoring/scorer.py`: 上記を統合するオーケストレーター。価格データは必ず`get_available_price_asof()`経由で取得し、Look-ahead bias防止を徹底。
- `src/stock_radar/scoring/weight_sets.py`: ベースライン`weight_set`（50/30/20、ウォークフォワード期間なし）を用意。
- `scripts/score_disclosures.py`: DB内の全開示をスコアリング（再実行時は対象weight_setの既存スコアを削除してから再投入、安全に再実行可能）。
- `scripts/review_scores.py`: 開示タイトルと材料/需給/テーマ/合計スコア・ランクを並べて表示する手動レビュー用CLI。

**実データでの手動確認は実施済み**（仕様書§12 Phase 4の完了条件）。実際の4銘柄・80件でスコアリングした結果、S/Aランクはほぼ出ず、Bランクも1件のみとなった。原因を`--show-volume-ratio`で調査したところ、バグではなく設計通りの挙動と判明:
- 実際のTOB開示（7743）で`volume_ratio=0.73`（平常並み）を確認 — 大引け後開示の場合、「開示日の確定出来高」（仕様書§6.2の定義通り）は開示**前**の出来高であり、開示への市場反応を捉える指標ではない
- テーマスコアは既知のギャップにより実質常時0点

この2点により実質的な到達点が下がり、S/Aがほぼ出ないのは想定内という結論に至った。**ユーザーの判断で閾値の調整は行わず、現状の仮説のまま維持**し、Phase 6のバックテストで実際に検証する方針とした（詳細は`scoring/rank.py`のREAL-DATA FINDING参照）。

```bash
python3 scripts/score_disclosures.py --db-path data/stock_radar.db3
python3 scripts/review_scores.py --db-path data/stock_radar.db3 --show-volume-ratio
```

### Phase 5（通知）

- `src/stock_radar/notification/message.py`: 通知本文を組み立てる。仕様書§11・§13ルール6に従い、**銘柄コード・会社名・検知した材料・SBIで確認すべき項目の「名前」のみ**を含み、証券会社の実際の値（現在値等）は一切含まない（自動取得しないため）。
- `src/stock_radar/notification/desktop.py`: デスクトップ通知。**現状macOSのみ対応**（`osascript`、追加インストール不要）。ユーザーの実行環境がMacのため、まずこちらを実装。仕様書が元々想定していたWindows環境向けの実装は未着手（必要になれば追加）。
- `src/stock_radar/notification/email_notifier.py`: メール通知（標準ライブラリ`smtplib`のみ、追加依存なし）。SMTP認証情報は環境変数から読み込み、**コードやDBに一切保存しない**。
- `src/stock_radar/notification/service.py`: S/Aランクのみ通知（仕様書§5）。`watchlist`テーブルへの登録が「通知済み」の記録を兼ねる設計 — 全通知手段が失敗した場合はwatchlistに登録せず、次回実行時に再試行される。
- `scripts/notify_watchlist.py`: 手動トリガー用CLI（仕様書§12 Phase 5の完了条件）。`--dry-run`で送信せず内容確認のみ可能。

**メール通知を使う場合**、以下の環境変数を設定してください（Gmailの場合は通常のパスワードではなく「アプリパスワード」が必要）:

```bash
export STOCK_RADAR_SMTP_HOST=smtp.gmail.com
export STOCK_RADAR_SMTP_PORT=587
export STOCK_RADAR_SMTP_USER=your_address@gmail.com
export STOCK_RADAR_SMTP_PASSWORD=your_app_password
export STOCK_RADAR_NOTIFY_EMAIL_TO=your_address@gmail.com
```

**動作確認**（仕様書§12 Phase 5の完了条件: 手動トリガーで通知確認）:

```bash
# まず内容だけ確認（送信しない）
python3 scripts/notify_watchlist.py --db-path data/stock_radar.db3 --dry-run

# デスクトップ通知で送信（Mac）
python3 scripts/notify_watchlist.py --db-path data/stock_radar.db3 --method desktop

# メールで送信（環境変数の設定が必要）
python3 scripts/notify_watchlist.py --db-path data/stock_radar.db3 --method email
```

**動作確認済み**: ユーザーのMac実機でデスクトップ通知バナーの表示を確認済み。なお実データ（`data/stock_radar.db3`）はPhase 4の結果（S:0/A:0/B:1/none:79）によりS/Aランクが存在しないため、確認にはPhase 1のモックデータ（4840=S、7743=A）を使用した。

```bash
python3 scripts/seed_mock_data.py --db-path data/stock_radar_mock.db3 --force
python3 -c "import sqlite3; c=sqlite3.connect('data/stock_radar_mock.db3'); c.execute('DELETE FROM watchlist'); c.commit()"
python3 scripts/notify_watchlist.py --db-path data/stock_radar_mock.db3 --method desktop
```

Phase 2/4で収集・スコアリング済みの実データ（`data/stock_radar.db3`）に対して実行し、通知が正しいタイミング・内容で届くか確認してください。既にwatchlistに入っている銘柄（4840, 7743など）は再通知されません。

### セットアップ

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

### テスト実行

```bash
python3 -m pytest
```

### モックデータ入りDBの作成

```bash
python3 scripts/seed_mock_data.py --db-path data/stock_radar_mock.db3
```
