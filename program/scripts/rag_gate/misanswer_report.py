# misanswer_product_path.py 가 남긴 결과(results/misanswer/{pool,decisions,replies_A,replies_E}.json)에서 오응답 지표를 센다 — 새 호출 없음.
#  집단: 규정 질문(답 있음) · 규정 질문처럼 보이나 규정에 답이 없는 말(코퍼스에 없음 · 주제 밖) · 비슷하지만 다른 말(근접·부분) · 규정이 아닌 말(일상 대화 · 구어체 · 관광지 질문 · 여행 대화 KLUE-WoS).
#  「규정을 붙임」 = 결정 단위가 ask_policy 로 고르고 + 규정 검색이 문턱을 넘은 조각을 실제로 답에 실었다(sources 가 비어 있지 않다).
#  지표: 정답 규정을 붙인 비율(재현율) · 붙인 것 중 맞은 비율(정밀도) · 오응답률(규정이 아닌 말 · 답 없는 말에 규정을 붙인 비율) — 모두 Wilson 95% · 지연 p50/p95.
# 사용: python misanswer_report.py [A|E]   → results/misanswer/report_<색인>.md
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'eval_kit'))
from stats import fmt_ratio, percentile  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
OUT = os.path.join(HERE, 'results', 'misanswer')
IDX = sys.argv[1] if len(sys.argv) > 1 else 'E'
P = json.load(open(os.path.join(OUT, 'pool.json'), encoding='utf-8'))
DEC = json.load(open(os.path.join(OUT, 'decisions.json'), encoding='utf-8'))
REP = json.load(open(os.path.join(OUT, f'replies_{IDX}.json'), encoding='utf-8'))


def group(x):
    if x['src'].startswith('합성'):
        return {'answerable': 'REG+ 규정 질문(답 있음)', 'uncovered': 'REG- 코퍼스에 없는 규정풍 질문', 'offtopic': 'REG- 주제 밖', 'near_miss': 'NEAR 비슷하지만 다른 말'}[x['label']]
    return {'일상 대화(AI Hub)': 'NON 일상 대화', '구어체 대화(KoCulture)': 'NON 구어체 대화', '관광지 질문(서울·경기 QA)': 'NON 관광지 질문', '여행 대화 발화(KLUE-WoS)': 'NON 여행 대화 발화(WoS)'}[x['src']]


def attached(q):
    d = DEC[q]
    r = REP.get(q)
    return d['action'] == 'ask_policy' and r is not None and bool(r.get('sources'))


rows = []
for x in P['pool']:
    q = x['q']
    if q not in DEC or DEC[q].get('error'):
        continue
    g = group(x)
    ok = None
    if g.startswith('REG+'):
        r = REP.get(q)
        gold = {s for s in x['gold']}
        ok = bool(DEC[q]['action'] == 'ask_policy' and r and set(r.get('sources') or []) & gold)
    rows.append({'g': g, 'q': q, 'action': DEC[q]['action'], 'item': DEC[q]['item'], 'att': attached(q), 'ok': ok, 'sec': DEC[q]['seconds']})
errs = sum(1 for x in P['pool'] if x['q'] in DEC and DEC[x['q']].get('error'))
out = [f'# 오응답 — 제품 실제 경로(결정 단위 → ask_policy 일 때만 규정 검색 → 문턱 0.55) · 규정 색인 {IDX} ({"운영 색인" if IDX == "A" else "개선 색인 E"})\n']
out.append(f'- 문장 {len(P["pool"])}개 중 결정 단위 호출 실패 {errs}개(분모에서 뺌, 아래 표 분모는 성공한 것). 여행은 고정 1개(일정 10개, 변경 이력 없음). 결정 모델 gemma4:12b.\n')
by = collections.defaultdict(list)
for r in rows:
    by[r['g']].append(r)
out.append('| 집단 | 문장 수 | 결정 단위가 ask_policy 로 고름 | **규정을 붙임**(실제로 규정 문장을 답에 실음) | 그중 정답 규정 |')
out.append('|---|---:|---|---|---|')
for g in sorted(by):
    v = by[g]
    n = len(v)
    ap = sum(1 for r in v if r['action'] == 'ask_policy')
    at = sum(1 for r in v if r['att'])
    ok = sum(1 for r in v if r['ok']) if g.startswith('REG+') else None
    out.append(f"| {g} | {n} | {fmt_ratio(ap, n)} | {fmt_ratio(at, n)} | " + (fmt_ratio(ok, n) if ok is not None else '—') + ' |')
