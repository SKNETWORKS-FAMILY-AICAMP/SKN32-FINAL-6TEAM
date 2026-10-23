# 서버 B 에서 학습한 한국어(다국어) 인코더 13종 + 기준선(공개 감정 모델 · gemma4 LLM)을 표로 모은다.
#  입력: results/_pull/cls/cls_result_<모델>.json · zeroshot_sentiment.json · llm_cls_<모델>.json · fixtures/cls/agreement.json
# 사용: python cls_report.py > results/cls_report.txt  (그림은 research/figures_2026-10-06/make_figures7.py)
import glob, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding='utf-8')
R = os.path.join(HERE, 'results/_pull/cls')
HEADS = ['intent', 'sentiment', 'severity', 'case_type']
agree = json.load(open(os.path.join(HERE, 'fixtures/cls/agreement.json'), encoding='utf-8'))
cx_ceiling = agree['CX(시험: Codex 작성 · Claude 교차)']['agree']
print('# 한국어 분류 모델 비교 — 의도 · 감정 · 긴급도 · 대상 종류\n')
print('시험 CX 400 = Codex 가 쓰고 Claude 가 정답 없이 교차 라벨(어긋난 칸은 제외). 학습 자료 CL 720 은 Claude 작성·Codex 교차. 시드 3 평균(±표준편차).')
print('작성자·교차 라벨러 일치율(= 사람 둘의 일치에 대응하는 현실적 천장): ' + ' · '.join(f'{h} {100 * cx_ceiling[h]:.1f}%' for h in HEADS) + '\n')
rows = []
for f in sorted(glob.glob(os.path.join(R, 'cls_result_*.json'))):
    d = json.load(open(f, encoding='utf-8'))
    s = d['summary']
    rows.append((d['model'], d.get('params_M'), d.get('cpu_ms_median'), s))
rows.sort(key=lambda r: -np.mean([r[3]['cx'][h]['acc'][0] for h in HEADS]))
print(f'{"모델":<46}{"파라미터M":>9}{"CPU ms":>8} | ' + ' '.join(f'{h[:6]:>12}' for h in HEADS) + ' |  평균')
for name, p, ms, s in rows:
    cx = ' '.join(f"{100 * s['cx'][h]['acc'][0]:5.1f}±{100 * s['cx'][h]['acc'][1]:3.1f}%" for h in HEADS)
    avg = np.mean([s['cx'][h]['acc'][0] for h in HEADS]) * 100
    print(f'{name:<46}{p:>9}{ms:>8} | {cx} | {avg:5.1f}')
print('\n## 서비스 평가 자료 96(golden 72 + holdout 24, Claude 초안 라벨) — 두 번째 확인')
for name, p, ms, s in rows:
    g = ' '.join(f"{100 * s['g96'][h]['acc'][0]:5.1f}±{100 * s['g96'][h]['acc'][1]:3.1f}%" for h in HEADS)
    print(f'{name:<46} | {g}')
zs = os.path.join(R, 'zeroshot_sentiment.json')
if os.path.exists(zs):
    print('\n## 공개 감정 모델을 학습 없이(영점) 그대로 — 감정 3분류 정확도')
    for k, v in json.load(open(zs, encoding='utf-8')).items():
        if 'error' in v:
            continue
        print(f"{k:<62} CX {100 * v['test_cx.jsonl']['acc']:5.1f}% · G96 {100 * v['test_g96.jsonl']['acc']:5.1f}% (중립 문턱 {v['margin']})")
for pat, title in (('llm_cls_*.json', 'LLM 기준선(서비스 프롬프트 그대로)'), ('jev_cls_*.json', 'Jev 계열 결정 모델(학습 없음 · 질문 4개를 한 번에)')):
  for f in sorted(glob.glob(os.path.join(R, pat))):
    d = json.load(open(f, encoding='utf-8'))
    print(f'\n## {title} —', os.path.basename(f))
    for t, v in d.items():
        gold = {json.loads(l)['id']: json.loads(l) for l in open(os.path.join(HERE, 'fixtures/cls', t), encoding='utf-8')}
        res = {}
        for h in HEADS:
            ok = [p[h] == gold[p['id']][h] for p in v['preds'] if not gold[p['id']].get('mask_' + h)]
            res[h] = 100 * sum(ok) / len(ok)
        print(f"  {t}: " + ' · '.join(f'{h} {res[h]:.1f}%' for h in HEADS) + f" · 중앙 지연 {v['lat_median_s']:.1f}초/건 (n={v['n']})")
