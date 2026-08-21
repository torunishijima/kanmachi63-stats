#!/usr/bin/env python3
"""
kanmachi63 ブログ スクレイパー
月次スケジュール記事からミュージシャンの出演回数を集計します。
"""

import json
import re
import csv
import time
import html
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from collections import defaultdict
from html.parser import HTMLParser
from datetime import datetime

from html_common import page_head, page_tail

# 設定ファイル（楽器コード・名前エイリアス）の場所
CONFIG_DIR = Path(__file__).resolve().parent / 'config'


def _load_json_config(name: str) -> dict:
    path = CONFIG_DIR / name
    if not path.exists():
        raise FileNotFoundError(f'設定ファイルがありません: {path}')
    return json.loads(path.read_text(encoding='utf-8'))


# ─── HTML パーサー ────────────────────────────────────────────────────────────

class BlogParser(HTMLParser):
    """FC2ブログページから記事一覧を抽出するパーサー"""

    def __init__(self):
        super().__init__()
        self.entries = []
        self._in_header = False
        self._in_body = False
        self._current_title = ''
        self._current_body = []
        self._body_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        cls = attrs_dict.get('class', '')

        if tag == 'h2' and 'entry_header' in cls:
            self._in_header = True
            self._current_title = ''

        if tag == 'div' and 'entry_body' in cls:
            self._in_body = True
            self._body_depth = 0
            self._current_body = []

        if self._in_body:
            if tag == 'div':
                self._body_depth += 1
            if tag in ('s', 'del', 'strike'):
                self._current_body.append(f'<{tag}>')
            elif tag == 'br':
                self._current_body.append('\n')

    def handle_endtag(self, tag):
        if tag == 'h2' and self._in_header:
            self._in_header = False

        if self._in_body:
            if tag in ('s', 'del', 'strike'):
                self._current_body.append(f'</{tag}>')
            if tag == 'div':
                self._body_depth -= 1
                if self._body_depth < 0:
                    self._in_body = False
                    if self._current_title:
                        self.entries.append({
                            'title': self._current_title.strip(),
                            'body_html': ''.join(self._current_body),
                        })
                    self._current_title = ''
                    self._current_body = []

    def handle_data(self, data):
        if self._in_header:
            self._current_title += data
        if self._in_body:
            self._current_body.append(data)


class NextPageParser(HTMLParser):
    """ページネーションの「次のページ」URLを抽出するパーサー"""

    def __init__(self):
        super().__init__()
        self.next_url = None

    def handle_starttag(self, tag, attrs):
        if tag == 'link':
            attrs_dict = dict(attrs)
            if attrs_dict.get('rel') == 'next':
                self.next_url = attrs_dict.get('href')


# ─── テキスト正規化 ──────────────────────────────────────────────────────────

def to_halfwidth(text: str) -> str:
    """全角英数字・記号を半角に変換する"""
    result = []
    for ch in text:
        code = ord(ch)
        # 全角英数字 (Ａ-Ｚ, ａ-ｚ, ０-９)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        # 全角スペース → 半角スペース
        elif ch == '\u3000':
            result.append(' ')
        else:
            result.append(ch)
    return ''.join(result)


# ─── 楽器コード定義 ──────────────────────────────────────────────────────────

_instruments_cfg = _load_json_config('instruments.json')
_KNOWN_INSTRUMENTS = set(_instruments_cfg.get('known_instruments', []))
_NON_INSTRUMENTS = set(_instruments_cfg.get('non_instruments', []))

def _is_instrument(part: str) -> bool:
    codes = [c for c in part.lower().split('.') if c]
    if not codes:
        return False
    if any(c in _NON_INSTRUMENTS for c in codes):
        return False
    return any(c in _KNOWN_INSTRUMENTS for c in codes)


# ─── 名前クリーニング ────────────────────────────────────────────────────────

