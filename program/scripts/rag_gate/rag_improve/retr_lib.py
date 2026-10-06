# 규정 검색 개선 실험 공용 도구 — 규정 조각 130개 · 질문 세트 · 임베딩 캐시(x600 서버 Ollama bge-m3) · 지표.
#  원칙(2026-10-06 사용자 지시를 받은 cs 서버 세션의 요청): 개발은 A(180)·B(160)로만 하고, 새로 만든 보류 세트(holdout)는 마지막에 한 번만 잰다.
#  임베딩은 텍스트 해시로 디스크에 캐시한다(results/rag_improve/emb_cache.json — git 에 올리지 않는다).
import hashlib
import json
import math
import os
import re
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RG = os.path.abspath(os.path.join(HERE, '..'))
OUT = os.path.join(RG, 'results', 'rag_improve')
os.makedirs(OUT, exist_ok=True)
OLLAMA = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434')
EMB_MODEL = 'bge-m3:latest'
CACHE_PATH = os.path.join(OUT, 'emb_cache.json')
_CACHE = json.load(open(CACHE_PATH, encoding='utf-8')) if os.path.exists(CACHE_PATH) else {}


def J(*a):
    return json.load(open(os.path.join(RG, *a), encoding='utf-8'))


CH = J('fixtures', 'policy_chunks.json')
IDS = [c['source'] for c in CH]
IDX = {s: i for i, s in enumerate(IDS)}


def _key(t):
    return hashlib.sha1((EMB_MODEL + '\n' + t).encode('utf-8')).hexdigest()


def embed(texts, batch=16):
    """텍스트 목록 → 정규화한 임베딩 행렬. 캐시에 없는 것만 Ollama 에 보낸다."""
    need = [t for t in dict.fromkeys(texts) if _key(t) not in _CACHE]
    for k in range(0, len(need), batch):
        part = need[k:k + batch]
        req = urllib.request.Request(OLLAMA + '/api/embed', data=json.dumps({'model': EMB_MODEL, 'input': part}).encode(), headers={'Content-Type': 'application/json'})
        vs = json.loads(urllib.request.urlopen(req, timeout=900).read())['embeddings']
        for t, v in zip(part, vs):
            _CACHE[_key(t)] = v
    if need:
        json.dump(_CACHE, open(CACHE_PATH, 'w', encoding='utf-8'))
    M = np.array([_CACHE[_key(t)] for t in texts], dtype=np.float32)
    return M / np.linalg.norm(M, axis=1, keepdims=True)


def text_A(c):      # 운영 색인(직원용 본문)
    return c['content']


def text_E(c):      # 색인 E(문서 제목 + 절 제목 + 고객용 문장, 문장이 없으면 본문)
    return f"{c['doc_title']} / {c['section']}: {c['line'] or c['content']}"


def load_sets():
    """A(180) · B(160) — 개발용. 각 질문: q · type · gold(정답 줄) · partial(B 의 부분 답 줄)."""
    A = J('fixtures', 'rag_questions.json')['questions']
    B = J('blind', 'fixtures', 'rag_questions.json')['questions']
    for r in A:
        r.setdefault('partial', [])
    return {'A': A, 'B': B}


def ranks_from_scores(S):
    """S: (질문수 × 130) 점수 → 질문마다 조각 번호 내림차순."""
    return np.argsort(-S, axis=1)


def recall_at(rows, S, k=3):
    """답 있음(answerable) 질문에서 정답 줄이 상위 k 안인 질문 수와 비율, MRR."""
    order = ranks_from_scores(S)
    hit = n = 0
    rr = []
    for r, o in zip(rows, order):
        if r['type'] != 'answerable':
            continue
        gold = {IDX[g] for g in r['gold']}
        n += 1
        top = set(o[:k].tolist())
        hit += bool(top & gold)
        pos = next((i for i, c in enumerate(o.tolist()) if c in gold), len(o))
        rr.append(1 / (pos + 1))
    return hit, n, (sum(rr) / len(rr) if rr else 0.0)


def leak_at(rows, S, gate, tau, k=3):
    """답 없는 질문(uncovered · offtopic)에서 게이트 점수(gate: 질문 × 130)가 문턱 이상인 조각이 상위 k 안에 있는 질문 수 — 운영 규칙(문턱 이상만 보임)의 재현."""
    order = ranks_from_scores(S)
    leak = n = 0
    for r, o, g in zip(rows, order, gate):
        if r['type'] not in ('uncovered', 'offtopic'):
            continue
        n += 1
        leak += any(g[c] >= tau for c in o[:k])
    return leak, n


def answer_rate(rows, S, gate, tau, k=3):
    """답 있음 질문 중 문턱 이상인 조각이 하나라도 보이는 비율(운영의 「답함」) + 그중 정답 줄이 보인 수."""
    order = ranks_from_scores(S)
    ans = ok = n = 0
    for r, o, g in zip(rows, order, gate):
        if r['type'] != 'answerable':
            continue
        n += 1
        shown = [c for c in o[:k] if g[c] >= tau]
        ans += bool(shown)
        ok += bool(set(shown) & {IDX[x] for x in r['gold']})
    return ans, ok, n


def bm25_ngram(docs, queries, n=2, k1=1.2, b=0.75):
    """한국어 글자 n-gram BM25 — 형태소 분석기 없이 조사·어미 변화를 흡수한다. 반환: (질문수 × 문서수) 점수."""
    def grams(t):
        t = re.sub(r'\s+', '', t)
        return [t[i:i + n] for i in range(max(len(t) - n + 1, 1))]
    D = [grams(d) for d in docs]
    avg = sum(len(d) for d in D) / len(D)
    df = {}
    for d in D:
        for g in set(d):
            df[g] = df.get(g, 0) + 1
    N = len(D)
    idf = {g: math.log(1 + (N - c + 0.5) / (c + 0.5)) for g, c in df.items()}
    tf = []
    for d in D:
        m = {}
        for g in d:
            m[g] = m.get(g, 0) + 1
        tf.append(m)
    S = np.zeros((len(queries), N), dtype=np.float32)
    for qi, q in enumerate(queries):
        qg = set(grams(q))
        for di in range(N):
            s = 0.0
            for g in qg:
                f = tf[di].get(g)
                if f:
                    s += idf[g] * f * (k1 + 1) / (f + k1 * (1 - b + b * len(D[di]) / avg))
            S[qi, di] = s
    return S


def zscore(S):
    return (S - S.mean(axis=1, keepdims=True)) / (S.std(axis=1, keepdims=True) + 1e-9)


def d2q_top2(Q, src='doc2query.json'):
    """질문 임베딩 Q → 조각별 「예상 질문(doc2query)과의 유사도 상위 2개 평균」(질문수 × 130). gen_doc2query.py 의 결과를 쓴다."""
    d2q = json.load(open(os.path.join(OUT, src), encoding='utf-8'))
    flat, owner = [], []
    for i, s in enumerate(IDS):
        for q in d2q.get(s, []):
            flat.append(q)
            owner.append(i)
    owner = np.array(owner)
    G = embed(flat)
    sim = Q @ G.T
    out = np.zeros((Q.shape[0], len(IDS)), dtype=np.float32)
    for i in range(len(IDS)):
        cols = np.where(owner == i)[0]
        if len(cols):
            out[:, i] = np.sort(sim[:, cols], axis=1)[:, ::-1][:, :2].mean(axis=1)
    return out
