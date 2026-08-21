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
