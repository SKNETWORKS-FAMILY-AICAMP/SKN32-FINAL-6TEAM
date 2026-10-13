# 잡담 부정 사례를 더해 다시 가르친 짚기 모델(oos1·oos2·oos3)이 시드마다 갈리던 오지목을 줄였는지 — D · D2 · D3 에서 기존 시드 1·2·3(서비스 기반 Q4_K_M)과 같은 문항으로 견준다. 새 호출 없음.
#  성공 기준(시험 전에 적어 둔 것): ① 잡담 오지목의 시드 사이 범위(최대−최소)가 기존보다 좁아짐 ② 정답 있는 질문 정확도가 기존 평균보다 3%p 넘게 떨어지지 않음.
#  입력: results/d_test/d_test_lp_q4km_<태그>.jsonl(D) · d_test_lp_d2_q4km_<태그>.jsonl(D2) · d_test_d3_q4km_<태그>.jsonl(D3) — 서버 A llama.cpp, 서비스 기반 Q4_K_M. 파일이 있는 태그만 센다.
#  주의: oos 학습 자료는 D · D2 · D3 의 잡담과 문장이 겹치지 않게 따로 만든 것이다(build_train_oos.py 의 Jaccard 검사). 표본 1회 · 합성이다.
# 사용: python oos_report.py  → results/oos_report.md
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'eval_kit'))
from stats import fmt_ratio  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
D = os.path.join(HERE, 'results', 'd_test')
BASE = [('시드 1', 'e4bt'), ('시드 2', 'e4bs2'), ('시드 3', 'e4bs3')]
OOS = [('oos1', 'oos1'), ('oos2', 'oos2'), ('oos3', 'oos3')]
EXTRA = [('oos2r(어려운 문장 보강)', 'oos2r')]
FILES = {'D': 'd_test_lp_q4km_{}.jsonl', 'D2': 'd_test_lp_d2_q4km_{}.jsonl', 'D3': 'd_test_d3_q4km_{}.jsonl'}


def load(ds, tag):
    p = os.path.join(D, FILES[ds].format(tag))
    if not os.path.exists(p):
        return None
    d = {}
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        d[r['i']] = r
    return d


def metrics(ds, rows):
    """그룹 → (분자, 분모). 오지목은 정답이 「없음」인데 항목을 고른 것, 정답은 정답 있는 질문에서 정확히 맞춘 것. 읽기 실패(parsed 거짓)는 엄격하게 오답."""
    g = {}

    def add(name, hit, tot):
        a, b = g.get(name, (0, 0))
        g[name] = (a + hit, b + tot)
    for r in rows.values():
        t, gold = r['type'], r['gold']
        if t == 'compound_intent':
            continue
        pick = r.get('pick') if r.get('parsed') else None
        fp = gold is None and pick is not None
        ok = gold is not None and r.get('parsed') and pick == gold
        if ds == 'D':
            if t == 'chitchat':
                add('잡담 오지목', fp, 1)
            if t == 'tourist_synth_out':
                add('관광객 말 중 일정 밖 오지목', fp, 1)
            if gold is None:
                add('정답 없는 질문 전체 오지목', fp, 1)
            else:
                add('정답 있는 질문 정확도', ok, 1)
        elif ds == 'D2':
            add('새 잡담 오지목', fp, 1)
        else:
            if gold is None:
                add('합성 잡담 오지목', fp, 1)
            else:
                add('정답 있는 질문 정확도', ok, 1)
    return g


rows_by = {}
for ds in FILES:
    for label, tag in BASE + OOS + EXTRA:
        r = load(ds, tag)
        if r is not None:
            rows_by[(ds, label)] = metrics(ds, r)
labels = [l for l, _ in BASE + OOS + EXTRA if any((ds, l) in rows_by for ds in FILES)]
out = ['# 잡담 부정 사례를 더해 다시 가르친 짚기 모델(oos) 대 기존 시드 1·2·3 — D · D2 · D3 (서비스 기반 Q4_K_M, 생각 끔, 엄격 계수)\n']
verdict = []
for ds, groups in (('D', ['잡담 오지목', '관광객 말 중 일정 밖 오지목', '정답 없는 질문 전체 오지목', '정답 있는 질문 정확도']), ('D2', ['새 잡담 오지목']), ('D3', ['합성 잡담 오지목', '정답 있는 질문 정확도'])):
    have = [l for l in labels if (ds, l) in rows_by]
    if not have:
        continue
    out.append(f'\n## {ds}\n')
    out.append('| 지표 | ' + ' | '.join(have) + ' | 기존 시드 범위(최대−최소) | oos 범위 |')
    out.append('|---|' + '---|' * (len(have) + 2))
    for gname in groups:
        cells, bvals, ovals = [], [], []
        for l in have:
            a, b = rows_by[(ds, l)].get(gname, (0, 0))
            cells.append(fmt_ratio(a, b) if b else '—')
            if b and l in {label for label, _ in BASE + OOS}:
                (ovals if l in {label for label, _ in OOS} else bvals).append(100 * a / b)
        br = f'{max(bvals) - min(bvals):.1f}%p' if len(bvals) >= 2 else '—'
        orr = f'{max(ovals) - min(ovals):.1f}%p' if len(ovals) >= 2 else ('(1개)' if ovals else '—')
        out.append(f'| {gname} | ' + ' | '.join(cells) + f' | {br} | {orr} |')
        if 'accuracy' in gname or '정확도' in gname:
            if bvals and ovals:
                verdict.append(f'{ds} {gname}: 기존 평균 {sum(bvals) / len(bvals):.1f}% → oos 평균 {sum(ovals) / len(ovals):.1f}% ({sum(ovals) / len(ovals) - sum(bvals) / len(bvals):+.1f}%p)')
        else:
            if bvals and ovals:
                verdict.append(f'{ds} {gname}: 기존 평균 {sum(bvals) / len(bvals):.1f}% → oos 평균 {sum(ovals) / len(ovals):.1f}% ({sum(ovals) / len(ovals) - sum(bvals) / len(bvals):+.1f}%p)')
out.append('\n- oos2r은 어려운 문장 900개를 더한 별도 학습판이며 1개 시드입니다. oos 범위와 평균은 첫 잡담 보강판 oos1·oos2·oos3만 계산합니다.\n')
out.append('\n## 한 줄 요약(평균 비교)\n')
out += [f'- {v}' for v in verdict] or ['- (oos 결과 파일 없음)']
out.append('\n- 성공 기준: ① 잡담 오지목의 시드 사이 범위가 기존보다 좁아짐 ② 정답 있는 질문 정확도가 기존 평균보다 3%p 넘게 떨어지지 않음. oos 가 1개뿐이면 범위를 말하지 않는다(시드 한 개로 순위·일반화를 말하지 않는다).')
out.append('- 한계: 시드마다 1회 · 합성 문제 · 학습 자료와 문장이 겹치지 않게 만든 보류 세트(D2 · D3)가 일반화 값에 가깝고 D 는 학습 분포와 같은 합성 분포라 낙관적이다.')
text = '\n'.join(out)
open(os.path.join(HERE, 'results', 'oos_report.md'), 'w', encoding='utf-8').write(text)
print(text)
