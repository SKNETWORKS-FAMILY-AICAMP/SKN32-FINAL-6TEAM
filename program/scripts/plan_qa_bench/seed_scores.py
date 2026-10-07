# 가르친 E4B(같은 레시피 · 시드만 다름)의 시드별 769문제(요청 둘 제외) 정답과 시드 사이 짝지은 비교 — 저장된 평가 파일(eval_<태그>_<세트>.json, 서버 B)에서 계산. 새 호출 없음.
#  한 항목 학생의 picks 는 정수 또는 null. 엄격 계수: 정답 집합과 다르면 오답(읽기 실패는 서버에서 null 로 기록돼 gold 가 null 인 문제만 맞는다 — 평가 파일의 _errors 도 같이 적는다).
#  태그: r16e2(시드 1, 레시피 처음 판) · e4bs2 · e4bs3 · e4bs4 · … — 파일이 있는 것만 센다.
# 사용: python seed_scores.py  → results/seed_scores.md
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'eval_kit'))
from stats import fmt_ratio, mcnemar_exact  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
SETS = ['mix8', 'mix9', 'mix10', 'mix11', 'mix12']
FX = {s: json.load(open(os.path.join(HERE, f'fixtures/{s}.json'), encoding='utf-8'))['sets'][s] for s in SETS}
GS = json.load(open(os.path.join(HERE, 'fixtures/gold_sets.json'), encoding='utf-8'))
KEYS = [(s, i) for s in SETS for i, q in enumerate(FX[s]['qs']) if q['type'] != 'compound_intent']
assert len(KEYS) == 769
D = os.path.join(HERE, 'results/_pull/distill_eval')
TAGS = [('r16e2', 'r16e2#lora', '시드 1(처음 판)'), ('e4bs2', 'e4bs2#lora', '시드 2'), ('e4bs3', 'e4bs3#lora', '시드 3'), ('e4bs4', 'e4bs4#lora', '시드 4'),
        ('e4bs5', 'e4bs5#lora', '시드 5'), ('e4bs6', 'e4bs6#lora', '시드 6'),
        ('oos1', 'oos1#lora', 'oos1(잡담 부정 사례 추가, 시드 20261012)'), ('oos2', 'oos2#lora', 'oos2(〃 시드 20261013)'), ('oos3', 'oos3#lora', 'oos3(〃 시드 20261014)')]
runs = {}
for tag, key, label in TAGS:
    good, errs = {}, 0
    for s in SETS:
        f = os.path.join(D, f'eval_{tag}_{s}.json')
        if not os.path.exists(f):
            break
        ev = json.load(open(f, encoding='utf-8'))[key]
        errs += ev.get('_errors', 0)
        for i, q in enumerate(FX[s]['qs']):
            if q['type'] == 'compound_intent':
                continue
            p = ev['picks'][i]
            good[(s, i)] = (p if not isinstance(p, list) else (p[0] if p else None)) == q['gold']
    else:
        runs[label] = (good, errs)
out = ['# 가르친 E4B 시드별 769문제(요청 둘 제외, 엄격 계수) — 같은 레시피(QLoRA r16 · 2 에폭 · lr 2e-4, 한 항목 학습 자료), 시드만 다름\n', '| 시드 | 정답 (Wilson 95%) | 호출 오류 |', '|---|---|---:|']
vals, ovals = [], []
for label, (good, errs) in runs.items():
    n = sum(good[k] for k in KEYS)
    (ovals if label.startswith('oos') else vals).append(n)
    out.append(f'| {label} | {fmt_ratio(n, 769)} | {errs} |')
if ovals:
    out.append('')
    out.append(f'- 잡담 부정 사례를 더해 다시 가르친 모델(oos) {len(ovals)}개: ' + ' · '.join(f'{v}/769 = {100 * v / 769:.1f}%' for v in ovals) + ' — 학습 자료가 다르므로 아래 시드 범위와 섞어 평균을 내지 않는다')
if len(vals) >= 3:
    out.append(f'\n- **같은 레시피 시드 {len(vals)}개: 평균 {sum(vals) / len(vals):.1f}/769 = {100 * sum(vals) / len(vals) / 769:.2f}% · 범위 {min(vals)}~{max(vals)} ({100 * min(vals) / 769:.1f}~{100 * max(vals) / 769:.1f}%)** — 시드 하나의 값으로 모델 순위를 말하지 않는 근거')
labels = list(runs)
out.append('\n**시드 사이 짝지은 비교**(McNemar 정확검정, 이쪽만 맞음 : 저쪽만 맞음)')
for a in range(len(labels)):
    for b in range(a + 1, len(labels)):
        m = mcnemar_exact([runs[labels[a]][0][k] for k in KEYS], [runs[labels[b]][0][k] for k in KEYS])
        out.append(f"- {labels[a]} 대 {labels[b]}: {m['a_only']} : {m['b_only']}, p={m['p']:.2g}")
out.append('\n- 한계: 학습 자료 · 레시피는 같고 시드(학습 순서 · LoRA 초기화)만 다르다. HF 4비트 + 어댑터 값이고 서비스 실행기(llama.cpp · 올라마)와 같지 않다. 합성 문제, 학습 자료와 같은 분포라 낙관적이다.')
text = '\n'.join(out)
open(os.path.join(HERE, 'results', 'seed_scores.md'), 'w', encoding='utf-8').write(text)
print(text)
