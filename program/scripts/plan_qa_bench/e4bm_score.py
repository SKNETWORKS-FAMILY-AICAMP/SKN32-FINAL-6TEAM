# 「여러 항목을 내는 학생」(가르친 E4B 를 항목 집합 출력으로 가르친 e4bm)을 같은 835문제(요청 둘 66 포함)에서 채점한다 — 새 호출 없음.
#  채점(§61): A = 먼저 말한 항목 하나가 정답 gold · B = 말한 항목 중 하나라도 맞음 · C = 고른 집합이 정답 집합과 정확히 같음.
#  비교 대상: 같은 레시피로 한 항목만 가르친 E4B(시드 1 = r16e2 · 시드 2 = e4bs2) — 요청 둘 제외 769문제에서 짝지은 McNemar, 요청 둘 66문제는 Gemma 12B(올라마, 「둘 다 찾기」 지시) 53/66 이 기준.
#  ★학습 자료의 요청 둘 비중 · 평가 세트 mix8~11 은 Codex 작성, mix12 는 Claude 작성 — 기록은 마스터 문서 §84.
# 사용: python e4bm_score.py  → results/e4bm_score.md   (결과 파일은 results/_pull/distill_eval/eval_<태그>_<세트>.json — 서버 B /root/work 에서 가져온다)
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
from testsets import fixture  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
sys.path.insert(0, os.path.join(HERE, '..', 'eval_kit'))
from stats import fmt_ratio, mcnemar_exact  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
SETS = ['mix8', 'mix9', 'mix10', 'mix11', 'mix12']
GS = json.load(open(fixture('gold_sets.json'), encoding='utf-8'))
FX = {s: json.load(open(fixture(f'{s}.json'), encoding='utf-8'))['sets'][s] for s in SETS}
KEYS = [(s, i) for s in SETS for i in range(len(FX[s]['qs']))]
GSET = {k: frozenset(GS[k[0]][str(k[1])]) for k in KEYS}
GOLD = {k: FX[k[0]]['qs'][k[1]]['gold'] for k in KEYS}
COMP = [k for k in KEYS if FX[k[0]]['qs'][k[1]]['type'] == 'compound_intent']
NONC = [k for k in KEYS if k not in set(COMP)]
assert len(KEYS) == 835 and len(COMP) == 66 and len(NONC) == 769


def load(tag, key):
    """eval_<태그>_<세트>.json 의 <태그>#lora picks → {(세트, 번호): 집합 리스트}. 항목 하나 모델은 정수/None 이라 리스트로 바꾼다."""
    d = {}
    for s in SETS:
        ev = json.load(open(os.path.join(HERE, f'results/_pull/distill_eval/eval_{tag}_{s}.json'), encoding='utf-8'))
        pk = ev[key]['picks']
        assert len(pk) == len(FX[s]['qs']), (tag, s, len(pk))
        for i, p in enumerate(pk):
            d[(s, i)] = list(p) if isinstance(p, list) else ([] if p is None else [p])
    return d


def hit(d, k):
    return frozenset(d.get(k) or []) == GSET[k]


models = {'가르친 E4B 한 항목(시드 1 · r16e2)': load('r16e2', 'r16e2#lora'), '가르친 E4B 한 항목(시드 2 · e4bs2)': load('e4bs2', 'e4bs2#lora'),
          '가르친 E4B 여러 항목(e4bm, 시드 1)': load('e4bm', 'e4bm#lora')}
out = ['# 가르친 E4B 를 「항목 집합」 출력으로 가르친 e4bm — 835문제(요청 둘 66 포함) · 새 호출 없음\n',
       '- 채점 A 먼저 말한 항목 · B 말한 항목 중 하나라도 · C 집합이 정답과 정확히 같음. 한 항목 모델은 요청 둘에서 C=0(집합 크기가 다르다). 학습 한 번 · 시드 1개라 순위가 아니다.\n',
       '| 모델 | 요청 둘 제외 769 정답(C) | 95% 구간 | 요청 둘 A /66 | 요청 둘 B /66 | 요청 둘 C /66 | 전체 C /835 |', '|---|---:|---|---:|---:|---:|---:|']
for name, d in models.items():
    non = sum(hit(d, k) for k in NONC)
    a = sum(bool(d.get(k)) and d[k][0] == GOLD[k] for k in COMP)
    b = sum(bool(frozenset(d.get(k) or []) & GSET[k]) for k in COMP)
    c = sum(hit(d, k) for k in COMP)
    out.append(f'| {name} | {fmt_ratio(non, 769)} | | {a} | {b} | {c} | {non + c} / 835 = {100 * (non + c) / 835:.1f}% |')
m = models['가르친 E4B 여러 항목(e4bm, 시드 1)']
out.append('')
out.append('**요청 둘 제외 769문제 짝지은 비교**(McNemar 정확검정, 이쪽만 맞음 : 저쪽만 맞음)')
for name in ('가르친 E4B 한 항목(시드 1 · r16e2)', '가르친 E4B 한 항목(시드 2 · e4bs2)'):
    s = models[name]
    r = mcnemar_exact([hit(m, k) for k in NONC], [hit(s, k) for k in NONC])
    out.append(f"- e4bm 대 {name}: {r['a_only']} : {r['b_only']}, p={r['p']:.2g}")
# 요청 둘 외 유형별
out.append('')
by = {}
for k in NONC:
    t = FX[k[0]]['qs'][k[1]]['type']
    by.setdefault(t, [0, 0, 0])
    by[t][0] += 1
    by[t][1] += hit(m, k)
    by[t][2] += hit(models['가르친 E4B 한 항목(시드 1 · r16e2)'], k)
out.append('**유형별(요청 둘 제외)** — 문제 수 · e4bm 정답 · 한 항목 시드 1 정답')
for t, (n, a, b) in sorted(by.items(), key=lambda x: -x[1][0]):
    out.append(f'- {t}: {n} · {a} · {b}')
# 엉뚱한 집합(집합 크기 문제)
over = sum(len(m.get(k) or []) > 1 for k in NONC)
under = sum(len(m.get(k) or []) == 0 and len(GSET[k]) > 0 for k in NONC)
out.append(f'\n- 요청 둘이 아닌데 항목을 둘 이상 낸 것 {over}/769 · 정답이 있는데 비워 낸 것 {under}')
out.append('- 기준: Gemma 12B(올라마, 「둘 다 찾기」 지시) 요청 둘 C 53/66 · Claude Opus 5.5 60/66(문제별 CLI, 클라우드 — 학습 없음, 공정 비교 아님 §84)')
text = '\n'.join(out)
open(os.path.join(HERE, 'results', 'e4bm_score.md'), 'w', encoding='utf-8').write(text)
print(text)
