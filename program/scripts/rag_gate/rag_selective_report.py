# 규정 검색의 「답할지 거절할지」 평가 — 위험–커버리지 곡선 · 거절 재현율 · 오거절률 · 문턱별 표 (저장된 측정에서 계산, 새 호출 없음).
#  정의(문헌): 커버리지 = 답한 질문 비율, 선택적 위험 = 답한 것 중 틀린 비율(Geifman·El-Yaniv 2017) · AURC = 위험–커버리지 곡선 아래 면적(Geifman 등 2019) ·
#   거절 재현율 = 답이 없어야 하는 질문 중 거절한 비율, 오거절률 = 답이 있는 질문 중 거절한 비율(Wen 등 2024 서베이, CLINC150 의 OOS 재현율 관행).
#  「답함」 = 운영 규칙(색인 점수 문턱 τ 이상인 조각이 상위 3개 안에 하나라도 있음 — 고객에게는 그중 앞 2개만 보인다). 「틀림」 = 답 있음 질문에서 보인 조각 중 정답 줄이 없음 / 답 없음 질문에 규정을 보임.
#  유형: 답 있음(answerable) · 코퍼스에 없음(uncovered) · 주제 밖(offtopic) · 근접·부분 답(near_miss — 양성도 음성도 아님, 따로 표시).
# 사용: python rag_selective_report.py  → results/rag_selective_report.txt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', 'eval_kit')))
sys.stdout.reconfigure(encoding='utf-8')
from stats import fmt_ratio, wilson  # noqa: E402

J = lambda *a: json.load(open(os.path.join(HERE, *a), encoding='utf-8'))
DOCS = {'개선 전(운영 색인)': J('results', 'rag_live_correct.json'), '개선 후(색인 E)': J('results', 'rag_live_correct_E.json')}
TAUS = [0.30, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]


def shown(r, tau):
    return [(s, sc) for s, sc in r['rank'][:3] if sc >= tau][:2]      # 제품은 상위 3 중 문턱 이상인 조각의 고객용 문장을 최대 2개만 보인다(저장된 sources 와 178/180 · 156/160 일치)


def at(rows, tau):
    ans = [r for r in rows if r['type'] == 'answerable']
    neg = [r for r in rows if r['type'] in ('uncovered', 'offtopic')]
    nm = [r for r in rows if r['type'] == 'near_miss']
    answered_ans = [r for r in ans if shown(r, tau)]
    right = [r for r in answered_ans if {s for s, _ in shown(r, tau)} & set(r['gold'])]
    leak = [r for r in neg if shown(r, tau)]
    nm_show = [r for r in nm if shown(r, tau)]
    answered_total = len(answered_ans) + len(leak)          # 근접 답은 위험 계산에서 뺀다(정답이 모호)
    wrong = (len(answered_ans) - len(right)) + len(leak)
    return {'tau': tau, 'n_ans': len(ans), 'n_neg': len(neg), 'n_nm': len(nm), 'answered_ans': len(answered_ans), 'right': len(right), 'leak': len(leak), 'nm_show': len(nm_show),
            'coverage_ans': len(answered_ans) / len(ans), 'false_reject': len(ans) - len(answered_ans), 'reject_recall': 1 - len(leak) / len(neg),
            'risk': (wrong / answered_total) if answered_total else 0.0, 'answered_total': answered_total, 'wrong': wrong}


def aurc(rows):
    """모든 문턱에서 (커버리지, 위험) 점들을 이어 아래 면적을 사다리꼴로 계산 — 점수가 높은 질문부터 답하는 순서로(문턱을 1.0 에서 0.0 까지 내림)."""
    pts = []
    n_scored = [r for r in rows if r['type'] in ('answerable', 'uncovered', 'offtopic')]
    for t in sorted({round(0.01 * k, 2) for k in range(0, 100)}, reverse=True):
        ans = [r for r in n_scored if shown(r, t)]
        if not ans:
            continue
        wrong = 0
        for r in ans:
            if r['type'] == 'answerable':
                wrong += not ({s for s, _ in shown(r, t)} & set(r['gold']))
            else:
                wrong += 1
        pts.append((len(ans) / len(n_scored), wrong / len(ans)))
    area = 0.0
    for (c0, r0), (c1, r1) in zip(pts, pts[1:]):
        area += (c1 - c0) * (r0 + r1) / 2
    return area, pts


print('# 규정 검색 — 답할지 거절할지(선택적 예측) 평가 (질문은 모두 합성, 1회 측정)')
print('- 「위험」 = 답한 질문 중 틀린 비율(답 있음인데 정답 줄을 못 보임 + 답 없음인데 규정을 보임) ÷ 답한 질문 수(근접·부분 답은 뺌). 커버리지 = 답 있음 질문 중 답한 비율.\n')
for sname in ('A', 'B'):
    print(f'## 세트 {sname}')
    for lab, doc in DOCS.items():
        rows = doc['correct'][sname]
        print(f'### {lab}')
        print('| 문턱 τ | 답 있음 중 답함(커버리지) | 답 있음 중 정답을 보임 | 오거절률(답 있음인데 거절) | 거절 재현율(답 없음 중 거절) | 선택적 위험(답한 것 중 틀림) | 근접·부분 답에 보임 |')
        print('|---:|---|---|---|---|---|---|')
        for t in TAUS:
            m = at(rows, t)
            mark = ' ◀ 운영' if abs(t - 0.55) < 1e-9 else ''
            print(f"| {t:.2f}{mark} | {fmt_ratio(m['answered_ans'], m['n_ans'])} | {fmt_ratio(m['right'], m['n_ans'])} | {fmt_ratio(m['false_reject'], m['n_ans'])} | {fmt_ratio(m['n_neg'] - m['leak'], m['n_neg'])} | {fmt_ratio(m['wrong'], m['answered_total'])} | {m['nm_show']}/{m['n_nm']} |")
        a, _ = aurc(rows)
        print(f'- AURC(위험–커버리지 곡선 아래 면적, 작을수록 좋음): {a:.3f}\n')
print('## 읽는 법')
print('- 문턱을 올리면 새어 나감은 줄지만 오거절이 는다 — 어디에 놓을지는 「틀린 규정을 보이는 비용」과 「답을 안 하는 비용」의 비중으로 정하며, 이 표는 그 맞바꿈을 보여 준다.')
print('- 문턱은 개발 세트에서 고르고 보류 세트에는 한 번만 적용한다(SQuAD 2.0 관행). 같은 세트에서 고른 문턱의 점수는 낙관적이다.')
