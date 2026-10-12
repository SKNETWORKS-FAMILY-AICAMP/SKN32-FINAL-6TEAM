# 고객 메시지 분류(의도 · 감정 · 긴급도 · 대상) — 클래스별 정밀도(P) · 재현율(R) · F1 을 저장된 예측으로 센다.
#  시험 세트: CX 400(Codex 가 쓰고 Claude 가 정답 없이 교차 라벨, 어긋난 칸은 제외) · G96(서비스 평가 자료 golden 72 + holdout 24, Claude 초안 라벨 — 사람 검수 전).
#  비교 대상: 항상 다수 클래스를 찍는 기준선 · 학습 없는 LLM(Gemma-4 E4B 제로샷) · 학습 없는 Jev 계열 모델(Winnow-E4B · OpenDecider-small · OpenDecider-nano · Laya) · 우리 데이터로 학습한 분류 인코더(multilingual-e5-base, 서버 C 에 저장한 첫 시드 가중치).
#  예측 파일: results/_pull/cls/*.json (jev_cls_run.py · llm 분류 · cls_predict_saved.py 가 만든 것). 값이 없는 칸(마스크)은 정답이 불확실해 제외한다.
# 사용: python cls_prf.py → results/cls_prf_report.txt
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PULL = os.path.join(HERE, 'results', '_pull', 'cls')
FIX = os.path.join(HERE, 'fixtures', 'cls')
sys.stdout.reconfigure(encoding='utf-8')
HEADS = {'intent': ['itinerary_submit', 'incident_report', 'confirm_request', 'adjust_reject', 'other'],
         'sentiment': ['positive', 'neutral', 'negative'],
         'severity': ['low', 'medium', 'high', 'critical'],
         'case_type': ['activity', 'dining', 'mobility', 'booking', 'lodging', 'flight', 'other']}
HEAD_KO = {'intent': '요청 종류(의도)', 'sentiment': '감정', 'severity': '긴급도', 'case_type': '대상 종류'}
MODELS = [
    ('항상 다수 클래스(기준선)', None),
    ('학습 없는 LLM — Gemma-4 E4B 제로샷', 'llm_cls_gemma4_e4b-it-qat.json'),
    ('학습 없는 Jev 계열 모델 — Winnow-E4B(한국어 입력)', 'jev_cls_winnow_e4b_ko.json'),
    ('학습 없는 Jev 계열 모델 — OpenDecider-small(한국어 입력)', 'jev_cls_od_small_ko.json'),
    ('학습 없는 Jev 계열 모델 — Laya 다국어(한국어 입력)', 'jev_cls_laya_ml_ko.json'),
    ('학습 없는 Jev 계열 모델 — OpenDecider-nano(한국어 입력)', 'jev_cls_od_nano_ko.json'),
    ('우리 데이터로 학습한 분류 인코더 — multilingual-e5-base', 'cls_pred_e5base.json'),
]


def gold_rows(name):
    return [json.loads(l) for l in open(os.path.join(FIX, name), encoding='utf-8')]


def prf(gold, pred, labels):
    """gold/pred = 같은 길이의 라벨 목록 → ({라벨: (P, R, F1, 지원수)}, 정확도, 매크로 F1)"""
    out = {}
    n = len(gold)
    ok = sum(1 for g, p in zip(gold, pred) if g == p)
    for lab in labels:
        tp = sum(1 for g, p in zip(gold, pred) if g == lab and p == lab)
        fp = sum(1 for g, p in zip(gold, pred) if g != lab and p == lab)
        fn = sum(1 for g, p in zip(gold, pred) if g == lab and p != lab)
        sup = tp + fn
        P = tp / (tp + fp) if tp + fp else None
        R = tp / sup if sup else None
        F = (2 * P * R / (P + R)) if P and R else (0.0 if sup else None)
        out[lab] = (P, R, F, sup)
    fs = [v[2] for v in out.values() if v[3] and v[2] is not None]
    return out, ok / n if n else 0.0, (sum(fs) / len(fs) if fs else 0.0)


def f(x):
    return '—' if x is None else f'{x:.2f}'


def main():
    train = gold_rows('train.jsonl')
    for tname, tfile in (('CX 400', 'test_cx.jsonl'), ('G96', 'test_g96.jsonl')):
        rows = gold_rows(tfile)
        print(f'\n# 시험 세트 {tname} — {len(rows)}개 ' + ('(어긋난 칸 제외)' if tname == 'CX 400' else '(Claude 초안 라벨, 사람 검수 전)'))
        summ = []
        detail = {}
        for label, pfile in MODELS:
            if pfile is None:
                preds = None
            else:
                p = os.path.join(PULL, pfile)
                if not os.path.exists(p):
                    print(f'- {label}: 예측 파일이 없다({pfile}) — 건너뜀')
                    continue
                d = json.load(open(p, encoding='utf-8'))
                preds = {x['id']: x for x in d[tfile]['preds']}
            row_sum = {}
            for h, labs in HEADS.items():
                g, pr = [], []
                maj = collections.Counter(r[h] for r in train if r.get(h) in labs and not r.get('mask_' + h)).most_common(1)[0][0]
                for r in rows:
                    if r.get(h) not in labs or r.get('mask_' + h):
                        continue
                    g.append(r[h])
                    pr.append(maj if preds is None else (preds.get(r['id'], {}).get(h) if preds.get(r['id'], {}).get(h) in labs else None))
                res, acc, mf = prf(g, pr, labs)
                row_sum[h] = (acc, mf, len(g))
                detail[(label, h)] = res
            summ.append((label, row_sum))
        print('\n## 요약 — 정확도 / 매크로 F1(클래스 F1 의 평균, 지원수 0 인 클래스 제외)')
        print('| 모델 | ' + ' | '.join(HEAD_KO.values()) + ' |')
        print('|---|' + '---:|' * len(HEADS))
        for label, rs in summ:
            print(f'| {label} | ' + ' | '.join(f'{100 * rs[h][0]:.1f}% / {rs[h][1]:.2f}' for h in HEADS) + ' |')
        print(f'\n(칸의 표본 수: ' + ' · '.join(f'{HEAD_KO[h]} {summ[0][1][h][2]}' for h in HEADS) + ')')
        for h in HEADS:
            print(f'\n## {HEAD_KO[h]} — 클래스별 정밀도 / 재현율 / F1 (지원수 = 정답이 그 클래스인 질문 수)')
            labs = HEADS[h]
            sup = {l: next(iter(detail.values()))[h][l][3] if False else detail[(summ[0][0], h)][l][3] for l in labs}
            print('| 모델 | ' + ' | '.join(f'{l}(n={sup[l]})' for l in labs) + ' |')
            print('|---|' + '---:|' * len(labs))
            for label, _ in summ:
                r = detail[(label, h)]
                print(f'| {label} | ' + ' | '.join(f'{f(r[l][0])}/{f(r[l][1])}/{f(r[l][2])}' for l in labs) + ' |')


if __name__ == '__main__':
    main()
