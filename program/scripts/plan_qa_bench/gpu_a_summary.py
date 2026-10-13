# 서버 A(RTX 2000 Ada, 16GB)에서 llama.cpp(GPU 전부 올림, 생각 끔, 한 번에 한 질문)로 푼 「가르친 E4B(어댑터) 대 가르치기 전(같은 기반)」 결과를 요약한다. 새 호출 없음.
#  입력: results/_pull/cpu/cpu_eval_a_gpu_taught_<세트>.json · cpu_eval_a_gpu_base_<세트>.json (서버 A /workspace/heavy 에서 가져온다). 기반 = 올라마가 받아 둔 gemma4:e4b-it-qat GGUF(Q4_0) — x600 의 gemma4:e4b(Q4_K_M)와 기반 양자화가 다르다.
#  채점은 cpu_eval_summary.py 와 같다(읽기 실패 = 엄격히 오답, 요청 둘 제외 769). 시간: 첫 질문(일정 전체 읽기) · 같은 일정 다음 질문(앞부분 캐시) 평균·중앙·95백분위, 하루 처리량 상한(첫 질문 비율별).
# 사용: python gpu_a_summary.py  → results/gpu_a_summary.md
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'eval_kit'))
from stats import fmt_ratio, mcnemar_exact, paired_bootstrap_diff, percentile  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
SETS = ['mix8', 'mix9', 'mix10', 'mix11', 'mix12']
FX = {s: json.load(open(os.path.join(HERE, f'fixtures/{s}.json'), encoding='utf-8'))['sets'][s] for s in SETS}


def load(tag):
    good, warm, cold, errs, picks = {}, [], [], 0, {}
    for s in SETS:
        d = json.load(open(os.path.join(HERE, f'results/_pull/cpu/cpu_eval_{tag}_{s}.json'), encoding='utf-8'))
        for i, q in enumerate(FX[s]['qs']):
            if q['type'] == 'compound_intent':
                continue
            good[(s, i)] = '"item"' in d['rows'][i]['raw'] and d['picks'][i] == q['gold']
        warm += [r['wall_s'] for r in d['rows'][1:]]
        cold.append(d['rows'][0]['wall_s'])
        errs += d['_errors']
    return good, warm, cold, errs


gt, wt, ct, et = load('a_gpu_taught')
gb, wb, cb, eb = load('a_gpu_base')
keys = sorted(gt)
assert len(keys) == 769 and set(keys) == set(gb)
at, ab = [gt[k] for k in keys], [gb[k] for k in keys]
m = mcnemar_exact(at, ab)
d = paired_bootstrap_diff([1.0 if x else 0.0 for x in at], [1.0 if x else 0.0 for x in ab])


def stat(v):
    return f'평균 {sum(v) / len(v):.2f} · 중앙 {sorted(v)[len(v) // 2]:.2f} · 95백분위 {percentile(v, 95):.2f}'


out = ['# 서버 A(RTX 2000 Ada 16GB) — llama.cpp GPU 실행, 가르친 E4B(어댑터) 대 가르치기 전(같은 기반 gemma4:e4b-it-qat Q4_0), 생각 끔, 요청 둘 제외 769문제, 엄격 계수\n',
       '| | 정답 (Wilson 95%) | 읽기 실패 | 첫 질문(일정 전체 읽기, 초) | 같은 일정 다음 질문(초) |', '|---|---|---:|---|---|',
       f'| 가르친 E4B(어댑터 + QAT 기반) | {fmt_ratio(sum(at), 769)} | {et} | 평균 {sum(ct) / len(ct):.2f} ({", ".join(f"{c:.2f}" for c in ct)}) | {stat(wt)} |',
       f'| 가르치기 전(같은 기반) | {fmt_ratio(sum(ab), 769)} | {eb} | 평균 {sum(cb) / len(cb):.2f} | {stat(wb)} |', '',
       f"- 짝지은 비교: 가르친 쪽만 맞음 {m['a_only']} : 기반만 맞음 {m['b_only']}, McNemar p={m['p']:.2g} · 정확도 차이 {d['diff']:+.4f} (95% 구간 {d['lo']:+.4f}~{d['hi']:+.4f})", '',
       '**하루 처리량 상한**(한 대 · 한 번에 한 질문 · 24시간 100% 가동 가정, 가르친 모델의 중앙값 기준 — 첫 질문 비율 s 에 따라 평균 서비스 시간 = s × 첫 질문 + (1−s) × 다음 질문)']
c0, w0 = sum(ct) / len(ct), sorted(wt)[len(wt) // 2]
for s in (0.0, 0.1, 0.3, 1.0):
    T = s * c0 + (1 - s) * w0
    out.append(f'- s={int(100 * s)}%: 질문당 {T:.2f}초 → 시간당 {3600 / T:,.0f}건 · 하루 약 {86400 / T:,.0f}건')
out.append('- 한계: ① 가르친 E4B 시드 1 · 한 번의 결정적 실행 ② 기반이 x600 의 gemma4:e4b(Q4_K_M)와 달라 같은 값이 아닐 수 있다(어댑터는 같다) ③ 첫 질문 표본은 세트당 1개(5개)라 구간이 넓다 ④ 한 슬롯 순차 실행 — 동시 요청 처리량은 따로 재지 않았다(올라마 병렬 4 값은 처리량 비교 문서) ⑤ 합성 문제, 학습 자료와 같은 분포라 낙관적이다.')
text = '\n'.join(out)
open(os.path.join(HERE, 'results', 'gpu_a_summary.md'), 'w', encoding='utf-8').write(text)
print(text)
