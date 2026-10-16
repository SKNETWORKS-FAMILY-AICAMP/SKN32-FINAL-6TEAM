# 소형 전문 모델(Qwen3-Reranker-4B · WeMM-4B · OpenDecider-small)에 줄 입력 만들기 — heavy·mix4 의 「대상 절」(tt)과 「말고 앞 절」(excl)마다 항목 51개 점수.
#  절 분석(clauses.py)은 작은 LLM 전문가 구조와 같은 것을 쓴다. 앞 대화는 이 모델들이 못 읽으므로 넣지 않는다(앞 대화 문제는 LLM 전문가 몫).
# 사용: python build_expert_inputs.py → fixtures/pairs_experts.json · fixtures/job_od_experts.json (서버 실행용)
import json, os
from datetime import date
from clauses import analyze
HERE = os.path.dirname(os.path.abspath(__file__))
from testsets import fixture  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
W = '월화수목금토일'
pairs, od = [], {'sets': {}}
for job in ('heavy', 'mix4'):
    st = json.load(open(fixture(f'{job}.json'), encoding='utf-8'))['sets'][job]
    items = sorted(st['items'], key=lambda i: (i['date'], i['start']))

    def doc(i):
        d = date.fromisoformat(i['date'])
        return f"{d.month}월 {d.day}일({W[d.weekday()]}) {i['start']} {i['title']} — 장소 {i['place']} — 종류 {i['kind']}"

    for kind in ('tt', 'excl'):
        qs = []
        for qi, x in enumerate(st['qs']):
            a = analyze(x['q'])
            text = a['tt'] if kind == 'tt' else a['excl']
            qs.append({'q': text or '(없음)', 'gold': None})
            if text is None:
                continue
            for it in items:
                pairs.append({'set': f'{job}_{kind}', 'qi': qi, 'item': it['id'], 'q': text, 'doc': doc(it)})
        od['sets'][f'{job}_{kind}'] = {'today': st['today'], 'items': st['items'], 'qs': qs}
json.dump(pairs, open(os.path.join(HERE, 'fixtures', 'pairs_experts.json'), 'w', encoding='utf-8'), ensure_ascii=False)
json.dump(od, open(os.path.join(HERE, 'fixtures', 'job_od_experts.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('쌍', len(pairs), '· 고유 질문', len({p['q'] for p in pairs}), '· 세트', list(od['sets']))
