# 9차 그림 — 「한 줄로 이은 시험」 결과. 값은 results/_pull/chain/chain_*.json(문제별 추적)에서 세어 넣는다(손으로 쓴 값 없음). 빈 응답은 틀린 것으로 센다.
import collections
import glob
import json
import os
from make_figures import canvas, box, t, head, PAL, INK, SUB, LINE, OUT
from make_figures4 import reading_box, lines_height

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, '..', '..', 'scripts', 'plan_qa_bench', 'results', '_pull', 'chain')
TR = {os.path.basename(f)[6:-5]: json.load(open(f, encoding='utf-8')) for f in glob.glob(os.path.join(D, 'chain_*.json')) if not f.endswith('summary.json')}


def okk(x):
    return x['pick'] == x['gold'] and not any(f.startswith('parse_fail') for f in x['fail'])


def n769(tr):
    xs = [x for x in tr if x['type'] != 'compound_intent']
    return sum(okk(x) for x in xs), len(xs)


def lat(tr):
    v = sorted(x['total_ms'] for x in tr)
    return v[len(v) // 2]


ROWS = [('e4b_only', '가르친 E4B 만 (단독 기준선)'), ('rules_e4b', '규칙 → E4B'), ('no_jev', '규칙 → ML 거름 → 가르친 E4B (Jev 계열 모델 뺌)'), ('full', '규칙 → ML → Jev 계열 모델(학습 없음) → 가르친 E4B'),
        ('no_rules', '수정 판에서 규칙 뺌'), ('no_ml', '수정 판에서 ML 뺌'), ('full_noctx', 'Jev 계열 모델(학습 없음) 입력에 메시지만'), ('full_v1', '사전 등록 판 (Jev 계열 모델 입력에 한 줄)')]


def fig30():
    base_ok, N = n769(TR['e4b_only'])
    reading = ['단독으로 가르친 E4B 는 748/769 (97.3%, 빈 응답 8개를 틀린 것으로 센 값 — 서버 B 의 CPU 평가와 같은 748). 규칙 → ML 거름 → E4B 로 이으면 745 로 단독과 구분되지 않고(3 대 6, p=0.51) E4B 호출만 835 → 674 로 줄지만 건당 시간은 같다(약 0.2초).',
               '학습 없는 Jev 계열 모델(Winnow-E4B)을 「어디로 보낼까」 판정 자리에 넣으면 697 로 51개 줄어든다(p=4e-13). 비교 대상 E4B 는 가르친 것이라 공정한 비교가 아니다(§92-6). 일정 질문 550개 중 135개를 「범위 밖」으로 닫았고(24.5%), 잘못 닫은 정답 있는 질문 53개 중 41개가 이름 없이 설명만 하는 질문이다. 사전 등록 입력(일정 보유 한 줄)은 472 (61.4%) 까지 떨어졌다.',
               '규칙을 빼면 11개 줄고(697 → 686) ML 판별기는 점수를 바꾸지 않는다(범위 밖 잡담 36개를 정확히 닫아 Jev 계열 모델 호출만 줄인다). 연결 전체는 건당 658ms(p95 765ms)로 단독(196ms)의 3.4배다.',
               '한계: 사후에 만든 수정 판(시험 세트 44문제 표본을 본 뒤), 문턱·문구는 한 가지씩, 시험은 각 1회(출력은 결정적 — 다시 호출해도 835/835 같은 답). Jev 계열 모델이 고를 전문가가 사실상 하나뿐인 구성이다(§92-1).']
    H = 200 + len(ROWS) * 62 + 40 + 190 + lines_height(reading, 70, 28) + 100
    fig, ax = canvas(H)
    head(ax, '한 줄로 이은 시험 — 가르친 E4B 단독과 나란히', '요청 둘 제외 769문제(mix8~12) · 빈 응답은 틀림 · 서버 C에서 문제마다 실제 호출')
    t(ax, 40, 168, '변형', 12, SUB, True)
    t(ax, 560, 168, '정답 수 / 769', 12, SUB, True)
    t(ax, 880, 168, '단독 대비', 12, SUB, True, 'center')
    t(ax, 1010, 168, '건당 ms', 12, SUB, True, 'center')
    y = 184
    x0, wmax = 400, 330
    for key, lab in ROWS:
        ok, n = n769(TR[key])
        d = ok - base_ok
        kind = 'plain' if key == 'e4b_only' else ('now' if d >= -3 else ('warn' if d >= -15 else 'bad'))
        box(ax, 30, y, 1020, 54, 'plain', 8, 1.2)
        t(ax, 42, y + 27, lab, 12.6, INK, True)
        ax.add_patch(__import__('matplotlib').patches.Rectangle((x0, y + 14), wmax * ok / n, 26, fc=PAL['gpu'][1] if key == 'e4b_only' else PAL[kind][1], ec='none', alpha=0.85))
        t(ax, x0 + wmax * ok / n + 8, y + 27, f'{ok}', 13, INK, True)
        box(ax, 850, y + 8, 60, 38, kind, 6, 1.4)
        t(ax, 880, y + 27, '—' if key == 'e4b_only' else f'{d:+d}', 13, PAL[kind][2], True, 'center')
        t(ax, 1010, y + 27, f'{lat(TR[key]):.0f}', 12.4, INK, False, 'center')
        y += 62
    y += 18
    # 수정 판의 흐름
    full = TR['full']
    c = collections.Counter(x['ended'] for x in full)
    rej_ml = sum(1 for x in full if x['ended'] == 'reject' and x.get('route_by') == 'ml')
    rej_jev = sum(1 for x in full if x['ended'] == 'reject' and x.get('route_by') == 'jev')
    bad = sum(1 for x in full if x['ended'] == 'reject' and x['gold'] is not None and x['type'] != 'compound_intent')
    t(ax, 40, y + 4, '수정 판(규칙 → ML → Jev 계열 모델[학습 없음] → 가르친 E4B) — 835문제가 어디서 끝났나', 15, INK, True)
    y += 28
    cells = [('① 규칙이 끝냄', c['rules'], 'now', '코드로 확정'), ('② ML 이 범위 밖으로', rej_ml, 'now', '잡담 36개 전부 정확'), ('③ Jev 계열 모델(학습 없음)이 범위 밖으로', rej_jev, 'bad', f'그중 정답 있는 {bad}개를 놓침'), ('④ E4B 가 짚음', c['e4b'], 'gpu', '가르친 E4B')]
    cw = 246
    for i, (a, n, k, b) in enumerate(cells):
        x = 30 + i * (cw + 12)
        box(ax, x, y, cw, 100, k, 12, 1.8)
        t(ax, x + 14, y + 26, a, 12.5, PAL[k][2], True)
        t(ax, x + 14, y + 62, f'{n}', 26, PAL[k][2], True)
        t(ax, x + 14, y + 86, b, 10.5, PAL[k][2])
    y += 120
    y_end = reading_box(ax, y, '읽는 법', reading, 'gpu', 70, 12, 28)
    fig.set_size_inches(10.8, (y_end + 10) / 100)
    ax.set_ylim(y_end + 10, 0)
    fig.savefig(os.path.join(OUT, 'fig30_한줄연결시험_결과.png'))
    print('ok', y_end)


def fig31():
    """가르친 Jev 계열 모델(Winnow-E4B + QLoRA)과 가르친 E4B 를 전문가로 놓은 구성들 — results/chain_experts_offline.txt 표에서 읽는다."""
    import re
    txt = open(os.path.join(HERE, '..', '..', 'scripts', 'plan_qa_bench', 'results', 'chain_experts_offline.txt'), encoding='utf-8').read()
    rows = []
    for m in re.finditer(r'^\| (.+?) \| \*\*(\d+)\*\* \(([\d.]+)%\) \| (\d+) · (\d+) \| (.+?) \|$', txt, re.M):
        rows.append((m.group(1), int(m.group(2)), m.group(6)))
    short = {'단독 가르친 E4B(규칙·ML 없음)': '가르친 E4B 단독', '단독 가르친 Winnow-E4B(Jev 계열)': '가르친 Winnow-E4B(Jev 계열 모델) 단독',
             'S1': '규칙 → ML → 가르친 E4B', 'S2': '규칙 → ML → 가르친 Winnow-E4B(Jev 계열)', 'S3a': '… 가르친 E4B, 확신 낮으면 Winnow-E4B 인계',
             'S3b': '… 가르친 Winnow-E4B, 확신 낮으면 E4B 인계', 'S4': '… ML 유형 판별기 → 유형별로 더 나은 모델', 'S5': '… 학습한 ML 라우터가 고름', '(상한)': '(상한) 둘 중 하나라도 맞히면 맞음'}
    def lab(n):
        for k, v in short.items():
            if n.startswith(k):
                return v
        return n
    base = next(r[1] for r in rows if r[0].startswith('단독 가르친 E4B'))
    reading = ['전문가 자리에 「가르친 Jev 계열 모델」을 놓으면 단독으로 756/769 (98.3%) 로 가르친 E4B(750)보다 6개 높지만 구분되지 않는다(10 대 4, p=0.18). 이름 없이 설명만 하는 질문에서 70 대 63 으로 앞선다.',
               '앞에 규칙·ML 판별기를 붙이면 두 전문가 모두 3~4개 낮아진다(747 · 752) — 이 앞단은 E4B 호출을 줄일 뿐 점수는 올리지 못한다.',
               '확신도 인계 · 유형별 보내기 · 학습한 ML 라우터는 모두 750~752 로 서로 구분되지 않는다(p≥0.8). 거름 뒤 두 전문가가 다른 답을 낸 문제가 12개뿐이라 고를 여지가 작다(상한 755).',
               '한계: 전문가 답·확신도는 서버 B 의 저장 결과(HF 4비트 + 어댑터, 두 전문가 같은 조건)이고 규칙·ML 판별기는 서버 C 의 실제 호출이다. 문턱·유형별 전문가·라우터는 한 세트 빼고 고른 값이며 라우터는 12개 안팎의 불일치 사례로 학습해 믿기 어렵다.']
    H = 200 + len(rows) * 62 + 40 + lines_height(reading, 70, 28) + 100
    fig, ax = canvas(H)
    head(ax, '가르친 Jev 계열 모델과 가르친 E4B 를 이은 구성', '요청 둘 제외 769문제(mix8~12) · 전문가 단계에 가르친 모델 둘 · 규칙·ML 은 실제 호출')
    t(ax, 40, 168, '구성', 12, SUB, True)
    t(ax, 560, 168, '정답 수 / 769', 12, SUB, True)
    t(ax, 920, 168, '가르친 E4B 단독 대비', 12, SUB, True, 'center')
    y = 184
    x0, wmax = 420, 320
    for name, ok, vs in rows:
        d = ok - base
        kind = 'gpu' if name.startswith('단독 가르친 Winnow') else ('plain' if name.startswith('단독 가르친 E4B') else ('now' if d >= -1 else 'warn'))
        box(ax, 30, y, 1020, 54, 'plain', 8, 1.2)
        t(ax, 42, y + 27, lab(name), 12.2, INK, True)
        ax.add_patch(__import__('matplotlib').patches.Rectangle((x0, y + 14), wmax * ok / 769, 26, fc=PAL['gpu'][1] if kind in ('gpu', 'plain') else PAL[kind][1], ec='none', alpha=0.85))
        t(ax, x0 + wmax * ok / 769 + 8, y + 27, f'{ok}', 13, INK, True)
        box(ax, 880, y + 8, 80, 38, kind, 6, 1.4)
        t(ax, 920, y + 27, '—' if name.startswith('단독 가르친 E4B') else f'{d:+d}', 13, PAL[kind][2], True, 'center')
        t(ax, 1005, y + 27, '' if name.startswith('단독 가르친 E4B') else vs.split('(')[-1].rstrip(')').replace('p=', 'p '), 10.5, SUB, False, 'center')
        y += 62
    y += 12
    y_end = reading_box(ax, y, '읽는 법', reading, 'gpu', 70, 12, 28)
    fig.set_size_inches(10.8, (y_end + 10) / 100)
    ax.set_ylim(y_end + 10, 0)
    fig.savefig(os.path.join(OUT, 'fig31_가르친Jev계열모델_전문가구성.png'))
    print('ok31', y_end)


if __name__ == '__main__':
    fig30()
    fig31()
