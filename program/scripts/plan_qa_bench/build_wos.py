# KLUE-WoS 지시어 검증 문제(사람이 쓴 문장 + 앞 대화)를 우리 일정 짚기 형식으로 바꾼다 — 평가 확장용(작성자·문체가 우리 세트와 다름).
#  각 문제는 「그 대화에 나온 장소」가 정답이다. 한 묶음(12문제)마다 가상 일정 하나를 만든다: 묶음 안 대화들의 장소(이름이 같으면 한 항목으로 합침) + 다른 묶음의 장소 몇 개를 채워 약 40항목.
#  정답과 앞 대화는 원본 그대로 두고, 날짜·시각만 임의로 붙인다(문제 풀이에 쓰이지 않는 칸이 아니라 일정 목록에 보이므로 종류에 맞는 시각을 쓴다).
#  한계: 대화가 예약 업무 중심이라 「마지막 거·가운데 거」 같은 순서형 지시어는 없다. 항목이 대화당 1~3개라 정답이 대화 안에서는 쉽고, 40항목 일정에서의 지시어 해소를 시험한다.
# 사용: python build_wos.py [검증만=valid|전체=all] → fixtures/wos.json  (sets: wos01 …)
import json, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', '..', '..', 'datasets', 'travel', 'klue_wos', 'processed', 'deixis_probes.jsonl')
which = sys.argv[1] if len(sys.argv) > 1 else 'valid'
rows = [json.loads(l) for l in open(SRC, encoding='utf-8')]
rows = [r for r in rows if which == 'all' or r['split'] != 'train']
rnd = random.Random(20261001)
rnd.shuffle(rows)
KIND_TIMES = {'dining': ['08:30', '12:30', '18:30', '20:00'], 'activity': ['09:30', '11:00', '14:00', '16:00'], 'lodging': ['15:00', '09:00']}
DATES = ['2026-11-02', '2026-11-03', '2026-11-04', '2026-11-05', '2026-11-06', '2026-11-07', '2026-11-08']
pool_all = {}
for r in rows:
    for it in r['items']:
        pool_all.setdefault(it['title'], it)
sets = {}
B = 12
for bi in range(0, len(rows), B):
    batch = rows[bi:bi + B]
    names = {}
    for r in batch:
        for it in r['items']:
            names.setdefault(it['title'], it)
    others = [v for k, v in pool_all.items() if k not in names]
    rnd.shuffle(others)
    for it in others[:max(0, 40 - len(names))]:
        names.setdefault(it['title'], it)
    lst = list(names.values())
    rnd.shuffle(lst)
    # 날짜별 시각 배정: 하루 6~7개, 종류에 맞는 시각을 순서대로(같은 날 같은 시각 중복은 피함)
    items = []
    used = {}
    for n, it in enumerate(lst):
        d = n // 6
        k = it['kind']
        times = KIND_TIMES.get(k, KIND_TIMES['activity'])
        cand = [t for t in times if (d, t) not in used] or [f'{9 + (n % 10):02d}:45']
        t = cand[0]
        used[(d, t)] = 1
        items.append({'id': 0, 'date': DATES[min(d, 6)], 'start': t, 'kind': k, 'title': it['title'], 'place': it['title']})
    items.sort(key=lambda i: (i['date'], i['start']))
    for n, i in enumerate(items):
        i['id'] = n + 1
    byname = {i['title']: i['id'] for i in items}
    qs = [{'q': r['q'], 'gold': byname[r['gold_name']], 'type': 'wos_deixis', 'split': 'held', 'history': r['history']} for r in batch]
    sets[f'wos{bi // B + 1:02d}'] = {'today': '2026-10-30', 'items': items, 'qs': qs}
json.dump({'sets': sets}, open(os.path.join(HERE, 'fixtures', 'wos.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('묶음', len(sets), '· 문제', sum(len(s['qs']) for s in sets.values()), '· 항목 수 범위', min(len(s['items']) for s in sets.values()), max(len(s['items']) for s in sets.values()))
