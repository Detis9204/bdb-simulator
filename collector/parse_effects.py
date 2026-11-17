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
    (r'相手の', lambda m, f: f.__setitem__('side', 'opp')),
    (r'あなたの', lambda m, f: f.__setitem__('side', 'own')),
    (r'このユニット以外の|他の', lambda m, f: f.__setitem__('notSelf', 1)),
    (r'総?コスト(\d+)以下の', lambda m, f: f.__setitem__('costLE', int(m.group(1)))),
    (r'総?コスト(\d+)以上の', lambda m, f: f.__setitem__('costGE', int(m.group(1)))),
    (r'パワー(\d+)以下の', lambda m, f: f.__setitem__('powLE', int(m.group(1)))),
    (r'パワー(\d+)以上の', lambda m, f: f.__setitem__('powGE', int(m.group(1)))),
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
    (r'エースか⁅バスターアイコン⁆の', lambda m, f: f.__setitem__('aceOrBuster', 1)),
    (r'「([^」]+)」を(?:名前に)?含む', lambda m, f: f.__setitem__('name', m.group(1))),
    (r'⁅(ハート|スペード|ダイヤ|クラブ)⁆か⁅(ハート|スペード|ダイヤ|クラブ)⁆(?:の|を持つ)?', lambda m, f: f.__setitem__('attr', [m.group(1), m.group(2)])),
    (r'⁅(ハート|スペード|ダイヤ|クラブ)⁆(?:の|を持つ)?', lambda m, f: f.__setitem__('attr', [m.group(1)])),
    (r'【ブライト】を持つ', lambda m, f: f.__setitem__('bright', 1)),
    (r'アイコン能力を持つ', lambda m, f: f.__setitem__('hasIcon', 1)),
    (r'(赤|青|白|黒)の', lambda m, f: f.__setitem__('color', [{'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[m.group(1)]])),
    (r'⁅バスターアイコン⁆を持つ|バスターの|⁅バスターアイコン⁆の?', lambda m, f: f.__setitem__('icon', 'buster')),
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
NOUN = r'(?P<noun>エースカード|エース|ユニットカード|ユニット|コマンドカード|カード)'


def noun_filter(f, noun):
    if noun.startswith('エース'):
        f['ace'] = 1
    if noun in ('ユニットカード', 'ユニット', 'エース'):
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
    if t == TO_SELF or t == 'このカード':
        return 'self'
    if t in ('ドロップゾーンのこのカード', 'あなたのドロップゾーンのこのカード'):
        return 'card'
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
        noun_filter(f, m.group('noun'))
        zone = m.group('zone')
        st = {'op': 'tgt', 'f': f, 'n': int(m.group('n')), 'upto': 1 if m.group('upto') else 0}
        if zone:
            st['zone'] = {'ドロップゾーン': 'drop', '手札': 'hand', 'エナジーゾーン': 'energy', 'エナジー': 'energy'}[zone]
        return st
    add(r'(?:(?:あなたの|相手の)?(?P<zone>ドロップゾーン|手札|エナジーゾーン|エナジー)の)?(?P<d>[^、。を]*?)' + NOUN + r'を(?P<n>\d+)枚(?P<upto>まで)?対象と' + V('し', 'する') + END, tgt)

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
        (r'(?:持ち主の)?山札の上に置' + V('く', 'き'), 'deckTop'),
        (r'(?:持ち主の)?山札の下に置' + V('く', 'き'), 'deckBottom'),
        (r'(?:持ち主の)?エナジーゾーンに置' + V('く', 'き'), 'energy'),
        (r'リムーブ' + V('する', 'し'), 'remove'),
        (r'レスト' + V('する', 'し', 'させる', 'させ'), 'rest'),
        (r'スタンド' + V('する', 'し', 'させる', 'させ'), 'stand'),
        (r'登場' + V('させる', 'させ'), 'summon'),
        (r'(?:あなたの)?ライフの先頭に置' + V('く', 'き'), 'life'),
    ]
    for rx, op in moves:
        def mv(m, op=op):
            to = subj(m.group('to'))
            st = to and {'op': op, 'to': to}
            if st and m.group('may'):
                st['may'] = 1
            return st
        add(r'(?:さらに)?(?P<to>[^、。]*?)を' + rx + MAY + END, mv)

    # 지연: 다음 엔드 페이즈 시작 시
    def delay(m):
        sub = parse_effects(m.group('x'))
        return sub and {'op': 'delay', 'at': 'endStart', 'do': sub}
    add(r'次の(?:あなたの)?エンドフェイズ開始時、(?P<x>[^。]+)(?:。|$)', delay)
    add(r'相手は手札を全て公開' + V('する', 'し') + END, lambda m: {'op': 'reveal'})
    # 드로우
    add(r'(?:あなたは)?(?P<n>\d+)枚引' + V('く', 'き', 'いて') + MAY + END,
        lambda m: {'op': 'draw', 'n': int(m.group('n')), **({'may': 1} if m.group('may') else {})})
    add(r'相手は(?P<n>\d+)枚引' + V('く', 'き') + END, lambda m: {'op': 'draw', 'n': int(m.group('n')), 'who': 'opp'})
    # 스카웃
    add(r'スカウト(?P<n>\d+)(?:する|し|を行う)?' + END, lambda m: {'op': 'scout', 'n': int(m.group('n'))})
    # 패 버리기
    add(r'(?:あなたは)?(?:あなたの)?手札(?:から|を)(?P<n>\d+)枚(?:選んで)?ドロップ' + V('する', 'し') + MAY + END,
        lambda m: {'op': 'discard', 'n': int(m.group('n')), **({'may': 1} if m.group('may') else {})})
    add(r'相手は(?:自身の)?手札を(?P<n>\d+)枚(?:選んで)?ドロップ' + V('する', 'し') + END,
        lambda m: {'op': 'discard', 'n': int(m.group('n')), 'who': 'opp'})
    # 덱 위에서 드롭
    add(r'あなたの山札(?:を|の)上から(?P<n>\d+)枚(?:を)?ドロップ' + V('する', 'し') + MAY + END,
        lambda m: {'op': 'mill', 'n': int(m.group('n')), **({'may': 1} if m.group('may') else {})})
    # 라이프 추가
    add(r'あなたの山札をシャッフル(?:して|し、)(?:山札を|その)?上から(?P<n>\d+)枚(?:を)?ライフ(?:ゾーン)?の先頭に置' + V('く', 'き') + END,
        lambda m: {'op': 'lifeTop', 'n': int(m.group('n')), 'shuffle': 1})
    add(r'あなたの山札(?:を|の)上から(?P<n>\d+)枚(?:を)?ライフ(?:ゾーン)?の先頭に置' + V('く', 'き') + END,
        lambda m: {'op': 'lifeTop', 'n': int(m.group('n'))})
    add(r'あなたの山札をシャッフル' + V('する', 'し') + END, lambda m: {'op': 'shuffle'})
    # 덱 위에서 에너지
    add(r'あなたの山札(?:を|の)上から(?P<n>\d+)枚(?:を)?エナジーゾーンに置' + V('く', 'き') + END,
        lambda m: {'op': 'deckEnergy', 'n': int(m.group('n'))})
    # 라이프 맨 앞 -> 에너지 / 패
    add(r'あなたのライフの先頭(?:の(?P<n>\d+)枚)?をエナジーゾーンに置' + V('く', 'き') + END,
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
        else:
            noun_filter(f, m.group('noun'))
        dest = 'field' if '登場' in m.group('v') else 'life' if 'ライフ' in m.group('v') else 'hand'
        zone = {'ドロップゾーン': 'drop', '手札': 'hand', 'エナジーゾーン': 'energy', 'エナジー': 'energy'}[m.group('zone')]
        if zone == dest:
            return None
        st = {'op': 'pick', 'from': zone, 'to': dest, 'f': f, 'n': int(m.group('n')), 'upto': 1 if m.group('upto') else 0}
        if m.group('may'):
            st['upto'] = 1
        return st
    add(r'(?:あなたの)?(?P<zone>ドロップゾーン|手札|エナジーゾーン|エナジー)(?:の|から)(?P<d>[^、。を]*?)' + NOUN[:-1] + r'|バスターアイコン)を(?P<n>\d+)枚(?P<upto>まで)?(?:選んで)?(?:公開して)?(?P<v>手札に加え(?:る|)|登場させ(?:る|)|ライフの先頭に置(?:く|き))' + MAY + END, pick)

    # 덱 위 N장 보고 고르기
    def look(m):
        f = parse_desc(m.group('d') or '')
        if f is None:
            return None
        noun_filter(f, m.group('noun'))
        dest = 'field' if '登場' in m.group('v') else 'hand'
        rest = {'ドロップ': 'drop', '山札の下に置': 'bottom', '望む順で山札の下に置': 'bottom', '山札の上に置': 'top', '望む順で山札の上に置': 'top'}[m.group('r')]
        return {'op': 'look', 'n': int(m.group('n')), 'f': f, 'k': int(m.group('k')), 'to': dest, 'rest': rest}
    add(r'あなたの山札(?:を|の)上から(?P<n>\d+)枚見て、その中(?:から|の)(?P<d>[^、。を]*?)' + NOUN + r'を(?P<k>\d+)枚まで(?:公開して)?(?P<v>手札に加え|登場させ)、残りを(?P<r>ドロップ|望む順で山札の下に置|山札の下に置|望む順で山札の上に置|山札の上に置)' + V('する', 'く', 'し', 'き') + END, look)
    return P


EFF = eff_patterns()

# ---------- 조건 ----------
def parse_cond(t):
    """'あなたのライフがレッドゾーン' 같은 조건문 (なら/中/で 앞부분) -> dict | None"""
    t = t.strip('、')
    C = [
        (r'あなたのライフがレッドゾーン', lambda m: {'red': 1}),
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
        (r'このコマンドが手札からプレイされた', lambda m: {'fromHand': 1}),
        (r'このコマンドがトリガーでプレイされた', lambda m: {'fromTrigger': 1}),
        (r'あなたのテリトリーが無い|あなたのテリトリーが開放されていない', lambda m: {'terr': 0}),
        (r'(?P<d>[^、。]*?)' + NOUN + r'がいる', None),
        (r'(?P<d>[^、。]*?)' + NOUN + r'がいない', 'none'),
    ]
    parts = re.split(r'(?:で、|かつ、|、かつ|かつ)', t)
    out = []
    for p in parts:
        for rx, fn in C:
            m = re.fullmatch(rx, p)
            if m:
                if fn is None or fn == 'none':
                    f = parse_desc(m.group('d'))
                    if f is None:
                        return None
                    f = noun_filter(f, m.group('noun'))
                    out.append({'exists': f} if fn is None else {'none': f})
                else:
                    out.append(fn(m))
                break
        else:
            return None
    return out


def parse_effects(t):
    """효과 문장들 -> 단계 목록 | None"""
    steps = []
    t = t.strip()
    while t:
        t = t.lstrip('。、 ')
        if not t:
            break
        # 조건 분기: 「Xなら、」
        m = re.match(r'(?P<c>[^。]*?)(?:なら|ならば|場合)、', t)
        if m and not re.search(r'対象と|ダメージ|を\d+枚', m.group('c')):
            c = parse_cond(m.group('c'))
            if c is not None:
                rest = t[m.end():]
                # 같은 문장 끝(。)까지를 조건 안쪽으로
                j = rest.find('。')
                inner, t = (rest, '') if j < 0 else (rest[:j], rest[j + 1:])
                alt = inner.startswith('代わりに')
                sub = parse_effects(inner[4:] if alt else inner)
                if sub is None:
                    return None
                if alt:
                    if not steps:
                        return None
                    prev = steps.pop()
                    steps.append({'op': 'if', 'c': c, 'then': sub, 'else': [prev]})
                else:
                    steps.append({'op': 'if', 'c': c, 'then': sub})
                continue
        for rx, fn in EFF:
            m = rx.match(t)
            if m:
                r = fn(m)
                if r:
                    steps.extend(r if isinstance(r, list) else [r])
                    t = t[m.end():]
                    break
        else:
            return None
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
    (r'このユニットが【ブライト】した時', ('bright', 'self', None)),
    (r'このユニットが総コスト(?P<n>\d+)以下のユニットとバトルする時', ('battle', 'self', 'vsCostLE')),
    (r'このユニットのアタック終了時', ('attackEnd', 'self', None)),
    (r'いずれかのアタックフェイズに相手のユニットが登場した時', ('enter', 'opp', {'attackPhase': 1})),
]


def parse_trigger(t):
    """'あなたのテリトリー開放中にこのユニットが登場した時' -> (on, src, conds) | None"""
    conds = []
    m = re.match(r'(?P<c>あなたの(?:称号「[^」]+」の)?テリトリー(?:開放中|が開放されていて)|あなたのライフがレッドゾーンで)(?:に|、|で、|で)?', t)
    if m:
        c = parse_cond(m.group('c').replace('が開放されていて', '開放中').rstrip('で'))
        if c is None:
            return None
        conds += c
        t = t[m.end():]
    for rx, (on, src, extra) in TRIGGERS:
        m = re.fullmatch(rx, t)
        if m:
            if extra == 'vsCostLE':
                conds.append({'vsCostLE': int(m.group('n'))})
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
            if fn == 'desc':
                f = parse_desc(m.group('d'))
                if f is None:
                    return None
                if m.group('noun'):
                    noun_filter(f, m.group('noun'))
                return [{'op': 'discard', 'n': int(m.group('n')), 'f': f}]
            return fn(m)
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
    conds = []
    m = re.match(r'(?P<c>.+?)(?:なら|中|中で|時)、', t)
    if m:
        c = parse_cond(m.group('c').rstrip('で'))
        if c is not None:
            conds = c
            t = t[m.end():]
    out = []
    for sent in [x for x in t.split('。') if x]:
        m = re.fullmatch(r'(?P<to>[^、。]*?)の(?P<mods>(?:パワー|ヒット)を[+-]\d+(?:、(?:パワー|ヒット)を[+-]\d+)?)(?:する)?', sent)
        if m:
            to = subj(m.group('to'))
            if not to:
                return None
            for k, v in re.findall(r'(パワー|ヒット)を([+-]\d+)', m.group('mods')):
                out.append({'op': 'pow' if k == 'パワー' else 'hit', 'n': int(v), 'to': to})
            continue
        m = re.fullmatch(r'(?P<to>[^、。]*?)は【(?P<k>デコイ|ブリッツ|バーサーク)】を得て、(?P<mods>(?:パワー|ヒット)を[+-]\d+)', sent)
        if m:
            to = subj(m.group('to'))
            if not to:
                return None
            out.append({'op': 'kw', 'kw': {'デコイ': 'decoy', 'ブリッツ': 'blitz', 'バーサーク': 'berserk'}[m.group('k')], 'to': to})
            for k, v in re.findall(r'(パワー|ヒット)を([+-]\d+)', m.group('mods')):
                out.append({'op': 'pow' if k == 'パワー' else 'hit', 'n': int(v), 'to': to})
            continue
        m = re.fullmatch(r'(?P<to>[^、。]*?)(?:は|では)(?P<k>アタックとブロックができない|アタックできない|アタックができない|ブロックができない|ブロックできない|ブロックされない)', sent)
        if m:
            to = subj(m.group('to'))
            if not to:
                return None
            ks = {'アタックとブロックができない': ['noAttack', 'noBlock'], 'アタックできない': ['noAttack'], 'アタックができない': ['noAttack'], 'ブロックができない': ['noBlock'], 'ブロックできない': ['noBlock'], 'ブロックされない': ['unblockable']}[m.group('k')]
            out += [{'op': 'kw', 'kw': k, 'to': to} for k in ks]
            continue
        m = re.fullmatch(r'(?P<to>[^、。]*?)は【(?P<k>デコイ|ブリッツ|バーサーク)】を得る', sent)
        if m:
            to = subj(m.group('to'))
            if not to:
                return None
            out.append({'op': 'kw', 'kw': {'デコイ': 'decoy', 'ブリッツ': 'blitz', 'バーサーク': 'berserk'}[m.group('k')], 'to': to})
            continue
        return None
    return {'if': conds, 'do': out} if out else None


# ---------- 카드 전체 ----------
def split_once(body):
    once = 0
    for rx in [r'この能力は(?:各|1)ターン(?:に)?1回(?:まで)?(?:しか)?発動(?:でき|し)(?:る|ない)。?', r'\(この能力は各ターン1回まで発動できる\)']:
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
    skill = None
    for x in lines:
        if x.startswith('【スキル】'):
            skill = parse_skill(x)
    abs_, done = [], set()
    i = 0
    while i < len(lines):
        ln = lines[i]
        # 「以下を1つ行う」 + ・줄들
        if re.fullmatch(r'以下を1つ(?:選んで)?行う。?', ln) or re.search(r'以下を1つ(?:選んで)?行う。?$', ln):
            head = re.sub(r'以下を1つ(?:選んで)?行う。?$', '', ln)
            j = i + 1
            opts = []
            while j < len(lines) and lines[j].startswith('・'):
                opts.append(parse_effects(lines[j][1:]))
                j += 1
            ok = opts and all(o is not None for o in opts)
            if ok:
                r = parse_body(head + '__CHOOSE__', d, skill)
                if r:
                    for st in r['do']:
                        if st.get('op') == 'choose':
                            st['opts'] = opts
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
        if ln in ('【魔法】',):
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'⁅永続⁆このカードは全(?:ての)?領域で称号「([^」]+)」(?:と称号「([^」]+)」)?を持つ。?', ln)
        if m:
            d['titles'] = list(dict.fromkeys((d.get('titles') or []) + [x for x in m.groups() if x]))
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
        r = parse_body(ln, d, skill)
        if r:
            r['li'] = [i]
            abs_.append(r)
            done.add(i)
        i += 1
    return abs_, done


def parse_body(ln, d, skill):
    ln = re.sub(r'\((?:[^()]*)\)$', '', ln).strip()   # 끝의 괄호 설명문(리마인더) 제거
    tags = re.findall(r'⁅(自動|永続|保持称号開放中|自|永)⁆', ln)
    body = re.sub(r'^(?:⁅(?:自動|永続|保持称号開放中|自|永)⁆)+', '', ln).strip()
    conds = [{'hold': 1}] if '保持称号開放中' in tags else []
    body, once = split_once(body)
    if '永続' in tags or '永' in tags:
        pm = parse_perm(body.rstrip('。'))
        if not pm:
            return None
        return {'k': 'perm', 'if': conds + pm['if'], 'do': pm['do']}
    if '自動' in tags or '自' in tags:
        m = re.match(r'(?P<t>(?:あなたの(?:称号「[^」]+」の)?テリトリー(?:が開放されていて|開放中で)、)?[^、]*?時)、', body)
        if not m:
            return None
        tr = parse_trigger(m.group('t'))
        if not tr:
            return None
        on, src, tc, extra = tr
        rest = body[m.end():]
        cost = None
        mc = re.match(r'(?P<c>[^。]*?)(?:ことで|事で|で)、', rest)
        if mc:
            cost = parse_cost(mc.group('c'), skill)
            if cost:
                rest = rest[mc.end():]
            elif '【スキル】' in mc.group('c'):
                return None
        if rest.startswith('【スキル】発動で、') or rest.startswith('【スキル】を発動することで、'):
            if not skill:
                return None
            cost = skill
            rest = rest.split('、', 1)[1]
        steps = parse_effects(rest)
        if steps is None:
            return None
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
