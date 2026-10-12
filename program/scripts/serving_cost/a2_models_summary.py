# 오라클 무료 서버(dr-a2, 2코어 ARM · 12GB)에서 모델별로 잰 질문당 지연 · 메모리를 한 표로 요약한다 (2026-10-07).
#  입력: results/dr-a2/<이름>_np1.jsonl · .mem.csv — 같은 합성 프롬프트(약 1,900토큰 일정 접두 + 짧은 질문, 서버 안에서 생성)로 모델만 바꿔 잰 값.
#  cold = 새 일정의 첫 질문(일정 접두를 처음 읽음), warm = 같은 일정의 이어지는 질문(접두가 캐시에 있음).
#  짧은 확인 질문(거부권 검토, 약 150토큰)의 시간은 「읽기 속도」로 환산한 예상이다 — 잰 값이 아니다.
# 사용: python a2_models_summary.py  → results/a2_models_summary.md
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'eval_kit'))
sys.stdout.reconfigure(encoding='utf-8')
from stats import latency_summary  # noqa: E402

D = os.path.join(HERE, 'results', 'dr-a2')
# (파일 이름표, 화면 이름, 하는 일)
MODELS = [
    ('q8', '가르친 E4B · Q8_0(8.0GB)', '짚기'),
    ('q4', '가르친 E4B · Q4_K_M(5.3GB, Q8 에서 다시 양자화)', '짚기'),
    ('e4b_qat_q40', 'E4B QAT Q4_0(공식 양자화 학습판)', '짚기 기반'),
    ('e2b_q8', 'Gemma-4 E2B · Q8_0(학습 없음)', '작은 대안'),
    ('e2b_qat_q40', 'Gemma-4 E2B QAT Q4_0(학습 없음)', '작은 대안'),
    ('frog4b_q8', 'FrogNano-4B · Q8_0(학습 없음)', '검토'),
    ('g12b_q4km', 'Gemma-4 12B · Q4_K_M(학습 없음)', '검토(서비스에 이미 있음)'),
    ('kanana2_3b_q8', 'Kanana-2 3B · Q8_0(학습 없음)', '작은 대안'),
    ('exaone40_12b_q8', 'EXAONE-4.0 1.2B · Q8_0(학습 없음)', '작은 대안'),
]
SHORT_TOKENS = 150  # 짧은 확인 질문의 읽을 토큰(건당 약 150토큰, §92-20 실측)


def load(label):
    p = os.path.join(D, f'{label}_np1.jsonl')
    return [json.loads(x) for x in open(p, encoding='utf-8')] if os.path.exists(p) else []


def mem(label):
    p = os.path.join(D, f'{label}_np1.mem.csv')
    if not os.path.exists(p):
        return None
    rows = [x.strip().split(',') for x in open(p, encoding='utf-8')][1:]
    rows = [r for r in rows if len(r) == 4 and all(v for v in r)]
    if not rows:
        return None
    return {'hwm': max(int(r[2]) for r in rows) / 1048576, 'avail': min(int(r[3]) for r in rows) / 1048576}


def f(ms):
    return f'{ms / 1000:.1f}'


out = ['# 오라클 무료 서버(dr-a2, 2코어 ARM · 12GB) — 모델별 서빙 감당량 (합성 프롬프트, 슬롯 1)\n']
out.append('같은 짚기 프롬프트(일정 접두 약 1,900토큰 + 질문)로 모델만 바꿔 잰 값이다. 비교 모델은 가르치지 않은 원본이라 **지연·메모리만** 보고, 정확도는 비교하지 않는다.\n')
out.append('| 모델 | 하는 일 | cold n · 중앙 · 최대 (초) | warm n · 중앙 · p95 · 최대 (초) | 메모리 최고 · 시스템 여유 최저 | 읽기 · 출력 (토큰/초) |')
out.append('|---|---|---|---|---|---|')
summ = {}
for label, name, role in MODELS:
    rows = [r for r in load(label) if r['phase'] != 'warmup']
    if not rows:
        continue
    cold = [r['ms'] for r in rows if r['phase'] in ('main', 'extra_cold') and r['kind'] == 'cold']
    warm = [r['ms'] for r in rows if r['phase'] == 'main' and r['kind'] == 'warm']
    cs = latency_summary(cold) if cold else None
    ws = latency_summary(warm) if warm else None
    m = mem(label)
    pp = [r['prompt_n'] / (r['prompt_ms'] / 1000) for r in rows if r['kind'] == 'cold' and r['prompt_ms'] and r['prompt_n'] and r['prompt_n'] > 1000]
    tg = [r['predicted_n'] / (r['predicted_ms'] / 1000) for r in rows if r['predicted_ms'] and r['predicted_n']]
    s = {'cold': cs, 'warm': ws, 'mem': m, 'pp': sum(pp) / len(pp) if pp else None, 'tg': sum(tg) / len(tg) if tg else None, 'name': name}
    summ[label] = s
    cstr = f"{cs['n']} · {f(cs['p50'])} · {f(cs['max'])}" if cs else '—'
    wstr = f"{ws['n']} · {f(ws['p50'])} · {f(ws['p95'])} · {f(ws['max'])}" if ws else '—'
    mstr = f"{m['hwm']:.1f}GB · {m['avail']:.1f}GB" if m else '—'
    pstr = f"{s['pp']:.1f} · {s['tg']:.1f}" if s['pp'] and s['tg'] else '—'
    out.append(f'| {name} | {role} | {cstr} | {wstr} | {mstr} | {pstr} |')
