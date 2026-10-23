# 실제 채팅 잡담(AI Hub 일상 대화 표본)에 일정 항목을 잘못 답하는 비율 — 정답은 항상 「없음」인 질문으로 읽는다. 앞단 점수는 mix7 일정(42항목)에 대한 값.
#  직접 = 앞단 없이 LLM 이 바로 푼 결과 · 소형 조합 = 앞단 점수 ≥ hi(0.6) 면 확정, lo ≤ 점수 < hi 면 LLM 에 넘겨 답한 것만 · 점수 < lo 는 「없음」. 비율의 95% 구간은 Wilson.
# 사용: python eval_chat_fp.py [앞단 점수 파일 접미 예: _e16d]
import json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, '..', '..', '..', 'datasets', 'travel', '020.주제별 텍스트 일상 대화 데이터', 'processed')
chat = json.load(open(os.path.join(D, 'chat_sample_3000.json'), encoding='utf-8'))
suf = sys.argv[1] if len(sys.argv) > 1 else ''
fr = json.load(open(os.path.join(HERE, 'results', f'chat_front_mix7{suf}.json')))
mx = [max(r) for r in fr['sims']]


def wilson(k, n):
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    a = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - a) / d, (c + a) / d


print(f'## 잡담 → 항목 오답 비율 (앞단 점수 파일 chat_front_mix7{suf}.json)')
print('| 넘김 모델 | 잡담 수 | 직접(앞단 없이) 항목으로 답함 | 소형 조합 lo 0.25: LLM 으로 넘김 · 항목으로 답함 | 소형 조합 lo 0.10: LLM 으로 넘김 · 항목으로 답함 |')
print('|---|---:|---|---|---|')
for name, f in (('E4B QAT', 'chat_llm_mix7_gemma4_e4b-it-qat.json'), ('12B', 'chat_llm_mix7_gemma4_12b.json')):
    L = json.load(open(os.path.join(HERE, 'results', f)))['picks']
    N = len(L)
    direct = sum(v is not None for v in L.values())
    cells = []
    for lo in (0.25, 0.10):
        routed = [k for k in range(N) if lo <= mx[k] < 0.6]
        fa = sum(L[str(k)] is not None for k in routed) + sum(mx[k] >= 0.6 for k in range(N))
        l, h = wilson(fa, N)
        cells.append(f'{len(routed) / N:.1%} · **{fa / N:.2%}** ({l:.2%}~{h:.2%})')
    l, h = wilson(direct, N)
    print(f'| {name} | {N} | **{direct / N:.1%}** ({l:.1%}~{h:.1%}) | ' + ' | '.join(cells) + ' |')
