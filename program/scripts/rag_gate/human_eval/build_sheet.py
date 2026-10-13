# 사람 평가용 표본 시트 만들기 — 사람이 아직 평가하지 않았다. 이 시트는 「평가할 자료」일 뿐 점수가 아니다(점수 칸은 비어 있다).
#  재료: 제품 경로로 이미 만든 답(규정 질문 답 · 알림 번역)에서 층을 나눠 뽑는다. 질문은 전부 Codex 합성 · 알림은 내가 쓴 합성 문구라 실제 고객 문장이 아니다.
#  평가자 2명이 같은 시트를 각자 채워 일치도(kappa)를 본다(score.py). 모델이 매긴 점수는 「모델 평가」라고 따로 표시하고 사람 점수처럼 쓰지 않는다.
# 사용: python build_sheet.py  → human_eval_sheet.csv (평가자 A·B 열은 비어 있다), human_eval_key.json (층·기계 판정 — 평가자에게 보여 주지 않는다)
import csv
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'results')
rnd = random.Random(20261006)
J = lambda f: json.load(open(os.path.join(RES, f), encoding='utf-8'))
items = []     # (종류, 층, 입력, 답, 기계 판정)

corr = J('rag_live_correct.json')['correct']
pool = {'정답 줄을 보임': [], '틀린 줄만 보임': [], '근접·부분 답 질문에 답함': [], '답 없는 질문에 답함(새어 나감)': [], '답 없는 질문을 거절': []}
for name in ('A', 'B'):
    for r in corr[name]:
        gold, srcs = set(r['gold']), r['sources']
        if r['type'] == 'answerable':
            if srcs and (set(srcs) & gold):
                pool['정답 줄을 보임'].append((name, r))
            elif srcs:
                pool['틀린 줄만 보임'].append((name, r))
        elif r['type'] == 'near_miss' and srcs:
            pool['근접·부분 답 질문에 답함'].append((name, r))
        elif r['type'] in ('uncovered', 'offtopic'):
            pool['답 없는 질문에 답함(새어 나감)' if srcs else '답 없는 질문을 거절'].append((name, r))
quota = {'정답 줄을 보임': 6, '틀린 줄만 보임': 6, '근접·부분 답 질문에 답함': 5, '답 없는 질문에 답함(새어 나감)': 3, '답 없는 질문을 거절': 4}
for st, n in quota.items():
    for name, r in rnd.sample(pool[st], min(n, len(pool[st]))):
        items.append(('규정 질문 답', st, r['q'], r.get('answer') or '', {'세트': name, '출처': r['sources']}))

tg = J('translate_guard_live.json')['rows']
byst = {'보호 장치 통과': [r for r in tg if r['status'] == 'passed' and not ({'time', 'money'} & set(r['indep']))],
        '보호 장치가 거름': [r for r in tg if r['status'] == 'guard_rejected']}
for st, n in (('보호 장치 통과', 8), ('보호 장치가 거름', 3)):
    for r in rnd.sample(byst[st], min(n, len(byst[st]))):
        items.append(('알림 번역', st, '[원문 한국어 알림 → ' + r['lang'] + '] ' + r['src'], r['raw'], {'언어': r['lang'], '독립 검사': r['indep']}))

rnd.shuffle(items)
cols = ['id', '종류', '고객 입력', '시스템 답'] + [f'평가자{p}_{c}' for p in 'AB' for c in ('정확성', '근거충실', '질문에맞음', '자연스러움', '안전성', '메모')]
key = []
with open(os.path.join(HERE, 'human_eval_sheet.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for i, (kind, st, q, a, mach) in enumerate(items, 1):
        rid = f'H{i:03d}'
        w.writerow({'id': rid, '종류': kind, '고객 입력': q, '시스템 답': a})
        key.append({'id': rid, '종류': kind, '층': st, '기계 판정': mach})
json.dump(key, open(os.path.join(HERE, 'human_eval_key.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('표본', len(items), '개 — 종류:', {k: sum(1 for x in items if x[0] == k) for k in ('규정 질문 답', '알림 번역')})