# 名前末尾から除去するパターン（順に適用）
_NAME_TAIL_PATTERNS = [
    r'[Ｓｓ][Ｏｏ][Ｌｌ][Ｏｏ]$',         # ＳＯＬＯ（全角）
    r'SOLO$',                               # SOLO（半角）
    r'【[^】]*】',                           # 【SOLDOUT】など
    r'（[^）]*）$',                          # （補足）
    r'[￥¥][\d,，\s]*$',                    # ¥3,300 などの価格
    r'(?<=[\u3040-\u30ff\u4e00-\u9fff])[a-zA-Z]{2,4}$',  # CJK文字の後に残った楽器コード (pf, ds, etc.)
    r'[\.．。、,，\s]+$',                    # 末尾の記号
]
_NAME_TAIL_RE = [re.compile(p, re.UNICODE) for p in _NAME_TAIL_PATTERNS]

# CJK文字（漢字・ひらがな・カタカナ）の先頭マッチ
_CJK_START = r'[\u3040-\u30ff\u4e00-\u9fff]'

# 名前先頭から除去するパターン
_NAME_HEAD_PATTERNS = [
    r'^[\.．。、,，\s]+',                        # 先頭の記号・空白
    r'^(?:[a-z]{1,8}\.)+',                     # 半角楽器コード+ドット (ss.、ts.ss. など)
    r'^[a-z]{2,}(?=' + _CJK_START + r')',       # ドットなし小文字prefix + CJK (etcかみむら、harp岩石 など)
]
_NAME_HEAD_RE = [re.compile(p, re.UNICODE) for p in _NAME_HEAD_PATTERNS]

def clean_name(name: str) -> str:
    """名前文字列から末尾・先頭のノイズを除去して正規化する"""
    name = name.strip()
    # 末尾ノイズを繰り返し除去
    prev = None
    while prev != name:
        prev = name
        for pat in _NAME_TAIL_RE:
            name = pat.sub('', name).strip()
    # 先頭ノイズを繰り返し除去
    prev = None
    while prev != name:
        prev = name
        for pat in _NAME_HEAD_RE:
            name = pat.sub('', name).strip()
    return name


# 名前エイリアスマップ（略称・誤字 → 正式名）は config/names.json から読み込む。
# 値が null のものは「明らかなノイズ」として除外。
_NAME_ALIASES: dict[str, str | None] = {
    k: (v if v is not None else None) for k, v in _load_json_config('names.json').items()
}

def normalize_name(name: str) -> str | None:
    """
    clean_name() → エイリアス解決 → None なら除外対象
    """
    name = clean_name(name)
    if name in _NAME_ALIASES:
        return _NAME_ALIASES[name]   # None の場合は除外
    return name if name else None


# ─── 出演者抽出 ──────────────────────────────────────────────────────────────

# スケジュール記事タイトルのパターン
SCHEDULE_TITLE_RE = re.compile(r'[0-9０-９]+月のスケジュール', re.UNICODE)
YEAR_MONTH_RE = re.compile(r'(20\d{2})年(\d+)月のスケジュール')

# 出演者パターン: 「楽器コード.名前」（半角化済みテキストに適用）
PERFORMER_TOKEN_RE = re.compile(
    r'((?:[a-zA-Z]{1,8}\.)+)[ \t]?'               # 楽器部分（直後の半角スペース1つを許容）
    r'((?:(?![a-z]{1,8}\.)[^\s、。,，\n<「」\[\]（）()@￥¥])+)',  # 名前部分
    re.UNICODE
)
# 西洋人名の姓部分: 大文字始まりでドットが直後に来ない単語
_SURNAME_RE = re.compile(r'[ \t]+([A-Z][a-zA-Z]+)(?!\.)')

# 日付行検出パターン（例: 4月1日、10月15日（祝））
DATE_LINE_RE = re.compile(r'\d+月\d+日')


