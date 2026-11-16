# -*- coding: utf-8 -*-
"""
빌디바이드 브라이트 카드 수집기 (1단계)

공식 사이트(tcg.build-divide.com/bright)의 카드 검색에서 모든 카드를 모아
  - data/filters.json     : 검색 필터 목록 (작품·상품·칭호·속성·아이콘 능력·색·트리거·종류 등)
  - data/tags.json        : 필터별로 해당하는 카드 ID 목록 (카드마다 작품·칭호·아이콘 등을 정확히 붙이기 위함)
  - data/cards/<id>.json  : 카드 상세 원문 (공식 사이트 카드 상세 창의 HTML 그대로)
  - data/images.json      : 카드 ID → 이미지 주소
  - images_raw/<id>.png   : 카드 이미지 원본 (용량이 커서 git에는 올리지 않음, .gitignore 처리)
  - data/photocraft_help.txt : PhotoCraft 명령 목록 (2단계 크기 줄이기 스크립트를 정확히 만들기 위함)
을 만듭니다. 파이썬 표준 라이브러리만 씁니다.

실행 (저장소 최상위 폴더에서):  python collector/bdb_collect.py
중간에 끊겨도 다시 실행하면 이미 받은 카드·이미지는 건너뜁니다.
"""
import json, os, re, sys, time, subprocess, threading
import urllib.request, urllib.parse
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor

BASE = os.environ.get("BDB_BASE", "https://tcg.build-divide.com")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 저장소 최상위 폴더
DATA = os.path.join(ROOT, "data")
CARDS = os.path.join(DATA, "cards")
IMG_RAW = os.path.join(ROOT, "images_raw")
PHOTOCRAFT = os.environ.get("BDB_PHOTOCRAFT", r"D:\Utill\photocraft-0.10.0\photocraft-cli.exe")
WORKERS = 4          # 동시에 보내는 요청 수 (서버에 부담 주지 않도록 작게)
DELAY = 0.15         # 요청마다 쉬는 시간(초)
UA = "Mozilla/5.0 (personal deck practice tool)"

try:
    sys.stdout.reconfigure(errors="replace")   # Windows 콘솔에서 글자 때문에 멈추지 않도록
except Exception:
    pass
os.makedirs(CARDS, exist_ok=True)
os.makedirs(IMG_RAW, exist_ok=True)
_lock = threading.Lock()


def log(*a):
    with _lock:
        print(*a, flush=True)


