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

    html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>上町63 共演者ランキング</title>
<style>
  * {{ box-sizing: border-box; }}
  :root {{
    --bg:#0f1115; --panel:#171a20; --panel-2:#20242c; --line:#2c313b;
    --text:#f1f3f5; --muted:#9aa3ad; --accent:#ff6a2a; --accent-soft:rgba(255,106,42,.13);
  }}
  body {{ font-family: "Hiragino Sans","Meiryo",sans-serif; margin:0; background:var(--bg); color:var(--text); }}

  /* ナビゲーションバー */
  .sitenav {{ position:sticky; top:0; z-index:20; display:flex; align-items:center; background:#141820; height:44px; overflow-x:auto; flex-shrink:0; -webkit-overflow-scrolling:touch; border-bottom:1px solid var(--line); }}
  .sitenav a {{ color:#d8dde3; text-decoration:none; padding:0 .95em; height:44px; line-height:44px; font-size:.82em; white-space:nowrap; display:inline-block; }}
  .sitenav a:hover {{ background:#202630; color:#fff; }}
  .sitenav a.nav-active {{ background:var(--accent); color:#fff; font-weight:bold; }}
  .snav-home {{ color:#ffd9c5 !important; border-right:1px solid var(--line); }}

  /* レイアウト */
  .container {{ display:flex; height:calc(100vh - 44px); }}
  .left-panel {{
    width:320px; min-width:220px; background:var(--panel); color:var(--text);
    display:flex; flex-direction:column; flex-shrink:0; border-right:1px solid var(--line);
  }}
  .right-panel {{ flex:1; padding:1.35em 1.6em 2em; overflow-y:auto; background:linear-gradient(180deg,#12161d 0%,var(--bg) 45%); }}

  /* 左パネル */
  .panel-title {{ padding:.9em 1em .35em; font-size:.78em; color:var(--muted); letter-spacing:.04em; }}
  .search-box {{
    margin:.3em .8em .65em; padding:.7em .85em;
    border:1px solid var(--line); border-radius:8px; width:calc(100% - 1.6em);
    font-size:.95em; background:#10141a; color:var(--text);
    outline:none;
  }}
  .search-box:focus {{ border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-soft); }}
  .search-box::placeholder {{ color:#6f7782; }}
  .list-wrap {{ flex:1; overflow:hidden; position:relative; }}
  .list-wrap::after {{
    content:''; pointer-events:none;
    position:absolute; bottom:0; left:0; right:0; height:3em;
    background:linear-gradient(transparent, var(--panel));
  }}
  .player-list {{ height:100%; overflow-y:auto; -webkit-overflow-scrolling:touch; }}
  .player-item {{
    min-height:42px; padding:.65em 1em; cursor:pointer; font-size:.9em;
    border-left:3px solid transparent;
    display:flex; justify-content:space-between; align-items:center;
  }}
  .player-item:hover {{ background:#202630; }}
  .player-item.active {{ background:var(--accent); border-left-color:#fff; color:#fff; }}
  .player-item .pname {{ flex:1; }}
  .player-item .ptotal {{ font-size:.78em; color:var(--muted); margin-left:.5em; }}
  .player-item.active .ptotal {{ color:#ffe; }}

  /* 右パネル */
  .placeholder {{
    display:flex; align-items:center; justify-content:center;
    height:60%; color:#69717c; font-size:1em;
  }}
  .detail-header {{ margin-bottom:1.2em; }}
  .detail-name {{ font-size:1.65em; font-weight:bold; color:#fff; line-height:1.25; }}
  .detail-meta {{ color:var(--muted); font-size:.88em; margin-top:.5em; display:flex; flex-wrap:wrap; gap:.5em 1.2em; }}
  .detail-meta span {{ margin-right:0; }}
  .detail-meta .inst {{ color:#fff; }}
  .detail-meta .days {{ color:#ffb38d; font-weight:bold; }}

  h3 {{ font-size:.95em; color:#c8ced6; margin:1.2em 0 .6em; border-bottom:1px solid var(--line); padding-bottom:.45em; }}

  /* 共演者テーブル */
  .co-table {{ border-collapse:collapse; width:100%; max-width:620px; background:var(--panel);
               border:1px solid var(--line); border-radius:8px; overflow:hidden; }}
  .co-table th {{ background:#11151b; color:#d8dde3; padding:9px 14px; text-align:left; font-size:.78em; }}
  .co-table td {{ padding:9px 14px; border-bottom:1px solid var(--line); font-size:.9em; }}
  .co-table tr:last-child td {{ border-bottom:none; }}
  .co-table tr:hover td {{ background:#202630; }}
  .co-rank {{ width:3em; text-align:center; color:#79818c; font-size:.85em; }}
  .co-name {{ cursor:pointer; color:#fff; white-space:nowrap; }}
  .co-name:hover {{ text-decoration:underline; }}
  .co-days {{ text-align:center; font-weight:bold; color:#ffb38d; width:5em; }}
  .co-inst {{ color:var(--muted); font-size:.82em; }}
  .co-pct {{ width:80px; }}
  .bar-bg {{ background:#2f3540; border-radius:3px; height:8px; }}
  .bar-fill {{ background:var(--accent); border-radius:3px; height:8px; }}

  .meta {{ color:#69717c; font-size:.78em; padding:.65em 1em; border-top:1px solid var(--line); }}

  /* スマホ対応 */
  @media (max-width: 640px) {{
    .sitenav {{ height:42px; }}
    .sitenav a {{ height:42px; line-height:42px; padding:0 .8em; }}
    .container {{ flex-direction:column; height:auto; min-height:calc(100vh - 42px); }}
    .left-panel {{ width:100%; height:36vh; min-height:230px; max-height:330px; min-width:unset; flex-shrink:0; border-right:none; border-bottom:1px solid var(--line); }}
    .right-panel {{ flex:1; padding:1em .9em 1.5em; }}
    .detail-name {{ font-size:1.3em; }}
    .co-inst {{ display:none; }}
    .co-pct {{ display:none; }}
    .co-table th, .co-table td {{ padding:9px 10px; }}
  }}
</style>
</head>
<body>
<nav class="sitenav">
  <a href="index.html" class="snav-home">kanmachi63</a>
  <a href="kanmachi63_history.html">履歴</a>
  <a href="kanmachi63_coplayers.html" class="nav-active">共演者</a>
  <a href="kanmachi63_yearly.html">年別</a>
  <a href="kanmachi63_heatmap.html">ヒートマップ</a>
</nav>
<div class="container">

  <!-- 左：出演者リスト -->
  <div class="left-panel">
    <div class="panel-title">出演者 ({total_players}名)</div>
    <input class="search-box" type="text" id="search" placeholder="名前で絞り込み…" oninput="filterList()">
    <div class="list-wrap"><div class="player-list" id="playerList"></div></div>
    <div class="meta">集計: {now}</div>
  </div>

  <!-- 右：共演者詳細 -->
  <div class="right-panel" id="rightPanel">
    <div class="placeholder">出演者を選んでください</div>
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
    entries = load_all_entries()
    if not entries:
        raise SystemExit('エラー: 記事を1件も取得できませんでした。処理を中止します。')
    print('共演データ集計中...')
    total, co, instruments = build_coplayer_data(entries)
    print(f'出演者: {len(total)}名')
    write_html(total, co, instruments, 'kanmachi63_coplayers.html')
    print('\n完了！')