def _prepare_text(body_html: str) -> str:
    """HTMLから取り消し線除去・タグ除去・全角正規化を行い、プレーンテキストを返す"""
    text = re.sub(r'<s>.*?</s>', '', body_html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<del>.*?</del>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<strike>.*?</strike>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = to_halfwidth(text)
    # 「○日○日」→「○月○日」の誤字を修正（例: 12日28日 → 12月28日）
    text = re.sub(r'(\d+)日(\d+)日', r'\1月\2日', text)
    return text


def _parse_performers(text: str) -> list[tuple[str, str]]:
    """プレーンテキストから出演者 (instrument, name) リストを返す"""
    results = []
    for m in PERFORMER_TOKEN_RE.finditer(text):
        instrument_raw = m.group(1).rstrip('.')
        name = m.group(2).strip()
        if not _is_instrument(instrument_raw):
            continue
        if not name or re.match(r'^[\d]', name):
            continue
        if len(name) < 2:
            continue
        # 日本語を含まないASCII名: 小文字始まりはJSコード等のノイズとして除外
        if not re.search(r'[\u3000-\u9fff\uff00-\uffef\u3040-\u30ff]', name) and re.match(r'^[a-z]', name):
            continue
        # 全大文字のASCII名（CHAKA, JOSENなど）はタイトルケースに正規化
        if re.match(r'^[A-Z]{2,}$', name):
            name = name.title()
        # 大文字始まりASCII名（Todd, Rosarioなど）の後に姓が続く場合は連結
        if re.match(r'^[A-Z][a-zA-Z]+$', name):
            sm = _SURNAME_RE.match(text[m.end():])
            if sm:
                surname = sm.group(1)
                if re.match(r'^[A-Z]{2,}$', surname):
                    surname = surname.title()
                name = name + ' ' + surname
        results.append((instrument_raw, name))
    return results


def extract_performers_by_date(body_html: str) -> list[list[tuple[str, str]]]:
    """
    記事本文HTMLを日付ごとに分割し、各日の出演者リストを返す。
    取り消し線内は除外。
    戻り値: [ [(instrument, name), ...], ... ]  # 日付ごとのリスト
    """
    text = _prepare_text(body_html)
    lines = text.splitlines()

    # 日付行でグループ化
    day_chunks: list[list[str]] = []
    current: list[str] = []
    in_schedule = False

    for line in lines:
        if DATE_LINE_RE.search(line):
            if current:
                day_chunks.append(current)
            current = [line]
            in_schedule = True
        elif in_schedule:
            current.append(line)

    if current:
        day_chunks.append(current)

    # 各日のテキストから出演者を抽出
    result = []
    for chunk in day_chunks:
        chunk_text = ' '.join(chunk)
        performers = _parse_performers(chunk_text)
        if performers:
            result.append(performers)

    return result


def extract_performers_from_body(body_html: str) -> list[tuple[str, str]]:
    """後方互換用：記事全体の出演者フラットリストを返す"""
    return _parse_performers(_prepare_text(body_html))


# ─── ネットワーク & キャッシュ ───────────────────────────────────────────────

CACHE_DIR = Path('.page_cache')

# 先頭から何ページを再取得するか。古い記事は内容が変わらないため全ページ取得は不要。
# 全ページ再取得はリクエストが集中して 403 を招くので既定にしない。
DEFAULT_REFRESH_PAGES = 3

# 一時的な遮断とみなして再試行する HTTP ステータス
RETRYABLE_STATUS = {403, 429, 500, 502, 503, 504}

def cache_path_for_url(url: str) -> Path:
    """URLに対応するキャッシュファイルのパスを返す"""
    safe = re.sub(r'[^\w]', '_', url) + '.html'
    return CACHE_DIR / safe

def fetch(url: str) -> str:
    """URLからHTMLを取得して文字列で返す。平文httpはhttpsに正規化してから取得する。"""
    if url.startswith('http://'):
        url = 'https://' + url[len('http://'):]
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (compatible; kanmachi-stats/1.0)'}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    for enc in ('utf-8', 'shift_jis', 'euc-jp', 'iso-2022-jp'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='replace')


def fetch_with_retry(url: str, attempts: int = 4, base_delay: float = 3.0) -> str:
    """
    指数バックオフ付きでURLを取得する。
    403/429/5xx は一時的な遮断とみなして待機後に再試行し、
    404 などの恒久的なエラーは即座に送出する。
    """
    delay = base_delay
    for attempt in range(1, attempts + 1):
        try:
            return fetch(url)
        except urllib.error.HTTPError as e:
            if e.code not in RETRYABLE_STATUS or attempt == attempts:
                raise
            wait = delay
            retry_after = e.headers.get('Retry-After') if e.headers else None
            if retry_after:
                try:
                    wait = max(wait, float(retry_after))
                except ValueError:
                    pass
            print(f'    HTTP {e.code} — {wait:.0f}秒待機して再試行 ({attempt}/{attempts})')
            time.sleep(wait)
            delay *= 2.5
        except urllib.error.URLError as e:
            if attempt == attempts:
                raise
            print(f'    通信エラー ({e.reason}) — {delay:.0f}秒待機して再試行 ({attempt}/{attempts})')
            time.sleep(delay)
            delay *= 2.5
    raise RuntimeError(f'取得に失敗しました: {url}')


def fetch_cached_with_meta(url: str, refresh: bool = False) -> tuple[str, bool]:
    """
    URLのHTMLを返す。
    refresh=True の場合はキャッシュがあっても再取得する。
    再取得に失敗してもキャッシュがあればそれを使う（警告を出す）。
    戻り値: (HTML文字列, キャッシュヒットならTrue)
    """
    CACHE_DIR.mkdir(exist_ok=True)
    cache_path = cache_path_for_url(url)
    if cache_path.exists() and not refresh:
        return cache_path.read_text(encoding='utf-8'), True
    try:
        text = fetch_with_retry(url)
    except Exception as e:
        if cache_path.exists():
            print(f'    警告: 再取得に失敗したためキャッシュを使用します ({e})')
            return cache_path.read_text(encoding='utf-8'), True
        raise
    cache_path.write_text(text, encoding='utf-8')
    return text, False


def fetch_cached(url: str, refresh: bool = False) -> str:
    """URLのHTML文字列を返す"""
    text, _ = fetch_cached_with_meta(url, refresh=refresh)
    return text


def load_all_entries(refresh_pages: int | None = DEFAULT_REFRESH_PAGES) -> list[dict]:
    """
    ブログ全ページを巡回して記事一覧を返す（各レポート共通の読み込み処理）。
    refresh_pages は先頭から再取得するページ数（既定 DEFAULT_REFRESH_PAGES）。
    None を渡すと全ページを再取得する。取得に失敗した場合はページを読み飛ばさず例外を送出する
    （黙って欠落したデータで集計が進むのを防ぐため）。
    """
    entries = []
    start_url = 'https://kanmachi63.blog.fc2.com/'
    url = start_url
    visited = set()
    page_num = 0
    while url and url not in visited:
        visited.add(url)
        refresh = refresh_pages is None or page_num < refresh_pages
        text = fetch_cached(url, refresh=refresh)
        p = BlogParser()
        p.feed(text)
        entries.extend(p.entries)
        np = NextPageParser()
        np.feed(text)
        url = np.next_url
        page_num += 1
    print(f'{len(entries)} 記事読み込み完了')
    return entries


# ─── メイン処理 ───────────────────────────────────────────────────────────────

def scrape_all_pages(start_url: str, refresh_pages: int | None = DEFAULT_REFRESH_PAGES) -> list[dict]:
    """
    全ページを巡回して記事一覧を返す。
    refresh_pages は先頭から再取得するページ数。None を渡すと全ページを再取得する。
    取得に失敗した場合はページを読み飛ばさず例外を送出する
    （黙って欠落したデータで集計が進むのを防ぐため）。
    """
    all_entries = []
    url = start_url
    page_num = 0

    while url:
        print(f'  取得中: {url}')
        refresh = refresh_pages is None or page_num < refresh_pages
        html_text, cache_hit = fetch_cached_with_meta(url, refresh=refresh)

        parser = BlogParser()
        parser.feed(html_text)
        all_entries.extend(parser.entries)
        print(f'    → 記事数: {len(parser.entries)} 件 (累計: {len(all_entries)} 件)')

        next_parser = NextPageParser()
        next_parser.feed(html_text)
        next_url = next_parser.next_url

        page_num += 1
        # キャッシュから読んだ場合はスリープしない
        if next_url and not cache_hit:
            time.sleep(1)
        url = next_url

    print(f'\n全 {page_num} ページ取得完了、合計 {len(all_entries)} 記事')
    return all_entries


def aggregate(entries: list[dict]) -> dict:
    """スケジュール記事から出演者を日付単位で集計する"""
    stats = defaultdict(lambda: {'instruments': set(), 'count': 0, 'articles': []})
    schedule_count = 0
    total_days = 0

    for entry in entries:
        title = entry['title']
        if not SCHEDULE_TITLE_RE.search(title):
            continue

        schedule_count += 1
        day_groups = extract_performers_by_date(entry['body_html'])
        total_days += len(day_groups)

        seen_in_article = set()  # 記事内で初出のときだけ articles に追加
        for performers in day_groups:
            seen_in_day = set()
            for instrument, raw_name in performers:
                name = normalize_name(raw_name)
                if name is None:
                    continue
                stats[name]['instruments'].add(instrument)
                if name not in seen_in_day:
                    stats[name]['count'] += 1
                    seen_in_day.add(name)
                if name not in seen_in_article:
                    stats[name]['articles'].append(title)
                    seen_in_article.add(name)

    print(f'スケジュール記事: {schedule_count} 件')
    print(f'集計した出演日数: {total_days} 日分')
    print(f'ユニーク出演者: {len(stats)} 名')
    return dict(stats)


# ─── 期間情報 ─────────────────────────────────────────────────────────────────

_TITLE_YEAR_RE  = re.compile(r'(20\d{2})')
_TITLE_MONTH_RE = re.compile(r'(\d+)月のスケジュール')

def get_period(entries: list[dict]) -> tuple[str, str, int]:
    """スケジュール記事の期間（開始、終了、件数）を返す"""
    months = []
    for entry in entries:
        title = entry['title']
        ym = _TITLE_YEAR_RE.search(title)
        mm = _TITLE_MONTH_RE.search(title)
        if ym and mm:
            months.append((int(ym.group(1)), int(mm.group(1))))
    if not months:
        return '不明', '不明', 0
    months.sort()
    start = f'{months[0][0]}年{months[0][1]}月'
    end = f'{months[-1][0]}年{months[-1][1]}月'
    return start, end, len(months)


# ─── 出力 ────────────────────────────────────────────────────────────────────

def write_csv(stats: dict, path: str):
    rows = []
    for name, info in stats.items():
        rows.append({
            'name': name,
            'instruments': ' / '.join(sorted(info['instruments'])),
            'count': info['count'],
        })
    rows.sort(key=lambda r: (-r['count'], r['name']))

    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=['name', 'instruments', 'count'])
        writer.writeheader()
        writer.writerows(rows)
    print(f'CSV 出力: {path}')


