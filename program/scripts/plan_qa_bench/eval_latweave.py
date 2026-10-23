# LatWeave(2609.27225) 아이디어 반영 전후 비교 — 「구조적 기권」(후보 0개면 모델 없이 없음) · 「되묻기」(날짜가 있고 후보 2~5개) · 근거 기록.
#  같은 배치(E4B/E4B/12B) · 같은 문제(heavy 판정 88 · mix4 88)에서 latweave=False(이전) 와 True(반영) 를 한 번씩만 잰다.
#  주의: mix4 는 이미 한 번 판정에 쓴 세트라 「처음 보는 세트」가 아니다(이 변경은 mix4 오류를 보고 만들지 않았고 논문 아이디어에서 왔다).
# 사용: python eval_latweave.py
import json
from eval_pipeline import load, run_one, LAST

REG = ('gemma4:e4b', 'gemma4:e4b', 'gemma4:12b')
trace = []
for job in ('heavy', 'mix4'):
    qs, items, out = load(job)
    idx = [i for i, x in enumerate(qs) if x.get('split', 'held') == 'held']
    res = {}
    for lw in (False, True):
        ok = bad = miss = 0
        clar = clar_hit = clar_none = struct_none = 0
        why_rows = []
        for i in idx:
            p, calls, how = run_one(i, REG, qs, items, out, latweave=lw)
            g = qs[i]['gold']
            if lw:
                trace.append({'job': job, 'q': qs[i]['q'], 'path': how, 'why': LAST.get('why'), 'slots': {k: v for k, v in (LAST.get('slots') or {}).items() if v not in (None, False)},
                              'answer': p[1] if how == 'clarify' else p, 'gold': g, 'experts': [f'{r}:{m.split(":")[1]}' for r, m in calls]})
            if how == 'clarify':
                clar += 1
                clar_hit += (g in p[1])
                clar_none += (g is None)
                why_rows.append((qs[i]['q'], p[1], p[2], g))
                continue
            ok += (p == g); bad += (p is not None and p != g); miss += (p is None and g is not None)
            if lw and how == 'struct' and p is None:
                struct_none += 1
        res[lw] = (ok, bad, miss, clar, clar_hit, clar_none, struct_none, why_rows)
    n = len(idx)
    a, b = res[False], res[True]
    print(f"## {job} ({n}문제)")
    print(f"  이전            정답 {a[0]} · 엉뚱 {a[1]} · 못 찾음 {a[2]}")
    print(f"  LatWeave 반영   정답 {b[0]} · 엉뚱 {b[1]} · 못 찾음 {b[2]} · 되물음 {b[3]} (그중 정답 항목이 후보에 포함 {b[4]} · 정답이 「없음」인 문제에 되물음 {b[5]}) · 구조가 모델 없이 「없음」 처리 {b[6]}")
    for q, ids, why, g in b[7]:
        print(f"     되물음: 「{q}」 → 후보 {ids} (정답 {g}) — {why}")

import os
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results', 'trace_latweave.jsonl'), 'w', encoding='utf-8') as f:
    for t in trace:
        f.write(json.dumps(t, ensure_ascii=False) + chr(10))
print('근거 기록', len(trace), '건 → results/trace_latweave.jsonl')
for t in trace[-3:]:
    print('  예:', t)
