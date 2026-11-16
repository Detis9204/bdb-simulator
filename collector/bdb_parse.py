# -*- coding: utf-8 -*-
"""
data/cards/<id>.json (공식 상세 창 원문) + data/tags.json (필터별 카드 목록)
→ data/cards.json (시뮬레이터가 쓰는 정리된 카드 목록)

실행 (저장소 최상위 폴더에서):  python collector/bdb_parse.py
"""
import json, os, re, html as H, glob
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# 검색 필터 라벨 (공식 카드 검색 화면 기준. 수집 때 라벨을 못 읽은 경우를 대비해 고정)
COLLAB = {1: "リコリス・リコイル", 2: "天元突破グレンラガン", 3: "ぼっち・ざ・ろっく！", 4: "NieR:Automata Ver1.1a",
          5: "アニメ「青春ブタ野郎」シリーズ", 6: "アニメ「ライザのアトリエ ～常闇の女王と秘密の隠れ家～」", 7: "「冴えない彼女の育てかた」シリーズ",
          8: "〈物語〉シリーズ", 10: "乃木坂46", 11: "Fate/Grand Order", 12: "TVアニメ「その着せ替え人形は恋をする」",
          13: "劇場版「空の境界」", 15: "TVアニメ「負けヒロインが多すぎる！」", 16: "TVアニメ「ATRI -My Dear Moments-」",
          17: "キルラキル", 18: "アニメ「かぐや様は告らせたい」シリーズ", 19: "Angel Beats!", 20: "『ディズニー ツイステッドワンダーランド』",
          21: "魔法少女まどか☆マギカ Magia Exedra", 22: "アニメ「魔法科高校の劣等生」", 23: "HUNDRED LINE -最終防衛学園-",
          24: "櫻坂46", 25: "TVアニメ『グノーシア』", 26: "TVアニメ『NEEDY GIRL OVERDOSE』", 27: "TVアニメ『上伊那ぼたん、酔へる姿は百合の花』"}
TITLE = {41: 'バディ', 45: '喫茶', 46: 'リコリス', 47: '大グレン団', 48: '螺旋', 56: 'ぼっち', 57: '結束バンド', 65: '青春', 66: '思春期症候群', 68: 'ヨルハ', 69: 'アンドロイド', 75: 'ライザのアトリエ', 76: 'ひと夏の冒険', 77: 'blessing software', 78: '冴えカノ', 79: '3期生', 80: '4期生', 81: '5期生', 82: '乃木坂', 85: '吸血鬼', 86: '怪異譚', 87: '閑話休題', 88: 'STARRY', 91: 'カルデア', 92: 'Lostbelt No.6', 93: '妖精國', 94: 'コスキュン', 95: '着せ恋', 96: 'マ!?', 97: '異能', 98: '伽藍の洞', 99: 'サルベージ', 100: '沈みゆく世界', 101: '文芸部', 102: '幼馴染', 103: '泥棒猫', 104: 'キルカ、キラレルカ', 105: '生命戦維', 106: '本能字学園', 107: '恋愛は戦!!', 108: '告白', 109: '秀知院学園', 110: 'Angel Player', 111: 'SSS/ガルデモ', 112: 'SSS', 113: 'ガルデモ', 114: 'カルデア', 115: 'カルデア/ミクトラン', 116: 'ミクトラン', 117: '青春/思春期症候群', 118: '思春期症候群', 119: '青春', 120: 'ハーツラビュル', 121: 'サバナクロー', 122: 'オクタヴィネル', 123: 'スカラビア', 124: 'ポムフィオーレ', 125: 'イグニハイド', 126: 'ディアソムニア', 127: '魔法少女', 128: 'リコリス', 129: '喫茶', 130: 'リコリス/バディ', 131: 'コスキュン', 132: '着せ恋', 133: '着せ恋/マ!?', 134: '一科生/二科生', 135: '二科生', 136: '一科生', 137: '櫻坂', 138: '最終防衛学園', 139: '銀の鍵', 140: '銀の鍵/星間航行船D.Q.O.', 141: '星間航行船D.Q.O.', 142: 'サマー', 143: 'カルデア/サマー', 144: 'ハーツラビュル', 145: 'オンボロ寮', 146: 'サバナクロー', 147: 'オクタヴィネル', 148: 'スカラビア', 149: 'ポムフィオーレ', 150: 'イグニハイド', 151: 'ディアソムニア', 152: '#夢見る', 153: '青春/思春期症候群', 154: '青春', 155: '青春/#夢見る', 156: '超てんちゃん', 157: 'カラマーゾフ', 158: '百合の花', 159: '乾杯'}
COLOR = {1: "black", 3: "blue", 2: "white", 4: "red"}
COST_COLOR = {"黒": "black", "青": "blue", "白": "white", "赤": "red", "無": "none"}
ABILITY = {1: "decoy", 2: "blitz", 3: "berserk", 4: "pow3", 5: "pow5", 6: "hit1", 7: "hit2", 8: "draw1", 9: "draw2",
           10: "scout1", 11: "scout2", 12: "life1", 13: "bright3", 14: "bright5"}


def text_of(fragment):
    """HTML 조각 → 줄 목록"""
    s = re.sub(r"<br\s*/?>", "\n", fragment)
    s = re.sub(r"</p>\s*<p>", "\n", s)
    s = H.unescape(re.sub(r"<[^>]+>", "", s))
    return [" ".join(x.split()) for x in s.split("\n") if x.strip()]


