# 소형(≤12B)만으로 짠 다수결·위임·규칙 결합을 769문제(요청 둘 제외, mix8~12)에서 오프라인으로 계산한다 — 새 모델 호출 없음.
#  입력: results/export/per_question.csv(기존 시험 값) + results/_pull/distill_eval/eval_r16e2_<세트>.json(가르친 E4B 의 답)
#  원칙: 같은 문제·같은 정답·null(없음)도 정답으로 센다. 비교는 짝지은 McNemar 정확검정. 구성원 선택·문턱은 개발 세트가 아니라
#        「한 세트 빼고 고르고 뺀 세트에서 시험」(leave-one-set-out)으로만 판정한다. 사전 등록 없이 본 탐색이라 결과는 「탐색」이다.
# 사용: python small_ensemble_769.py > results/small_ensemble_769.txt
import csv, itertools, json, math, os, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SETS = ['mix8', 'mix9', 'mix10', 'mix11', 'mix12']
sys.stdout.reconfigure(encoding='utf-8')


def fnum(x):
    return None if x in ('', None) else int(float(x))


rows = list(csv.DictReader(open(os.path.join(HERE, 'results/export/per_question.csv'), encoding='utf-8-sig')))
GOLD, TYPE, PICK, CALLS = {}, {}, defaultdict(dict), defaultdict(dict)
for r in rows:
    if r['set'] not in SETS:
        continue
    k = (r['set'], int(r['q_index']))
    GOLD[k] = fnum(r['gold'])
    TYPE[k] = r['q_type']
    PICK[r['model']][k] = fnum(r['pick'])
    CALLS[r['model']][k] = int(float(r['llm_calls'] or 0))
KEYS = [k for k in sorted(GOLD, key=lambda k: (SETS.index(k[0]), k[1])) if TYPE[k] != 'compound_intent']
assert len(KEYS) == 769, len(KEYS)

# 가르친 E4B(LoRA) 의 답을 같은 모양으로 붙인다
E4BT = {}
for s in SETS:
    ev = json.load(open(os.path.join(HERE, f'results/_pull/distill_eval/eval_r16e2_{s}.json'), encoding='utf-8'))
    for i, p in enumerate(ev['r16e2#lora']['picks']):
        E4BT[(s, i)] = p
PICK['E4B-가르침'] = E4BT


def find(prefix):
    c = [m for m in PICK if m.startswith(prefix)]
    assert len(c) == 1, (prefix, c)
    return c[0]


M = {
    'E4B-가르침': 'E4B-가르침',
    'E4B QAT(무학습)': find('Gemma 4 E4B QAT'),
    'Gemma 12B': find('Gemma 4 12B'),
    'Decider-12B': find('Decider-12B bf16'),
    'Winnow-12B': find('Winnow-12B Q8'),
    'Cygnet-12B': find('Cygnet(얼린'),
    'Hopper-12B': find('Hopper 12B'),
    'JevOmni-12B': find('Jev-Omni 묶음'),
    # 큰 기준
    'Gemma 26B': find('Gemma 4 26B'),
    'Qwen3.8 27B': find('Qwen3.8 27B'),
    'OpenJev 26B': find('OpenJev 26B'),
    'decider-chat 31B': find('decider-chat Gemma4-31B'),
}
COMBO = {
    'L1 규칙→E4B': find('L1 규칙→E4B'),
    'L6 규칙→게이트→E4B': find('L6 규칙→게이트'),
    'V9 전문가(E4B/E4B/12B)': find('V9 전문가'),
    'H2 L6→E4B확신↓→Decider-12B': find('H2 L6'),
    'H4 규칙→Decider-12B 확신': find('H4 규칙'),
    'L5 규칙→Decider-12B': find('L5 규칙 → Decider-12B'),
    'L5 규칙→Winnow-12B': find('L5 규칙 → Winnow-12B'),
    'Ens3 다수결(L6·V9·L5-D12)': find('Ens3'),
}
for name, m in COMBO.items():
    M[name] = m


def P(name):
    return PICK[M.get(name, name)]


def ok(model, k):
    return PICK[M.get(model, model)].get(k) == GOLD[k]


def acc(model, keys=KEYS):
    n = sum(1 for k in keys if ok(model, k))
    return n, len(keys)


