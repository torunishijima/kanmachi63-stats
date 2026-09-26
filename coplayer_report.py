#!/usr/bin/env python3
"""
kanmachi63 共演者ランキング
全出演者の共演回数を集計してインタラクティブHTMLを出力します。
"""

import re
import html
import json
from collections import defaultdict
from datetime import datetime
from itertools import combinations

from html_common import (
    page_head, page_tail, TWO_PANE_CSS, TWO_PANE_JS, two_pane_body,
)
from scrape_kanmachi import (
    SCHEDULE_TITLE_RE,
    _prepare_text, _parse_performers, DATE_LINE_RE,
    normalize_name, load_all_entries,
)

YEAR_RE = re.compile(r'(20\d{2})')


def build_coplayer_data(entries):
    """
    戻り値:
      total[name]          = 総出演日数
      co[name][co_name]    = 共演日数
      instruments[name]    = 使用楽器セット
    """
    total = defaultdict(int)
    co = defaultdict(lambda: defaultdict(int))
    instruments = defaultdict(set)

    for entry in entries:
        if not SCHEDULE_TITLE_RE.search(entry['title']):
            continue

        text = _prepare_text(entry['body_html'])
        lines = text.splitlines()
        current_date, current_lines = None, []
        day_groups = []
        for line in lines:
            if DATE_LINE_RE.search(line):
                if current_lines:
                    day_groups.append(current_lines)
                current_date = DATE_LINE_RE.search(line).group()
                current_lines = [line]
            elif current_date:
                current_lines.append(line)
        if current_lines:
            day_groups.append(current_lines)

        for chunk in day_groups:
            performers = _parse_performers(' '.join(chunk))
            names = []
            for inst, raw_name in performers:
                name = normalize_name(raw_name)
                if name is None:
                    continue
                instruments[name].add(inst)
                if name not in names:
                    names.append(name)

            for name in names:
                total[name] += 1

            for a, b in combinations(names, 2):
                co[a][b] += 1
                co[b][a] += 1

    return dict(total), dict(co), dict(instruments)


