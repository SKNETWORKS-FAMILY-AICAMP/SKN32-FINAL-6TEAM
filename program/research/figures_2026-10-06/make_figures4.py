# 4차 그림 — JevBench 오늘자(v1.6.0) 순위와 우리 시험 · 소형 모델만으로 짠 구성 · C 채점 포함 비교 · (CPU 전용 배포는 make_figures5.py). 폭 1080px.
#  값은 scripts/plan_qa_bench/results/small_ensemble_769.txt · c_scoring_all.txt · jevbench_v1.6.0_순위_2026-10-06.tsv 에서 옮겼다(손으로 만든 값 없음).
import os
import textwrap
from make_figures import canvas, box, t, head, PAL, INK, SUB, LINE, OUT
from matplotlib.patches import Rectangle


def reading_box(ax, y, title, lines, kind='gpu', width_chars=66, size=12.6, lh=28):
    wrapped = []
    for s in lines:
        w = textwrap.wrap(s, width_chars, subsequent_indent='  ')
        wrapped.extend(w)
    h = 58 + len(wrapped) * lh + 14
    box(ax, 30, y, 1020, h, kind, 16, 2)
    t(ax, 56, y + 30, title, 16.5, PAL[kind][2], True)
    for i, s in enumerate(wrapped):
        t(ax, 56, y + 64 + i * lh, s, size, PAL[kind][2])
    return y + h + 14


def lines_height(lines, width_chars=66, lh=28):
    return 58 + sum(len(textwrap.wrap(s, width_chars, subsequent_indent='  ')) for s in lines) * lh + 14 + 14


# ───────────────── 24. JevBench 오늘자 순위와 우리 시험 ─────────────────
def fig24():
    rows = [  # 보드순위, 모델, 지능, choice, noul, 우리 정확도, 비고, 종류
        ('4', 'torchcast-decision-12b (Gemma-4-12B)', '60.5', '68.4', '62.4', '미시험', '상업 금지·영어·용량', 'warn'),
        ('6', 'Winnow-12B Q8 (Gemma-4-12B)', '59.5', '69.7', '52.5', '94.0', 'n=769', 'plain'),
        ('8', 'Jev-Omni (Gemma-4-12B)', '55.5', '68.9', '32.5', '91.8', '묶음 읽기 n=769', 'plain'),
        ('7', 'Cygnet (Gemma-4-12B, 무학습)', '54.8', '65.5', '39.6', '90.8', 'n=769', 'plain'),
        ('11', 'spark-s1-4b-v6 (Qwen3.5-4B)', '43.2', '58.0', '33.9', '미시험', '다음 후보', 'warn'),
        ('10', 'Plumb-4B (Qwen3.5-4B 계열)', '43.0', '58.2', '23.4', '83.3', 'n=460', 'plain'),
        ('13', 'Quyet-1.0-Medium (Qwen3.5-4B)', '41.7', '59.0', '26.0', '미시험', '다음 후보', 'warn'),
        ('14', 'lev (Qwen3.5-4B + LoRA)', '41.1', '54.5', '29.6', '79.8', 'n=460', 'plain'),
        ('17', 'decider-4b v2 (Qwen3.5-4B)', '40.1', '56.8', '11.6', '79.0', 'n=309', 'plain'),
        ('18', 'JevK5 v0.3 4B (Qwen3.5-4B)', '38.5', '58.8', '22.9', '81.1', 'n=460', 'plain'),
        ('25', 'Hopper 4B (Qwen3.5-4B)', '35.1', '57.3', '0.0', '87.6', 'n=460', 'plain'),
        ('—', 'Winnow-E4B (Gemma-4-E4B)', '보드에 없음', '', '', '70.9', 'n=460', 'bad'),
        ('—', '가르친 E4B (우리: E4B + LoRA)', '', '', '', '97.5', 'n=769', 'now'),
    ]
    reading = ['보드의 「지능」 순위와 우리 정확도 순위는 잘 맞는다 — 스피어만 순위상관 +0.89 (14개 모델). 속도·비용이 섞인 헤드라인 점수는 +0.56 으로 덜 맞는다.',
               '그래서 모델을 고를 때는 보드의 「지능」·choice 열을 본다. noul 은 「없음」을 맞히는 힘이다 (우리 문제의 20~26% 가 「없음」).',
               '보드에 Gemma-4-E4B 바탕의 결정 모델은 없다. 공개된 E4B 계열은 Winnow-E4B 뿐이고 우리 시험에서 12B 보다 20%p 이상 낮았다.',
               '보드 점수는 영어·무학습이고 우리 97.5% 는 한국어 일정 문제를 학습시킨 값이라 직접 비교가 아니다. 같은 학습을 큐웬 3.5 4B 에도 걸어 두었다.']
    src = ['출처: benchmarkheaven.com/api/jevbench/v1.6.0 (JevBench v1.6.0, 확인 2026-10-06 06:00 KST). GitHub 안내문(v1.4.2.2)과 benchlm.ai(v1.5.4)는 낡았다.',
           'n = 푼 문제 수 (769 = mix8~12 요청 둘 제외 · 460 = mix8~10 · 309 = mix8~9). 우리 정확도 % 는 같은 시험지·같은 채점이다.']
    H = 200 + len(rows) * 62 + lines_height(reading) + lines_height(src, 70) + 40
    fig, ax = canvas(H)
    head(ax, 'JevBench 오늘자 순위와 우리 시험', 'v1.6.0 실시간 자료 · 12B 이하 공개 모델 · 보드 점수는 영어 결정 문제 기준')
    x = [40, 95, 505, 585, 655, 720, 850]
    for xi, s in zip(x, ['순위', '모델 (바탕)', '지능', 'choice', 'noul', '우리 %', '비고']):
        t(ax, xi, 168, s, 13.5, SUB, True)
    y = 190
    for rk, nm, a, b, c, ours, note, kind in rows:
        box(ax, 30, y, 1020, 56, kind, 10, 1.4)
        col = PAL[kind][2]
        t(ax, x[0], y + 28, rk, 15, col, True)
        t(ax, x[1], y + 28, nm, 13.6, col, kind == 'now')
        for xi, v in zip(x[2:5], [a, b, c]):
            t(ax, xi, y + 28, v, 14, col)
        t(ax, x[5], y + 28, ours, 16, col, True)
        t(ax, x[6], y + 28, note, 11.5, SUB)
        y += 62
    y += 10
    y = reading_box(ax, y, '읽는 법', reading, 'gpu')
    y = reading_box(ax, y, '출처와 주의', src, 'warn', 70, 12)
    fig.savefig(os.path.join(OUT, 'fig24_JevBench_오늘자_순위와_우리_시험.png'))