def mcnemar(a, b, keys=KEYS):
    only_a = sum(1 for k in keys if ok(a, k) and not ok(b, k))
    only_b = sum(1 for k in keys if ok(b, k) and not ok(a, k))
    n = only_a + only_b
    if n == 0:
        return only_a, only_b, 1.0
    t = min(only_a, only_b)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(t + 1)) / 2 ** n)
    return only_a, only_b, p


def vote(models, tiebreak=None, keys=KEYS, name='vote'):
    out = {}
    for k in keys:
        c = Counter(P(m).get(k) for m in models)
        top = max(c.values())
        cands = [p for p, v in c.items() if v == top]
        if len(cands) == 1:
            out[k] = cands[0]
        else:
            tb = P(tiebreak).get(k) if tiebreak else None
            out[k] = tb if tb in cands else cands[0]
    PICK[name] = out
    return name


def line(label, model, ref='E4B-가르침', keys=KEYS):
    n, d = acc(model, keys)
    a, b, p = mcnemar(model, ref, keys) if ref and model != ref else (0, 0, 1.0)
    extra = '' if (not ref or model == ref) else f'  | {ref} 대비 이쪽만 {a} · 저쪽만 {b} · p={p:.3f}'
    calls = ''
    return f'{label:<42} {n:>4}/{d} = {100 * n / d:5.1f}%{extra}'


print('# 소형(≤12B)만으로 짠 구성 — 769문제(요청 둘 제외, mix8~12) 오프라인 계산\n')
print('## 1. 단독 성능 (정답 수 / 769)')
for name in M:
    if name.startswith(('L1', 'L6', 'V9', 'H2', 'H4', 'L5', 'Ens3')):
        continue
    print(line(name, M[name]))
print()
print('## 2. 기존 조합(규칙·게이트 앞단 포함) — 새로 계산하지 않고 저장된 값')
for name in COMBO:
    print(line(name, M[name]))

print('\n## 3. 소형 다수결 (구성원 ≤12B만). 동률이면 가르친 E4B 의 답')
POOLS = {
    'S3 = 가르친E4B+Decider-12B+Winnow-12B': ['E4B-가르침', 'Decider-12B', 'Winnow-12B'],
    'S3b = 가르친E4B+Decider-12B+Cygnet': ['E4B-가르침', 'Decider-12B', 'Cygnet-12B'],
    'S3c = 가르친E4B+Winnow-12B+Hopper-12B': ['E4B-가르침', 'Winnow-12B', 'Hopper-12B'],
    'S5 = 가르친E4B+Decider+Winnow+Cygnet+Hopper': ['E4B-가르침', 'Decider-12B', 'Winnow-12B', 'Cygnet-12B', 'Hopper-12B'],
    'S5b = 가르친E4B+Decider+Winnow+Cygnet+JevOmni': ['E4B-가르침', 'Decider-12B', 'Winnow-12B', 'Cygnet-12B', 'JevOmni-12B'],
    'S3d = 12B 셋(Decider·Winnow·Cygnet, E4B 없음)': ['Decider-12B', 'Winnow-12B', 'Cygnet-12B'],
}
for lab, ms in POOLS.items():
    nm = vote(ms, tiebreak='E4B-가르침' if 'E4B-가르침' in ms else ms[0], name='_v_' + lab[:3])
    print(line(lab, nm))
    # 비교 대상: 가르친 E4B 단독
print('  (구성원 호출 수 = 구성원 수 × 769. 가르친 E4B 하나는 1×)')

print('\n## 4. 합집합 천장 — 구성원 중 하나라도 맞히는 문제 (실제로 고를 방법이 있어야 의미가 있다)')
for lab, ms in [('가르친E4B + Decider-12B', ['E4B-가르침', 'Decider-12B']), ('가르친E4B + Decider + Winnow', ['E4B-가르침', 'Decider-12B', 'Winnow-12B']),
                ('가르친E4B + Decider + Winnow + Cygnet + Hopper + JevOmni', ['E4B-가르침', 'Decider-12B', 'Winnow-12B', 'Cygnet-12B', 'Hopper-12B', 'JevOmni-12B'])]:
    n = sum(1 for k in KEYS if any(ok(m, k) for m in ms))
    only_t = sum(1 for k in KEYS if ok('E4B-가르침', k) and not any(ok(m, k) for m in ms if m != 'E4B-가르침'))
    print(f'{lab:<60} {n}/769 = {100 * n / 769:.1f}% | 가르친 E4B 만 맞히는 문제 {only_t}')