def write_html(stats: dict, path: str, period_start: str = '', period_end: str = '', period_count: int = 0):
    rows = []
    for name, info in stats.items():
        rows.append({
            'name': name,
            'instruments': ' / '.join(sorted(info['instruments'])),
            'count': info['count'],
            'articles': info['articles'],
        })
    rows.sort(key=lambda r: (-r['count'], r['name']))

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    table_rows = ''
    for i, r in enumerate(rows, 1):
        articles_html = '<br>'.join(
            f'<span class="article">{html.escape(a)}</span>' for a in r['articles']
        )
        table_rows += (
            f'<tr>'
            f'<td class="rank">{i}</td>'
            f'<td class="name"><a href="kanmachi63_coplayers.html#{urllib.parse.quote(r["name"])}">{html.escape(r["name"])}</a></td>'
            f'<td class="inst">{html.escape(r["instruments"])}</td>'
            f'<td class="count">{r["count"]}</td>'
            f'<td class="articles">{articles_html}</td>'
            f'</tr>\n'
        )

    css_extra = """
  .page-content { padding: 1.2em 1em 2em; overflow-x:auto; -webkit-overflow-scrolling:touch; }
  table { border-collapse: collapse; min-width: 760px; width: 100%; background: var(--panel); border:1px solid var(--line); }
  th { background: #11151b; color: #d8dde3; padding: 9px 12px; text-align: left; font-size:.8em; }
  td { padding: 8px 12px; border-bottom: 1px solid var(--line); vertical-align: top; font-size:.88em; }
  tr:hover td { background: #202630; }
  .rank { color: var(--muted); font-size: .9em; width: 3em; text-align: center; }
  .count { font-weight: bold; color: #ffb38d; font-size: 1.05em; text-align: center; width: 5em; }
  .inst { color: #c8ced6; font-size: .82em; }
  .articles { font-size: .76em; color: var(--muted); max-width: 340px; }
  .article { display: inline-block; background: var(--panel-2); border:1px solid var(--line); border-radius: 999px; padding: 1px 7px; margin: 1px; }
  .name a { color: #fff; text-decoration: none; }
  .name a:hover { color: var(--accent); text-decoration: underline; }
  @media (max-width:640px) {
    .page-content { padding:.95em .9em 1.4em; }
    h1 { font-size:1.15em; }
  }
"""
    html_content = (
        page_head('上町63 出演者統計', css_extra, active='')
        + '<div class="page-content">\n'
        + f'<h1>上町63 出演者統計</h1>\n'
        + f'<p class="meta">集計日時: {now} ／ 出演者数: {len(rows)} 名 ／ 対象期間: {period_start}〜{period_end}（{period_count}ヶ月）</p>\n'
        + '<table>\n<thead>\n<tr>\n  <th>順位</th>\n  <th>名前</th>\n  <th>パート</th>\n  <th>出演日数</th>\n  <th>掲載記事</th>\n</tr>\n</thead>\n'
        + f'<tbody>\n{table_rows}</tbody>\n</table>\n</div>\n'
        + page_tail()
    )
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f'HTML 出力: {path}')


