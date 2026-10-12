# 7차 그림 — 한국어 소형 분류 모델 비교(의도 · 감정 · 긴급도 · 대상 종류). 값은 results/_pull/cls/*.json 과 fixtures/cls/agreement.json 에서 읽는다(손으로 쓴 값 없음).
#  같은 모델을 8에폭 / 20에폭 두 설정으로 돌렸으면 개발 점수(dev_macro_f1)가 높은 쪽을 쓴다.
import glob
import json
import os
import re
import numpy as np
from make_figures import canvas, box, t, head, PAL, INK, SUB, LINE, OUT
from make_figures4 import reading_box, lines_height

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, '..', '..', 'scripts', 'plan_qa_bench')
R = os.path.join(S, 'results', '_pull', 'cls')
HEADS = ['intent', 'sentiment', 'severity', 'case_type']
HN = {'intent': '의도', 'sentiment': '감정', 'severity': '긴급도', 'case_type': '대상'}
agree = json.load(open(os.path.join(S, 'fixtures', 'cls', 'agreement.json'), encoding='utf-8'))['CX(시험: Codex 작성 · Claude 교차)']['agree']

best = {}
for f in glob.glob(os.path.join(R, 'cls_result_*.json')):
    d = json.load(open(f, encoding='utf-8'))
    base = re.sub(r'_e20$', '', d['model'])
    dev = float(np.mean([r['dev_macro_f1'] for r in d['runs']]))
    if base not in best or dev > best[base][0]:
        best[base] = (dev, d)
rows = []
for base, (dev, d) in best.items():
    s = d['summary']
    cx = [s['cx'][h]['acc'][0] for h in HEADS]
    g = [s['g96'][h]['acc'][0] for h in HEADS]
    rows.append({'name': base, 'cfg': f"{d['epochs']}에폭", 'params': d.get('params_M'), 'ms': d.get('cpu_ms_median'), 'cx': cx, 'g': g, 'avg': float(np.mean(cx)), 'gavg': float(np.mean(g))})
rows.sort(key=lambda r: -r['avg'])
SHORT = {'jhu-clsp/mmBERT-small': 'mmBERT-small (jhu-clsp, 2025-10)', 'jhu-clsp/mmBERT-base': 'mmBERT-base (jhu-clsp, 2025-10)', 'skt/A.X-Encoder-base': 'A.X-Encoder-base (SKT, 2026-01)',
         'intfloat/multilingual-e5-base': 'multilingual-e5-base', 'intfloat/multilingual-e5-small': 'multilingual-e5-small', 'BAAI/bge-m3': 'BGE-M3', 'klue/roberta-base': 'KLUE-RoBERTa-base',
         'klue/roberta-small': 'KLUE-RoBERTa-small', 'klue/roberta-large': 'KLUE-RoBERTa-large', 'FacebookAI/xlm-roberta-base': 'XLM-RoBERTa-base', 'beomi/KcELECTRA-base-v2022': 'KcELECTRA-base-v2022',
         'monologg/koelectra-base-v3-discriminator': 'KoELECTRA-base-v3', 'monologg/koelectra-small-v3-discriminator': 'KoELECTRA-small-v3'}

# 기준선: 서비스가 지금 쓰는 방식(LLM + 서비스 프롬프트)과 공개 감정 모델 영점
llm = {}
for f in glob.glob(os.path.join(R, 'llm_cls_*.json')):
    d = json.load(open(f, encoding='utf-8'))
    for tname, v in d.items():
        gold = {json.loads(l)['id']: json.loads(l) for l in open(os.path.join(S, 'fixtures', 'cls', tname), encoding='utf-8')}
        res = []
        for h in HEADS:
            ok = [p[h] == gold[p['id']][h] for p in v['preds'] if not gold[p['id']].get('mask_' + h)]
            res.append(sum(ok) / len(ok))
        llm.setdefault(os.path.basename(f), {})[tname] = (res, v['lat_median_s'])
zs = json.load(open(os.path.join(R, 'zeroshot_sentiment.json'), encoding='utf-8')) if os.path.exists(os.path.join(R, 'zeroshot_sentiment.json')) else {}


def tone(v):
    return 'now' if v >= 0.92 else ('warn' if v >= 0.85 else 'bad')


