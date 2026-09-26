"""
html_common — 全レポートページ共通の HTML 断片（CSS・ナビゲーション・ヘッダ/フッタ）
デザイン変更はこのファイルを修正するだけで全ページに反映される。
"""

from __future__ import annotations

# ─── 共通 CSS ─────────────────────────────────────────────────────────────────

COMMON_CSS = """
  * { box-sizing: border-box; }
  :root {
    --bg:#0f1115; --panel:#171a20; --panel-2:#20242c; --line:#2c313b;
    --text:#f1f3f5; --muted:#9aa3ad; --accent:#ff6a2a; --accent-soft:rgba(255,106,42,.13);
  }
  body { font-family: "Hiragino Sans","Meiryo",sans-serif; margin:0; background:var(--bg); color:var(--text); }

  /* ページ見出し */
  h1 { margin:0; padding:1em 1rem .35em; color:#fff; font-size:1.35em; line-height:1.25; }
  p.meta { margin:0 1rem 1em; color:var(--muted); font-size:.82em; }
  .name a, .hname a { color: inherit; text-decoration: none; }
  .name a:hover, .hname a:hover { color: var(--accent); text-decoration: underline; }

  /* ナビゲーションバー */
  .sitenav { position:sticky; top:0; z-index:20; display:flex; align-items:center; background:#141820; height:44px; overflow-x:auto; flex-shrink:0; -webkit-overflow-scrolling:touch; border-bottom:1px solid var(--line); }
  .sitenav a { color:#d8dde3; text-decoration:none; padding:0 .95em; height:44px; line-height:44px; font-size:.82em; white-space:nowrap; display:inline-block; }
  .sitenav a:hover { background:#202630; color:#fff; }
  .sitenav a.nav-active { background:var(--accent); color:#fff; font-weight:bold; }
  .snav-home { color:#ffd9c5 !important; border-right:1px solid var(--line); }

  @media (max-width:640px) {
    .sitenav { height:42px; }
    .sitenav a { height:42px; line-height:42px; padding:0 .8em; }
    h1 { font-size:1.15em; padding:.9em .9rem .3em; }
    p.meta { margin-left:.9rem; margin-right:.9rem; }
  }
"""

# ─── 2ペイン（出演者リスト + 詳細）共通 CSS ──────────────────────────────────
# 履歴ページ・共演者ページで共通のレイアウト。
# スマホでは「一覧」と「詳細」を切り替えて表示する（body.detail-open で切替）。

