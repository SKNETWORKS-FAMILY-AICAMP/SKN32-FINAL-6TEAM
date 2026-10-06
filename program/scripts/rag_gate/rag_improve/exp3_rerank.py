# 실험 3 — 1단계(색인 E + 예상 질문 상위 2 평균)로 후보 10개를 뽑고, 모델이 「고객 질문에 직접 답하는 줄」을 골라 순서를 다시 매긴다(재순위).
#  모델: x600 서버 Ollama(기본 gemma4:12b, 생각 끔, 온도 0). 결과는 results/rag_improve/rerank_cache.json 에 질문·후보·모델 키로 캐시한다.
#  지표: 재순위 뒤 상위 3 안에 정답이 있는 비율(Recall@3) — 1단계 상위 10 안에 정답이 있는 비율이 천장이다. 모델이 고르지 않은 후보는 1단계 순서대로 뒤에 둔다.
# 사용: python exp3_rerank.py [모델] [후보수] [세트들: A,B]
import concurrent.futures as cf
import hashlib
import json
import os
import sys
import time
import urllib.request

import numpy as np

from retr_lib import CH, IDS, IDX, OLLAMA, OUT, embed, load_sets, recall_at, text_E, zscore

MODEL = sys.argv[1] if len(sys.argv) > 1 else 'gemma4:12b'
NC = int(sys.argv[2]) if len(sys.argv) > 2 else 10
WHICH = sys.argv[3].split(',') if len(sys.argv) > 3 else ['A', 'B']
sys.stdout.reconfigure(encoding='utf-8')
CP = os.path.join(OUT, 'rerank_cache.json')
CACHE = json.load(open(CP, encoding='utf-8')) if os.path.exists(CP) else {}
SYSTEM = ('당신은 여행 서비스의 규정 검색 재순위 담당입니다. 고객 질문과 후보 안내 문장들이 주어집니다. '
          '각 후보는 서비스가 고객에게 그대로 보여 줄 안내 문장입니다. 고객 질문에 **직접 답이 되는** 문장만 골라 가장 알맞은 순서로 번호를 적습니다. '
          '관련 주제여도 질문이 묻는 구체 내용에 답하지 않는 문장은 고르지 않습니다. 직접 답하는 문장이 없으면 빈 목록입니다. 최대 3개. '
          '출력은 JSON 한 줄: {"ranking":[번호,...]}')


def d2q_scores(rows, Q):
    d2q = json.load(open(os.path.join(OUT, 'doc2query.json'), encoding='utf-8'))
    flat, owner = [], []
    for i, s in enumerate(IDS):
        for q in d2q.get(s, []):
            flat.append(q)
            owner.append(i)
    owner = np.array(owner)
    G = embed(flat)
    sim = Q @ G.T
    top2 = np.zeros((Q.shape[0], len(IDS)), dtype=np.float32)
    for i in range(len(IDS)):
        cols = np.where(owner == i)[0]
        top = np.sort(sim[:, cols], axis=1)[:, ::-1][:, :2]
        top2[:, i] = top.mean(axis=1)
    return top2


def first_stage(rows):
    DE = embed([text_E(c) for c in CH])
    Q = embed([r['q'] for r in rows])
    SE = Q @ DE.T
    return zscore(SE) + 1.0 * zscore(d2q_scores(rows, Q)), SE


def llm_rank(q, cand):
    lines = '\n'.join(f"{k + 1}. [{CH[c]['section']}] {CH[c]['line'] or CH[c]['content'][:120]}" for k, c in enumerate(cand))
    key = hashlib.sha1(('\n'.join([MODEL, q, ','.join(map(str, cand))])).encode('utf-8')).hexdigest()
    if key in CACHE:
        return CACHE[key]
    body = {'model': MODEL, 'stream': False, 'think': False, 'format': 'json', 'options': {'temperature': 0},
            'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': f'고객 질문: {q}\n\n후보 안내 문장:\n{lines}'}]}
    out = None
    for _ in range(3):
        try:
            req = urllib.request.Request(OLLAMA + '/api/chat', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
            r = json.loads(urllib.request.urlopen(req, timeout=600).read())
            rk = json.loads(r['message']['content']).get('ranking', [])
            out = [cand[int(n) - 1] for n in rk if isinstance(n, int) and 1 <= n <= len(cand)]
            break
        except Exception:  # noqa: BLE001
            time.sleep(2)
    CACHE[key] = out if out is not None else []
    return CACHE[key]


SETS = load_sets()
for name in WHICH:
    rows = SETS[name]
    S1, SE = first_stage(rows)
    order = np.argsort(-S1, axis=1)
    jobs = [(r['q'], order[i][:NC].tolist()) for i, r in enumerate(rows)]
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        picks = list(ex.map(lambda a: llm_rank(*a), jobs))
    json.dump(CACHE, open(CP, 'w', encoding='utf-8'), ensure_ascii=False)
    S2 = np.zeros_like(S1)
    for i, (jb, pk) in enumerate(zip(jobs, picks)):
        cand = jb[1]
        rest = [c for c in cand if c not in pk]
        full = pk + rest
        for rank, c in enumerate(full):
            S2[i, c] = 100 - rank
        for c in range(len(IDS)):
            if c not in full:
                S2[i, c] = S1[i, c] - 1000
    h1, n, m1 = recall_at(rows, S1, 3)
    h2, _, m2 = recall_at(rows, S2, 3)
    h10 = sum(1 for r, o in zip(rows, order) if r['type'] == 'answerable' and ({IDX[g] for g in r['gold']} & set(o[:NC].tolist())))
    empty = sum(1 for p in picks if not p)
    print(f'{name}: 1단계 Recall@3 {h1}/{n} = {h1 / n:.3f} → 재순위({MODEL}, 후보 {NC}) {h2}/{n} = {h2 / n:.3f} · MRR {m1:.3f} → {m2:.3f} · 후보 안 천장 {h10}/{n} · 모델이 아무것도 안 고름 {empty}/{len(rows)} · {round(time.time() - t0)}초')
