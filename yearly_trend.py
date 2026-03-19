#!/usr/bin/env python3
"""
kanmachi63 年別トレンド分析
月次スケジュール記事から年ごとの出演者データを集計してHTMLレポートを出力します。
"""

import re
import html
import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from scrape_kanmachi import (
    BlogParser, NextPageParser, SCHEDULE_TITLE_RE,
    extract_performers_by_date, normalize_name, fetch_cached,
)

# ─── 年付きタイトルから年を抽出 ───────────────────────────────────────────────

YEAR_RE = re.compile(r'(20\d{2})', re.UNICODE)

def extract_year(title: str) -> int | None:
    m = YEAR_RE.search(title)
    return int(m.group(1)) if m else None


# ─── 全記事を年別に集計 ──────────────────────────────────────────────────────

def aggregate_by_year(entries: list[dict]) -> dict[int, dict]:
    """
    戻り値: {year: {name: {'instruments': set, 'count': int}}}
    count = その年に出演した月数
    """
    by_year = defaultdict(lambda: defaultdict(lambda: {'instruments': set(), 'count': 0}))

    for entry in entries:
        title = entry['title']
        if not SCHEDULE_TITLE_RE.search(title):
            continue
        year = extract_year(title)
        if year is None:
            continue

        day_groups = extract_performers_by_date(entry['body_html'])
        for performers in day_groups:
            seen_in_day = set()
            for inst, raw_name in performers:
                name = normalize_name(raw_name)
                if name is None:
                    continue
                by_year[year][name]['instruments'].add(inst)
                if name not in seen_in_day:
                    by_year[year][name]['count'] += 1
                    seen_in_day.add(name)

    # defaultdict → 普通のdict
    return {y: dict(d) for y, d in sorted(by_year.items())}


# ─── キャッシュから全記事を読み込む ──────────────────────────────────────────

def load_entries_from_cache() -> list[dict]:
    import time
    cache_dir = Path('.page_cache')
    all_entries = []
    url = 'http://kanmachi63.blog.fc2.com/'
    visited = set()

    while url and url not in visited:
        visited.add(url)
        try:
            text = fetch_cached(url)
        except Exception as e:
            print(f'  スキップ: {url} ({e})')
            break

        p = BlogParser()
        p.feed(text)
        all_entries.extend(p.entries)

        np = NextPageParser()
        np.feed(text)
        url = np.next_url

    print(f'合計 {len(all_entries)} 記事読み込み完了')
    return all_entries


# ─── HTML レポート生成 ────────────────────────────────────────────────────────

def rank_color(rank: int) -> str:
    if rank == 1:   return '#f0c040'
    if rank == 2:   return '#c0c0c0'
    if rank == 3:   return '#cd8f5a'
    return ''

_COMMON_CSS = """
  body { font-family: "Hiragino Sans","Meiryo",sans-serif; margin:0; background:#111; color:#eee; }
  h1 { margin:0; padding:.8em 1em .4em; color:#FF6600; font-size:1.3em; }
  p.meta { margin:0 1em .8em; color:#888; font-size:.82em; }
  .name a, .hname a { color: inherit; text-decoration: none; }
  .name a:hover, .hname a:hover { color: #FF6600; text-decoration: underline; }
  /* ナビゲーションバー */
  .sitenav {
    display:flex; align-items:center; background:#222; height:40px;
    overflow-x:auto; flex-shrink:0; -webkit-overflow-scrolling:touch;
  }
  .sitenav a {
    color:#FFFFCC; text-decoration:none;
    padding:0 .9em; height:40px; line-height:40px;
    font-size:.82em; white-space:nowrap; display:inline-block;
  }
  .sitenav a:hover { background:#333; color:#fff; }
  .sitenav a.nav-active { background:#FF6600; color:#fff; font-weight:bold; }
  .snav-home { color:#FF6600 !important; border-right:1px solid #444; }
"""

