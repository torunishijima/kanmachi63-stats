"""
scrape_kanmachi のパーサー・名前正規化ユニットテスト。
実データ（CSV の実在名・エイリアスマップ）に基づく回帰テスト。
オーディオデバイスやネットワークは不要。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import pytest
except ImportError:  # pytest なしの簡易ランナー向け
    pytest = None

from scrape_kanmachi import (
    to_halfwidth, clean_name, normalize_name,
    _is_instrument, _prepare_text, _parse_performers,
    extract_performers_by_date,
)


# ── to_halfwidth ──────────────────────────────────────────────────────────────

def test_to_halfwidth_converts_fullwidth():
    assert to_halfwidth('ＡＢＣ０１２') == 'ABC012'
    assert to_halfwidth('ｐｆ．西山瞳') == 'pf.西山瞳'


def test_to_halfwidth_fullwidth_space():
    assert to_halfwidth('西山瞳　大村亘') == '西山瞳 大村亘'


# ── clean_name / normalize_name ──────────────────────────────────────────────

def test_clean_name_strips_trailing_noise():
    assert clean_name('渋谷毅SOLO') == '渋谷毅'
    assert clean_name('西山瞳ＳＯＬＯ') == '西山瞳'
    assert clean_name('田中菜緒子【SOLDOUT】') == '田中菜緒子'
    assert clean_name('大村亘￥3') == '大村亘'


def test_clean_name_strips_leading_instrument_prefix():
    assert clean_name('pf.蜂谷真紀') == '蜂谷真紀'
    assert clean_name('ss.山口真文') == '山口真文'
    assert clean_name('ts.ss.竹内直') == '竹内直'


def test_normalize_name_resolves_alias():
    assert normalize_name('リンヘイテツ') == 'リン・ヘイテツ'
    assert normalize_name('今泉') == '今泉総之輔'
    assert normalize_name('マサカマグチ') == 'マサ・カマグチ'
    assert normalize_name('大村') == '大村亘'


def test_normalize_name_returns_none_for_noise():
    assert normalize_name('￥3') is None
    assert normalize_name('.electronics') is None


def test_normalize_name_passes_known_name():
    assert normalize_name('西山瞳') == '西山瞳'
    assert normalize_name('馬場孝喜') == '馬場孝喜'


# ── _is_instrument ───────────────────────────────────────────────────────────

def test_is_instrument_known_codes():
    assert _is_instrument('pf') is True
    assert _is_instrument('ts') is True
    assert _is_instrument('as.ts') is True
    assert _is_instrument('wb.vln') is True


def test_is_instrument_rejects_noise():
    assert _is_instrument('img') is False
    assert _is_instrument('http') is False
    assert _is_instrument('js') is False


# ── _prepare_text ────────────────────────────────────────────────────────────

def test_prepare_text_removes_strikethrough():
    body = '<p>pf.西山瞳 <s>ds.大村亘</s><br>ts.竹内直</p>'
    text = _prepare_text(body)
    assert '大村亘' not in text
    assert '西山瞳' in text
    assert '竹内直' in text


def test_prepare_text_fixes_day_typo():
    body = '12日28日'
    assert _prepare_text(body) == '12月28日'


# ── _parse_performers ────────────────────────────────────────────────────────

def test_parse_performers_basic():
    text = 'pf.西山瞳 ts.竹内直 b.西嶋徹'
    performers = _parse_performers(text)
    names = [n for _, n in performers]
    assert '西山瞳' in names
    assert '竹内直' in names
    assert '西嶋徹' in names


def test_parse_performers_skips_noise():
    text = 'img src="x.png" pf.西山瞳'
    performers = _parse_performers(text)
    assert all(n != 'img' for _, n in performers)


def test_parse_performers_western_title_case():
    text = 'gt.CHAKA pf.マーティー'
    performers = _parse_performers(text)
    names = [n for _, n in performers]
    assert any(n == 'Chaka' for n in names)


# ── extract_performers_by_date ───────────────────────────────────────────────

def test_extract_performers_by_date_groups_by_day():
    # 実ブログ形式: <br> 区切りの1行に日付または出演者
    body = (
        '<div class="entry_body">'
        '4月1日<br>pf.西山瞳<br>ts.竹内直<br>'
        '4月2日<br>ds.大村亘<br>b.西嶋徹'
        '</div>'
    )
    days = extract_performers_by_date(body)
    assert len(days) == 2
    assert len(days[0]) == 2
    assert len(days[1]) == 2


def test_extract_performers_by_date_empty():
    assert extract_performers_by_date('<p>通常の記事</p>') == []


if __name__ == '__main__':
    # 簡易ランナー（pytest なしで直接実行可能）
    import traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f'  PASS  {fn.__name__}')
        except Exception as e:
            failed += 1
            print(f'  FAIL  {fn.__name__}: {e}')
            traceback.print_exc()
    print(f'\n{len(tests) - failed}/{len(tests)} passed, {failed} failed')
    sys.exit(1 if failed else 0)