def write_html(total, co, instruments, path):
    # 出演日数順にソートした名前リスト
    sorted_names = sorted(total.keys(), key=lambda n: -total[n])

    # JS用データ構造を構築
    # players_data: [{name, total, inst, co: [{name, days}, ...]}, ...]
    players_data = []
    for name in sorted_names:
        co_list = sorted(
            [{'name': cn, 'days': days} for cn, days in co.get(name, {}).items()],
            key=lambda x: -x['days']
        )
        players_data.append({
            'name': name,
            'total': total[name],
            'inst': ' / '.join(sorted(instruments.get(name, set()))),
            'co': co_list,
        })

    players_json = json.dumps(players_data, ensure_ascii=False)
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    total_players = len(sorted_names)

    css_extra = """
  /* 共演者テーブル */
  h3 { font-size:.95em; color:#c8ced6; margin:1.2em 0 .6em; border-bottom:1px solid var(--line); padding-bottom:.45em; }
  .co-table { border-collapse:collapse; width:100%; max-width:620px; background:var(--panel);
               border:1px solid var(--line); border-radius:8px; overflow:hidden; }
  .co-table th { background:#11151b; color:#d8dde3; padding:9px 14px; text-align:left; font-size:.78em; }
  .co-table td { padding:9px 14px; border-bottom:1px solid var(--line); font-size:.9em; }
  .co-table tr:last-child td { border-bottom:none; }
  .co-table tr:hover td { background:#202630; }
  .co-rank { width:3em; text-align:center; color:#79818c; font-size:.85em; }
  .co-name { cursor:pointer; color:#fff; white-space:nowrap; }
  .co-name:hover { text-decoration:underline; }
  .co-days { text-align:center; font-weight:bold; color:#ffb38d; width:5em; }
  .co-inst { color:var(--muted); font-size:.82em; }
  .co-pct { width:80px; }
  .bar-bg { background:#2f3540; border-radius:3px; height:8px; }
  .bar-fill { background:var(--accent); border-radius:3px; height:8px; }

  @media (max-width: 640px) {
    .co-inst { display:none; }
    .co-pct { display:none; }
    .co-table th, .co-table td { padding:9px 10px; }
  }
"""
    html_content = (
        page_head('上町63 共演者ランキング', TWO_PANE_CSS + css_extra, active='coplayers')
        + two_pane_body(total_players, now, '名前をえらぶと、その人の共演者ランキングが出ます。')
        + f'''
<script>
const DATA = {players_json};
const byName = {{}};
DATA.forEach(p => byName[p.name] = p);
const OVERVIEW_LEAD = '名前をえらぶと、その人がだれと何日いっしょに演奏したかが出ます。上の検索で名前を探せます。';
{TWO_PANE_JS}

function showPlayer(name) {{
  const p = byName[name];
  if (!p) return;

  // URLハッシュ更新
  history.replaceState(null, '', '#' + encodeURIComponent(name));

  // アクティブ状態更新
  document.querySelectorAll('.player-item').forEach(el => el.classList.remove('active'));
  const item = document.getElementById('item-' + name);
  if (item) {{ item.classList.add('active'); item.scrollIntoView({{block:'nearest'}}); }}
  openDetail();

  const maxDays = p.co.length > 0 ? p.co[0].days : 1;

  const coRows = p.co.map((c, i) => {{
    const cp = byName[c.name] || {{}};
    const pct = Math.round(c.days / maxDays * 100);
    return `<tr>
      <td class="co-rank">${{i+1}}</td>
      <td class="co-name" onclick="showPlayer('${{esc(c.name)}}')">
        ${{c.name}}
      </td>
      <td class="co-days">${{c.days}}</td>
      <td class="co-pct"><div class="bar-bg"><div class="bar-fill" style="width:${{pct}}%"></div></div></td>
    </tr>`;
  }}).join('');

  const historyUrl = 'kanmachi63_history.html#' + encodeURIComponent(name);

  document.getElementById('rightPanel').innerHTML = `
    <div class="detail-header">
      <div class="detail-name">${{p.name}}</div>
      <div class="detail-meta">
        <span class="inst">${{p.inst || '不明'}}</span>
        <span class="days">総出演: ${{p.total}} 日</span>
        <span>共演者: ${{p.co.length}} 名</span>
      </div>
    </div>
    <div style="margin:.6em 0 1.2em;font-size:.85em;">
      <a href="${{historyUrl}}" style="color:#ffd9c5;text-decoration:none;">出演履歴を見る</a>
    </div>
    <h3>共演者ランキング</h3>
    <table class="co-table">
      <thead><tr>
        <th>順位</th><th>名前</th><th>共演日数</th><th></th>
      </tr></thead>
      <tbody>${{coRows || '<tr><td colspan=5 style="color:#aaa;text-align:center">データなし</td></tr>'}}</tbody>
    </table>
  `;
}}

renderList();
// URLハッシュがあればその人を、なければ「よく出ている人」を出す
const hash = decodeURIComponent(location.hash.slice(1));
if (hash && byName[hash]) showPlayer(hash);
else renderOverview(OVERVIEW_LEAD);
</script>
'''
        + page_tail()
    )
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f'HTML 出力: {path}')


if __name__ == '__main__':
    print('=== kanmachi63 共演者ランキング生成 ===\n')
    entries = load_all_entries()
    if not entries:
        raise SystemExit('エラー: 記事を1件も取得できませんでした。処理を中止します。')
    print('共演データ集計中...')
    total, co, instruments = build_coplayer_data(entries)
    print(f'出演者: {len(total)}名')
    write_html(total, co, instruments, 'kanmachi63_coplayers.html')
    print('\n完了！')
