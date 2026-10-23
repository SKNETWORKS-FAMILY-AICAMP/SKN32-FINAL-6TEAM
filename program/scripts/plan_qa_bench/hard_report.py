# 어려운 보류 세트 H(솔 6.1 이 만든 오지목 유발 문장 + 정답 있는 대조 문장, 루나 6.0 이 따로 라벨해 합의한 1,316개)에서 짚기 모델들의 유형별 오지목 · 정답 선택률을 센다. 새 호출 없음.
#  유형: N1 항목 낱말을 섞은 잡담 · N2 일정에 없는 비슷한 장소 · N3 일반 여행 정보 · N4 어느 항목인지 모르는 짧은 말 · N5 일정 전체 감정 · N6 새 항목 추가 요청 (정답 모두 「없음」)
#        P1 이름 그대로 · P2 줄임/별칭/오타 · P3 날짜·순서·시각으로 가리킴 · P4 내용 설명으로 가리킴 (정답 = 항목 하나)
#  ★같은 장소가 여러 번 나오는 일정에서 다른 방문을 고른 것은 따로 센다(정답 표시가 모호한 경우 — §92-18 추가 문단).
# 사용: python hard_report.py  → results/hard_report.md
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'eval_kit'))
from stats import fmt_ratio  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
D = os.path.join(HERE, 'results', 'd_test')
SET = os.path.join(HERE, '..', '..', '..', 'datasets', 'core', 'pointing', 'testset', 'confusing_trap_sentences_v1', 'h_set_test_30_20261015_agree.json')
TAGS = [('시드 1', 'e4bt'), ('시드 2', 'e4bs2'), ('시드 3', 'e4bs3'), ('oos1', 'oos1'), ('oos2', 'oos2'), ('oos3', 'oos3'), ('oos2r(어려운 문장 보강)', 'oos2r')]
P = {x['i']: x for x in json.load(open(SET, encoding='utf-8'))}


def line(pr, k):
    m = re.search(rf'^{k}\. (.*)$', pr, re.M)
    return m.group(1) if m else None


def place(l):
    return l.split(' @ ')[-1].strip() if l and ' @ ' in l else None


def load(tag):
    p = os.path.join(D, f'd_test_lp_h_q4km_{tag}.jsonl')
    if not os.path.exists(p):
        return None
    return {json.loads(l)['i']: json.loads(l) for l in open(p, encoding='utf-8')}


runs = {lab: load(t) for lab, t in TAGS}
runs = {k: v for k, v in runs.items() if v}
NEG = ['hard_N1', 'hard_N2', 'hard_N3', 'hard_N4', 'hard_N5', 'hard_N6']
POSC = ['hard_P1', 'hard_P2', 'hard_P3', 'hard_P4']
NAME = {'hard_N1': 'N1 항목 낱말 섞인 잡담', 'hard_N2': 'N2 일정에 없는 비슷한 장소', 'hard_N3': 'N3 일반 여행 정보', 'hard_N4': 'N4 어느 항목인지 모르는 말', 'hard_N5': 'N5 일정 전체 감정',
        'hard_N6': 'N6 새 항목 추가 요청', 'hard_P1': 'P1 이름 그대로', 'hard_P2': 'P2 줄임 · 별칭 · 오타', 'hard_P3': 'P3 날짜 · 순서 · 시각', 'hard_P4': 'P4 내용 설명'}
out = ['# 어려운 세트 H — 짚기 모델 유형별 오지목 · 정답 선택률 (서비스 기반 Q4_K_M, 생각 끔, 엄격 계수)\n',
       'H = 솔 6.1 이 일정 30개마다 만든 함정 · 대조 문장 중 루나 6.0 이 따로 라벨해 합의한 1,316개(함정 855 · 대조 461). 이견 64개는 뺐다. 정답이 「없음」인 문장에서 항목을 고르면 오지목.\n',
       '| 유형 | 문장 수 | ' + ' | '.join(runs) + ' |', '|---|---:|' + '---|' * len(runs)]
tot_neg = {}
for c in NEG:
    ids = [i for i, x in P.items() if x['type'] == c]
    cells = []
    for lab, R in runs.items():
        k = sum(1 for i in ids if i in R and R[i].get('parsed') and R[i]['pick'] is not None)
        cells.append(fmt_ratio(k, len(ids)).split(' (')[0])
    out.append(f'| {NAME[c]} | {len(ids)} | ' + ' | '.join(cells) + ' |')
ids_all = [i for i, x in P.items() if x['type'] in NEG]
cells = []
for lab, R in runs.items():
    k = sum(1 for i in ids_all if i in R and R[i].get('parsed') and R[i]['pick'] is not None)
    cells.append(fmt_ratio(k, len(ids_all)))
out.append(f'| **함정 전체 오지목** | {len(ids_all)} | ' + ' | '.join(cells) + ' |')
out.append('\n| 대조(정답 = 항목 하나) | 문장 수 | ' + ' | '.join(runs) + ' |')
out.append('|---|---:|' + '---|' * len(runs))
for c in POSC:
    ids = [i for i, x in P.items() if x['type'] == c]
    cells = []
    for lab, R in runs.items():
        k = sum(1 for i in ids if i in R and R[i].get('parsed') and R[i]['pick'] == P[i]['gold'])
        cells.append(f'{k}/{len(ids)} = {100 * k / len(ids):.1f}%')
    out.append(f'| {NAME[c]} | {len(ids)} | ' + ' | '.join(cells) + ' |')
ids_p = [i for i, x in P.items() if x['type'] in POSC]
cells, cells2, cells3 = [], [], []
for lab, R in runs.items():
    ok = wrong = none = same = 0
    for i in ids_p:
        r = R.get(i)
        if not r or not r.get('parsed'):
            continue
        if r['pick'] == P[i]['gold']:
            ok += 1
        elif r['pick'] is None:
            none += 1
        else:
            wrong += 1
            pr = P[i]['prompt']
            if place(line(pr, r['pick'])) == place(line(pr, P[i]['gold'])):
                same += 1
    cells.append(f'{ok}/{len(ids_p)} = {100 * ok / len(ids_p):.1f}%')
    cells2.append(f'{wrong}(같은 장소 다른 방문 {same}) · 없음 {none}')
    cells3.append(f'{100 * (ok + same) / len(ids_p):.1f}%')
out.append(f'| **대조 전체 정답 선택률** | {len(ids_p)} | ' + ' | '.join(cells) + ' |')
out.append(f'| 틀린 것: 다른 항목 · 없음으로 처리 | | ' + ' | '.join(cells2) + ' |')
out.append(f'| 같은 장소 다른 방문을 맞는 것으로 다시 세면 | | ' + ' | '.join(cells3) + ' |')
out.append('\n- 한계: 문장은 솔 6.1 이 쓰고 루나 6.0 이 라벨했다(둘 다 Codex 계열 · 사람 점검 없음). 일정 30개 · 문장은 일정마다 44개 안팎. 시드 · oos 모델당 1회. 합의하지 못한 64개(N1 32 · N6 13 · P2 10 · P3 7 · P1 2)는 사람 골든셋 후보로 따로 둔다. oos2 · oos3 는 학습이 끝난 뒤 같은 표에 이어 쓴다.')
out.append('- oos2r은 첫 잡담 보강 자료에 어려운 문장 900개를 더한 학습판이며, 별도 보류 세트 H로 평가합니다. 한 시드의 1회 측정이므로 반복 간 편차는 아직 확인하지 않았습니다.')
text = '\n'.join(out)
open(os.path.join(HERE, 'results', 'hard_report.md'), 'w', encoding='utf-8').write(text)
print(text)
