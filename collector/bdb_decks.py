"""공식 사이트 덱 레시피에서 브라이트 입상 덱을 모아 data/decks_winning.json 으로 저장.

  python collector/bdb_decks.py            # 전체 수집 (기존 samples 목록은 유지)
  python collector/bdb_decks.py --pages 5  # 앞쪽 5쪽만

이름에 優勝, 準優勝, 位, 入賞, ベスト 가 들어간 레시피를 입상 덱으로 본다.
그다음 python collector/build_samples.py 로 시뮬레이터에 넣는다.
"""
import argparse, html, json, re, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'decks_winning.json'
BASE = 'https://tcg.build-divide.com'
PLACED = re.compile(r'優勝|準優勝|位|入賞|ベスト')
UA = {'User-Agent': 'Mozilla/5.0 (bdb-simulator deck collector)', 'X-Requested-With': 'XMLHttpRequest'}


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return r.read().decode('utf-8')
        except Exception as e:
            if i == tries - 1:
                raise
            print('  다시 시도:', url, e, file=sys.stderr)
            time.sleep(2 + i * 3)


def list_page(n):
    """레시피 목록 한 쪽 -> [(hashid, name, updated)]"""
    t = get(f'{BASE}/official/recipes?tag=bright&order=updated_at&page={n}')
    out = []
    for item in re.split(r'class="recipes-result-list-item', t)[1:]:
        h = re.search(r'hashid=([0-9A-Za-z]+)', item)
        nm = re.search(r'__deck-name[^>]*>(.*?)</', item, re.S)
        up = re.search(r'__updated[^>]*>(.*?)</', item, re.S)
        if h and nm:
            name = html.unescape(re.sub(r'<[^>]+>', '', nm.group(1))).strip()
            date = re.search(r'(\d{4})[./-](\d{1,2})[./-](\d{1,2})', up.group(1) if up else '')
            out.append((h.group(1), name, '-'.join([date.group(1), date.group(2).zfill(2), date.group(3).zfill(2)]) if date else ''))
    return out


def deck_cards(hashid):
    j = json.loads(get(f'{BASE}/bright/decks/detail/{hashid}'))
    cs = j.get('cards') or (j.get('deck') or {}).get('cards') or (j.get('data') or {}).get('cards') or []
    return [[int(c['card_id']), int(c.get('size') or c.get('count') or 1)] for c in cs]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pages', type=int, default=200)
    a = ap.parse_args()
    old = json.load(open(OUT, encoding='utf-8')) if OUT.exists() else {}
    have = {d['hashid']: d for d in old.get('decks', [])}
    found = []
    for n in range(1, a.pages + 1):
        rows = list_page(n)
        if not rows:
            break
        found += [r for r in rows if PLACED.search(r[1])]
        print(f'{n}쪽: 레시피 {len(rows)}개, 입상 덱 누적 {len(found)}개')
        time.sleep(0.4)
    decks = []
    for i, (h, name, date) in enumerate(found, 1):
        if h in have and have[h].get('cards'):
            decks.append(have[h]); continue
        try:
            decks.append({'hashid': h, 'date': date, 'name': name, 'cards': deck_cards(h)})
            print(f'[{i}/{len(found)}] {name}')
        except Exception as e:
            print(f'[{i}/{len(found)}] 실패 {h}: {e}', file=sys.stderr)
        time.sleep(0.4)
    res = {'source': f'{BASE}/official/recipes?tag=bright', 'samples': old.get('samples', []), 'decks': decks}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'저장: {OUT} (덱 {len(decks)}개)')


if __name__ == '__main__':
    main()
