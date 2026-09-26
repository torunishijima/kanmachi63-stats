#!/usr/bin/env python3
"""HTML共通化の動作検証：既存キャッシュから各レポートを生成し、共通要素を確認する"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scrape_kanmachi import load_all_entries, aggregate
from html_common import site_nav

# 1. site_nav の動作確認（ネットワーク不要）
nav = site_nav('yearly')
assert 'nav-active' in nav and 'kanmachi63_yearly.html' in nav
nav_stats = site_nav('')
assert 'nav-active' not in nav_stats
print('OK: site_nav 共通ナビ')

# 2. キャッシュから記事を読んで HTML 生成（refresh しない＝キャッシュ利用）
entries = load_all_entries(refresh_pages=0)
print(f'OK: キャッシュから {len(entries)} 記事')

# 3. 各 HTML 生成関数が page_head を使い、共通 nav を含むことを確認
from scrape_kanmachi import write_html
import io, contextlib
stats = aggregate(entries)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    write_html(stats, '_verify_stats.html')
text = Path('_verify_stats.html').read_text(encoding='utf-8')
assert '<!DOCTYPE html>' in text
assert 'class="sitenav"' in text
assert '上町63 出演者統計' in text
print('OK: scrape_kanmachi.write_html')

from yearly_trend import write_yearly_ranking, write_heatmap, aggregate_by_year
by_year = aggregate_by_year(entries)
with contextlib.redirect_stdout(buf):
    write_yearly_ranking(by_year, '_verify_yearly.html')
    write_heatmap(by_year, '_verify_heatmap.html')
t1 = Path('_verify_yearly.html').read_text(encoding='utf-8')
t2 = Path('_verify_heatmap.html').read_text(encoding='utf-8')
assert 'class="sitenav"' in t1 and 'nav-active' in t1
assert 'class="sitenav"' in t2 and 'nav-active' in t2
print('OK: yearly_trend.write_yearly_ranking / write_heatmap')

from coplayer_report import build_coplayer_data, write_html as co_write
total, co, inst = build_coplayer_data(entries)
with contextlib.redirect_stdout(buf):
    co_write(total, co, inst, '_verify_coplayers.html')
t3 = Path('_verify_coplayers.html').read_text(encoding='utf-8')
assert 'class="sitenav"' in t3 and 'nav-active' in t3
print('OK: coplayer_report.write_html')

from history_report import build_history_data, write_html as h_write
hist, hinstr, htotal = build_history_data(entries)
with contextlib.redirect_stdout(buf):
    h_write(hist, hinstr, htotal, '_verify_history.html')
t4 = Path('_verify_history.html').read_text(encoding='utf-8')
assert 'class="sitenav"' in t4 and 'nav-active' in t4
print('OK: history_report.write_html')

# 検証ファイル削除
for f in ['_verify_stats.html', '_verify_yearly.html', '_verify_heatmap.html',
          '_verify_coplayers.html', '_verify_history.html']:
    Path(f).unlink(missing_ok=True)

print('\nALL HTML VERIFY OK')
