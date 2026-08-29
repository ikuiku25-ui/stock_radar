# stock_radar

日本株の適時開示（TDnet）を分析し、材料・需給・テーマの観点でランキングする個人用ツール。
仕様は [`docs/implementation_spec_v1.3.md`](docs/implementation_spec_v1.3.md) を参照（Phase制で段階実装、各Phase完了後にユーザー承認を得て次に進む）。

## 現在のステータス: Phase 2（無料データ収集）

### Phase 1（SQLite + モックデータ + テスト基盤）

- `src/stock_radar/db/schema.sql`: DDL（仕様書§6.1 + Phase 0で承認した整合性用CHECK/UNIQUE制約3件、詳細はファイル冒頭コメント参照）
- `src/stock_radar/db/connection.py`: DB接続・初期化
- `src/stock_radar/mock_data.py`: 4銘柄（4840, 7743, 3987, 3907）のケーススタディ用モックデータ（`dataset_tag='case_study'`）
- `scripts/seed_mock_data.py`: モックデータ入りDBファイルを作成するCLI

### Phase 2（TDnet取得・yfinance連携）

- `src/stock_radar/collectors/tdnet.py`: TDnet適時開示の収集クライアント。**非公式の個人運営API**（例: やのしん氏形式のJSON API）を利用（仕様書§4.1で「0円だが規約・安定性のグレーゾーン」と明記された手段）。Interval設定（デフォルト30秒間隔）を組み込み済み。レスポンス形式は公開資料ベースの推測であり、**実装着手時に実サービスで再検証が必要**（ファイル冒頭コメント参照）。
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
