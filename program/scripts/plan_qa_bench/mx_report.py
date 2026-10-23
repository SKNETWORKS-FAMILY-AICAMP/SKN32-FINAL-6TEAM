# MX 시험(잡담 속에 일정 질문 · 변경 요청이 섞인 입력) 결과표 — 모델마다 「섞인 문장」과 「요청만 있는 대조 짝」을 같은 문항으로 짝지어 비교한다. 새 호출 없음.
#  지표: 정답이 항목인 유형(MX1 일정 질문 · MX2 변경 요청 · MX6a 두 항목 언급, 요청은 하나)은 항목 선택률, 정답이 없음인 유형(MX3 일정 밖 · MX4 일정 낱말 잡담 · MX5a 추가/전체 변경 · MX5b 감정)은 오지목률.
#        섞임 손실 = 대조 − 혼합(선택률) / 혼합 − 대조(오지목). 짝지은 McNemar(정확검정). 신뢰구간은 일정 단위 군집 부트스트랩(2,000회).
#  성공 기준(시험 전에 고정 — Codex 솔 6.1 제안을 채택, 설계 문서 program/research/시험세트_MX_설계_2026-10-07.md): 항목 선택률 ≥ 95% · 정답 없음 유형 오지목 ≤ 1%(MX3 · MX4 · MX5a 는 각각 ≤ 3%) · 섞임에 따른 선택률 손실 ≤ 2%p · 오지목 증가 ≤ 1%p.
# 사용: python mx_report.py <표시이름=태그> …   (결과 파일 results/d_test/d_test_lp_mx_q4km_<태그>.jsonl)  → results/mx_report.md
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'eval_kit'))
from stats import mcnemar_exact  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
MXDIR = next(p for p in (os.path.join(ROOT, 'datasets', 'core', 'pointing', 'testset', 'requests_inside_chitchat_pairs_v1'), os.path.join(ROOT, 'program', 'datasets', 'core', 'pointing', 'testset', 'requests_inside_chitchat_pairs_v1')) if os.path.exists(os.path.join(p, 'mx_main_prompts.json')))
D = os.path.join(HERE, 'results', 'd_test')
ITEMS = json.load(open(os.path.join(MXDIR, 'mx_main_prompts.json'), encoding='utf-8'))
POS = ['MX1', 'MX2', 'MX6a']
NUL = ['MX3', 'MX4', 'MX5a', 'MX5b']
NAME = {'MX1': 'MX1 잡담+일정 질문', 'MX2': 'MX2 잡담+변경 요청', 'MX6a': 'MX6a 잡담+두 항목 언급(요청은 하나)', 'MX3': 'MX3 잡담+일정 밖 질문', 'MX4': 'MX4 일정 낱말 잡담(요청 없음)', 'MX5a': 'MX5a 잡담+추가·전체 변경', 'MX5b': 'MX5b 잡담+일정 전체 감정'}
args = dict(a.split('=', 1) for a in sys.argv[1:]) or {'시드 1': 'e4bt', '시드 2': 'e4bs2', '시드 3': 'e4bs3', 'oos1': 'oos1'}


def load(tag):
    p = os.path.join(D, f'd_test_lp_mx_q4km_{tag}.jsonl')
    if not os.path.exists(p):
        return None
    return {json.loads(l)['i']: json.loads(l) for l in open(p, encoding='utf-8')}


SRC = os.environ.get('SRC', '')   # SRC=code 또는 llm 이면 그 생성 방식만(기본: 합쳐서)
by_pair = {}
for x in [i for i in ITEMS if not SRC or i['src'] == SRC]:
    by_pair.setdefault(x['pair'], {})[x['kind']] = x


def hit(R, x):
    r = R.get(x['i'])
    if not r or not r.get('parsed'):
        return None
    return r['pick'] == x['gold'] if x['gold'] is not None else r['pick'] is not None   # 항목 유형: 정답 선택 / 없음 유형: 오지목(True = 틀림)


def boot(pairs, fn, n=2000, seed=7):
    rnd = random.Random(seed)
    cl = {}
    for p in pairs:
        cl.setdefault(p[0]['itin'], []).append(p)
    ks = list(cl)
    vals = []
    for _ in range(n):
        s = [q for k in (rnd.choice(ks) for _ in ks) for q in cl[k]]
        vals.append(fn(s))
    vals.sort()
    return vals[int(0.025 * n)], vals[int(0.975 * n) - 1]


out = ['# MX 시험 — 잡담에 일정 질문 · 변경 요청이 섞인 입력 (서비스 기반 Q4_K_M, 생각 끔, 엄격 계수)\n',
       '모든 섞인 문장에는 「요청만 있는 대조 짝」이 있다. 표의 「혼합」 = 잡담이 섞인 문장, 「대조」 = 같은 요청만. 항목 유형은 항목 선택률(높을수록 좋음), 정답 없음 유형은 오지목률(낮을수록 좋음). 구간은 일정 단위 군집 부트스트랩 95%.\n']
