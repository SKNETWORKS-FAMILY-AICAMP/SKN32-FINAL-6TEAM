# C 채점(요청 둘 「둘 다 찾기」 = 항목 집합이 정답 집합과 정확히 같다)까지 넣은 비교 — 새 모델 호출 없음, 이미 있는 결과 파일만 읽는다.
#  채점 세 가지(§61): A = 먼저 말한 항목 하나(정답 gold) · B = 말한 항목 중 하나라도 맞히면 정답 · C = 고른 집합이 정답 집합과 정확히 같음.
#  정답 집합: fixtures/gold_sets.json (한 항목 583 · 없음 186(빈 집합) · 둘 66).
#  한 항목만 고르는 모델은 요청 둘(66)에서 C 가 0 이다(집합 크기가 다르다) — 그래서 「C 전체 = 요청 둘 제외 정답 수 / 835」가 된다.
# 사용: python c_scoring_all.py > results/c_scoring_all.txt
import csv, json, math, os, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SETS = ['mix8', 'mix9', 'mix10', 'mix11', 'mix12']
sys.stdout.reconfigure(encoding='utf-8')
GS = json.load(open(os.path.join(HERE, 'fixtures/gold_sets.json'), encoding='utf-8'))
FX = {s: json.load(open(os.path.join(HERE, f'fixtures/{s}.json'), encoding='utf-8'))['sets'][s] for s in SETS}
KEYS = [(s, i) for s in SETS for i in range(len(FX[s]['qs']))]
GSET = {(s, i): frozenset(GS[s][str(i)]) for s, i in KEYS}
GOLD = {(s, i): FX[s]['qs'][i]['gold'] for s, i in KEYS}
TYPE = {(s, i): FX[s]['qs'][i]['type'] for s, i in KEYS}
COMP = [k for k in KEYS if TYPE[k] == 'compound_intent']
NONC = [k for k in KEYS if TYPE[k] != 'compound_intent']
assert len(KEYS) == 835 and len(COMP) == 66 and len(NONC) == 769, (len(KEYS), len(COMP), len(NONC))


def score_multi(picks):
    """picks: {key: list[int]} → (C 전체, C 비복합, C 복합, A 복합, B 복합)"""
    c_all = c_non = c_comp = a_comp = b_comp = 0
    for k in KEYS:
        p = picks.get(k)
        ps = frozenset(p or [])
        hit = ps == GSET[k]
        c_all += hit
        if k in COMP:
            c_comp += hit
            a_comp += bool(p) and p[0] == GOLD[k]
            b_comp += bool(ps & GSET[k])
        else:
            c_non += hit
    return c_all, c_non, c_comp, a_comp, b_comp


def score_single(pick):
    """한 항목 모델: 집합 = {pick} (없음이면 빈 집합)"""
    return score_multi({k: ([] if pick.get(k) is None else [pick[k]]) for k in KEYS})


def fnum(x):
    return None if x in ('', None) else int(float(x))


rows = list(csv.DictReader(open(os.path.join(HERE, 'results/export/per_question.csv'), encoding='utf-8-sig')))
SINGLE = defaultdict(dict)
for r in rows:
    if r['set'] in SETS:
        SINGLE[r['model']][(r['set'], int(r['q_index']))] = fnum(r['pick'])
E4BT = {}
for s in SETS:
    ev = json.load(open(os.path.join(HERE, f'results/_pull/distill_eval/eval_r16e2_{s}.json'), encoding='utf-8'))
    for i, p in enumerate(ev['r16e2#lora']['picks']):
        E4BT[(s, i)] = p
SINGLE['E4B-가르침'] = E4BT


def find(prefix):
    c = [m for m in SINGLE if m.startswith(prefix)]
    assert len(c) == 1, (prefix, c)
    return c[0]


MULTI = {}
for tag, label in (('claude_opus_5_5', 'Claude Opus 5.5(문제별 CLI·생각 끔, 클라우드)'), ('claude_fable_5_1', 'Claude Fable 5.1(문제별 CLI·생각 끔, 클라우드)')):
    d = {}
    for s in SETS:
        f = os.path.join(HERE, f'results/claude_{tag}_{s}_multi.json')
        if not os.path.exists(f):
            break
        rr = json.load(open(f, encoding='utf-8'))['rows']
        for i in range(len(FX[s]['qs'])):
            d[(s, i)] = rr[str(i)].get('picks') or []
    else:
        MULTI[label] = d
d = {}
for s in SETS:
    f = os.path.join(HERE, f'results/_pull/multi/llm_{s}_multi_out.json')
    if os.path.exists(f):
        pk = json.load(open(f, encoding='utf-8'))['gemma4:12b#multi']['picks']
        for i, p in enumerate(pk):
            d[(s, i)] = p
if len(d) == 835:
    MULTI['Gemma 12B(올라마, 「둘 다 찾기」 지시)'] = d

print('# C 채점까지 넣은 비교 — 835문제(요청 둘 66 포함)\n')
print('채점: A 먼저 말한 항목 · B 말한 항목 중 하나라도 · C 고른 집합이 정답 집합과 정확히 같음. 한 항목 모델은 요청 둘 C = 0(집합 크기가 다름).\n')
print('## 1. 한 항목만 고르는 모델 (C 전체 = 요청 둘 제외 정답 / 835)')
print(f'{"모델":<44}{"C 전체(835)":>14}{"요청 둘 제외(769)":>18}{"요청 둘 A":>10}{"요청 둘 B":>10}{"요청 둘 C":>10}')
singles = [('E4B-가르침', 'E4B-가르침'), ('Gemma 4 E4B QAT', find('Gemma 4 E4B QAT')), ('Decider-12B bf16', find('Decider-12B bf16')), ('Winnow-12B Q8', find('Winnow-12B Q8')),
           ('Gemma 4 26B(올라마)', find('Gemma 4 26B')), ('Qwen3.8 27B(올라마)', find('Qwen3.8 27B')), ('OpenJev 26B', find('OpenJev 26B')), ('decider-chat 31B', find('decider-chat Gemma4-31B'))]
