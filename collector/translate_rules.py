"""정형화된 카드 문장을 규칙으로 한국어로 바꾼다 (사람이 번역한 db/ko_lines.json이 우선)."""
import re, unicodedata

ATTR = {'ハート': '하트', 'スペード': '스페이드', 'スぺード': '스페이드', 'ダイヤ': '다이아', 'クラブ': '클럽'}
KW = {'デコイ': '디코이', 'ブリッツ': '블리츠', 'バーサーク': '버서크', 'ブライト': '브라이트'}


def n(t):
    return unicodedata.normalize('NFKC', t)


def attrs(s):
    return '/'.join(ATTR.get(a, a) for a in s.split('/'))


COND = [
    (r'あなたのテリトリーが開放されているなら、', '내 테리토리가 개방되어 있다면, '),
    (r'あなたのテリトリー開放中なら、', '내 테리토리 개방 중이라면, '),
    (r'あなたのテリトリー開放中、', '내 테리토리 개방 중, '),
    (r'あなたのライフがレッドゾーンなら、', '내 라이프가 레드 존이라면, '),
    (r'あなたのターン中、', '내 턴 동안, '),
    (r'相手のターン中、', '상대 턴 동안, '),
]
EFFECT = [
    (r'このユニットのパワーを\+(\d+)。', lambda m: f'이 유닛의 파워 +{m.group(1)}.'),
    (r'このユニットのヒットを\+(\d+)。', lambda m: f'이 유닛의 히트 +{m.group(1)}.'),
    (r'このユニットは【(\S+?)】を得る。', lambda m: f'이 유닛은 【{KW.get(m.group(1), m.group(1))}】을(를) 얻는다.'),
]
AUTO_WHEN = [
    (r'このユニットが手札から登場した時、', '이 유닛이 패에서 등장했을 때, '),
    (r'このユニットが登場した時、', '이 유닛이 등장했을 때, '),
    (r'このユニットがフィールドからドロップした時、', '이 유닛이 필드에서 드롭되었을 때, '),
    (r'このユニットがバトルする時、', '이 유닛이 배틀할 때, '),
]
AUTO_DO = [
    (r'スカウト(\d)する。', lambda m: f'스카웃 {m.group(1)}을 한다.'),
    (r'(\d)枚引く。', lambda m: f'{m.group(1)}장 뽑는다.'),
    (r'あなたの山札をシャッフル(?:して|し、山札を)上から(\d)枚ライフ(?:ゾーン)?の先頭に置く。', lambda m: f'내 덱을 섞고 위에서 {m.group(1)}장을 라이프 맨 앞에 놓는다.'),
    (r'あなたに(\d)ダメージ。', lambda m: f'나에게 {m.group(1)} 데미지.'),
]


def rule_translate(line):
    t = n(line).replace('パワーえ', 'パワー')
    if t == '・アイコン能力':
        return '・아이콘 능력'
    m = re.fullmatch(r'【ブライト(\d+):(.+?)】', t)
    if m:
        return f'【브라이트 {m.group(1)}: {attrs(m.group(2))}】'
    m = re.fullmatch(r'【(デコイ|ブリッツ|バーサーク)】', t)
    if m:
        return f'【{KW[m.group(1)]}】'
    m = re.fullmatch(r'【スカウト(\d):(登場|ドロップ|バトル)時】', t)
    if m:
        return f'【스카웃 {m.group(1)}: {dict(登場="등장", ドロップ="드롭", バトル="배틀")[m.group(2)]} 시】'
    m = re.fullmatch(r'⁅永(?:続)?⁆(.*)', t) or (re.fullmatch(r'(あなたのテリトリー.*)', t))
    if m:
        body = m.group(1)
        for a, b in COND:
            if body.startswith(a):
                rest = body[len(a):]
                for pat, f in EFFECT:
                    mm = re.fullmatch(pat, rest)
                    if mm:
                        return '[영속] ' + b + f(mm)
    m = re.fullmatch(r'⁅自(?:動)?⁆(.*)', t)
    if m:
        body = m.group(1)
        for a, b in AUTO_WHEN:
            if body.startswith(a):
                rest = body[len(a):]
                for pat, f in AUTO_DO:
                    mm = re.fullmatch(pat, rest)
                    if mm:
                        return '[자동] ' + b + f(mm)
    return None
