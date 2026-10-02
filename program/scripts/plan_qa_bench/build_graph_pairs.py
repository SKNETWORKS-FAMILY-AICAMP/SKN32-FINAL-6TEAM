# §42 V6 — 시험 세트의 쌍 파일(pairs_*.json)의 문서에 그래프 이웃(앞·뒤 일정, 같은 장소 몇 번째 방문)을 덧붙인 사본(*_g.json)을 만든다.
#  접미 형식은 학습 자료(gen_train.py GRAPH=1)와 같아야 한다. 질문·항목 번호·순서는 그대로, 문서 글자만 다르다.
# 사용: python build_graph_pairs.py → fixtures/pairs_experts_g.json · pairs_mix5_g.json · pairs_mix6_g.json · pairs_mix7_g.json · pairs_mix8_g.json
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
F = lambda n: os.path.join(HERE, 'fixtures', n)
J = lambda n: json.load(open(F(n), encoding='utf-8'))


def suffix(prev, nxt, nth, total):
    return (f' — 앞 일정 {prev}' if prev else '') + (f' — 뒤 일정 {nxt}' if nxt else '') + (f' — 같은 장소 {nth}/{total}번째 방문' if total > 1 else '')


def graph_map(job):
    items = sorted(J(f'{job}.json')['sets'][job]['items'], key=lambda i: (i['date'], i['start']))
    tot = {}
    for i in items:
        tot[i['place']] = tot.get(i['place'], 0) + 1
    seen, m = {}, {}
    for k, i in enumerate(items):
        seen[i['place']] = seen.get(i['place'], 0) + 1
        m[i['id']] = suffix(items[k - 1]['title'] if k else None, items[k + 1]['title'] if k + 1 < len(items) else None, seen[i['place']], tot[i['place']])
    return m


for src, dst in (('pairs_experts.json', 'pairs_experts_g.json'), ('pairs_mix5.json', 'pairs_mix5_g.json'), ('pairs_mix6.json', 'pairs_mix6_g.json'),
                 ('pairs_mix7.json', 'pairs_mix7_g.json'), ('pairs_mix8.json', 'pairs_mix8_g.json')):
    pairs = J(src)
    maps = {}
    out = []
    for p in pairs:
        job = p['set'].rsplit('_', 1)[0]
        if job not in maps:
            maps[job] = graph_map(job)
        q = dict(p)
        q['doc'] = p['doc'] + maps[job][p['item']]
        out.append(q)
    json.dump(out, open(F(dst), 'w', encoding='utf-8'), ensure_ascii=False)
    print(dst, len(out), '예:', out[0]['doc'])
