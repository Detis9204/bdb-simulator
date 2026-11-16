# -*- coding: utf-8 -*-
"""
카드 이미지 준비 (2단계): 공식 썸네일·테리토리 뒷면을 받고, PhotoCraft로 작게 줄여 images/에 WebP로 저장

  1) data/cards.json 의 썸네일 주소로 images_raw/thumb/<id>.png, 테리토리 뒷면은 images_raw/back/<id>.png 로 받음
     (썸네일이 목표 크기보다 작으면 1단계에서 받은 원본 images_raw/<id>.png 를 대신 씀)
  2) PhotoCraft에서 image.imageSize 명령의 매개변수를 직접 조회하고(data/photocraft_imageSize.json),
     한 장으로 시험해 결과 크기를 info로 확인한 뒤에만 전체에 적용
  3) photocraft-cli batch 로 폴더 전체를 가로 240px WebP(품질 80)로 변환 → images/<id>.webp, images/back/<id>.webp

실행 (저장소 최상위 폴더에서):  python collector/bdb_images.py
끝나면:  git add images data  →  git commit  →  git push
"""
import json, os, re, sys, shutil, struct, subprocess, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(ROOT, "images_raw")
OUT = os.path.join(ROOT, "images")
PC = os.environ.get("BDB_PHOTOCRAFT", r"D:\Utill\photocraft-0.10.0\photocraft-cli.exe")
TW = 240            # 목표 가로 크기(px). 게임 화면 카드 104px의 2배 이상, 설명 패널에도 충분
QUALITY = "80"
UA = "Mozilla/5.0 (personal deck practice tool)"

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass


def log(*a):
    print(*a, flush=True)


