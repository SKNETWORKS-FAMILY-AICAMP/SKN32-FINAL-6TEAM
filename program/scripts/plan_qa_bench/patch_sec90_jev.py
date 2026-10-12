# 정본 문서 §90-4(Jev 계열 분류 영점 시험) 를 results/_pull/cls/jev_cls_*.json 의 값으로 다시 쓴다 — 표의 숫자는 파일에서 세어 넣는다(손으로 쓰지 않는다).
# 사용: python patch_sec90_jev.py   (문서는 results/_backup/ 에 먼저 복사한다)
import glob
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DOC = os.path.join(HERE, '..', '..', 'research', '여행일정_질문인식_모델비교_2026-09-29.md')
R = os.path.join(HERE, 'results', '_pull', 'cls')
HEADS = ['intent', 'sentiment', 'severity', 'case_type']
NAMES = [('laya_ml_en', 'Laya 다국어(인코더형 약 0.3B) · 영어 설명'), ('laya_ml_ko', 'Laya 다국어(인코더형) · 한국어 설명'),
         ('od_nano_en', 'OpenDecider-nano(인코더형 약 0.4B, 다른 세션 기록) · 영어 설명'), ('od_nano_ko', 'OpenDecider-nano · 한국어 설명'),
         ('od_small_en', 'OpenDecider-small(LLM형 4B) · 영어 설명'), ('od_small_ko', 'OpenDecider-small(LLM형 4B) · 한국어 설명'),
         ('winnow_e4b_en', 'Winnow-E4B(LLM형 유효 4B) · 영어 설명'), ('winnow_e4b_ko', 'Winnow-E4B(LLM형 유효 4B) · 한국어 설명')]
gold = {json.loads(l)['id']: json.loads(l) for l in open(os.path.join(HERE, 'fixtures', 'cls', 'test_cx.jsonl'), encoding='utf-8')}


def row(tag):
    f = os.path.join(R, f'jev_cls_{tag}.json')
    if not os.path.exists(f):
        return None
    v = json.load(open(f, encoding='utf-8')).get('test_cx.jsonl')
    if not v or v.get('errors'):
        return None
    acc = []
    for h in HEADS:
        ok = [p[h] == gold[p['id']][h] for p in v['preds'] if not gold[p['id']].get('mask_' + h)]
        acc.append(100 * sum(ok) / len(ok))
    return acc, v['lat_median_s']


lines = ['| 방법 | 의도 | 감정 | 긴급도 | 대상 | 건당(서버 A GPU, 질문 4개) |', '|---|---:|---:|---:|---:|---|',
         '| (기준) 한 라벨만 계속 찍기 | 27.4 | 62.0 | 47.0 | 26.6 | — |']
res = {}
for tag, name in NAMES:
    r = row(tag)
    res[tag] = r
    if r is None:
        lines.append(f'| {name} | — | — | — | — | 결과 없음 |')
    else:
        acc, lat = r
        lines.append(f'| {name} | ' + ' | '.join(f'{a:.1f}' for a in acc) + f' | {lat * 1000:.0f}ms |')
lines += ['| (비교) 학습한 인코더 최고 | 98.2 | 94.8 | 90.6 | 95.4 | CPU 35~120ms |', '| (비교) gemma4 E4B QAT 서비스 프롬프트(학습 없음) | 97.2 | 83.9 | 60.9 | 86.2 | 5.3초 |']
table = '\n'.join(lines)
missing = [t for t, r in res.items() if r is None]
if missing:
    print('결과가 없는 행:', missing)

w_ko, w_en = res.get('winnow_e4b_ko'), res.get('winnow_e4b_en')
o_ko, o_en = res.get('od_small_ko'), res.get('od_small_en')


def f(r, i):
    return f'{r[0][i]:.1f}' if r else '—'