def write_yearly_ranking(by_year: dict[int, dict], path: str, top_n: int = 0):
    years = sorted(by_year.keys())
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    latest_year = max(years)

    tab_contents = ''
    for year in years:
        yd = by_year[year]
        ranked = sorted(yd.items(), key=lambda x: -x[1]['count'])
        total_performers = len(yd)
        total_appearances = sum(v['count'] for v in yd.values())
        rows_html = ''
        for rank, (name, info) in enumerate(ranked if not top_n else ranked[:top_n], 1):
            color = rank_color(rank)
            bg = f'background:{color}' if color else ''
            rows_html += (
                f'<tr>'
                f'<td class="rank" style="{bg}">{rank}</td>'
                f'<td class="name"><a href="kanmachi63_coplayers.html#{quote(name)}">{html.escape(name)}</a></td>'
                f'<td class="inst">{html.escape(" / ".join(sorted(info["instruments"])))}</td>'
                f'<td class="count">{info["count"]}</td>'
                f'</tr>\n'
            )
        tab_contents += f'''
<div class="tab-pane" id="tab-{year}">
  <div class="year-summary">
    <span>出演者数: <strong>{total_performers}</strong> 名</span>
    <span>延べ出演日数: <strong>{total_appearances}</strong></span>
  </div>
  <table>
    <thead><tr><th>順位</th><th>名前</th><th>パート</th><th>出演日数</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>
'''

    tab_buttons = ''.join(
        f'<button class="tab-btn{" active" if y == latest_year else ""}" onclick="showTab({y})" id="btn-{y}">{y}</button>'
        for y in years
    )

    content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>上町63 年別ランキング</title>