for label, m in singles:
    c_all, c_non, c_comp, a, b = score_single(SINGLE[m])
    print(f'{label:<44}{c_all:>8}/835 {100 * c_all / 835:4.1f}%{c_non:>10}/769{a:>9}/66{b:>8}/66{c_comp:>8}/66')

print('\n## 2. 여러 항목을 낼 수 있는 모델 (집합 출력)')
print(f'{"모델":<44}{"C 전체(835)":>14}{"요청 둘 제외(769)":>18}{"요청 둘 A":>10}{"요청 둘 B":>10}{"요청 둘 C":>10}')
for label, d in MULTI.items():
    c_all, c_non, c_comp, a, b = score_multi(d)
    print(f'{label:<44}{c_all:>8}/835 {100 * c_all / 835:4.1f}%{c_non:>10}/769{a:>9}/66{b:>8}/66{c_comp:>8}/66')

print('\n## 3. 결정 모델 오프라인 「확률 ≥ τ 인 항목 집합」 (기존 c_offline.csv — 개발 mix8+9 에서 τ 를 골라 시험 mix10~12)')
off = list(csv.DictReader(open(os.path.join(HERE, 'results/export/c_offline.csv'), encoding='utf-8-sig')))
by = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0]))
for r in off:
    k = (r['model'], r['tau'])
    comp = r['compound'] == 'True'
    by[k]['all'][0] += int(r['exact'])
    by[k]['all'][1] += 1
    if comp:
        by[k]['comp'][0] += int(r['exact'])
        by[k]['comp'][1] += 1
best = {}
for (m, tau), v in by.items():
    if v['all'][1] == 835 and (m not in best or v['all'][0] > best[m][1]['all'][0]):
        best[m] = (tau, v)
print(f'{"모델(전체 835 에서 C 가 가장 높은 τ — 낙관적)":<56}{"τ":>6}{"C 전체":>14}{"요청 둘 C":>12}')
for m, (tau, v) in sorted(best.items(), key=lambda x: -x[1][1]['all'][0]):
    print(f'{m:<56}{tau:>6}{v["all"][0]:>8}/835 {100 * v["all"][0] / 835:4.1f}%{v["comp"][0]:>8}/{v["comp"][1]}')

print('\n## 4. 요청 둘을 미리 알아보는 규칙(질문에 서로 다른 일정 항목 이름 조각이 둘 이상 들었나) — 있다면 한 항목 모델 + 집합 모델을 이어 붙일 수 있다')


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


def n_items_named(s, i, thr):
    job = FX[s]
    q = ''.join(job['qs'][i]['q'].split())
    hit = 0
    for it in job['items']:
        nm = [''.join(str(it.get(f, '')).split()) for f in ('title', 'place')]
        if any(len(n) >= 2 and lcs(q, n) >= thr for n in nm):
            hit += 1
    return hit


for thr in (3, 4):
    f = {k: n_items_named(k[0], k[1], thr) for k in KEYS}
    for need in (2,):
        tp = sum(1 for k in COMP if f[k] >= need)
        fp = sum(1 for k in NONC if f[k] >= need)
        print(f'  이름 조각(≥{thr}글자)이 항목 {need}개 이상에 걸림: 요청 둘 {tp}/66 을 잡고, 요청 둘이 아닌데 걸린 것 {fp}/769 (정밀도 {tp / max(1, tp + fp):.2f} · 재현율 {tp / 66:.2f})')

print('\n## 5. 이어 붙이기 모의: 요청 둘이라고 알아본 질문만 집합 모델에게, 나머지는 가르친 E4B 에게 (규칙 = 이름 조각 ≥3글자가 항목 2개 이상)')
f3 = {k: n_items_named(k[0], k[1], 3) for k in KEYS}
for label, d in MULTI.items():
    hy = {k: (d[k] if f3[k] >= 2 else ([] if E4BT[k] is None else [E4BT[k]])) for k in KEYS}
    c_all, c_non, c_comp, a, b = score_multi(hy)
    print(f'  가르친 E4B + {label[:30]:<30} C 전체 {c_all}/835 = {100 * c_all / 835:.1f}% · 요청 둘 C {c_comp}/66 · 요청 둘 제외 {c_non}/769')
base = score_single(E4BT)
print(f'  (참고) 가르친 E4B 단독 C 전체 {base[0]}/835 = {100 * base[0] / 835:.1f}%')
# 오라클 규칙: 요청 둘을 완벽히 알아본다고 가정한 상한
for label, d in MULTI.items():
    hy = {k: (d[k] if k in COMP else ([] if E4BT[k] is None else [E4BT[k]])) for k in KEYS}
    c_all, c_non, c_comp, a, b = score_multi(hy)
    print(f'  [상한: 요청 둘을 완벽히 가려낸다고 가정] 가르친 E4B + {label[:30]:<30} C 전체 {c_all}/835 = {100 * c_all / 835:.1f}% · 요청 둘 C {c_comp}/66')
