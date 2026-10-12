# 한 줄로 이은 시험 2차 — 전문가 단계를 「가르친 Jev 계열 모델(Winnow-E4B + QLoRA)」과 「가르친 E4B」 둘로 놓고 이어 붙이는 구성들을 비교한다.
#  규칙 단계와 ML 판별기(분류 인코더 거름)의 출력은 서버 C 에서 실제로 호출한 추적(results/_pull/chain/chain_no_jev.json · chain_rules_e4b.json)을 그대로 쓰고,
#  전문가 단계의 답·확신도는 서버 B 에서 같은 조건(HF 4비트 + 어댑터, 같은 학습 레시피·같은 질의문)으로 저장한 평가 결과를 쓴다 — 두 전문가를 같은 조건에서 견주려는 것이다.
#  구성: S0 단독 · S1 규칙→ML→가르친 E4B · S2 규칙→ML→가르친 Winnow-E4B · S3 가르친 E4B 확신이 낮으면 가르친 Winnow-E4B 로 인계(그 반대도) · S4 ML 유형 판별기 → 유형별 더 나은 전문가 ·
#        S5 학습한 ML 라우터(확신도·일치 여부·유형 확률로 어느 전문가 답을 쓸지) — 모든 문턱·유형별 전문가·라우터는 「한 세트 빼고 고르고 그 세트에서 시험」(leave-one-set-out)으로만 정한다.
# 사용: python chain_experts_offline.py > results/chain_experts_offline.txt
import collections
import json
import math
import os
import re
import sys

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding='utf-8')
SETS = ['mix8', 'mix9', 'mix10', 'mix11', 'mix12']
D = os.path.join(HERE, 'results', '_pull', 'distill_eval')
C = os.path.join(HERE, 'results', '_pull', 'chain')
J = lambda f: json.load(open(f, encoding='utf-8'))
JOB = {w: J(os.path.join(HERE, 'fixtures', f'{w}.json'))['sets'][w] for w in SETS}
GS = J(os.path.join(HERE, 'fixtures', 'gold_sets.json'))
norm = lambda v: None if v in (None, 'null', 'None') else (int(v) if str(v).lstrip('-').isdigit() else v)

E = {w: J(os.path.join(D, f'eval_r16e2_{w}.json'))['r16e2#lora'] for w in SETS}
EC = {w: J(os.path.join(D, f'eval_e4bconf_{w}.json'))['e4bconf#lora'] for w in SETS}
W = {w: J(os.path.join(D, f'eval_winnow_e4b_{w}.json'))['winnow_e4b#lora'] for w in SETS}
TR = {n: J(os.path.join(C, f'chain_{n}.json')) for n in ('no_jev', 'rules_e4b')}
# (세트, 번호) → 규칙 단계가 끝낸 답 · ML 판별기가 범위 밖으로 닫았는지
RULE, MLREJ = {}, set()
for x in TR['no_jev']:
    k = (x['set'], x['qi'])
    if x['ended'] == 'rules':
        RULE[k] = x['pick']
    elif x['ended'] == 'reject' and x.get('route_by') == 'ml':
        MLREJ.add(k)
Q = [(w, i) for w in SETS for i in range(len(JOB[w]['qs']))]
GOLD = {k: JOB[k[0]]['qs'][k[1]]['gold'] for k in Q}
TYPE = {k: JOB[k[0]]['qs'][k[1]]['type'] for k in Q}
PE = {k: norm(E[k[0]]['picks'][k[1]]) for k in Q}
PW = {k: norm(W[k[0]]['picks'][k[1]]) for k in Q}
CE = {k: EC[k[0]]['_confs'][k[1]] for k in Q}
CW = {k: W[k[0]]['_confs'][k[1]] for k in Q}
assert all(norm(E[w]['picks'][i]) == norm(EC[w]['picks'][i]) for w in SETS for i in range(len(JOB[w]['qs']))), '확신도 판 답이 다르다'
N769 = [k for k in Q if TYPE[k] != 'compound_intent']
COMP = [k for k in Q if TYPE[k] == 'compound_intent']


def front(k):
    """규칙·ML 거름이 끝낸 문제면 (True, 답) — 아니면 (False, None)."""
    if k in RULE:
        return True, RULE[k]
    if k in MLREJ:
        return True, None
    return False, None


def run(policy, keys):
    out = {}
    for k in keys:
        done, a = front(k)
        out[k] = a if done else policy(k)
    return out


def ok769(pred):
    return sum(pred[k] == GOLD[k] for k in N769)


def AB(pred):
    return sum(pred[k] == GOLD[k] for k in COMP), sum(pred[k] in (GS[k[0]].get(str(k[1])) or []) for k in COMP)


