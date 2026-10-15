# 가르친 E4B(시드 1)를 GGUF Q8_0 에서 Q4_K_M 으로 다시 양자화(llama-quantize --allow-requantize)했을 때 정확도가 얼마나 떨어지나 — 서버 B CPU 4코어, 같은 평가 틀(cpu_eval_gguf.py)·같은 문제.
#  채점은 cpu_eval_summary.py 와 같다: 읽기 실패(빈 응답)는 엄격히 틀린 것으로 센다(null 정답과 우연히 맞는 것을 막는다). 요청 둘 제외 769문제에서 짝지은 McNemar 정확검정과 짝지은 부트스트랩 차이 구간.
#  ★이 평가는 x86 CPU 에서 했다. 오라클 무료 서버(ARM)는 합성 프롬프트로 속도만 쟀다 — 양자화 손실은 계산 방식이 달라도 거의 같지만(작은 수치 차이는 있을 수 있다) ARM 에서 직접 확인하지는 않았다.
# 사용: python cpu_q4_vs_q8.py   → results/cpu_q4_vs_q8.md   (입력 results/_pull/cpu/cpu_eval_e4bt_q8nt_<세트>.json · cpu_eval_e4bt_q4nt_<세트>.json — 둘 다 생각 모드를 끈 판. 처음 판 cpu_eval_e4bt_q8_*(생각 켬, 빈 답 12)는 기록으로만 남긴다)
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
from testsets import fixture  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
sys.path.insert(0, os.path.join(HERE, '..', 'eval_kit'))
from stats import fmt_ratio, mcnemar_exact, paired_bootstrap_diff  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
SETS = ['mix8', 'mix9', 'mix10', 'mix11', 'mix12']
FX = {s: json.load(open(fixture(f'{s}.json'), encoding='utf-8'))['sets'][s] for s in SETS}


def load(tag):
    good, warm, cold, errs = {}, [], [], 0
    for s in SETS:
        d = json.load(open(os.path.join(HERE, f'results/_pull/cpu/cpu_eval_{tag}_{s}.json'), encoding='utf-8'))
        qs = FX[s]['qs']
        for i, q in enumerate(qs):
            if q['type'] == 'compound_intent':
                continue
            good[(s, i)] = '"item"' in d['rows'][i]['raw'] and d['picks'][i] == q['gold']
        warm += [r['wall_s'] for r in d['rows'][1:]]
        cold.append(d['rows'][0]['wall_s'])
        errs += d['_errors']
    return good, warm, cold, errs


g8, w8, c8, e8 = load('e4bt_q8nt')
g4, w4, c4, e4 = load('e4bt_q4nt')
keys = sorted(g8)
assert len(keys) == 769 and set(keys) == set(g4), (len(keys), len(g4))
a8, a4 = [g8[k] for k in keys], [g4[k] for k in keys]
m = mcnemar_exact(a4, a8)
d = paired_bootstrap_diff([1.0 if x else 0.0 for x in a4], [1.0 if x else 0.0 for x in a8])


def med(v):
    v = sorted(v)
    return v[len(v) // 2]


out = ['# 가르친 E4B(시드 1) — GGUF Q8_0 대 Q4_K_M(Q8 에서 다시 양자화) 정확도 · 서버 B CPU 4코어, 요청 둘 제외 769문제, 엄격 계수\n',
       '| | 정답 (Wilson 95%) | 읽기 실패 | 첫 질문 평균(초) | 같은 일정 다음 질문 중앙값(초) |', '|---|---|---:|---:|---:|',
       f'| Q8_0 (7.5GB) | {fmt_ratio(sum(a8), 769)} | {e8} | {sum(c8) / len(c8):.1f} | {med(w8):.2f} |',
       f'| Q4_K_M (Q8 에서 다시 양자화) | {fmt_ratio(sum(a4), 769)} | {e4} | {sum(c4) / len(c4):.1f} | {med(w4):.2f} |', '',
       f"- 짝지은 비교: Q4 만 맞음 {m['a_only']} : Q8 만 맞음 {m['b_only']}, McNemar 정확검정 p={m['p']:.2g} · 정확도 차이(Q4−Q8) {d['diff']:+.4f} (95% 구간 {d['lo']:+.4f}~{d['hi']:+.4f})",
       '- 한계: ① 가르친 E4B 시드 1 하나, 한 번의 결정적 실행(온도 0) ② 다시 양자화(Q8→Q4)라 원본(F16)에서 만든 Q4 와 값이 다를 수 있다 ③ 시간은 x86 EPYC 코어 4개(다른 작업이 같은 기계에서 돌던 중)라 오라클 ARM 의 시간과 다르다 — 시간 비교는 오라클 서버 값(처리량 비교 문서)을 쓴다 ④ 합성 문제, 학습 자료와 같은 분포라 낙관적이다.']
text = '\n'.join(out)
open(os.path.join(HERE, 'results', 'cpu_q4_vs_q8.md'), 'w', encoding='utf-8').write(text)
print(text)
