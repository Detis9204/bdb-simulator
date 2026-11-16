# -*- coding: utf-8 -*-
"""
게시용 카드 이미지 묶음 만들기

images/<id>.webp, images/back/<id>.webp 를 작품별로 이어 붙여 dist/packs/c<작품ID>.bin 으로 만들고,
카드 ID → (묶음, 시작 위치, 길이) 색인을 dist/packs/index.json 에 저장.
게시 페이지는 외부 이미지를 못 불러오지만 자기 파일은 불러올 수 있어서, 필요한 작품 묶음만 받아
잘라 쓰는(blob 주소) 방식으로 이미지를 보여줌. 파일 수천 개 대신 묶음 수십 개만 올리면 됨.

실행 (저장소 최상위 폴더에서):  python collector/build_packs.py
"""
import json, os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "images")
OUT = os.path.join(ROOT, "dist", "packs")
MAX_PACK = 15 * 1024 * 1024     # 게시 파일 한 개 최대 20MB보다 넉넉히 작게


def main():
    cards = json.load(open(os.path.join(ROOT, "data", "cards.json"), encoding="utf-8"))
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        os.remove(os.path.join(OUT, f))
    groups = defaultdict(list)
    for c in cards:
        groups[c.get("collab") or 0].append(c)
    index = {"v": 1, "packs": {}, "img": {}}
    total = 0
    for col, cs in sorted(groups.items()):
        part, buf, n = 0, bytearray(), 0
        def flush():
            nonlocal part, buf
            if not buf:
                return
            name = f"c{col}" + (f"_{part}" if part else "") + ".pack.webp"
            with open(os.path.join(OUT, name), "wb") as f:
                f.write(buf)
            index["packs"][name[:-10]] = name
            part += 1
            buf = bytearray()
        for c in sorted(cs, key=lambda c: c["id"]):
            for key, path in ((str(c["id"]), os.path.join(IMG, f'{c["id"]}.webp')), ("b" + str(c["id"]), os.path.join(IMG, "back", f'{c["id"]}.webp'))):
                if not os.path.exists(path):
                    continue
                data = open(path, "rb").read()
                if len(buf) + len(data) > MAX_PACK:
                    flush()
                pack = f"c{col}" + (f"_{part}" if part else "")
                index["img"][key] = [pack, len(buf), len(data)]
                buf += data; n += 1; total += len(data)
        flush()
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, separators=(",", ":"))
    print(f"묶음 {len(index['packs'])}개, 이미지 {len(index['img'])}장, 합계 {total / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
