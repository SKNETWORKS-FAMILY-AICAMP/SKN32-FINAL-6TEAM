# 규정 관련성 판정 모델(교차 인코더) 학습 자료를 만든다 — 평가 세트(A · B · H · 섞은 입력)와 겹치지 않게.
#  양성(1): 조각마다 gemma4:12b 가 만든 예상 질문 6개(doc2query.json) ↔ 그 조각의 고객용 문장.
#  음성(0): ① 같은 질문의 어려운 음성 — 색인 E 점수가 높지만 **다른 문서 · 다른 절**의 조각(같은 절은 정답일 수 있어 뺀다) 3개 ② 무작위 다른 문서 조각 2개
#          ③ 규정이 아닌 말(KLUE-WoS 고객 발화, 평가에 쓴 대화는 제외) ↔ 색인 E 점수 상위 조각 4개 — 「규정 질문 아님이면 어떤 조각도 답이 아니다」를 가르친다.
#  겹침 제거: 평가 질문(A · B · H · 평가에 쓴 모든 문장)과 글자 2-gram 자카드 ≥ 0.5 인 학습 질문은 뺀다. 결과: results/rag_improve/ce_train.jsonl (+ 겹침 보고)
# 사용: python ce_build_train.py
import ast
import json
import os
import random
import sys

import numpy as np

from retr_lib import CH, HERE, IDS, OUT, embed, load_sets, text_E

sys.stdout.reconfigure(encoding='utf-8')
rnd = random.Random(20261007)
D2Q = json.load(open(os.path.join(OUT, 'doc2query.json'), encoding='utf-8'))
SETS = load_sets()
SETS['H'] = json.load(open(os.path.join(HERE, 'holdout', 'holdout_questions.json'), encoding='utf-8'))['questions']
eval_q = [r['q'] for rows in SETS.values() for r in rows]
pool = json.load(open(os.path.join(OUT, '..', 'misanswer', 'pool.json'), encoding='utf-8'))['pool'] if os.path.exists(os.path.join(OUT, '..', 'misanswer', 'pool.json')) else []
eval_q += [x['q'] for x in pool]


def grams(s):
    s = ''.join(s.split())
    return {s[i:i + 2] for i in range(len(s) - 1)} or {s}


EG = [grams(q) for q in eval_q]


def overlaps(q):
    g = grams(q)
    return any(len(g & e) / len(g | e) >= 0.5 for e in EG)


text = {i: f"{c['section']}: {c['line'] or c['content'][:160]}" for i, c in enumerate(CH)}
sec_of = {i: (c['doc_title'], c['section']) for i, c in enumerate(CH)}
DE = embed([text_E(c) for c in CH])
pairs, dropped = [], 0
for i, src in enumerate(IDS):
    for q in D2Q.get(src, []):
        if overlaps(q):
            dropped += 1
            continue
        pairs.append({'q': q, 'p': text[i], 'y': 1, 'kind': 'pos'})
        v = embed([q])[0]
        sc = DE @ v
        hard = [j for j in np.argsort(-sc)[:25] if j != i and sec_of[j] != sec_of[i] and CH[j]['doc_title'] != CH[i]['doc_title']][:3]
        for j in hard:
            pairs.append({'q': q, 'p': text[int(j)], 'y': 0, 'kind': 'hard'})
        others = [j for j in range(len(CH)) if CH[j]['doc_title'] != CH[i]['doc_title']]
        for j in rnd.sample(others, 2):
            pairs.append({'q': q, 'p': text[j], 'y': 0, 'kind': 'rand'})
print('양성 질문', sum(1 for p in pairs if p['kind'] == 'pos'), '· 평가 질문과 겹쳐 뺀 것', dropped)
# ③ 규정이 아닌 말 — KLUE-WoS 고객 발화
base = os.path.join(HERE, '..', '..', '..', '..', 'datasets', 'travel', 'klue_wos', 'processed', 'dialogues.jsonl')
utts = []
for line in open(base, encoding='utf-8'):
    d = json.loads(line)
    turns = d['turns'] if isinstance(d['turns'], list) else ast.literal_eval(d['turns'])
    utts += [t['text'] for t in turns if t.get('role') == 'customer' and 4 <= len(t['text']) <= 100]
utts = [u for u in dict.fromkeys(utts) if not overlaps(u)]
rnd.shuffle(utts)
wos = utts[:500]
V = embed(wos)
for k, u in enumerate(wos):
    sc = DE @ V[k]
    for j in np.argsort(-sc)[:4]:
        pairs.append({'q': u, 'p': text[int(j)], 'y': 0, 'kind': 'nonreg'})
rnd.shuffle(pairs)
import collections
print('학습 쌍', len(pairs), dict(collections.Counter(p['kind'] for p in pairs)))
with open(os.path.join(OUT, 'ce_train.jsonl'), 'w', encoding='utf-8') as f:
    for p in pairs:
        f.write(json.dumps(p, ensure_ascii=False) + '\n')
print('저장', os.path.join(OUT, 'ce_train.jsonl'))
