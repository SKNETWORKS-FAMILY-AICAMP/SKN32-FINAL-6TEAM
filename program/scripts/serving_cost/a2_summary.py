# 오라클 무료 서버(dr-a2, 2코어 ARM)에서 잰 질문당 지연 · 메모리 기록(results/dr-a2/*.jsonl · *.mem.csv)을 요약한다.
#  구분: 새 일정 첫 질문(cold — 일정 접두를 처음 읽음) / 같은 일정 이어지는 질문(warm — 접두가 캐시에 있어 질문 부분만 읽음) / 일정 여러 개를 번갈아 묻기(interleave).
#  처리량 환산(잰 값으로 계산): 한 슬롯이 평균 서비스 시간 T = s×cold중앙 + (1−s)×warm중앙 로 일한다고 보고 1시간 3600/T 건. s = 새 일정 첫 질문 비율(사용 패턴을 몰라 0 · 10 · 30 · 100% 를 모두 보인다).
# 사용: python a2_summary.py  → results/a2_summary.md
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'eval_kit'))
sys.stdout.reconfigure(encoding='utf-8')
from stats import latency_summary  # noqa: E402

D = os.path.join(HERE, 'results', 'dr-a2')
CFG = [('q8', 1), ('q8', 2), ('q4', 1), ('q4', 2)]
NAME = {'q8': 'Q8_0(8.0GB)', 'q4': 'Q4_K_M(5.3GB, Q8 에서 다시 양자화)'}


def load(label, conc):
    p = os.path.join(D, f'{label}_np{conc}.jsonl')
    return [json.loads(l) for l in open(p, encoding='utf-8')] if os.path.exists(p) else []


def mem(label, conc):
    p = os.path.join(D, f'{label}_np{conc}.mem.csv')
    if not os.path.exists(p):
        return None
    rows = [l.strip().split(',') for l in open(p, encoding='utf-8')][1:]
    rows = [r for r in rows if len(r) == 4 and all(x for x in r)]
    if not rows:
        return None
    return {'hwm_gb': max(int(r[2]) for r in rows) / 1048576, 'min_avail_gb': min(int(r[3]) for r in rows) / 1048576, 'rss_gb': max(int(r[1]) for r in rows) / 1048576}


def f(ms):
    return f'{ms / 1000:.1f}'


out = ['# 오라클 무료 서버(dr-a2) — 가르친 E4B CPU 실행 측정 요약 (합성 프롬프트, 서버 안에서 생성)\n']
out.append('| 설정 | 새 일정 첫 질문(cold) n · 중앙 · p95 · 최대 (초) | 같은 일정 이어지는 질문(warm) n · 중앙 · p95 · 최대 (초) | 서버 메모리 최고(VmHWM) · 시험 중 시스템 여유 최저 | 읽기 속도(prompt) · 출력 속도 |')
out.append('|---|---|---|---|---|')
summ = {}
for label, conc in CFG:
    rows = [r for r in load(label, conc) if r['phase'] != 'warmup']
    if not rows:
        continue
    cold = [r['ms'] for r in rows if r['phase'] in ('main', 'extra_cold') and r['kind'] == 'cold']
    warm = [r['ms'] for r in rows if r['phase'] == 'main' and r['kind'] == 'warm']
    cs, ws = latency_summary(cold), latency_summary(warm)
    m = mem(label, conc)
    pp = [r['prompt_n'] / (r['prompt_ms'] / 1000) for r in rows if r['kind'] == 'cold' and r['prompt_ms'] and r['prompt_n'] and r['prompt_n'] > 1000]
    tg = [r['predicted_n'] / (r['predicted_ms'] / 1000) for r in rows if r['predicted_ms'] and r['predicted_n']]
    summ[(label, conc)] = {'cold': cs, 'warm': ws, 'mem': m, 'pp': sum(pp) / len(pp) if pp else None, 'tg': sum(tg) / len(tg) if tg else None, 'rows': rows}
    out.append(f"| {NAME[label]} · 슬롯 {conc}(동시 {conc}) | {cs['n']} · {f(cs['p50'])} · {f(cs['p95'])} · {f(cs['max'])} | {ws['n']} · {f(ws['p50'])} · {f(ws['p95'])} · {f(ws['max'])} | " +
               (f"{m['hwm_gb']:.1f}GB · {m['min_avail_gb']:.1f}GB" if m else '—') + f" | {summ[(label, conc)]['pp']:.1f} 토큰/초 · {summ[(label, conc)]['tg']:.1f} 토큰/초 |")