def get(url, accept="application/json", tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept, "X-Requested-With": "XMLHttpRequest"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            time.sleep(DELAY)
            return data
        except Exception as e:
            if k == tries - 1:
                raise
            log(f"  다시 시도 {k + 1}/{tries - 1}: {url} ({e})")
            time.sleep(2 * (k + 1))


# ── 1. 검색 필터 목록 ─────────────────────────────────────
class FilterParser(HTMLParser):
    """카드 검색 폼의 체크박스(name=card[...][], value, id)와 그 라벨 글자를 모음"""
    def __init__(self):
        super().__init__()
        self.inputs, self.labels, self._for, self._buf = [], {}, None, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "input" and a.get("type") in ("checkbox", "radio") and (a.get("name") or "").startswith("card["):
            self.inputs.append({"name": a["name"], "value": a.get("value", ""), "id": a.get("id")})
        if tag == "label" and a.get("for"):
            self._for, self._buf = a["for"], []

    def handle_data(self, d):
        if self._for is not None:
            self._buf.append(d)

    def handle_endtag(self, tag):
        if tag == "label" and self._for is not None:
            self.labels[self._for] = " ".join("".join(self._buf).split())
            self._for = None


def collect_filters():
    html = get(BASE + "/bright/decks", accept="text/html").decode("utf-8")
    p = FilterParser(); p.feed(html)
    out = []
    for i in p.inputs:
        if not i["value"]:
            continue
        key = re.match(r"card\[([a-z_]+)\]", i["name"]).group(1)
        if key == "freeword_category":
            continue
        out.append({"key": key, "name": i["name"], "value": i["value"], "label": p.labels.get(i["id"], "")})
    with open(os.path.join(DATA, "filters.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    log(f"필터 {len(out)}개")
    return out


# ── 2. 검색 (페이지 넘기며 카드 ID와 이미지 주소 모으기) ──────────
def search(params):
    """params: [(name, value), ...]. 모든 페이지의 (카드ID, 이미지주소) 목록을 돌려줌"""
    found, page = {}, 1
    while True:
        q = urllib.parse.urlencode(params + [("page", str(page))])
        j = json.loads(get(f"{BASE}/bright/decks/search?{q}"))
        entries = j.get("entries") or ""
        ids = re.findall(r'card-id-param="(\d+)"', entries)
        imgs = re.findall(r'card-id-param="(\d+)"[^>]*>\s*<img src="([^"]+)"', entries)
        new = [i for i in ids if i not in found]
        for i in ids:
            found.setdefault(i, None)
        for i, src in imgs:
            found[i] = src
        # 페이지 표기 형식에 기대지 않고, 새 카드가 더 안 나올 때까지 다음 페이지를 요청
        if not new or page >= 300:
            break
        page += 1
    return found


def collect_all(filters):
    log("전체 카드 목록 수집 중…")
    all_cards = search([])
    log(f"카드 {len(all_cards)}장")
    # 필터별 태그: 같은 종류(key)끼리 묶어 카드마다 정확한 값을 붙임
    tags = {}
    tag_path = os.path.join(DATA, "tags.json")
    if os.path.exists(tag_path):
        with open(tag_path, encoding="utf-8") as f:
            tags = json.load(f)
    todo = [x for x in filters if f'{x["key"]}={x["value"]}' not in tags]
    log(f"필터별 검색 {len(todo)}개 남음")

    def run(x):
        res = search([(x["name"], x["value"])])
        for i, src in res.items():
            if src and not all_cards.get(i):
                all_cards[i] = src
        return f'{x["key"]}={x["value"]}', {"label": x["label"], "ids": sorted(res, key=int)}

    done = 0
    with ThreadPoolExecutor(WORKERS) as ex:
        for k, v in ex.map(run, todo):
            tags[k] = v; done += 1
            if done % 20 == 0:
                log(f"  필터 {done}/{len(todo)}")
                with open(tag_path, "w", encoding="utf-8") as f:
                    json.dump(tags, f, ensure_ascii=False)
    with open(tag_path, "w", encoding="utf-8") as f:
        json.dump(tags, f, ensure_ascii=False)
    # 필터 검색에서만 나온 카드도 포함
    for v in tags.values():
        for i in v["ids"]:
            all_cards.setdefault(i, None)
    with open(os.path.join(DATA, "images.json"), "w", encoding="utf-8") as f:
        json.dump({k: all_cards[k] for k in sorted(all_cards, key=int)}, f, ensure_ascii=False, indent=0)
    return all_cards


# ── 3. 카드 상세 원문 ───────────────────────────────────
def collect_details(ids):
    todo = [i for i in ids if not os.path.exists(os.path.join(CARDS, f"{i}.json"))]
    log(f"카드 상세 {len(todo)}장 남음 (전체 {len(ids)}장)")

    def run(i):
        j = json.loads(get(f"{BASE}/bright/decks/card?card_id={i}"))
        with open(os.path.join(CARDS, f"{i}.json"), "w", encoding="utf-8") as f:
            json.dump({"id": int(i), "html": j.get("contents", "")}, f, ensure_ascii=False)
        return i

    with ThreadPoolExecutor(WORKERS) as ex:
        for n, _ in enumerate(ex.map(run, todo), 1):
            if n % 50 == 0:
                log(f"  상세 {n}/{len(todo)}")


# ── 4. 이미지 원본 ──────────────────────────────────────
def collect_images(cards):
    todo = [(i, u) for i, u in cards.items() if u and not os.path.exists(os.path.join(IMG_RAW, f"{i}.png"))]
    log(f"이미지 {len(todo)}장 남음")

    def run(t):
        i, u = t
        data = get(u, accept="image/*")
        with open(os.path.join(IMG_RAW, f"{i}.png"), "wb") as f:
            f.write(data)
        return i

    with ThreadPoolExecutor(WORKERS) as ex:
        for n, _ in enumerate(ex.map(run, todo), 1):
            if n % 50 == 0:
                log(f"  이미지 {n}/{len(todo)}")


# ── 5. PhotoCraft 명령 목록 (2단계 준비) ──────────────────
def photocraft_help():
    out = []
    if not os.path.exists(PHOTOCRAFT):
        out.append(f"PhotoCraft를 찾지 못함: {PHOTOCRAFT}")
    else:
        for args in (["--help"], ["run", "--help"], ["batch", "--help"], ["list"], ["commands"], ["help", "commands"]):
            try:
                r = subprocess.run([PHOTOCRAFT] + args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
                out.append(f"$ photocraft-cli {' '.join(args)}  (종료 코드 {r.returncode})\n{r.stdout}\n{r.stderr}")
            except Exception as e:
                out.append(f"$ photocraft-cli {' '.join(args)}  실패: {e}")
    with open(os.path.join(DATA, "photocraft_help.txt"), "w", encoding="utf-8") as f:
        f.write("\n\n".join(out))
    log("PhotoCraft 명령 목록 저장")


def main():
    t0 = time.time()
    filters = collect_filters()
    cards = collect_all(filters)
    collect_details(sorted(cards, key=int))
    collect_images(cards)
    photocraft_help()
    size = sum(os.path.getsize(os.path.join(IMG_RAW, f)) for f in os.listdir(IMG_RAW))
    log(f"\n끝! 카드 {len(cards)}장, 이미지 원본 {len(os.listdir(IMG_RAW))}장 ({size / 1e6:.0f} MB), {time.time() - t0:.0f}초")
    log("이제 git add data 후 commit, push 해 주세요. (images_raw 폴더는 올리지 않아요)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\n중단했어요. 다시 실행하면 이어서 받아요.")
        sys.exit(1)
