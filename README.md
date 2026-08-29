# stock_radar

日本株の適時開示（TDnet）を分析し、材料・需給・テーマの観点でランキングする個人用ツール。
仕様は [`docs/implementation_spec_v1.3.md`](docs/implementation_spec_v1.3.md) を参照（Phase制で段階実装、各Phase完了後にユーザー承認を得て次に進む）。

## 現在のステータス: Phase 1（SQLite + モックデータ + テスト基盤）

- `src/stock_radar/db/schema.sql`: DDL（仕様書§6.1 + Phase 0で承認した整合性用CHECK/UNIQUE制約3件、詳細はファイル冒頭コメント参照）
- `src/stock_radar/db/connection.py`: DB接続・初期化
- `src/stock_radar/mock_data.py`: 4銘柄（4840, 7743, 3987, 3907）のケーススタディ用モックデータ（`dataset_tag='case_study'`）
- `scripts/seed_mock_data.py`: モックデータ入りDBファイルを作成するCLI
- `tests/`: 全テーブルのCRUD・制約・モックデータの pytest テスト

### セットアップ

```bash
pip install -r requirements-dev.txt
```

### テスト実行

```bash
python3 -m pytest
```

### モックデータ入りDBの作成

```bash
python3 scripts/seed_mock_data.py --db-path data/stock_radar_mock.db3
```
