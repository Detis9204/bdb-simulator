"""번역 작업 파일(/tmp/tr/out_XX.tsv, 번호<TAB>한국어)을 db/ko_lines.json 에 합친다.
db/ko_lines.json: {"v":1, "lines": {일본어 원문 한 줄: 한국어 한 줄}} — 카드 효과 번역 DB.
같은 문장은 판본이 달라도 한 번만 번역한다."""
import json, sys, glob
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / 'db' / 'ko_lines.json'
order = json.load(open(sys.argv[1] if len(sys.argv) > 1 else '/tmp/tr/order.json', encoding='utf-8'))
db = json.load(open(DB, encoding='utf-8')) if DB.exists() else {'v': 1, 'lines': {}}
n = 0
for f in sorted(glob.glob('/tmp/tr/out_*.tsv')):
    for line in open(f, encoding='utf-8'):
        line = line.rstrip('\n')
        if not line.strip():
            continue
        i, ko = line.split('\t', 1)
        db['lines'][order[int(i)]] = ko
        n += 1
DB.parent.mkdir(exist_ok=True)
DB.write_text(json.dumps(db, ensure_ascii=False, indent=0, sort_keys=True), encoding='utf-8')
print(f'합침 {n}줄, DB 전체 {len(db["lines"])}줄')
