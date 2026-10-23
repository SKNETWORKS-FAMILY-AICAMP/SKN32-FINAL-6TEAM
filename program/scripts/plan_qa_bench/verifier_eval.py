# 「짧은 확인 질문」 검토자 모델들을 같은 입력 · 같은 정답으로 견준다 — 문턱 τ 를 정하지 않고 모델 자체의 가려내는 힘(AUROC)과 「맞은 답을 95·98·99% 남길 때 틀린 답을 몇 % 잡나」로 비교한다.
#  입력: results/d_test/verify_<이름>.jsonl (verify_llama.py 출력: key = "세트|문항번호|고른번호", p_yes 와 content) · 정답은 짚기 모델 결과 파일의 gold 에서 읽는다.
#  라벨: 고른 번호가 gold 와 같으면 「맞은 답」(YES 가 옳음), 다르면 「틀린 답」(NO 가 옳음). 틀린 답은 gold 가 「없음」(오지목)인 것과 다른 항목을 짚은 것으로 나눠 센다.
#  확률이 없는 모델(API · 구독 CLI)은 YES/NO 한 점만 있다 → 그 점의 (맞은 답 유지율, 틀린 답 잡는 율)만 적고 곡선 지표는 비운다.
#  세트: ALL(D · D2 · D3 전체) · D3(Claude 가 새로 쓴 합성 — 외부로 보내도 되는 유일한 세트). D · D2 의 AI Hub 문장은 외부 서비스에 보내지 않으므로 API 모델은 D3 로만 시험한다.
# 사용: python verifier_eval.py [이름=파일 …]  → results/verifier_eval.md   (인자 없으면 기본 목록)
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding='utf-8')
D = os.path.join(HERE, 'results', 'd_test')
SRC = {'D': 'd_test_lp_q4km_{}.jsonl', 'D2': 'd_test_lp_d2_q4km_{}.jsonl', 'D3': 'd_test_d3_q4km_{}.jsonl'}
TAGS = ['e4bt', 'e4bs2', 'e4bs3', 'oos1']


def jl(path):
    out = {}
    for line in open(path, encoding='utf-8'):
        r = json.loads(line)
        out[r.get('key', r.get('i'))] = r
    return out


gold = {}
for ds, pat in SRC.items():
    for t in TAGS:
        p = os.path.join(D, pat.format(t))
        if os.path.exists(p):
            for i, r in jl(p).items():
                gold[(ds, i)] = r['gold']


def label(key):
    ds, i, pick = key.split('|')
    g = gold.get((ds, int(i)))
    return ('ok' if g == int(pick) else ('fp' if g is None else 'wrong')), ds