def parse_card(cid, h):
    c = {"id": cid}
    m = re.search(r"data-decks-player-deck-card-param='([^']+)'", h) or re.search(r'data-decks-player-deck-card-param="([^"]+)"', h)
    meta = json.loads(H.unescape(m.group(1))) if m else {}
    tags = [H.unescape(x).strip() for x in re.findall(r'p-deck-modal-card-info__tag-item">([^<]*)<', h)]
    c["name"] = H.unescape((re.search(r'p-deck-modal-card-info__name">([^<]*)<', h) or re.search(r'p-deck-modal-card-name">([^<]*)<', h)).group(1)).strip()
    c["typeLine"] = tags[0] if tags else ""
    c["attr"] = [a for t in tags[1:] for a in t.split("/") if a and a != "属性なし"]
    d = re.search(r'p-deck-modal-card-info__description">(.*?)</div>', h, re.S)
    c["text"] = text_of(d.group(1)) if d else []
    items = dict((H.unescape(k).strip(), v) for k, v in re.findall(r'<label>([^<]+)</label>\s*(.*?)\s*</div>', h, re.S))
    def plain(k):
        v = items.get(k)
        return H.unescape(re.sub(r"<[^>]+>", "", v)).strip() if v is not None else None
    for k, key in (("パワー", "power"), ("ヒット", "hit")):
        v = plain(k)
        if v not in (None, "", "-"):
            try: c[key] = int(v)
            except ValueError: c[key] = v
    cost = plain("コスト") or ""
    c["costRaw"] = cost
    parts = re.findall(r"\((.)(\d+)\)", cost)
    colors = [COST_COLOR.get(col, col) for col, n in parts if col != "無"]
    c["cost"] = sum(int(n) for _, n in parts)
    c["color"] = colors[0] if colors else "none"
    if len(set(colors)) > 1: c["colors"] = sorted(set(colors))
    c["colorCost"] = sum(int(n) for col, n in parts if col != "無") if colors else 0
    c["product"] = plain("収録弾")
    c["rarity"] = plain("レアリティ")
    c["abilityIconImgs"] = re.findall(r"uploads/ability/([0-9a-f]+)/", h)
    # 종류·트리거 (공식 JSON 플래그 기준)
    c["type"] = "territory" if meta.get("territory") else "unit" if meta.get("unit") else "command" if meta.get("action") else (c["typeLine"].split("/")[0] or "unknown")
    if meta.get("ace"): c["sub"] = "ace"
    c["trigger"] = "buster" if meta.get("baster") else "shot" if meta.get("shot") else None
    img = (meta.get("image_path") or {})
    c["img"] = img.get("url"); c["thumb"] = (img.get("thumb") or {}).get("url")
    back = re.search(r'(https://[^"\']+/territory_image_path\.png[^"\'&\s]*)', h)
    if back: c["imgBack"] = back.group(1)
    return c


def main():
    tags = json.load(open(os.path.join(DATA, "tags.json"), encoding="utf-8"))
    filters = json.load(open(os.path.join(DATA, "filters.json"), encoding="utf-8"))
    flabel = {f'{f["key"]}={f["value"]}': f["label"] for f in filters}
    by = defaultdict(lambda: defaultdict(list))
    for k, v in tags.items():
        key, val = k.split("=", 1)
        for i in v["ids"]:
            by[int(i)][key].append(val)
    cards = []
    for fp in sorted(glob.glob(os.path.join(DATA, "cards", "*.json")), key=lambda p: int(os.path.basename(p)[:-5])):
        raw = json.load(open(fp, encoding="utf-8"))
        c = parse_card(raw["id"], raw["html"])
        t = by.get(c["id"], {})
        col = [int(x) for x in t.get("collaboration_id", [])]
        c["collab"] = col[0] if col else None
        c["collabName"] = COLLAB.get(c["collab"])
        # 칭호: 「A/B」처럼 묶인 항목은 낱개 칭호로 나눔 (테리토리 개방 판정은 낱개 칭호 기준)
        c["titles"] = sorted({n for x in t.get("card_title_id", []) for n in (flabel.get(f"card_title_id={x}") or TITLE.get(int(x), x)).split("/")})
        c["titleIds"] = sorted(int(x) for x in t.get("card_title_id", []))
        c["icons"] = sorted(ABILITY.get(int(x), x) for x in t.get("ability_id", []))
        if "color_id" in t and not c.get("colors"):
            cols = [COLOR[int(x)] for x in t["color_id"]]
            if len(cols) > 1: c["colors"] = cols
        cards.append(c)
    # 같은 카드의 패럴렐(그림·레어리티만 다른 판) 묶기: 이름·텍스트·수치가 같으면 같은 카드
    groups = defaultdict(list)
    for c in cards:
        groups[(c["name"], tuple(c["text"]), c.get("power"), c.get("hit"), c["costRaw"], c["typeLine"])].append(c)
    for g in groups.values():
        base = min(g, key=lambda c: c["id"])
        for c in g:
            c["base"] = base["id"]
    with open(os.path.join(DATA, "cards.json"), "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, separators=(",", ":"))
    print(f"카드 {len(cards)}장 (패럴렐을 묶으면 {len(groups)}종)")


if __name__ == "__main__":
    main()