# ───────────────── 25. 소형 모델만으로 짠 구성 ─────────────────
def fig25():
    singles = [('Winnow-12B', 723), ('Decider-12B', 728), ('Gemma 26B (올라마)', 732), ('Qwen3.8 27B', 749), ('decider-chat 31B', 748)]
    combos = [
        ('가르친 E4B 단독 (기준선)', 750, '호출 1×', 'now', ''),
        ('+ 증류 자료로 학습한 ML 라우터 → Decider-12B (46문제만)', 755, '호출 1.06×', 'now', '기준선과 8 : 3 · p=0.23 구분 안 됨'),
        ('소형 다수결 3 (가르친 E4B · Decider-12B · Winnow-12B)', 754, '호출 3×', 'gpu', '15 : 11 · p=0.56 구분 안 됨'),
        ('이름 겹침 규칙 라우터', 750, '효과 없음', 'bad', '판별 AUC 0.70 — 문턱을 올리면 오히려 떨어짐'),
        ('[낙관] 평가 세트 안 교차검증 ML 라우터', 761, '호출 1.1×', 'warn', '13 : 2 · p=0.007 — 평가와 같은 저자 문체를 학습한 값'),
        ('[상한] 문제 유형을 미리 안다고 가정한 라우팅', 759, '유형 라벨 필요', 'warn', '11 : 2 · p=0.022'),
        ('[천장] 가르친 E4B 와 Decider-12B 중 하나라도 맞힘', 767, '고르는 방법 없음', 'done', '두 모델의 틀린 문제가 거의 안 겹친다'),
    ]
    reading = ['소형 다수결은 호출이 3배인데 가르친 E4B 단독과 구분되지 않는다 (754 대 750).',
               '가르친 E4B 의 오답 19개 중 12개가 「이름 없는 묘사」 유형이다. 그 유형만 Decider-12B 에 넘기면 8개를 고치고 3개를 망쳤다 (순증 +5).',
               '규칙(이름 겹침)은 그 유형을 가려내지 못했고, 학습한 ML 라우터는 가려낸다 (AUC 0.93 — 평가 문체가 달라 검증 0.996 에서 떨어짐).',
               '가르친 E4B 의 확신도로 큰 쪽에 넘기는 위임은 서버 B 에서 확신도 저장 평가를 돌리는 중이라 아직 숫자가 없다.']
    n_rows = len(combos) + len(singles)
    H = 200 + n_rows * 90 + 140 + lines_height(reading)
    fig, ax = canvas(H)
    head(ax, '소형 모델만으로 짠 구성 — 769문제', '요청 둘 제외 · 가르친 E4B 750 이 기준선 · 막대 축은 90% 에서 시작 · mix8~12')
    x0, x1, lo, hi = 40, 1040, 90.0, 100.0

    def bar(y, label, n, kind, tag, note):
        pct = 100 * n / 769
        t(ax, 40, y + 12, label, 13.4, INK, kind == 'now')
        ax.add_patch(Rectangle((x0, y + 30), x1 - x0, 32, fc='#eef0f2', ec='none'))
        w = (x1 - x0) * (max(lo, pct) - lo) / (hi - lo)
        ax.add_patch(Rectangle((x0, y + 30), w, 32, fc=PAL[kind][1], ec='none'))
        t(ax, x0 + w - 10, y + 46, f'{n}/769 = {pct:.1f}%', 13.5, '#ffffff', True, 'right')
        if note:
            t(ax, 40, y + 76, note, 11.2, SUB)
        if tag:
            t(ax, x1, y + 76, tag, 11.2, SUB, False, 'right')

    y = 168
    t(ax, 40, y, '조합 (모두 소형 · 가르친 E4B 가 중심)', 16, INK, True)
    y += 24
    for lab, n, tag, kind, note in combos:
        bar(y, lab, n, kind, tag, note)
        y += 90
    y += 10
    t(ax, 40, y, '참고: 한 모델 단독 (큰 모델 포함)', 16, INK, True)
    y += 24
    for lab, n in singles:
        bar(y, lab, n, 'done', '', '')
        y += 90
    y += 4
    reading_box(ax, y, '읽는 법', reading, 'gpu')
    fig.savefig(os.path.join(OUT, 'fig25_소형_구성_769.png'))


