#!/usr/bin/env python3
"""
kanmachi63 出演履歴
出演者ごとの日付別共演者を集計してインタラクティブHTMLを出力します。
"""

import re
import html
import json
from collections import defaultdict
from datetime import datetime
from urllib.parse import quote

from scrape_kanmachi import (
    BlogParser, NextPageParser, SCHEDULE_TITLE_RE,
    _prepare_text, _parse_performers, DATE_LINE_RE,
    normalize_name, fetch_cached,
)

DATE_DAY_RE = re.compile(r'(\d+)月(\d+)日')
# タイトルから年と月を取得: "2026|　4月のスケジュール" or "2026年4月のスケジュール" など
TITLE_YEAR_RE = re.compile(r'(20\d{2})')
TITLE_MONTH_RE = re.compile(r'(\d+)月のスケジュール')


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


def build_history_data(entries):
    """
    戻り値:
      history[name] = [{'date': '2024-07-15', 'co': [{'name':..., 'inst':...}, ...]}, ...]
      instruments[name] = 使用楽器セット
      total[name]    = 総出演日数
    """
    history = defaultdict(list)
    instruments = defaultdict(set)
    total = defaultdict(int)

    for entry in entries:
        if not SCHEDULE_TITLE_RE.search(entry['title']):
            continue

        ym = TITLE_YEAR_RE.search(entry['title'])
        mm = TITLE_MONTH_RE.search(entry['title'])
        if not ym or not mm:
            continue
        title_year, title_month = int(ym.group(1)), int(mm.group(1))

        text = _prepare_text(entry['body_html'])
        lines = text.splitlines()
        current_date_str, current_lines = None, []
        day_groups = []

        for line in lines:
            if DATE_LINE_RE.search(line):
                if current_lines:
                    day_groups.append((current_date_str, current_lines))
                current_date_str = DATE_LINE_RE.search(line).group()
                current_lines = [line]
            elif current_date_str:
                current_lines.append(line)
        if current_lines:
            day_groups.append((current_date_str, current_lines))

        for date_str, chunk in day_groups:
            dm = DATE_DAY_RE.search(date_str)
            if not dm:
                continue
            d_month, d_day = int(dm.group(1)), int(dm.group(2))

            # 年末年始またぎを考慮
            year = title_year
            if d_month == 1 and title_month == 12:
                year = title_year + 1
            elif d_month == 12 and title_month == 1:
                year = title_year - 1

            full_date = f'{year}-{d_month:02d}-{d_day:02d}'

            performers = _parse_performers(' '.join(chunk))
            name_inst_pairs = []
            for inst, raw_name in performers:
                name = normalize_name(raw_name)
                if name is None:
                    continue
                instruments[name].add(inst)
                name_inst_pairs.append({'name': name, 'inst': inst})

            # 同名重複除去（最初の楽器を採用）
            seen = set()
            unique = []
            for p in name_inst_pairs:
                if p['name'] not in seen:
                    seen.add(p['name'])
                    unique.append(p)

            is_explicit_solo = bool(re.search(r'\bSOLO\b', ' '.join(chunk), re.IGNORECASE))

            for p in unique:
                total[p['name']] += 1
                co = [q for q in unique if q['name'] != p['name']]
                solo = is_explicit_solo and len(unique) == 1
                history[p['name']].append({'date': full_date, 'co': co, 'solo': solo})

    # 日付昇順でソート
    for name in history:
        history[name].sort(key=lambda x: x['date'])

    return dict(history), dict(instruments), dict(total)