out.append('')
out.append('- 사용한 중앙값은 표본 수가 작아(cold 5~15, warm 76~95) 구간이 넓다. p95 는 표본이 59개 미만이면 사실상 최댓값 근처이니 cold 의 p95 는 참고만 한다(규칙: n≥59 에서 p95 상한 보장).')
# 섞어 묻기
for label, conc in CFG:
    if (label, conc) not in summ or conc != 1:
        continue
    il = [r for r in summ[(label, conc)]['rows'] if r['phase'] == 'interleave']
    if il:
        out.append(f'\n**일정 3개를 번갈아 묻기({NAME[label]}, 슬롯 1)** — 라운드별 질문당 시간(초): ' + ' · '.join(f"{r['kind']}/일정{r['itin']}={f(r['ms'])}(읽은 토큰 {r['prompt_n']}·캐시 {r['cache_n']})" for r in il))
# 처리량 환산
out.append('\n## 처리량 환산 (잰 중앙값으로 계산 — 슬롯 하나가 쉬지 않고 일한다고 본 상한)\n')
out.append('| 설정 | cold 비율 s | 평균 서비스 시간 (초/질문) | 시간당 | 하루 | 한 달(30일) | 이용률 50% 로 일할 때 한 달 |')
out.append('|---|---:|---:|---:|---:|---:|---:|')
for (label, conc), v in summ.items():
    if conc != 1 or not v['cold']['n'] or not v['warm']['n']:
        continue
    C, W = v['cold']['p50'] / 1000, v['warm']['p50'] / 1000
    for s in (0.0, 0.1, 0.3, 1.0):
        T = s * C + (1 - s) * W
        h = 3600 / T
        out.append(f"| {NAME[label]} | {int(s * 100)}% | {T:.1f} | {h:,.0f} | {h * 24:,.0f} | {h * 24 * 30:,.0f} | {h * 24 * 30 * 0.5:,.0f} |")
# 동시 2
out.append('\n## 동시 요청 2개 (슬롯 2) — 두 연결이 번갈아 같은 서버를 부를 때\n')
out.append('| 설정 | 완료 요청 수 | 걸린 시간(초) | 처리량(건/시간) | warm 중앙 (초) | 〃 슬롯 1 의 warm 중앙 대비 |')
out.append('|---|---:|---:|---:|---:|---:|')
for (label, conc), v in summ.items():
    if conc != 2:
        continue
    rows = [r for r in v['rows'] if r['phase'] == 'main']
    if not rows or 'ts' not in rows[0]:
        continue
    span = max(r['ts'] for r in rows) - (min(r['ts'] for r in rows) - rows[0]['ms'] / 1000)
    base = summ.get((label, 1))
    ratio = f"{v['warm']['p50'] / base['warm']['p50']:.2f}배" if base and base['warm']['n'] else '—'
    out.append(f"| {NAME[label]} | {len(rows)} | {span:.0f} | {len(rows) / span * 3600:,.0f} | {f(v['warm']['p50'])} | {ratio} |")
text = '\n'.join(out)
os.makedirs(os.path.join(HERE, 'results'), exist_ok=True)
open(os.path.join(HERE, 'results', 'a2_summary.md'), 'w', encoding='utf-8').write(text)
print(text)
