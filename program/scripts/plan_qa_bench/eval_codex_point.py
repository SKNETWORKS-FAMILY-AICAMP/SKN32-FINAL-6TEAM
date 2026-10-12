# codex_point.py 결과(codex_<모델>.json)를 보류 90문항(test50+hard40)으로 채점하고 Gemma 계열(results/llm_out.json)과 나란히 낸다.
# 채점: 엉뚱한 답 = 틀린 항목 + 없는 질문에 항목, 못 찾음 = 정답이 있는데 null. 쉬운/어려운 묶음은 job.json 의 type 으로 나눈다.
# 사용: python eval_codex_point.py <codex_*.json ...>
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
job = json.load(open(os.path.join(HERE, 'fixtures', 'job.json'), encoding='utf-8'))['sets']
gem = json.load(open(os.path.join(HERE, 'results', 'llm_out.json'), encoding='utf-8'))
HELD, HARD = ('test50', 'hard40'), {'paraphrase_knowledge', 'sequence'}


def score(get):
    r = {'all': [0, 0, 0, 0], 'easy': [0, 0], 'hard': [0, 0]}
    for s in HELD:
        for qi, x in enumerate(job[s]['qs']):
            p, g = get(s, qi), x['gold']
            k = 'hard' if x.get('type') in HARD else 'easy'
            hit = int(p == g)
            r['all'][0] += hit; r['all'][1] += 1
            r['all'][2] += int(p is not None and p != g)
            r['all'][3] += int(p is None and g is not None)
            r[k][0] += hit; r[k][1] += 1
    return r


def show(name, r, extra=''):
    a = r['all']
    print(f"  {name:<30} {a[0]}/{a[1]}={a[0] / a[1]:.0%} 엉뚱 {a[2]} 못 찾음 {a[3]} | 쉬운 {r['easy'][0]}/{r['easy'][1]} 어려운 {r['hard'][0]}/{r['hard'][1]} {extra}")


print('보류 90문항(test50+hard40), 각 1회. Gemma 는 질문 하나씩, Codex 는 세트 한 번에 묶어 풀이.')
for m in ('gemma4:e4b', 'gemma4:12b', 'gemma4:26b'):
    show(m, score(lambda s, qi, m=m: gem[m][s][qi]))
for path in sys.argv[1:]:
    c = json.load(open(path, encoding='utf-8'))
    name = os.path.basename(path)[6:-5]
    show(name, score(lambda s, qi, c=c: c[s].get(str(qi))), f"| {sum(v for k, v in c.items() if k.startswith('_sec_')) / 4:.0f}초/세트")
