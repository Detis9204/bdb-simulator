# -*- coding: utf-8 -*-
"""
카드 이미지 용량 줄이기: 투명 채널을 없애고(병합) 다시 변환

공식 썸네일 PNG에 투명 채널이 붙어 있어, WebP마다 압축 안 된 투명 정보(약 80KB)가 같이 저장됐음.
그림 자체는 13~21KB. 원본 PNG(images_raw/src, src_back)에서 다시
  layer.flattenImage (병합: 투명 채널 제거) → image.imageSize (가로 240px)
를 PhotoCraft batch로 적용해 images/ 를 덮어씀.

실행 (저장소 최상위 폴더에서):  python collector/bdb_images_flatten.py
먼저 한 장으로 투명 채널이 없어졌는지 확인한 뒤 전체에 적용.
"""
import json, os, struct, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "images_raw")
OUT = os.path.join(ROOT, "images")
PC = os.environ.get("BDB_PHOTOCRAFT", r"D:\Utill\photocraft-0.10.0\photocraft-cli.exe")
QUALITY = "80"

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass


def chunks(path):
    b = open(path, "rb").read(); i, out = 12, []
    while i + 8 <= len(b):
        n = struct.unpack("<I", b[i + 4:i + 8])[0]; out.append(b[i:i + 4].decode("latin1")); i += 8 + n + (n & 1)
    return out


def pc(*args, timeout=600):
    r = subprocess.run([PC, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, (r.stderr or r.stdout).strip()


def main():
    man_p = os.path.join(ROOT, "data", "images_manifest.json")
    man = json.load(open(man_p, encoding="utf-8"))
    size = man["params"]
    src, srcb = os.path.join(RAW, "src"), os.path.join(RAW, "src_back")
    if not os.path.isdir(src) or not os.listdir(src):
        print("images_raw/src 가 없어요. 먼저 python collector/bdb_images.py 를 실행해 주세요."); sys.exit(1)
    sample = os.path.join(src, sorted(os.listdir(src))[0])
    test = os.path.join(RAW, "_flat_test.webp")
    steps = None
    for flat in ("layer.flattenImage", "layer.new.backgroundFromLayer"):
        if os.path.exists(test): os.remove(test)
        code, msg = pc("run", sample, "--cmd", flat, "--params", "{}", "--cmd", "image.imageSize", "--params", json.dumps(size), "--out", test, "--quality", QUALITY)
        if code != 0 or not os.path.exists(test):
            print(f"시험 {flat}: 실패 ({msg[:200]})"); continue
        ch = chunks(test)
        print(f"시험 {flat}: {os.path.getsize(test) // 1024}KB, 구성 {ch}")
        if "ALPH" not in ch:
            steps = [[flat, {}], ["image.imageSize", size]]; break
    if not steps:
        print("투명 채널을 없애는 방법을 찾지 못했어요. 이 출력 내용을 알려 주세요."); sys.exit(1)

    acts = os.path.join(RAW, "_actions_flat.json")
    json.dump(steps, open(acts, "w", encoding="utf-8"))
    for s, o in ((src, OUT), (srcb, os.path.join(OUT, "back"))):
        if not os.path.isdir(s) or not os.listdir(s):
            continue
        os.makedirs(o, exist_ok=True)
        t0 = time.time()
        print(f"일괄 변환 {len(os.listdir(s))}장 → {os.path.relpath(o, ROOT)}")
        code, msg = pc("batch", "--actions", acts, "--in", s, "--out", o, "--format", "webp", "--quality", QUALITY, timeout=6 * 3600)
        if code != 0:
            print(f"일괄 변환 실패: {msg[-1500:]}"); sys.exit(1)
        print(f"  {time.time() - t0:.0f}초")
    files = [os.path.join(OUT, f) for f in os.listdir(OUT) if f.endswith(".webp")]
    files += [os.path.join(OUT, "back", f) for f in os.listdir(os.path.join(OUT, "back"))] if os.path.isdir(os.path.join(OUT, "back")) else []
    left = sum(1 for f in files if "ALPH" in chunks(f))
    total = sum(os.path.getsize(f) for f in files)
    man["steps"] = steps; man["quality"] = int(QUALITY)
    json.dump(man, open(man_p, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"\n끝! {len(files)}장, 합계 {total / 1e6:.0f} MB, 투명 채널이 남은 파일 {left}장")
    print('이제  git add images data  →  git commit -m "카드 이미지 용량 줄이기"  →  git push')


if __name__ == "__main__":
    main()
