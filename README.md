# stock_radar

日本株の適時開示（TDnet）を分析し、材料・需給・テーマの観点でランキングする個人用ツール。
仕様は [`docs/implementation_spec_v1.3.md`](docs/implementation_spec_v1.3.md) を参照（Phase制で段階実装、各Phase完了後にユーザー承認を得て次に進む）。

## 現在のステータス: Phase 3（材料分類）

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

- `src/stock_radar/classification/keywords.py`: カテゴリA〜G（上方修正/増配/自社株買い/大型受注・契約/M&A・資本業務提携/新製品・特許・承認/株式分割）＋HARD_BLOCK（民事再生・上場廃止等、存続性リスクのみ）＋SOFT_NEGATIVE（下方修正・減損等、ポジティブと共存）のキーワード辞書。**v1.2の実辞書は現存せず、v1.3仕様書にも本体が含まれていなかったため新規設計**（詳細はファイル冒頭のPROVENANCE NOTICE参照）。実データでの精度検証はまだ未実施。
- `src/stock_radar/classification/classifier.py`: `classify_disclosure(title, raw_text)` — NFKC正規化後にキーワード辞書と照合し、`category`/`positive_material_raw`/`negative_penalty_raw`/`is_hard_block`を算出。HARD_BLOCKによるスコアのゼロ化はここでは行わない（disclosuresの生の値はそのまま記録し、ゼロ化はPhase 4のスコアリング時に適用、仕様書§8.3）。
- `src/stock_radar/classification/repository.py`: 分類結果を`disclosures`テーブルに書き戻す。
- `scripts/classify_disclosures.py`: DB内の全開示を分類（辞書修正後の再実行にも対応、毎回全件再分類）。
- `scripts/review_classifications.py`: 開示タイトルと分類結果を並べて表示する手動レビュー用CLI。

**要実施**: Phase 2で収集した実データに対して分類を実行し、手動で適合率・再現率を確認してください（仕様書§12 Phase 3の完了条件）。

```bash
python3 scripts/classify_disclosures.py --db-path data/stock_radar.db3
python3 scripts/review_classifications.py --db-path data/stock_radar.db3
```

出力された各開示のタイトルと`category`/`positive_raw`/`HARD_BLOCK`/`SOFT_NEGATIVE`を見比べて、明らかな誤分類（例: 上方修正なのに検出されない、無関係な開示がカテゴリ判定されている等）があれば教えてください。`keywords.py`のパターンを調整します。

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