def mcnemar(pa, pb):
    x = sum(pa[k] == GOLD[k] and pb[k] != GOLD[k] for k in N769)
    y = sum(pb[k] == GOLD[k] and pa[k] != GOLD[k] for k in N769)
    n = x + y
    return x, y, (1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(x, y) + 1)) / 2 ** n))


def loso(select, apply, keys=Q):
    """한 세트씩 빼고 나머지로 고른 값(select)으로 그 세트를 시험(apply) — 세트별 결과를 합친다."""
    pred = {}
    for w in SETS:
        dev = [k for k in keys if k[0] != w]
        par = select(dev)
        for k in keys:
            if k[0] == w:
                done, a = front(k)
                pred[k] = a if done else apply(par, k)
    return pred, None


results = {}
results['단독 가르친 E4B(규칙·ML 없음)'] = PE
results['단독 가르친 Winnow-E4B(Jev 계열)'] = PW
results['S1 규칙 → ML → 가르친 E4B'] = run(lambda k: PE[k], Q)
results['S2 규칙 → ML → 가르친 Winnow-E4B(Jev 계열)'] = run(lambda k: PW[k], Q)

# ---- S3 확신도 인계: 앞 전문가의 확신이 문턱 미만이면 다른 전문가 답으로
GRID = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98, 0.99, 0.995, 0.999]


def sel_conf(first):
    def f(dev):
        best = None
        for t in GRID:
            s = 0
            for k in dev:
                if TYPE[k] == 'compound_intent':
                    continue
                done, a = front(k)
                if done:
                    s += a == GOLD[k]
                else:
                    c = CE[k] if first == 'E' else CW[k]
                    other = PW[k] if first == 'E' else PE[k]
                    mine = PE[k] if first == 'E' else PW[k]
                    s += (other if c < t else mine) == GOLD[k]
            if best is None or s > best[0] or (s == best[0] and t > best[1]):
                best = (s, t)
        return best[1]
    return f


def app_conf(first):
    def f(t, k):
        c = CE[k] if first == 'E' else CW[k]
        other = PW[k] if first == 'E' else PE[k]
        mine = PE[k] if first == 'E' else PW[k]
        return other if c < t else mine
    return f


S3a, _ = loso(sel_conf('E'), app_conf('E'))
S3b, _ = loso(sel_conf('W'), app_conf('W'))
results['S3a 규칙 → ML → 가르친 E4B, 확신 낮으면 가르친 Winnow-E4B 로 인계'] = S3a
results['S3b 규칙 → ML → 가르친 Winnow-E4B, 확신 낮으면 가르친 E4B 로 인계'] = S3b
TAUS = {}
for first in ('E', 'W'):
    TAUS[first] = [sel_conf(first)([k for k in Q if k[0] != w]) for w in SETS]

# ---- S4 ML 유형 판별기(증류 학습 자료의 유형으로 학습) → 유형별 더 나은 전문가
qre = re.compile(r'고객 질문:\s*(.+?)\n\n이 질문이')
tr_rows = [json.loads(l) for l in open(os.path.join(HERE, 'fixtures', 'distill', 'train_multi.jsonl'), encoding='utf-8')]
tx, ty = [], []
for r in tr_rows:
    m = qre.search(r['prompt'])
    if m:
        tx.append(m.group(1))
        ty.append(r['type'])
vec = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4), min_df=2, sublinear_tf=True)
Xtr = vec.fit_transform(tx)
clf = LogisticRegression(C=20, max_iter=2000).fit(Xtr, ty)
QTXT = {k: JOB[k[0]]['qs'][k[1]]['q'] for k in Q}
PRED_TYPE = dict(zip(Q, clf.predict(vec.transform([QTXT[k] for k in Q]))))
PTYPE_PROB = dict(zip(Q, clf.predict_proba(vec.transform([QTXT[k] for k in Q]))))
CLASSES = list(clf.classes_)
type_acc = sum(PRED_TYPE[k] == TYPE[k] for k in N769) / len(N769)


def sel_type(dev):
    best = {}
    for t in set(TYPE[k] for k in dev):
        a = sum(PE[k] == GOLD[k] for k in dev if TYPE[k] == t and not front(k)[0])
        b = sum(PW[k] == GOLD[k] for k in dev if TYPE[k] == t and not front(k)[0])
        best[t] = 'W' if b > a else 'E'
    return best


def app_type(best, k):
    return PW[k] if best.get(PRED_TYPE[k], 'E') == 'W' else PE[k]


S4, _ = loso(sel_type, app_type)
results['S4 규칙 → ML(유형 판별기) → 유형별로 더 나은 가르친 모델에 보냄'] = S4
S4types = [sel_type([k for k in Q if k[0] != w]) for w in SETS]

