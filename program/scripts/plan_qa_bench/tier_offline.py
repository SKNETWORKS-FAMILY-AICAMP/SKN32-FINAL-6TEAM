# 가벼운 LLM·단계형(cascade)을 오프라인으로 재계산한다(저장된 모델 번호, 서버·비용 없음).
#  - 보류 90문항(test50 + hard40)을 「쉬운 묶음」(이름·분명한 설명·시간·영어 등)과 「어려운 묶음」(지식으로 설명한 질문 + 순서 질문)으로 나눈다.
#  - 단계형: E4B 와 12B 가 같은 번호면 그것을 답하고, 다르면 26B 로 넘긴다.
# 주의: 모델·구성을 같은 90문항 성적으로 골랐으므로 낙관적이다. 새 시험 세트로 다시 확인해야 한다.
import collections, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
job = json.load(open(os.path.join(HERE, 'fixtures', 'job.json'), encoding='utf-8'))['sets']
out = json.load(open(os.path.join(HERE, 'results', 'llm_out.json'), encoding='utf-8'))
H = ('test50', 'hard40')
HARD = {'paraphrase_knowledge', 'sequence'}
rows = [(s, i, x) for s in H for i, x in enumerate(job[s]['qs'])]
easy = [r for r in rows if r[2].get('type') not in HARD]
hard = [r for r in rows if r[2].get('type') in HARD]


def st(pick, sub):
    ok = bad = miss = 0
    for s, i, x in sub:
        p, g = pick(s, i), x['gold']
        ok += (p == g)
        bad += (p is not None and p != g)
        miss += (p is None and g is not None)
    return ok, len(sub), bad, miss


def line(name, pick):
    a, b = st(pick, easy), st(pick, hard)
    print(f"{name:<40}{a[0]}/{a[1]}={a[0] / a[1]:.0%} 엉뚱 {a[2]} 못찾음 {a[3]}".ljust(68)
          + f"{b[0]}/{b[1]}={b[0] / b[1]:.0%} 엉뚱 {b[2]} 못찾음 {b[3]}")


def single(k):
    return lambda s, i: out[k][s][i]


def vote(names, need):
    def f(s, i):
        t, k = collections.Counter(out[n][s][i] for n in names).most_common(1)[0]
        return t if k >= need else None
    return f


def agree(a, b):
    return lambda s, i: out[a][s][i] if out[a][s][i] == out[b][s][i] else None


def cascade(s, i):
    a, b = out['gemma4:e4b'][s][i], out['gemma4:12b'][s][i]
    return a if a == b else out['gemma4:26b'][s][i]


if __name__ == '__main__':
    print(f"쉬운 묶음 {len(easy)}문항 / 어려운 묶음 {len(hard)}문항\n{'방식':<40}{'쉬운 묶음':<28}어려운 묶음")
    for k in ('gemma4:26b', 'gemma4:12b', 'gemma4:e4b', 'gemma4:e2b', 'qwen3.5:9b', 'qwen3.5:4b'):
        line(k, single(k))
    line('E4B·12B 같을 때만', agree('gemma4:e4b', 'gemma4:12b'))
    line('E4B·26B 같을 때만', agree('gemma4:e4b', 'gemma4:26b'))
    line('가벼운 3종(E4B·9B·12B) 2표', vote(['gemma4:e4b', 'qwen3.5:9b', 'gemma4:12b'], 2))
    line('가벼운 4종(E4B·E2B·4B·9B) 2표', vote(['gemma4:e4b', 'gemma4:e2b', 'qwen3.5:4b', 'qwen3.5:9b'], 2))
    line('단계형: E4B·12B 같으면 답, 다르면 26B', cascade)
    n = sum(1 for s, i, x in rows if out['gemma4:e4b'][s][i] != out['gemma4:12b'][s][i])
    print(f"\n단계형에서 26B 를 부르는 비율: {n}/{len(rows)} = {n / len(rows):.0%}")