def fig28():
    n_llm = sum(len(v) for v in llm.values())
    reading = ['시험 CX 400문제는 Codex 가 쓰고 Claude 가 정답 없이 교차 라벨했다. 학습 자료 720문제는 반대(Claude 작성 · Codex 교차) — 출제자가 학습과 시험에서 다르다. 점수는 두 라벨러가 일치한 칸만 센다(사람 둘의 일치율에 해당하는 천장은 표 맨 아래).',
               '상위 인코더는 의도 96~98% · 감정 92~95% · 대상 89~95%이고 긴급도가 가장 어렵다(87~91% — 라벨러끼리도 88% 일치). CPU 한 건은 9~120ms 라 GPU 도 LLM 호출도 필요 없다. 상위 셋(BGE-M3 · e5-base · XLM-R-base)은 오차 범위 안이라 구분되지 않는다.',
               '같은 모델도 에폭 8 로는 덜 배운다 — ELECTRA 계열·e5-small 은 「대상 종류」가 37~56% 였다가 에폭 20 으로 81~92%. 표는 개발 점수가 높은 설정 하나만 보인다. 다국어 모델(e5·XLM-R·BGE-M3·mmBERT)은 영어·일본어·중국어 메시지도 같은 모델로 받는다.',
               '비교: 공개 감정 모델 영점 최고 71%(tabularisai, 비상업 라이선스) · 서비스 프롬프트 그대로 gemma4 E4B(학습 없음, 5.3초/건)는 의도 97 · 감정 84 · 긴급도 61 · 대상 86 — 학습한 인코더가 감정·긴급도·대상에서 크게 앞선다(LLM 은 우리 자료로 학습하지 않은 값). 서비스 평가 96 은 Claude 초안 라벨이라 긴급도 기준이 달라 점수가 낮다.']
    top = rows[:14]
    H = 200 + (len(top) + 4) * 66 + lines_height(reading, 72, 28) + 90
    fig, ax = canvas(H)
    head(ax, '한국어 소형 분류 모델 비교 — 오늘 기준', '의도·감정·긴급도·대상 종류 · 시험 CX 400(출제자 다름) 정확도 · 인코더 학습은 시드 3 평균')
    xs = [40, 410, 500, 585, 665, 745, 825, 905, 985]
    for x, lab in zip(xs, ['모델', '파라미터M', 'CPU ms', '의도', '감정', '긴급도', '대상', '평균', '서비스96']):
        t(ax, x if x == 40 else x + 0, 170, lab, 12, SUB, True, 'left' if x == 40 else 'center')
    y = 188
    for r in top:
        box(ax, 30, y, 1020, 58, 'plain', 8, 1.2)
        t(ax, 42, y + 22, SHORT.get(r['name'], r['name']), 12.6, INK, True)
        t(ax, 42, y + 44, f"설정 {r['cfg']}", 10, SUB)
        t(ax, xs[1], y + 29, f"{r['params']:.0f}", 12.4, INK, False, 'center')
        t(ax, xs[2], y + 29, f"{r['ms']:.0f}", 12.4, INK, False, 'center')
        for x, v in zip(xs[3:7], r['cx']):
            box(ax, x - 31, y + 8, 62, 42, tone(v), 6, 1.4)
            t(ax, x, y + 29, f'{100 * v:.1f}', 13, PAL[tone(v)][2], True, 'center')
        box(ax, xs[7] - 31, y + 8, 62, 42, tone(r['avg']), 6, 2)
        t(ax, xs[7], y + 29, f"{100 * r['avg']:.1f}", 13.4, PAL[tone(r['avg'])][2], True, 'center')
        t(ax, xs[8], y + 29, f"{100 * r['gavg']:.1f}", 12.4, SUB, False, 'center')
        y += 66
    # 기준선 행
    box(ax, 30, y, 1020, 58, 'plain', 8, 1.2)
    t(ax, 42, y + 22, '공개 감정 모델 영점(학습 없이) 최고', 12.6, INK, True)
    best_zs = max(((v['test_cx.jsonl']['acc'], k) for k, v in zs.items() if 'error' not in v), default=None)
    if best_zs:
        t(ax, 42, y + 44, best_zs[1].split('/')[-1][:46], 10, SUB)
        box(ax, xs[4] - 31, y + 8, 62, 42, tone(best_zs[0]), 6, 1.4)
        t(ax, xs[4], y + 29, f'{100 * best_zs[0]:.1f}', 13, PAL[tone(best_zs[0])][2], True, 'center')
        t(ax, xs[3], y + 29, '—', 12, SUB, False, 'center')
        t(ax, xs[5], y + 29, '—', 12, SUB, False, 'center')
        t(ax, xs[6], y + 29, '—', 12, SUB, False, 'center')
    y += 66
    for key, v in llm.items():
        cx = v.get('test_cx.jsonl')
        g96 = v.get('test_g96.jsonl')
        box(ax, 30, y, 1020, 58, 'plain', 8, 1.2)
        t(ax, 42, y + 22, 'LLM(서비스 프롬프트 그대로) — ' + key.replace('llm_cls_', '').replace('.json', '').replace('_', ':', 1), 12, INK, True)
        t(ax, 42, y + 44, f"중앙 지연 {(cx or g96)[1]:.1f}초/건 (서버 A GPU)", 10, SUB)
        if cx:
            for x, val in zip(xs[3:7], cx[0]):
                box(ax, x - 31, y + 8, 62, 42, tone(val), 6, 1.4)
                t(ax, x, y + 29, f'{100 * val:.1f}', 13, PAL[tone(val)][2], True, 'center')
            t(ax, xs[7], y + 29, f'{100 * np.mean(cx[0]):.1f}', 13, INK, True, 'center')
        if g96:
            t(ax, xs[8], y + 29, f'{100 * np.mean(g96[0]):.1f}', 12.4, SUB, False, 'center')
        y += 66
    box(ax, 30, y, 1020, 58, 'gpu', 8, 1.4)
    t(ax, 42, y + 22, '라벨러끼리 일치율(= 사람 둘의 일치에 해당하는 천장)', 12, PAL['gpu'][2], True)
    t(ax, 42, y + 44, 'CX 400 · 모델 점수는 일치한 칸만 센다', 10, PAL['gpu'][2])
    for x, h in zip(xs[3:7], HEADS):
        t(ax, x, y + 29, f'{100 * agree[h]:.1f}', 13, PAL['gpu'][2], True, 'center')
    y += 74
    y_end = reading_box(ax, y, '읽는 법', reading, 'gpu', 72, 12, 28)
    fig.set_size_inches(10.8, (y_end + 10) / 100)
    ax.set_ylim(y_end + 10, 0)
    fig.savefig(os.path.join(OUT, 'fig28_한국어_분류_모델_비교.png'))


if __name__ == '__main__':
    fig28()
    print('ok', len(rows), '모델')