TWO_PANE_CSS = """
  /* レイアウト */
  .container { display:flex; height:calc(100vh - 44px); }
  .left-panel {
    width:320px; min-width:220px; background:var(--panel); color:var(--text);
    display:flex; flex-direction:column; flex-shrink:0; border-right:1px solid var(--line);
  }
  .right-panel { flex:1; overflow-y:auto; background:linear-gradient(180deg,#12161d 0%,var(--bg) 45%); }
  .right-inner { padding:1.35em 1.6em 2em; }

  /* 左パネル */
  .panel-title { padding:.9em 1em .15em; font-size:.78em; color:var(--muted); letter-spacing:.04em; }
  .panel-hint { padding:0 1em .3em; font-size:.75em; color:#69717c; }
  .search-box {
    margin:.3em .8em .65em; padding:.7em .85em;
    border:1px solid var(--line); border-radius:8px; width:calc(100% - 1.6em);
    font-size:.95em; background:#10141a; color:var(--text); outline:none;
  }
  .search-box:focus { border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-soft); }
  .search-box::placeholder { color:#6f7782; }
  .list-wrap { flex:1; overflow:hidden; position:relative; }
  .list-wrap::after {
    content:''; pointer-events:none;
    position:absolute; bottom:0; left:0; right:0; height:3em;
    background:linear-gradient(transparent, var(--panel));
  }
  .player-list { height:100%; overflow-y:auto; -webkit-overflow-scrolling:touch; }
  .player-item {
    min-height:42px; padding:.65em 1em; cursor:pointer; font-size:.9em;
    border-left:3px solid transparent;
    display:flex; justify-content:space-between; align-items:center;
  }
  .player-item:hover { background:#202630; }
  .player-item.active { background:var(--accent); border-left-color:#fff; color:#fff; }
  .player-item .pname { flex:1; }
  .player-item .ptotal { font-size:.78em; color:var(--muted); margin-left:.5em; }
  .player-item.active .ptotal { color:#ffe; }
  .list-empty { padding:1em; color:#69717c; font-size:.85em; }

  /* 右パネル共通 */
  .detail-header { margin-bottom:1.2em; }
  .detail-name { font-size:1.65em; font-weight:bold; color:#fff; line-height:1.25; }
  .detail-meta { color:var(--muted); font-size:.88em; margin-top:.5em; display:flex; flex-wrap:wrap; gap:.5em 1.2em; }
  .detail-meta span { margin-right:0; }
  .detail-meta .inst { color:#fff; }
  .detail-meta .days { color:#ffb38d; font-weight:bold; }
  .meta { color:#69717c; font-size:.78em; padding:.65em 1em; border-top:1px solid var(--line); }

  /* 最初に出す案内（出演回数トップ20） */
  .ov-title { font-size:1.15em; color:#fff; margin:0 0 .4em; }
  .ov-lead { color:var(--muted); font-size:.88em; margin:0 0 1.4em; line-height:1.7; }
  .ov-list { list-style:none; margin:0; padding:0; max-width:620px; }
  .ov-item {
    display:flex; align-items:center; gap:.8em; cursor:pointer;
    padding:.6em .8em; border-bottom:1px solid var(--line);
  }
  .ov-item:last-child { border-bottom:none; }
  .ov-item:hover { background:#202630; }
  .ov-rank { width:1.8em; text-align:right; color:#79818c; font-size:.85em; flex-shrink:0; }
  .ov-name { color:#fff; font-size:.95em; flex:1; }
  .ov-inst { color:var(--muted); font-size:.8em; }
  .ov-days { color:#ffb38d; font-weight:bold; font-size:.9em; flex-shrink:0; }

  /* 詳細から一覧に戻る（スマホのみ） */
  .back-btn {
    display:none; align-items:center; gap:.4em;
    position:sticky; top:0; z-index:5; width:100%;
    padding:.8em 1em; border:none; border-bottom:1px solid var(--line);
    background:#141820; color:#ffd9c5; font-size:.85em; font-family:inherit;
    cursor:pointer; text-align:left;
  }

  /* スマホ: 一覧と詳細を切り替える */
  @media (max-width: 640px) {
    .container { flex-direction:column; height:auto; min-height:calc(100vh - 42px); }
    .left-panel {
      width:100%; min-width:unset; height:calc(100vh - 42px);
      border-right:none; border-bottom:1px solid var(--line);
    }
    .right-panel { display:none; flex:1; }
    .right-inner { padding:1em .9em 1.5em; }
    body.detail-open .left-panel { display:none; }
    body.detail-open .right-panel { display:block; }
    .back-btn { display:flex; }
    .detail-name { font-size:1.3em; }
  }
"""

# ─── 2ペイン共通 HTML / JS ───────────────────────────────────────────────────


def two_pane_body(total_players: int, updated: str, hint: str) -> str:
    """出演者リスト（左）と詳細（右）の共通マークアップを返す。"""
    return f"""<div class="container">

  <div class="left-panel">
    <div class="panel-title">出演者 {total_players}名 · 出演日数の多い順</div>
    <div class="panel-hint">{hint}</div>
    <input class="search-box" type="text" id="search" placeholder="名前で絞り込み…" oninput="filterList()">
    <div class="list-wrap"><div class="player-list" id="playerList"></div></div>
    <div class="meta">集計: {updated}</div>
  </div>

  <div class="right-panel" id="rightPanelWrap">
    <button type="button" class="back-btn" onclick="closeDetail()">← 出演者一覧にもどる</button>
    <div class="right-inner" id="rightPanel"></div>
  </div>

</div>
"""


