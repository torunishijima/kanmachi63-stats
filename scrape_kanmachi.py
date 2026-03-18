#!/usr/bin/env python3
"""
kanmachi63 ブログ スクレイパー
月次スケジュール記事からミュージシャンの出演回数を集計します。
"""

import re
import csv
import time
import html
import urllib.request
from pathlib import Path
from collections import defaultdict
from html.parser import HTMLParser
from datetime import datetime


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

_KNOWN_INSTRUMENTS = {
    'pf', 'gt', 'ag', 'eg', 'b', 'eb', 'ds', 'vo', 'fl', 'cl', 'tp', 'tb',
    'ts', 'as', 'bs', 'ss', 'vc', 'vn', 'vln', 'va', 'org', 'syn', 'key',
    'perc', 'harp', 'oud', 'sax', 'harm', 'har', 'acc', 'mand', 'vib', 'mar',
    'etc', 'mc', 'dj', 'rap', 'cho', 'wb',
}

_NON_INSTRUMENTS = {
    'img', 'src', 'var', 'div', 'span', 'href', 'http', 'https',
    'www', 'com', 'net', 'org', 'jp', 'html', 'css', 'js', 'gif', 'png',
    'jpg', 'svg', 'addEventListener', 'attachEvent', 'style', 'type',
    'function', 'return', 'document', 'window', 'null', 'undefined',
}

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
    r'(?<=[^\s])[a-zA-Z]{2,4}$',           # 末尾に楽器コードが残ったもの (pf, ds, etc.)
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