neg = [r for r in rows if r['g'].startswith('NON') or r['g'].startswith('REG-')]
pos = [r for r in rows if r['g'].startswith('REG+')]
tp = sum(1 for r in pos if r['ok'])
fp_neg = sum(1 for r in neg if r['att'])
fp_wrong = sum(1 for r in pos if r['att'] and not r['ok'])
out.append('\n**요약 지표**(근접·부분 답은 양성도 음성도 아니라 뺀다)')
out.append(f'- **오응답률** = 규정이 아닌 말 · 규정에 답이 없는 말 {len(neg)}개 중 규정을 붙인 비율: **{fmt_ratio(fp_neg, len(neg))}**')
non = [r for r in rows if r['g'].startswith('NON')]
out.append(f"  - 규정이 아닌 말만(일상 대화 · 구어체 · 관광지 질문 · 여행 대화 {len(non)}개): {fmt_ratio(sum(1 for r in non if r['att']), len(non))}")
out.append(f"  - 규정풍이지만 답이 없는 말 {len(neg) - len(non)}개: {fmt_ratio(sum(1 for r in neg if r['g'].startswith('REG-') and r['att']), len(neg) - len(non))}")
out.append(f'- **재현율** = 규정 질문(답 있음) {len(pos)}개 중 정답 규정을 붙인 비율: **{fmt_ratio(tp, len(pos))}** (결정 단위가 ask_policy 로 못 고른 것 {sum(1 for r in pos if r["action"] != "ask_policy")}개)')
prec_den = tp + fp_neg + fp_wrong
out.append(f'- **정밀도** = 규정을 붙인 답 {prec_den}개 중 정답 규정을 붙인 비율: **{fmt_ratio(tp, prec_den)}** (틀린 규정 {fp_wrong} + 규정 아닌 말에 붙인 것 {fp_neg})')
f1 = 2 * (tp / prec_den) * (tp / len(pos)) / ((tp / prec_den) + (tp / len(pos))) if prec_den and tp else 0.0
out.append(f'- F1 = {f1:.3f}')
# 일정 항목 짚기·조작 오응답 — 규정 아닌 말에 일정을 건드리거나 일정 사실을 답한 비율
out.append('\n**규정이 아닌 말에서 결정 단위가 고른 할 일**(일정과 무관한 말인데 일정을 짚거나 바꾸려는 것이 오응답)')
out.append('| 집단 | other | clarify | ask_policy | answer_fact | 일정 바꾸기·되돌리기·신고(apply · propose · rollback · redo · report) |')
out.append('|---|---:|---:|---:|---:|---:|')
for g in sorted(by):
    if not g.startswith('NON'):
        continue
    c = collections.Counter(r['action'] for r in by[g])
    ch = sum(c[a] for a in ('apply_change', 'propose_alternatives', 'rollback', 'redo', 'report_delay', 'report_closed'))
    n = len(by[g])
    out.append(f"| {g} ({n}) | {c['other']} | {c['clarify']} | {c['ask_policy']} | {c['answer_fact']} | {ch} ({ch / n:.1%}) |")
# 일정 항목 짚기 오응답 — 일정과 무관한 말(일상 대화 · 구어체)에서 결정 단위가 일정 항목을 짚은 비율(규정과 별개의 오응답)
CHG = ('apply_change', 'propose_alternatives', 'rollback', 'redo', 'report_delay', 'report_closed')
out.append('\n**일정 항목 짚기 오응답** — 결정 단위가 일정 항목(대상)을 짚은 비율. 일상 대화 · 구어체는 일정과 무관한 말이라 짚으면 오응답이다. 여행 대화(KLUE-WoS) · 관광지 질문은 일정과 관련될 수 있어 정답 라벨이 없다(참고).')
out.append('| 집단 | 문장 수 | 일정 항목을 짚음 | 그중 일정을 바꾸는 할 일 + 항목을 짚음 | 바꾸는 할 일(항목 없이도) | 사실 답 + 항목을 짚음 |')
out.append('|---|---:|---|---|---|---|')
for lab, keys in (('일상 대화(AI Hub)', ('NON 일상 대화',)), ('구어체(KoCulture)', ('NON 구어체 대화',)), ('일상 + 구어체(일정과 무관, 주 지표)', ('NON 일상 대화', 'NON 구어체 대화')),
                  ('여행 대화(KLUE-WoS, 참고)', ('NON 여행 대화 발화(WoS)',)), ('관광지 질문(참고)', ('NON 관광지 질문',))):
    v = [r for g in keys for r in by[g]]
    n = len(v)
    pinned = sum(1 for r in v if r['item'] not in ('none', None))
    chp = sum(1 for r in v if r['action'] in CHG and r['item'] not in ('none', None))
    cha = sum(1 for r in v if r['action'] in CHG)
    afp = sum(1 for r in v if r['action'] == 'answer_fact' and r['item'] not in ('none', None))
    out.append(f'| {lab} | {n} | {fmt_ratio(pinned, n)} | {fmt_ratio(chp, n)} | {fmt_ratio(cha, n)} | {fmt_ratio(afp, n)} |')
secs = [r['sec'] for r in rows]
rep_ms = [REP[q]['ms'] for q in REP if REP[q] and REP[q].get('ms')]
out.append(f"\n**지연**: 결정 단위(모델 한 번) 중앙 {percentile(secs, 50):.2f}초 · p95 {percentile(secs, 95):.2f}초 · 최대 {max(secs):.1f}초 (n={len(secs)}, 3개 동시 호출 속에서 잼 — 단독 호출보다 느릴 수 있다) · 규정 답(ask_policy 일 때) 중앙 {percentile(rep_ms, 50):.0f}ms · p95 {percentile(rep_ms, 95):.0f}ms (n={len(rep_ms)})")
text = '\n'.join(out)
open(os.path.join(OUT, f'report_{IDX}.md'), 'w', encoding='utf-8').write(text)
print(text)