def auroc(pos, neg):
    """pos = 맞은 답의 p_yes, neg = 틀린 답의 p_yes. P(pos > neg) + 0.5 P(=)."""
    if not pos or not neg:
        return None
    allv = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    # 순위합(동점은 평균 순위)
    ranks, i = {}, 0
    n = len(allv)
    rs = [0.0] * n
    while i < n:
        j = i
        while j + 1 < n and allv[j + 1][0] == allv[i][0]:
            j += 1
        for k in range(i, j + 1):
            rs[k] = (i + j) / 2 + 1
        i = j + 1
    sp = sum(r for r, (_, y) in zip(rs, allv) if y == 1)
    return (sp - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def tnr_at_tpr(pos, neg, tpr):
    """맞은 답의 tpr 비율 이상을 YES 로 남기는 가장 높은 문턱에서 틀린 답을 NO 로 잡는 비율."""
    if not pos or not neg:
        return None
    ps = sorted(pos)
    k = int((1 - tpr) * len(ps))  # 이만큼은 NO 로 잘려도 됨
    thr = ps[k]  # p_yes < thr 이면 NO
    return sum(1 for v in neg if v < thr) / len(neg)


def evaluate(name, path):
    V = jl(path)
    rows = {'ALL': {'ok': [], 'fp': [], 'wrong': []}, 'D3': {'ok': [], 'fp': [], 'wrong': []}}
    binary = {'ALL': [0, 0, 0, 0], 'D3': [0, 0, 0, 0]}  # YES|ok, NO|ok, NO|bad, YES|bad
    err = 0
    for key, r in V.items():
        if key not in {k for k in V}:
            continue
        lab, ds = label(key)
        p = r.get('p_yes')
        if p is None:
            # 확률이 없으면 content 의 YES/NO 로 0/1
            c = (r.get('content') or '').strip().upper()
            if c.startswith('YES'):
                p = 1.0
            elif c.startswith('NO'):
                p = 0.0
            else:
                err += 1
                continue
        for grp in ('ALL',) + (('D3',) if ds == 'D3' else ()):
            rows[grp][lab].append(p)
            b = binary[grp]
            yes = p >= 0.5
            if lab == 'ok':
                b[0 if yes else 1] += 1
            else:
                b[3 if yes else 2] += 1
    return rows, binary, err, len(V)


DEFAULT = {'FrogNano-4B(학습 없음)': 'verify_frog.jsonl', 'gemma4:12b(학습 없음)': 'verify_g12b.jsonl', 'Gemma-4 E4B QAT(학습 없음)': 'verify_e4bbase.jsonl', 'Gemma-4 E4B Q4_K_M(학습 없음)': 'verify_e4bq4km.jsonl'}
args = dict(a.split('=', 1) for a in sys.argv[1:]) if len(sys.argv) > 1 else DEFAULT
out = ['# 검토자(짧은 확인 질문) 모델 비교 — 문턱 없이 가려내는 힘\n',
       '입력은 짚기 모델 시드 1·2·3·oos1 이 D · D2 · D3 에서 항목을 골랐던 답(중복 제거)이다. 「맞은 답」 = 고른 항목이 정답, 「틀린 답」 = 정답이 「없음」인데 고른 것(오지목) 또는 다른 항목을 고른 것.',
       'AUROC = 맞은 답이 틀린 답보다 YES 확률이 높을 확률(0.5 = 구분 못 함, 1.0 = 완벽). TNR@TPR95 = 맞은 답의 95% 를 YES 로 남기는 문턱에서 틀린 답을 NO 로 잡는 비율.\n',
       '| 모델 | 세트 | 맞은 답 n | 틀린 답 n(오지목 · 다른 항목) | AUROC | 틀린 답 잡기 @맞은 답 95% 유지 | @98% | @99% | YES/NO 한 점(0.5): 맞은 답 유지 · 틀린 답 잡음 | 읽기 실패 |',
       '|---|---|---:|---|---:|---:|---:|---:|---|---:|']
for name, f in args.items():
    path = f if os.path.isabs(f) else os.path.join(D, f)
    if not os.path.exists(path):
        continue
    rows, binary, err, n = evaluate(name, path)
    for grp in ('ALL', 'D3'):
        ok = rows[grp]['ok']
        bad = rows[grp]['fp'] + rows[grp]['wrong']
        if not ok or not bad:
            continue
        a = auroc(ok, bad)
        t = [tnr_at_tpr(ok, bad, x) for x in (0.95, 0.98, 0.99)]
        b = binary[grp]
        # 확률이 0/1 뿐인 모델은 곡선 지표를 비운다
        two_valued = len(set(ok + bad)) <= 2
        def pc(x):
            return '—' if (x is None or two_valued) else f'{100 * x:.1f}%'
        out.append(f"| {name} | {grp} | {len(ok)} | {len(bad)}({len(rows[grp]['fp'])} · {len(rows[grp]['wrong'])}) | {'—' if two_valued else f'{a:.3f}'} | {pc(t[0])} | {pc(t[1])} | {pc(t[2])} | "
                   f"{100 * b[0] / max(1, b[0] + b[1]):.1f}% · {100 * b[2] / max(1, b[2] + b[3]):.1f}% | {err} |")
out.append('\n- 한계: 입력이 「짚기 모델이 실제로 고른 답」이라 시드 · oos1 이 쉽게 틀리는 유형에 치우친다. 라벨은 합성 문제의 gold 라 모호한 말은 틀린 답으로 셀 수 있다. 모델마다 1회 · 결정적 실행.')
text = '\n'.join(out)
open(os.path.join(HERE, 'results', 'verifier_eval.md'), 'w', encoding='utf-8').write(text)
print(text)