# ---- S5 학습한 ML 라우터: 두 전문가의 답이 다를 때 어느 쪽을 쓸지(로지스틱 — 특징: 두 확신도 · 유형 확률 11개)
def feat(k):
    return np.array([CE[k], CW[k], math.log10(1 - min(CE[k], 0.999999) + 1e-6), math.log10(1 - min(CW[k], 0.999999) + 1e-6)] + list(PTYPE_PROB[k]))


def sel_router(dev):
    rows = [k for k in dev if not front(k)[0] and PE[k] != PW[k] and TYPE[k] != 'compound_intent']
    if len(rows) < 6:
        return None
    X = np.array([feat(k) for k in rows])
    y = np.array([1 if PW[k] == GOLD[k] and PE[k] != GOLD[k] else (0 if PE[k] == GOLD[k] and PW[k] != GOLD[k] else -1) for k in rows])
    m = y >= 0
    if m.sum() < 4 or len(set(y[m])) < 2:
        return None
    mu, sd = X[m].mean(0), X[m].std(0) + 1e-6
    return (LogisticRegression(C=1.0, max_iter=1000).fit((X[m] - mu) / sd, y[m]), mu, sd, int(m.sum()))


def app_router(par, k):
    if PE[k] == PW[k] or par is None:
        return PE[k]
    clf_, mu, sd, _ = par
    return PW[k] if clf_.predict_proba(((feat(k) - mu) / sd)[None])[0][1] > 0.5 else PE[k]


S5, _ = loso(sel_router, app_router)
results['S5 규칙 → ML(학습한 라우터) → 두 가르친 모델 중 고름'] = S5
dis = sum(1 for k in N769 if not front(k)[0] and PE[k] != PW[k])

# ---- 상한(어느 쪽이든 맞히면 맞음)
UB = {k: (GOLD[k] if (PE[k] == GOLD[k] or PW[k] == GOLD[k]) else PE[k]) for k in Q}
results['(상한) 두 가르친 모델 중 하나라도 맞히면 맞음 — 고르는 방법 없음'] = run(lambda k: UB[k], Q)

print('### 전문가 단계를 가르친 Jev 계열 모델(Winnow-E4B + QLoRA)과 가르친 E4B 로 놓은 구성 — 요청 둘 제외 769문제(mix8~12)')
print('규칙·ML 판별기 단계는 서버 C 에서 실제 호출한 결과, 전문가 답·확신도는 서버 B 에서 같은 조건(HF 4비트 + 어댑터)으로 저장한 평가 결과. 문턱·유형별 전문가·라우터는 한 세트 빼고 고른 값(leave-one-set-out).')
print('| 구성 | 정답/769 | 요청 둘 A · B (/66) | 단독 가르친 E4B 와(이쪽만 : 단독만, p) |')
print('|---|---:|---|---|')
base = results['단독 가르친 E4B(규칙·ML 없음)']
for name, p in results.items():
    a, b = AB(p)
    x, y, pv = mcnemar(p, base)
    print(f'| {name} | **{ok769(p)}** ({100 * ok769(p) / len(N769):.1f}%) | {a} · {b} | ' + ('—' if p is base else f'{x} : {y} (p={pv:.3g})') + ' |')
print()
print(f'- 규칙·ML 거름이 끝낸 문제 {sum(1 for k in N769 if front(k)[0])}/769 · 두 전문가가 서로 다른 답을 낸 문제(거름 뒤) {dis}')
print(f'- 확신도 인계 문턱(세트별로 고른 값): 앞 전문가=가르친 E4B {TAUS["E"]} · 앞 전문가=가르친 Winnow-E4B {TAUS["W"]}')
print(f'- 유형 판별기(증류 학습 자료 {len(tx)}문제로 글자 2~4-gram 로지스틱 학습) 시험 세트 유형 정확도 {100 * type_acc:.1f}% · 세트별로 고른 「유형 → 전문가」: ' + ' / '.join(','.join(f'{t}:{v}' for t, v in sorted(s.items()) if v == 'W') or '모두 E4B' for s in S4types))
print('- 유형별 정답(거름 뒤 · 단독 기준): ' + ' · '.join(f"{t} E4B {sum(PE[k] == GOLD[k] for k in N769 if TYPE[k] == t)} / Winnow {sum(PW[k] == GOLD[k] for k in N769 if TYPE[k] == t)} (/{sum(1 for k in N769 if TYPE[k] == t)})" for t in sorted({TYPE[k] for k in N769})))
json.dump({n: {f'{k[0]}:{k[1]}': v for k, v in p.items()} for n, p in results.items()}, open(os.path.join(HERE, 'results', 'chain_experts_offline.json'), 'w', encoding='utf-8'), ensure_ascii=False)