def write_html(history, instruments, total, path):
    sorted_names = sorted(total.keys(), key=lambda n: -total[n])

    players_data = []
    for name in sorted_names:
        players_data.append({
            'name': name,
            'total': total[name],
            'inst': ' / '.join(sorted(instruments.get(name, set()))),
            'dates': history.get(name, []),
        })

    players_json = json.dumps(players_data, ensure_ascii=False)
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    total_players = len(sorted_names)

    html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>上町63 出演履歴</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: "Hiragino Sans","Meiryo",sans-serif; margin:0; background:#f0f2f5; color:#222; }}

  /* ナビゲーションバー */
  .sitenav {{ display:flex; align-items:center; background:#2c3e50; height:40px; overflow-x:auto; flex-shrink:0; -webkit-overflow-scrolling:touch; }}
  .sitenav a {{ color:#bdc3c7; text-decoration:none; padding:0 .9em; height:40px; line-height:40px; font-size:.82em; white-space:nowrap; display:inline-block; }}
  .sitenav a:hover {{ background:#34495e; color:#ecf0f1; }}
  .sitenav a.nav-active {{ background:#1abc9c; color:#fff; font-weight:bold; }}
  .snav-home {{ color:#c8a84b !important; border-right:1px solid #3d5166; }}

  .container {{ display:flex; height:calc(100vh - 40px); }}
  .left-panel {{
    width:300px; min-width:200px; background:#2c3e50; color:#ecf0f1;
    display:flex; flex-direction:column; flex-shrink:0;
  }}
  .right-panel {{ flex:1; padding:1.5em; overflow-y:auto; }}

  .panel-title {{ padding:.8em 1em .4em; font-size:.85em; color:#95a5a6; letter-spacing:.05em; }}
  .search-box {{
    margin:.3em .8em .6em; padding:.5em .8em;
    border:none; border-radius:6px; width:calc(100% - 1.6em);
    font-size:.9em; background:#34495e; color:#ecf0f1; outline:none;
  }}
  .search-box::placeholder {{ color:#7f8c8d; }}
  .list-wrap {{ flex:1; overflow:hidden; position:relative; }}
  .list-wrap::after {{
    content:''; pointer-events:none;
    position:absolute; bottom:0; left:0; right:0; height:3em;
    background:linear-gradient(transparent, #2c3e50);
  }}
  .player-list {{ height:100%; overflow-y:auto; -webkit-overflow-scrolling:touch; }}
  .player-item {{
    padding:.55em 1em; cursor:pointer; font-size:.88em;
    border-left:3px solid transparent;
    display:flex; justify-content:space-between; align-items:center;
  }}
  .player-item:hover {{ background:#34495e; }}
  .player-item.active {{ background:#1abc9c; border-left-color:#f1c40f; color:#fff; }}
  .player-item .pname {{ flex:1; }}
  .player-item .ptotal {{ font-size:.8em; color:#95a5a6; margin-left:.5em; }}
  .player-item.active .ptotal {{ color:#dff; }}

  .placeholder {{
    display:flex; align-items:center; justify-content:center;
    height:60%; color:#aaa; font-size:1.1em;
  }}
  .detail-header {{ margin-bottom:1.2em; }}
  .detail-name {{ font-size:1.6em; font-weight:bold; color:#2c3e50; }}
  .detail-meta {{ color:#777; font-size:.88em; margin-top:.3em; }}
  .detail-meta span {{ margin-right:1.5em; }}
  .detail-meta .inst {{ color:#2980b9; }}
  .detail-meta .days {{ color:#c0392b; font-weight:bold; }}

  .links {{ margin:.6em 0 1em; font-size:.85em; }}
  .links a {{ color:#2980b9; text-decoration:none; margin-right:1.2em; }}
  .links a:hover {{ text-decoration:underline; }}

  /* 年タブ */
  .yr-tabs {{ display:flex; flex-wrap:wrap; gap:.35em; margin:.2em 0 1.2em; }}
  .yr-tab {{
    border:1px solid #ddd; background:#fff; padding:.3em .7em;
    border-radius:4px; cursor:pointer; font-size:.82em; color:#555;
  }}
  .yr-tab:hover {{ background:#eef2f7; border-color:#aaa; }}
  .yr-tab.active {{ background:#2c3e50; color:#fff; border-color:#2c3e50; font-weight:bold; }}

  h3 {{ font-size:1em; color:#555; margin:1.2em 0 .5em; border-bottom:1px solid #ddd; padding-bottom:.3em; }}

  /* 年グループ */
  .year-group {{ margin-bottom:1.5em; }}
  .year-label {{
    font-size:.85em; font-weight:bold; color:#fff;
    background:#2c3e50; display:inline-block;
    padding:.2em .8em; border-radius:3px; margin-bottom:.5em;
  }}

  /* 日付ごとの行 */
  .date-row {{
    display:flex; align-items:flex-start; gap:1em;
    padding:.5em 0; border-bottom:1px solid #eee; font-size:.88em;
  }}
  .date-row:last-child {{ border-bottom:none; }}
  .date-label {{
    min-width:5.5em; color:#555; font-weight:bold; flex-shrink:0; padding-top:.1em;
  }}
  .co-chips {{ display:flex; flex-wrap:wrap; gap:.35em; }}
  .chip {{
    background:#eef2f7; border-radius:4px; padding:.2em .6em;
    font-size:.85em; cursor:pointer; white-space:nowrap;
  }}
  .chip:hover {{ background:#d4e6f1; }}
  .chip .chip-inst {{ color:#7f8c8d; font-size:.8em; margin-left:.3em; }}
  .no-co {{ color:#aaa; font-size:.85em; font-style:italic; }}

  .meta {{ color:#888; font-size:.8em; padding:.5em 1em; border-top:1px solid #3d5166; }}

  @media (max-width: 640px) {{
    .container {{ flex-direction:column; height:auto; min-height:calc(100vh - 40px); }}
    .left-panel {{ width:100%; height:40vh; min-width:unset; flex-shrink:0; }}
    .right-panel {{ flex:1; padding:1em; }}
    .detail-name {{ font-size:1.3em; }}
  }}
</style>
</head>
<body>
<nav class="sitenav">
  <a href="index.html" class="snav-home">🎵 kanmachi63</a>
  <a href="kanmachi63_history.html" class="nav-active">📅 履歴</a>
  <a href="kanmachi63_coplayers.html">👥 共演者</a>
  <a href="kanmachi63_yearly.html">📊 年別</a>
  <a href="kanmachi63_heatmap.html">🌡️ ヒートマップ</a>
</nav>
<div class="container">

  <div class="left-panel">
    <div class="panel-title">出演者 ({total_players}名)</div>
    <input class="search-box" type="text" id="search" placeholder="名前で絞り込み…" oninput="filterList()">
    <div class="list-wrap"><div class="player-list" id="playerList"></div></div>
    <div class="meta">集計: {now}<br>対象: 2012年8月〜2026年4月</div>
  </div>

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

function showPlayer(name, year) {{
  const p = byName[name];
  if (!p) return;

  // URLハッシュ更新（year指定あり: #name/year、なし: #name）
  const hashVal = encodeURIComponent(name) + (year ? '/' + year : '');
  history.replaceState(null, '', '#' + hashVal);

  document.querySelectorAll('.player-item').forEach(el => el.classList.remove('active'));
  const item = document.getElementById('item-' + name);
  if (item) {{ item.classList.add('active'); item.scrollIntoView({{block:'nearest'}}); }}

  // 年別グループ化
  const byYear = {{}};
  for (const d of p.dates) {{
    const y = d.date.slice(0, 4);
    if (!byYear[y]) byYear[y] = [];
    byYear[y].push(d);
  }}
  const years = Object.keys(byYear).sort((a, b) => b - a);

  // 有効な年を確定（指定がなければ最新年）
  const activeYear = year && byYear[year] ? year : years[0];

  // 年タブ
  const esc = n => n.replace(/'/g, "\\'");
  const tabs = years.map(y => {{
    const cls = y === activeYear ? ' active' : '';
    return `<button class="yr-tab${{cls}}" onclick="showPlayer('${{esc(name)}}', '${{y}}')">${{y}}年</button>`;
  }}).join('');

  // 表示する日付リスト（選択年のみ、新しい順）
  const dates = (byYear[activeYear] || []).slice().reverse();
  const rows = dates.map(d => {{
    const [, mm, dd] = d.date.split('-');
    const dateLabel = `${{parseInt(mm)}}/${{parseInt(dd)}}`;
    const chips = d.co.length > 0
      ? d.co.map(c => `<span class="chip" onclick="showPlayer('${{esc(c.name)}}')">
          ${{c.name}}<span class="chip-inst">${{c.inst}}</span>
        </span>`).join('')
      : d.solo
        ? '<span class="no-co">solo</span>'
        : '<span class="no-co">共演者不明</span>';
    return `<div class="date-row">
      <div class="date-label">${{dateLabel}}</div>
      <div class="co-chips">${{chips}}</div>
    </div>`;
  }}).join('');

  const coplayersUrl = 'kanmachi63_coplayers.html#' + encodeURIComponent(name);
  const yearCount = dates.length;

  document.getElementById('rightPanel').innerHTML = `
    <div class="detail-header">
      <div class="detail-name">${{p.name}}</div>
      <div class="detail-meta">
        <span class="inst">🎵 ${{p.inst || '不明'}}</span>
        <span class="days">📅 総出演: ${{p.total}} 日</span>
      </div>
    </div>
    <div class="links">
      <a href="${{coplayersUrl}}">👥 共演者ランキングを見る</a>
    </div>
    <div class="yr-tabs">${{tabs}}</div>
    <h3>${{activeYear}}年の出演 (${{yearCount}}日)</h3>
    ${{rows || '<p style="color:#aaa">データなし</p>'}}
  `;
}}

renderList();
// ハッシュ解析: #name または #name/year
const rawHash = decodeURIComponent(location.hash.slice(1));
const slashIdx = rawHash.indexOf('/');
const initName = slashIdx >= 0 ? rawHash.slice(0, slashIdx) : rawHash;
const initYear = slashIdx >= 0 ? rawHash.slice(slashIdx + 1) : null;
if (initName && byName[initName]) showPlayer(initName, initYear);
</script>
</body>
</html>
"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f'HTML 出力: {path}')


if __name__ == '__main__':
    print('=== kanmachi63 出演履歴生成 ===\n')
    entries = load_entries()
    print('履歴データ集計中...')
    history, instruments, total = build_history_data(entries)
    print(f'出演者: {len(total)}名')
    write_html(history, instruments, total, 'kanmachi63_history.html')
    print('\n完了！')