# ───────────────── 26. C 채점 포함 ─────────────────
def fig26():
    items = [  # 라벨, C 정답 수/835, 요청 둘 C(/66), kind, 비고
        ('가르친 E4B (한 항목)', 750, 0, 'done', '요청 둘 A·B 는 66/66 이지만 C 는 0'),
        ('Qwen3.8 27B (한 항목)', 749, 0, 'done', ''),
        ('결정 모델 OpenJev 26B 「확률 ≥ τ 인 항목 집합」', 757, 22, 'done', '낙관 — 835문제에서 τ 를 골랐다'),
        ('Gemma 12B 「둘 다 찾기」 지시', 718, 53, 'gpu', '요청 둘은 잘 하지만 한 항목 문제를 많이 틀린다 (769 중 665)'),
        ('가르친 E4B + Gemma 12B (이름 규칙으로 요청 둘 판별)', 770, 46, 'now', '규칙 정밀도 0.19 — 한 항목 문제 일부를 요청 둘로 오해'),
        ('[상한] 요청 둘을 완벽히 가려낸다면 (E4B + Gemma 12B)', 803, 53, 'warn', ''),
        ('Claude Opus 5.5 (클라우드, 참고)', 819, 60, 'bad', '로컬 아님'),
        ('Claude Fable 5.1 (클라우드, 참고)', 821, 59, 'bad', '로컬 아님'),
    ]
    reading = ['한 항목만 내는 모델은 요청 둘(66문제 = 7.9%)에서 C 가 0 이라 835 기준 최대 92.1% (769÷835) 에서 막힌다. 지금까지 769문제로 비교해서 이 부분이 가려졌다.',
               '요청 둘을 알아보는 규칙(질문에 일정 항목 이름 조각이 둘 이상)은 요청 둘 51/66 을 잡지만 한 항목 문제 224개를 잘못 걸어 정밀도가 0.19 다.',
               '그래서 가르친 E4B 를 여러 항목 형식으로 가르치는 실험을 서버 B 대기열(37)에 걸었다. 학습 자료의 요청 둘 128개가 둘 다 정답으로 들어 있다.',
               '성공 기준(사전): 요청 둘 제외 769 에서 가르친 단일 E4B(750)와 구분되지 않고, 요청 둘 C 가 Gemma 12B(53/66) 이상.']
    H = 200 + len(items) * 90 + 60 + lines_height(reading)
    fig, ax = canvas(H)
    head(ax, 'C 채점(둘 다 찾기)까지 넣은 비교 — 835문제', '요청 둘 66문제 포함 · C = 고른 항목 집합이 정답 집합과 정확히 같음 · 막대 축은 82% 에서 시작')
    x0, x1, lo, hi = 40, 880, 82.0, 100.0
    t(ax, 40, 168, 'C 전체 정답 (835 중)', 13.5, SUB, True)
    t(ax, 1040, 168, '요청 둘 C (66 중)', 13.5, SUB, True, 'right')
    y = 190
    for lab, n, c2, kind, note in items:
        pct = 100 * n / 835
        t(ax, 40, y + 12, lab, 13.4, INK, kind == 'now')
        ax.add_patch(Rectangle((x0, y + 30), x1 - x0, 32, fc='#eef0f2', ec='none'))
        w = (x1 - x0) * (max(lo, pct) - lo) / (hi - lo)
        ax.add_patch(Rectangle((x0, y + 30), w, 32, fc=PAL[kind][1], ec='none'))
        txt = f'{n} = {pct:.1f}%'
        if w > 130:
            t(ax, x0 + w - 10, y + 46, txt, 13.5, '#ffffff', True, 'right')
        else:
            t(ax, x0 + w + 10, y + 46, txt, 13.5, INK, True, 'left')
        t(ax, 1040, y + 46, f'{c2}/66', 17, INK, True, 'right')
        if note:
            t(ax, 40, y + 76, note, 11.2, SUB)
        y += 90
    y += 10
    reading_box(ax, y, '읽는 법', reading, 'gpu')
    fig.savefig(os.path.join(OUT, 'fig26_C채점_포함_비교.png'))


if __name__ == '__main__':
    fig24()
    fig25()
    fig26()
    print('ok')
