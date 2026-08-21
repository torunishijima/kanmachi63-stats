# kanmachi63-stats

ジャズライブハウス「上町63」（FC2ブログ）の月次スケジュール記事をスクレイピングし、
出演ミュージシャンの統計（出演回数・共演者ランキング・年次トレンド）を集計・可視化するプロジェクトです。

## スクリプト

| スクリプト | 出力 | 内容 |
|---|---|---|
| [`scrape_kanmachi.py`](scrape_kanmachi.py) | `kanmachi63_stats.csv` / `kanmachi63_stats.html` / `index.html` | 出演者集計（共通ロジックを含む） |
| [`coplayer_report.py`](coplayer_report.py) | `kanmachi63_coplayers.html` | 共演者ランキング |
| [`history_report.py`](history_report.py) | `kanmachi63_history.html` | 出演者ごとの履歴 |
| [`yearly_trend.py`](yearly_trend.py) | `kanmachi63_yearly.csv` / `kanmachi63_yearly.html` / `kanmachi63_heatmap.html` | 年別トレンド・ヒートマップ |

共通の記事読み込み処理は [`scrape_kanmachi.load_all_entries()`](scrape_kanmachi.py) に集約されています。

## 実行

```bash
# スクレイピング + 全レポート生成（月次更新）
python scrape_kanmachi.py
python coplayer_report.py
python history_report.py
python yearly_trend.py
```

月次更新は GitHub Actions（[`.github/workflows/monthly_update.yml`](.github/workflows/monthly_update.yml)）で自動実行されます。

## テスト

オーディオデバイスやネットワーク不要のユニットテストがあります。

```bash
# pytest がある場合
python -m pytest tests/ -v

# pytest がない場合（簡易ランナー）
python tests/test_scrape_kanmachi.py
```

テストは [`tests/test_scrape_kanmachi.py`](tests/test_scrape_kanmachi.py) にあり、
パーサー（`_prepare_text` / `_parse_performers` / `extract_performers_by_date`）と
名前正規化（`clean_name` / `normalize_name` / `_is_instrument`）の回帰を検証します。
