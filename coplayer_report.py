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

from scrape_kanmachi import (
    BlogParser, NextPageParser, SCHEDULE_TITLE_RE,
    _prepare_text, _parse_performers, DATE_LINE_RE,
    normalize_name, fetch_cached,
)

YEAR_RE = re.compile(r'(20\d{2})')


def load_entries():
    entries = []
    url = 'http://kanmachi63.blog.fc2.com/'
    visited = set()
    while url and url not in visited:
        visited.add(url)
        try:
            text = fetch_cached(url)
        except Exception as e:
            print(f'  スキップ: {e}')
            break
        p = BlogParser()
        p.feed(text)
        entries.extend(p.entries)
        np = NextPageParser()
        np.feed(text)
        url = np.next_url
    print(f'{len(entries)} 記事読み込み完了')
    return entries


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

    html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>上町63 共演者ランキング</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: "Hiragino Sans","Meiryo",sans-serif; margin:0; background:#111; color:#eee; }}

  /* ナビゲーションバー */
  .sitenav {{ display:flex; align-items:center; background:#222; height:40px; overflow-x:auto; flex-shrink:0; -webkit-overflow-scrolling:touch; }}
  .sitenav a {{ color:#FFFFCC; text-decoration:none; padding:0 .9em; height:40px; line-height:40px; font-size:.82em; white-space:nowrap; display:inline-block; }}
  .sitenav a:hover {{ background:#333; color:#fff; }}
  .sitenav a.nav-active {{ background:#CC4400; color:#fff; font-weight:bold; }}
  .snav-home {{ color:#CC4400 !important; border-right:1px solid #444; }}

  /* レイアウト */
  .container {{ display:flex; height:calc(100vh - 40px); }}
  .left-panel {{
    width:300px; min-width:200px; background:#222; color:#eee;
    display:flex; flex-direction:column; flex-shrink:0;
  }}
  .right-panel {{ flex:1; padding:1.5em; overflow-y:auto; }}

  /* 左パネル */
  .panel-title {{ padding:.8em 1em .4em; font-size:.85em; color:#888; letter-spacing:.05em; }}
  .search-box {{
    margin:.3em .8em .6em; padding:.5em .8em;
    border:none; border-radius:6px; width:calc(100% - 1.6em);
    font-size:.9em; background:#333; color:#eee;
    outline:none;
  }}
  .search-box::placeholder {{ color:#666; }}
  .list-wrap {{ flex:1; overflow:hidden; position:relative; }}
  .list-wrap::after {{
    content:''; pointer-events:none;
    position:absolute; bottom:0; left:0; right:0; height:3em;
    background:linear-gradient(transparent, #222);
  }}
  .player-list {{ height:100%; overflow-y:auto; -webkit-overflow-scrolling:touch; }}
  .player-item {{
    padding:.55em 1em; cursor:pointer; font-size:.88em;
    border-left:3px solid transparent;
    display:flex; justify-content:space-between; align-items:center;
  }}
  .player-item:hover {{ background:#333; }}
  .player-item.active {{ background:#CC4400; border-left-color:#FFFFCC; color:#fff; }}
  .player-item .pname {{ flex:1; }}
  .player-item .ptotal {{ font-size:.8em; color:#888; margin-left:.5em; }}
  .player-item.active .ptotal {{ color:#ffe; }}

  /* 右パネル */
  .placeholder {{
    display:flex; align-items:center; justify-content:center;
    height:60%; color:#666; font-size:1.1em;
  }}
  .detail-header {{ margin-bottom:1.2em; }}
  .detail-name {{ font-size:1.6em; font-weight:bold; color:#CC4400; }}
  .detail-meta {{ color:#888; font-size:.88em; margin-top:.3em; }}
  .detail-meta span {{ margin-right:1.5em; }}
  .detail-meta .inst {{ color:#FFFFCC; }}
  .detail-meta .days {{ color:#CC4400; font-weight:bold; }}

  h3 {{ font-size:1em; color:#888; margin:1.2em 0 .5em; border-bottom:1px solid #333; padding-bottom:.3em; }}

  /* 共演者テーブル */
  .co-table {{ border-collapse:collapse; width:100%; max-width:560px; background:#222;
               box-shadow:0 1px 4px rgba(0,0,0,.4); border-radius:6px; overflow:hidden; }}
  .co-table th {{ background:#111; color:#eee; padding:7px 14px; text-align:left; font-size:.82em; }}
  .co-table td {{ padding:7px 14px; border-bottom:1px solid #333; font-size:.88em; }}
  .co-table tr:last-child td {{ border-bottom:none; }}
  .co-table tr:hover td {{ background:#2a2a2a; }}
  .co-rank {{ width:3em; text-align:center; color:#666; font-size:.85em; }}
  .co-name {{ cursor:pointer; color:#FFFFCC; white-space:nowrap; }}
  .co-name:hover {{ text-decoration:underline; }}
  .co-days {{ text-align:center; font-weight:bold; color:#CC4400; width:5em; }}
  .co-inst {{ color:#888; font-size:.82em; }}
  .co-pct {{ width:80px; }}
  .bar-bg {{ background:#333; border-radius:3px; height:8px; }}
  .bar-fill {{ background:#CC4400; border-radius:3px; height:8px; }}

  .meta {{ color:#666; font-size:.8em; padding:.5em 1em; border-top:1px solid #444; }}

  /* スマホ対応 */
  @media (max-width: 640px) {{
    .container {{ flex-direction:column; height:auto; min-height:calc(100vh - 40px); }}
    .left-panel {{ width:100%; height:40vh; min-width:unset; flex-shrink:0; }}
    .right-panel {{ flex:1; padding:1em; }}
    .detail-name {{ font-size:1.3em; }}
    .co-inst {{ display:none; }}
    .co-pct {{ display:none; }}
  }}
</style>
</head>
<body>
<nav class="sitenav">
  <a href="index.html" class="snav-home">🎵 kanmachi63</a>
  <a href="kanmachi63_history.html">📅 履歴</a>
  <a href="kanmachi63_coplayers.html" class="nav-active">👥 共演者</a>
  <a href="kanmachi63_yearly.html">📊 年別</a>
  <a href="kanmachi63_heatmap.html">🌡️ ヒートマップ</a>
</nav>
<div class="container">

  <!-- 左：出演者リスト -->
  <div class="left-panel">
    <div class="panel-title">出演者 ({total_players}名)</div>
    <input class="search-box" type="text" id="search" placeholder="名前で絞り込み…" oninput="filterList()">
    <div class="list-wrap"><div class="player-list" id="playerList"></div></div>
    <div class="meta">集計: {now}<br>対象: 2012年8月〜2026年4月</div>
  </div>

  <!-- 右：共演者詳細 -->
  <div class="right-panel" id="rightPanel">
    <div class="placeholder">← 出演者を選んでください</div>
  </div>

</div>

<script>
const DATA = {players_json};
const byName = {{}};
DATA.forEach(p => byName[p.name] = p);

function filterList() {{
  const q = document.getElementById('search').value.trim();
  renderList(q);
}}

function renderList(filter='') {{
  const el = document.getElementById('playerList');
  el.innerHTML = DATA
    .filter(p => !filter || p.name.includes(filter))
    .map(p => `<div class="player-item" id="item-${{p.name}}" onclick="showPlayer('${{p.name.replace(/'/g, "\\\\'")}}')">
      <span class="pname">${{p.name}}</span>
      <span class="ptotal">${{p.total}}日</span>
    </div>`).join('');
}}

function showPlayer(name) {{
  const p = byName[name];
  if (!p) return;

  // URLハッシュ更新
  history.replaceState(null, '', '#' + encodeURIComponent(name));

  // アクティブ状態更新
  document.querySelectorAll('.player-item').forEach(el => el.classList.remove('active'));
  const item = document.getElementById('item-' + name);
  if (item) {{ item.classList.add('active'); item.scrollIntoView({{block:'nearest'}}); }}

  const maxDays = p.co.length > 0 ? p.co[0].days : 1;

  const coRows = p.co.map((c, i) => {{
    const cp = byName[c.name] || {{}};
    const pct = Math.round(c.days / maxDays * 100);
    return `<tr>
      <td class="co-rank">${{i+1}}</td>
      <td class="co-name" onclick="showPlayer('${{c.name.replace(/'/g, "\\\\'")}}')">
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
        <span class="inst">🎵 ${{p.inst || '不明'}}</span>
        <span class="days">📅 総出演: ${{p.total}} 日</span>
        <span>👥 共演者: ${{p.co.length}} 名</span>
      </div>
    </div>
    <div style="margin:.6em 0 1.2em;font-size:.85em;">
      <a href="${{historyUrl}}" style="color:#2980b9;text-decoration:none;">📅 出演履歴を見る</a>
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
// URLハッシュからプレイヤーを自動選択
const hash = decodeURIComponent(location.hash.slice(1));
if (hash && byName[hash]) showPlayer(hash);
</script>
</body>
</html>
"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f'HTML 出力: {path}')


if __name__ == '__main__':
    print('=== kanmachi63 共演者ランキング生成 ===\n')
    entries = load_entries()
    print('共演データ集計中...')
    total, co, instruments = build_coplayer_data(entries)
    print(f'出演者: {len(total)}名')
    write_html(total, co, instruments, 'kanmachi63_coplayers.html')
    print('\n完了！')
