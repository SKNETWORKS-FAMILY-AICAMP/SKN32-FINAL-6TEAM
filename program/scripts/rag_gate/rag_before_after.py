# 규정 검색(RAG) 개선 전후 비교 — 기준(운영 색인 A, results/rag_live_*.json)과 개선 후(색인 E, results/rag_live_*_E.json)를 같은 질문·같은 제품 답변 함수로 잰 값을 나란히 놓는다.
#  사용: python rag_before_after.py > results/rag_before_after.txt
import json
import math
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
from rag_metrics_lib import HERE, J, confusion, pct, retrieval, shown  # noqa: E402

BEF = J('results', 'rag_live_correct.json')
AFT = J('results', 'rag_live_correct_E.json')
BMX = J('results', 'rag_live_mixed.json') if os.path.exists(os.path.join(HERE, 'results', 'rag_live_mixed.json')) else None
AMX = J('results', 'rag_live_mixed_E.json') if os.path.exists(os.path.join(HERE, 'results', 'rag_live_mixed_E.json')) else None
BML = J('results', 'rag_live_multilang.json') if os.path.exists(os.path.join(HERE, 'results', 'rag_live_multilang.json')) else None
AML = J('results', 'rag_live_multilang_E.json') if os.path.exists(os.path.join(HERE, 'results', 'rag_live_multilang_E.json')) else None


def mcn(a, b):
    """짝지은 정확 검정: a 만 맞음 / b 만 맞음 / p"""
    n = a + b
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(min(a, b) + 1)) / 2 ** n) if n else 1.0


print('# 규정 검색(RAG) 개선 전후 — 같은 질문·같은 제품 답변 함수(question_reply)·같은 임베딩(x600 Ollama bge-m3)')
print(f"- 개선 전 = 운영 색인 A(직원용 본문, DB 의 벡터 칸) · 개선 후 = 색인 E(문서 제목 + 절 제목 + 고객용 문장)를 제품 코드가 같은 방식으로 임베딩해 검색 자리(policy_search)에만 바꿔 끼운 판(제품 코드·DB 는 안 바꿨다). 문턱 0.55·상위 3·고객용 문장 2개 그대로.")
print(f"- 측정일 {BEF['meta']['날짜']} (개선 전) · {AFT['meta']['날짜']} (개선 후). 질문은 모두 합성(Codex 가 쓴 A·B, 일상 대화는 AI Hub 실제 대화 문장).")
for name, lab in (('A', 'A(고객용 문장을 보고 쓴 180문제 — 낱말이 겹쳐 쉽다)'), ('B', 'B(독립 160문제)')):
    b, a = BEF['correct'][name], AFT['correct'][name]
    mb, ma = retrieval(b, ks=(1, 3, 5, 10)), retrieval(a, ks=(1, 3, 5, 10))
    cb, ca = confusion(b, 0.55), confusion(a, 0.55)
    print(f'\n## {lab}')
    print('| 지표 | 개선 전 | 개선 후 | 변화 |')
    print('|---|---:|---:|---:|')
    for k in (1, 3, 5, 10):
        print(f'| Recall@{k} | {mb[k][1]:.3f} ({mb[k][3]}/{mb["n"]}) | {ma[k][1]:.3f} ({ma[k][3]}/{ma["n"]}) | {ma[k][1] - mb[k][1]:+.3f} |')
    print(f'| Precision@3 | {mb[3][0]:.3f} | {ma[3][0]:.3f} | {ma[3][0] - mb[3][0]:+.3f} |')
    print(f'| F1@3(질문별 평균) | {mb[3][2]:.3f} | {ma[3][2]:.3f} | {ma[3][2] - mb[3][2]:+.3f} |')
    print(f'| MRR | {mb["mrr"]:.3f} | {ma["mrr"]:.3f} | {ma["mrr"] - mb["mrr"]:+.3f} |')
    print(f'| nDCG@10 | {mb["ndcg10"]:.3f} | {ma["ndcg10"]:.3f} | {ma["ndcg10"] - mb["ndcg10"]:+.3f} |')
    print(f"| τ 0.55 답할 질문 판정 Precision | {cb['p']:.3f} | {ca['p']:.3f} | {ca['p'] - cb['p']:+.3f} |")
    print(f"| τ 0.55 답할 질문 판정 Recall | {cb['r']:.3f} ({cb['tp']}/{cb['tp'] + cb['fn']}) | {ca['r']:.3f} ({ca['tp']}/{ca['tp'] + ca['fn']}) | {ca['r'] - cb['r']:+.3f} |")
    print(f"| τ 0.55 F1 | {cb['f1']:.3f} | {ca['f1']:.3f} | {ca['f1'] - cb['f1']:+.3f} |")
    ans = [(x, y) for x, y in zip(b, a) if x['type'] == 'answerable']
    ok_b = [bool(set(x['sources']) & set(x['gold'])) for x, y in ans]
    ok_a = [bool(set(y['sources']) & set(y['gold'])) for x, y in ans]
    wb = [bool(x['sources']) and not (set(x['sources']) & set(x['gold'])) for x, y in ans]
    wa = [bool(y['sources']) and not (set(y['sources']) & set(y['gold'])) for x, y in ans]
    only_a = sum(1 for p, q in zip(ok_b, ok_a) if q and not p)
    only_b = sum(1 for p, q in zip(ok_b, ok_a) if p and not q)
    print(f"| 정답 줄을 보인 비율(답 있음 {len(ans)}문제) | {pct(sum(ok_b), len(ans))} | {pct(sum(ok_a), len(ans))} | 개선 후만 맞음 {only_a} · 개선 전만 맞음 {only_b} (정확검정 p={mcn(only_a, only_b):.3g}) |")
    print(f"| 틀린 줄만 보인 비율 | {pct(sum(wb), len(ans))} | {pct(sum(wa), len(ans))} | |")
    neg = [(x, y) for x, y in zip(b, a) if x['type'] in ('uncovered', 'offtopic')]
    print(f"| 답 없는 질문(코퍼스에 없음·주제 밖)에 규정 문장을 보임 | {pct(sum(1 for x, y in neg if x['sources']), len(neg))} | {pct(sum(1 for x, y in neg if y['sources']), len(neg))} | |")
    nm = [(x, y) for x, y in zip(b, a) if x['type'] == 'near_miss']
    print(f"| 근접 오답·부분 답 질문에 규정 문장을 보임({len(nm)}) | {pct(sum(1 for x, y in nm if x['sources']), len(nm))} | {pct(sum(1 for x, y in nm if y['sources']), len(nm))} | |")