print('\n## 5. 유형별 정확도 — 가르친 E4B 가 약한 유형과 그 유형에서 강한 소형')
types = sorted({TYPE[k] for k in KEYS})
cols = ['E4B-가르침', 'E4B QAT(무학습)', 'Decider-12B', 'Winnow-12B', 'Cygnet-12B', 'Hopper-12B', 'JevOmni-12B', 'Gemma 26B']
print(f'{"유형":<22} {"n":>4} ' + ' '.join(f'{c[:9]:>9}' for c in cols))
for t in types:
    ks = [k for k in KEYS if TYPE[k] == t]
    print(f'{t:<22} {len(ks):>4} ' + ' '.join(f'{100 * acc(M[c], ks)[0] / len(ks):9.1f}' for c in cols))

print('\n## 6. 유형별로 소형 전문가를 붙이면? (한 세트 빼고 유형마다 최고 소형을 고르고, 뺀 세트에서 시험 = leave-one-set-out)')
SMALL = ['E4B-가르침', 'Decider-12B', 'Winnow-12B', 'Cygnet-12B', 'Hopper-12B', 'JevOmni-12B', 'Gemma 12B', 'E4B QAT(무학습)']
route = {}
for held in SETS:
    train = [k for k in KEYS if k[0] != held]
    pick_model = {}
    for t in types:
        ks = [k for k in train if TYPE[k] == t]
        best = max(SMALL, key=lambda m: (acc(m and M[m], ks)[0], m == 'E4B-가르침'))
        pick_model[t] = best
    for k in KEYS:
        if k[0] == held:
            route[k] = PICK[M[pick_model[TYPE[k]]]].get(k)
    print(f'  {held} 를 뺐을 때 유형→모델: ' + ', '.join(f'{t.split("_")[0]}:{m[:7]}' for t, m in pick_model.items()))
PICK['LOSO-유형라우팅(유형을 안다고 가정)'] = route
print(line('유형 라우팅 (★유형을 미리 안다고 가정한 상한)', 'LOSO-유형라우팅(유형을 안다고 가정)'))
oracle = {}
for t in types:
    ks = [k for k in KEYS if TYPE[k] == t]
    best = max(SMALL, key=lambda m: acc(M[m], ks)[0])
    for k in ks:
        oracle[k] = PICK[M[best]].get(k)
PICK['ORACLE-유형'] = oracle
print(line('유형 라우팅 (같은 769 에서 고른 값 — 낙관적)', 'ORACLE-유형'))

print('\n## 7. 규칙·게이트(기계학습 앞단)가 맡는 몫 — L1/L6 에서 모델을 부르지 않은(llm_calls=0) 문제')
for name in ('L1 규칙→E4B', 'L6 규칙→게이트→E4B'):
    m = M[name]
    solved = [k for k in KEYS if CALLS[m].get(k, 1) == 0]
    good = sum(1 for k in solved if ok(m, k))
    print(f'{name}: 앞단이 처리한 문제 {len(solved)}/769 = {100 * len(solved) / 769:.1f}% · 그중 정답 {good}/{len(solved)} = {100 * good / max(1, len(solved)):.1f}%')
    byt = Counter(TYPE[k] for k in solved)
    print('   처리한 유형: ' + ', '.join(f'{t}:{v}' for t, v in byt.most_common()))
    # 앞단이 처리하지 않은 문제에서 모델 답이 무학습 E4B QAT 답과 같은가 (같다면 가르친 E4B 로 바꿔 끼워도 입력이 같다는 뜻)
    called = [k for k in KEYS if CALLS[m].get(k, 1) > 0]
    same = sum(1 for k in called if PICK[m].get(k) == PICK[M['E4B QAT(무학습)']].get(k))
    print(f'   모델을 부른 {len(called)}문제 중 무학습 E4B 직접 답과 같은 것 {same} ({100 * same / len(called):.1f}%) — 입력이 같으면 100% 에 가까워야 한다')
    # 바꿔 끼우기: 앞단이 처리한 것은 앞단 답, 나머지는 가르친 E4B 답
    sub = {k: (PICK[m].get(k) if CALLS[m].get(k, 1) == 0 else E4BT[k]) for k in KEYS}
    PICK['SUB-' + name] = sub
    print(line(f'  {name} 의 모델 자리에 가르친 E4B 를 끼움', 'SUB-' + name))
    print(f'  호출 수: 가르친 E4B 직접 769 → 이 구성 {len(called)} (앞단 처리 {len(solved)})')