summary = []
for name, tag in args.items():
    R = load(tag)
    if R is None:
        continue
    out.append(f'\n## {name}\n')
    out.append('| 유형 | 쌍 수 | 대조 | 혼합 | 섞임 손실(대조−혼합) · 구간 | 대조 맞고 혼합 틀림 : 반대 · p |')
    out.append('|---|---:|---:|---:|---|---|')
    tot = {'pos': [], 'nul': []}
    for src in ('code', 'llm', 'all'):
        pass
    for cat in POS + NUL:
        pairs = [(v['mixed'], v['control']) for v in by_pair.values() if 'mixed' in v and 'control' in v and v['mixed']['cat'] == cat]
        pairs = [(m, c) for m, c in pairs if hit(R, m) is not None and hit(R, c) is not None]
        if not pairs:
            continue
        isnul = cat in NUL
        cm = [hit(R, c) for _, c in pairs]
        mm = [hit(R, m) for m, _ in pairs]
        n = len(pairs)
        rc, rm = sum(cm) / n, sum(mm) / n
        loss = (rm - rc) if isnul else (rc - rm)
        fn = (lambda s: (sum(hit(R, m) for m, _ in s) - sum(hit(R, c) for _, c in s)) / len(s)) if isnul else (lambda s: (sum(hit(R, c) for _, c in s) - sum(hit(R, m) for m, _ in s)) / len(s))
        lo, hi = boot(pairs, fn)
        # 짝지은 McNemar: 「좋음」 기준으로 맞춘다(항목 유형: 맞음 / 없음 유형: 오지목 아님)
        good_c = [(not x) if isnul else x for x in cm]
        good_m = [(not x) if isnul else x for x in mm]
        mn = mcnemar_exact(good_c, good_m)
        out.append(f"| {NAME[cat]} | {n} | {sum(cm)}/{n} = {100 * rc:.2f}% | {sum(mm)}/{n} = {100 * rm:.2f}% | {100 * loss:+.2f}%p ({100 * lo:+.1f} ~ {100 * hi:+.1f}) | {mn['a_only']} : {mn['b_only']}, p={mn['p']:.3g} |")
        tot['nul' if isnul else 'pos'].append((pairs, cm, mm))
    # 합산
    def pool(key):
        P = [p for g in tot[key] for p in g[0]]
        c = sum(sum(g[1]) for g in tot[key])
        m = sum(sum(g[2]) for g in tot[key])
        return P, c, m
    Pp, cp, mp = pool('pos')
    Pn, cn, mn_ = pool('nul')
    if Pp:
        out.append(f'| **항목 유형 합산** | {len(Pp)} | {cp}/{len(Pp)} = {100 * cp / len(Pp):.2f}% | {mp}/{len(Pp)} = {100 * mp / len(Pp):.2f}% | {100 * (cp - mp) / len(Pp):+.2f}%p | |')
    if Pn:
        out.append(f'| **정답 없음 유형 합산(오지목)** | {len(Pn)} | {cn}/{len(Pn)} = {100 * cn / len(Pn):.2f}% | {mn_}/{len(Pn)} = {100 * mn_ / len(Pn):.2f}% | {100 * (mn_ - cn) / len(Pn):+.2f}%p | |')
    summary.append((name, len(Pp), (mp / len(Pp) if Pp else None), (cp - mp) / len(Pp) if Pp else None, len(Pn), (mn_ / len(Pn) if Pn else None), (mn_ - cn) / len(Pn) if Pn else None, mp, mn_))
out.append('\n## 한눈에(성공 기준: 항목 선택률 ≥95% · 오지목 ≤1% · 선택률 손실 ≤2%p · 오지목 증가 ≤1%p — 시험 전에 고정한 값)\n')
out.append('| 모델 | 항목 선택률(혼합) | 선택률 손실 | 오지목(혼합) | 오지목 증가 | 기준 통과 |')
out.append('|---|---:|---:|---:|---:|---|')
for name, npos, sel, loss, nnul, fp, inc, selected_count, false_count in summary:
    ok = [sel is not None and sel >= 0.95, fp is not None and fp <= 0.01, loss is not None and loss <= 0.02, inc is not None and inc <= 0.01]
    out.append(f"| {name} | {selected_count}/{npos} = {100 * sel:.2f}% | {100 * loss:+.2f}%p | {false_count}/{nnul} = {100 * fp:.2f}% | {100 * inc:+.2f}%p | {sum(ok)}/4 ({'선택률' if ok[0] else '✗선택률'} · {'오지목' if ok[1] else '✗오지목'} · {'손실' if ok[2] else '✗손실'} · {'증가' if ok[3] else '✗증가'}) |")
out.append('\n- 한계: 점추정이 기준을 넘는 것과 구간이 기준을 넘는 것은 다르다(표의 구간 참조). 코드로 이어 붙인 혼합(src=code)은 연결어 · 위치가 지름길이 될 수 있어 LLM 이 쓴 소량판(src=llm)과 나눠 봐야 한다 — 이 표는 SRC 환경변수가 없으면 합쳐 낸 값이고, `SRC=code` · `SRC=llm` 으로 나눠 따로 낸다(파일 이름에 붙음). 일정 59개 · 모델당 1회.')
text = '\n'.join(out)
open(os.path.join(HERE, 'results', f'mx_report{("_" + SRC) if SRC else ""}.md'), 'w', encoding='utf-8').write(text)
print(text)