# 名前エイリアスマップ（略称・誤字 → 正式名）
# 値が None のものは「明らかなノイズ」として除外
_NAME_ALIASES: dict[str, str | None] = {
    # ── 略称 → 正式名 ──────────────────────────────────────────
    'リンヘイテツ':    'リン・ヘイテツ',
    'リンヘテツ':      'リン・ヘイテツ',
    'リン':           'リン・ヘイテツ',
    '落合':           '落合康介',
    '今泉':           '今泉総之輔',
    '渋谷':           '渋谷毅',
    '古木':           '古木佳祐',
    '浅川':           '浅川太平',
    '杉本':           '杉本亮',
    '菅原':           '菅原高志',
    '座小田諒':       '座小田諒一',
    'ファビオボッタッツォ': 'ファビオ・ボッタッツォ',
    'ファビオ':       'ファビオ・ボッタッツォ',
    'ハクエイキム':   'ハクエイ・キム',
    'ハクエイ':       'ハクエイ・キム',
    'マサカマグチ':    'マサ・カマグチ',
    'マサ　カマグチ':  'マサ・カマグチ',
    'マサ カマグチ':   'マサ・カマグチ',
    'マサ':           'マサ・カマグチ',
    'ジョーローゼンバーグ': 'ジョー・ローゼンバーグ',
    'スティーブバリー': 'スティーブ・バリー',
    'デビッドバーグマン': 'デビッド・バーグマン',
    'バート':          'バート・シーガー',
    'イスル':          'イスル・キム',
    'イスル キム':     'イスル・キム',
    'エルセン':        'エルセン・プライス',
    'マーティー':      'マーティー・ホロベック',
    'シューミ朱美':   '宅シューミ朱美',
    '大村':           '大村亘',
    '滝野':           '滝野聡',
    # ── ニックネーム・よみがな表記 ────────────────────────────────
    'HARU高内':        '高内春彦',
    '高内HARU晴彦':    '高内春彦',
    '高内晴彦':        '高内春彦',
    'ハル高内':        '高内春彦',
    '高内ハル':        '高内春彦',
    '蜂谷マキ':        '蜂谷真紀',
    'つのだ健':        'つの犬',
    # ── 字の誤り（名前） ───────────────────────────────────────
    '増田涼一朗':      '増田涼一郎',
    '増田諒一郎':      '増田涼一郎',
    '三嶋大樹':        '三嶋大輝',
    '下梶川雅人':      '下梶谷雅人',
    '小松信之':        '小松伸之',
    '鬼努無月':        '鬼怒無月',
    '橋爪督亮':        '橋爪亮督',
    '福富博':          '福冨博',
    'のばら小太刀':    '小太刀のばら',
    '宅\u201cシュミー\u201d朱美': '宅シューミ朱美',
    '進藤陽吾':        '進藤陽悟',
    '沢田譲治':        '沢田穣治',
    'ませひろ子':      'ませひろこ',
    '池戸裕太':        '池戸祐太',
    '柳沼佑育':        '柳沼祐育',
    '佐々木マン正弘':  '佐々木正弘',
    '松田\u201cGORI\u201d広士': '松田広士',
    'Joｓen':          'Josen',
    'ユリアリマサ':    'ユキアリマサ',
    # ── 字の誤り（ユーザー確認済み） ─────────────────────────────
    '斎藤良':          '斉藤良',        # 多い方(6)に統一
    '鈴木瑶子':        '鈴木瑤子',      # 多い方(3)に統一
    '林祐一':          '林祐市',        # 多い方(4)に統一
    '小林航太郎':      '小林航太朗',    # 多い方(2)に統一
    '佐藤節夫':        '佐藤節雄',      # 多い方(3)に統一
    '竹中直':          '竹内直',        # 多い方(150)に統一
    '安藤昇':          '安東昇',        # 多い方(86)に統一
    '公平徹太郎':      '公手徹太郎',    # 同数のため公手を採用
    # ── ノイズ除去 ────────────────────────────────────────────
    '￥3':             None,
    '￥３':            None,
    '.electronics':    None,
    '渋谷毅SOLO':      '渋谷毅',
    '西山瞳ＳＯＬＯ': '西山瞳',
    '田中菜緒子【SOLDOUT】': '田中菜緒子',
    '大村亘￥3':       '大村亘',
    '大村亘￥３':      '大村亘',
    '安東昇￥3':       '安東昇',
    '中道みさき￥３':  '中道みさき',
    '甲斐正樹￥￥３':  '甲斐正樹',
    '山崎隼￥３':      '山崎隼',
    '則武諒￥３':      '則武諒',
    '則武諒pf':        '則武諒',
    '則武諒一':        '則武諒',
    'ｓｓ.山口真文':   '山口真文',
    'ｆｌ.竹内直':     '竹内直',
    'ｐｆ.蜂谷真紀':   '蜂谷真紀',
    'ｐｆ.宅シューミ朱美': '宅シューミ朱美',
    '山口真文ｇ':      '山口真文',
    '.橋爪亮督':       '橋爪亮督',
    '橋爪亮督.':       '橋爪亮督',
    '佐々木MAN正弘':   '佐々木正弘',
    '松田"GORI"広士':  '松田広士',
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

# 出演者パターン: 「楽器コード.名前」（半角化済みテキストに適用）
PERFORMER_TOKEN_RE = re.compile(
    r'((?:[a-zA-Z]{1,8}\.)+)'                      # 楽器部分
    r'((?:(?![a-z]{1,8}\.)[^\s、。,，\n<「」\[\]（）()@￥¥])+)',  # 名前部分
    re.UNICODE
)

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
        if not re.search(r'[\u3000-\u9fff\uff00-\uffef\u3040-\u30ff]', name) and re.match(r'^[a-zA-Z]+$', name):
            continue
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

def fetch(url: str) -> str:
    """URLからHTMLを取得して文字列で返す"""
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


def fetch_cached(url: str) -> str:
    """キャッシュがあればそれを使い、なければ取得してキャッシュする"""
    CACHE_DIR.mkdir(exist_ok=True)
    # URL をファイル名に変換
    safe = re.sub(r'[^\w]', '_', url) + '.html'
    cache_path = CACHE_DIR / safe
    if cache_path.exists():
        return cache_path.read_text(encoding='utf-8')
    text = fetch(url)
    cache_path.write_text(text, encoding='utf-8')
    return text


# ─── メイン処理 ───────────────────────────────────────────────────────────────

def scrape_all_pages(start_url: str) -> list[dict]:
    """全ページを巡回して記事一覧を返す"""
    all_entries = []
    url = start_url
    page_num = 0

    while url:
        print(f'  取得中: {url}')
        html_text = None
        for attempt in range(3):
            try:
                html_text = fetch_cached(url)
                break
            except Exception as e:
                print(f'  エラー (試行 {attempt+1}/3): {e}')
                if attempt < 2:
                    time.sleep(3)
        if html_text is None:
            print('  スキップして次ページを推定します...')
            m = re.search(r'page-(\d+)\.html', url)
            if m:
                url = re.sub(r'page-\d+\.html', f'page-{int(m.group(1))+1}.html', url)
            else:
                break
            page_num += 1
            continue

        parser = BlogParser()
        parser.feed(html_text)
        all_entries.extend(parser.entries)
        print(f'    → 記事数: {len(parser.entries)} 件 (累計: {len(all_entries)} 件)')

        next_parser = NextPageParser()
        next_parser.feed(html_text)
        next_url = next_parser.next_url

        page_num += 1
        # キャッシュから読んだ場合はスリープしない
        cache_hit = (CACHE_DIR / (re.sub(r'[^\w]', '_', url) + '.html')).exists()
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


def write_html(stats: dict, path: str):
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
            f'<td class="name">{html.escape(r["name"])}</td>'
            f'<td class="inst">{html.escape(r["instruments"])}</td>'
            f'<td class="count">{r["count"]}</td>'
            f'<td class="articles">{articles_html}</td>'
            f'</tr>\n'
        )

    html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>kanmachi63 出演者統計</title>