print('\n## 8. 규칙·게이트 + 소형 다수결 (앞단이 처리한 문제는 앞단 답, 나머지는 가르친E4B+Decider-12B+Winnow-12B 다수결)')
m = M['L6 규칙→게이트→E4B']
S3 = vote(['E4B-가르침', 'Decider-12B', 'Winnow-12B'], tiebreak='E4B-가르침', name='S3')
mix = {k: (PICK[m].get(k) if CALLS[m].get(k, 1) == 0 else PICK[S3].get(k)) for k in KEYS}
PICK['L6-S3'] = mix
print(line('L6 앞단 + 소형 다수결', 'L6-S3'))
called = sum(1 for k in KEYS if CALLS[m].get(k, 1) > 0)
print(f'  호출 수: 앞단 처리 {769 - called}문제는 0회, 나머지 {called}문제는 3회 = {3 * called}회 (S3 단독 {3 * 769}회)')

print('\n## 9. 위임: 가르친 E4B 가 Decider-12B 와 Winnow-12B 가 둘 다 같은 다른 답을 낼 때만 따른다 (= S3 과 같음) / 12B 두 개가 합의할 때만 위임')
dele = {}
for k in KEYS:
    a, b = P('Decider-12B').get(k), P('Winnow-12B').get(k)
    t = E4BT[k]
    dele[k] = a if (a == b and a != t) else t
PICK['DELEG'] = dele
print(line('위임(E4B, 12B 둘이 합의하면 12B)', 'DELEG'))

print('\n## 10. 규칙 라우터 — 질문에 일정 항목의 이름·장소 조각이 하나도 안 들었으면(=이름 없는 묘사 후보) Decider-12B 에게, 아니면 가르친 E4B')
FEAT = {}
for s in SETS:
    job = json.load(open(os.path.join(HERE, 'fixtures', f'{s}.json'), encoding='utf-8'))['sets'][s]
    names = []
    for it in job['items']:
        for fld in ('title', 'place'):
            t = ''.join(str(it.get(fld, '')).split())
            if len(t) >= 2:
                names.append(t)

    def lcs(a, b):
        best = 0
        prev = [0] * (len(b) + 1)
        for i in range(1, len(a) + 1):
            cur = [0] * (len(b) + 1)
            for j in range(1, len(b) + 1):
                if a[i - 1] == b[j - 1]:
                    cur[j] = prev[j - 1] + 1
                    best = max(best, cur[j])
            prev = cur
        return best

    for i, q in enumerate(job['qs']):
        qt = ''.join(q['q'].split())
        ht = ''.join(''.join(h['text'].split()) for h in (q.get('history') or []))
        FEAT[(s, i)] = (max(lcs(qt, n) for n in names), max(lcs(qt + ht, n) for n in names))


def auc(pos, neg):
    # 이름 조각이 짧을수록 nameless 에 가깝다 → 점수 = −겹침
    gt = sum(1 for p in pos for n in neg if p < n) + 0.5 * sum(1 for p in pos for n in neg if p == n)
    return gt / (len(pos) * len(neg))


for fi, fname in enumerate(('질문만', '질문+앞 대화')):
    pos = [FEAT[k][fi] for k in KEYS if TYPE[k] == 'nameless_description']
    neg = [FEAT[k][fi] for k in KEYS if TYPE[k] != 'nameless_description']
    print(f'  겹침({fname}) 으로 이름 없는 묘사를 가려내는 AUC = {auc(pos, neg):.3f} (nameless {len(pos)} · 그 밖 {len(neg)})  | nameless 평균 겹침 {sum(pos) / len(pos):.2f} · 그 밖 {sum(neg) / len(neg):.2f}')

for fi, fname in enumerate(('질문만', '질문+앞 대화')):
    print(f'  [{fname}] 문턱 τ(겹침 길이 < τ 이면 Decider-12B 로) 별 — 전체 769 정확도 / 보낸 문제 수 / 보낸 문제 중 nameless 비율')
    for tau in (1, 2, 3, 4):
        r = {k: (P('Decider-12B').get(k) if FEAT[k][fi] < tau else E4BT[k]) for k in KEYS}
        PICK[f'_r{fi}{tau}'] = r
        sent = [k for k in KEYS if FEAT[k][fi] < tau]
        nm = sum(1 for k in sent if TYPE[k] == 'nameless_description')
        n, d = acc(f'_r{fi}{tau}')
        a, b, p = mcnemar(f'_r{fi}{tau}', 'E4B-가르침')
        print(f'     τ={tau}: {n}/{d} = {100 * n / d:.1f}% (E4B 대비 {a}:{b}, p={p:.3f}) · 보냄 {len(sent)} · 그중 nameless {nm}')

