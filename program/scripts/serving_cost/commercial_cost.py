# 상용 API 로 같은 질문(일정 항목 짚기 한 건)을 처리할 때의 비용 — 실제 프롬프트 토큰 수 × 공개 단가.
#  토큰 수: 시험 세트 769문제(요청 둘 제외, 합성)의 프롬프트를 가르친 E4B 의 Gemma 토크나이저로 센 값(서버 B 의 llama-server /tokenize).
#   프롬프트 평균 1,815 토큰 = 일정 목록 접두 1,731(같은 일정이면 같다) + 질문·지시 84. 출력은 {"item": N} 한 줄 약 7토큰(Gemma) → 상용은 10 으로 잡는다.
#   ★상용 모델의 토크나이저로 센 것이 아니다 — 그래서 민감도 열(+30%)을 둔다(Anthropic 문서: 4.7 이후 모델은 이전 토크나이저보다 같은 글에서 약 30% 더 센다).
#   ★생각(추론) 토큰: Codex GPT-6 은 기본으로 추론 토큰이 출력으로 과금될 수 있다 — 출력 10 토큰은 「생각 끔」 가정이다(우리 평가의 상용 점수는 묶음 풀이라 생각 통제 불가).
# 단가 출처(2026-10-07 확인): Anthropic https://platform.claude.com/docs/en/about-claude/pricing · OpenAI https://developers.openai.com/api/docs/pricing
# 환율 가정: 1 USD = 1,400 KRW (민감도 1,350 · 1,500). 사용자 제시: 상용 API 월 5~10만원, RunPod 월 24만원 고정, 오라클 무료 0원.
# 사용: python commercial_cost.py  → results/commercial_cost.md
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding='utf-8')

IN_TOK, PREFIX_TOK, TAIL_TOK, OUT_TOK = 1825, 1731, 84, 10       # 1,815 + 채팅 틀 약 10 / 접두 1,731 / 질문·지시 84 / 출력 10
FX = 1400
# 모델: (이름, 입력 $/MTok, 출력 $/MTok, 캐시 읽기 $/MTok, 캐시 쓰기 배수(입력 대비), 토크나이저 민감도 배수)
MODELS = [
    ('Claude Fable 5.1', 10.0, 50.0, 0.25, 1.25, 1.3),
    ('Claude Opus 5.5', 4.0, 20.0, 0.20, 1.25, 1.3),
    ('Claude Sonnet 5.5', 2.0, 10.0, 0.20, 1.25, 1.3),
    ('Claude Haiku 4.5', 1.0, 5.0, 0.10, 1.25, 1.3),
    ('GPT-6 Astra (Codex)', 10.0, 50.0, 1.00, 1.0, 1.0),
    ('GPT-6 Sol (Codex)', 2.0, 10.0, 0.20, 1.0, 1.0),
    ('GPT-6 Luna (Codex)', 0.10, 0.50, 0.01, 1.0, 1.0),
]
K_SESSION = 10      # 같은 일정에서 연속으로 묻는 질문 수(접두 캐시를 쓰는 경우의 가정 — 실제 사용 패턴은 모른다)


def per_q(m, tok_mult=1.0, cache=False):
    name, pin, pout, pread, wmul, _ = m
    i, p, t, o = IN_TOK * tok_mult, PREFIX_TOK * tok_mult, TAIL_TOK * tok_mult, OUT_TOK * tok_mult
    if not cache:
        return (i * pin + o * pout) / 1e6
    # 일정 한 번에 K 질문: 첫 질문은 접두를 캐시에 쓰고(쓰기 단가), 나머지 K-1 질문은 읽는다. 질문·지시는 매번 일반 입력.
    first = p * pin * wmul + (i - p) * pin
    rest = p * pread + (i - p) * pin
    return ((first + (K_SESSION - 1) * rest) / K_SESSION + o * pout) / 1e6


rows = []
for m in MODELS:
    base = per_q(m)
    sens = per_q(m, m[5])
    cached = per_q(m, 1.0, True)
    rows.append((m[0], base, sens, cached))

out = ['# 상용 API 로 같은 질문을 처리할 때의 비용 (질문 한 건 = 일정 목록 + 고객 질문 → 항목 번호)\n']
out.append(f'- 질문 한 건: 입력 {IN_TOK:,} 토큰(그중 같은 일정이면 반복되는 접두 {PREFIX_TOK:,}) · 출력 {OUT_TOK} 토큰(생각 끔 가정). 환율 1 USD = {FX:,} KRW 가정.')
out.append('')
out.append('| 모델 | 입력 / 출력 단가 ($/MTok) | 질문 1건 (캐시 없음) | 〃 토크나이저 +30% | 〃 접두 캐시(한 일정 10질문) | 5만원이 감당하는 월 질문 수 (캐시 없음) | 10만원이 감당하는 월 질문 수 (캐시 없음) | 월 1만 건 비용 (캐시 없음) | 월 10만 건 비용 (캐시 없음) |')
out.append('|---|---|---|---|---|---:|---:|---:|---:|')
for (m, (name, base, sens, cached)) in zip(MODELS, rows):
    krw = lambda usd: usd * FX
    n5 = int(50000 / krw(base))
    n10 = int(100000 / krw(base))
    out.append(f'| {name} | {m[1]:g} / {m[2]:g} | ${base:.5f} (≈{krw(base):.1f}원) | ${sens:.5f} | ${cached:.5f} (≈{krw(cached):.1f}원) | {n5:,} | {n10:,} | {krw(base) * 10000:,.0f}원 | {krw(base) * 100000:,.0f}원 |')
out.append('')
opus = next(r for r in rows if r[0] == 'Claude Opus 5.5')
out.append(f'- 읽는 법: 상용 API 는 **쓴 만큼** 과금이라 월 비용 = 질문 수 × 건당 비용이다. 사용자 숫자 월 5~10만원이 감당하는 질문 수는 모델에 따라 수천 건(Opus 5.5 · 캐시 없음 약 {int(50000 / (opus[1] * FX)):,}~{int(100000 / (opus[1] * FX)):,}건)에서 수십만 건(Luna)까지 갈린다.')
out.append('- 한계: ① 토큰 수는 Gemma 토크나이저로 센 것(상용 토크나이저는 다를 수 있음 — +30% 열) ② 출력은 생각을 끈 10 토큰 가정, Codex GPT-6 이 추론 토큰을 쓰면 출력이 몇 배가 된다 ③ 접두 캐시는 모델별 최소 캐시 길이 조건(우리 접두 1,731 토큰이 만족하는지)을 확인하지 못했다 `[미확인]` ④ 한 일정 10질문은 가정이다 — 실제 사용 패턴을 모른다 ⑤ 구독(ChatGPT·Claude 요금제)으로 쓰는 Codex·Claude 는 API 단가가 아니라 구독료·한도다.')
text = '\n'.join(out)
os.makedirs(os.path.join(HERE, 'results'), exist_ok=True)
open(os.path.join(HERE, 'results', 'commercial_cost.md'), 'w', encoding='utf-8').write(text)
print(text)
