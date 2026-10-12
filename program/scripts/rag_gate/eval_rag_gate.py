# 규정 질문 경로의 「검색 결과 거르기」 채점 — 운영 방식(코사인 점수 문턱)과, Self-RAG 의 [Retrieve]·[IsRel] 에 해당하는 일을 작은 모델이 추론 때 하는 방식을 같은 질문 180개로 비교한다.
#  운영 방식(P0): 임베딩 상위 3개 절 중 점수 ≥ τ 인 것의 고객용 문장 상위 2개를 보인다(없으면 「못 찾음」). 운영 문턱 τ = 0.55.
#  거르기(J): 임베딩 상위 5개 「고객용 문장이 있는 절」 중 코사인 ≥ floor 인 것을 모델이 「질문에 답이 되는가」로 판정, p_true ≥ τj 인 것 상위 2개를 보인다. gate = 「규정 질문인가」 판정이 τg 이상일 때만.
#  결과 점수: 답 있음 — 정답 줄을 보이면 +1 · 답 안 함 0 · 틀린 줄만 보이면 −2 / 답 없음(코퍼스에 없음·주제 밖) — 답 안 함 0 · 뭐든 보이면 −2. 비슷하지만 다름(near_miss)은 모호해 따로 센다.
#  문턱·floor 는 짝수 번째 질문(개발용)으로만 고르고 홀수 번째(시험용)로 판정한다. 고르는 기준 = 개발용 합계 점수.
# 사용: python eval_rag_gate.py [모델 이름 ...]   (rag_judge_<모델>.json 이 results/ 에 있어야 한다)
import itertools, json, math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
J = lambda *a: json.load(open(os.path.join(HERE, *a), encoding='utf-8'))
Q = J('fixtures', 'rag_questions.json')['questions']
CH = J('fixtures', 'policy_chunks.json')
VAR = os.environ.get('VARIANT')          # 예: VARIANT=E_문서제목+절제목+고객용문장 — 임베딩 대상을 바꾼 점수표(rag_embed_variants.json)로 후보를 뽑는다
if VAR:
    _v = J('results', 'rag_embed_variants.json')
    SIM = {'sources': _v['sources'], 'sims': _v['variants'][VAR]}
else:
    SIM = J('results', 'rag_sims.json')
SRC = SIM['sources']
IDX = {s: i for i, s in enumerate(SRC)}
LINE = {c['source']: c['line'] for c in CH if c['line']}
N = len(Q)
DEV = [i for i in range(N) if i % 2 == 0]
TEST = [i for i in range(N) if i % 2 == 1]
models = sys.argv[1:] or ['gemma4_e4b-it-qat', 'gemma4_12b', 'gemma4_26b-a4b-it-q4_K_M']
SUF = ('__' + VAR[:1]) if VAR else ''
JD = {m: J('results', f'rag_judge_{m}{SUF}.json') for m in models if os.path.exists(os.path.join(HERE, 'results', f'rag_judge_{m}{SUF}.json'))}


def cosv(qi, s):
    return SIM['sims'][qi][IDX[s]]


def p0(qi, tau, topk=3, top=2):
    order = sorted(range(len(SRC)), key=lambda i: -SIM['sims'][qi][i])[:topk]
    return [SRC[i] for i in order if SIM['sims'][qi][i] >= tau and SRC[i] in LINE][:top]


def pj(qi, m, tau_j, floor, tau_g=None, top=2):
    d = JD[m]
    if tau_g is not None:
        g = d['gate'].get(str(qi))
        if g is None or g[1] is None or g[1] < tau_g:
            return []
    out = []
    for s, v, p in d['judge'][str(qi)]:
        if cosv(qi, s) < floor:
            continue
        if (p is not None and p >= tau_j) or (p is None and v):
            out.append(s)
    return out[:top]


def outcome(qi, shown):
    q = Q[qi]
    if q['type'] == 'answerable':
        if not shown:
            return 'miss', 0
        return ('correct', 1) if set(shown) & set(q['gold']) else ('wrong', -2)
    return ('abstain', 0) if not shown else ('false', -2)


def tally(idx, fn):
    c = {'correct': 0, 'miss': 0, 'wrong': 0, 'abstain': 0, 'false': 0, 'near_false': 0, 'near_n': 0, 'score': 0, 'n_ans': 0, 'n_none': 0}
    for qi in idx:
        shown = fn(qi)
        o, sc = outcome(qi, shown)
        if Q[qi]['type'] == 'near_miss':
            c['near_n'] += 1
            c['near_false'] += o == 'false'
            continue
        c[o] += 1
        c['score'] += sc
        c['n_ans' if Q[qi]['type'] == 'answerable' else 'n_none'] += 1
    return c


def row(name, c):
    return (f"| {name} | {c['correct']}/{c['n_ans']} | {c['miss']} | {c['wrong']} | {c['false']}/{c['n_none']} | {c['near_false']}/{c['near_n']} | **{c['score']}** |")


def best(cands, fnmaker):
    return max(cands, key=lambda cfg: (tally(DEV, fnmaker(cfg))['score'], -len(str(cfg))))