print('  ▶ 문턱을 한 세트 빼고 골라 그 세트에서 시험(leave-one-set-out), 특징 = 질문+앞 대화')
loso = {}
for held in SETS:
    best_tau, best_n = None, -1
    for tau in (1, 2, 3, 4):
        n = sum(1 for k in KEYS if k[0] != held and ok(f'_r1{tau}', k))
        if n > best_n:
            best_tau, best_n = tau, n
    for k in KEYS:
        if k[0] == held:
            loso[k] = PICK[f'_r1{best_tau}'][k]
    print(f'     {held} 를 뺐을 때 고른 τ={best_tau}')
PICK['LOSO-규칙라우터'] = loso
print(line('규칙 라우터(LOSO)', 'LOSO-규칙라우터'))

print('\n## 11. ML 라우터 — 질문 글자 조각(2~3-gram)과 이름 겹침 특징으로 「이름 없는 묘사」를 학습해 맞히고, 그렇다고 하면 Decider-12B 에게 (한 세트 빼고 학습 · 그 세트에서 시험)')
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from scipy.sparse import hstack, csr_matrix

QTXT = {}
for s in SETS:
    job = json.load(open(os.path.join(HERE, 'fixtures', f'{s}.json'), encoding='utf-8'))['sets'][s]
    for i, q in enumerate(job['qs']):
        QTXT[(s, i)] = q['q']
y = np.array([1 if TYPE[k] == 'nameless_description' else 0 for k in KEYS])
auc_list, pred_all = [], {}
for held in SETS:
    tr = [j for j, k in enumerate(KEYS) if k[0] != held]
    te = [j for j, k in enumerate(KEYS) if k[0] == held]
    vec = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 3), min_df=2, sublinear_tf=True)
    Xtr = vec.fit_transform([QTXT[KEYS[j]] for j in tr])
    Xte = vec.transform([QTXT[KEYS[j]] for j in te])
    ftr = csr_matrix(np.array([[FEAT[KEYS[j]][0], FEAT[KEYS[j]][1]] for j in tr], float) / 6.0)
    fte = csr_matrix(np.array([[FEAT[KEYS[j]][0], FEAT[KEYS[j]][1]] for j in te], float) / 6.0)
    clf = LogisticRegression(C=4.0, max_iter=2000, class_weight='balanced').fit(hstack([Xtr, ftr]), y[tr])
    p = clf.predict_proba(hstack([Xte, fte]))[:, 1]
    if y[te].sum() and (1 - y[te]).sum():
        auc_list.append(roc_auc_score(y[te], p))
    for j, pj in zip(te, p):
        pred_all[KEYS[j]] = pj
print('  이름 없는 묘사 판별 AUC(세트별, 그 세트를 빼고 학습): ' + ' · '.join(f'{a:.3f}' for a in auc_list) + f' | 평균 {sum(auc_list) / len(auc_list):.3f}')
for tau in (0.5, 0.6, 0.7, 0.8, 0.9):
    r = {k: (P('Decider-12B').get(k) if pred_all[k] >= tau else E4BT[k]) for k in KEYS}
    PICK[f'_ml{int(tau * 10)}'] = r
    sent = [k for k in KEYS if pred_all[k] >= tau]
    nm = sum(1 for k in sent if TYPE[k] == 'nameless_description')
    n, d = acc(f'_ml{int(tau * 10)}')
    a, b, p = mcnemar(f'_ml{int(tau * 10)}', 'E4B-가르침')
    print(f'     τ={tau}: {n}/{d} = {100 * n / d:.1f}% (E4B 대비 {a}:{b}, p={p:.3f}) · Decider-12B 로 보냄 {len(sent)} (그중 nameless {nm})')

print('\n## 12. ML 라우터를 「평가 세트 밖」 자료로만 학습 — 증류 학습 자료(Claude 가 만든 여행자 10명 · 질문 유형 라벨 있음)로 학습하고 mix8~12 769문제에서 한 번만 시험')
DJ = {}
for i in range(1, 11):
    nm = f'distill_p{i:02d}'
    DJ[f'p{i:02d}'] = json.load(open(os.path.join(HERE, 'fixtures', 'distill', f'{nm}.json'), encoding='utf-8'))['sets'][nm]
