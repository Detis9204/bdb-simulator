"""입상 덱 샘플을 시뮬레이터에 넣는다.

data/decks_winning.json (공식 사이트 입상 덱) 중 samples 목록의 덱을 골라,
그 덱에 쓰인 카드를 data/cards.json에서 찾아 시뮬레이터 카드 정의로 바꾼 뒤
simulator/index.html 의 /*GEN-SAMPLES-START*/ ~ /*GEN-SAMPLES-END*/ 사이에 넣는다.

자동 처리: 코스트, 색, 파워, 히트, 속성, 칭호, 에이스, 버스터/샷,
          아이콘 능력(조건 x 효과), 브라이트.
나머지 텍스트 능력은 카드 설명에 원문을 보여 주고 수동 조작으로 처리한다.

  python collector/build_samples.py
"""
import json, re, sys, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from translate_rules import rule_translate
from parse_effects import parse_card
_KO = (json.load(open(ROOT / 'db' / 'ko_lines.json', encoding='utf-8'))['lines'] if (ROOT / 'db' / 'ko_lines.json').exists() else {})


def ko(line):
    """한국어 번역: 번역 DB 우선, 없으면 정형 문장 규칙, 그래도 없으면 None"""
    return _KO.get(line) or rule_translate(line)
CARDS = ROOT / 'data' / 'cards.json'
DECKS = ROOT / 'data' / 'decks_winning.json'
HTML = ROOT / 'simulator' / 'index.html'


def norm(t):
    return unicodedata.normalize('NFKC', t).replace('スぺード', 'スペード').replace('パワーえ', 'パワー')


def parse_icon(line):
    """아이콘 능력 한 줄 -> ('icon', {cond, eff}) | ('bright', {...}) | None"""
    t = norm(line)
    m = re.fullmatch(r'【ブライト(\d+):(.+?)】', t)
    if m:
        return 'bright', {'attrs': m.group(2).split('/'), 'amount': int(m.group(1))}
    kw = {'デコイ': 'decoy', 'ブリッツ': 'blitz', 'バーサーク': 'berserk'}
    m = re.fullmatch(r'【(デコイ|ブリッツ|バーサーク)】', t)
    if m:
        return 'icon', {'cond': 'always', 'eff': kw[m.group(1)]}
    m = re.fullmatch(r'【スカウト(\d):(登場|ドロップ|バトル)時】', t)
    if m:
        return 'icon', {'cond': {'登場': 'enter', 'ドロップ': 'drop', 'バトル': 'battle'}[m.group(2)], 'eff': 'scout' + m.group(1)}
    if '自' in t[:3] and '時' in t:
        cond = 'enter' if '登場した時' in t else 'drop' if 'ドロップした時' in t else 'battle' if 'バトルする時' in t else None
        m = re.search(r'スカウト(\d)', t)
        eff = f'scout{m.group(1)}' if m else None
        if not eff:
            m = re.search(r'(\d)枚引く', t)
            eff = f'draw{m.group(1)}' if m else None
        if not eff and 'ライフの先頭' in t:
            eff = 'life1'
        return ('icon', {'cond': cond, 'eff': eff}) if cond and eff else None
    cond = ('terr' if 'テリトリー' in t else 'redzone' if 'レッドゾーン' in t
            else 'oppTurn' if '相手のターン中' in t else 'myTurn' if 'あなたのターン中' in t else None)
    eff = None
    m = re.search(r'パワーを\+(\d+)', t)
    if m and m.group(1) in ('3000', '5000'):
        eff = 'pow' + m.group(1)[0]
    m = re.search(r'ヒットを\+(\d)', t)
    if m:
        eff = 'hit' + m.group(1)
    m = re.search(r'【(デコイ|ブリッツ|バーサーク)】を得る', t)
    if m:
        eff = kw[m.group(1)]
    return ('icon', {'cond': cond, 'eff': eff}) if cond and eff else None


_LAND = set(json.load(open(ROOT / 'data' / 'territory_landscape.json', encoding='utf-8'))['ids']) if (ROOT / 'data' / 'territory_landscape.json').exists() else set()