out = []
# 검색 상한(재현율): 정답 줄이 상위 k 에 드는 비율
ans = [i for i in range(N) if Q[i]['type'] == 'answerable']
rec = {}
for k in (1, 3, 5):
    hit = 0
    for qi in ans:
        order = [SRC[i] for i in sorted(range(len(SRC)), key=lambda i: -SIM['sims'][qi][i]) if SRC[i] in LINE][:k]
        hit += bool(set(order) & set(Q[qi]['gold']))
    rec[k] = hit
out.append(f"## 규정 질문 거르기 — {N}문제(답 있음 {len(ans)} · 코퍼스에 없음 {sum(q['type'] == 'uncovered' for q in Q)} · 비슷하지만 다름 {sum(q['type'] == 'near_miss' for q in Q)} · 주제 밖 {sum(q['type'] == 'offtopic' for q in Q)})")
out.append(f"검색 상한(정답 줄이 임베딩 상위 k 「고객용 문장이 있는 절」 안): @1 {rec[1]}/{len(ans)} · @3 {rec[3]}/{len(ans)} · @5 {rec[5]}/{len(ans)}\n")
hdr = ['| 방식 | 답 있음: 정답 줄 보임 | 못 찾음 | 틀린 줄만 보임 | 답 없음: 틀리게 답함 | 비슷하지만 다름: 답함 | 점수 |', '|---|---:|---:|---:|---:|---:|---:|']
for label, idx in (('시험용(홀수 번째 90)', TEST), ('전체 180', list(range(N)))):
    out.append(f'### {label}')
    out += hdr
    out.append(row('운영(τ=0.55)', tally(idx, lambda qi: p0(qi, 0.55))))
    tb = best([round(0.30 + 0.025 * k, 3) for k in range(19)], lambda t: (lambda qi: p0(qi, t)))
    out.append(row(f'P0 점수 문턱 τ={tb}(개발용 최적)', tally(idx, lambda qi: p0(qi, tb))))
    for m in JD:
        cfgs = [(tj, fl, tg) for tj in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95) for fl in (0.0, 0.3, 0.4, 0.5) for tg in (None, 0.3, 0.5, 0.7)]
        cfg = best(cfgs, lambda c: (lambda qi: pj(qi, m, c[0], c[1], c[2])))
        out.append(row(f'거르기 {m} (τj={cfg[0]}, floor={cfg[1]}, 문지기={cfg[2]})', tally(idx, lambda qi: pj(qi, m, cfg[0], cfg[1], cfg[2]))))
        cfg2 = best([(tj, fl, None) for tj in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95) for fl in (0.0, 0.3, 0.4, 0.5)], lambda c: (lambda qi: pj(qi, m, c[0], c[1], None)))
        out.append(row(f'  └ 문지기 없이 {m} (τj={cfg2[0]}, floor={cfg2[1]})', tally(idx, lambda qi: pj(qi, m, cfg2[0], cfg2[1], None))))
    out.append('')
# 짝지은 점수 차이(시험용) — 운영 대비
for m in JD:
    cfgs = [(tj, fl, tg) for tj in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95) for fl in (0.0, 0.3, 0.4, 0.5) for tg in (None, 0.3, 0.5, 0.7)]
    cfg = best(cfgs, lambda c: (lambda qi: pj(qi, m, c[0], c[1], c[2])))
    d = [outcome(qi, pj(qi, m, *cfg[:2], cfg[2]))[1] - outcome(qi, p0(qi, 0.55))[1] for qi in TEST if Q[qi]['type'] != 'near_miss']
    r = random.Random(20261001)
    bs = sorted(sum(r.choice(d) for _ in d) / len(d) for _ in range(2000))
    out.append(f"시험용 점수 차이(거르기 {m} − 운영 0.55), 문제당 평균 {sum(d) / len(d):+.3f} [{bs[49]:+.3f}, {bs[1949]:+.3f}] (개발용 선택 {cfg})")
# 문지기 단독(Self-RAG [Retrieve] 에 해당): 답 없음·주제 밖을 거르는 힘
for m in JD:
    g = JD[m]['gate']
    for t in (0.3, 0.5, 0.7):
        tp = sum(1 for i in range(N) if Q[i]['type'] in ('answerable',) and g[str(i)][1] is not None and g[str(i)][1] >= t)
        off = sum(1 for i in range(N) if Q[i]['type'] == 'offtopic' and g[str(i)][1] is not None and g[str(i)][1] >= t)
        unc = sum(1 for i in range(N) if Q[i]['type'] == 'uncovered' and g[str(i)][1] is not None and g[str(i)][1] >= t)
        out.append(f"문지기 {m} τg={t}: 규정 질문으로 통과 — 답 있음 {tp}/{len(ans)} · 주제 밖 {off}/20 · 코퍼스에 없음 {unc}/40")
print('\n'.join(out))
if '--md' in sys.argv:
    open(sys.argv[sys.argv.index('--md') + 1], 'w', encoding='utf-8').write('\n'.join(out) + '\n')