if BMX and AMX:
    print('\n## 실전처럼 섞은 입력(2,340건) — 규정과 무관한 말에 규정 문장을 보인 비율')
    print('| 출처 | 건수 | 개선 전 | 개선 후 |')
    print('|---|---:|---:|---:|')
    for src in ('일상 대화(AI Hub)', '구어체 대화(KoCulture)', '관광지 질문(서울·경기 QA)', '여행 대화 발화(KLUE-WoS)'):
        rb = [r for r in BMX['rows'] if r['src'] == src]
        ra = [r for r in AMX['rows'] if r['src'] == src]
        print(f"| {src} | {len(rb)} | {pct(sum(1 for r in rb if r['sources']), len(rb))} | {pct(sum(1 for r in ra if r['sources']), len(ra))} |")
    cb = [r for r in BMX['rows'] if r['label'] == 'chitchat']
    ca = [r for r in AMX['rows'] if r['label'] == 'chitchat']
    print(f"| **규정과 무관한 말 합계(일상 대화+구어체)** | {len(cb)} | **{pct(sum(1 for r in cb if r['sources']), len(cb))}** | **{pct(sum(1 for r in ca if r['sources']), len(ca))}** |")

if BML and AML:
    print('\n## 다국어(독립 세트 B 의 영·일·중 번역) — 개선 전후')
    print('| 언어 | Recall@1 전 → 후 | Recall@3 전 → 후 | τ 0.55 양성 Recall 전 → 후 | 음성 거절 전 → 후 |')
    print('|---|---|---|---|---|')
    for lang, lab in (('ko', '한국어'), ('en', '영어'), ('ja', '일본어'), ('zh', '중국어 간체')):
        rb = BEF['correct']['B'] if lang == 'ko' else [r for r in BML['rows'] if r['lang'] == lang]
        ra = AFT['correct']['B'] if lang == 'ko' else [r for r in AML['rows'] if r['lang'] == lang]
        mb, ma = retrieval(rb, ks=(1, 3)), retrieval(ra, ks=(1, 3))
        cb, ca = confusion(rb, 0.55), confusion(ra, 0.55)
        print(f"| {lab} | {mb[1][3]}/{mb['n']} → {ma[1][3]}/{ma['n']} | {mb[3][3]}/{mb['n']} → {ma[3][3]}/{ma['n']} | {cb['tp']}/{cb['tp'] + cb['fn']} → {ca['tp']}/{ca['tp'] + ca['fn']} | {cb['tn']}/{cb['tn'] + cb['fp']} → {ca['tn']}/{ca['tn'] + ca['fp']} |")
