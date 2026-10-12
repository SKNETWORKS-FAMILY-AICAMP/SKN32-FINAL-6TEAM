# 분류 네 축 — 우리(학습한 e5-base 분류기) · Gemma-4 E4B 제로샷 · Codex 루나 · 솔(제로샷, 서비스 지시문 그대로)을 같은 시험 문장에서 센다. 새 호출 없음.
#  지표: 축마다 정확도(Wilson 95%) · 매크로 F1(부트스트랩 95%) · 네 축 동시 정답(네 라벨이 모두 값이 있고 모두 맞은 문장) · 우리와 짝지은 McNemar(축별) · 지연 중앙/p95(CLI 기준).
#  ★CX 400 은 Codex 가 쓴 문장이라 Codex 모델에 출제자 편향이 있다. G96(Claude 초안 라벨)을 주 비교로 읽는다.
# 사용: python codex_cls_report.py   → results/codex_cls_report.md
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'eval_kit'))
from stats import bootstrap_ci, fmt_ratio, mcnemar_exact, percentile, prf_table  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
PULL = os.path.join(HERE, 'results', '_pull', 'cls')
FIX = os.path.join(HERE, 'fixtures', 'cls')
HEADS = ['intent', 'sentiment', 'severity', 'case_type']
LABS = {'intent': ['adjust_reject', 'confirm_request', 'incident_report', 'itinerary_submit', 'other'], 'sentiment': ['positive', 'neutral', 'negative'], 'severity': ['low', 'medium', 'high', 'critical'],
        'case_type': ['activity', 'dining', 'mobility', 'booking', 'lodging', 'flight', 'other']}
KO = {'intent': '의도', 'sentiment': '감정', 'severity': '긴급도', 'case_type': '대상 종류'}


def load(name):
    p = os.path.join(PULL, name)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}


SYS = {'우리(학습한 e5-base)': load('cls_pred_e5base.json'), 'Gemma-4 E4B 제로샷': load('llm_cls_gemma4_e4b-it-qat.json'),
       'Codex 루나(제로샷)': load('codex_cls_gpt-6-luna.json'), 'Codex 솔(제로샷)': load('codex_cls_gpt-6-sol.json')}
out = ['# 고객 말 분류 — 우리 · Gemma 제로샷 · Codex 루나 · 솔 (같은 시험 문장, 서비스 지시문 그대로, 학습 없음은 제로샷)\n',
       '- ★CX 400 은 Codex 가 쓴 문장 → Codex 모델에 출제자 편향. **G96(Claude 초안 라벨, 사람 검수 전)을 주 비교**로 읽는다. 우리 분류기는 CX 와 같은 합성 분포로 학습했다.',
       '- Codex 는 CLI 를 문장마다 한 번씩 불러 잰 값(구독 CLI, API 직접 호출이 아님) — 지연은 CLI 시작·추론 오버헤드를 포함해 API 보다 느리다.\n']
for fname, title in (('test_g96.jsonl', 'G96 (96문장, 주 비교)'), ('test_cx.jsonl', 'CX 400 (Codex 출제자 편향 있음)')):
    rows = [json.loads(l) for l in open(os.path.join(FIX, fname), encoding='utf-8')]
    out.append(f'\n## {title}\n')
    out.append('| 시스템 | 의도 | 감정 | 긴급도 | 대상 종류 | 네 축 동시 정답 | 매크로 F1(의도/감정/긴급도/대상) | 호출 실패 | 지연 p50 / p95 (초) |')
    out.append('|---|---|---|---|---|---|---|---:|---|')
    ours_ok = {}
    for sname, data in SYS.items():
        d = data.get(fname)
        if not d:
            continue
        pred = {p['id']: p for p in d['preds']}
        cells, f1s = [], []
        allc = {}
        flags = {h: {} for h in HEADS}
        fail = sum(1 for r in rows if r['id'] not in pred or 'error' in pred[r['id']])
        for h in HEADS:
            idx = [r for r in rows if r.get(h) in LABS[h] and not r.get('mask_' + h)]
            ok = []
            gold, pr = [], []
            for r in idx:
                p = pred.get(r['id'])
                good = bool(p) and 'error' not in p and p.get(h) == r[h]
                ok.append(good)
                flags[h][r['id']] = good
                allc.setdefault(r['id'], {})[h] = good
                gold.append(r[h])
                pr.append(p.get(h) if p and 'error' not in p else '__fail__')
            cells.append(fmt_ratio(sum(ok), len(ok)))
            pt = prf_table(gold, pr, LABS[h])['macro_f1']
            f1s.append(f'{pt:.2f}')
        full = [v for v in allc.values() if len(v) == 4]
        simul = fmt_ratio(sum(1 for v in full if all(v.values())), len(full)) if full else '—'
        secs = [p['sec'] for p in pred.values() if 'sec' in p and 'error' not in p]
        lat = f'{percentile(secs, 50):.1f} / {percentile(secs, 95):.1f}' if secs else ('(해당 없음)' if '우리' in sname else '—')
        out.append(f"| {sname} | " + ' | '.join(cells) + f" | {simul} | {' / '.join(f1s)} | {fail} | {lat} |")
        if '우리' in sname:
            ours_ok = flags
        elif ours_ok:
            ms = []
            for h in HEADS:
                keys = [k for k in flags[h] if k in ours_ok[h]]
                m = mcnemar_exact([flags[h][k] for k in keys], [ours_ok[h][k] for k in keys])
                ms.append(f"{KO[h]} {m['a_only']}:{m['b_only']}(p={m['p']:.2g})")
            out.append(f"| ↳ 우리와 짝지은 비교(이쪽만 : 우리만) | {' · '.join(ms)} | | | | | | | |")
out.append('\n- 한계: 합성 문장 · 제로샷 · 1회. 우리 분류기는 시드 1개. G96 은 표본이 96이라 구간이 넓다. 호출 실패(메모리 부족 등 시스템 오류)는 재시도 뒤에도 남은 것만 센다.')
text = '\n'.join(out)
open(os.path.join(HERE, 'results', 'codex_cls_report.md'), 'w', encoding='utf-8').write(text)
print(text)
