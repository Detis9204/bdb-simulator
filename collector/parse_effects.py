"""카드 텍스트 능력(일본어 원문) -> 시뮬레이터가 실행하는 효과 스크립트.

원문을 문장 조각 단위로 읽어, 아는 조각만으로 끝까지 읽히는 줄만 자동 처리한다.
한 조각이라도 모르면 그 줄은 None (수동 조작으로 남음).

결과 형식 (카드 정의의 ab 배열 한 항목):
  {li:[원문 줄 번호], k:'auto'|'perm'|'play', on:발동 시점, src:'self'|'own'|'ownAce'|'opp',
   if:[조건], once:1, cost:[비용], do:[단계]}
"""
import re, unicodedata

N = lambda t: unicodedata.normalize('NFKC', t)

# ---------- 대상 묘사 (…ユニット) ----------
_DESC_TOKENS = [
    (r'⁅?(?:ハート|スペード|ダイヤ|クラブ)⁆?(?:か⁅?(?:ハート|スペード|ダイヤ|クラブ)⁆?)+(?:の)?', lambda m, f: f.__setitem__('attr', re.findall('ハート|スペード|ダイヤ|クラブ', m.group(0)))),
    (r'相手の', lambda m, f: f.__setitem__('side', 'opp')),
    (r'、', lambda m, f: None),
    (r'属性(\d)つの', lambda m, f: f.__setitem__('attrN', int(m.group(1)))),
    (r'あなたの', lambda m, f: f.__setitem__('side', 'own')),
    (r'このユニット以外の|他の', lambda m, f: f.__setitem__('notSelf', 1)),
    (r'総?コスト(\d+)以下(?:の|で)', lambda m, f: f.__setitem__('costLE', int(m.group(1)))),
    (r'総?コスト(\d+)以上(?:の|で)', lambda m, f: f.__setitem__('costGE', int(m.group(1)))),
    (r'パワー(\d+)以下(?:の|で)', lambda m, f: f.__setitem__('powLE', int(m.group(1)))),
    (r'パワー(\d+)以上(?:の|で)', lambda m, f: f.__setitem__('powGE', int(m.group(1)))),
    (r'⁅バスターアイコン⁆でない|バスターアイコンでない', lambda m, f: f.__setitem__('notIcon', 'buster')),
    (r'このターンに登場していない', lambda m, f: f.__setitem__('notNew', 1)),
    (r'ヒット(\d+)以下の', lambda m, f: f.__setitem__('hitLE', int(m.group(1)))),
    (r'ヒット(\d+)以上の', lambda m, f: f.__setitem__('hitGE', int(m.group(1)))),
    (r'レストしている|レスト状態の', lambda m, f: f.__setitem__('rested', 1)),
    (r'スタンドしている|スタンド状態の', lambda m, f: f.__setitem__('rested', 0)),
    (r'ダメージを受けている', lambda m, f: f.__setitem__('damaged', 1)),
    (r'エースでない', lambda m, f: f.__setitem__('ace', 0)),
    (r'称号「([^」]+)」(?:の|を持つ)?', lambda m, f: f.__setitem__('title', m.group(1))),
    (r'【スキル】を持つ', lambda m, f: f.__setitem__('skill', 1)),
    (r'(ハート|スペード|ダイヤ|クラブ)か(ハート|スペード|ダイヤ|クラブ)(?:の)?', lambda m, f: f.__setitem__('attr', [m.group(1), m.group(2)])),
    (r'(赤|青|白|黒)か(赤|青|白|黒)の', lambda m, f: f.__setitem__('color', [{'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[x] for x in m.groups()])),
    (r'エースか⁅バスターアイコン⁆の|エースカードか⁅バスターアイコン⁆', lambda m, f: f.__setitem__('aceOrBuster', 1)),
    (r'魔法', lambda m, f: f.__setitem__('magic', 1)),
    (r'(赤|青|白|黒)か⁅(ハート|スペード|ダイヤ|クラブ)⁆の', lambda m, f: f.__setitem__('colorOrAttr', [{'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[m.group(1)], m.group(2)])),
    (r'クラスカード(?:を持つ|がついている|のついた|がついた)', lambda m, f: f.__setitem__('hasClass', 1)),
    (r'(?:カード名に)?「([^」]+)」(?:か「([^」]+)」)+を(?:名前に)?含む', lambda m, f: f.__setitem__('nameAny', re.findall(r'「([^」]+)」', m.group(0)))),
    (r'(?:カード名に)?「([^」]+)」を(?:名前に)?含む', lambda m, f: f.__setitem__('name', m.group(1))),
    (r'カード名に、', lambda m, f: None),
    (r'⁅(ハート|スペード|ダイヤ|クラブ)⁆か⁅(ハート|スペード|ダイヤ|クラブ)⁆(?:の|を持つ)?', lambda m, f: f.__setitem__('attr', [m.group(1), m.group(2)])),
    (r'⁅(ハート|スペード|ダイヤ|クラブ)⁆(?:の|を持つ)?', lambda m, f: f.__setitem__('attr', [m.group(1)])),
    (r'【ブライト】を持つ', lambda m, f: f.__setitem__('bright', 1)),
    (r'【コスプレ】を持つ', lambda m, f: f.__setitem__('cos', 1)),
    (r'【我駆力】を持つ', lambda m, f: f.__setitem__('gaku', 1)),
    (r'【夢を見ない】を持つ', lambda m, f: f.__setitem__('yumemi', 1)),
    (r'⁅神衣⁆を持つ', lambda m, f: f.__setitem__('kamui', 1)),
    (r'【ブライト】を持たない', lambda m, f: f.__setitem__('noBright', 1)),
    (r'【(?!スキル|ブライト|コスプレ|デコイ|ブリッツ|バーサーク)([^】]+)】を持つ', lambda m, f: f.__setitem__('kwText', m.group(1))),
    (r'【(マギア|マケイン|ログ)】を持つ', lambda m, f: f.__setitem__({'マギア': 'magia', 'マケイン': 'makein', 'ログ': 'log'}[m.group(1)], 1)),
    (r'アタック中の', lambda m, f: f.__setitem__('attacking', 1)),
    (r'アタックして', lambda m, f: None),
    (r'(ハート|スペード|ダイヤ|クラブ)の', lambda m, f: f.__setitem__('attr', [m.group(1)])),
    (r'【(デコイ|ブリッツ|バーサーク)】を持つ', lambda m, f: f.__setitem__('kw', {'デコイ': 'decoy', 'ブリッツ': 'blitz', 'バーサーク': 'berserk'}[m.group(1)])),
    (r'パワーがこのユニット(?:のパワー)?以下の', lambda m, f: f.__setitem__('powLE_self', 1)),
    (r'パワーがこのユニット(?:のパワー)?より低い', lambda m, f: f.__setitem__('powLT_self', 1)),
    (r'パワーが対象(?:のパワー)?以下の', lambda m, f: f.__setitem__('powLE_T', 1)),
    (r'パワーが対象(?:のパワー)?より低い', lambda m, f: f.__setitem__('powLT_T', 1)),
    (r'⁅B⁆の|バスターアイコンの', lambda m, f: f.__setitem__('icon', 'buster')),
    (r'アイコン能力を持つ', lambda m, f: f.__setitem__('hasIcon', 1)),
    (r'(赤|青|白|黒)の', lambda m, f: f.__setitem__('color', [{'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[m.group(1)]])),
    (r'⁅バスターアイコン⁆を持つ|バスターの|⁅バスターアイコン⁆の?', lambda m, f: f.__setitem__('icon', 'buster')),
    (r'⁅ショットアイコン⁆の?|⁅☆⁆の?', lambda m, f: f.__setitem__('icon', 'shot')),
    (r'(赤|青|白|黒)でない', lambda m, f: f.__setitem__('notColor', {'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[m.group(1)])),
    (r'パワー(\d+)(?:の|で)', lambda m, f: f.__setitem__('powEQ', int(m.group(1)))),
    (r'総?コスト(\d+)(?:ちょうど)?(?:の|で)', lambda m, f: f.__setitem__('costEQ', int(m.group(1)))),
    (r'「([^」]+)」(?:か「([^」]+)」)+(?:の)?', lambda m, f: f.__setitem__('nameAny', re.findall(r'「([^」]+)」', m.group(0)))),
    (r'「([^」]+)」(?=を\d|を全て|をN)', lambda m, f: f.__setitem__('name', m.group(1))),
    (r'⁅ショットアイコン⁆を持つ|ショットの', lambda m, f: f.__setitem__('icon', 'shot')),
    (r'で|、|かつ|の', lambda m, f: None),
]


def parse_desc(desc, f=None):
    """'相手の総コスト4以下の' 같은 묘사 -> 필터. 모르는 말이 남으면 None"""
    f = dict(f or {})
    t = desc
    while t:
        for pat, fn in _DESC_TOKENS:
            m = re.match(pat, t)
            if m:
                fn(m, f)
                t = t[m.end():]
                break
        else:
            return None
    return f


# 명사: 유닛 / 에이스 (카드)
_LAST = {}
_FAIL = {}   # 디버그: 마지막으로 못 읽은 조각
DESC = r'(?P<d>(?:[^。を]|を持つ|を含む)*?)'
NOUN = r'(?P<noun>エースカード|エース|ユニットカード|ユニット|コマンドカード|カード|エナジー)'


def noun_filter(f, noun):
    noun = noun or ''
    if noun.startswith('エース'):
        f['ace'] = 1
    if noun in ('ユニットカード', 'ユニット', 'エース', 'エースカード'):
        f['type'] = 'unit'
    if noun == 'コマンドカード':
        f['type'] = 'command'
    return f


# ---------- 동사 끝 (끝맺음/이음) ----------
def V(*stems):
    return '(?:' + '|'.join(stems) + ')'


END = r'(?:。|、|$)'
MAY = r'(?P<may>(?:て|で)(?:も)?よい)?'

TO_SELF = r'このユニット'
TO_T = r'(?:対象|そのユニット|そのカード|それ)'

_DUR = r'(?:(?P<dur>そのターン中|このターン(?:中)?|次の(?:あなたの|相手の)?ターン(?:の)?(?:開始時|終了時)まで)、)?'


def subj(t):
    """효과 받는 쪽: 'T' | 'self' | {'all': filter}"""
    if re.fullmatch(TO_T, t):
        return 'T'
    if t == 'バトル相手':
        return 'vs'
    if t in ('そのアタックしたユニット', 'アタックしたユニット'):
        return 'T'
    if t == TO_SELF or t == 'このカード':
        return 'self'
    if t in ('あなたのドロップゾーンからこのカード', 'ドロップゾーンからこのカード', 'ドロップしたこのカード'):
        return 'card'
    if t in ('ドロップゾーンのこのカード', 'あなたのドロップゾーンのこのカード', 'ドロップゾーンからそのカード', 'ドロップゾーンのそのカード'):
        return 'T' if 'その' in t else 'card'
    if t in ('ドロップゾーンのこのカード', 'あなたのドロップゾーンのこのカード'):
        return 'card'
    if t in ('このカードがついているユニット', 'このカードがついたユニット', 'このカードをつけたユニット'):
        return 'host'
    if t in ('あなた', 'あなた自身'):
        return 'me'
    if t == '相手':
        return 'opp'
    m = re.fullmatch(r'(?P<d>.*?)' + NOUN + r'全て', t)
    if m:
        f = parse_desc(m.group('d'))
        if f is None:
            return None
        return {'all': noun_filter(f, m.group('noun'))}
    return None


# ---------- 효과 조각 ----------
def eff_patterns():
    P = []

    def add(rx, fn):
        P.append((re.compile(rx), fn))

    # 대상 지정
    def tgt(m):
        f = parse_desc(m.group('d') or '')
        if f is None:
            return None
        if not m.group('noun') and not m.group('zone'):
            return None
        noun_filter(f, m.group('noun'))
        zone = m.group('zone')
        if m.group('noun') == 'エナジー':
            zone = 'エナジー'
            f.setdefault('side', 'own')
        st = {'op': 'tgt', 'f': f, 'n': int(m.group('n')), 'upto': 1 if m.group('upto') else 0}
        if zone:
            st['zone'] = {'ドロップゾーン': 'drop', '手札': 'hand', 'エナジーゾーン': 'energy', 'エナジー': 'energy'}[zone]
        return st
    add(r'(?:(?:あなたの|相手の)?(?P<zone>ドロップゾーン|手札|エナジーゾーン|エナジー)の)?(?P<d>(?:[^。を]|を持つ|を含む)*?)(?:' + NOUN + r')?を(?P<n>\d+)枚(?P<upto>まで)?対象と' + V('し', 'する') + END, tgt)

    # 데미지
    def dmg(m):
        to = subj(m.group('to'))
        if to in ('me', 'opp'):
            return {'op': 'lifeDmg', 'n': int(m.group('n')), 'who': to}
        return to and {'op': 'dmg', 'n': int(m.group('n')), 'to': to}
    add(r'(?P<to>[^、。]*?)に(?P<n>\d+)ダメージ(?:を与え(?:る|))?' + END, dmg)

    # 파워/히트 수정
    def mod(m):
        to = subj(m.group('to'))
        if not to:
            return None
        out = []
        for k, v in re.findall(r'(パワー|ヒット)を([+-]\d+)', m.group('mods')):
            out.append({'op': 'pow' if k == 'パワー' else 'hit', 'n': int(v), 'to': to})
        if not out:
            return None
        return out
    add(_DUR + r'(?P<to>[^、。]*?)の(?P<mods>(?:パワー|ヒット)を[+-]\d+(?:、(?:パワー|ヒット)を[+-]\d+)?)(?:する|し)?' + END, mod)

    # 키워드 얻기
    def kw(m):
        to = subj(m.group('to'))
        k = {'デコイ': 'decoy', 'ブリッツ': 'blitz', 'バーサーク': 'berserk'}.get(m.group('k'))
        return to and k and {'op': 'kw', 'kw': k, 'to': to}
    add(_DUR + r'(?P<to>[^、。]*?)は【(?P<k>デコイ|ブリッツ|バーサーク)】を得' + V('る', 'て') + END, kw)

    def restrict(m):
        to = subj(m.group('to'))
        ks = {'アタックとブロックができない': ['noAttack', 'noBlock'], 'アタックできない': ['noAttack'], 'ブロックができない': ['noBlock'],
              'ブロックできない': ['noBlock'], 'ブロックされない': ['unblockable'], 'アタックができない': ['noAttack']}[m.group('k')]
        return to and [{'op': 'kw', 'kw': k, 'to': to} for k in ks]
    add(_DUR + r'(?P<to>[^、。]*?)(?:は|では)(?P<k>アタックとブロックができない|アタックできない|アタックができない|ブロックができない|ブロックできない|ブロックされない)' + END, restrict)
    # 플레이어 데미지
    add(r'(?P<w>あなた|相手)に(?P<n>\d+)ダメージ' + END, lambda m: {'op': 'lifeDmg', 'n': int(m.group('n')), 'who': 'me' if m.group('w') == 'あなた' else 'opp'})

    # 이동
    moves = [
        (r'ドロップ' + V('させる', 'させ', 'する', 'し'), 'drop'),
        (r'(?:持ち主の)?手札に戻' + V('す', 'し'), 'bounce'),
        (r'(?:持ち主の)?山札の上に置' + V('く', 'き', 'い'), 'deckTop'),
        (r'(?:持ち主の)?山札の下に置' + V('く', 'き', 'い'), 'deckBottom'),
        (r'(?:持ち主の)?エナジーゾーンに置' + V('く', 'き', 'い'), 'energy'),
        (r'リムーブ' + V('する', 'し'), 'remove'),
        (r'レスト' + V('する', 'し', 'させる', 'させ'), 'rest'),
        (r'スタンド' + V('する', 'し', 'させる', 'させ'), 'stand'),
        (r'レストで登場' + V('させる', 'させ'), 'summonRested'),
        (r'登場' + V('させる', 'させ'), 'summon'),
        (r'(?:あなたの)?ライフの先頭に置' + V('く', 'き', 'い'), 'life'),
    ]
    for rx, op in moves:
        def mv(m, op=op):
            to = subj(m.group('to'))
            st = to and {'op': op, 'to': to}
            if st and m.group('may'):
                st['may'] = 1
            return st
        add(r'(?:さらに)?(?P<to>[^、。]*?)を' + rx + MAY + END, mv)

    # 대상 없이 쓰는 데미지 (앞의 대상에게)
    add(r'(?:代わりに)?(?P<n>\d+)ダメージ' + END, lambda m: {'op': 'dmg', 'n': int(m.group('n')), 'to': 'T'})
    # 주어 없는 수정: 앞 문장의 대상에게 (예: 「ブロックされず、ヒットを+1」)
    add(r'(?:さらに)?(?P<mods>(?:パワー|ヒット)を[+-]\d+)' + END, lambda m: {'op': 'pow' if m.group('mods').startswith('パワー') else 'hit', 'n': int(re.search(r'[+-]\d+', m.group('mods')).group()), 'to': '$prev'})
    add(r'さらに(?P<n>[+-]\d+)' + END, lambda m: {'op': '$prevop', 'n': int(m.group('n')), 'to': '$prev'})
    add(_DUR + r'(?P<to>[^、。]*?)はブロックされず' + END, lambda m: subj(m.group('to')) and {'op': 'kw', 'kw': 'unblockable', 'to': subj(m.group('to'))})
    # 상대는 ~ 유닛으로 공격·블록 못 함
    add(_DUR + r'相手は(?P<d>[^、。]*?)ユニットでは(?P<k>アタックとブロック|アタック|ブロック)ができない' + END,
        lambda m: (lambda f: f is not None and [{'op': 'kw', 'kw': k, 'to': {'all': {**f, 'side': 'opp', 'type': 'unit'}}} for k in {'アタックとブロック': ['noAttack', 'noBlock'], 'アタック': ['noAttack'], 'ブロック': ['noBlock']}[m.group('k')]])(parse_desc(m.group('d'))))
    # 대상을 A하거나 B
    add(r'(?:対象|そのカード)を手札に戻すか登場させる' + END, lambda m: {'op': 'choose', 'opts': [[{'op': 'bounce', 'to': 'T'}], [{'op': 'summon', 'to': 'T'}]], 'labels': ['패로 되돌린다', '등장시킨다']})
    # 에너지의 카드를 패로
    add(r'あなたの' + DESC + r'(?:' + NOUN[:-1] + r'))?の?エナジーを(?P<n>\d+)枚(?P<upto>まで)?手札に戻' + V('す', 'し') + END,
        lambda m: (lambda f: f is not None and {'op': 'pick', 'from': 'energy', 'to': 'hand', 'f': noun_filter(f, m.group('noun')), 'n': int(m.group('n')), 'upto': 1 if m.group('upto') else 0})(parse_desc(m.group('d'))))
    # 패의 카드를 공개해서 라이프 맨 앞에
    add(r'あなたの手札の、?' + DESC + r'を(?P<n>\d+)枚(?P<upto>まで)?公開し、公開したカードをライフの先頭に置' + V('く', 'き', 'い') + END,
        lambda m: (lambda f: f is not None and {'op': 'pick', 'from': 'hand', 'to': 'life', 'f': f, 'n': int(m.group('n')), 'upto': 1 if m.group('upto') else 0})(parse_desc(m.group('d'))))
    # 덱 위 1장 공개: 맞으면 패/등장, 아니면 드롭/덱 아래
    def reveal_top(m):
        f = parse_desc(m.group('d') or '')
        if f is None:
            return None
        if m.group('noun'):
            noun_filter(f, m.group('noun'))
        st = {'op': 'revealTop', 'f': f, 'yes': 'field' if '登場' in m.group('y') else 'hand', 'no': 'drop' if 'ドロップ' in m.group('n2') else 'hand' if '手札' in m.group('n2') else 'bottom'}
        if m.group('may'):
            st['may'] = 1
        return st
    add(r'(?:あなたの)?山札(?:を|の)上から1枚(?:を)?公開(?:し|して|する)' + MAY + r'(?:。|、)それが' + DESC + r'(?:' + NOUN[:-1] + r'))?なら(?P<y>手札に加え|登場させ)、違うなら(?P<n2>ドロップ|山札の下に置|手札に加え)' + V('する', 'く', 'し', 'き', 'る', '') + END, reveal_top)
    # 에너지의 커맨드를 코스트 없이 플레이
    add(r'あなたの' + DESC + r'コマンドカードのエナジーを1枚、コストを払わずにプレイ' + V('する', 'し') + MAY + END,
        lambda m: (lambda f: f is not None and {'op': 'playFree', 'from': 'energy', 'f': {**f, 'type': 'command'}, 'may': 1})(parse_desc(m.group('d').rstrip('で'))))
    # 플레이어 1명이 자기 유닛 1장을 드롭
    add(r'プレイヤー1人を対象とし、対象は自身のユニットを(?P<n>\d+)枚ドロップさせ' + V('る', '') + END,
        lambda m: {'op': 'choose', 'opts': [[{'op': 'sacrifice', 'who': 'me', 'n': int(m.group('n'))}], [{'op': 'sacrifice', 'who': 'opp', 'n': int(m.group('n'))}]], 'labels': ['나를 대상으로', '상대를 대상으로']})
    # 대상을 받는 말이 생략된 동사 (「対象とし、ドロップさせる」)
    for rx, op in [(r'ドロップさせ' + V('る', ''), 'drop'), (r'手札に戻' + V('す', 'し'), 'bounce'), (r'エナジーゾーンに置' + V('く', 'き', 'い'), 'energy'),
                   (r'山札の下に置' + V('く', 'き', 'い'), 'deckBottom'), (r'登場させ' + V('る', ''), 'summon'),
                   (r'ライフの先頭に置' + V('く', 'き', 'い'), 'life'), (r'山札の上に置' + V('く', 'き', 'い'), 'deckTop'), (r'リムーブ' + V('する', 'し'), 'remove')]:
        add(rx + MAY + END, lambda m, op=op: {'op': op, 'to': 'T', **({'may': 1} if m.group('may') else {})})
    # 다음 스탠드 페이즈에 스탠드하지 않음
    add(r'(?P<to>[^、。]*?)は次の(?:相手の|あなたの)?スタンドフェイズにスタンドしない' + END, lambda m: subj(m.group('to')) and {'op': 'freeze', 'to': subj(m.group('to'))})
    # 이번 턴 대상이 드롭되었을 때 ~
    def watch(m):
        sub = parse_effects(m.group('x'))
        return sub and {'op': 'watch', 'on': 'leave', 'do': sub}
    add(r'(?:そのターン中|このターン)、?対象が(?:フィールドから)?ドロップした時、(?P<x>[^。]+)(?:。|$)', watch)
    # 계약서 (ツイステッドワンダーランド): 덱 위 카드를 앞면으로 테리토리에 붙임
    add(r'あなたの山札(?:を|の)上から(?P<n>\d+)枚、表で(?:この)?テリトリーに契約書としてつけ' + V('る', '') + END, lambda m: {'op': 'contract', 'n': int(m.group('n'))})
    add(r'あなたの山札(?:を|の)上から(?P<n>\d+)枚、表で契約書としてこのテリトリーにつけ' + V('る', '') + END, lambda m: {'op': 'contract', 'n': int(m.group('n'))})
    add(r'あなたのつけた契約書を(?P<n>\d+)枚ドロップ' + V('する', 'し') + MAY + END, lambda m: {'op': 'contractDrop', 'n': int(m.group('n')), **({'may': 1} if m.group('may') else {})})
    add(r'相手のテリトリーにつけられている契約書を全てドロップ' + V('する', 'し') + END, lambda m: {'op': 'contractDrop', 'all': 1, 'who': 'opp'})
    add(r'あなたは追加の1ターンを行う' + END, lambda m: {'op': 'extraTurn'})
    add(r'__CHOOSE__$', lambda m: {'op': 'choose'})
    # 「~해도 된다」 비용형: 패의 카드를 드롭/공개, 에너지 드롭
    add(r'(?:あなたは)?(?:あなたの)?手札(?:の|から)、?' + DESC + r'(?:' + NOUN[:-1] + r'))?を(?P<n>\d+)枚(?P<v>ドロップ|公開)' + V('する', 'し') + MAY + END,
        lambda m: (lambda f: f is not None and {'op': 'discard' if m.group('v') == 'ドロップ' else 'revealHand', 'n': int(m.group('n')), 'f': noun_filter(f, m.group('noun')), **({'may': 1, 'opt': 1} if m.group('may') else {})})(parse_desc(m.group('d'))))
    add(r'あなたのエナジーを(?P<n>\d+)枚ドロップ' + V('する', 'し') + MAY + END, lambda m: {'op': 'payEnergy', 'n': int(m.group('n')), 'how': 'drop', **({'may': 1} if m.group('may') else {})})
    add(r'(?:あなたは)?(?:自分の|あなたの)?山札(?:を|の)上から(?P<n>\d+)枚(?P<upto>まで)?(?:を)?ドロップ' + V('する', 'し') + MAY + END,
        lambda m: {'op': 'mill', 'n': int(m.group('n')), **({'may': 1} if m.group('may') or m.group('upto') else {})})
    add(r'(?:あなたは)?(?P<n>\d+)枚引いてよい' + END, lambda m: {'op': 'draw', 'n': int(m.group('n')), 'may': 1})
    add(r'相手のライフの先頭をドロップ' + V('する', 'し', 'させる', 'させ') + END, lambda m: {'op': 'lifeDrop', 'n': 1, 'who': 'opp'})
    add(r'相手のライフの先頭を墓地に置' + V('く', 'き') + END, lambda m: {'op': 'lifeDrop', 'n': 1, 'who': 'opp'})
    add(r'(?:あなたの)?山札(?:を|の)上から(?P<n>\d+)枚、?(?:を)?(?P<z>ライフ(?:ゾーン)?の先頭|エナジーゾーン)に置' + V('く', 'き', 'い') + END,
        lambda m: {'op': 'lifeTop' if 'ライフ' in m.group('z') else 'deckEnergy', 'n': int(m.group('n'))})
    add(r'(?:あなたの)?山札をシャッフルして上から(?P<n>\d+)枚(?:を)?ライフ(?:ゾーン)?の先頭に置' + V('く', 'き', 'い') + END, lambda m: {'op': 'lifeTop', 'n': int(m.group('n')), 'shuffle': 1})
    add(r'対象とこのユニットは(?:互いの)?パワー分、ダメージを与えあう' + END, lambda m: [{'op': 'fight', 'self': 1}])
    add(r'それらは互いのパワー分、ダメージを与えあう' + END, lambda m: {'op': 'fight'})
    add(r'(?:そのターン中、)?(?P<to>このユニット|対象)(?:の)?ヒット(?P<n>[+-]\d+)' + END, lambda m: {'op': 'hit', 'n': int(m.group('n')), 'to': subj(m.group('to'))})
    add(r'ヒット(?P<n>[+-]\d+)' + END, lambda m: {'op': 'hit', 'n': int(m.group('n')), 'to': '$prev'})
    add(r'あなたのライフの先頭を見る。それが' + DESC + r'(?:' + NOUN[:-1] + r'))?なら、(?:公開して)?手札に加え(?:る|て(?:も)?よい)' + END,
        lambda m: (lambda f: f is not None and {'op': 'lifeTake', 'f': noun_filter(f, m.group('noun')), 'may': 1})(parse_desc(m.group('d'))))
    add(r'このカードを(?:ドロップゾーンに置く|ドロップする|解決しドロップする)際、代わりに手札に戻' + V('す', 'し') + END, lambda m: {'op': 'selfToHand'})
    add(r'(?:このターン|そのターン中、)?(?P<to>[^、。]*?)は1ダメージでも受けるとドロップする' + END, lambda m: subj(m.group('to')) and {'op': 'kw', 'kw': 'fragile', 'to': subj(m.group('to'))})
    add(r'(?:そのターン中、)?対象がドロップする際、代わりにリムーブ' + V('する', 'し') + END, lambda m: {'op': 'kw', 'kw': 'exile', 'to': 'T'})
    add(r'相手は対象を(?P<r>レストで)?登場させ' + V('る', '') + END, lambda m: {'op': 'summonRested' if m.group('r') else 'summon', 'to': 'T'})
    add(r'対象とこのユニットを(?P<st>スタンドで)?入れ替え' + V('る', '') + END, lambda m: {'op': 'swapT', **({'stand': 1} if m.group('st') else {})})
    add(r'あなたのエナジーを(?P<n>\d+)枚、?(?:望む順で)?山札の下に置' + V('く', 'き', 'い') + END, lambda m: {'op': 'pick', 'from': 'energy', 'to': 'bottom', 'f': {}, 'n': int(m.group('n')), 'upto': 0})
    add(r'(?:そのターン中、)?相手のユニット全ては可能な限りブロックする' + END, lambda m: {'op': 'kw', 'kw': 'mustBlock', 'to': {'all': {'side': 'opp', 'type': 'unit'}}})
    add(r'(?:あなたの)?山札を上から1枚見る。それがアタックしたユニットと異なる色でヒット(?P<h>\d+)なら登場させ、違うならドロップしてよい' + END,
        lambda m: {'op': 'peekDiff', 'hit': int(m.group('h'))})
    add(r'相手は対象をライフの先頭に置' + V('く', 'き', 'い') + END, lambda m: {'op': 'life', 'to': 'T'})
    add(r'ドロップゾーンのこのカードをレストで登場させるかエナジーゾーンに置' + V('く', 'き') + END,
        lambda m: {'op': 'choose', 'opts': [[{'op': 'summonRested', 'to': 'card'}], [{'op': 'energy', 'to': 'card'}]], 'labels': ['레스트로 등장', '에너지 존에 놓음']})
    add(_DUR + r'(?:次の(?:相手|あなたの)?ターンまで、)?(?P<to>[^、。]*?)はドロップ以外の方法でフィールドを離れない' + END,
        lambda m: subj(m.group('to')) and {'op': 'kw', 'kw': 'stayField', 'to': subj(m.group('to'))})
    def tturn(m):
        sub = parse_effects(m.group('x'))
        return sub and {'op': 'turnTrig', 'on': 'leave', 'side': 'opp' if m.group('w') == '相手' else 'own', 'do': sub}
    add(r'このターン(?P<w>相手|あなた)のユニットがフィールドからドロップした時、(?P<x>[^。]+)(?:。|$)', tturn)
    def twin(m):
        sub = parse_effects(m.group('x'))
        return sub and {'op': 'watch', 'on': 'win', 'do': sub}
    add(r'(?:そのターン中、)?対象がバトルに勝利した時、(?P<x>[^。]+)(?:。|$)', twin)
    add(r'あなたの山札(?:を|の)下から(?P<n>\d+)枚(?:を)?ドロップ' + V('する', 'し') + END, lambda m: {'op': 'millBottom', 'n': int(m.group('n'))})
    add(_DUR + r'(?P<to>[^、。]*?)はいかなる方法でもドロップしない' + END, lambda m: subj(m.group('to')) and {'op': 'kw', 'kw': 'indestructible', 'to': subj(m.group('to'))})
    add(r'(?:そのターン中、)?あなたはライフの枚数に関わらずレッドゾーンとなる' + END, lambda m: {'op': 'turnFlag', 'flag': 'red'})
    add(_DUR + r'(?:さらに)?(?P<mods>(?:パワー|ヒット)を[+-]\d+)' + END, lambda m: {'op': 'pow' if m.group('mods').startswith('パワー') else 'hit', 'n': int(re.search(r'[+-]\d+', m.group('mods')).group()), 'to': '$prev'})
    add(_DUR + r'(?P<to>このユニット|対象)は(?P<mods>(?:パワー|ヒット)を[+-]\d+)' + END, lambda m: {'op': 'pow' if m.group('mods').startswith('パワー') else 'hit', 'n': int(re.search(r'[+-]\d+', m.group('mods')).group()), 'to': subj(m.group('to'))})
    add(r'あなたの手札を(?P<n>\d+)枚(?P<upto>まで)?公開' + V('する', 'し') + END, lambda m: {'op': 'revealHand', 'n': int(m.group('n')), 'f': {}, **({'opt': 1} if m.group('upto') else {})})
    add(r'あなたの手札を(?P<n>\d+)枚リムーブ' + V('する', 'し') + MAY + END, lambda m: {'op': 'pick', 'from': 'hand', 'to': 'remove', 'f': {}, 'n': int(m.group('n')), 'upto': 1 if m.group('may') else 0})
    add(r'あなたの(?P<z>ドロップゾーン|手札|エナジーゾーン)の、?' + DESC + r'(?:' + NOUN[:-1] + r'))?を(?P<n>\d+)枚、コストを払わず(?:に)?プレイ' + V('する', 'し') + MAY + END,
        lambda m: (lambda f: f is not None and {'op': 'playFree', 'from': {'ドロップゾーン': 'drop', '手札': 'hand', 'エナジーゾーン': 'energy'}[m.group('z')], 'f': noun_filter(f, m.group('noun')), 'may': 1})(parse_desc(m.group('d'))))
    MV = {'手札に戻': 'bounce', '山札の下に置': 'deckBottom', '山札の上に置': 'deckTop', 'ライフの先頭に置': 'life', 'エナジーゾーンに置': 'energy', 'ドロップさせ': 'drop', 'リムーブ': 'remove'}
    LB = {'bounce': '패로 되돌림', 'deckBottom': '덱 맨 아래', 'deckTop': '덱 맨 위', 'life': '라이프 맨 앞', 'energy': '에너지 존', 'drop': '드롭', 'remove': '리무브'}
    def or_move(m):
        a, b = MV[m.group('a')], MV[m.group('b')]
        return {'op': 'choose', 'opts': [[{'op': a, 'to': 'T'}], [{'op': b, 'to': 'T'}]], 'labels': [LB[a], LB[b]]}
    alts = '|'.join(MV)
    add(r'対象を、?(?P<a>' + alts + r')(?:す|く|る|)か(?P<b>' + alts + r')' + V('す', 'く', 'る', 'する', '') + END, or_move)
    add(r'(?P<to>対象|このユニット)に(?P<src>このユニット|対象)のパワー(?:分の|と同じ)ダメージを与え' + V('る', '') + END,
        lambda m: {'op': 'dmgPow', 'to': subj(m.group('to')), 'from': subj(m.group('src'))})
    add(r'(?:あなたは)?(?P<n>\d+)枚引いて(?P<k>\d+)枚ドロップ' + V('する', 'し') + END, lambda m: [{'op': 'draw', 'n': int(m.group('n'))}, {'op': 'discard', 'n': int(m.group('k'))}])
    add(r'(?P<d>[^、。]*?)ユニットを望む枚数対象と' + V('し', 'する') + END,
        lambda m: (lambda f: f is not None and {'op': 'tgt', 'f': {**f, 'type': 'unit'}, 'n': 99, 'upto': 1})(parse_desc(m.group('d'))))
    add(r'(?P<d>[^、。]*?)ユニットを望む枚数対象とし、(?P<n>\d+)ダメージ' + END,
        lambda m: (lambda f: f is not None and [{'op': 'tgt', 'f': {**f, 'type': 'unit'}, 'n': 99, 'upto': 1}, {'op': 'dmg', 'n': int(m.group('n')), 'to': 'T'}])(parse_desc(m.group('d'))))
    add(r'レストで登場させ' + V('る', '') + END, lambda m: {'op': 'summonRested', 'to': 'T'})
    add(r'対象は互いのパワー分、ダメージを与えあう' + END, lambda m: {'op': 'fight'})
    add(r'(?P<n>[+-]\d+)' + END, lambda m: {'op': '$prevop', 'n': int(m.group('n')), 'to': '$prev'})
    # 라이프 맨 앞 보기 / 공개
    add(r'あなたのライフの先頭を見る' + END, lambda m: {'op': 'peekLife'})
    # 배틀 상대 중 조건에 맞으면 드롭
    add(r'(?P<d>[^、。]*?)バトル相手をドロップさせ' + V('る', '') + END,
        lambda m: (lambda f: f is not None and {'op': 'drop', 'to': 'vs', 'vf': f})(parse_desc(m.group('d'))))
    # 이 카드를 (드롭 존/에너지에서) 코스트 없이 플레이
    add(r'(?P<z>ドロップゾーン|エナジー|手札)のこのカードをコストを払わず(?:に)?プレイ' + V('する', 'し') + MAY + END,
        lambda m: {'op': 'playSelf', 'from': {'ドロップゾーン': 'drop', 'エナジー': 'energy', '手札': 'hand'}[m.group('z')], 'may': 1})
    add(r'あなたのライフの先頭をドロップ' + V('する', 'し') + MAY + END, lambda m: {'op': 'lifeDrop', 'n': 1, **({'may': 1} if m.group('may') else {})})
    add(r'相手は自身のユニットを(?P<n>\d+)枚ドロップさせ' + V('る', '') + END, lambda m: {'op': 'sacrifice', 'who': 'opp', 'n': int(m.group('n'))})
    add(r'(?:次のエンドフェイズ開始時、)?あなたのテリトリーを閉じ' + V('る', '') + END, lambda m: {'op': 'closeTerr'})
    for rx, op in [(r'スタンド' + V('する', 'し', 'させる', 'させ'), 'stand'), (r'レスト' + V('する', 'し', 'させる', 'させ'), 'rest')]:
        add(rx + END, lambda m, op=op: {'op': op, 'to': 'T'})
    # 서로 파워만큼 데미지
    add(r'あなたのユニット1枚と相手のユニット1枚を対象とし、それらは互いのパワー分、ダメージを与えあう' + END,
        lambda m: [{'op': 'tgt', 'f': {'side': 'own', 'type': 'unit'}, 'n': 1, 'upto': 0, 'save': 'A'}, {'op': 'tgt', 'f': {'side': 'opp', 'type': 'unit'}, 'n': 1, 'upto': 0, 'save': 'B'}, {'op': 'fight'}])
    add(r'(?:レストしている)?ユニットを2枚対象とし、(?:それらは)?互いのパワー分、ダメージを与えあう' + END,
        lambda m: [{'op': 'tgt', 'f': {'type': 'unit'}, 'n': 2, 'upto': 0}, {'op': 'fight'}])
    # 필드에 뒷면으로 두기 (かぐや様)
    add(r'(?:自分|あなた)の手札を(?P<n>\d+)枚(?P<upto>まで)?フィールドに伏せ' + V('る', '') + MAY + END, lambda m: {'op': 'setHand', 'n': int(m.group('n')), **({'may': 1} if m.group('upto') or m.group('may') else {})})
    add(r'このユニットを(?:裏にして)?フィールドに伏せ' + V('る', '') + MAY + END, lambda m: {'op': 'setSelf', **({'may': 1} if m.group('may') else {})})
    add(r'対象をフィールドに伏せ' + V('る', '') + END, lambda m: {'op': 'setT'})
    add(r'あなたの伏せたカードの中から、?' + DESC + r'(?:' + NOUN[:-1] + r'))?を(?P<n>\d+)枚(?P<upto>まで)?(?P<rest>レストで)?登場させ' + V('る', '') + END,
        lambda m: (lambda f: f is not None and {'op': 'pick', 'from': 'set', 'to': 'field', 'f': noun_filter(f, m.group('noun')), 'n': int(m.group('n')), 'upto': 1 if m.group('upto') else 0, **({'rested': 1} if m.group('rest') else {})})(parse_desc(m.group('d'))))
    add(r'あなたの伏せたカード(?P<n>\d+)枚をドロップ' + V('する', 'し') + MAY + END, lambda m: {'op': 'pick', 'from': 'set', 'to': 'drop', 'f': {}, 'n': int(m.group('n')), 'upto': 1, 'rec': 1})
    add(r'あなたの伏せたカード(?:を)?全てをドロップ' + V('する', 'し') + MAY + END, lambda m: {'op': 'setDropAll', **({'may': 1} if m.group('may') else {})})
    add(r'あなたの伏せたカードを全てドロップ' + V('する', 'し') + MAY + END, lambda m: {'op': 'setDropAll', **({'may': 1} if m.group('may') else {})})
    add(r'相手の伏せたカード全てを手札に戻' + V('す', 'し') + END, lambda m: {'op': 'setBounceOpp'})
    add(r'あなたの裏のエナジーを(?P<n>\d+)枚(?:まで)?表に' + V('する', 'し') + END, lambda m: {'op': 'unflipEnergy', 'n': int(m.group('n'))})
    def at_end(m):
        sub = parse_effects(m.group('x'))
        return sub and {'op': 'delay', 'at': 'attackEnd', 'do': sub}
    add(r'このアタック(?:の)?終了時、(?P<x>[^。]+)(?:。|$)', at_end)
    add(r'(?:そのターン中、)?あなたはダメージで(?:は)?敗北せず' + END, lambda m: {'op': 'turnFlag', 'flag': 'noLoseDmg'})
    add(r'(?:そのターン中、)?あなたはダメージで(?:は)?敗北しない' + END, lambda m: {'op': 'turnFlag', 'flag': 'noLoseDmg'})
    add(r'各プレイヤーは(?P<n>\d+)枚引(?:く|き|いて(?P<may>(?:も)?よい))' + END,
        lambda m: [{'op': 'draw', 'n': int(m.group('n')), **({'may': 1} if m.group('may') else {})}, {'op': 'draw', 'n': int(m.group('n')), 'who': 'opp', **({'may': 1} if m.group('may') else {})}])
    add(_DUR + r'(?P<to>[^、。]*?)のパワーを0になるよう(?:減少|増減)させ' + V('る', '') + END, lambda m: subj(m.group('to')) and {'op': 'powZero', 'to': subj(m.group('to'))})
    add(r'このターンあなたの手札上限は(?P<n>\d+)枚になる' + END, lambda m: {'op': 'turnFlag', 'flag': 'hand' + m.group('n')})
    # 클래스 카드 (Fate/Grand Order)
    add(r'(?:あなたは)?クラスカードを(?P<n>\d+)枚生成してエナジーゾーンに置' + V('く', 'き', 'い') + END, lambda m: {'op': 'genClass', 'n': int(m.group('n')), 'to': 'energy'})
    def gen_att(m):
        t = m.group('t')
        if t in ('このユニット', 'そのユニット', 'このテリトリー'):
            return {'op': 'genClass', 'n': int(m.group('n')), 'to': {'このユニット': 'self', 'そのユニット': 'T', 'このテリトリー': 'terr'}[t]}
        if 'エースか⁅バスターアイコン⁆' in t:
            return [{'op': 'tgt', 'f': {'side': 'own', 'type': 'unit', 'aceOrBuster': 1}, 'n': 1, 'upto': 0}, {'op': 'genClass', 'n': int(m.group('n')), 'to': 'T'}]
        f = parse_desc(re.sub(r'^あなたの、?', 'あなたの', t).replace('ユニット', '').replace('エース', '') or '')
        if f is None:
            return None
        if 'エース' in t and 'エースか' not in t:
            f['ace'] = 1
        f.setdefault('side', 'own')
        f['type'] = 'unit'
        return [{'op': 'tgt', 'f': f, 'n': 1, 'upto': 0}, {'op': 'genClass', 'n': int(m.group('n')), 'to': 'T'}]
    add(r'(?:あなたは)?(?P<t>このユニット|そのユニット|このテリトリー|エース|あなたの[^。]*?ユニット(?:1枚)?)にクラスカードを(?P<n>\d+)枚生成してつけ' + V('る', '') + END, gen_att)
    add(r'(?:あなたは)?クラスカードを(?P<n>\d+)枚生成して(?P<t>このユニット|そのユニット)につけ' + V('る', '') + END,
        lambda m: {'op': 'genClass', 'n': int(m.group('n')), 'to': 'self' if m.group('t') == 'このユニット' else 'T'})
    add(r'あなたのドロップゾーンのクラスカードを(?P<n>\d+)枚(?P<upto>まで)?エナジーゾーンに置' + V('く', 'き', 'い') + MAY + END,
        lambda m: {'op': 'classFromDrop', 'n': int(m.group('n')), 'to': 'energy', **({'may': 1} if m.group('may') else {})})
    add(r'あなたのドロップゾーンのクラスカードを1枚、あなたの(?P<d>[^、。]*?)ユニットにつけ(?:る|て)' + MAY + END,
        lambda m: (lambda f: f is not None and [{'op': 'tgt', 'f': {**f, 'side': 'own', 'type': 'unit'}, 'n': 1, 'upto': 1}, {'op': 'classFromDrop', 'n': 1, 'to': 'T'}])(parse_desc(m.group('d'))))
    # 「生成」 없이 「つける」여도 게임 밖에서 붙임 (FAQ 赤く染まる大平原)
    add(r'あなたの(?P<d>[^、。]*?)ユニット1枚にクラスカードを1枚つけ' + V('る', '') + END,
        lambda m: (lambda f: f is not None and [{'op': 'tgt', 'f': {**f, 'side': 'own', 'type': 'unit'}, 'n': 1, 'upto': 0}, {'op': 'genClass', 'n': 1, 'to': 'T'}])(parse_desc(m.group('d'))))
    add(r'このテリトリーにつけたクラスカードを(?P<n>\d+)枚ドロップ' + V('する', 'し') + MAY + END,
        lambda m: {'op': 'classTerrDrop', 'n': int(m.group('n')), **({'may': 1} if m.group('may') else {})})
    add(r'次の相手ターンまで、クラスカードであなたのユニットのパワーが増加する際、\+1000の代わりに\+3000される' + END, lambda m: {'op': 'classBoost'})
    add(_DUR + r'(?P<to>このユニット|対象)はヒット(?P<n>[+-]\d+)' + END, lambda m: {'op': 'hit', 'n': int(m.group('n')), 'to': subj(m.group('to'))})
    # 코스프레 관련
    add(_DUR + r'(?P<to>このユニット|そのユニット|対象)は【コスプレ(?P<n>\d+)】を得(?:る|て)(?:、(?P<mods>(?:パワー|ヒット)を[+-]\d+))?' + END,
        lambda m: [{'op': 'kw', 'kw': 'cos' + m.group('n'), 'to': subj(m.group('to'))}] + ([{'op': 'pow' if m.group('mods').startswith('パワー') else 'hit', 'n': int(re.search(r'[+-]\d+', m.group('mods')).group()), 'to': subj(m.group('to'))}] if m.group('mods') else []))
    add(r'(?:そのターン中、)?あなたのユニットの【コスプレ】は手札とエナジーから選べる' + END, lambda m: {'op': 'turnFlag', 'flag': 'cosEnergy'})
    add(r'このターンに【コスプレ】で登場するあなたのユニットはスタンドで登場する' + END, lambda m: {'op': 'turnFlag', 'flag': 'cosStand'})
    add(r'その【コスプレ】で登場するバスターアイコンはスタンドで登場する' + END, lambda m: {'op': 'turnFlag', 'flag': 'cosBusterStand'})
    add(r'このユニットは【コスプレ】' + V('する', 'し') + MAY + END, lambda m: {'op': 'cosplayNow', 'may': 1})
    # 붙이기
    add(r'このカードを(?:対象|そのユニット)につけ' + V('る', '') + END, lambda m: {'op': 'attachSelf'})
    add(r'このカードをあなたのユニット1枚につけ(?:る|て)' + MAY + END,
        lambda m: [{'op': 'tgt', 'f': {'side': 'own', 'type': 'unit'}, 'n': 1, 'upto': 0, **({'may': 1} if m.group('may') else {})}, {'op': 'attachSelf'}])
    add(r'(?:相手の)?ライフの先頭をドロップさせ' + V('る', '') + END, lambda m: {'op': 'lifeDrop', 'n': 1, 'who': 'opp'})
    # 지연: 다음 엔드 페이즈 시작 시
    def delay(m):
        sub = parse_effects(m.group('x'))
        return sub and {'op': 'delay', 'at': 'endStart', 'do': sub}
    add(r'次の(?:あなたの)?エンドフェイズ開始時、(?P<x>[^。]+)(?:。|$)', delay)
    add(r'相手は手札を全て公開' + V('する', 'し') + END, lambda m: {'op': 'reveal'})
    # 드로우
    add(r'(?:あなたは)?(?P<n>\d+)枚引' + V('く', 'き', 'いて') + MAY + END,
        lambda m: {'op': 'draw', 'n': int(m.group('n')), **({'may': 1} if m.group('may') else {})})
    add(r'相手は(?P<n>\d+)枚引' + V('く', 'き', 'い') + END, lambda m: {'op': 'draw', 'n': int(m.group('n')), 'who': 'opp'})
    # 스카웃
    add(r'(?:あなたは)?スカウト(?P<n>\d+)(?:する|し|を行う)?' + END, lambda m: {'op': 'scout', 'n': int(m.group('n'))})
    # 패 버리기
    add(r'(?:あなたは)?(?:あなたの)?手札(?:から|を)(?P<n>\d+)枚(?:選んで)?ドロップ' + V('する', 'し') + MAY + END,
        lambda m: {'op': 'discard', 'n': int(m.group('n')), **({'may': 1} if m.group('may') else {})})
    add(r'相手は(?:自身の)?手札を(?P<n>\d+)枚(?:選んで)?ドロップ' + V('する', 'し') + END,
        lambda m: {'op': 'discard', 'n': int(m.group('n')), 'who': 'opp'})
    # 덱 위에서 드롭
    add(r'(?:その後、)?あなたの山札(?:を|の)上から(?P<n>\d+)枚(?:を)?ドロップ' + V('する', 'し') + MAY + END,
        lambda m: {'op': 'mill', 'n': int(m.group('n')), **({'may': 1} if m.group('may') else {})})
    # 라이프 추가
    add(r'あなたの山札をシャッフル(?:して|し、)(?:山札を|その)?上から(?P<n>\d+)枚(?:を)?ライフ(?:ゾーン)?の先頭に置' + V('く', 'き', 'い') + END,
        lambda m: {'op': 'lifeTop', 'n': int(m.group('n')), 'shuffle': 1})
    add(r'あなたの山札(?:を|の)上から(?P<n>\d+)枚(?:を)?ライフ(?:ゾーン)?の先頭に置' + V('く', 'き', 'い') + END,
        lambda m: {'op': 'lifeTop', 'n': int(m.group('n'))})
    add(r'あなたの山札をシャッフル' + V('する', 'し') + END, lambda m: {'op': 'shuffle'})
    # 덱 위에서 에너지
    add(r'あなたの山札(?:を|の)上から(?P<n>\d+)枚(?:を)?エナジーゾーンに置' + V('く', 'き', 'い') + END,
        lambda m: {'op': 'deckEnergy', 'n': int(m.group('n'))})
    # 라이프 맨 앞 -> 에너지 / 패
    add(r'あなたのライフの先頭(?:の(?P<n>\d+)枚)?をエナジーゾーンに置' + V('く', 'き', 'い') + END,
        lambda m: {'op': 'lifeEnergy', 'n': int(m.group('n') or 1)})
    add(r'あなたのライフの先頭(?:の(?P<n>\d+)枚)?を手札に加え' + V('る', '') + END,
        lambda m: {'op': 'lifeHand', 'n': int(m.group('n') or 1)})
    # 에너지 스탠드
    add(r'あなたのエナジーを(?P<n>\d+)枚(?:まで)?スタンド' + V('する', 'し') + END,
        lambda m: {'op': 'energyStand', 'n': int(m.group('n'))})

    # 존에서 골라 패/필드로
    def pick(m):
        f = parse_desc(m.group('d') or '')
        if f is None:
            return None
        if m.group('noun') == 'バスターアイコン':
            f['icon'] = 'buster'
        elif m.group('noun'):
            noun_filter(f, m.group('noun'))
        dest = 'field' if '登場' in m.group('v') else 'life' if 'ライフ' in m.group('v') else 'energy' if 'エナジー' in m.group('v') else 'remove' if 'リムーブ' in m.group('v') else 'hand'
        zone = {'ドロップゾーン': 'drop', '手札': 'hand', 'エナジーゾーン': 'energy', 'エナジー': 'energy'}[m.group('zone')]
        if zone == dest:
            return None
        st = {'op': 'pick', 'from': zone, 'to': dest, 'f': f, 'n': int(m.group('n')), 'upto': 1 if m.group('upto') else 0}
        if m.group('rest'):
            st['rested'] = 1
        if m.group('may'):
            st['upto'] = 1
        return st
    add(r'(?:あなたの)?(?P<zone>ドロップゾーン|手札|エナジーゾーン|エナジー)(?:の|から)(?P<d>(?:[^。を]|を持つ|を含む)*?)(?:' + NOUN[:-1] + r'|バスターアイコン))?を(?P<n>\d+)枚(?P<upto>まで)?(?:選んで)?(?:公開して)?(?P<rest>レストで)?(?P<v>手札に加え(?:る|)|登場させ(?:る|)|ライフの先頭に置(?:く|き|い)|エナジーゾーンに置(?:く|き|い)|リムーブ(?:する|し))' + MAY + END, pick)

    # 덱 위 N장 보고 고르기
    def look(m):
        f = parse_desc(m.group('d') or '')
        if f is None:
            return None
        if m.group('noun'):
            noun_filter(f, m.group('noun'))
        dest = 'field' if '登場' in m.group('v') else 'energy' if 'エナジー' in m.group('v') else 'hand'
        r = m.group('r') or m.group('r2') or ''
        rest = 'drop' if 'ドロップ' in r else 'top' if '上' in r else 'shuffle' if 'シャッフル' in r else 'energy' if 'エナジー' in r else 'bottom'
        k = 99 if m.group('all') else int(m.group('k'))
        return {'op': 'look', 'n': int(m.group('n')), 'f': f, 'k': k, 'to': dest, 'rest': rest, **({'rested': 1} if m.group('rst') else {})}
    add(r'あなたの山札(?:を|の)上から(?P<n>\d+)枚(?:見て|公開し)、(?:その中(?:から|の)、?)?(?P<d>(?:[^。を]|を持つ|を含む)*?)(?:' + NOUN + r')?(?:を(?P<k>\d+)枚まで|(?P<all>全て)を)(?:公開して)?(?P<rst>レストで)?(?P<v>手札に加え|登場させ|エナジーゾーンに置き)、(?:残りを(?P<r>ドロップ|望む順で山札の下に置|山札の下に置|望む順で山札の上に置|山札の上に置|エナジーゾーンに置)' + V('する', 'く', 'し', 'き') + r'|(?P<r2>山札をシャッフル)' + V('する', 'し') + r')' + END,
        lambda m: look(m) if m.group('r') or True else None)
    return P


EFF = eff_patterns()

# ---------- 조건 ----------
def _pair(a, b):
    """「「日向」を含むカードと「ユイ」を含むカード」 / 「青と赤のエースカード」 -> 두 묘사"""
    noun = re.search(r'(エースカード|ユニットカード|コマンドカード|カード)$', b)
    if noun and not re.search(r'(カード)$', a):
        return a + 'の' + noun.group(1), b
    return a, b


def _zdesc(d):
    """장수 조건의 카드 묘사 -> 필터 (없으면 전부)"""
    if not d:
        return {}
    d = d.strip()
    m = re.fullmatch(r'「([^」]+)」', d)
    if m:
        return {'name': m.group(1)}
    noun = re.search(r'(エースカード|エース|ユニットカード|ユニット|コマンドカード|カード)$', d)
    core = d[:noun.start()] if noun else d
    f = parse_desc(core) if core else {}
    if f is None and core and not core.endswith('の'):
        f = parse_desc(core + 'の')
    if f is None:
        return None
    return noun_filter(f, noun.group(1) if noun else '')


def parse_cond(t):
    """'あなたのライフがレッドゾーン' 같은 조건문 (なら/中/で 앞부분) -> dict | None"""
    t = t.strip('、')
    if t.endswith('てい'):
        t += 'る'
    t = re.sub(r'クラスカードが(\d+)枚以上ついたこのユニットがレストしている', r'このユニットにつけたクラスカードが\1枚以上かつこのユニットがレストしている', t)
    if t.startswith('あなたの、'):   # 「あなたの、手札が1枚以下でテリトリー開放中」
        xs = re.split(r'で(?=テリトリー|ライフ|手札|ドロップ|エナジー|称号|リムーブ|フィールド)|(?<=がい)て(?=テリトリー)', t[5:])
        xs = [x + 'る' if x.endswith('がい') else x for x in xs]
        t = 'かつ'.join('あなたの' + x if not x.startswith(('あなた', '相手')) else x for x in xs)
    t = re.sub(r'が開放されていて、', 'が開放されているかつ', t)
    t = re.sub(r'引いていた$', '引いている', t)
    t = re.sub(r'(ユニット|エース)がいて、?', r'\1がいるかつ', t)
    _LAST.setdefault('cond', None)
    C = [
        (r'このターン(?:に)?あなたがコマンドをプレイしてい(?:る|た)', lambda m: {'cmdTurn': 1}),
        (r'このターン(?:に)?あなたのカードがリムーブされてい(?:る|た)', lambda m: {'removedTurn': 1}),
        (r'あなたのユニットが合計(?P<n>\d+)色(?:以上)?', lambda m: {'unitColorsGE': int(m.group('n'))}),
        (r'相手のメインフェイズ(?:中)?', lambda m: {'oppTurn': 1, 'phase': 'main'}),
        (r'あなたのメインフェイズ(?:中)?', lambda m: {'myTurn': 1, 'phase': 'main'}),
        (r'このユニットがエースとバトルする', lambda m: {'battleVsAce': 1}),
        (r'あなたの「(?P<n>[^」]+)」が開放中', lambda m: {'terrName': m.group('n')}),
        (r'あなたのドロップゾーンにある称号が合計(?P<n>\d+)種類以上', lambda m: {'dropTitlesGE': int(m.group('n'))}),
        (r'あなたの(?P<z>ドロップゾーン|リムーブゾーン)に(?:カード名に、)?(?P<a>[^、。]+?)と(?P<b>[^、。]+?)がそれぞれある',
         lambda m: (lambda Z, fa, fb: fa is not None and fb is not None and {'zcAll': [{'side': 'own', 'zone': Z, 'f': fa, 'n': 1, 'cmp': 'ge'}, {'side': 'own', 'zone': Z, 'f': fb, 'n': 1, 'cmp': 'ge'}]})(
             m.group('z'), _zdesc(_pair(m.group('a'), m.group('b'))[0]), _zdesc(_pair(m.group('a'), m.group('b'))[1]))),
        (r'あなたのフィールドかドロップゾーンに(?P<d>[^、。]+?)がある', lambda m: (lambda f: f is not None and {'zc': {'side': 'own', 'zones': ['field', 'drop'], 'f': f, 'n': 1, 'cmp': 'ge'}})(_zdesc(m.group('d')))),
        (r'あなたの(?P<z>ドロップゾーン|リムーブゾーン)に(?P<d>[^、。]+?)が(?P<n>\d+)(?P<k>枚|種類)(?:以上)?ある', lambda m: (lambda f: f is not None and {'zc': {'side': 'own', 'zone': m.group('z'), 'f': f, 'n': int(m.group('n')), 'cmp': 'ge', **({'kinds': 1} if m.group('k') == '種類' else {})}})(_zdesc(m.group('d')))),
        (r'あなたの(?P<d>[^、。]+?)エナジーが(?:合計)?(?P<n>\d+)枚以上', lambda m: (lambda f: f is not None and {'zc': {'side': 'own', 'zone': 'エナジー', 'f': f, 'n': int(m.group('n')), 'cmp': 'ge'}})(_zdesc(m.group('d')))),
        (r'(?:あなたの)?ライフがレッドゾーン', lambda m: {'red': 1}),
        (r'相手のユニットがあなたより多い', lambda m: {'oppMore': 1}),
        (r'相手のユニットの枚数があなたのユニット以上', lambda m: {'oppGE': 1}),
        (r'対象が【(?P<k>デコイ|ブリッツ|バーサーク)】を持つ', lambda m: {'tHasKw': {'デコイ': 'decoy', 'ブリッツ': 'blitz', 'バーサーク': 'berserk'}[m.group('k')]}),
        (r'山札から(?P<d>[^、。]*?)をドロップした?', lambda m: {'milled': parse_desc(m.group('d').replace('バスターアイコン', 'バスターの'))}),
        (r'(?:ドロップ|それ)しない|そうしない', lambda m: {'did': 0}),
        (r'あなたのドロップゾーンの(?P<d>[^、。]*?)(?:ユニットカード|カード)?が(?P<n>\d+)枚以上', 'count'),
        (r'(?:さらに)?(?P<n>\d+)枚(?:以上|以下)?', 'again'),
        (r'相手のライフがレッドゾーン', lambda m: {'oppRed': 1}),
        (r'あなたのテリトリー(?:が開放されている|開放中)', lambda m: {'terr': 1}),
        (r'あなたの称号「(?P<t>[^」]+)」のテリトリー(?:が開放されている|開放中)', lambda m: {'terrTitle': m.group('t')}),
        (r'あなたのターン(?:中)?', lambda m: {'myTurn': 1}),
        (r'相手のターン(?:中)?', lambda m: {'oppTurn': 1}),
        (r'このユニットがレストしている', lambda m: {'selfRested': 1}),
        (r'このユニットがスタンドしている', lambda m: {'selfRested': 0}),
        (r'あなたのドロップゾーン(?:のカード)?が(?P<n>\d+)枚以上', lambda m: {'dropGE': int(m.group('n'))}),
        (r'あなたの手札が(?P<n>\d+)枚以下', lambda m: {'handLE': int(m.group('n'))}),
        (r'あなたの手札が(?P<n>\d+)枚以上', lambda m: {'handGE': int(m.group('n'))}),
        (r'あなたのエナジーが(?P<n>\d+)枚以上', lambda m: {'energyGE': int(m.group('n'))}),
        (r'相手のエナジーが(?P<n>\d+)枚以上', lambda m: {'oppEnergyGE': int(m.group('n'))}),
        (r'あなたのライフが(?P<n>\d+)枚以下', lambda m: {'lifeLE': int(m.group('n'))}),
        (r'相手のライフが(?P<n>\d+)枚以下', lambda m: {'oppLifeLE': int(m.group('n'))}),
        (r'あなたのライフが相手(?:のライフ)?より少ない', lambda m: {'lifeLess': 1}),
        (r'このターン(?:に)?このユニットが登場している', lambda m: {'enteredThisTurn': 1}),
        (r'このユニットが【コスプレ】で登場した', lambda m: {'cos': 1}),
        (r'このユニットにクラスカードがついている', lambda m: {'selfHasClass': 1}),
        (r'あなたの他のユニットがいない', lambda m: {'noOther': 1}),
        (r'相手が引かなかった', lambda m: {'oppDeclined': 1}),
        (r'このターン(?:に)?相手がダメージを受けている', lambda m: {'oppDmgTurn': 1}),
        (r'対象がエース', lambda m: {'tF': {'ace': 1}}),
        (r'対象が(?P<d>[^、。]*?)(?:エースカード|ユニットカード|カード|ユニット)', lambda m: (lambda f: f is not None and {'tF': {**f, **({'ace': 1} if 'エース' in m.group(0) else {})}})(parse_desc(m.group('d')))),
        (r'各プレイヤーのライフの枚数が同じ', lambda m: {'lifeEq': 1}),
        (r'エースカードをドロップした', lambda m: {'milled': {'ace': 1}}),
        (r'相手のエナジーがあなたのエナジーより(?P<n>\d+)枚以上多い', lambda m: {'oppEnergyMore': int(m.group('n'))}),
        (r'あなたのユニットの枚数が相手のユニットの枚数以下', lambda m: {'unitsLE': 1}),
        (r'このユニットのパワーが(?P<n>\d+)以上', lambda m: {'selfPowGE': int(m.group('n'))}),
        (r'このユニットがレストしている', lambda m: {'selfRested': 1}),
        (r'あなたのドロップゾーンに(?P<l>(?:⁅(?:スペード|ハート|ダイヤ|クラブ)⁆、?)+)がある', lambda m: {'dropAttrsEach': re.findall(r'スペード|ハート|ダイヤ|クラブ', m.group('l'))}),
        (r'相手のエナジーが(?P<n>\d+)枚以下', lambda m: {'oppEnergyLE': int(m.group('n'))}),
        (r'あなたのつけたログが(?P<n>\d+)枚以上', lambda m: {'logGE': int(m.group('n'))}),
        (r'(?:このターン(?:に)?)?あなたのユニットが【ブライト】している', lambda m: {'brightTurn': 1}),
        (r'あなたのエナジーが(?P<n>\d+)色(?:以上)?', lambda m: {'energyColorsGE': int(m.group('n'))}),
        (r'このターン(?:に)?あなたが【結束】でカードを引いている', lambda m: {'kessoDrew': 1}),
        (r'このターン(?:に)?あなたのユニットが【ブライト】している', lambda m: {'brightTurn': 1}),
        (r'あなたのリムーブゾーンが(?P<n>\d+)枚以上', lambda m: {'removeGE': int(m.group('n'))}),
        (r'あなたのライフがイエローゾーン', lambda m: {'yellow': 1}),
        (r'相手の手札が(?P<n>\d+)枚以下', lambda m: {'oppHandLE': int(m.group('n'))}),
        (r'相手のユニットが(?P<n>\d+)枚以上', lambda m: {'oppUnitsGE': int(m.group('n'))}),
        (r'あなたの伏せたカードが(?:ない|無い)', lambda m: {'setCount': 0}),
        (r'あなたの伏せたカードがある', lambda m: {'setHas': 1}),
        (r'(?:ドロップした|それらの)カードのコストの合計が(?P<n>\d+)以上', lambda m: {'milledCostGE': int(m.group('n'))}),
        (r'(?P<d>[^、。]+?)をドロップした', lambda m: (lambda f: f is not None and {'milled': f})(parse_desc(m.group('d').replace('ユニットカード', 'ユニット') + 'の') if not m.group('d').endswith('カード') else noun_filter(parse_desc(re.sub(r'(ユニット|コマンド)?カード$', '', m.group('d'))) or {}, re.search(r'(ユニットカード|コマンドカード|カード)$', m.group('d')).group(1)))),
        (r'このユニットが【(?P<n>[^】]+)】を着ている', lambda m: {'wearing': m.group('n').split('/')}),
        (r'このターン(?:に)?あなたがダメージを受けている', lambda m: {'meDmgTurn': 1}),
        (r'あなたの山札が(?P<n>\d+)枚以下', lambda m: {'deckLE': int(m.group('n'))}),
        (r'このターン(?:に)?あなたの他のユニットが登場している', lambda m: {'otherEntered': 1}),
        (r'(?:あなたの、?)?つけた契約書が(?P<n>\d+)枚以上', lambda m: {'contractGE': int(m.group('n'))}),
        (r'あなたのドロップゾーンに(?P<d>[^、。]+?)がある', lambda m: (lambda f: f is not None and {'zoneHas': {'zone': 'drop', 'f': f}})(parse_desc(m.group('d') + 'の') if parse_desc(m.group('d') + 'の') is not None else _zdesc(m.group('d')))),
        (r'バトル相手が(?P<c>赤|青|白|黒)', lambda m: {'vsF': {'color': [{'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[m.group('c')]]}}),
        (r'このユニットにつけたクラスカードが(?P<n>\d+)枚以上', lambda m: {'selfClassGE': int(m.group('n'))}),
        (r'あなたの(?:称号「(?P<t>[^」]+)」の)?テリトリーが開放(?:中|されている)?', lambda m: {'terrTitle': m.group('t')} if m.group('t') else {'terr': 1}),
        (r'あなたの(?:称号「(?P<t>[^」]+)」の)?テリトリー開放', lambda m: {'terrTitle': m.group('t')} if m.group('t') else {'terr': 1}),
        (r'あなたが「[^」]+」', lambda m: {'never': 1}),
        (r'このターン(?:に)?あなたが【スカウト】している', lambda m: {'scoutedTurn': 1}),
        (r'あなたのドロップゾーンに(?P<l>(?:⁅(?:スペード|ハート|ダイヤ|クラブ)⁆、?)+)がそれぞれ別に1枚以上ある', lambda m: {'dropAttrsEach': re.findall(r'スペード|ハート|ダイヤ|クラブ', m.group('l'))}),
        (r'あなたの、称号「(?P<a>[^」]+)」か(?:称号)?「(?P<b>[^」]+)」のテリトリー開放中', lambda m: {'terrTitleAny': [m.group('a'), m.group('b')]}),
        # 일반 장수 조건: 「あなたのリムーブゾーンのエースカードが2枚以上」「相手の表のエナジーが3枚以下」
        (r'(?P<w>あなた|相手)の(?P<z>ドロップゾーン|リムーブゾーン|手札|ライフ|表のエナジー|裏のエナジー|エナジー|他のユニット|ユニット)(?:の(?P<d>[^、。]*?))?が(?:合計)?(?P<n>\d+)枚(?P<c>以上|以下)?',
         lambda m: (lambda f: f is not None and {'zc': {'side': 'opp' if m.group('w') == '相手' else 'own', 'zone': m.group('z'), 'f': f, 'n': int(m.group('n')), 'cmp': 'le' if m.group('c') == '以下' else 'ge' if m.group('c') else 'eq'}})(_zdesc(m.group('d')))),
        (r'(?P<w>あなた|相手)の(?P<z>ドロップゾーン|リムーブゾーン|手札|エナジーゾーン|フィールド)に(?P<d>[^、。]+?)がある',
         lambda m: (lambda f: f is not None and {'zc': {'side': 'opp' if m.group('w') == '相手' else 'own', 'zone': m.group('z'), 'f': f, 'n': 1, 'cmp': 'ge'}})(_zdesc(m.group('d')))),
        (r'(?P<w>あなた|相手)の(?P<z>ドロップゾーン|リムーブゾーン|手札|エナジーゾーン|フィールド)に(?P<d>[^、。]+?)がない',
         lambda m: (lambda f: f is not None and {'zc': {'side': 'opp' if m.group('w') == '相手' else 'own', 'zone': m.group('z'), 'f': f, 'n': 0, 'cmp': 'le'}})(_zdesc(m.group('d')))),
        (r'あなたのテリトリーが無い|あなたのテリトリーが開放されていない', lambda m: {'terr': 0}),
        (r'(?P<d>[^、。]*?)' + NOUN + r'がいる', None),
        (r'(?P<d>[^、。]*?)' + NOUN + r'がいない', 'none'),
        (r'あなたの(?:エナジーゾーンに)?(?P<d>[^、。]*?)(?:エースカード|カード|エナジー)が(?:エナジーゾーンに)?ある', 'zone'),
        (r'このコマンドが手札からプレイされた', lambda m: {'fromHand': 1}),
        (r'このコマンドがトリガーでプレイされた', lambda m: {'fromTrigger': 1}),
    ]
    t = re.sub(r'(開放中|開放されている|レッドゾーン|している|がある|がいる|以上|以下)で(?=あなた|この|相手|対象)', r'\1かつ', t)
    parts = re.split(r'(?:で、|かつ、|、かつ|かつ)', t)
    out = []
    for p in parts:
        for rx, fn in C:
            m = re.fullmatch(rx, p)
            if m:
                if fn == 'count':
                    f = parse_desc(m.group('d'))
                    if f is None:
                        f = _zdesc(re.match(r'あなたのドロップゾーンの(.*?)が\d+枚', p).group(1))
                    if f is None:
                        return None
                    if 'ユニット' in p:
                        f['type'] = 'unit'
                    c = {'countGE': {'zone': 'drop', 'f': f, 'n': int(m.group('n'))}}
                    _LAST['cond'] = c
                    out.append(c)
                    break
                if fn == 'again':
                    prev = _LAST.get('cond')
                    if not prev:
                        return None
                    k, v = next(iter(prev.items()))
                    if isinstance(v, dict):
                        c = {k: {**v, 'n': int(m.group('n'))}}
                    elif k.endswith('GE') or k.endswith('LE'):
                        c = {k: int(m.group('n'))}
                    else:
                        return None
                    out.append(c)
                    break
                if fn == 'zone':
                    f = parse_desc(m.group('d'))
                    if f is None:
                        return None
                    if 'エース' in p:
                        f['ace'] = 1
                    out.append({'zoneHas': {'zone': 'energy', 'f': f}})
                    break
                if fn is None or fn == 'none':
                    f = parse_desc(m.group('d'))
                    if f is None:
                        return None
                    f = noun_filter(f, m.group('noun'))
                    out.append({'exists': f} if fn is None else {'none': f})
                else:
                    c = fn(m)
                    if not c:
                        return None
                    if any(k.endswith('GE') or k.endswith('LE') for k in c):
                        _LAST['cond'] = c
                    out.append(c)
                break
        else:
            return None
    return out


_MAY = re.compile(r'(?:て|で)(?:も)?よい')


def _has_choice(steps):
    for st in steps:
        if st.get('may') or st.get('upto'):
            return True
        if st.get('op') == 'if' and (_has_choice(st.get('then', [])) or _has_choice(st.get('else', []))):
            return True
    return False


def _mark_may(steps):
    st = steps[0]
    if st.get('op') == 'if' and st.get('then'):
        _mark_may(st['then'])
    else:
        st['may'] = 1


def parse_effects(t):
    """효과 문장들 -> 단계 목록 | None. 「~てよい」 문장은 실행 전에 쓸지 묻도록 may 표시"""
    t = re.sub(r'(ユニット)を全て', r'\1全てを', t)
    out = []
    sents = []
    for x in [x for x in t.split('。') if x.strip()]:
        if x.startswith('それが') and sents:
            sents[-1] += '。' + x
        else:
            sents.append(x)
    for sent in sents:
        n0 = len(out)
        if _parse_seq(sent, out) is None:
            return None
        steps = out[max(0, n0 - 1):] if len(out) <= n0 else out[n0:]
        if steps and _MAY.search(sent) and not _has_choice(steps):
            _mark_may(steps)
    return out


def _resolve_prev(seq, ctx):
    """'$prev'(앞의 수정 대상), '$prevop'(앞의 수정 종류)을 실제 값으로"""
    last = None
    for st in ctx:
        if st.get('op') in ('pow', 'hit', 'kw', 'dmg') and st.get('to') not in (None, '$prev'):
            last = st
    for st in seq:
        if st.get('op') == 'if':
            _resolve_prev(st.get('then', []), ctx + [x for x in seq if x is not st])
            _resolve_prev(st.get('else', []), ctx)
            continue
        if st.get('to') == '$prev':
            if not last:
                return False
            st['to'] = last['to']
            if st['op'] == '$prevop':
                st['op'] = last['op'] if last['op'] in ('pow', 'hit') else 'pow'
        if st.get('op') in ('pow', 'hit', 'kw', 'dmg'):
            last = st
    return True


_LEN = {'on': False}   # 못 읽은 부분을 '조건 묻기'·'처리 방법 고르기'로 바꿔서라도 자동 진행


def _infer_acts(frag):
    """못 읽은 효과 조각 -> [(표시 이름, 단계 목록)]: 글에 나온 동사로 그럴듯한 처리를 추려 사용자가 고르게"""
    acts = []
    fr = re.sub(r'\([^)]*\)', '', frag)
    mlook = re.search(r'山札を(?:上|下)から(\d+)枚(?:見|公開)', fr)
    if mlook:   # 덱 위 N장 보기 계열: 고른 카드를 어디로 보낼지
        k = int(mlook.group(1))
        rest = 'top' if re.search(r'残りを[^、。]*山札の上', fr) else 'drop' if re.search(r'残りを[^、。]*ドロップ', fr) else 'bottom'
        rk = {'top': '덱 맨 위', 'drop': '드롭 존', 'bottom': '덱 맨 아래'}[rest]
        if '手札に加え' in fr:
            acts.append((f'덱 위 {k}장을 보고 원하는 카드를 패에 넣기 (나머지 {rk})', [{'op': 'look', 'n': k, 'f': {}, 'k': k, 'to': 'hand', 'rest': rest}]))
        if '登場させ' in fr:
            acts.append((f'덱 위 {k}장을 보고 원하는 유닛을 등장시키기 (나머지 {rk})', [{'op': 'look', 'n': k, 'f': {'type': 'unit'}, 'k': k, 'to': 'field', 'rest': rest}]))
        if 'エナジー' in fr:
            acts.append((f'덱 위 {k}장을 보고 원하는 카드를 에너지로 (나머지 {rk})', [{'op': 'look', 'n': k, 'f': {}, 'k': k, 'to': 'energy', 'rest': rest}]))
        if 'ドロップ' in fr:
            acts.append((f'덱 위 {k}장을 보고 남길 카드를 고르기 (안 고른 카드는 드롭)', [{'op': 'look', 'n': k, 'f': {}, 'k': k, 'to': 'top', 'rest': 'drop'}]))
        if 'ライフ' in fr:
            acts.append((f'덱 위 1장을 라이프 맨 앞에', [{'op': 'lifeTop', 'n': 1}]))
        if not acts:
            acts.append((f'덱 위 {k}장을 보고 순서를 그대로 두기', [{'op': 'look', 'n': k, 'f': {}, 'k': 0, 'to': 'hand', 'rest': 'top'}]))
        return acts
    n = lambda rx, dflt=1: int(re.search(rx, fr).group(1)) if re.search(rx, fr) else dflt
    # 대상 묘사
    tg = None
    # 비용 조각 (「~ことで」): 내지 않으면 이후 효과 없음
    if re.search(r'ことで$', fr):
        cacts = []
        mm = re.search(r'手札[^、。]*?を(\d+)枚(?:ずつ)?ドロップ', fr)
        if mm:
            cacts.append((f'비용으로 패 {mm.group(1)}장 버리기', [{'op': 'discard', 'n': int(mm.group(1))}]))
        mm = re.search(r'エナジーを(\d+)枚裏に', fr)
        if mm:
            cacts.append((f'비용으로 에너지 {mm.group(1)}장 뒷면으로', [{'op': 'flipEnergy', 'n': int(mm.group(1))}]))
        mm = re.search(r'エナジーを(\d+)枚レスト', fr)
        if mm:
            cacts.append((f'비용으로 에너지 {mm.group(1)}장 레스트', [{'op': 'payEnergy', 'n': int(mm.group(1))}]))
        if re.search(r'テリトリーを閉じ', fr):
            cacts.append(('비용으로 내 테리토리 닫기', [{'op': 'closeTerr'}]))
        if re.search(r'このユニットをリムーブ', fr):
            cacts.append(('비용으로 이 유닛 리무브', [{'op': 'remove', 'to': 'self'}]))
        if re.search(r'このユニットをレスト', fr):
            cacts.append(('비용으로 이 유닛 레스트', [{'op': 'rest', 'to': 'self'}]))
        if re.search(r'ライフの先頭をドロップ', fr):
            cacts.append(('비용으로 내 라이프 맨 앞 드롭', [{'op': 'lifeDrop', 'n': 1}]))
        mm = re.search(r'山札を上から(\d+)枚(?:ドロップ|リムーブ)', fr)
        if mm:
            cacts.append((f'비용으로 덱 위 {mm.group(1)}장 {"리무브" if "リムーブ" in fr else "드롭"}', [{'op': 'mill', 'n': int(mm.group(1))}]))
        return [(a, b, 'cost') for a, b in cacts]
    m = re.search(r'(?P<d>[^、。]*?)(?P<noun>ユニットカード|ユニット|エースカード|エース|カード|⁅[^⁆]+⁆|ハート|スペード|ダイヤ|クラブ)(?:である)?(?P<en>のエナジー|エナジー)?を(?P<n>\d+)枚(?P<upto>まで)?対象と', fr)
    if m:
        dd = re.sub(r'^.*?(あなたの|相手の)', r'\1', m.group('d'))
        zone = 'energy' if m.group('en') or 'エナジー' in dd else 'drop' if 'ドロップゾーン' in dd else None
        dd2 = re.sub(r'^(あなたの|相手の)(?:ドロップゾーンの|エナジーゾーンの)?', r'\1', dd)
        f = parse_desc(dd2) or ({'side': 'opp'} if '相手の' in dd else {'side': 'own'} if 'あなたの' in dd else {})
        noun = m.group('noun')
        if noun.startswith('⁅') or noun in ('ハート', 'スペード', 'ダイヤ', 'クラブ'):
            f = dict(f, attr=[noun.strip('⁅⁆')]) if not noun.endswith('アイコン⁆') else f
            noun = 'カード'
        if zone:
            f = {k2: v for k2, v in f.items() if k2 != 'type'}
            f = noun_filter(f, noun) if noun != 'エナジー' else f
        tg = {'op': 'tgt', 'f': noun_filter(f, noun) if not zone else f, 'n': int(m.group('n')), 'upto': 1, **({'zone': zone} if zone else {})}
    elif 'このユニット' in fr and '対象' not in fr:
        tg = 'self'
    elif '対象' in fr or 'そのユニット' in fr:
        tg = 'T'
    else:
        tg = {'op': 'tgt', 'f': {'type': 'unit', **({'side': 'opp'} if '相手の' in fr else {'side': 'own'} if 'あなたの' in fr else {})}, 'n': 1, 'upto': 1}
    mall = re.search(r'(?P<d>[^。]*?)(?P<noun>ユニット|エース)全て(?:を|に|の)', fr)
    if mall and not (isinstance(tg, dict) and tg.get('op') == 'tgt' and m):
        dd = re.sub(r'^.*?(あなたの|相手の)、?', r'\1', mall.group('d')).replace('、', '')
        f = parse_desc(dd) if parse_desc(dd) is not None else ({'side': 'opp'} if '相手の' in dd else {'side': 'own'} if 'あなたの' in dd else {})
        tg = {'all': noun_filter(f, mall.group('noun'))}
    zn = {'energy': '에너지', 'drop': '드롭 존의 카드'}.get(tg.get('zone') if isinstance(tg, dict) else None, '유닛')
    side_ko = lambda f: '상대 ' if f.get('side') == 'opp' else '내 ' if f.get('side') == 'own' else ''
    who = '이 유닛' if tg == 'self' else '대상' if tg == 'T' else f"조건에 맞는 {side_ko(tg['all'])}유닛 전부" if 'all' in tg else f"{side_ko(tg.get('f', {}))}{zn} 1장" if tg['n'] == 1 else f"{side_ko(tg.get('f', {}))}{zn} {tg['n']}장까지"
    def unit(label, st):
        if tg == 'self':
            acts.append((f'{who}{label}', [dict(st, to='self')]))
        elif tg == 'T':
            acts.append((f'{who}{label}', [dict(st, to='T')]))
        elif 'all' in tg:
            acts.append((f'{who}{label.replace("하기", "")}{"하기" if label.endswith("하기") else ""}', [dict(st, to={'all': tg['all']})]))
        else:
            acts.append((f'{who}을 골라{label}', [dict(tg), dict(st, to='T')]))
    if re.search(r'手札に戻', fr):
        unit(' 패로 되돌리기', {'op': 'bounce'})
    if re.search(r'(?:ユニット|対象|それ|エース)[^、。]*?をドロップ(?:させ|する|し)|ドロップさせ', fr) and not re.search(r'手札を\d+枚ドロップ|ライフの先頭をドロップ|山札を上から', fr):
        unit(' 드롭시키기', {'op': 'drop'})
    m = re.search(r'(\d+)ダメージ', fr)
    if m:
        unit(f' {m.group(1)} 데미지 주기', {'op': 'dmg', 'n': int(m.group(1))})
    m = re.search(r'パワーを([+-]\d+)', fr)
    if m:
        unit(f' 파워 {m.group(1)} (이번 턴)', {'op': 'pow', 'n': int(m.group(1))})
    m = re.search(r'ヒットを([+-]\d+)', fr)
    if m:
        unit(f' 히트 {m.group(1)} (이번 턴)', {'op': 'hit', 'n': int(m.group(1))})
    if re.search(r'スタンド(?:する|させ|し|で)', fr) and 'スタンドで登場' not in fr:
        unit(' 스탠드하기', {'op': 'stand'})
    if re.search(r'をレスト(?:する|させ|し)', fr):
        unit(' 레스트하기', {'op': 'rest'})
    if re.search(r'山札の下に置', fr) and not re.search(r'残りを[^、。]*山札の下', fr):
        unit(' 덱 맨 아래에 놓기', {'op': 'deckBottom'})
    if re.search(r'山札の上に置', fr) and not re.search(r'残りを[^、。]*山札の上', fr):
        unit(' 덱 맨 위에 놓기', {'op': 'deckTop'})
    if re.search(r'(?:ユニット|対象|それ)[^、。]*?をエナジーゾーンに置', fr):
        unit(' 에너지 존에 놓기', {'op': 'energy'})
    if re.search(r'(?:ユニット|対象|それ)[^、。]*?をリムーブ', fr):
        unit(' 리무브하기', {'op': 'remove'})
    m = re.search(r'(\d+)枚引', fr)
    if m:
        acts.append((f'{m.group(1)}장 뽑기', [{'op': 'draw', 'n': int(m.group(1))}]))
    if re.search(r'手札[^。]*?登場させ', fr):
        acts.append(('패에서 유닛 1장 등장시키기', [{'op': 'pick', 'from': 'hand', 'to': 'field', 'f': {'type': 'unit'}, 'n': 1, 'upto': 1}]))
    if re.search(r'ドロップゾーン[^。]*?登場させ', fr):
        acts.append(('드롭 존에서 유닛 1장 등장시키기', [{'op': 'pick', 'from': 'drop', 'to': 'field', 'f': {'type': 'unit'}, 'n': 1, 'upto': 1}]))
    if re.search(r'エナジー[^。]*?登場させ', fr) and 'ドロップゾーン' not in fr:
        acts.append(('에너지에서 유닛 1장 등장시키기', [{'op': 'pick', 'from': 'energy', 'to': 'field', 'f': {'type': 'unit'}, 'n': 1, 'upto': 1}]))
    if re.search(r'ドロップゾーン[^。]*?手札に加え', fr):
        acts.append(('드롭 존에서 카드 1장 패에 넣기', [{'op': 'pick', 'from': 'drop', 'to': 'hand', 'f': {}, 'n': 1, 'upto': 1}]))
    if re.search(r'山札[^。]*?(?:見|公開)[^。]*?手札に加え', fr):
        k = n(r'上から(\d+)枚', 3)
        acts.append((f'덱 위 {k}장을 보고 1장 패에 넣기 (나머지 덱 아래)', [{'op': 'look', 'n': k, 'f': {}, 'k': 1, 'to': 'hand', 'rest': 'bottom'}]))
    if re.search(r'ライフ[^。]*?手札に加え', fr):
        acts.append(('라이프 맨 앞 1장 패에 넣기', [{'op': 'lifeHand', 'n': 1}]))
    if re.search(r'手札を(\d+)枚ドロップ', fr):
        k = n(r'手札を(\d+)枚ドロップ')
        acts.append((f'패 {k}장 버리기', [{'op': 'discard', 'n': k}]))
    if re.search(r'山札を上から(\d+)枚ドロップ', fr):
        k = n(r'山札を上から(\d+)枚ドロップ')
        acts.append((f'덱 위 {k}장 드롭', [{'op': 'mill', 'n': k}]))
    if re.search(r'ライフの先頭をドロップ', fr):
        w = 'opp' if re.search(r'相手のライフ|相手は自身のライフ', fr) else 'me'
        acts.append(((('상대 ' if w == 'opp' else '내 ') + '라이프 맨 앞 드롭'), [{'op': 'lifeDrop', 'n': 1, **({'who': 'opp'} if w == 'opp' else {})}]))
    if re.search(r'上から(\d+)枚[^。]*?ライフ', fr):
        k = n(r'上から(\d+)枚')
        acts.append((f'덱 위 {k}장을 라이프 맨 앞에', [{'op': 'lifeTop', 'n': k}]))
    if re.search(r'上から(\d+)枚[^。]*?エナジー', fr):
        k = n(r'上から(\d+)枚')
        acts.append((f'덱 위 {k}장을 에너지로', [{'op': 'deckEnergy', 'n': k}]))
    if re.search(r'ライフの先頭をエナジー', fr):
        acts.append(('라이프 맨 앞을 에너지로', [{'op': 'lifeEnergy', 'n': 1}]))
    if re.search(r'(?:ユニット|対象|それ|カード)[^、。]*?をドロップゾーンに置', fr):
        unit(' 드롭 존에 놓기', {'op': 'drop'})
    if isinstance(tg, dict) and tg.get('zone') and re.search(r'登場させ', fr) and not any(l.endswith('등장시키기') for l, _ in acts):
        unit(' 등장시키기', {'op': 'summonRested' if 'レストで登場' in fr else 'summon'})
    if isinstance(tg, dict) and tg.get('zone') and re.search(r'手札に(?:加え|戻)', fr):
        unit(' 패에 넣기', {'op': 'bounce'})
    mm = re.search(r'手札の(?P<d>[^、。]*?)を(?P<n>\d+)枚公開', fr)
    if mm:
        acts.append((f'패에서 {mm.group("n")}장 공개하기', [{'op': 'revealHand', 'n': int(mm.group('n')), 'f': parse_desc(mm.group('d')) or {}}]))
    if re.search(r'テリトリーを閉じ', fr):
        acts.append(('내 테리토리 닫기', [{'op': 'closeTerr'}]))
    if re.search(r'追加の1ターンを行う', fr):
        acts.append(('추가 턴 진행', [{'op': 'extraTurn'}]))
    mm = re.search(r'手札が(\d+)枚になるように引', fr)
    if mm:
        acts.append((f'패가 {mm.group(1)}장이 되도록 뽑기', [{'op': 'drawTo', 'n': int(mm.group(1))}]))
    if re.search(r'山札をシャッフル', fr) and not re.search(r'上から\d+枚', fr):
        acts.append(('덱 섞기', [{'op': 'shuffle'}]))
    return acts


def _guide(frag):
    """못 읽은 조각 -> 처리 방법을 고르는 단계 (추정할 처리가 없으면 None)"""
    acts = _infer_acts(frag)
    if not acts:
        return None
    if any(len(a) > 2 for a in acts):   # 비용: 안 내면 이후 효과 없음
        return {'op': 'choose', 'opts': [a[1] for a in acts] + [[{'op': 'stop'}]], 'labels': [a[0] for a in acts] + ['비용을 내지 않음 (효과 없음)'], 'guide': frag,
                'text': '이 능력의 비용을 자동으로 읽지 못했어요. 카드 문구대로 낼 비용을 고르세요'}
    labels = [a[0] for a in acts] + ['아무것도 하지 않음']
    return {'op': 'choose', 'opts': [a[1] for a in acts] + [[]], 'labels': labels, 'guide': frag,
            'text': '이 부분은 자동으로 읽지 못했어요. 카드 문구대로 처리할 방법을 고르세요'}


def _parse_seq(t, steps=None):
    """효과 문장 -> 단계 목록 | None (steps가 있으면 거기에 이어 붙임: '代わりに'가 앞 문장의 단계를 바꿀 수 있게)"""
    steps = [] if steps is None else steps
    t = t.strip()
    while t:
        t = t.lstrip('。、 ')
        if not t:
            break
        m = re.match(r'(?:そうしたら|つけたら|登場させたら|置いたら|戻したら|入れ替えたら|公開したら)、(?:その後、)?', t)
        if m:
            sub = []
            if _parse_seq(t[m.end():], sub) is None:
                return None
            steps.append({'op': 'if', 'c': [{'did': 1}], 'then': sub})
            break
        m = re.match(r'その後、|さらに(?![+-])', t)
        if m:
            t = t[m.end():]
            continue
        # 「~1枚につき、」: 다음 효과의 수치를 개수만큼 곱함
        m = re.match(r'(?P<w>あなたの|相手の)(?P<z>手札|エナジー|ドロップゾーン(?:のカード)?|ユニット|エナジーの色|リムーブゾーン)(?P<k>\d+)(?:枚|つ)につき、|対象のヒット(?P<h>\d+)につき、', t)
        if m:
            sub = []
            j = t.find('。')
            inner, rest = (t[m.end():], '') if j < 0 else (t[m.end():j], t[j + 1:])
            if _parse_seq(inner, sub) is None:
                return None
            per = {'tHit': 1} if m.group('h') else {'side': 'opp' if m.group('w') == '相手の' else 'own', 'zone': {'手札': 'hand', 'エナジー': 'energy', 'ユニット': 'field', 'エナジーの色': 'colors', 'リムーブゾーン': 'remove'}.get(m.group('z'), 'drop'), 'k': int(m.group('k'))}
            for st in sub:
                if st.get('op') not in ('tgt', 'if', 'choose'):
                    st['per'] = per
            steps.extend(sub)
            t = rest
            continue
        # 비용을 내면 이어서: 「(비용)ことで、」
        m = re.match(r'(?P<c>[^。、]*(?:、[^。、]*)?)ことで、', t)
        if m:
            cost = parse_cost(m.group('c'), None)
            if cost:
                steps.append({'op': 'confirm', 'text': '비용을 내고 효과를 쓸까요?', 'cost': 1, 'need': cost})
                steps.extend(cost)
                t = t[m.end():]
                continue
        # 조건 분기: 「Xなら、」
        m = re.match(r'(?P<c>[^。]*?)(?:なら|ならば|場合|(?<!そうし)たら)、', t)
        if m and not re.search(r'対象と|ダメージ|を\d+枚', m.group('c')):
            c = parse_cond(m.group('c'))
            ask = c is None and _LEN['on'] and not re.search(r'時、|(?:し|き|せ|け|い)、', m.group('c'))
            if ask:
                c = [{'ask': m.group('c')}]
            if c is not None:
                rest = re.sub(r'^その後、', '', t[m.end():])
                # 같은 문장 끝(。)까지를 조건 안쪽으로
                j = rest.find('。')
                inner, t = (rest, '') if j < 0 else (rest[:j], rest[j + 1:])
                mrep = re.fullmatch(r'手札に加える代わりに(?P<r>レストで)?登場させてよい', inner)
                if mrep and not ask and steps and steps[-1].get('op') in ('look', 'pick') and steps[-1].get('to') == 'hand':
                    prev = steps.pop()
                    alt2 = dict(prev, to='field', **({'rested': 1} if mrep.group('r') else {}))
                    steps.append({'op': 'if', 'c': c, 'then': [{'op': 'confirm', 'text': '패에 넣는 대신 등장시킬까요?', 'alt': 1, 'no': [prev]}, alt2], 'else': [prev]})
                    continue
                alt = inner.startswith('代わりに')
                sub = parse_effects(inner[4:] if alt else inner)
                if sub is None:
                    return None
                _resolve_prev(sub, steps)
                if alt:
                    if not steps:
                        return None
                    prev = steps.pop()
                    steps.append({'op': 'askIf', 'jp': m.group('c'), 'then': sub, 'else': [prev]} if ask else {'op': 'if', 'c': c, 'then': sub, 'else': [prev]})
                else:
                    steps.append({'op': 'askIf', 'jp': m.group('c'), 'then': sub} if ask else {'op': 'if', 'c': c, 'then': sub})
                continue
        for rx, fn in EFF:
            m = rx.match(t)
            if m:
                r = fn(m)
                if r:
                    r = r if isinstance(r, list) else [r]
                    _resolve_prev(r, steps)   # 못 찾으면 바깥 문맥에서 다시
                    steps.extend(r)
                    t = t[m.end():]
                    break
        else:
            _FAIL['at'] = t
            if not _LEN['on']:
                return None
            # 못 읽은 조각: 뒤쪽에서 읽을 수 있는 곳까지만 잘라 '처리 방법 고르기'로
            j = t.find('。')
            seg = t if j < 0 else t[:j]
            cut = None
            for k in [i for i, ch in enumerate(seg) if ch == '、']:
                _LEN['on'] = False
                ok = _parse_seq(seg[k + 1:], []) is not None
                _LEN['on'] = True
                if ok:
                    cut = k
                    break
            frag = seg if cut is None else seg[:cut]
            g = _guide(frag)
            if g is None and cut is not None:
                frag = seg
                g = _guide(frag)
            if g is None:
                return None
            if _MAY.search(frag):
                g['labels'][-1] = '쓰지 않음'
            steps.append(g)
            t = t[len(frag):]
    return steps


# ---------- 발동 시점 ----------
TRIGGERS = [
    (r'このユニットが手札から登場した時', ('enter', 'self', {'fromHand': 1})),
    (r'このユニットが(?:登場した|登場)時|このユニットの登場時', ('enter', 'self', None)),
    (r'このユニットがフィールドからドロップした時', ('leave', 'self', None)),
    (r'このユニットがアタックしてバトルに勝利した時', ('win', 'self', None)),
    (r'このユニットが(?:アタックした|アタック)時|このユニットのアタック時', ('attack', 'self', None)),
    (r'このユニットがバトルする時', ('battle', 'self', None)),
    (r'このユニットがバトルに勝利した時', ('win', 'self', {'any': 1})),
    (r'あなたのユニットがアタックしてバトルに勝利した時', ('win', 'own', None)),
    (r'あなたのエースがアタックした時', ('attack', 'ownAce', None)),
    (r'あなたのユニットがアタックした時', ('attack', 'own', None)),
    (r'あなたのユニットが登場した時', ('enter', 'own', None)),
    (r'あなたのユニットがフィールドからドロップした時', ('leave', 'own', None)),
    (r'相手のユニットが登場した時', ('enter', 'opp', None)),
    (r'相手のユニットがフィールドからドロップした時', ('leave', 'opp', None)),
    (r'あなたのターン開始時', ('turnStart', 'me', None)),
    (r'あなたのメインフェイズ開始時', ('mainStart', 'me', None)),
    (r'あなたのアタックフェイズ開始時', ('attackStart', 'me', None)),
    (r'あなたのエンドフェイズ開始時', ('endStart', 'me', None)),
    (r'相手のターン開始時', ('turnStart', 'opp', None)),
    (r'相手のアタックフェイズ開始時', ('attackStart', 'opp', None)),
    (r'相手のエンドフェイズ開始時', ('endStart', 'opp', None)),
    (r'このテリトリーが開放された時', ('terrOpen', 'me', None)),
    (r'このユニットが卒業した時', ('graduate', 'self', None)),
    (r'あなたのユニットが【ブライト】した時', ('bright', 'own', None)),
    (r'このユニットが【コスプレ】で登場した時', ('enter', 'self', {'cos': 1})),
    (r'あなたの他のユニットが【コスプレ】で登場した時', ('enter', 'own', {'cos': 1, 'evNotSelf': 1})),
    (r'あなたのユニットが【コスプレ】で登場した時', ('enter', 'own', {'cos': 1})),
    (r'エンドフェイズ以外にあなたのユニットが【コスプレ】で登場した時', ('enter', 'own', {'cos': 1, 'notEnd': 1})),
    (r'このユニットが【コスプレ】で手札に戻った時', ('cosReturn', 'self', None)),
    (r'このユニットにクラスカードがついた時', ('classAttach', 'self', None)),
    (r'このユニットがレストで登場した時', ('enter', 'self', {'enteredRested': 1})),
    (r'このユニットでテリトリーを開放した時', ('terrOpen', 'self', None)),
    (r'このユニットが効果で登場した時', ('enter', 'self', {'notPlayed': 1})),
    (r'このユニットがエナジーゾーンから登場した時', ('enter', 'self', {'fromEnergy': 1})),
    (r'このカードを【ブライト】でドロップした時|このカードが【ブライト】で手札からドロップされた時', ('brightDrop', 'self', None)),
    (r'あなたのエースがフィールドからドロップした時', ('leave', 'ownAce', None)),
    (r'このユニットがフィールドからドロップされた時', ('leave', 'self', None)),
    (r'このカードがフィールドからリムーブされた時', ('removed', 'self', None)),
    (r'あなたのユニットが卒業した時', ('graduate', 'own', None)),
    (r'このユニットがブロックした時', ('block', 'self', None)),
    (r'あなたの他のユニットがブロックしてバトルする時', ('block', 'own', {'evNotSelf': 1})),
    (r'このユニットが【(?P<n>[^】]+)】を着た時', ('dressed', 'self', None)),
    (r'このユニットが【ブライト】してバトルに勝利した時', ('win', 'self', {'brightWin': 1})),
    (r'このユニットが相手ターンにバトルする時', ('battle', 'self', {'oppTurnX': 1})),
    (r'ダメージでこのカードがライフからドロップした時', ('lifeDmgDrop', 'self', None)),
    (r'あなたのユニットがバトルする時', ('battle', 'own', None)),
    (r'あなたのユニットがアタックしたターンのエンドフェイズ開始時', ('endStart', 'me', {'attackedTurn': 1})),
    (r'このカードがどこからでもリムーブされた時', ('removed', 'self', None)),
    (r'(?:あなたのターンに)?あなたがカードをフィールドに伏せた時', ('setCard', 'me', None)),
    (r'フィールドに伏せられたこのカードがドロップされた時', ('setDrop', 'self', None)),
    (r'あなたのエースが【マギア】でエナジーを裏にした時', ('magiaFlip', 'ownAce', None)),
    (r'このカードを【夢を見ない】で公開してドロップした時', ('yumemiDrop', 'self', None)),
    (r'このユニットの【CAD】でコマンドを解決した時', ('cad', 'self', None)),
    (r'あなたが【CAD】でコマンドを解決した時', ('cad', 'own', None)),
    (r'(?:あなたのターンに)?あなたがコマンドを解決した時', ('cmdResolved', 'me', None)),
    (r'相手が効果でカードを引いた時', ('effDraw', 'opp', None)),
    (r'あなたのユニットにクラスカードがついた時', ('classAttach', 'own', None)),
    (r'(?:あなたが)?スキルコストで、?手札かライフ(?:の|から)このカードをドロップした時', ('skillDrop', 'self', None)),
    (r'(?:あなたのターン中、)?あなたのユニットが【スキル】を発動した時', ('skillUsed', 'own', None)),
    (r'このユニットがレストした時', ('rest', 'self', None)),
    (r'ユニットにつけたこのカードがドロップした時', ('attDrop', 'self', None)),
    (r'(?P<w>あなた|相手)の(?P<d>[^、。]*?)ユニットがアタックした時', ('attack', 'desc', None)),
    (r'(?P<w>あなた|相手)の(?P<d>[^、。]+?)ユニットが(?:フィールドから)?ドロップした時', ('leave', 'desc', None)),
    (r'(?P<w>あなた|相手)の(?P<d>[^、。]+?)ユニットが登場した時', ('enter', 'desc', None)),
    (r'このユニットが【ブライト】した時', ('bright', 'self', None)),
    (r'このユニットが総コスト(?P<n>\d+)以下のユニットとバトルする時', ('battle', 'self', 'vsCostLE')),
    (r'このユニットが(?P<d>[^、。]+?)ユニットとバトルする時', ('battle', 'self', 'vsDesc')),
    (r'バトル中のこのユニットがフィールドからドロップした時|このユニットがバトル中にフィールドからドロップした時', ('leave', 'self', {'inBattle': 1})),
    (r'このユニットのアタック終了時', ('attackEnd', 'self', None)),
    (r'いずれかのアタックフェイズに相手のユニットが登場した時', ('enter', 'opp', {'attackPhase': 1})),
]


def _approx_trigger(h):
    """정확히 못 읽은 발동 시점 -> 가장 가까운 시점 (on, src, conds) — 실제로 해당하는지는 그때 플레이어에게 물음"""
    conds = []
    h = re.sub(r'」テリトリー', '」のテリトリー', h)
    m = re.match(r'あなたの(?:称号「(?P<ti>[^」]+)」の)?テリトリー(?:が開放されていて|開放中で|が開放中で|開放中に|が開放中に|開放中)、?', h)
    if m:
        conds.append({'terrTitle': m.group('ti')} if m.group('ti') else {'terr': 1})
        h = h[m.end():]
        tr = parse_trigger(h)
        if tr:
            return tr[0], tr[1], conds + tr[2], False
    side = 'self' if re.search(r'このユニット|このカード', h) else 'own' if h.startswith('あなた') else 'opp' if h.startswith('相手') else None
    who = 'opp' if h.startswith('相手') else 'me'
    fam = None
    if 'エンドフェイズ開始時' in h:
        fam = ('endStart', who)
    elif 'アタックフェイズ開始時' in h:
        fam = ('attackStart', who)
    elif 'メインフェイズ開始時' in h:
        fam = ('mainStart', who)
    elif 'ターン開始時' in h:
        fam = ('turnStart', who)
    elif side and 'バトルに勝利した時' in h:
        fam = ('win', side)
    elif side and 'バトルに負けた時' in h:
        fam = ('lose', side)
    elif side and re.search(r'バトルする時', h):
        fam = ('battle', side)
    elif side and re.search(r'ユニット[^、。]*?ドロップ(?:した|された)時|ユニットがバトルでドロップした時', h) and '手札' not in h:
        fam = ('leave', side)
    elif side and re.search(r'登場(?:した)?時', h):
        fam = ('enter', side)
    elif side and re.search(r'ブロックした時', h):
        fam = ('block', side)
    elif side and re.search(r'【ブライト】した時', h):
        fam = ('bright', side)
    elif side and re.search(r'アタック(?:した)?時', h):
        fam = ('attack', side)
    if not fam:
        return None
    return fam[0], fam[1], conds, True


def parse_trigger(t):
    """'あなたのテリトリー開放中にこのユニットが登場した時' -> (on, src, conds) | None"""
    conds = []
    t = re.sub(r'」テリトリー', '」のテリトリー', t)
    if t.startswith('あなたのターンに'):
        conds.append({'myTurn': 1})
        t = t[len('あなたのターンに'):]
    m = re.match(r'(?P<c>あなたの、称号「[^」]+」か(?:称号)?「[^」]+」のテリトリー開放中|あなたの(?:称号「[^」]+」の)?テリトリー(?:開放中|が開放されていて)|あなたのライフがレッドゾーンで)(?:に|、|で、|で)?', t)
    if m:
        c = parse_cond(m.group('c').replace('が開放されていて', '開放中').rstrip('で'))
        if c is None:
            return None
        conds += c
        t = t[m.end():]
    mw = re.match(r'、?((?:【[^】]+】か?)+)を着ている(?=このユニット)', t)
    if mw:
        conds.append({'wearing': re.findall(r'【([^】]+)】', mw.group(1))})
        t = t[mw.end():]
    for rx, (on, src, extra) in TRIGGERS:
        m = re.fullmatch(rx, t)
        if m:
            if extra == 'vsCostLE':
                conds.append({'vsCostLE': int(m.group('n'))})
                extra = None
            if extra == 'vsDesc':
                f = parse_desc(m.group('d'))
                if f is None:
                    continue
                conds.append({'vsF': f})
                extra = None
            if extra and 'inBattle' in extra:
                conds.append(extra)
                extra = None
            if src == 'desc':
                f = parse_desc(m.group('d'))
                if f is None:
                    continue
                src = 'own' if m.group('w') == 'あなた' else 'opp'
                conds.append({'evF': f})
            if extra and 'brightWin' in extra:
                conds.append({'selfBrighted': 1})
                extra = {'any': 1}
            if extra and 'oppTurnX' in extra:
                conds.append({'oppTurn': 1})
                extra = None
            if extra and ('notPlayed' in extra or 'fromEnergy' in extra or 'evNotSelf' in extra):
                conds.append(extra)
                extra = None
            if extra and ('enteredRested' in extra or 'attackedTurn' in extra):
                conds.append(extra)
                extra = None
            if extra and 'cos' in extra:
                conds.append(extra)
                extra = None
            elif extra and ('fromHand' in extra or 'attackPhase' in extra):
                conds.append(extra)
            return on, src, conds, extra
    return None


# ---------- 비용 (ことで) ----------
def parse_cost(t, skill):
    C = [
        (r'【スキル】(?:を)?発動(?:する|すること)?', lambda m: skill),
        (r'あなたのライフの先頭をドロップする', lambda m: [{'op': 'lifeDrop', 'n': 1}]),
        (r'あなたのエナジー(?:の中)?から、(?P<l>(?:[黒青白赤]\d+枚、?)+)(?:を)?(?P<h>レスト|ドロップ)する', lambda m: [{'op': 'payEnergyMulti', 'colors': {{'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[c]: int(n) for c, n in re.findall(r'([黒青白赤])(\d+)枚', m.group('l'))}, 'how': 'rest' if m.group('h') == 'レスト' else 'drop'}]),
        (r'あなたの(?P<c>赤|青|白|黒)のエナジー(?:を)?(?P<n>\d+)枚(?:を)?ドロップする', lambda m: [{'op': 'payEnergy', 'n': int(m.group('n')), 'color': {'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[m.group('c')], 'how': 'drop'}]),
        (r'あなたの白と赤のエナジーをそれぞれ1枚ずつドロップ(?:する|してよい)', lambda m: [{'op': 'payEnergyMulti', 'colors': {'white': 1, 'red': 1}, 'how': 'drop'}]),
        (r'あなたの、?(?P<d>[^。]*?)のエナジーを(?:合計)?(?P<n>\d+)枚レストする', 'edesc'),
        (r'あなたのドロップゾーンのクラスカードを(?P<n>\d+)枚取り除く', lambda m: [{'op': 'classRemove', 'n': int(m.group('n'))}]),
        (r'このユニットをドロップさせる', lambda m: [{'op': 'drop', 'to': 'self'}]),
        (r'次のエンドフェイズ開始時、(?:これ|このユニット)をドロップさせる', lambda m: [{'op': 'delay', 'at': 'endStart', 'do': [{'op': 'drop', 'to': 'self'}]}]),
        (r'あなたの(?P<c>赤|青|白|黒)?の?エナジーを(?P<n>\d+)枚レストする', lambda m: [{'op': 'payEnergy', 'n': int(m.group('n')), **({'color': {'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[m.group('c')]} if m.group('c') else {})}]),
        (r'あなたの手札を(?P<n>\d+)枚ドロップする', lambda m: [{'op': 'discard', 'n': int(m.group('n'))}]),
        (r'あなたの手札の(?P<d>[^。]*?)' + NOUN + r'?を(?P<n>\d+)枚ドロップする', 'desc'),
        (r'あなたの⁅(?P<a>ハート|スペード|ダイヤ|クラブ)⁆のエナジーを(?P<n>\d+)枚レストする', lambda m: [{'op': 'payEnergy', 'n': int(m.group('n')), 'attr': m.group('a')}]),
        (r'あなたのエナジーを(?P<n>\d+)枚レストする', lambda m: [{'op': 'payEnergy', 'n': int(m.group('n'))}]),
        (r'このユニットをレストする', lambda m: [{'op': 'rest', 'to': 'self'}]),
        (r'このユニットをドロップする', lambda m: [{'op': 'drop', 'to': 'self'}]),
        (r'このユニットを手札に戻す', lambda m: [{'op': 'bounce', 'to': 'self'}]),
        (r'このユニットを山札の下に置く', lambda m: [{'op': 'deckBottom', 'to': 'self'}]),
        (r'このユニットをリムーブする', lambda m: [{'op': 'remove', 'to': 'self'}]),
        (r'あなたのライフの先頭を(?:ドロップ|手札に加え)る?', lambda m: [{'op': 'lifeHand', 'n': 1}]),
    ]
    for rx, fn in C:
        m = re.fullmatch(rx, t)
        if m:
            if fn == 'edesc':
                f = parse_desc(m.group('d') + 'の')
                if f is None:
                    return None
                return [{'op': 'payEnergy', 'n': int(m.group('n')), 'f': f, 'inCost': 1}]
            if fn == 'desc':
                f = parse_desc(m.group('d'))
                if f is None:
                    return None
                if m.group('noun'):
                    noun_filter(f, m.group('noun'))
                return [{'op': 'discard', 'n': int(m.group('n')), 'f': f, 'inCost': 1}]
            r = fn(m)
            return r and [{**x, 'inCost': 1} for x in r]
    return None


def parse_skill(line):
    """【スキル】… 줄 -> 비용 단계 | None"""
    m = re.fullmatch(r'【スキル】(.+?)。?', N(line))
    if not m:
        return None
    body = m.group(1)
    parts = re.split(r'か、|か(?=あなたの)', body)
    if len(parts) > 1:
        return None   # 'A か B' 선택형 비용은 아직 수동
    return parse_cost(body.rstrip('。'), None)


# ---------- 상시 능력 ----------
def parse_perm(t):
    """⁅永続⁆ 본문 -> {if:[...], do:[pow/hit/kw ...]} | None"""
    t = re.sub(r'(\d+)億', lambda m: str(int(m.group(1)) * 100000000), t)
    t = re.sub(r'(\d+)万', lambda m: str(int(m.group(1)) * 10000), t)
    t = t.replace('。』', '』')
    t = re.sub(r'各ターン1回まで、(このユニットはレストしていてもアタックできる)', r'\1', t)
    t = re.sub(r'(を[+-]\d+)し、', r'\1。', t)
    t = re.sub(r'(を[+-]\d+)、(?=相手は|このユニットは|あなたは|あなたの|パワーを\d+倍)', r'\1。', t)
    # 규칙 문장
    R = [(r'あなたがドローフェイズにカードを引く際、自分の手札が1枚以下なら、1枚引く代わりに(?:あなたの)?手札が3枚になるように引(?:く|いてよい)', 'drawTo3'),
         (r'あなたのドロップゾーンのカードは他の領域に移動できない', 'dropLock')]
    pre_rules = []
    for rx, rule in R:
        if re.search(rx, t):
            pre_rules.append({'op': 'rule', 'rule': rule})
            t = re.sub(rx + r'。?', '', t).strip('。')
    if pre_rules and not t:
        return {'if': [], 'do': pre_rules}
    conds = []
    for _ in range(3):
        m = re.match(r'(?P<c>.+?)(?:なら|ていたら|中で|中|時|際)、', t)
        if not m:
            break
        c = parse_cond(m.group('c').rstrip('で') + ('ている' if m.group(0).endswith('ていたら、') else ''))
        if c is None:
            break
        conds += c
        t = t[m.end():]
    out = list(pre_rules)
    last = {}
    m0 = re.match(r'クラスカード(?:を持つ|がついた|がついている)(?=このユニット)', t)
    if m0:
        conds = conds + [{'selfHasClass': 1}]
        t = t[m0.end():]
    for sent in [x for x in t.split('。') if x]:
        n0 = len(out)
        per = None
        sc = None
        msc = re.match(r'(?P<c>[^、。]+?)(?:なら|ていたら)、(?:さらに)?', sent)
        if msc:
            cc = parse_cond(msc.group('c') + ('ている' if msc.group(0).rstrip('さらに').endswith('ていたら、') else ''))
            if cc is not None:
                sc = cc
                sent = sent[msc.end():]
        if re.fullmatch(r'[+-]\d+', sent) and last:   # 「さらに+1」: 앞과 같은 수정
            out.append(dict(last, n=int(sent), **({'c': sc} if sc else {})))
            continue
        mp = re.match(r'あなたの(?P<z>エナジー|手札|ドロップゾーンのカード|ドロップゾーン|ユニット|つけた契約書|つけたログ)(?P<k>\d+)枚につき、', sent)
        if mp:
            per = {'zone': {'エナジー': 'energy', '手札': 'hand', 'ドロップゾーンのカード': 'drop', 'ドロップゾーン': 'drop', 'ユニット': 'field', 'つけた契約書': 'contract', 'つけたログ': 'log'}[mp.group('z')], 'k': int(mp.group('k'))}
            sent = sent[mp.end():]
        mp = re.match(r'(?:あなたのターン中、)?あなたの(?P<z>ドロップゾーンの)?(?P<d>[^、。]+?)(?P<noun>ユニット|カード)(?P<k>\d+)枚につき、', sent) if not per else None
        if mp:
            f = _zdesc(mp.group('d') + mp.group('noun'))
            if f is not None:
                per = {'zone': 'drop' if mp.group('z') else 'field', 'k': int(mp.group('k')), 'f': f}
                sent = sent[mp.end():]
        mp = re.match(r'このユニットのパワー(?P<k>\d+)につき、', sent) if not per else None
        if mp:
            per = {'selfPow': int(mp.group('k'))}
            sent = sent[mp.end():]
        sent = re.sub(r'^フィールドの', '', sent)
        if re.match(r'【(?:デコイ|ブリッツ|バーサーク)】を得', sent):
            sent = 'このユニットは' + sent
        if re.match(r'(?:パワー|ヒット)を(?:[+-]\d+|\d+倍にする)$', sent) and last:   # 주어 생략: 앞 문장의 대상
            sent = {'self': 'このユニット', 'host': 'このカードをつけたユニット'}.get(last.get('to'), 'このユニット') + 'の' + sent
        r = _perm_sent(sent, per)
        if r is None:
            _FAIL['at'] = 'PERM:' + sent
            return None
        for st in r:
            if sc:
                st['c'] = sc
        out += r
        if r and r[-1].get('op') in ('pow', 'hit'):
            last = {k: v for k, v in r[-1].items() if k != 'c'}
    return {'if': conds, 'do': out} if out else None


def _perm_sent(sent, per):
    """영속 효과 한 문장 -> 단계 목록 | None"""
    out = []
    m = re.fullmatch(r'相手は(?P<d>[^、。]*?)ユニットではアタックができない', sent)
    if m:
        f = parse_desc('相手の' + m.group('d'))
        return None if f is None else [{'op': 'kw', 'kw': 'noAttack', 'to': {'all': dict(f, type='unit')}}]
    if True:
        sent = re.sub(r'^あなたの、', 'あなたの', sent)
        m = re.fullmatch(r'(?P<to>[^。]*?)の(?P<mods>(?:パワー|ヒット)を[+-]\d+(?:、(?:パワー|ヒット)を[+-]\d+)?)(?:する)?', sent)
        if m and per:
            to = subj(m.group('to'))
            if not to:
                return None
            for k, v in re.findall(r'(パワー|ヒット)を([+-]\d+)', m.group('mods')):
                out.append({'op': 'pow' if k == 'パワー' else 'hit', 'n': int(v), 'to': to, 'per': per})
            return out
        if m:
            to = subj(m.group('to'))
            if not to:
                return None
            for k, v in re.findall(r'(パワー|ヒット)を([+-]\d+)', m.group('mods')):
                out.append({'op': 'pow' if k == 'パワー' else 'hit', 'n': int(v), 'to': to})
            return out
        m = re.fullmatch(r'(?P<to>[^、。]*?)は【(?P<k>デコイ|ブリッツ|バーサーク)】を得て、(?P<mods>(?:パワー|ヒット)を[+-]\d+)', sent)
        if m:
            to = subj(m.group('to'))
            if not to:
                return None
            out.append({'op': 'kw', 'kw': {'デコイ': 'decoy', 'ブリッツ': 'blitz', 'バーサーク': 'berserk'}[m.group('k')], 'to': to})
            for k, v in re.findall(r'(パワー|ヒット)を([+-]\d+)', m.group('mods')):
                out.append({'op': 'pow' if k == 'パワー' else 'hit', 'n': int(v), 'to': to})
            return out
        KWP = [(r'アタックもブロックもされ(?:ず|ない)', ['noBeAttacked', 'unblockable']), (r'ユニットにアタックできない', ['noAttackUnit']), (r'他の能力を全て失う', ['blank']),
               (r'受けるダメージ全てを0にする', ['noDamage']), (r'ドロップ以外の方法でフィールドを離れない', ['stayField']), (r'コマンドの対象にならず', ['cmdImmune']),
               (r'アタックされ(?:ず|ない)', ['noBeAttacked']), (r'【デコイ】を無視してアタックでき(?:る)?', ['ignoreDecoy']), (r'ブロックされ(?:ず|ない)', ['unblockable']),
               (r'ブロックができ(?:ず|ない)', ['noBlock']), (r'アタックもブロックもできない', ['noAttack', 'noBlock']), (r'レストで登場する', ['enterRested']),
               (r'可能な限りアタックする', ['mustAttack']), (r'手札に戻らず(?:、)?山札に置かれない', ['noBounce', 'noDeck']), (r'手札に戻らない', ['noBounce']),
               (r'卒業できず(?:、)?リムーブされない', ['noGraduate', 'noRemove']), (r'相手の効果でレストしない', ['noOppRest']),
               (r'(?:相手の)?エースにアタックされない', ['noAtkByAce']), (r'相手の効果の対象にならない', ['oppFxImmune']), (r'ユニットの効果の対象にならない', ['unitFxImmune']),
               (r'相手のコマンドの対象にならない', ['cmdImmune']), (r'相手の効果でパワーが減少しない', ['noOppDebuff']), (r'【デコイ】を失い', ['loseDecoy']),
               (r'(?:各ターン1回まで、)?レストしていてもアタックできる', ['attackRested']), (r'スタンドしているユニットにアタックできる', ['atkStand']),
               (r'コマンドカードでも【ブライト】できる', ['brightCmdSelf']),
               (r'(?:パワーを(?P<pw>[+-]\d+)(?:、|し、))', 'POW'), (r'(?:ヒットを(?P<ht>[+-]\d+)(?:、|し、)?)', 'HIT'),
               (r'【(デコイ|ブリッツ|バーサーク)】(?:と【(デコイ|ブリッツ|バーサーク)】)?を得(?:る|て)', None)]
        sent = re.sub(r'^このユニットが受けるダメージ全てを0にする$', 'このユニットは受けるダメージ全てを0にする', sent)
        mk = re.fullmatch(r'(?P<to>[^。]*?)(?:では|は)(?P<l>.+)', sent)
        if mk and subj(re.sub(r'^あなたの、', 'あなたの', mk.group('to'))):
            to = subj(re.sub(r'^あなたの、', 'あなたの', mk.group('to')))
            rest_, ks = mk.group('l'), []
            while rest_:
                for rx, kk in KWP:
                    mm = re.match(rx + r'(?:、)?', rest_)
                    if mm:
                        if kk in ('POW', 'HIT'):
                            ks.append(('pow', int(mm.group('pw'))) if kk == 'POW' else ('hit', int(mm.group('ht'))))
                        elif kk is None:
                            ks += [{'デコイ': 'decoy', 'ブリッツ': 'blitz', 'バーサーク': 'berserk'}[x] for x in mm.groups() if x]
                        else:
                            ks += kk
                        rest_ = rest_[mm.end():]
                        break
                else:
                    break
            if not rest_ and ks:
                out += [{'op': k[0], 'n': k[1], 'to': to} if isinstance(k, tuple) else {'op': 'kw', 'kw': k, 'to': to} for k in ks]
                return out
        mb = re.fullmatch(r'(?P<to>[^。]*?)は【ブライト(?P<n>\d+):(?P<a>[^】]+)】を得る', sent)
        if mb and subj(mb.group('to')):
            out.append({'op': 'kw', 'kw': 'bright:' + mb.group('n') + ':' + mb.group('a'), 'to': subj(mb.group('to'))})
            return out
        if re.fullmatch(r'相手はあなたのユニットのアタックを可能な限りブロックする', sent):
            out.append({'op': 'kw', 'kw': 'mustBlock', 'to': {'all': {'side': 'opp', 'type': 'unit'}}})
            return out
        m = re.fullmatch(r'(?P<to>[^、。]*?)は(?P<k>アタックされない|スタンドフェイズにスタンドしない|エースでないユニットにはアタックされない|スタンドしているユニットにアタックできる|レストで登場し、スタンドフェイズにスタンドしない)', sent)
        if m:
            to = subj(m.group('to'))
            if not to:
                return None
            out.append({'op': 'kw', 'kw': {'アタックされない': 'noBeAttacked', 'スタンドフェイズにスタンドしない': 'noStand', 'エースでないユニットにはアタックされない': 'aceOnlyAttack', 'スタンドしているユニットにアタックできる': 'atkStand', 'レストで登場し、スタンドフェイズにスタンドしない': 'noStand'}[m.group('k')], 'to': to})
            if 'レストで登場' in m.group('k'):
                out.append({'op': 'kw', 'kw': 'enterRested', 'to': to})
            return out
        if re.fullmatch(r'あなたは(?:ライフが0枚でも)?ダメージで敗北しない', sent):
            out.append({'op': 'rule', 'rule': 'noLoseDmg'})
            return out
        if re.fullmatch(r'相手の手札上限は(\d+)枚になる', sent):
            out.append({'op': 'rule', 'rule': 'oppHand' + re.search(r'\d+', sent).group()})
            return out
        m = re.fullmatch(r'(?P<to>[^、。]*?)(?:は|では)(?P<k>アタックとブロックができない|アタックできない|アタックができない|ブロックができない|ブロックできない|ブロックされない)', sent)
        if m:
            to = subj(m.group('to'))
            if not to:
                return None
            ks = {'アタックとブロックができない': ['noAttack', 'noBlock'], 'アタックできない': ['noAttack'], 'アタックができない': ['noAttack'], 'ブロックができない': ['noBlock'], 'ブロックできない': ['noBlock'], 'ブロックされない': ['unblockable']}[m.group('k')]
            out += [{'op': 'kw', 'kw': k, 'to': to} for k in ks]
            return out
        m = re.fullmatch(r'(?P<to>[^、。]*?)は(?P<n>\d+)ダメージでも受けるとドロップする', sent)
        if m and subj(m.group('to')):
            out.append({'op': 'kw', 'kw': 'fragile', 'to': subj(m.group('to'))})
            return out
        m = re.fullmatch(r'(?P<to>[^、。]*?)は【(?P<k>デコイ|ブリッツ|バーサーク)】を得る', sent)
        if m:
            to = subj(m.group('to'))
            if not to:
                return None
            out.append({'op': 'kw', 'kw': {'デコイ': 'decoy', 'ブリッツ': 'blitz', 'バーサーク': 'berserk'}[m.group('k')], 'to': to})
            return out
        # 그 밖의 영속 문장
        sent2 = re.sub(r'^フィールドの', '', sent)
        m = re.fullmatch(r'相手はこのユニットを、トリガーでプレイするコマンド以外で対象にできない', sent2)
        if m:
            return [{'op': 'kw', 'kw': 'oppFxImmuneT', 'to': 'self'}]
        m = re.fullmatch(r'相手はこのユニットのアタックを可能な限りブロックする', sent2)
        if m:
            return [{'op': 'kw', 'kw': 'forceBlock', 'to': 'self'}]
        m = re.fullmatch(r'このユニットは【ブリッツ】を得て、相手はこのユニットのアタックを可能な限りブロックする', sent2)
        if m:
            return [{'op': 'kw', 'kw': 'blitz', 'to': 'self'}, {'op': 'kw', 'kw': 'forceBlock', 'to': 'self'}]
        m = re.fullmatch(r'相手は(?P<d>[^、。]*?)ユニットではアタックができない', sent2)
        if m:
            f = parse_desc('相手の' + m.group('d'))
            if f is not None:
                return [{'op': 'kw', 'kw': 'noAttack', 'to': {'all': dict(f, type='unit')}}]
        m = re.fullmatch(r'(?:クラスカードがついた)?このユニットがダメージを与えたユニットは、パワーに関わらずドロップされる', sent2)
        if m:
            return [{'op': 'kw', 'kw': 'deathtouch', 'to': 'self'}]
        if re.fullmatch(r'その際、そのユニットが持つ能力は全て発動しない', sent2):
            return [{'op': 'kw', 'kw': 'deathtouchSilent', 'to': 'self'}]
        m = re.fullmatch(r'このユニットはコスト(?P<n>\d+)のユニットにアタックされない', sent2)
        if m:
            return [{'op': 'kw', 'kw': 'noAtkByCost:' + m.group('n'), 'to': 'self'}]
        m = re.fullmatch(r'(?P<to>[^、。]*?)は【(?P<a>デコイ|ブリッツ|バーサーク)】と【(?P<b>デコイ|ブリッツ|バーサーク)】を得て、それらが受ける効果によるダメージを0にする', sent2)
        if m and subj(m.group('to')):
            to = subj(m.group('to'))
            KM = {'デコイ': 'decoy', 'ブリッツ': 'blitz', 'バーサーク': 'berserk'}
            return [{'op': 'kw', 'kw': KM[m.group('a')], 'to': to}, {'op': 'kw', 'kw': KM[m.group('b')], 'to': to}, {'op': 'kw', 'kw': 'noEffDmg', 'to': to}]
        m = re.fullmatch(r'(?P<to>相手のユニット|あなたのユニット)が受けるダメージは2倍になる', sent2)
        if m:
            return [{'op': 'kw', 'kw': 'dmgDouble', 'to': {'all': {'side': 'opp' if m.group('to').startswith('相手') else 'own', 'type': 'unit'}}}]
        if re.fullmatch(r'このユニットが受けるダメージ全てを0にする|そのバトル中にこのユニットが受けるダメージ全てを0にする', sent2):
            return [{'op': 'kw', 'kw': 'noDamage', 'to': 'self'}]
        m = re.fullmatch(r'このユニットの色は(?P<c>赤|青|白|黒)になり、(?:赤|青|白|黒)以外の色を失う', sent2)
        if m:
            c = {'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[m.group('c')]
            return [{'op': 'kw', 'kw': 'colorAs:only', 'to': 'self'}, {'op': 'kw', 'kw': 'colorAs:' + c, 'to': 'self'}]
        m = re.fullmatch(r'このユニットは⁅(?P<i>バスター|ショット)アイコン⁆を持つ', sent2)
        if m:
            return [{'op': 'kw', 'kw': 'iconAs:' + ('buster' if m.group('i') == 'バスター' else 'shot'), 'to': 'self'}]
        if re.fullmatch(r'あなたのバスターアイコンがライフからドロップする際、代わりに手札に戻す', sent2):
            return [{'op': 'rule', 'rule': 'lifeBusterToHand'}]
        if re.fullmatch(r'このユニットがダメージを与えたユニットは、そのターン中、ドロップする際、代わりにエナジーゾーンに置く', sent2):
            return [{'op': 'kw', 'kw': 'dmgToEnergy', 'to': 'self'}]
        if re.fullmatch(r'このユニットがこのターンのアタックフェイズに登場したユニットから受けるダメージは0になる', sent2):
            return [{'op': 'kw', 'kw': 'noDmgFromAtkEntered', 'to': 'self'}]
        if re.fullmatch(r'各プレイヤーはショットアイコンのコマンドをプレイできない', sent2):
            return [{'op': 'rule', 'rule': 'noShotCmd'}]
        m = re.fullmatch(r'このユニットのパワーを(?P<n>\d+)倍にする', sent2)
        if m:
            return [{'op': 'kw', 'kw': 'powMul:' + m.group('n'), 'to': 'self'}]
        m = re.fullmatch(r'このユニットは色に(?P<a>赤|青|白|黒)と(?P<b>赤|青|白|黒)も持つ', sent2)
        if m:
            CL = {'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}
            return [{'op': 'kw', 'kw': 'colorAs:' + CL[m.group('a')], 'to': 'self'}, {'op': 'kw', 'kw': 'colorAs:' + CL[m.group('b')], 'to': 'self'}]
        # 『~』を得る: 다른 능력 부여
        m = re.fullmatch(r'(?P<to>[^、。『]*?)は(?P<kws>(?:【(?:デコイ|ブリッツ|バーサーク)】と)*)『(?P<ab>⁅自動⁆[^』]+?)。?』を得(?:る|て、(?P<mods>(?:(?:パワー|ヒット)を[+-]\d+、?)+))?', sent2)
        if m and subj(m.group('to')):
            to = subj(m.group('to'))
            ab = _parse_body2(m.group('ab'), {}, None)
            if ab and ab.get('k') == 'auto':
                r = [{'op': 'kw', 'kw': {'デコイ': 'decoy', 'ブリッツ': 'blitz', 'バーサーク': 'berserk'}[x], 'to': to} for x in re.findall(r'【([^】]+)】', m.group('kws') or '')]
                r.append({'op': 'grant', 'ab': ab, 'to': to})
                for kk, vv in re.findall(r'(パワー|ヒット)を([+-]\d+)', m.group('mods') or ''):
                    r.append({'op': 'pow' if kk == 'パワー' else 'hit', 'n': int(vv), 'to': to})
                return r
        return None


# ---------- 카드 전체 ----------
def split_once(body):
    once = 0
    for rx in [r'この能力は(?:各|1)ターン(?:に)?1回(?:まで|のみ)?(?:しか)?発動(?:でき|し)(?:る|ない)。?', r'\(この能力は各ターン1回まで発動できる\)']:
        if re.search(rx, body):
            once = 1
            body = re.sub(rx, '', body)
    return body.strip(), once


def parse_card(d):
    """카드 정의 d(text/tfx 포함) -> (ab 목록, 자동 처리된 줄 번호 집합)"""
    if d.get('type') == 'territory':
        lines = [x for x in (d.get('tfx', {}).get('text', '') or '').split(' / ') if x and x != '(효과 없음)']
    else:
        lines = list(d.get('text') or [])
    lines = [N(x) for x in lines]
    # 원문 줄이 문장 중간에서 끊긴 경우 이어 붙임 (줄 번호는 첫 줄)
    joined = {}
    k = 0
    while k < len(lines) - 1:
        j = k + 1
        while j < len(lines):
            a, b = lines[k], lines[j]
            if a and not re.search(r'[。)」】]$', a) and b and not re.match(r'[⁅【・(「]', b) and not a.startswith('【スキル】'):
                lines[k] = a + b
                lines[j] = ''
                joined[j] = k
                j += 1
                continue
            break
        k = j
    skill = None
    for x in lines:
        if x.startswith('【スキル】'):
            skill = parse_skill(x)
    abs_, done, mts = [], set(), []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln:
            i += 1
            continue
        # 「以下を1つ行う」 + ・줄들
        ln = re.sub(r'(行う。)\([^)]*\)$', r'\1', ln)
        # 「以下を行う。Xなら、2回行う / もう1回行ってよい」: 묶음을 한 번 더
        mrep = re.fullmatch(r'(?P<h>.*?)以下を行う。(?P<c>[^。]+?)なら、(?:その後、)?(?:2回行う|もう1回行(?P<may>ってよい|う))。?(?:\(.*\))?', ln)
        if mrep and i + 1 < len(lines) and lines[i + 1].startswith('・'):
            j = i + 1
            opts = []
            while j < len(lines) and lines[j].startswith('・'):
                opts.append(parse_effects_lenient(lines[j][1:]))
                j += 1
            c = parse_cond(mrep.group('c'))
            if all(o is not None for o in opts):
                body = sum(opts, [])
                again = ([{'op': 'confirm', 'text': '한 번 더 할까요?', 'alt': 1, 'no': []}] if mrep.group('may') else []) + body
                tail = {'op': 'if', 'c': c, 'then': again} if c is not None else {'op': 'askIf', 'jp': mrep.group('c'), 'then': again}
                r = parse_body(mrep.group('h') + '__CHOOSE__', d, skill) or parse_body_lenient(mrep.group('h') + '__CHOOSE__', d, skill)
                if r:
                    for k2, st in enumerate(r['do']):
                        if st.get('op') == 'choose':
                            r['do'][k2:k2 + 1] = body + [tail]
                            break
                    if c is None:
                        r['guided'] = 1
                    r['li'] = list(range(i, j))
                    abs_.append(r)
                    done.update(range(i, j))
            i = j
            continue
        # 「以下を1つ行う。Xなら、N つ目の選択肢は選べない」
        mdis = re.fullmatch(r'(?P<h>.*?以下を1つ行う。)(?P<c>[^。]+?)なら、(?P<k>\d)つ目の選択肢は選べない。?', ln)
        dis = None
        if mdis:
            dis = {'k': int(mdis.group('k')) - 1, 'c': parse_cond(mdis.group('c'))}
            ln = mdis.group('h')
        mall = re.fullmatch(r'(?P<h>.*?)以下を(?:全て)?行う。?', ln)
        if mall and i + 1 < len(lines) and lines[i + 1].startswith('・'):
            j = i + 1
            opts = []
            while j < len(lines) and lines[j].startswith('・'):
                opts.append(parse_effects_lenient(lines[j][1:]))
                j += 1
            if all(o is not None for o in opts):
                r = parse_body(mall.group('h') + '__CHOOSE__', d, skill) or parse_body_lenient(mall.group('h') + '__CHOOSE__', d, skill)
                if r:
                    for st in r['do']:
                        if st.get('op') == 'choose':
                            st['op'] = 'all'
                            st['opts'] = opts
                    r['li'] = list(range(i, j))
                    abs_.append(r)
                    done.update(range(i, j))
            i = j
            continue
        mb = re.search(r'以下を1つ(?:選んで)?行う。(?P<c>[^。]+?)なら、(?:代わりに)?両方行(?:う|ってよい)。?$', ln)
        kwline = re.search(r'【(?:夢を見ない|マギア|マケイン)】', ln)
        if not kwline and (re.fullmatch(r'以下を1つ(?:選んで)?行う。?', ln) or re.search(r'以下を1つ(?:選んで)?行う。?$', ln) or mb):
            both = parse_cond(mb.group('c')) if mb else None
            if mb and both is None:
                i += 1
                continue
            head = re.sub(r'以下を1つ(?:選んで)?行う。.*$|以下を1つ(?:選んで)?行う。?$', '', ln)
            j = i + 1
            opts = []
            while j < len(lines) and lines[j].startswith('・'):
                opts.append(parse_effects_lenient(lines[j][1:]))
                j += 1
            ok = opts and all(o is not None for o in opts)
            if ok:
                r = parse_body(head + '__CHOOSE__', d, skill) or parse_body_lenient(head + '__CHOOSE__', d, skill)
                if r:
                    def _fill(seq):
                        for st in seq:
                            if st.get('op') == 'choose' and not st.get('opts'):
                                st['opts'] = opts
                                if both:
                                    st['bothIf'] = both
                                if dis and dis['c'] is not None:
                                    st['dis'] = dis
                            if st.get('op') in ('if', 'askIf'):
                                _fill(st.get('then', []))
                    _fill(r['do'])
                    r['li'] = list(range(i, j))
                    abs_.append(r)
                    done.update(range(i, j))
            i = j
            continue
        if re.fullmatch(r'【卒業】(?:\(.*\))?', ln):
            abs_.append({'k': 'auto', 'on': 'attackEnd', 'src': 'self', 'if': [], 'do': [{'op': 'graduate', 'may': 1}], 'li': [i]})
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'【コスプレ(\d+)】(?:\(.*\))?', ln)
        if m:
            d['cos'] = int(m.group(1))
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'⁅永続⁆このカードが「([^」]+)」を含むユニットの【コスプレ】で登場する際、コスト(\d+)として扱う。?', ln)
        if m:
            d['cosCost'] = {'name': m.group(1), 'cost': int(m.group(2))}
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'⁅永続⁆あなたの称号「([^」]+)」のテリトリー開放中なら、このユニットの【コスプレ】は手札とエナジーから選べる。エナジーと入れ替えたら、1枚引く。?', ln)
        if m:
            abs_.append({'k': 'perm', 'if': [{'terrTitle': m.group(1)}], 'do': [{'op': 'rule', 'rule': 'cosEnergySelf', 'to': 'self'}], 'li': [i]})
            done.add(i)
            i += 1
            continue
        if re.fullmatch(r'⁅永続⁆あなたのユニットの【コスプレ】は、あなたのアタックフェイズ開始時にも発動する。?', ln):
            abs_.append({'k': 'perm', 'if': [], 'do': [{'op': 'rule', 'rule': 'cosAttackStart'}], 'li': [i]})
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'⁅永続⁆(?:あなたの称号「([^」]+)」のテリトリー開放中、)?このユニットはブロックされず、【デコイ】を無視してアタックでき、ライフがレッドゾーンなら、さらにヒットを\+(\d)。?', ln)
        if m:
            c = [{'terrTitle': m.group(1)}] if m.group(1) else []
            abs_.append({'k': 'perm', 'if': c, 'do': [{'op': 'kw', 'kw': 'unblockable', 'to': 'self'}, {'op': 'kw', 'kw': 'ignoreDecoy', 'to': 'self'}], 'li': [i]})
            abs_.append({'k': 'perm', 'if': c + [{'red': 1}], 'do': [{'op': 'hit', 'n': int(m.group(2)), 'to': 'self'}], 'li': [i]})
            done.add(i)
            i += 1
            continue
        if re.fullmatch(r'⁅永続⁆あなたのクラスカードのエナジーは色が黒と青と赤になる。?', ln):
            abs_.append({'k': 'perm', 'if': [], 'do': [{'op': 'rule', 'rule': 'classTri'}], 'li': [i]})
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'(?P<h>⁅保持称号開放中⁆)?【CAD】(?P<spec>[^(]*?)(?:\(.*\))?', ln)
        if m:
            spec = m.group('spec')
            f = {'magic': 1}
            mm = re.fullmatch(r'(?:(?P<c1>赤|青|白|黒)(?:か(?P<c2>赤|青|白|黒))?(?:で|の))?(?:コスト(?P<n>\d+)(?P<le>以下)?)?(?P<shot>ショットアイコン)?', spec)
            if mm:
                CL = {'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}
                if mm.group('c1'):
                    f['color'] = [CL[x] for x in (mm.group('c1'), mm.group('c2')) if x]
                if mm.group('n'):
                    f['costLE' if mm.group('le') else 'costEQ'] = int(mm.group('n'))
                if mm.group('shot'):
                    f['icon'] = 'shot'
                d['cad'] = f
                abs_.append({'k': 'auto', 'on': 'attack', 'src': 'self', 'if': ([{'hold': 1}] if m.group('h') else []) + [{'cadOk': 1}],
                             'do': [{'op': 'playFree', 'from': 'hand', 'f': f, 'may': 1, 'cad': 1}], 'li': [i]})
                done.add(i)
                i += 1
                continue
        if re.fullmatch(r'⁅永続⁆あなたのテリトリーが開放されていないなら、このユニットの【CAD】は使えない。?', ln):
            d['cadNeedsTerr'] = 1
            done.add(i)
            i += 1
            continue
        if re.fullmatch(r'⁅永続⁆あなたのテリトリー開放中なら、このユニットの【CAD】でプレイする魔法カードは手札とエナジーから選べる。?', ln):
            abs_.append({'k': 'perm', 'if': [{'terr': 1}], 'do': [{'op': 'rule', 'rule': 'cadEnergy'}], 'li': [i]})
            done.add(i)
            i += 1
            continue
        # 【マギア】: 공격 시 에너지 2장을 뒷면으로 해서 발동 / 【マケイン】: 배틀에서 졌을 때 / 【ログ】: 등장 시 덱 위를 뒷면으로 테리토리에
        m = re.fullmatch(r'(?P<h>⁅保持称号開放中⁆)?【(?P<k>マギア|マケイン)】(?:\([^)]*\))?(?P<x>.*)', ln)
        if m:
            k = m.group('k')
            d['magia' if k == 'マギア' else 'makein'] = 1
            body = m.group('x')
            if re.fullmatch(r'以下を1つ(?:選んで)?行う。?', body):
                j = i + 1
                opts = []
                while j < len(lines) and lines[j].startswith('・'):
                    opts.append(parse_effects_lenient(lines[j][1:]))
                    j += 1
                sub = [{'op': 'choose', 'opts': opts}] if opts and all(o is not None for o in opts) else None
                rng = list(range(i, j))
            else:
                _LAST.clear()
                sub = parse_effects_lenient(body) if body else []
                if sub is not None and '$prev' in str(sub):
                    sub = None
                rng = [i]
                j = i + 1
            on = 'attack' if k == 'マギア' else 'lose'
            if sub is not None:
                ab = {'k': 'auto', 'on': on, 'src': 'self', 'if': [{'hold': 1}] if m.group('h') else [], 'do': sub, 'li': rng}
                if k == 'マギア':
                    ab['cost'] = [{'op': 'flipEnergy', 'n': 2, 'inCost': 1}]
                abs_.append(ab)
                done.update(rng)
            else:
                mts.append({'on': on, 'src': 'self', 'if': [], 'li': rng})
            i = j
            continue
        # 【恋愛頭脳戦】: 등장 시 패 1장을 필드에 뒷면으로 둘 수 있음
        if re.fullmatch(r'【恋愛頭脳戦】(?:\(.*\))?', ln):
            d['renai'] = 1
            abs_.append({'k': 'auto', 'on': 'enter', 'src': 'self', 'if': [], 'do': [{'op': 'setHand', 'n': 1, 'may': 1}], 'li': [i]})
            done.add(i)
            i += 1
            continue
        # 뒷면으로 둔 이 카드를 코스트 없이 플레이할 수 있는 때
        m = re.fullmatch(r'(?:(?P<c>[^。]*?)なら、)?伏せられたこのカードは(?P<w>相手エンドフェイズ|自分のメインフェイズ)にコストを払わずプレイできる。?', ln)
        if m:
            c = parse_cond(m.group('c').replace('このターンにあなたがダメージを受けている', 'このターンあなたがダメージを受けている')) if m.group('c') else []
            if c is not None:
                d['setPlay'] = {'when': 'oppEnd' if '相手' in m.group('w') else 'myMain', 'if': c}
                done.add(i)
            i += 1
            continue
        # 【神衣-鮮血】【神衣-純潔】: 내가 플레이한 그 커맨드를 이 유닛에 겹쳐 입힐 수 있음
        m = re.fullmatch(r'((?:【神衣-[^】]+】)+)(?:\(.*\))?', ln)
        if m:
            d['kamui'] = re.findall(r'【神衣-([^】]+)】', m.group(1))
            done.add(i)
            i += 1
            continue
        # 입히는 커맨드: 【鮮血】着ているユニットのパワーを+3000
        m = re.fullmatch(r'【(?P<n>[^】]+)】着ているユニットの(?P<mods>(?:パワー|ヒット)を[+-]\d+(?:、(?:パワー|ヒット)を[+-]\d+)?)。?', ln)
        if m:
            d['dress'] = m.group('n').split('/')
            abs_.append({'k': 'perm', 'if': [], 'do': [{'op': 'pow' if k == 'パワー' else 'hit', 'n': int(v), 'to': 'host'} for k, v in re.findall(r'(パワー|ヒット)を([+-]\d+)', m.group('mods'))], 'li': [i]})
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'あなたの(?P<d>[^。]*?)ユニットにこのカードを重ねて着せてよい。?', ln)
        if m and parse_desc(m.group('d')) is not None:
            d['dressAny'] = parse_desc(m.group('d'))
            done.add(i)
            i += 1
            continue
        if re.fullmatch(r'【ログ】(?:\(.*\))?', ln):
            d['log'] = 1
            abs_.append({'k': 'auto', 'on': 'enter', 'src': 'self', 'if': [], 'do': [{'op': 'logAttach', 'may': 1}], 'li': [i]})
            done.add(i)
            i += 1
            continue
        # 【夢を見ない】〔색/속성〕: 공격 시 덱 위 1장을 공개해서 드롭할 수 있고, 지정 색·속성이면 효과 발동
        m = re.fullmatch(r'(?P<h>⁅保持称号開放中⁆)?【夢を見ない】〔(?P<spec>[^〕]+)〕(?:\([^)]*\))?:?(?P<x>.+?)(?:\((?:[^()]|\([^)]*\))*\))?', ln)
        if m:
            d['yumemi'] = 1
            CL = {'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}
            parts = m.group('spec').split('か')
            f = {'color': [CL[x] for x in parts if x in CL]} if all(x in CL for x in parts) else {'attr': parts}
            body = m.group('x')
            if re.fullmatch(r'以下を1つ(?:選んで)?行う。?', body):
                j = i + 1
                opts = []
                while j < len(lines) and lines[j].startswith('・'):
                    opts.append(parse_effects_lenient(lines[j][1:]))
                    j += 1
                sub = [{'op': 'choose', 'opts': opts}] if opts and all(o is not None for o in opts) else None
                rng = list(range(i, j))
            else:
                _LAST.clear()
                sub = parse_effects_lenient(body)
                if sub is not None and '$prev' in str(sub):
                    sub = None
                rng = [i]
                j = i + 1
            if sub is not None:
                abs_.append({'k': 'auto', 'on': 'attack', 'src': 'self', 'if': [{'hold': 1}] if m.group('h') else [],
                             'do': [{'op': 'yumemi', 'f': f, 'may': 1}, {'op': 'if', 'c': [{'did': 1}], 'then': sub}], 'li': rng})
                done.update(rng)
            else:
                mts.append({'on': 'attack', 'src': 'self', 'if': [], 'li': rng})
            i = j
            continue
        m = re.fullmatch(r'⁅永続⁆あなたの【夢を見ない】で公開されている(このカード|エースカード)は全ての色を持つ。?', ln)
        if m:
            if m.group(1) == 'このカード':
                d['yumemiAll'] = 1
            else:
                abs_.append({'k': 'perm', 'if': [], 'do': [{'op': 'rule', 'rule': 'yumemiAce'}], 'li': [i]})
            done.add(i)
            i += 1
            continue
        if re.fullmatch(r'⁅永続⁆あなたの【夢を見ない】で公開されているコマンドカードは⁅スペード⁆⁅ハート⁆⁅ダイヤ⁆⁅クラブ⁆として扱う。?', ln):
            abs_.append({'k': 'perm', 'if': [], 'do': [{'op': 'rule', 'rule': 'yumemiCmd'}], 'li': [i]})
            done.add(i)
            i += 1
            continue
        if ln in ('【魔法】',):
            d['magic'] = 1
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'⁅永続⁆(?P<t>あなたのテリトリー開放中、)?このカードを含めて「[^」]+」が手札に(?P<n>\d+)枚揃ったら、あなたはそれらを全て公開し、このゲームに勝利する。?', ln)
        if m:
            d['win5'] = {'n': int(m.group('n')), **({'terr': 1} if m.group('t') else {})}
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'⁅永続⁆このカードは全(?:ての)?領域でコスト(\d+)になる。?', ln)
        if m:
            d['cost'] = int(m.group(1))
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'⁅永続⁆このカードは(?:全(?:ての)?領域で)?称号「([^」]+)」(?:と称号「([^」]+)」)?を持つ。?', ln)
        if m:
            d['titles'] = list(dict.fromkeys((d.get('titles') or []) + [x for x in m.groups() if x]))
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'あなたのエナジーが(\d+)色(?:以上)?なら、このカードをプレイする際のコストを(\d+)減らしてプレイできる。?', ln)
        if m:
            d['costRed'] = {'colors': int(m.group(1)), 'by': int(m.group(2))}
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'⁅永続⁆このユニットは((?:称号「[^」]+」か?)+)のテリトリー(?:も|を)開放できる。?(?:\(.*\))?', ln)
        if m:
            d['openTitles'] = re.findall(r'「([^」]+)」', m.group(1))
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'このカードはデッキに(\d+)枚まで入れられる。?', ln)
        if m:
            d['maxCopies'] = int(m.group(1))
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'⁅永続⁆(?:このユニット|このカード)は(?:全(?:ての)?領域で)?(?:カード名を)?「([^」]+)」(?:として|としても)扱う。?(?:\(.*\))?', ln)
        if m:
            d['alias'] = m.group(1)
            done.add(i)
            i += 1
            continue
        if re.fullmatch(r'このカードはデッキに\d+枚より多く入れられる。?', ln):
            d['anyCopies'] = 1
            done.add(i)
            i += 1
            continue
        if re.fullmatch(r'⁅永続⁆あなたは「同じ色のコマンドカード」でも【ブライト】できる。?', ln):
            abs_.append({'k': 'perm', 'if': [], 'do': [{'op': 'rule', 'rule': 'brightCmd'}], 'li': [i]})
            done.add(i)
            i += 1
            continue
        m = re.match(r'【結束:([^】]+)】', ln)
        if m:
            d['kesso'] = m.group(1).split('/')
            done.add(i)
            i += 1
            continue
        if ln.startswith('【スキル】') and skill is not None:
            done.add(i)   # 비용 정의 줄: 다른 줄에서 씀
            i += 1
            continue
        if re.fullmatch(r'\(ライフからトリガーした時、コストを払わずに登場させてよい\)|\(この登場でテリトリー開放はできない\)', ln):
            done.add(i)
            i += 1
            continue
        r = parse_body(ln, d, skill) or parse_body_lenient(ln, d, skill)
        if r:
            r['li'] = [i]
            abs_.append(r)
            done.add(i)
            if r.get('guided'):
                d.setdefault('gl', []).append(i)
        else:
            mt = manual_trigger(ln, d)
            if mt:
                mt['li'] = [i]
                mts.append(mt)
        i += 1
    for j2, k2 in joined.items():   # 이어 붙인 줄은 앞줄과 같이 처리됨
        if k2 in done:
            done.add(j2)
            for r in abs_:
                if k2 in r.get('li', []):
                    r['li'] = sorted(set(r['li']) | {j2})
    # 커맨드의 못 읽은 본문은 한 번에 묶어 플레이할 때 직접 처리
    play = [m for m in mts if m['on'] == 'play']
    if len(play) > 1:
        play[0]['li'] = sorted(sum((m['li'] for m in play), []))
        mts = [m for m in mts if m['on'] != 'play'] + [play[0]]
    # 그래도 못 읽은 줄: 시점을 알면, 글에서 추정한 처리들을 원하는 만큼 골라 실행 (직접 처리 창은 마지막 수단)
    rest_mts = []
    for mt in mts:
        body = ''.join(lines[i] for i in mt['li'] if i < len(lines))
        body = re.sub(r'^(?:⁅[^⁆]+⁆|【[^】]+】(?:〔[^〕]*〕)?(?:\([^)]*\))?:?)+', '', body)
        if mt['on'] != 'play':
            body = re.sub(r'^[^。]*?時、', '', body, count=1)
        acts, seen = [], set()
        for sent in [x for x in re.split(r'。', body) if x.strip()]:
            for a in _infer_acts(re.sub(r'\([^)]*\)', '', sent)):
                if a[0] not in seen:
                    seen.add(a[0])
                    acts.append(a)
        if not acts or len(acts) > 7:
            rest_mts.append(mt)
            continue
        step = {'op': 'choose', 'loop': 1, 'guide': body[:60],
                'opts': [a[1] for a in acts] + [[{'op': 'manualOpen'}], []],
                'labels': [a[0] for a in acts] + ['다른 처리가 필요해요 (직접 처리 창 열기)', '처리 끝내기'],
                'text': '이 능력은 자동으로 다 읽지 못했어요. 카드 문구에 맞는 처리를 차례로 고르고, 다 했으면 \'처리 끝내기\'를 누르세요'}
        ab = {'k': 'play' if mt['on'] == 'play' else 'auto', 'if': mt['if'], 'do': [step], 'li': mt['li'], 'guided': 1}
        if mt['on'] != 'play':
            ab.update(on=mt['on'], src=mt['src'])
        abs_.append(ab)
        done.update(mt['li'])
        for j2, k2 in joined.items():
            if k2 in mt['li']:
                done.add(j2)
        d.setdefault('gl', []).extend(mt['li'])
    mts = rest_mts
    if mts:
        d['mt'] = mts
    elif 'mt' in d:
        del d['mt']
    _ko_ask(d, abs_)
    return abs_, done


def _ko_ask(d, abs_):
    """'조건 묻기' 단계에 한국어 문구의 해당 조건절을 붙임 (몇 번째 조건인지로 맞춤)"""
    ko = d.get('ko') or []
    for r in abs_:
        if not r.get('guided'):
            continue
        line = ' '.join(ko[i] for i in r.get('li', []) if i < len(ko))
        cl = re.findall(r'(?:^|[,.] ?)([^,.]*?(?:라면|다면|이라면|하면|이면|으면|있으면|없으면))(?=,)', line)
        k = [0]
        def walk(seq):
            for st in seq:
                if st.get('op') == 'askIf' and st.get('trig'):
                    mt = re.search(r'^(?:\[[^\]]+\]\s*)*(.*?때),', line)
                    if mt:
                        st['ko'] = mt.group(1).strip()
                elif st.get('op') == 'askIf':
                    if k[0] < len(cl):
                        st['ko'] = re.sub(r'^\s*(?:그 후|그리고|또한)\s*', '', cl[k[0]]).strip()
                    k[0] += 1
                for key in ('then', 'else'):
                    walk(st.get(key) or [])
                for o in st.get('opts') or []:
                    walk(o)
        walk(r.get('do', []))


def manual_trigger(ln, d):
    """자동 처리하지 못한 줄이라도 발동 시점을 알면 그때 '직접 처리' 창을 띄우도록 {on, src, if}"""
    hold = [{'hold': 1}] if '⁅保持称号開放中⁆' in ln else []
    body = re.sub(r'^(?:⁅(?:自動|永続|保持称号開放中|自|永)⁆)+', '', ln).strip()
    if '⁅永続⁆' in ln or ln.startswith('【スキル】') or re.fullmatch(r'\(.*\)', ln):
        return None
    if '⁅自動⁆' in ln or '⁅自⁆' in ln:
        m = re.match(r'(?P<t>(?:あなたの(?:称号「[^」]+」の)?テリトリー(?:が開放されていて|開放中で)、)?[^、]*?時)、', body)
        if m:
            tr = parse_trigger(m.group('t'))
            if tr:
                return {'on': tr[0], 'src': tr[1], 'if': hold + tr[2]}
            h = m.group('t')
            if 'このユニット' in h and '登場' in h:
                return {'on': 'enter', 'src': 'self', 'if': hold}
            if 'このユニット' in h and 'アタック' in h and '終了' not in h:
                return {'on': 'attack', 'src': 'self', 'if': hold}
            if 'このユニット' in h and 'フィールドからドロップ' in h:
                return {'on': 'leave', 'src': 'self', 'if': hold}
        return None
    # 작품 고유 키워드: 괄호 설명으로 시점을 판단
    if body.startswith('【'):
        if re.search(r'\(登場時', body):
            return {'on': 'enter', 'src': 'self', 'if': hold}
        if re.search(r'\(アタック時|アタック時、', body) or body.startswith('【CAD】') or body.startswith('【マギア】'):
            return {'on': 'attack', 'src': 'self', 'if': hold}
        if re.search(r'バトルに負けた時', body):
            return {'on': 'lose', 'src': 'self', 'if': hold}
        if re.search(r'エンドフェイズ', body) and body.startswith('【コスプレ'):
            return {'on': 'endStart', 'src': 'me', 'if': hold + [{'terr': 1}]}
        if d.get('type') != 'command':
            return None
    if d.get('type') == 'command':
        return {'on': 'play', 'src': 'self', 'if': []}
    return None


def parse_body_lenient(ln, d, skill):
    """엄격히 못 읽은 줄: 모르는 조건은 묻고, 모르는 효과는 처리 방법을 고르게 해서라도 자동 진행"""
    _LEN['on'] = True
    try:
        r = parse_body(ln, d, skill)
    finally:
        _LEN['on'] = False
    if r:
        r['guided'] = 1
    return r


def parse_effects_lenient(t):
    r = parse_effects(t)
    if r is not None:
        return r
    _LEN['on'] = True
    try:
        return parse_effects(t)
    finally:
        _LEN['on'] = False


def parse_body(ln, d, skill):
    _LAST.clear()
    r = _parse_body(ln, d, skill)
    if r and '$prev' in str(r):
        return None   # 앞 대상을 끝내 찾지 못함
    return r


def _parse_body(ln, d, skill):
    gk = False
    m0 = re.match(r'^((?:⁅保持称号開放中⁆)?)【相棒】⁅(ハート|スペード|ダイヤ|クラブ)⁆(?:\([^)]*\))?', ln)
    if m0:   # 相棒: 내 다른 지정 속성 유닛이 있으면 유효
        d['aibou'] = m0.group(2)
        r = _parse_body2(m0.group(1) + ln[m0.end():], d, skill)
        if r:
            r['if'] = r.get('if', []) + [{'exists': {'side': 'own', 'attr': [m0.group(2)], 'notSelf': 1, 'type': 'unit'}}]
        return r
    m = re.match(r'^((?:⁅保持称号開放中⁆)?)【(我駆力|INTERNET[34]\.0|特記事項(\d+)|怪異:([^】]+)|境界-([^】]+))】(?:\([^)]*\))?', ln)
    kc = None
    if m:   # 조건이 맞을 때만 유효한 작품 키워드
        gk = m.group(2)
        if gk == '我駆力':
            d['gaku'] = 1; kc = {'dmgTurn': 1}               # 이번 턴 어느 플레이어든 데미지
        elif gk.startswith('INTERNET'):
            d['net3'] = 1; kc = {'net3': 4 if '4.0' in gk else 1}   # 레스트한 에너지 3색(4.0은 4색) 이상
        elif gk.startswith('特記事項'):
            d['tokki'] = int(m.group(3)); kc = {'countGE': {'zone': 'drop', 'f': {'type': 'command'}, 'n': int(m.group(3))}}
        elif gk.startswith('怪異'):
            d['kaii'] = m.group(4).split('/'); kc = {'droppedAttr': m.group(4).split('/')}   # 이번 턴 내 해당 속성 카드가 드롭
        else:
            CL = {'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}
            cols = [CL[c] for c in m.group(5) if c in CL]
            d['kyokai'] = m.group(5); kc = {'energyEach': {'colors': cols, 'n': 2}} if cols else {'energyColorsEq': 2}
        ln = m.group(1) + ln[m.end():]
    r = _parse_body2(ln, d, skill)
    if r and kc:
        r['if'] = r.get('if', []) + [kc]
    return r


def _parse_body2(ln, d, skill):
    ln = re.sub(r'\((?:[^()]*)\)$', '', ln).strip()   # 끝의 괄호 설명문(리마인더) 제거
    tags = re.findall(r'⁅(自動|永続|保持称号開放中|自|永)⁆', ln)
    body = re.sub(r'^(?:⁅(?:自動|永続|保持称号開放中|自|永)⁆)+', '', ln).strip()
    conds = [{'hold': 1}] if '保持称号開放中' in tags else []
    body, once = split_once(body)
    if '永続' in tags or '永' in tags:
        pm = parse_perm(body.rstrip('。'))
        if not pm and re.match(r'[^。]*?時、', body) and '⁅' not in body:   # 영속 표기지만 '~時' 자동 능력
            return _parse_body2('⁅自動⁆' + body, d, skill)
        if not pm:
            return None
        return {'k': 'perm', 'if': conds + pm['if'], 'do': pm['do']}
    if '自動' in tags or '自' in tags:
        m = re.match(r'(?P<t>(?:あなたの(?:称号「[^」]+」の)?テリトリー(?:が開放されていて|開放中で)、|(?:あなたのターン中|スキルコストで)、)?[^、]*?時)、', body)
        if not m:
            return None
        tr = parse_trigger(m.group('t'))
        if not tr:
            _FAIL['at'] = 'TRIG:' + m.group('t')
            ap = _approx_trigger(m.group('t')) if _LEN['on'] else None
            mt = manual_trigger(ln, d) if _LEN['on'] and not ap else None
            if ap:
                tr = (ap[0], ap[1], ap[2], {'approx': m.group('t')} if ap[3] else None)
            elif mt:
                tr = (mt['on'], mt['src'], [c for c in mt['if'] if c != {'hold': 1}], None)
            else:
                return None
        on, src, tc, extra = tr
        rest = body[m.end():]
        pre_ask = None
        mcnd = re.match(r'(?P<c>[^、。]*?)なら、(?=【スキル】)', rest)
        if mcnd:
            cc = parse_cond(mcnd.group('c'))
            if cc is None:
                if not _LEN['on']:
                    return None
                pre_ask = mcnd.group('c')
                cc = []
            tc = tc + cc
            rest = rest[mcnd.end():]
        cost = None
        mc = re.match(r'(?P<c>[^。]*?)(?:ことで|事で|で)、', rest)
        if mc:
            cost = parse_cost(mc.group('c'), skill)
            if cost:
                rest = rest[mc.end():]
            elif '【スキル】' in mc.group('c'):
                if not (_LEN['on'] and skill):
                    return None
                cost = skill
                rest = rest[mc.end():]
        if rest.startswith('【スキル】発動で、') or rest.startswith('【スキル】を発動することで、'):
            if not skill:
                return None
            cost = skill
            rest = rest.split('、', 1)[1]
        if rest.endswith('__CHOOSE__'):
            pre = rest[:-len('__CHOOSE__')]
            mc2 = re.fullmatch(r'(?P<c>[^、。]+?)なら、', pre)
            if mc2:
                cc = parse_cond(mc2.group('c'))
                if cc is not None:
                    steps = [{'op': 'if', 'c': cc, 'then': [{'op': 'choose'}]}]
                elif _LEN['on']:
                    steps = [{'op': 'askIf', 'jp': mc2.group('c'), 'then': [{'op': 'choose'}]}]
                else:
                    steps = None
            else:
                steps = (parse_effects(pre) if pre else [])
                steps = None if steps is None else steps + [{'op': 'choose'}]
        else:
            steps = parse_effects(rest)
        if steps is None:
            return None
        if pre_ask:
            steps = [{'op': 'askIf', 'jp': pre_ask, 'then': steps}]
        if extra and extra.get('approx'):
            steps = [{'op': 'askIf', 'jp': extra['approx'], 'trig': 1, 'then': steps}]
            extra = None
        r = {'k': 'auto', 'on': on, 'src': src, 'if': conds + tc, 'do': steps}
        if extra and extra.get('any'):
            r['any'] = 1
        if cost:
            r['cost'] = cost
        if once:
            r['once'] = 1
        return r
    # 태그 없음: 커맨드 본문
    if d.get('type') != 'command':
        return None
    if body.endswith('__CHOOSE__'):
        pre = body[:-len('__CHOOSE__')]
        steps = parse_effects(pre) if pre else []
        if steps is None:
            return None
        return {'k': 'play', 'if': [], 'do': steps + [{'op': 'choose'}]}
    steps = parse_effects(body)
    if steps is None:
        return None
    return {'k': 'play', 'if': [], 'do': steps}