def to_def(c):
    d = {'jp': c['id'], 'name': c['name'], 'color': c['color'], 'type': c['type'], 'cost': c['cost'],
         'attr': c.get('attr') or [], 'titles': c.get('titles') or [], 'icons': [], 'gen': 1}
    m = re.search(r'/card/([0-9a-f]+)/image_path\.png\?(\d+)', c.get('img') or '')
    if m:
        d['im'] = m.group(1) + '?' + m.group(2)   # 공식 이미지 주소 (게시 페이지 밖에서 열 때만 사용)
    if c['type'] == 'unit':
        d['power'] = c.get('power') or 0
        d['hit'] = c.get('hit') or 0
        if c.get('sub') == 'ace':
            d['sub'] = 'ace'
    if c.get('trigger'):
        d['icon'] = c['trigger']
    text, rest, in_icon = [], [], False
    for line in c.get('text') or []:
        if line.strip() == '・アイコン能力':
            in_icon = True
            continue
        if in_icon:
            r = parse_icon(line)
            if r and r[0] == 'bright':
                d['bright'] = r[1]
                continue
            if r:
                d['icons'].append(r[1])
                continue
        rest.append(line)
    if c['type'] == 'territory' and c['id'] in _LAND:
        d['land'] = 1   # 앞면 그림이 가로
    if c['type'] == 'territory':
        d['tfx'] = {'text': ' / '.join(rest) or '(효과 없음)'}
        k = [ko(x) for x in rest]
        if rest and all(k):
            d['tfx']['ko'] = ' / '.join(k)
    else:
        text = rest
    if text:
        d['text'] = text
        d['manual'] = 1
        k = [ko(x) for x in text]
        if any(k):
            d['ko'] = k
    ab, done = parse_card(d)
    if ab:
        d['ab'] = ab
    if done:
        d['al'] = sorted(done)
    nlines = len(d.get('text') or []) if c['type'] != 'territory' else len([x for x in d['tfx']['text'].split(' / ') if x != '(효과 없음)'])
    if d.get('manual') and len(done) >= nlines:
        del d['manual']   # 모든 줄 자동 처리
    if not d['icons']:
        del d['icons']
    if not d['attr']:
        del d['attr']
    if not d['titles']:
        del d['titles']
    return d


def export_db(cards):
    """덱 편성용 전체 카드 정의 -> simulator/cards_db.json (게시 페이지에서 cards_db.json 으로 불러옴)"""
    collabs, defs, base = [], {}, []
    for cid in sorted(cards):
        c = cards[cid]
        d = to_def(c)
        cn = c.get('collabName') or ''
        if cn not in collabs:
            collabs.append(cn)
        d['cb'] = collabs.index(cn)
        if c.get('rarity'):
            d['r'] = c['rarity']
        if c.get('base') and c['base'] != cid:
            d['b'] = c['base']
        else:
            base.append(cid)
        defs[str(cid)] = d
    out = ROOT / 'simulator' / 'cards_db.json'
    out.write_text(json.dumps({'v': 1, 'collabs': collabs, 'base': base, 'defs': defs}, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'전체 카드 {len(defs)}장 (기본 {len(base)}종) -> {out.name} {out.stat().st_size // 1024}KB')


def main():
    cards = {c['id']: c for c in json.load(open(CARDS, encoding='utf-8'))}
    export_db(cards)
    src = json.load(open(DECKS, encoding='utf-8'))
    pick = src.get('samples') or [d['hashid'] for d in src['decks']]
    decks = {d['hashid']: d for d in src['decks']}
    defs, out = {}, []
    for h in pick:
        dk = decks[h]
        cs = dk['cards']
        terr = [c for c in cs if cards[c[0]]['type'] == 'territory']
        if len(terr) != 1:
            print('테리토리 개수 이상, 건너뜀:', h, file=sys.stderr)
            continue
        for cid, _ in cs:
            defs[str(cid)] = to_def(cards[cid])
        main_ = [[str(cid), n] for cid, n in cs if cards[cid]['type'] != 'territory']
        tc = cards[terr[0][0]]
        out.append({'key': 'w' + h, 'label': dk['name'], 'date': dk['date'], 'territory': str(terr[0][0]),
                    'main': main_, 'collab': tc.get('collabName', '')})
    block = ('/*GEN-SAMPLES-START*/\n'
             '/* 자동 생성: collector/build_samples.py — 공식 사이트 입상 덱과 그 카드 */\n'
             f'const GEN_DEFS = {json.dumps(defs, ensure_ascii=False, separators=(",", ":"))};\n'
             f'const GEN_DECKS = {json.dumps(out, ensure_ascii=False, separators=(",", ":"))};\n'
             '/*GEN-SAMPLES-END*/')
    html = HTML.read_text(encoding='utf-8')
    html2 = re.sub(r'/\*GEN-SAMPLES-START\*/.*?/\*GEN-SAMPLES-END\*/', lambda m: block, html, flags=re.S)
    assert html2 != html or block in html, '표시(GEN-SAMPLES) 위치를 찾지 못했습니다'
    HTML.write_text(html2, encoding='utf-8')
    manual = sum(1 for d in defs.values() if d.get('manual'))
    print(f'덱 {len(out)}개, 카드 {len(defs)}종 (텍스트 능력 수동 {manual}종), {len(block) // 1024}KB')


if __name__ == '__main__':
    main()
