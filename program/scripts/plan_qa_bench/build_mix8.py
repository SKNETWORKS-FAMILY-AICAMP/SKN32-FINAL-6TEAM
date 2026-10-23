# 새 독립 세트 mix8(작성자 Codex, 176문제) 변환·검증 — Codex 가 낸 JSON(일정 + 11유형 × 16 문제)을 fixtures/mix8.json 으로 바꾼다.
#  검증만 한다: 형식·정답 키 존재·유형별 16개·장소 겹침(평가 세트 5개 + 학습 풀). 문장·정답은 고치지 않는다(삭제는 사유를 출력).
# 사용: python build_mix8.py <Codex 가 낸 JSON 파일> → fixtures/mix8.json
import glob, json, os, re, sys
from collections import Counter
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
from testsets import fixture  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
raw = open(sys.argv[1], encoding='utf-8').read()
m = re.search(r'\{.*\}', raw, re.S)
d = json.loads(m.group(0))
dates = d['dates']
assert len(dates) == 7
RAW = sorted(d['itinerary'], key=lambda r: (r['day'], r['start']))
ID = {r['key']: n + 1 for n, r in enumerate(RAW)}
assert len(ID) == len(RAW), '키 중복'
items = [{'id': ID[r['key']], 'date': dates[r['day']], 'start': r['start'], 'kind': r['kind'], 'title': r['title'], 'place': r['place']} for r in RAW]
# Claude 의 정답 검토에서 「명백히 틀렸거나 사람이 하나로 못 정하는」 것으로 판단해 뺀 문제(문장·정답은 고치지 않고 삭제만, 사유 기록)
MANUAL_DROP = {
    '거기 다시 가는 날은?': '앞 대화에서 서비스가 이미 「금요일 15시 소마미술관 특별전」이라 답해, 「다시 가는 날」이 그 방문인지 다른 방문(목요일 소마미술관)인지 하나로 못 정함 — 정답 모호',
    '소마미술관 취소하고 갈비집은 갈게': '소마미술관이 목요일 관람·금요일 특별전 두 항목이고 날짜가 없어 첫 대상을 하나로 못 정함(갈비집도 세 번) — 정답 모호',
    '민속박물관 시간 주고 지하상가도 알려줘': '롯데월드 민속박물관이 금요일 관람·일요일 재방문 두 항목이고 날짜·순서가 없어 하나로 못 정함 — 정답 모호',
    '석촌고분역 말고 소마미술관': '소마미술관 관람(목)과 소마미술관 특별전 관람(금) 두 항목이고 날짜가 없어 하나로 못 정함 — 정답 모호',
    '민속박물관 말고 지하상가요': '잠실 지하상가가 금요일 둘러보기·일요일 쇼핑 두 항목이고 날짜가 없어 하나로 못 정함(민속박물관도 두 번) — 정답 모호',
}
qs, dropped = [], []
seen = set()
for x in d['questions']:
    if x['q'] in MANUAL_DROP:
        dropped.append((x['q'], MANUAL_DROP[x['q']]))
        continue
    if x['gold'] is not None and x['gold'] not in ID:
        dropped.append((x['q'], '정답 키가 일정에 없음 ' + str(x['gold'])))
        continue
    if x['q'] in seen:
        dropped.append((x['q'], '문장 중복'))
        continue
    seen.add(x['q'])
    h = x.get('history') or []
    qs.append({'q': x['q'], 'gold': ID[x['gold']] if x['gold'] else None, 'type': x['type'], 'split': 'held',
               'history': [{'role': 'customer' if k % 2 == 0 else 'service', 'text': t} for k, t in enumerate(h)]})
json.dump({'sets': {'mix8': {'today': d['today'], 'items': items, 'qs': qs}}}, open(fixture('mix8.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('mix8 항목', len(items), '· 문제', len(qs), '· 정답 null', sum(x['gold'] is None for x in qs), '· 앞 대화', sum(bool(x['history']) for x in qs))
print('유형별', dict(Counter(x['type'] for x in qs)))
print('종류별 항목', dict(Counter(i['kind'] for i in items)))
print('버린 문제', len(dropped), dropped)
# 장소 겹침: 평가 세트 5개 + 학습 풀
names = set()
for j in ('heavy', 'mix4', 'mix5', 'mix6', 'mix7'):
    names |= {i['place'].replace(' ', '') for i in json.load(open(fixture(f'{j}.json'), encoding='utf-8'))['sets'][j]['items']}
train_dir = os.path.join(HERE, '..', '..', '..', 'datasets', 'travel', 'plan_qa_bench', 'train')
tr = set()
for f in glob.glob(os.path.join(train_dir, 'places_*.json')):
    tr |= {p['name'].replace(' ', '') for p in json.load(open(f, encoding='utf-8'))['places']}
extra = os.environ.get('TRAIN2')
if extra:
    for f in glob.glob(os.path.join(extra, 'places_*.json')):
        tr |= {p['name'].replace(' ', '') for p in json.load(open(f, encoding='utf-8'))['places']}
mine = {i['place'].replace(' ', '') for i in items}
print('평가 세트 장소와 겹침:', sorted(n for n in mine if n in names) or '없음')
print('학습 풀 장소와 겹침(정확 일치):', sorted(n for n in mine if n in tr) or '없음')
print('학습 풀과 부분 겹침(포함 관계):', sorted(n for n in mine if any((n in t or t in n) and n != t for t in tr)) or '없음')
