"""Travel-only, cache-only development comparison. Public equations independently implemented.

References: arXiv:2610.09412v1 (RNG/Vendi rule), arXiv:2609.34776v1 (RRF).
Does not read used holdout H, contact a model, edit caches, or change product retrieval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import time
from pathlib import Path

import numpy as np


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def order(scores):
    return np.argsort(-np.asarray(scores), kind="stable")


def vendi(vectors):
    kernel = vectors @ vectors.T / len(vectors)
    eig = np.clip(np.linalg.eigvalsh(kernel), 0, None)
    eig = eig / eig.sum()
    nz = eig[eig > 0]
    return float(np.clip(np.exp(-np.sum(nz * np.log(nz))), 1, len(vectors)))


def rng_order(similarities, vectors, gamma=0.0):
    distance = 1 - np.clip(similarities, -1, 1)
    pair_distance = 1 - np.clip(vectors @ vectors.T, -1, 1)
    closer = distance[:, None] < distance[None, :]
    obstruction = np.maximum(distance[None, :] - pair_distance + gamma, 0)
    score = distance + (obstruction * closer).sum(axis=0)
    return np.argsort(score, kind="stable")


def mmr_order(similarities, vectors, k, weight=0.7):
    selected = [int(order(similarities)[0])]
    pairs = vectors @ vectors.T
    while len(selected) < min(k, len(vectors)):
        scores = weight * similarities - (1 - weight) * pairs[:, selected].max(axis=1)
        scores[selected] = -np.inf
        selected.append(int(order(scores)[0]))
    return np.array(selected)


def adaptive(similarities, vectors, k, requirement, weight):
    baseline = order(similarities)[:k]
    effective = vendi(vectors[baseline])
    trigger = effective < min(requirement, k)
    return (mmr_order(similarities, vectors, k, weight) if trigger else baseline), effective, trigger


def bm25(docs, questions, n, k1, b):
    def grams(t):
        t = ''.join(t.split())
        return [t[i:i+n] for i in range(max(len(t)-n+1, 1))]
    tokenized = [grams(t) for t in docs]
    average = sum(map(len, tokenized)) / len(docs)
    counts, df = [], {}
    for doc in tokenized:
        count = {}
        for token in doc:
            count[token] = count.get(token, 0) + 1
        counts.append(count)
        for token in count:
            df[token] = df.get(token, 0) + 1
    scores = np.zeros((len(questions), len(docs)))
    for qi, question in enumerate(questions):
        for di, count in enumerate(counts):
            for token in set(grams(question)):
                f = count.get(token, 0)
                if f:
                    idf = math.log(1 + (len(docs)-df[token]+0.5)/(df[token]+0.5))
                    scores[qi,di] += idf*f*(k1+1)/(f+k1*(1-b+b*len(tokenized[di])/average))
    return scores


def rrf(first, second, constant, pool):
    score = np.zeros(len(first))
    for ranks in (order(first), order(second)):
        score[ranks[:pool]] += 1 / (constant + np.arange(1, min(pool, len(ranks))+1))
    return order(score)


def paired(before, after, seed, repetitions):
    x = np.array(after, dtype=int) - np.array(before, dtype=int)
    a, b = int((x==1).sum()), int((x==-1).sum())
    discordant = a+b
    p = min(1.0, 2*sum(math.comb(discordant, i) for i in range(min(a,b)+1))/2**discordant) if discordant else 1.0
    rng = np.random.default_rng(seed)
    boot = x[rng.integers(0, len(x), size=(repetitions, len(x)))].mean(axis=1)
    return {"after_only": a, "before_only": b, "exact_mcnemar_p": p, "difference": float(x.mean()), "bootstrap_95": np.quantile(boot,[0.025,0.975]).tolist()}


def self_test():
    eye = np.eye(3)
    assert np.isclose(vendi(eye), 3)
    assert np.isclose(vendi(np.ones((3,1))), 1)
    sim = np.array([0.9,0.8,0.6])
    assert rng_order(sim, eye, -2).tolist() == order(sim).tolist()
    tied = np.array([0.9,0.9,0.6])
    assert rng_order(tied, eye, -2).tolist() == [0,1,2]
    pick, _, triggered = adaptive(sim, eye, 3, 1, 0.7)
    assert not triggered and pick.tolist() == [0,1,2]
    assert paired([False,False,True],[True,True,True],1,100)["exact_mcnemar_p"] == 0.5
    try:
        cached_vectors(["missing"], {}, "bge-m3:latest")
    except ValueError:
        pass
    else:
        raise AssertionError("missing cache must fail")
    return {"passed": 7, "total": 7}


def cached_vectors(texts, cache, model):
    keys = [hashlib.sha1((model+'\n'+text).encode()).hexdigest() for text in texts]
    missing = [key for key in keys if key not in cache]
    if missing:
        raise ValueError(f"Missing {len(missing)}/{len(keys)} cached embeddings; no requests made")
    matrix = np.array([cache[key] for key in keys],dtype=np.float64)
    norms = np.linalg.norm(matrix,axis=1,keepdims=True)
    if matrix.ndim != 2 or not np.isfinite(matrix).all() or (norms==0).any():
        raise ValueError("Malformed cached embeddings")
    return matrix/norms


def run(root, out):
    if out.exists():
        raise FileExistsError(out)
    prereg = root/'program/research/daily_rag_slm/2026-10-09_retrieval_prereg_v1.json'
    contract = json.loads(prereg.read_text(encoding='utf-8'))
    rg = root/'program/scripts/rag_gate'
    sources = [prereg,rg/'fixtures/policy_chunks.json',rg/'results/rag_improve/emb_cache.json']
    chunks = json.loads(sources[1].read_text(encoding='utf-8'))
    assert len(chunks)==130 and all(c['scope'].startswith('travel_') for c in chunks)
    ids = [c['source'] for c in chunks]
    assert len(set(ids)) == len(ids)
    cache = json.loads(sources[2].read_text(encoding='utf-8'))
    texts = [f"{c['doc_title']} / {c['section']}: {c['line'] or c['content']}" for c in chunks]
    vectors = cached_vectors(texts,cache,'bge-m3:latest')
    p = contract['parameters']; k = p['top_k']; pool = p['candidate_pool']
    all_rows, summaries = [], {}
    for name, relative in contract['datasets'].items():
        path = root/relative; sources.append(path)
        rows = json.loads(path.read_text(encoding='utf-8'))['questions']
        if any(r['type'] not in ('answerable','uncovered','offtopic','near_miss') for r in rows):
            raise ValueError('Unknown type')
        if any(g not in ids for r in rows for g in r['gold']):
            raise ValueError('Unknown gold source')
        queries = cached_vectors([r['q'] for r in rows],cache,'bge-m3:latest')
        sims = queries @ vectors.T
        lexical = bm25(texts,[r['q'] for r in rows],p['BM25_char_ngram'],p['BM25_k1'],p['BM25_b'])
        results = {v: [] for v in contract['variants']}
        for qi, row in enumerate(rows):
            nearest = order(sims[qi]); cand = nearest[:pool]
            for variant in contract['variants']:
                start = time.perf_counter_ns(); triggered = False; effective = None
                if variant == 'dense_E':
                    selected = nearest[:k]
                elif variant == 'RRF_dense_BM25':
                    selected = rrf(sims[qi],lexical[qi],p['rrf_rank_constant'],p['rrf_each_pool'])[:k]
                elif variant == 'RNG_gamma0':
                    selected = cand[rng_order(sims[qi,cand],vectors[cand],p['RNG_gamma'])[:k]]
                else:
                    h = 1 if variant == 'adaptive_MMR_h1' else 2
                    local, effective, triggered = adaptive(sims[qi,cand],vectors[cand],k,h,p['MMR_lambda'])
                    selected = cand[local]
                latency = (time.perf_counter_ns()-start)/1e6
                chosen = [ids[c] for c in selected]
                shown = [ids[c] for c in selected if sims[qi,c]>=p['display_cosine_threshold']]
                gold = set(row['gold'])
                rec = {"set": name, "row": qi, "type": row['type'], "question_sha256": hashlib.sha256(row['q'].encode()).hexdigest(), "variant": variant, "selected": chosen, "shown": shown, "recall3": bool(gold.intersection(chosen)), "shown_gold": bool(gold.intersection(shown)), "shown_wrong_only": bool(shown) and not gold.intersection(shown), "trigger": bool(triggered), "effective": effective, "selector_ms": latency}
                results[variant].append(rec); all_rows.append(rec)
        summaries[name] = {}
        for variant, records in results.items():
            positives = [r for r in records if r['type']=='answerable']
            negatives = [r for r in records if r['type'] in ('uncovered','offtopic')]
            near = [r for r in records if r['type']=='near_miss']
            base = [r for r in results['dense_E'] if r['type']=='answerable']
            lat = [r['selector_ms'] for r in records]
            m = {"complete": len(records), "expected": len(rows), "failures": 0, "recall3": sum(r['recall3'] for r in positives), "positive_n": len(positives), "shown_gold": sum(r['shown_gold'] for r in positives), "wrong_only": sum(r['shown_wrong_only'] for r in positives), "null_false_show": sum(bool(r['shown']) for r in negatives), "null_n": len(negatives), "near_show": sum(bool(r['shown']) for r in near), "near_n": len(near), "trigger": sum(r['trigger'] for r in records), "selector_ms_median": float(np.median(lat)), "selector_ms_p95": float(np.quantile(lat,.95)), "paired_recall3_vs_dense": paired([r['recall3'] for r in base],[r['recall3'] for r in positives],p['bootstrap_seed'],p['bootstrap_repetitions'])}
            summaries[name][variant] = m
    baseline = 'dense_E'
    gates = {}
    for v in contract['variants']:
        gates[v] = all(m[v]['recall3']/m[v]['positive_n']>=contract['candidate_gate']['each_set_recall_at3_min'] and m[v]['null_false_show']/m[v]['null_n']<=contract['candidate_gate']['each_set_null_false_show_max'] and m[v]['shown_gold']>=m[baseline]['shown_gold'] and m[v]['null_false_show']<=m[baseline]['null_false_show'] for m in summaries.values())
    output = {"schema_version": 1, "observed_at_utc": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(), "self_test": self_test(), "runtime": {"python": platform.python_version(),"numpy": np.__version__,"platform": platform.platform()}, "input_sha256": {str(path.relative_to(root)).replace('\\','/'):sha(path) for path in sources}, "parameters": p, "summaries": summaries, "development_gate": gates, "adopted": False, "independent_validation": "pending; previously used H not read", "latency_scope": "CPU selector only, existing cached embeddings; excludes BM25 construction, embedding and generation; one deterministic data run, timing observations descriptive"}
    out.mkdir(parents=True)
    (out/'summary.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'decisions.jsonl').write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in all_rows)+'\n',encoding='utf-8')
    print(json.dumps({"self_test":output['self_test'],"summaries":summaries,"development_gate":gates},ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[4])
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    run(args.root,args.out)
