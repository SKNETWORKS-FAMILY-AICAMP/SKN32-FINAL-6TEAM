# 저장된 LLM 번호(results/llm_out.json)로 다중 모델 합의를 오프라인 재계산한다(서버·비용 없음).
# 주의: 모델 선택이 같은 90문항(test50 + hard40)의 성적에 기댄 값이라 낙관적이다 — 새 시험 세트로 다시 확인해야 한다.
import collections, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
job = json.load(open(os.path.join(HERE, 'fixtures', 'job.json'), encoding='utf-8'))['sets']
out = json.load(open(os.path.join(HERE, 'results', 'llm_out.json'), encoding='utf-8'))
HELD = ('test50', 'hard40')
gold = {s: [x['gold'] for x in job[s]['qs']] for s in HELD}


def key(m):
    return next(k for k in out if k.endswith(m) or k == m)


M = {'g26': key('gemma4:26b'), 'q38': key('qwen3.8:27b'), 'g12': key('gemma4:12b'), 'oss': key('gpt-oss:20b')}
P = {n: {s: out[k][s] for s in HELD} for n, k in M.items()}


def stat(picks):
    ok = w = fp = miss = n = 0
    for s in HELD:
        for p, g in zip(picks[s], gold[s]):
            n += 1
            ok += (p == g)
            w += p is not None and g is not None and p != g
            fp += p is not None and g is None
            miss += p is None and g is not None
    return ok, n, w, fp, miss


def show(label, picks):
    ok, n, w, fp, miss = stat(picks)
    print(f"{label:<44} 맞음 {ok}/{n}={ok / n:.0%} · 엉뚱한 답 {w + fp}(틀린 항목 {w}·없는 질문 오짚음 {fp}) · 못 찾음 {miss}")


def vote(names, need):
    res = {}
    for s in HELD:
        r = []
        for i in range(len(gold[s])):
            top, cnt = collections.Counter(P[n][s][i] for n in names).most_common(1)[0]
            r.append(top if cnt >= need else None)
        res[s] = r
    return res


def base_agree(base, others, need):
    res = {}
    for s in HELD:
        r = []
        for i in range(len(gold[s])):
            b = P[base][s][i]
            r.append(b if sum(1 for o in others if P[o][s][i] == b) >= need else None)
        res[s] = r
    return res


if __name__ == '__main__':
    for n in P:
        show(n + ' 단독', P[n])
    show('3모델 합의(26B·Qwen3.8·12B) 2표 이상', vote(['g26', 'q38', 'g12'], 2))
    show('3모델 합의 3표 전부 같을 때만', vote(['g26', 'q38', 'g12'], 3))
    show('2모델 합의(26B·Qwen3.8) 같을 때만', vote(['g26', 'q38'], 2))
    show('2모델 합의(26B·12B) 같을 때만', vote(['g26', 'g12'], 2))
    show('4모델(+gpt-oss) 3표 이상', vote(['g26', 'q38', 'g12', 'oss'], 3))
    show('26B 기본, 다른 둘 중 1개 이상 동의해야 답', base_agree('g26', ['q38', 'g12'], 1))
    show('26B 기본, 12B 와 다르면 기권', base_agree('g26', ['g12'], 1))