<style>
{_COMMON_CSS}
  .tabs {{ padding:.5em 1em 0; border-bottom:2px solid #FF6600; overflow-x:auto; white-space:nowrap; }}
  .tab-btn {{
    border:none; background:#333; padding:.4em .7em; margin-right:3px;
    border-radius:4px 4px 0 0; cursor:pointer; font-size:.85em; color:#aaa;
  }}
  .tab-btn.active {{ background:#FF6600; color:#fff; font-weight:bold; }}
  .tab-pane {{ display:none; padding:.8em 1em; overflow-x:auto; }}
  .tab-pane.active {{ display:block; }}
  .year-summary {{ margin-bottom:.8em; font-size:.88em; color:#aaa; }}
  .year-summary span {{ margin-right:1.5em; }}
  table {{ border-collapse:collapse; background:#222; box-shadow:0 1px 3px rgba(0,0,0,.4); width:100%; max-width:680px; }}
  th {{ background:#111; color:#eee; padding:7px 10px; text-align:left; font-size:.82em; }}
  td {{ padding:6px 10px; border-bottom:1px solid #333; font-size:.85em; }}
  .rank {{ width:2.5em; text-align:center; font-weight:bold; color:#aaa; border-radius:3px; }}
  .count {{ text-align:center; font-weight:bold; color:#FF6600; width:4.5em; }}
  .inst {{ color:#FFFFCC; font-size:.8em; }}
  @media (max-width:480px) {{
    .inst {{ display:none; }}
  }}
</style>
</head>
<body>
<nav class="sitenav">
  <a href="index.html" class="snav-home">🎵 kanmachi63</a>
  <a href="kanmachi63_history.html">📅 履歴</a>
  <a href="kanmachi63_coplayers.html">👥 共演者</a>
  <a href="kanmachi63_yearly.html" class="nav-active">📊 年別</a>
  <a href="kanmachi63_heatmap.html">🌡️ ヒートマップ</a>
</nav>
<h1>📅 上町63 年別ランキング</h1>
<p class="meta">集計日時: {now} ／ 対象期間: {min(years)}年〜{max(years)}年</p>
<div class="tabs">{tab_buttons}</div>
{tab_contents}
<script>
function showTab(year) {{
  document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + year).classList.add('active');
  document.getElementById('btn-' + year).classList.add('active');
}}
showTab({latest_year});
</script>
</body>
</html>
"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'HTML 出力: {path}')


def write_heatmap(by_year: dict[int, dict], path: str):
    years = sorted(by_year.keys())
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    total_counts = defaultdict(int)
    for yd in by_year.values():
        for name, info in yd.items():
            total_counts[name] += info['count']
    top_names = [n for n, _ in sorted(total_counts.items(), key=lambda x: -x[1])]

    heat_header = ''.join(f'<th>{y}</th>' for y in years) + '<th class="total-col">合計</th>'
    heat_rows = ''
    for name in top_names:
        cells = ''
        for year in years:
            cnt = by_year[year].get(name, {}).get('count', 0)
            if cnt == 0:
                cells += '<td class="heat-0">—</td>'
            else:
                intensity = min(int(cnt / 30 * 100), 100)
                url = f'kanmachi63_history.html#{quote(name)}/{year}'
                cells += f'<td class="heat-n" style="--pct:{intensity}%"><a href="{url}" class="heat-link">{cnt}</a></td>'
        cells += f'<td class="total-cell">{total_counts[name]}</td>'
        heat_rows += f'<tr><td class="hname"><a href="kanmachi63_coplayers.html#{quote(name)}">{html.escape(name)}</a></td>{cells}</tr>\n'

    content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>上町63 出演日数ヒートマップ</title>
<style>
{_COMMON_CSS}
  .wrap {{ overflow-x:auto; padding:0 1em 2em; -webkit-overflow-scrolling:touch; }}
  table {{ border-collapse:collapse; background:#222; box-shadow:0 1px 3px rgba(0,0,0,.4); font-size:.82em; white-space:nowrap; }}
  th {{ background:#111; color:#eee; padding:5px 10px; }}
  thead th:first-child {{ position:sticky; left:0; z-index:2; background:#111; }}
  td {{ padding:4px 8px; border:1px solid #333; text-align:center; }}
  .hname {{ text-align:left !important; padding-left:12px !important; font-weight:bold; min-width:120px; white-space:nowrap; position:sticky; left:0; background:#222; z-index:1; box-shadow:2px 0 4px rgba(0,0,0,.4); }}
  .heat-0 {{ color:#555; }}
  .heat-n {{
    background: color-mix(in srgb, #FF6600 var(--pct), #222);
    color: #eee; font-weight:bold;
  }}
  .heat-link {{ color:inherit; text-decoration:none; display:block; }}
  .heat-link:hover {{ text-decoration:underline; }}
  .total-col {{ background:#000 !important; }}
  .total-cell {{ font-weight:bold; color:#FF6600; background:#1a0d00; border-left:2px solid #FF6600; }}
</style>
</head>
<body>
<nav class="sitenav">
  <a href="index.html" class="snav-home">🎵 kanmachi63</a>
  <a href="kanmachi63_history.html">📅 履歴</a>
  <a href="kanmachi63_coplayers.html">👥 共演者</a>
  <a href="kanmachi63_yearly.html">📊 年別</a>
  <a href="kanmachi63_heatmap.html" class="nav-active">🌡️ ヒートマップ</a>
</nav>
<h1>🌡️ 上町63 出演日数ヒートマップ</h1>
<p class="meta">集計日時: {now} ／ 総合TOP30 × 年別出演日数</p>
<div class="wrap">
<table>
<thead><tr><th>名前</th>{heat_header}</tr></thead>
<tbody>{heat_rows}</tbody>
</table>
</div>
</body>
</html>
"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'HTML 出力: {path}')


def write_csv_report(by_year: dict[int, dict], path: str):
    """年×人名のクロス集計CSVを出力"""
    years = sorted(by_year.keys())
    all_names = sorted({n for yd in by_year.values() for n in yd})

    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['名前'] + [str(y) for y in years] + ['合計'])
        for name in all_names:
            row = [name]
            total = 0
            for y in years:
                cnt = by_year[y].get(name, {}).get('count', 0)
                row.append(cnt)
                total += cnt
            row.append(total)
            writer.writerow(row)
    print(f'CSV 出力: {path}')


# ─── エントリポイント ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=== kanmachi63 年別トレンド分析 ===\n')
    print('記事読み込み中...')
    entries = load_entries_from_cache()

    print('年別集計中...')
    by_year = aggregate_by_year(entries)
    for y, yd in by_year.items():
        print(f'  {y}年: {len(yd)}名')

    print('\nレポート出力中...')
    write_yearly_ranking(by_year, 'kanmachi63_yearly.html')
    write_heatmap(by_year, 'kanmachi63_heatmap.html')
    write_csv_report(by_year, 'kanmachi63_yearly.csv')
    print('\n完了！')