<style>
  body {{ font-family: "Hiragino Sans", "Meiryo", sans-serif; margin: 2em; background: #fafafa; color: #222; }}
  h1 {{ color: #333; border-bottom: 2px solid #c8a84b; padding-bottom: .3em; }}
  p.meta {{ color: #888; font-size: .85em; }}
  table {{ border-collapse: collapse; width: 100%; background: #fff; box-shadow: 0 1px 4px rgba(0,0,0,.1); }}
  th {{ background: #2c3e50; color: #fff; padding: 10px 14px; text-align: left; }}
  td {{ padding: 8px 14px; border-bottom: 1px solid #e8e8e8; vertical-align: top; }}
  tr:hover td {{ background: #f0f4f8; }}
  .rank {{ color: #888; font-size: .9em; width: 3em; text-align: center; }}
  .count {{ font-weight: bold; color: #c0392b; font-size: 1.1em; text-align: center; width: 5em; }}
  .inst {{ color: #2980b9; font-size: .85em; }}
  .articles {{ font-size: .78em; color: #555; max-width: 300px; }}
  .article {{ display: inline-block; background: #eef2f7; border-radius: 3px; padding: 1px 5px; margin: 1px; }}
</style>
</head>
<body>
<h1>🎵 kanmachi63 出演者統計</h1>
<p class="meta">集計日時: {now} ／ 出演者数: {len(rows)} 名 ／ 対象期間: 2012年8月〜2026年4月</p>
<table>
<thead>
<tr>
  <th>順位</th>
  <th>名前</th>
  <th>パート</th>
  <th>出演日数</th>
  <th>掲載記事</th>
</tr>
</thead>
<tbody>
{table_rows}
</tbody>
</table>
</body>
</html>
"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f'HTML 出力: {path}')


# ─── エントリポイント ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    BASE_URL = 'http://kanmachi63.blog.fc2.com/'
    OUT_CSV  = 'kanmachi63_stats.csv'
    OUT_HTML = 'kanmachi63_stats.html'

    print('=== kanmachi63 出演者集計スクリプト ===\n')
    print('1. 全ページ取得中...')
    entries = scrape_all_pages(BASE_URL)

    print('\n2. スケジュール記事から出演者を集計中...')
    stats = aggregate(entries)

    print('\n3. 結果を出力中...')
    write_csv(stats, OUT_CSV)
    write_html(stats, OUT_HTML)

    print('\n完了！')
