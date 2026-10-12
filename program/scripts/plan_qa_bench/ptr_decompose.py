# 일정 항목 짚기의 분해 지표 — 「항목 번호 또는 없음」 과제를 범위 밖(OOS) 평가 관행(CLINC150, Larson 등 2019)에 맞춰 나눈다. 섞은 시험 세트 2,735문제의 저장 결과(git 밖)에서 계산, 새 호출 없음.
#  · 항목 있는 질문(정답 = 일정 항목): 정확도 · 다른 항목을 짚음 · 「없음」으로 닫음(미스) · 읽기 실패(빈 답)
#  · 정답이 없는 질문(정답 = 없음): 「없음」 재현율(= OOS 재현율) · 항목을 짚음(오지목) · 읽기 실패
#  · 「없음」 판정의 정밀도: 「없음」이라고 답한 것 중 실제로 정답이 없음인 비율
#  모든 비율에 Wilson 95% 구간. 엄격 계수(읽기 실패는 오답). 정답 라벨의 한계(같은 장소의 다른 항목)는 평가 리포트 §3-4.
# 사용: python ptr_decompose.py [변형,...]  → results/ptr_decompose.txt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(HERE, '..', 'eval_kit'))
sys.stdout.reconfigure(encoding='utf-8')
from stats import fmt_ratio, mcnemar_exact  # noqa: E402

RES = os.path.join(ROOT, 'datasets', 'travel', 'mixed_testset', 'results')
VARS = sys.argv[1].split(',') if len(sys.argv) > 1 else ['e4b_only', 'rules_e4b', 'no_jev', 'full']
LAB = {'e4b_only': '가르친 E4B 단독', 'rules_e4b': '규칙 → 가르친 E4B', 'no_jev': '규칙 → ML → 가르친 E4B', 'full': '규칙 → ML → Jev 계열(파인튜닝 전 Winnow-E4B) → 가르친 E4B'}


def bad(t):
    return any(f == 'parse_fail' or f.startswith('http_error') for f in t['fail'])


out = ['# 일정 항목 짚기 — 분해 지표 (섞은 시험 세트 2,735문제, 복수 항목 질의 66 제외 2,669, 변형당 1회, 엄격 계수)\n']
data = {}
for v in VARS:
    p = os.path.join(RES, f'chain_mixed_{v}.json')
    if not os.path.exists(p):
        continue
    rows = [t for t in json.load(open(p, encoding='utf-8')) if t['type'] != 'compound_intent']
    data[v] = rows
    item = [t for t in rows if t['gold'] is not None]
    none = [t for t in rows if t['gold'] is None]
    ok = sum(1 for t in item if t['pick'] == t['gold'] and not bad(t))
    wrong = sum(1 for t in item if t['pick'] is not None and t['pick'] != t['gold'] and not bad(t))
    miss = sum(1 for t in item if t['pick'] is None and not bad(t))
    rf_i = sum(1 for t in item if bad(t))
    rec = sum(1 for t in none if t['pick'] is None and not bad(t))
    leak = sum(1 for t in none if t['pick'] is not None)
    rf_n = sum(1 for t in none if bad(t))
    said_none = [t for t in rows if t['pick'] is None and not bad(t)]
    prec = sum(1 for t in said_none if t['gold'] is None)
    out.append(f'## {LAB.get(v, v)}')
    out.append('| 구분 | 지표 | 값 |')
    out.append('|---|---|---|')
    out.append(f'| 항목 있는 질문 {len(item)} | 정확도(정답 항목을 짚음) | {fmt_ratio(ok, len(item))} |')
    out.append(f'| | 다른 항목을 짚음 | {fmt_ratio(wrong, len(item))} |')
    out.append(f'| | 항목이 있는데 「없음」으로 닫음(미스) | {fmt_ratio(miss, len(item))} |')
    out.append(f'| | 읽기 실패(빈 답) | {fmt_ratio(rf_i, len(item))} |')
    out.append(f'| 정답이 없는 질문 {len(none)} | 「없음」 재현율(범위 밖을 제대로 거절) | {fmt_ratio(rec, len(none))} |')
    out.append(f'| | 항목을 짚음(오지목 — 가장 해로운 오류) | {fmt_ratio(leak, len(none))} |')
    out.append(f'| | 읽기 실패(빈 답) | {fmt_ratio(rf_n, len(none))} |')
    out.append(f'| 「없음」 판정 전체 {len(said_none)} | 「없음」 정밀도(그중 실제 정답이 없음) | {fmt_ratio(prec, len(said_none))} |')
    out.append('')
if 'e4b_only' in data:
    base = data['e4b_only']
    out.append('## 전문가 단독과 견줌 (같은 질문 짝지은 McNemar 정확검정 · 엄격 정오)')
    out.append('| 변형 | 이쪽만 맞음 | 단독만 맞음 | p |')
    out.append('|---|---:|---:|---:|')
    for v, rows in data.items():
        if v == 'e4b_only':
            continue
        r = mcnemar_exact([t['pick'] == t['gold'] and not bad(t) for t in rows], [t['pick'] == t['gold'] and not bad(t) for t in base])
        out.append(f"| {LAB.get(v, v)} | {r['a_only']} | {r['b_only']} | {r['p']:.3g} |")
out.append('\n- 한계: 질문은 모델이 쓴 합성(관광지 질문 틀은 우리 장소 이름을 끼운 것)이고 일상 대화 · 구어체는 실제 사람 문장이지만 정답 라벨이 「없음」으로 정해진 것이다. 정답 항목이 같은 장소에 여러 개 있는 질문은 엄격 정답이 낮게 나온다(평가 리포트 §3-4).')
text = '\n'.join(out)
open(os.path.join(HERE, 'results', 'ptr_decompose.txt'), 'w', encoding='utf-8').write(text)
print(text)