def get(url, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            time.sleep(0.1)
            return data
        except Exception as e:
            if k == tries - 1:
                raise
            time.sleep(2 * (k + 1))


def img_size(path):
    """PNG/JPEG/WebP 머리 부분만 읽어 (가로, 세로)"""
    with open(path, "rb") as f:
        head = f.read(64 * 1024)
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", head[16:24])
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        if head[12:16] == b"VP8X":
            return 1 + int.from_bytes(head[24:27], "little"), 1 + int.from_bytes(head[27:30], "little")
        if head[12:16] == b"VP8 ":
            w, h = struct.unpack("<HH", head[26:30]); return w & 0x3FFF, h & 0x3FFF
        if head[12:16] == b"VP8L":
            b = int.from_bytes(head[21:25], "little"); return (b & 0x3FFF) + 1, ((b >> 14) & 0x3FFF) + 1
    if head[:2] == b"\xff\xd8":
        i = 2
        while i < len(head) - 9:
            if head[i] != 0xFF: i += 1; continue
            mk = head[i + 1]
            if mk in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", head[i + 5:i + 9]); return w, h
            i += 2 + struct.unpack(">H", head[i + 2:i + 4])[0]
    return None


def pc(*args, timeout=600):
    r = subprocess.run([PC, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, r.stdout, r.stderr


# ── 1. 받기 ──────────────────────────────────────────────
def download(cards):
    os.makedirs(os.path.join(RAW, "thumb"), exist_ok=True)
    os.makedirs(os.path.join(RAW, "back"), exist_ok=True)
    jobs = []
    for c in cards:
        if c.get("thumb"):
            jobs.append((c["thumb"], os.path.join(RAW, "thumb", f'{c["id"]}.png')))
        if c.get("imgBack"):
            jobs.append((c["imgBack"].replace("/territory_image_path", "/thumb_territory_image_path"), os.path.join(RAW, "back", f'{c["id"]}.png'), c["imgBack"]))
    todo = [j for j in jobs if not os.path.exists(j[1])]
    log(f"썸네일·뒷면 {len(todo)}장 받는 중 (전체 {len(jobs)}장)")

    def run(j):
        url, path = j[0], j[1]
        try:
            data = get(url)
        except Exception:
            if len(j) > 2:
                data = get(j[2])      # 뒷면 썸네일이 없으면 원본
            else:
                raise
        with open(path, "wb") as f:
            f.write(data)

    with ThreadPoolExecutor(4) as ex:
        for n, _ in enumerate(ex.map(run, todo), 1):
            if n % 200 == 0:
                log(f"  {n}/{len(todo)}")


# ── 2. 변환할 원본 고르기 ─────────────────────────────────
def stage_sources(cards):
    """썸네일이 TW보다 작으면 원본을 씀. 변환할 파일을 images_raw/src(앞면), images_raw/src_back(뒷면)에 모음"""
    src, srcb = os.path.join(RAW, "src"), os.path.join(RAW, "src_back")
    for d in (src, srcb):
        os.makedirs(d, exist_ok=True)
    sizes, used_full, missing = [], 0, []
    for c in cards:
        i = c["id"]
        t, full = os.path.join(RAW, "thumb", f"{i}.png"), os.path.join(RAW, f"{i}.png")
        pick = t if os.path.exists(t) else None
        wh = img_size(pick) if pick else None
        if (not wh or wh[0] < TW) and os.path.exists(full):
            pick, used_full = full, used_full + 1
            wh = img_size(full)
        if not pick:
            missing.append(i); continue
        sizes.append(wh[0] if wh else 0)
        dst = os.path.join(src, f"{i}.png")
        if not os.path.exists(dst):
            shutil.copyfile(pick, dst)
        b = os.path.join(RAW, "back", f"{i}.png")
        if os.path.exists(b) and not os.path.exists(os.path.join(srcb, f"{i}.png")):
            shutil.copyfile(b, os.path.join(srcb, f"{i}.png"))
    sizes.sort()
    if sizes:
        log(f"원본 가로 크기: 최소 {sizes[0]}, 중간 {sizes[len(sizes) // 2]}, 최대 {sizes[-1]} px / 원본 이미지로 대신한 카드 {used_full}장 / 이미지 없음 {len(missing)}장")
    return src, srcb


# ── 3. PhotoCraft image.imageSize 매개변수 확인 ──────────────
def keys_in(o, acc):
    if isinstance(o, dict):
        for k, v in o.items():
            acc.append(k); keys_in(v, acc)
    elif isinstance(o, list):
        for v in o:
            keys_in(v, acc)
    return acc


def find_num(o, name):
    if isinstance(o, dict):
        for k, v in o.items():
            if k.lower() == name and isinstance(v, (int, float)):
                return v
            r = find_num(v, name)
            if r is not None:
                return r
    elif isinstance(o, list):
        for v in o:
            r = find_num(v, name)
            if r is not None:
                return r
    return None


def resize_params(sample):
    code, out, err = pc("commands", "--json", "--filter", "imageSize")
    with open(os.path.join(DATA, "photocraft_imageSize.json"), "w", encoding="utf-8") as f:
        f.write(out or err)
    try:
        spec = json.loads(out)
    except Exception:
        spec = {}
    names = keys_in(spec, [])
    # 이 명령에 해당하는 매개변수 이름 후보 (조회 결과 우선, 없으면 흔한 이름)
    wk = next((k for k in names if re.fullmatch(r"(pixel)?width|w", k, re.I)), None) or "width"
    hk = next((k for k in names if re.fullmatch(r"(pixel)?height|h", k, re.I)), None) or "height"
    unit_k = next((k for k in names if re.search(r"unit", k, re.I)), None)
    samp_k = next((k for k in names if re.search(r"resampl|interpol|method", k, re.I)), None)
    keep_k = next((k for k in names if re.search(r"constrain|proportion|keepAspect|aspect", k, re.I)), None)
    w0, h0 = img_size(sample)
    th = round(h0 * TW / w0)
    base = {wk: TW, hk: th}
    tries = [dict(base)]
    if keep_k: tries.append({**base, keep_k: True})
    if unit_k:
        for u in ("pixels", "px", "pixel"):
            tries.append({**base, unit_k: u})
    if samp_k:
        for s in ("bicubic", "bicubicSharper", "bilinear", "auto"):
            tries.append({**base, samp_k: s})
            if unit_k: tries.append({**base, unit_k: "pixels", samp_k: s})
    test = os.path.join(RAW, "_test.webp")
    log(f"PhotoCraft 크기 줄이기 시험: {os.path.basename(sample)} {w0}x{h0} → {TW}x{th}")
    for p in tries:
        if os.path.exists(test): os.remove(test)
        code, out, err = pc("run", sample, "--cmd", "image.imageSize", "--params", json.dumps(p), "--out", test, "--quality", QUALITY)
        if code != 0 or not os.path.exists(test):
            log(f"  매개변수 {p}: 실패 ({(err or out).strip()[:200]})"); continue
        wh = img_size(test)
        if wh and abs(wh[0] - TW) <= 1:
            log(f"  매개변수 {p}: 성공, 결과 {wh[0]}x{wh[1]}, {os.path.getsize(test) // 1024}KB")
            return p, (w0, h0)
        log(f"  매개변수 {p}: 실행은 됐지만 결과 크기가 {wh}")
    return None, (w0, h0)


# ── 4. 일괄 변환 ────────────────────────────────────────
def batch(src, out, params, w0h0):
    os.makedirs(out, exist_ok=True)
    acts = os.path.join(RAW, "_actions.json")
    with open(acts, "w", encoding="utf-8") as f:
        json.dump([["image.imageSize", params]], f)
    n = len(os.listdir(src))
    if not n:
        return
    log(f"일괄 변환 {n}장 → {os.path.relpath(out, ROOT)}  (시간이 좀 걸려요)")
    t0 = time.time()
    code, o, e = pc("batch", "--actions", acts, "--in", src, "--out", out, "--format", "webp", "--quality", QUALITY, timeout=6 * 3600)
    if code != 0:
        log(f"일괄 변환 실패 (종료 코드 {code})\n{(e or o)[-2000:]}")
        sys.exit(1)
    log(f"  {time.time() - t0:.0f}초")


def main():
    cards = json.load(open(os.path.join(DATA, "cards.json"), encoding="utf-8"))
    if not os.path.exists(PC):
        log(f"PhotoCraft를 찾지 못했어요: {PC}"); sys.exit(1)
    download(cards)
    src, srcb = stage_sources(cards)
    sample = os.path.join(src, sorted(os.listdir(src))[0])
    params, w0h0 = resize_params(sample)
    if not params:
        log("\nPhotoCraft 크기 줄이기 매개변수를 찾지 못했어요. data/photocraft_imageSize.json 을 git에 올려 주시면 보고 고칠게요.")
        sys.exit(1)
    # 뒷면은 가로·세로가 다를 수 있어 같은 비율로 세로를 다시 계산하지 않고 가로만 맞춤 (앞면과 같은 크기 체계)
    batch(src, OUT, params, w0h0)
    if os.listdir(srcb):
        batch(srcb, os.path.join(OUT, "back"), params, w0h0)
    files = [f for f in os.listdir(OUT) if f.endswith(".webp")]
    total = sum(os.path.getsize(os.path.join(OUT, f)) for f in files)
    bad = [f for f in files[:50] if (img_size(os.path.join(OUT, f)) or (0,))[0] != TW]
    with open(os.path.join(DATA, "images_manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"width": TW, "quality": int(QUALITY), "params": params,
                   "front": sorted(int(re.match(r"\d+", x).group()) for x in files if re.match(r"\d+", x)),
                   "back": sorted(int(re.match(r"\d+", x).group()) for x in os.listdir(os.path.join(OUT, "back")) if x.endswith(".webp") and re.match(r"\d+", x)) if os.path.isdir(os.path.join(OUT, "back")) else []},
                  f, ensure_ascii=False)
    log(f"\n끝! 앞면 {len(files)}장, 합계 {total / 1e6:.0f} MB" + (f" / 크기가 다른 파일 {len(bad)}개(앞 50장 중)" if bad else ""))
    log("이제  git add images data  →  git commit -m \"카드 이미지\"  →  git push")


if __name__ == "__main__":
    main()