out.append('')
out.append('- 표본이 작다: cold 는 2~10건, warm 은 12~95건이다. 12B 는 한 건이 cold 7분·warm 27초라 표본을 줄였다. p95 는 표본이 59건 미만이면 사실상 최댓값 근처다.')
out.append('- 시스템 여유 최저가 1~2GB 이하면 다른 일을 같이 돌릴 수 없고, 메모리 부족으로 죽을 위험이 있다는 뜻이다.')
out.append('\n## 처리량 환산 (잰 중앙값으로 계산 — 슬롯 하나가 쉬지 않고 일한다고 본 상한)\n')
out.append('s = 새 일정 첫 질문(cold) 비율. 사용 패턴을 몰라 0 · 10 · 30 · 100% 를 모두 적는다. 평균 서비스 시간 T = s×cold중앙 + (1−s)×warm중앙.\n')
out.append('| 모델 | s=0% 시간당 | s=10% 시간당 | s=30% 시간당 | s=100% 시간당 |')
out.append('|---|---:|---:|---:|---:|')
for label, name, role in MODELS:
    v = summ.get(label)
    if not v or not v['cold'] or not v['warm']:
        continue
    C, W = v['cold']['p50'] / 1000, v['warm']['p50'] / 1000
    cells = []
    for s in (0.0, 0.1, 0.3, 1.0):
        T = s * C + (1 - s) * W
        cells.append(f'{3600 / T:,.0f}')
    out.append(f"| {name} | " + ' | '.join(cells) + ' |')
out.append('\n## 짧은 확인 질문(거부권 검토)으로 쓸 때 — **예상**(읽기 속도로 환산, 잰 값 아님)\n')
out.append(f'한 건 약 {SHORT_TOKENS}토큰을 읽고 YES/NO 한 단어를 낸다고 보고 `{SHORT_TOKENS} ÷ 읽기 속도 + 1 ÷ 출력 속도` 로 계산했다. 접두 캐시가 약한 모델은 이 값이 그대로 건당 시간이다.\n')
out.append('| 모델 | 읽기 속도 | 건당 예상 시간(초) | 시간당 예상 건수(1슬롯) |')
out.append('|---|---:|---:|---:|')
for label, name, role in MODELS:
    v = summ.get(label)
    if not v or not v['pp'] or not v['tg']:
        continue
    t = SHORT_TOKENS / v['pp'] + 1 / v['tg']
    out.append(f"| {name} | {v['pp']:.1f} 토큰/초 | {t:.1f} | {3600 / t:,.0f} |")

# 임베딩
emb = os.path.join(D, 'bge_m3_q8_embed.json')
if os.path.exists(emb):
    e = json.load(open(emb, encoding='utf-8'))
    out.append('\n## 임베딩 모델 bge-m3(Q8_0, 0.6GB) — 2코어 ARM\n')
    out.append('| 입력 | 호출 수 | 건당 평균(초) | 호출 중앙(초) | 토큰/초 |')
    out.append('|---|---:|---:|---:|---:|')
    for k, v in e.items():
        if k == 'model':
            continue
        out.append(f"| {k} | {v['호출 수']} | {v['건당 평균 초']} | {v['호출 중앙 초']} | {v['토큰/초']} |")
text = '\n'.join(out)
open(os.path.join(HERE, 'results', 'a2_models_summary.md'), 'w', encoding='utf-8').write(text)
print(text)
