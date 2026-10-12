# 새 독립 세트 mix11(작성자 Codex, 176문제 · mix8·mix9 결과를 본 뒤 만든 확인용 세트) 변환·검증 — Codex 가 낸 JSON(일정 + 11유형 × 16 문제)을 fixtures/mix11.json 으로 바꾼다.
#  검증만 한다: 형식·정답 키 존재·유형별 16개·장소 겹침(평가 세트 8개 + 학습 풀). 문장·정답은 고치지 않는다(삭제는 사유를 출력).
# 사용: python build_mix11.py <Codex 가 낸 JSON 파일> → fixtures/mix11.json
import glob, json, os, re, sys
from collections import Counter
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
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
    # 아래 13문제는 시스템 결과를 보기 전에 Claude 가 문장·정답만 보고 뺐다(2026-10-04). 문장·정답은 고치지 않았다.
    '거기 몇 시에 가요?': '앞 대화 서비스 답이 석파정(13시)과 창의문(14시 30분) 둘을 말해 「거기」가 어느 쪽인지 하나로 못 정함 — 정답 모호',
    '그다음 일정은 뭐예요?': '앞 대화 서비스가 「그다음 성북선잠박물관」이라 답해 「그다음 일정」이 선잠박물관인지 그 뒤(저녁)인지 하나로 못 정함, Codex 정답(최순우 옛집)은 앞 대화와 어긋남 — 정답 모호',
    '두 번째 거 시간은요?': '앞 대화 「광진교를 다시 걷고 구의시장을 구경」에서 「두 번째 거」는 구의시장(36)인데 Codex 정답은 광진교(35) — 정답 오류',
    '일요일 암사종합시장 첫 일정은?': '「일요일 암사종합시장 첫 일정은?」 — 일요일의 첫 일정(길동생태공원)인지 일요일 첫 암사종합시장 일정(33)인지 하나로 못 정함 — 정답 모호',
    '정동성당 방문은 언제죠?': '「정동성당」이 성공회 서울주교좌성당(정동 위치)을 가리킬 수 있어 일정 밖인지 하나로 못 정함 — 정답 모호',
    '암사종합시장 구경하고 두부 점심도요': '암사종합시장 구경이 토·일 두 항목(구경·다시 구경)이고 요일이 없어 첫 대상을 하나로 못 정함 — 정답 모호',
    '공항 택시 늦추고 호텔 퇴실도 확인요': '「공항 택시」가 첫날 공항발 택시(1)와 마지막 날 공항행 택시(43) 둘로 읽힐 수 있어 첫 대상을 하나로 못 정함 — 정답 모호',
    '창의문 말고 차 마시는 뜰요': '차 마시는 뜰이 수·월 두 항목이고 날짜가 없어 원하는 대상을 하나로 못 정함 — 정답 모호',
    '차마시는뜰 몇시얌': '차 마시는 뜰이 수·월 두 항목이고 요일이 없어 하나로 못 정함 — 정답 모호',
    '공항택시몇시야염': '「공항 택시」가 공항발(1)·공항행(43) 둘로 읽힐 수 있고 날짜가 없어 하나로 못 정함 — 정답 모호',
    '한옥에서 잔에 우려 마시는 시간?': '차 마시는 뜰이 수·월 두 항목이고 요일이 없어 「한옥에서 잔에 우려 마시는 시간」을 하나로 못 정함 — 정답 모호',
    '공항 택시 한 시간 앞당겨줘요': '「공항 택시」가 공항발(1)·공항행(43) 둘로 읽힐 수 있고 날짜가 없어 하나로 못 정함 — 정답 모호',
    '한양도성 백악구간도 가나요?': '창의문이 한양도성 백악구간의 성문이라 「한양도성 백악구간」이 일정 안(창의문)인지 밖인지 하나로 못 정함 — 정답 모호',
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
json.dump({'sets': {'mix11': {'today': d['today'], 'items': items, 'qs': qs}}}, open(os.path.join(HERE, 'fixtures', 'mix11.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('mix11 항목', len(items), '· 문제', len(qs), '· 정답 null', sum(x['gold'] is None for x in qs), '· 앞 대화', sum(bool(x['history']) for x in qs))
print('유형별', dict(Counter(x['type'] for x in qs)))
print('종류별 항목', dict(Counter(i['kind'] for i in items)))
print('버린 문제', len(dropped), dropped)
# 장소 겹침: 평가 세트 8개 + 학습 풀
names = set()
for j in ('heavy', 'mix4', 'mix5', 'mix6', 'mix7', 'mix8', 'mix9', 'mix10'):
    names |= {i['place'].replace(' ', '') for i in json.load(open(os.path.join(HERE, 'fixtures', f'{j}.json'), encoding='utf-8'))['sets'][j]['items']}
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