block = f'''### 90-4. Jev 계열 소형 결정 모델 (학습 없음) — 같은 시험, 질문 4개를 한 번에 `[실측 2026-10-06, 각 1회(결정적 출력이라 반복 없음)]`
- **왜 넣나**: 사용자 구상(「규칙 → ML → Jev 분류 → 임베딩 또는 분야별 소형 LLM」)의 Jev 분류 칸이 일정 항목 짚기에서만 재졌고 분류 과제 점수는 비어 있었다(§50-1 · §52-1 기록: 이 모델들은 선택지가 고정된 분류용). 기록에 있던 영어 공개 과제 점수(감성 91~94 · 뉴스 86~91)는 다른 세션 측정이고 우리 한국어 여행 분류에서는 처음 잰다.
- **방법**: [`server/jev_cls_run.py`](../scripts/plan_qa_bench/server/jev_cls_run.py) — 한 메시지에 질문 네 개(의도·감정·긴급도·대상)를 한 번에 보내고 선택지 설명(criteria)은 서비스 라벨 정의를 한국어판·영어판으로 한 번씩 줬다. 우리 학습 자료는 주지 않았다. 점수 계산은 학습한 인코더와 같다(두 라벨러가 일치한 칸만, CX 400). 표는 [`patch_sec90_jev.py`](../scripts/plan_qa_bench/patch_sec90_jev.py) 가 결과 파일에서 세어 넣었다.
{table}
- **읽기 — 「Jev 계열」을 한 덩어리로 말하면 안 된다. 인코더형과 LLM형이 갈린다.**
  - **인코더형**(Laya · OpenDecider-nano)은 한 라벨만 찍는 값에 가깝다(긴급도는 기준 47.0 이하 · 감정은 기준 62.0 보다 1~19%p 위). 우리 한국어 여행 분류에는 쓸 수 없다.
  - **LLM형**(Winnow-E4B 유효 4B · OpenDecider-small 4B)은 학습 없이도 한국어 설명으로 의도 {f(w_ko,0)}/{f(o_ko,0)} · 감정 {f(w_ko,1)}/{f(o_ko,1)} · 대상 {f(w_ko,3)}/{f(o_ko,3)} (Winnow / OpenDecider-small) 로, 학습한 인코더(98.2 · 94.8 · 95.4)와의 차이는 Winnow 가 3~4%p · OpenDecider-small 이 3~8%p 다. 서비스 프롬프트 그대로의 gemma4 E4B(학습 없음, 5.3초)보다 감정·대상이 높고 의도는 낮다. 건당 약 0.3~0.4초로 5.3초보다 훨씬 빠르다(서버 A GPU, 다른 작업이 겹친 때는 1.8초까지 느려졌다).
  - **긴급도는 어느 쪽도 어렵다**: LLM형 {f(w_ko,2)}/{f(o_ko,2)} 로 학습한 인코더 90.6 에 25%p 이상 못 미친다. 긴급도는 이 서비스 고유의 기준(「지금~1~2시간 안 일정에 지장」)이라 설명 문구만으로는 배우기 어렵다고 읽는다 `[추정]`.
  - 영어 설명이 늘 낫지는 않다 — 한국어 설명이 대체로 같거나 높다(Winnow 대상 {f(w_ko,3)} 대 영어 {f(w_en,3)}, OpenDecider-small 대상 {f(o_ko,3)} 대 영어 {f(o_en,3)}). 모델마다 설명 문구 한 가지씩만 써 봤다.
  - **조건이 같지 않다**: 서비스 프롬프트 E4B 는 한 번의 JSON 출력, Jev 계열은 질문 4개를 한 번에 푸는 전용 입출력이다. Winnow-E4B 의 저자 학습 자료와 시험 문장이 겹쳤는지는 모른다 `[미확인]`.
- **아직 못 한 것**: ① Laya·OpenDecider·Winnow 를 우리 720문제로 **학습**시키는 길은 시험하지 않았다 `[미시험]` — 특히 LLM형의 긴급도가 학습으로 따라오는지가 다음 질문이다 ② 선택지 설명 문구를 바꿔 보는 탐색은 하지 않았다(한계: 점수는 이 문구에서의 값이다) ③ CPU 단독 속도는 안 쟀다 — Winnow-E4B Q8(8GB)·OpenDecider-small(4B)은 GPU 에서만 쟀다.
- **실행 중 겪은 일**:
  1. 서버 A 에서 CPU 로 돌린 첫 시도는 30분 넘게 첫 결과가 나오지 않았다 — ① 서버 A 의 `/workspace`(네트워크 디스크)에서 `transformers` 를 불러오는 데만 수 분씩 걸림(파이썬 `faulthandler` 로 확인) → 컨테이너 로컬 디스크(`/tmp`)에 환경을 새로 만들어 해결 ② 코어 64개에 다른 작업이 겹쳐 스레드 경쟁(부하 평균 40~90) → 스레드 8 개로 제한해도 건당 6.3초 → 서버 A GPU 의 남는 자리(약 6.5GB)로 옮기니 건당 0.07~0.2초.
  2. Winnow-E4B 첫 시도는 **서버 응답 503 으로 496건 전부 오류**였다 — OpenJev 회전 시험이 GPU 를 9.8GB 쓰고 있어 모델(8GB)을 올릴 자리가 없었다. 그 결과 파일은 점수로 쓰지 않고 `_failed` 로 치웠다(서버 A `/workspace/heavy/cls/_failed/`). OpenJev 회전 시험의 남은 5건(회전 21 mix12·mix10, 회전 32 세 세트)은 멈추고, 분류 시험 뒤에 이어서 돌리도록 대기열에 다시 걸었다.
  3. OpenDecider-small 첫 시도는 `peft` 패키지가 없어 멈췄고(설치), 두 번째 시도는 **서버 A 디스크 한도(약 80GB)** 에 걸려 기반 모델(약 8GB)을 못 받았다. 다시 받을 수 있는 OpenJev 파일(19GB)만 지우고 받았다. 회전 시험을 이어갈 때 OpenJev 를 다시 받는다.

'''
shutil.copy(DOC, os.path.join(HERE, 'results', '_backup', time.strftime('%Y-%m-%d_%H%M') + '_doc_before_sec90_jev_patch.md'))
t = open(DOC, encoding='utf-8').read()
a = t.index('### 90-4.')
b = t.index('### 90-5.')
t = t[:a] + block + t[b:]
t = t.replace('Jev 계열 소형 모델(Laya · OpenDecider-nano)까지 반영 — OpenDecider-small · Winnow-E4B 는 대기]', 'Jev 계열(Laya · OpenDecider nano/small · Winnow-E4B)까지 반영]')
open(DOC, 'w', encoding='utf-8').write(t)
print('문서 갱신 끝 — 행', len(NAMES), '· 결과 없음', len(missing))
sys.stdout.reconfigure(encoding='utf-8')
