# 학습한 분류 인코더(e5-base) 대 학습 없는 LLM(Gemma-4 E4B 제로샷) — 같은 문장에서 짝지은 비교. 저장된 예측에서 계산(새 호출 없음).
#  라벨 칸마다: 학습한 쪽 정확도 · 학습 없는 쪽 정확도 · McNemar 정확검정(이쪽만 맞음 : 저쪽만 맞음) · 짝지은 부트스트랩 정확도 차이 95% 구간.
#  시험 세트 CX 400(교차 라벨, 어긋난 칸 제외) · G96(Claude 초안 라벨, 사람 검수 전). 값이 없는(마스크) 칸은 제외.
# 사용: python cls_paired.py  → results/cls_paired.txt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8')
from stats import fmt_ratio, mcnemar_exact, paired_bootstrap_diff  # noqa: E402

PULL = os.path.join(ROOT, 'program', 'scripts', 'plan_qa_bench', 'results', '_pull', 'cls')
FIX = os.path.join(ROOT, 'program', 'scripts', 'plan_qa_bench', 'fixtures', 'cls')
HEADS = ['intent', 'sentiment', 'severity', 'case_type']
KO = {'intent': '요청 종류(의도)', 'sentiment': '감정', 'severity': '긴급도', 'case_type': '대상 종류'}
trained = json.load(open(os.path.join(PULL, 'cls_pred_e5base.json'), encoding='utf-8'))
zero = json.load(open(os.path.join(PULL, 'llm_cls_gemma4_e4b-it-qat.json'), encoding='utf-8'))
out = ['# 학습한 분류 인코더(e5-base, 시드 1개) 대 학습 없는 LLM(Gemma-4 E4B 제로샷) — 같은 문장 짝지은 비교\n']
for tname in ('test_cx.jsonl', 'test_g96.jsonl'):
    rows = [json.loads(l) for l in open(os.path.join(FIX, tname), encoding='utf-8')]
    tp = {p['id']: p for p in trained[tname]['preds']}
    zp = {p['id']: p for p in zero[tname]['preds']}
    out.append(f'## {tname} ({len(rows)}문장)')
    out.append('| 라벨 | 표본 | 학습한 분류기 | 학습 없는 LLM | 학습한 쪽만 맞음 : LLM 만 맞음 | McNemar p | 정확도 차이(학습−LLM) 95% 구간 |')
    out.append('|---|---:|---|---|---|---:|---|')
    for h in HEADS:
        idx = [r for r in rows if r.get(h) and not r.get('mask_' + h) and r['id'] in tp and r['id'] in zp]
        a = [tp[r['id']].get(h) == r[h] for r in idx]
        b = [zp[r['id']].get(h) == r[h] for r in idx]
        m = mcnemar_exact(a, b)
        d = paired_bootstrap_diff([1.0 if x else 0.0 for x in a], [1.0 if x else 0.0 for x in b])
        out.append(f"| {KO[h]} | {len(idx)} | {fmt_ratio(sum(a), len(a))} | {fmt_ratio(sum(b), len(b))} | {m['a_only']} : {m['b_only']} | {m['p']:.3g} | {d['diff']:+.3f} ({d['lo']:+.3f}~{d['hi']:+.3f}) |")
    out.append('')
out.append('- 한계: CX 의 정답은 Codex 작성 + Claude 교차 라벨, G96 은 Claude 초안 라벨(사람 검수 전). 학습한 분류기는 시드 1개. G96 은 표본이 96이라 구간이 넓다.')
text = '\n'.join(out)
os.makedirs(os.path.join(HERE, 'results'), exist_ok=True)
open(os.path.join(HERE, 'results', 'cls_paired.txt'), 'w', encoding='utf-8').write(text)
print(text)
