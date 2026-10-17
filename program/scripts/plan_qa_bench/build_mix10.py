# 새 독립 세트 mix10(작성자 Codex, 176문제 · mix8·mix9 결과를 본 뒤 만든 확인용 세트) 변환·검증 — Codex 가 낸 JSON(일정 + 11유형 × 16 문제)을 fixtures/mix10.json 으로 바꾼다.
#  검증만 한다: 형식·정답 키 존재·유형별 16개·장소 겹침(평가 세트 7개 + 학습 풀). 문장·정답은 고치지 않는다(삭제는 사유를 출력).
# 사용: python build_mix10.py <Codex 가 낸 JSON 파일> → fixtures/mix10.json
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
    # 아래 16문제는 시스템 결과를 보기 전에 Claude 가 문장·정답만 보고 뺐다(2026-10-04). 문장·정답은 고치지 않았다.
    '그거 몇 시야?': '앞 대화 서비스 답이 이미 「두 번째 일정은 11시」라 「그거」가 수도박물관인지 하수도과학관인지 하나로 못 정함 — 정답 모호',
    '그 다음 일정 언제야?': '앞 대화 서비스가 「다음 일정은 감자탕 점심」이라 답해 「그 다음」이 감자탕인지 감자탕의 다음(수도박물관)인지 하나로 못 정함 — 정답 모호',
    '두 번째 거 멀어?': '앞 대화 「묘원 걷기 다음에 책방」에서 「두 번째 거」는 책방(29)인데 Codex 정답은 묘원(28) — 정답 오류',
    '수도박물관 관람 시간?': '수도박물관이 화·일 두 항목(관람·재방문)이고 요일이 없어 하나로 못 정함 — 정답 모호',
    '수도박물관 취소하고 하수도과학관 시간 알려줘': '수도박물관이 두 항목이고 요일이 없어 첫 대상을 하나로 못 정함 — 정답 모호',
    '미미면가 시간 보고 진주회관 메뉴도 알려줘': '미미면가가 화·월 두 항목이고 요일이 없어 첫 대상을 하나로 못 정함 — 정답 모호',
    '농업박물관 시간 바꾸고 허준박물관도 확인해줘': '농업박물관이 금·월 두 항목이고 요일이 없어 첫 대상을 하나로 못 정함 — 정답 모호',
    '마포나루 예약하고 양화진책방 시간도 줘': '마포나루가 금·토 두 항목이고 요일이 없어 첫 대상을 하나로 못 정함 — 정답 모호',
    '응봉체육공원 취소, 왕십리광장은 몇 시?': '응봉체육공원이 수·일 두 항목이고 요일이 없어 첫 대상을 하나로 못 정함 — 정답 모호',
    '소문난성수감자탕 예약하고 수도박물관 시간 줘': '소문난성수감자탕이 수·일 두 항목이고 요일이 없어 첫 대상을 하나로 못 정함 — 정답 모호',
    '호텔 체크아웃 늦추고 공항 택시도 늦춰줘': '호텔 체크아웃이 금(ENA)·월(롯데시티) 두 항목이고 요일이 없어 첫 대상을 하나로 못 정함 — 정답 모호',
    '수도박물관 말고 서울하수도과학관 몇 시야?': '서울하수도과학관이 수·일 두 항목이고 요일이 없어 원하는 대상을 하나로 못 정함 — 정답 모호',
    '진주회관 저녁 말고 미미면가 점심은?': '미미면가 점심이 화·월 두 항목이고 요일이 없어 원하는 대상을 하나로 못 정함 — 정답 모호',
    '수돗물 역사 배우는 곳 언제야?': '수도박물관이 두 항목이고 요일이 없어 「수돗물 역사 배우는 곳」을 하나로 못 정함 — 정답 모호',
    '하수 처리 원리 체험은 몇 시?': '서울하수도과학관이 두 항목이고 요일이 없어 「하수 처리 원리 체험」을 하나로 못 정함 — 정답 모호',
    '농사 도구 보는 곳 몇 시?': '농업박물관이 두 항목이고 요일이 없어 「농사 도구 보는 곳」을 하나로 못 정함 — 정답 모호',
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
json.dump({'sets': {'mix10': {'today': d['today'], 'items': items, 'qs': qs}}}, open(fixture('mix10.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('mix10 항목', len(items), '· 문제', len(qs), '· 정답 null', sum(x['gold'] is None for x in qs), '· 앞 대화', sum(bool(x['history']) for x in qs))
print('유형별', dict(Counter(x['type'] for x in qs)))
print('종류별 항목', dict(Counter(i['kind'] for i in items)))
print('버린 문제', len(dropped), dropped)
# 장소 겹침: 평가 세트 7개 + 학습 풀
names = set()
for j in ('heavy', 'mix4', 'mix5', 'mix6', 'mix7', 'mix8', 'mix9'):
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