# 各ページの showPlayer(name) から呼ばれる共通処理。
# renderOverview(lead) は最初に出す「よく出ている人」一覧を描く。
TWO_PANE_JS = """
function esc(s) { return String(s).replace(/'/g, "\\\\'"); }

function filterList() {
  renderList(document.getElementById('search').value.trim());
}

function renderList(filter='') {
  const el = document.getElementById('playerList');
  const hits = DATA.filter(p => !filter || p.name.includes(filter));
  if (hits.length === 0) {
    el.innerHTML = '<div class="list-empty">見つかりませんでした</div>';
    return;
  }
  el.innerHTML = hits.map(p => `<div class="player-item" id="item-${p.name}" onclick="showPlayer('${esc(p.name)}')">
      <span class="pname">${p.name}</span>
      <span class="ptotal">${p.total}日</span>
    </div>`).join('');
}

/* 詳細を開いたことを知らせる（スマホでは一覧と入れ替わる） */
function openDetail() {
  document.body.classList.add('detail-open');
  const wrap = document.getElementById('rightPanelWrap');
  if (wrap) wrap.scrollTop = 0;
  window.scrollTo(0, 0);
}

function closeDetail() {
  document.body.classList.remove('detail-open');
  history.replaceState(null, '', location.pathname + location.search);
  document.querySelectorAll('.player-item').forEach(el => el.classList.remove('active'));
  renderOverview(OVERVIEW_LEAD);
  window.scrollTo(0, 0);
}

/* 何も選ばれていないときに出す、出演回数の多い人の一覧 */
function renderOverview(lead) {
  const top = DATA.slice(0, 20);
  const rows = top.map((p, i) => `<li class="ov-item" onclick="showPlayer('${esc(p.name)}')">
      <span class="ov-rank">${i + 1}</span>
      <span class="ov-name">${p.name}<span class="ov-inst"> ${p.inst || ''}</span></span>
      <span class="ov-days">${p.total}日</span>
    </li>`).join('');
  document.getElementById('rightPanel').innerHTML = `
    <h2 class="ov-title">よく出ている人</h2>
    <p class="ov-lead">${lead}</p>
    <ol class="ov-list">${rows}</ol>`;
}
"""

# ─── ナビゲーション項目 ───────────────────────────────────────────────────────
# (href, ラベル, キー)。キーは site_nav(active=...) の指定に使う。

NAV_ITEMS = [
    ('index.html', 'kanmachi63', 'home'),
    ('kanmachi63_history.html', '履歴', 'history'),
    ('kanmachi63_coplayers.html', '共演者', 'coplayers'),
    ('kanmachi63_yearly.html', '年別', 'yearly'),
    ('kanmachi63_heatmap.html', 'ヒートマップ', 'heatmap'),
]


def site_nav(active: str = '') -> str:
    """ナビゲーションバー HTML を返す。active にはアクティブ項目のキーを指定。"""
    links = []
    for href, label, key in NAV_ITEMS:
        cls_parts = []
        if key == 'home':
            cls_parts.append('snav-home')
        if key == active:
            cls_parts.append('nav-active')
        cls_attr = f' class="{" ".join(cls_parts)}"' if cls_parts else ''
        links.append(f'  <a href="{href}"{cls_attr}>{label}</a>')
    return '<nav class="sitenav">\n' + '\n'.join(links) + '\n</nav>\n'


def page_head(title: str, css_extra: str = '', active: str = '') -> str:
    """HTML 冒頭（<!DOCTYPE>〜<body>開始 + ナビゲーション）を返す。"""
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
{COMMON_CSS}
{css_extra}
</style>
</head>
<body>
{site_nav(active)}
"""


def page_tail() -> str:
    """HTML 末尾（</body></html>）を返す。"""
    return "</body>\n</html>\n"
