# D3(합성 잡담 240[A 무관 120 · B 음식·장소·활동 잡담 120] + 정답 있는 질문 120)에서 Codex 솔 · FrogNano · 가르친 E4B 시드 3개(서비스 기반 Q4_K_M)의 오지목과 정답을 같은 문항으로 비교하고,
#  짚기 모델 + 거부권(FrogNano 또는 솔이 「없음」이면 거부)의 결합 값을 오프라인으로 계산한다. 새 호출 없음.
# 사용: python d3_report.py [솔 결과 파일 이름 접미: gpt-6.1-sol]   → results/d3_report.md
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding='utf-8')
SOL = sys.argv[1] if len(sys.argv) > 1 else 'gpt-6.1-sol'
D = os.path.join(HERE, 'results', 'd_test')


def load(path):
    d = {}
    for line in open(path, encoding='utf-8'):
        r = json.loads(line)
        d[r['i']] = r
    return d


models = {'가르친 E4B 시드 1': load(f'{D}/d_test_d3_q4km_e4bt.jsonl'), '가르친 E4B 시드 2': load(f'{D}/d_test_d3_q4km_e4bs2.jsonl'), '가르친 E4B 시드 3': load(f'{D}/d_test_d3_q4km_e4bs3.jsonl'),
          'FrogNano-4B(학습 없음)': load(f'{D}/d_test_d3_frog.jsonl'), f'Codex {SOL}(구독 CLI)': load(f'{D}/codex_d3_{SOL}.jsonl')}
ids = sorted(models['가르친 E4B 시드 1'])
typ = {i: models['가르친 E4B 시드 1'][i]['type'] for i in ids}
gold = {i: models['가르친 E4B 시드 1'][i]['gold'] for i in ids}
A = [i for i in ids if typ[i] == 'synth_chat_A']
B = [i for i in ids if typ[i] == 'synth_chat_B']
ANS = [i for i in ids if gold[i] is not None]


def pick(m, i):
    r = models[m].get(i)
    return None if (r is None or 'error' in r) else r.get('pick')


def err(m):
    return sum(1 for i in ids if models[m].get(i) is None or 'error' in models[m][i])


def pct(a, n):
    return f'{a}/{n} = {100 * a / n:.1f}%'


out = ['# D3 — 합성 잡담 240 + 정답 있는 질문 120 (Claude 작성 잡담 · AI Hub 문장 없음)\n',
       '| 모델 | A 무관한 잡담 오지목(120) | B 음식·장소·활동 잡담 오지목(120) | 잡담 전체 오지목(240) | 정답 있는 질문 정확도(120) | 호출 오류 |', '|---|---|---|---|---|---:|']
for m in models:
    fa = sum(1 for i in A if pick(m, i) is not None)
    fb = sum(1 for i in B if pick(m, i) is not None)
    ok = sum(1 for i in ANS if pick(m, i) == gold[i])
    out.append(f'| {m} | {pct(fa, 120)} | {pct(fb, 120)} | {pct(fa + fb, 240)} | {pct(ok, 120)} | {err(m)} |')
out.append('\n**거부권 결합**(짚기 모델이 항목을 골랐을 때 거부권 모델이 「없음」이면 「없음」)')
out.append('| 짚기 모델 | 거부권 | 잡담 오지목(240) | 정답 있는 질문(120) |')
out.append('|---|---|---|---|')
for s in ('가르친 E4B 시드 1', '가르친 E4B 시드 2', '가르친 E4B 시드 3'):
    for v in ('FrogNano-4B(학습 없음)', f'Codex {SOL}(구독 CLI)'):
        fin = lambda i: pick(s, i) if pick(v, i) is not None else None
        fp = sum(1 for i in A + B if fin(i) is not None)
        ok = sum(1 for i in ANS if fin(i) == gold[i])
        out.append(f'| {s} | {v} | {pct(fp, 240)} | {pct(ok, 120)} |')
out.append('\n- 표본이 작다(잡담 240 · 정답 있는 120, 모델당 1회, 합성 · Claude 작성). 솔은 구독 CLI 의 에이전트 세션을 거친 값이다(API 직접 호출과 다를 수 있다).')
text = '\n'.join(out)
open(os.path.join(HERE, 'results', 'd3_report.md'), 'w', encoding='utf-8').write(text)
print(text)