drows = []
for split in ('train', 'val'):
    for l in open(os.path.join(HERE, 'fixtures', 'distill', f'{split}.jsonl'), encoding='utf-8'):
        r = json.loads(l)
        drows.append((split, r['persona'], r['idx'], r['type']))


def feats_for(job, q):
    names = []
    for it in job['items']:
        for fld in ('title', 'place'):
            t = ''.join(str(it.get(fld, '')).split())
            if len(t) >= 2:
                names.append(t)
    qt = ''.join(q['q'].split())
    ht = ''.join(''.join(h['text'].split()) for h in (q.get('history') or []))
    return (max(lcs(qt, n) for n in names), max(lcs(qt + ht, n) for n in names))


dtext = [DJ[p]['qs'][i]['q'] for _s, p, i, _t in drows]
dfeat = np.array([feats_for(DJ[p], DJ[p]['qs'][i]) for _s, p, i, _t in drows], float) / 6.0
dy = np.array([1 if t == 'nameless_description' else 0 for _s, _p, _i, t in drows])
dsplit = np.array([s for s, _p, _i, _t in drows])
print(f'  학습 자료 {len(drows)}문제 (이름 없는 묘사 {int(dy.sum())}개) · 평가 세트 문장은 한 줄도 학습에 쓰지 않았다')
vec = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 3), min_df=2, sublinear_tf=True)
tr, va = dsplit == 'train', dsplit == 'val'
Xall = vec.fit_transform(dtext)
clf = LogisticRegression(C=4.0, max_iter=2000, class_weight='balanced').fit(hstack([Xall[tr], csr_matrix(dfeat[tr])]), dy[tr])
pv = clf.predict_proba(hstack([Xall[va], csr_matrix(dfeat[va])]))[:, 1]
best_tau, best_f1 = 0.5, -1
for tau in np.arange(0.2, 0.96, 0.05):
    pr = pv >= tau
    tp = int((pr & (dy[va] == 1)).sum())
    fp = int((pr & (dy[va] == 0)).sum())
    fn = int((~pr & (dy[va] == 1)).sum())
    f1 = 2 * tp / max(1, 2 * tp + fp + fn)
    if f1 > best_f1:
        best_tau, best_f1 = float(tau), f1
print(f'  검증 여행자(p09·p10)에서 고른 τ={best_tau:.2f} (F1 {best_f1:.2f}, AUC {roc_auc_score(dy[va], pv):.3f}) — 이 값을 시험 전에 고정')
clf = LogisticRegression(C=4.0, max_iter=2000, class_weight='balanced').fit(hstack([Xall, csr_matrix(dfeat)]), dy)
mtext = [QTXT[k] for k in KEYS]
mfeat = np.array([[FEAT[k][0], FEAT[k][1]] for k in KEYS], float) / 6.0
pm = clf.predict_proba(hstack([vec.transform(mtext), csr_matrix(mfeat)]))[:, 1]
pd_ = {k: pm[j] for j, k in enumerate(KEYS)}
print(f'  평가 769문제에서 이름 없는 묘사 판별 AUC = {roc_auc_score(y, pm):.3f}')
r = {k: (P('Decider-12B').get(k) if pd_[k] >= best_tau else E4BT[k]) for k in KEYS}
PICK['ML라우터(증류자료 학습)'] = r
sent = [k for k in KEYS if pd_[k] >= best_tau]
nm = sum(1 for k in sent if TYPE[k] == 'nameless_description')
print(line(f'가르친 E4B + 증류자료 학습 라우터(τ={best_tau:.2f}) → Decider-12B', 'ML라우터(증류자료 학습)'))
print(f'  Decider-12B 로 보낸 문제 {len(sent)} (그중 이름 없는 묘사 {nm}) · 호출 수: E4B 769 + Decider-12B {len(sent)}')
bt = Counter(TYPE[k] for k in sent)
print('  보낸 문제의 유형: ' + ', '.join(f'{t}:{v}' for t, v in bt.most_common()))
a_ = sum(1 for k in sent if E4BT[k] != GOLD[k] and P('Decider-12B').get(k) == GOLD[k])
b_ = sum(1 for k in sent if E4BT[k] == GOLD[k] and P('Decider-12B').get(k) != GOLD[k])
print(f'  보낸 문제 중 Decider-12B 가 고쳐 준 것 {a_} · 오히려 망친 것 {b_}')