# ─── index.html 更新 ─────────────────────────────────────────────────────────

def update_index_html(stats: dict, period_start: str, period_end: str, period_count: int, path: str = 'index.html'):
    """index.html の出演者数・期間・ヶ月数を書き換える"""
    import re as _re
    with open(path, encoding='utf-8') as f:
        content = f.read()
    new_span = f'<span class="period">{period_start} 〜 {period_end} ／ {period_count}ヶ月 ／ {len(stats)}名</span>'
    content = _re.sub(r'<span class="period">.*?</span>', new_span, content)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'index.html 更新: {period_start}〜{period_end} {period_count}ヶ月 {len(stats)}名')


# ─── エントリポイント ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    BASE_URL = 'https://kanmachi63.blog.fc2.com/'
    OUT_CSV  = 'kanmachi63_stats.csv'
    OUT_HTML = 'kanmachi63_stats.html'

    print('=== kanmachi63 出演者集計スクリプト ===\n')
    print('1. 全ページ取得中...')
    entries = scrape_all_pages(BASE_URL)
    if not entries:
        raise SystemExit('エラー: 記事を1件も取得できませんでした。処理を中止します。')

    print('\n2. スケジュール記事から出演者を集計中...')
    stats = aggregate(entries)

    print('\n3. 結果を出力中...')
    write_csv(stats, OUT_CSV)
    period_start, period_end, period_count = get_period(entries)
    write_html(stats, OUT_HTML, period_start, period_end, period_count)
    update_index_html(stats, period_start, period_end, period_count)

    print('\n完了！')
