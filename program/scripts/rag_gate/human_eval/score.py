# 사람 평가 시트(human_eval_sheet.csv)를 두 평가자가 채운 뒤 점수와 평가자 일치도를 센다.
#  각 기준은 1~5점(1 = 전혀 아니다, 5 = 완전히 맞다). 평가자가 둘 다 채운 행만 센다. 채운 행이 없으면 「아직 평가 없음」이라고만 출력한다(점수를 만들어 내지 않는다).
#  일치도: 가중 카파(이차 가중, 1 = 완전 일치, 0 = 우연 수준) · 평가자 점수 차가 1점 이내인 비율. 정답 라벨은 없다 — 평가자 의견이 기준이다.
# 사용: python score.py [시트 경로]
import collections
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'human_eval_sheet.csv')
CRIT = ['정확성', '근거충실', '질문에맞음', '자연스러움', '안전성']
sys.stdout.reconfigure(encoding='utf-8')
rows = list(csv.DictReader(open(path, encoding='utf-8-sig')))
key = {k['id']: k for k in json.load(open(os.path.join(HERE, 'human_eval_key.json'), encoding='utf-8'))}


def num(x):
    try:
        v = int(str(x).strip())
        return v if 1 <= v <= 5 else None
    except ValueError:
        return None


def wkappa(a, b):
    n = len(a)
    if n < 2:
        return None
    labs = range(1, 6)
    o = collections.Counter(zip(a, b))
    ca, cb = collections.Counter(a), collections.Counter(b)
    num_ = sum(((i - j) ** 2) * o[(i, j)] / n for i in labs for j in labs)
    den = sum(((i - j) ** 2) * ca[i] * cb[j] / (n * n) for i in labs for j in labs)
    return None if den == 0 else 1 - num_ / den


done = [r for r in rows if all(num(r[f'평가자{p}_{c}']) for p in 'AB' for c in CRIT)]
print(f'# 사람 평가 결과 — 두 평가자가 모두 채운 행 {len(done)}/{len(rows)}')
if not done:
    print('아직 평가 없음 — 점수를 만들어 내지 않는다.')
    sys.exit(0)
print('| 기준 | 평가자 A 평균 | 평가자 B 평균 | 가중 카파 | 1점 이내 일치 |')
print('|---|---:|---:|---:|---:|')
for c in CRIT:
    a = [num(r[f'평가자A_{c}']) for r in done]
    b = [num(r[f'평가자B_{c}']) for r in done]
    k = wkappa(a, b)
    print(f'| {c} | {sum(a) / len(a):.2f} | {sum(b) / len(b):.2f} | {"—" if k is None else f"{k:.2f}"} | {sum(1 for x, y in zip(a, b) if abs(x - y) <= 1)}/{len(a)} |')
print('\n## 층별 두 평가자 평균(기준 5개 평균)')
by = collections.defaultdict(list)
for r in done:
    by[(key[r['id']]['종류'], key[r['id']]['층'])].append(sum(num(r[f'평가자{p}_{c}']) for p in 'AB' for c in CRIT) / 10)
print('| 종류 | 층 | 행 수 | 평균(1~5) |')
print('|---|---|---:|---:|')
for (k, s), v in sorted(by.items()):
    print(f'| {k} | {s} | {len(v)} | {sum(v) / len(v):.2f} |')
