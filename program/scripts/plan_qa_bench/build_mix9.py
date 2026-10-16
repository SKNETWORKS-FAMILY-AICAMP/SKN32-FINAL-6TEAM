# 새 독립 세트 mix9(작성자 Codex, 176문제) 변환·검증 — Codex 가 낸 JSON(일정 + 11유형 × 16 문제)을 fixtures/mix9.json 으로 바꾼다.
#  검증만 한다: 형식·정답 키 존재·유형별 16개·장소 겹침(평가 세트 6개 + 학습 풀). 문장·정답은 고치지 않는다(삭제는 사유를 출력).
# 사용: python build_mix9.py <Codex 가 낸 JSON 파일> → fixtures/mix9.json
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
    '그 다음 일정 시간은?': '앞 대화에서 서비스가 이미 「다음에는 마포한강공원」이라 답해, 「그 다음」이 공원인지 공원의 다음(저녁)인지 하나로 못 정함 — 정답 모호',
    '그 앞 일정 몇 시야?': '앞 대화가 「아울렛 다음에 닭한마리 저녁」이라 「그 앞」이 닭한마리의 앞(아울렛)인지 아울렛의 앞(체크인)인지 하나로 못 정함 — 정답 모호',
    '동대문디자인플라자 뮤지엄 몇 시?': '일정의 「동대문디자인플라자 디자인랩」과 같은 건물이라 사람이 일정 밖 장소로 볼지 같은 항목으로 볼지 하나로 못 정함 — 정답 모호',
    '동대문역 이동 늦추고 칼국수 시간 알려줘': '장소가 동대문역인 항목이 지하철 이동(목)과 공항 가는 버스(일) 두 개라 첫 대상을 하나로 못 정함 — 정답 모호',
    '혜화칼국수 예약하고 전시도 예매해줘': '혜화칼국수가 목요일 점심·일요일 마지막 점심 두 항목이고 날짜가 없어 하나로 못 정함 — 정답 모호',
    '마포한강공원 늦추고 우동도 늦춰줘': '마포한강공원이 화요일·토요일 두 항목이고 날짜가 없어 하나로 못 정함 — 정답 모호',
    '연남토마 말고 청수당 연남 시간?': '청수당 연남이 첫날·토요일 두 항목이고 날짜가 없어 하나로 못 정함 — 정답 모호',
    '카페 어스 말고 마포한강공원 몇 시?': '마포한강공원이 화요일·토요일 두 항목이고 날짜가 없어 하나로 못 정함 — 정답 모호',
    '동대문역 말고 혜화칼국수 몇 시?': '혜화칼국수가 목요일 점심·일요일 마지막 점심 두 항목이고 날짜가 없어 하나로 못 정함 — 정답 모호',
    '목요일 큰 천막시장 근처로 가는 교통편?': '「큰 천막시장」이 무엇을 가리키는지 사람이 하나로 못 정함(동대문 이동이라는 근거가 문장에 없음) — 정답 모호',
    '망원시장 먹거리 투어는?': '일정에 「시장 간식 구경(마포농수산물시장)」이 있어 사람이 같은 항목으로 볼지 일정 밖으로 볼지 하나로 못 정함 — 정답 모호',
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
json.dump({'sets': {'mix9': {'today': d['today'], 'items': items, 'qs': qs}}}, open(fixture('mix9.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('mix9 항목', len(items), '· 문제', len(qs), '· 정답 null', sum(x['gold'] is None for x in qs), '· 앞 대화', sum(bool(x['history']) for x in qs))
print('유형별', dict(Counter(x['type'] for x in qs)))
print('종류별 항목', dict(Counter(i['kind'] for i in items)))
print('버린 문제', len(dropped), dropped)
# 장소 겹침: 평가 세트 6개 + 학습 풀
names = set()
for j in ('heavy', 'mix4', 'mix5', 'mix6', 'mix7', 'mix8'):
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
