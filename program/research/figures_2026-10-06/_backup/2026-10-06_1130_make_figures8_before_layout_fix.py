# 8차 그림 — 「모델 조합」 5단계(규칙 → ML → Jev 분류 → 임베딩 분류 · 소형 LLM)에서 단계마다 잰 값과 비어 있는 곳.
#  값은 기록 문서의 숫자(절 번호를 칸에 적음)와 results/_pull/cls/ 의 결과에서 읽는다. Jev 분류 칸은 jev_cls_*.json 이 있을 때만 채운다.
import glob
import json
import os
import numpy as np
from make_figures import canvas, box, t, head, PAL, INK, SUB, LINE, OUT
from make_figures4 import lines_height

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, '..', '..', 'scripts', 'plan_qa_bench')
R = os.path.join(S, 'results', '_pull', 'cls')
HEADS = ['intent', 'sentiment', 'severity', 'case_type']
SHORT = {'intent': '의도', 'sentiment': '감정', 'severity': '긴급도', 'case_type': '대상'}


def jev_rows():
    """jev_cls_*.json → {태그: ([4머리 정확도 CX], 중앙 지연 초)} (두 교차 라벨러가 일치한 칸만 센다)"""
    out = {}
    for f in sorted(glob.glob(os.path.join(R, 'jev_cls_*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        v = d.get('test_cx.jsonl')
        if not v:
            continue
        gold = {json.loads(l)['id']: json.loads(l) for l in open(os.path.join(S, 'fixtures', 'cls', 'test_cx.jsonl'), encoding='utf-8')}
        res = []
        for h in HEADS:
            ok = [p[h] == gold[p['id']][h] for p in v['preds'] if not gold[p['id']].get('mask_' + h)]
            res.append(sum(ok) / len(ok))
        out[os.path.basename(f).replace('jev_cls_', '').replace('.json', '')] = (res, v['lat_median_s'])
    return out


def tone(v):
    return 'now' if v >= 0.92 else ('warn' if v >= 0.85 else 'bad')


def fig29():
    jev = jev_rows()
    best_enc = [0.982, 0.948, 0.906, 0.954]   # 학습한 인코더 중 머리별 최고(cls_report.txt: e5-base 98.2 · bge-m3 94.8 · e5-base 90.6 · bge-m3 95.4)
    cards = [
        ('now', '① 규칙(코드)', '「두 번째」「바로 다음」처럼 순서·위치로 정해지는 말을 코드로 확정',
         ['서수·상대 위치 61문제: 규칙 58 맞음 · 가르친 E4B 55 (탐색 — 규칙을 오류를 본 뒤 만듦)', '규칙 앞단이 처리한 몫: 122/769 = 15.9%, 그중 92.6% 맞음 (§82-5 · §85-3)'], '잰 값 있음'),
        ('warn', '② ML(학습한 판별기)', '질문 유형을 가려 처리 방향을 정함 · 확신 높으면 앞에서 끝냄',
         ['유형 판별기(글자 조각 로지스틱) 평가 밖 학습 → 755 대 750(단독) — 구분 안 됨 (§82-4)', '학습 임베딩 앞단 + 규칙 + E4B: 호출 25% 줄고 정확도 743 대 750 (§82-5)'], '잰 값 있음 · 정확도 이득 없음'),
    ]
    jl = []
    if jev:
        for k, (res, lat) in jev.items():
            jl.append(f"{k}: " + ' · '.join(f'{SHORT[h]} {100 * v:.0f}' for h, v in zip(HEADS, res)) + f' ({lat * 1000:.0f}ms)')
    else:
        jl = ['의도·감정·긴급도·대상 분류 점수: 시험 중']
    cards.append(('gpu', '③ Jev 계열 분류', '고정된 라벨 중 하나를 학습 없이 고르는 소형 결정 모델 — 이번에 비어 있던 칸',
                  ['일정 항목 짚기(후보 40~50개): 인코더형 Laya 21% · 4B급 Jev류 71~88% · 가르친 E4B 98% (§85-2 · §50)'] + jl,
                  '이번에 채움' if jev else '시험 중'))
    cards.append(('now', '④-a 임베딩 분류(앞서 보여 드린 표)', '학습한 작은 인코더 하나가 4가지 라벨을 한 번에',
                  [f'학습한 인코더 최고(CX 400): ' + ' · '.join(f'{SHORT[h]} {100 * v:.0f}' for h, v in zip(HEADS, best_enc)) + ' (CPU 35~120ms)',
                   '공개 감정 모델을 학습 없이 쓰면 감정 71% 가 최고 (§90)'], '잰 값 있음'))
    cards.append(('now', '④-b 소형 LLM', '항목 짚기 · 사람 말투가 어려운 문장',
                  ['항목 짚기: 가르친 E4B 750/769 = 97.5% (§69-5)', '학습 없는 E4B 분류(서비스 프롬프트): 의도 97 · 감정 84 · 긴급도 61 · 대상 86, 5.3초/건 — 학습한 인코더가 감정·긴급도에서 크게 앞섬'], '잰 값 있음'))
    foot = ['한 줄로 이어 끝까지 돌린 시험은 아직 없다 — 지금까지는 단계 하나 또는 둘씩만 이어서 쟀다(규칙 → 임베딩 게이트 → E4B 가 가장 긴 연결).',
            '「감정 전문 소형 LLM」을 따로 부를 필요는 근거가 없다: 감정·긴급도·의도 분류는 학습한 인코더가 학습 없는 LLM 보다 높다. LLM 이 꼭 필요한 곳은 일정 항목 짚기(앞 대화 지시어·이름 없는 묘사).']
    H = 200 + len(cards) * 200 + lines_height(foot, 70, 26) + 140
    fig, ax = canvas(H)
    head(ax, '모델 조합 — 질의가 지나가는 단계와 단계별로 잰 값', '질의 → ① 규칙 → ② ML → ③ Jev 분류 → ④ 임베딩 분류 또는 소형 LLM · 앞 단계가 처리하면 거기서 끝')
    y = 170
    for kind, title, what, lines, status in cards:
        box(ax, 30, y, 1020, 184, kind, 14, 2)
        t(ax, 50, y + 28, title, 17, PAL[kind][2], True)
        t(ax, 1030, y + 28, status, 12.5, PAL[kind][2], True, 'right')
        t(ax, 50, y + 58, what, 12, SUB)
        yy = y + 90
        for ln in lines:
            t(ax, 56, yy, '· ' + ln[:96], 12, INK)
            if len(ln) > 96:
                t(ax, 66, yy + 20, ln[96:192], 12, INK)
                yy += 20
            yy += 26
        y += 200
    yb = y + 4
    box(ax, 30, yb, 1020, 40 + 28 * len(foot) * 2, 'plain', 12, 1.6)
    yy = yb + 28
    for ln in foot:
        for i in range(0, len(ln), 70):
            t(ax, 50, yy, ('' if i else '▶ ') + ln[i:i + 70], 12.5, INK, bool(i == 0))
            yy += 24
        yy += 6
    y_end = yy + 24
    fig.set_size_inches(10.8, (y_end + 10) / 100)
    ax.set_ylim(y_end + 10, 0)
    fig.savefig(os.path.join(OUT, 'fig29_모델조합_5단계와_잰값.png'))
    print('ok', y_end, 'jev', list(jev))


if __name__ == '__main__':
    fig29()
