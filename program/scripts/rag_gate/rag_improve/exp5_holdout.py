# 실험 5 — 보류(holdout) 세트에서 사전 등록한 변형(V0 · V1 · V5d · V7a · V7b)을 **한 번씩** 잰다(holdout/PREREG.md). 개발 세트(A · B)에서 같은 변형의 값도 같은 표에 둔다.
#  이 스크립트를 보류 세트로 돌리는 것은 한 번뿐이다 — 결과가 나온 뒤 변형을 바꿔 다시 돌리지 않는다. 결과는 results/rag_improve/holdout_result.json 에 남긴다.
# 사용: python exp5_holdout.py [--run]   (--run 이 있어야 보류 세트를 실제로 잰다. 없으면 개발 세트 표만 낸다)
import concurrent.futures as cf
import json
import os
import sys

import numpy as np

from rerank_lib import llm_rank, load_cache, save_cache
from retr_lib import CH, IDS, IDX, OUT, HERE, d2q_top2, embed, load_sets, text_A, text_E, zscore

sys.stdout.reconfigure(encoding='utf-8')
RUN = '--run' in sys.argv
SETS = load_sets()
SETS['H'] = json.load(open(os.path.join(HERE, 'holdout', 'holdout_questions.json'), encoding='utf-8'))['questions']
DA = embed([text_A(c) for c in CH])
DE = embed([text_E(c) for c in CH])
CACHE = load_cache()
MODELS = {'V7a': 'gemma4:12b', 'V7b': 'gemma4:e4b'}
NC = 10
result = {}


def metrics_rank(rows, S, label):
    order = np.argsort(-S, axis=1)
    n = h1 = h3 = 0
    rr = []
    for r, o in zip(rows, order):
        if r['type'] != 'answerable':
            continue
        gold = {IDX[g] for g in r['gold']}
        n += 1
        h1 += int(o[0]) in gold
        h3 += bool(set(o[:3].tolist()) & gold)
        pos = next((i for i, c in enumerate(o.tolist()) if c in gold), len(o))
        rr.append(1 / (pos + 1))
    return {'n': n, 'recall1': h1, 'recall3': h3, 'mrr': round(sum(rr) / len(rr), 3)}


def leak_rank(rows, S, gate, tau):
    order = np.argsort(-S, axis=1)
    neg = [(r, o, g) for r, o, g in zip(rows, order, gate) if r['type'] in ('uncovered', 'offtopic')]
    leak = sum(any(g[c] >= tau for c in o[:3]) for r, o, g in neg)
    nm = [(r, o, g) for r, o, g in zip(rows, order, gate) if r['type'] == 'near_miss']
    nms = sum(any(g[c] >= tau for c in o[:3]) for r, o, g in nm)
    return {'neg_n': len(neg), 'neg_leak': leak, 'nm_n': len(nm), 'nm_show': nms}


def run_set(name):
    rows = SETS[name]
    Q = embed([r['q'] for r in rows])
    SA, SE = Q @ DA.T, Q @ DE.T
    S5 = zscore(SE) + 1.0 * zscore(d2q_top2(Q))
    out = {}
    for lab, S, gate in (('V0', SA, SA), ('V1', SE, SE), ('V5d', S5, SE)):
        out[lab] = {**metrics_rank(rows, S, lab), **leak_rank(rows, S, gate, 0.55)}
    order = np.argsort(-S5, axis=1)
    for lab, model in MODELS.items():
        jobs = [(model, r['q'], order[i][:NC].tolist(), CACHE) for i, r in enumerate(rows)]
        with cf.ThreadPoolExecutor(max_workers=3) as ex:
            picks = list(ex.map(lambda a: llm_rank(*a), jobs))
        save_cache(CACHE)
        S7 = np.zeros_like(S5)
        for i, (jb, pk) in enumerate(zip(jobs, picks)):
            full = pk + [c for c in jb[2] if c not in pk]
            for rank, c in enumerate(full):
                S7[i, c] = 100 - rank
            S7[i, [c for c in range(len(IDS)) if c not in full]] = -1000
        m = metrics_rank(rows, S7, lab)
        shown_ok = shown_wrong = neg_leak = nm_show = 0
        for i, (r, pk) in enumerate(zip(rows, picks)):
            pk = pk[:3]
            if r['type'] == 'answerable':
                hit = bool(set(pk) & {IDX[g] for g in r['gold']})
                shown_ok += hit
                shown_wrong += (bool(pk) and not hit)
            elif r['type'] in ('uncovered', 'offtopic'):
                neg_leak += bool(pk)
            elif r['type'] == 'near_miss':
                nm_show += bool(pk)
        out[lab] = {**m, 'shown_ok': shown_ok, 'shown_wrong': shown_wrong, 'neg_n': sum(1 for r in rows if r['type'] in ('uncovered', 'offtopic')), 'neg_leak': neg_leak, 'nm_n': sum(1 for r in rows if r['type'] == 'near_miss'), 'nm_show': nm_show, 'model': model}
    return out


for name in (['A', 'B'] + (['H'] if RUN else [])):
    result[name] = run_set(name)
    print('\n##', name)
    for lab, m in result[name].items():
        extra = f" · 모델이 고른 줄에 정답 {m['shown_ok']}/{m['n']} · 틀린 줄만 {m['shown_wrong']}" if 'shown_ok' in m else ''
        print(f"{lab:4s} Recall@1 {m['recall1']}/{m['n']} · Recall@3 {m['recall3']}/{m['n']} = {m['recall3'] / m['n']:.3f} · MRR {m['mrr']}{extra} | 답 없음 {m['neg_leak']}/{m['neg_n']} 규정을 보임 | 근접·부분 {m['nm_show']}/{m['nm_n']} 보임")
if RUN:
    json.dump(result, open(os.path.join(OUT, 'holdout_result.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
