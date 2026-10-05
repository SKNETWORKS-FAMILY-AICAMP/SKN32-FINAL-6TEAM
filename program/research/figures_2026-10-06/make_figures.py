# 휴대폰에서 보는 설명용 PNG 5장 — 지금까지 한 일 · 상시 GPU 월 비용 · API 대 GPU 손익분기 · 추천 배포 구성 · 증류 파일럿.
#  수치는 연구 문서(여행일정_질문인식_모델비교_2026-09-29.md)의 69·71·72절과 같다. 가정: 1달러 = 1,400원, 상시 = 730시간/월, 호출 1건 = 입력 약 1,700토큰.
# 사용: python make_figures.py   → 같은 폴더에 fig1~fig5 PNG(폭 1080px)
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
import numpy as np

OUT = os.path.dirname(os.path.abspath(__file__))
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False
INK, SUB, LINE = '#1f2937', '#4b5563', '#cbd5e1'
PAL = {'done': ('#eef0f2', '#9aa3ad', '#374151'), 'now': ('#dff3ec', '#1d9e75', '#085041'), 'gpu': ('#ebe9fb', '#534ab7', '#26215C'),
       'warn': ('#fbeed6', '#ba7517', '#633806'), 'bad': ('#fbe9e9', '#c0392b', '#7f1d1d'), 'plain': ('#ffffff', '#cbd5e1', '#1f2937')}


def canvas(h):
    fig = plt.figure(figsize=(10.8, h / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1080)
    ax.set_ylim(h, 0)
    ax.axis('off')
    fig.patch.set_facecolor('white')
    return fig, ax


def box(ax, x, y, w, h, kind, r=16, lw=2.2):
    f, e, _ = PAL[kind]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f'round,pad=0,rounding_size={r}', fc=f, ec=e, lw=lw))


def t(ax, x, y, s, size=15, color=INK, bold=False, ha='left', va='center', **kw):
    ax.text(x, y, s, fontsize=size, color=color, fontweight='bold' if bold else 'normal', ha=ha, va=va, **kw)


def head(ax, title, sub, w=1080):
    t(ax, 40, 56, title, 27, INK, True)
    t(ax, 40, 104, sub, 15, SUB)
    ax.plot([40, w - 40], [136, 136], color=LINE, lw=2)


# ───────────────── 1. 지금까지 한 일 ─────────────────
def fig1():
    rows = [
        ('done', '끝', '시험지 만들기', ['고객 질문 835문제, 문제마다 정답 번호가 있음', '(Codex가 4세트, Claude가 1세트 작성)'], (5, 5, '세트')),
        ('done', '끝', '모델 비교 시험', ['모델 73종을 같은 문제로 채점해 표로 정리', '(큰 모델·작은 모델·조합까지 한 표)'], None),
        ('done', '끝', '공정성 정리', ['규칙을 알려 준 점수·묶음 풀이는', '「공정 비교 아님」으로 따로 표시, CSV·엑셀로 내보냄'], None),
        ('now', '진행', '작은 모델 가르치기 (증류)', ['연습문제 1,760개 검증 100% 일치 → 학습 1,313문제', '학습 끝(148.7분) → 지금 평가 중, 판정 남음'], (6, 7, '단계')),
        ('now', '진행', 'Spark 1.3 시험 (OpenCode 무료)', ['중간: mix10 120문제 중 114 맞음 (공정 비교 아님)', '에이전트 지시문 2.6만 토큰이 같이 실리고 생각도 함'], (120, 835, '문제')),
        ('now', '진행', 'CPU 속도 측정 (GPU 없는 4코어)', ['첫 질문 4B 154초 · 12B 435초, 캐시 뒤 25~45초', '오라클 ARM은 더 느릴 가능성 (x86 CPU로 잰 값)'], (2, 3, '모델')),
        ('done', '끝', '배포 비용 조사', ['RunPod 월 약 24.5만원 · AWS는 2.2~4.2배 · API는 쓴 만큼', '코랩은 약관상 배포 불가 · 정확도 비교가 남음'], (3, 4, '비교 축')),
        ('bad', '막힘', 'Clef 27B 시험', ['16GB GPU에서 올라가지 않아 전부 오류 (점수 아님)', 'GPU에 올리는 층 수를 줄여 우회 시험 예정'], (0, 5, '세트')),
    ]
    H = 190 + len(rows) * 152 + 190
    fig, ax = canvas(H)
    head(ax, '지금까지 한 일 (10월 6일 새벽 기준)', '목표: 고객 채팅 한 줄 → 여행 일정 중 어느 항목인지 짚기 — 작은 모델로 큰 모델만큼')
    y = 160
    for kind, chip, title, lines, prog in rows:
        box(ax, 30, y, 1020, 140, 'plain' if kind != 'bad' else 'bad', 18, 2)
        box(ax, 50, y + 16, 104, 44, kind, 12, 2)
        t(ax, 102, y + 38, chip, 18, PAL[kind][2], True, 'center')
        t(ax, 172, y + 36, title, 20, INK, True)
        t(ax, 172, y + 76, lines[0], 14.5, SUB)
        t(ax, 172, y + 104, lines[1], 14.5, SUB)
        if prog:
            n, m, unit = prog
            bx, bw = 172, 858
            ax.add_patch(Rectangle((bx, y + 122), bw, 9, fc='#e5e7eb', ec='none'))
            ax.add_patch(Rectangle((bx, y + 122), bw * n / m, 9, fc=PAL[kind][1], ec='none'))
            t(ax, 1030, y + 36, f'{n}/{m} {unit} = {100 * n / m:.0f}%', 16.5, INK, True, 'right')
        y += 152
    box(ax, 30, y + 6, 1020, 120, 'warn', 18, 2)
    t(ax, 56, y + 40, '알려 드릴 일', 17, PAL['warn'][2], True)
    t(ax, 56, y + 76, 'GPU 서버 B가 학습이 끝난 뒤 약 2시간 쉬었음 — 평가 명령에 값을 하나 더 넘긴 제 실수.', 14.5, PAL['warn'][2])
    t(ax, 56, y + 102, '고쳐서 평가를 다시 시작했고, 지금은 정상으로 돌고 있습니다.', 14.5, PAL['warn'][2])
    fig.savefig(os.path.join(OUT, 'fig1_지금까지_한_일.png'))
    plt.close(fig)


# ───────────────── 2. 상시 GPU 월 비용 ─────────────────
def fig2():
    H = 1020
    fig, ax = canvas(H)
    head(ax, '상시 GPU는 한 달에 얼마?', '24시간 켜 둘 때 · 1달러 = 1,400원 가정 · 시간당 가격 × 730시간')
    data = [('RunPod\nRTX 2000 Ada 16GB', 24.5, 'gpu', '24.5만원 (기준 1.0배)'), ('AWS g4dn\nT4 16GB', 53.8, 'done', '53.8만원 (2.2배)'),
            ('AWS g6\nL4 24GB', 82.3, 'done', '82.3만원 (3.4배)'), ('AWS g5\nA10G 24GB', 102.8, 'done', '102.8만원 (4.2배)')]
    x0, scale, y = 330, 4.3, 190
    for name, v, k, lab in data:
        t(ax, 40, y + 34, name, 16.5, INK, True)
        box(ax, x0, y, v * scale, 68, k, 10, 2)
        t(ax, x0 + v * scale + 14, y + 34, lab, 15.5, INK, True)
        y += 112
    t(ax, 40, y + 34, 'Colab\n(참고)', 16.5, INK, True)
    ax.add_patch(FancyBboxPatch((x0, y), 12 * scale, 68, boxstyle='round,pad=0,rounding_size=10', fc='#ffffff', ec='#c0392b', lw=2.2, ls='--'))
    t(ax, x0 + 12 * scale + 14, y + 20, '상시로 흉내 내면 약 12만원', 15.5, INK, True)
    t(ax, x0 + 12 * scale + 14, y + 50, '하지만 서비스 배포는 약관 위반', 15.5, '#c0392b', True)
    y += 112
    box(ax, 30, y + 10, 1020, 250, 'plain', 18, 2)
    notes = ['읽는 법', '· 가장 싼 것은 RunPod. 같은 급 AWS는 2.2~4.2배', '· 코랩은 「웹 서비스 제공」과 터널 연결이 금지,', '   무료 12시간·Pro+ 24시간 제한, GPU 종류도 보장 안 됨', '· 가격 주의: RunPod 값은 출처마다 반대로 나옴 → 콘솔 값이 정본',
             '· 연 단위 계약 할인율은 공개 숫자를 못 찾음 (확인 필요)']
    yy = y + 44
    for i, s in enumerate(notes):
        t(ax, 56, yy, s, 17 if i == 0 else 14.5, INK if i == 0 else SUB, i == 0)
        yy += 38 if i == 0 else 32
    fig.savefig(os.path.join(OUT, 'fig2_상시_월_비용.png'))
    plt.close(fig)


# ───────────────── 3. API 대 GPU 손익분기 ─────────────────
def fig3():
    FX = 1400
    apis = {'Luna': ('#1d9e75', 0.25, 0.06), 'Sol': ('#ba7517', 4.93, 1.15), 'Astra': ('#c0392b', 24.64, 5.74)}
    fig = plt.figure(figsize=(10.8, 11.0), dpi=100)
    fig.patch.set_facecolor('white')
    fig.text(0.037, 0.965, '외부 API vs 상시 GPU, 어디가 쌀까?', fontsize=27, fontweight='bold', color=INK, va='center')
    fig.text(0.037, 0.93, '월 질문 수에 따른 월 비용 (원 → 만원) · 막대 폭 = 캐시 없음~있음', fontsize=15, color=SUB, va='center')
    ax = fig.add_axes([0.13, 0.37, 0.82, 0.52])
    n = np.logspace(3, 7, 200)
    gpu = 245280 / 1e4
    for name, (c, hi, lo) in apis.items():
        ax.fill_between(n, n * lo / 1e4, n * hi / 1e4, color=c, alpha=0.18, lw=0)
        ax.plot(n, n * hi / 1e4, color=c, lw=2.4)
        ax.plot(n, n * lo / 1e4, color=c, lw=2.4, ls='--')
    ax.axhline(gpu, color='#534ab7', lw=4)
    ax.axhline(53.8, color='#9aa3ad', lw=2, ls=':')
    ax.axvline(1e4, color='#374151', lw=1.6, ls='--')
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlim(1e3, 1e7)
    ax.set_ylim(0.01, 1000)
    ax.set_xticks([1e3, 1e4, 1e5, 1e6, 1e7])
    ax.set_xticklabels(['1천', '1만', '10만', '100만', '1,000만'], fontsize=15)
    ax.set_yticks([0.01, 0.1, 1, 10, 100, 1000])
    ax.set_yticklabels(['0.01', '0.1', '1', '10', '100', '1,000'], fontsize=14)
    ax.set_xlabel('월 질문 수 (건)', fontsize=16, labelpad=8)
    ax.set_ylabel('월 비용 (만원)', fontsize=16, labelpad=8)
    ax.grid(True, which='major', color='#e5e7eb', lw=1)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    ax.text(1.15e3, gpu * 0.62, 'RunPod GPU 상시 24.5만원 (0건이어도)', color='#534ab7', fontsize=14.5, fontweight='bold', zorder=6, bbox=dict(fc='white', ec='none', pad=2.5, alpha=0.92))
    ax.text(1.15e3, 53.8 * 1.2, 'AWS g4dn 상시 53.8만원', color='#6b7280', fontsize=13, zorder=6, bbox=dict(fc='white', ec='none', pad=2, alpha=0.92))
    ax.text(1.05e4, 0.016, '가정: 월 1만 건\n(100팀 × 100질문)', color='#374151', fontsize=13)
    ax.text(2.6e6, 1.1, 'Luna', color='#1d9e75', fontsize=17, fontweight='bold')
    ax.text(2.2e5, 14, 'Sol', color='#ba7517', fontsize=17, fontweight='bold')
    ax.text(2.4e4, 120, 'Astra', color='#c0392b', fontsize=17, fontweight='bold')
    fig.text(0.037, 0.285, '선이 보라색 GPU 선과 만나는 곳 = 손익분기 (그보다 적게 쓰면 API가 쌈)', fontsize=15.5, fontweight='bold', color=INK)
    rows = [('Astra', '#c0392b', '1만 ~ 4.3만 건'), ('Sol', '#ba7517', '5만 ~ 21만 건'), ('Luna', '#1d9e75', '100만 ~ 427만 건')]
    y = 0.245
    for nm, c, s in rows:
        fig.text(0.06, y, '●', color=c, fontsize=19, va='center')
        fig.text(0.10, y, f'{nm}: 월 {s} 근처에서 GPU와 같아짐', fontsize=15.5, color=INK, va='center')
        y -= 0.036
    fig.text(0.037, 0.115, '실선 = 캐시 없음, 점선 = 캐시가 걸릴 때 (일정 앞부분 할인)', fontsize=13.5, color=SUB)
    fig.text(0.037, 0.082, '정확도는 이 비교에 넣지 못함 (Sol·Astra 문제별 점수 미측정, Luna는 묶음 풀이뿐)', fontsize=13.5, color=SUB)
    fig.text(0.037, 0.05, '가정: 호출 1건 = 입력 약 1,700토큰 + 출력 12토큰, 환율 1,400원 · API 단가는 2차 자료', fontsize=13.5, color=SUB)
    fig.savefig(os.path.join(OUT, 'fig3_API_대_GPU_손익분기.png'))
    plt.close(fig)


# ───────────────── 4. 추천 배포 구성 ─────────────────
def fig4():
    H = 1180
    fig, ax = canvas(H)
    head(ax, '추천 배포 구성', '앱은 무료·저가 CPU에 두고, 질문 분류만 GPU 또는 외부 API로 보낸다')
    boxes = [(40, 'done', '고객·에이전트', '채팅·API 요청'), (390, 'now', 'cs 프로젝트 서버', '무료·저가 CPU'), (740, 'gpu', 'RunPod GPU', '월 약 24.5만원 고정')]
    for x, k, a, b in boxes:
        box(ax, x, 190, 300, 130, k, 18, 2.4)
        t(ax, x + 150, 233, a, 20, PAL[k][2], True, 'center')
        t(ax, x + 150, 277, b, 15, PAL[k][2], False, 'center')
    for x1, x2 in ((340, 390), (690, 740)):
        ax.annotate('', xy=(x2, 255), xytext=(x1, 255), arrowprops=dict(arrowstyle='-|>', color=SUB, lw=2.4, mutation_scale=22))
    ax.plot([540, 540], [320, 440], color=SUB, lw=2.4)
    ax.annotate('', xy=(740, 440), xytext=(540, 440), arrowprops=dict(arrowstyle='-|>', color=SUB, lw=2.4, mutation_scale=22))
    box(ax, 740, 385, 300, 130, 'warn', 18, 2.4)
    t(ax, 890, 428, '외부 API', 20, PAL['warn'][2], True, 'center')
    t(ax, 890, 472, '쓴 만큼, 0건이면 0원', 15, PAL['warn'][2], False, 'center')
    t(ax, 40, 400, '위쪽(보라) 또는 아래쪽(주황)', 14.5, SUB)
    t(ax, 40, 430, '한 곳으로 분류 요청을 보낸다', 14.5, SUB)
    t(ax, 40, 575, '어느 쪽이 맞나?', 22, INK, True)
    box(ax, 30, 610, 500, 300, 'gpu', 18, 2.4)
    t(ax, 56, 650, 'GPU를 어차피 계속 쓴다면', 18, PAL['gpu'][2], True)
    for i, s in enumerate(['· 연구·학생 모델·다른 LLM 일에도', '  같은 GPU를 쓰는 경우', '· 분류만의 추가 비용이 거의 0', '· 일정·이름이 밖으로 안 나감', '· 단, GPU 한 대 고정 = 멈추면 같이 멈춤']):
        t(ax, 56, 695 + i * 34, s, 14.5, PAL['gpu'][2])
    t(ax, 280, 882, '→ 자체 모델 추천', 17, PAL['gpu'][2], True, 'center')
    box(ax, 550, 610, 500, 300, 'warn', 18, 2.4)
    t(ax, 576, 650, '분류만 위해 GPU를 새로 잡는다면', 18, PAL['warn'][2], True)
    for i, s in enumerate(['· 월 질문이 적을 때 훨씬 쌈', '  (월 1만 건: Sol 약 1.1만~4.9만원)', '· 5만~20만 건(Sol 기준)을 넘으면 역전', '· 일정·이름이 외부 사업자로 나감', '  → 약관 고지 필요']):
        t(ax, 576, 695 + i * 34, s, 14.5, PAL['warn'][2])
    t(ax, 800, 882, '→ 외부 API 추천', 17, PAL['warn'][2], True, 'center')
    box(ax, 30, 950, 1020, 190, 'plain', 18, 2)
    t(ax, 56, 988, '아직 모르는 것', 17, INK, True)
    for i, s in enumerate(['· 연 단위 계약 할인율 (공개 숫자 없음)', '· 서버리스(요청 때만 과금)의 콜드스타트 시간', '· Sol·Astra의 문제별 정확도', '· 팀당 실제 질문 수 (지금은 가정)']):
        t(ax, 56, 1030 + i * 28, s, 14.5, SUB)
    fig.savefig(os.path.join(OUT, 'fig4_추천_배포_구성.png'))
    plt.close(fig)


# ───────────────── 5. 증류 파일럿 ─────────────────
def fig5():
    steps = [
        ('done', '1', '연습문제 만들기', 'Claude가 여행자 10명 × 176문제 = 1,760문제', '11가지 유형 × 16문제, 정답 null 22%'),
        ('done', '2', '독립 검증', '만든 쪽과 따로 푼 풀이와 대조', '1,760 / 1,760 일치 (100%)'),
        ('done', '3', '조립', '시험지와 같거나 비슷한 122문제 제외', '학습 1,313문제 · 검증 325문제'),
        ('done', '4', '학습 (QLoRA)', 'Gemma 4 E4B를 4비트로 올려 LoRA만 학습', '329단계 · 148.7분 · 최대 GPU 10.6GB'),
        ('now', '5', '평가 (지금 진행 중)', '같은 모델의 「가르치기 전」과 「후」를 같은 문제로', '검증 325 → 시험지 835문제 순서'),
    ]
    H = 190 + len(steps) * 162 + 330
    fig, ax = canvas(H)
    head(ax, '작은 모델 가르치기 (증류 파일럿)', '작은 모델(E4B)에게 연습문제를 풀게 해 점수가 오르는지 본다')
    y = 160
    for k, n, a, b, c in steps:
        box(ax, 30, y, 1020, 146, k, 18, 2.2)
        ax.add_patch(plt.Circle((100, y + 73), 34, fc='white', ec=PAL[k][1], lw=2.4))
        t(ax, 100, y + 73, n, 24, PAL[k][2], True, 'center')
        t(ax, 160, y + 36, a, 20, PAL[k][2], True)
        t(ax, 160, y + 78, b, 15, PAL[k][2])
        t(ax, 160, y + 112, c, 15.5, PAL[k][2], True)
        y += 162
    box(ax, 30, y + 8, 1020, 150, 'plain', 18, 2)
    t(ax, 56, y + 42, '성공 기준 (평가를 보기 전에 정해 둠)', 17, INK, True)
    t(ax, 56, y + 80, '시험지 769문제(요청 둘 유형 제외)에서 가르치기 전보다', 14.5, SUB)
    t(ax, 56, y + 110, '3%p 이상 오르고, 같은 문제 짝비교 검정 p < 0.05', 14.5, SUB)
    box(ax, 30, y + 180, 1020, 130, 'warn', 18, 2)
    t(ax, 56, y + 214, '주의: 100% 일치의 한계', 17, PAL['warn'][2], True)
    t(ax, 56, y + 250, '만든 쪽과 푼 쪽이 같은 계열(Claude)이라 같은 약점을 공유했을 수 있음.', 14.5, PAL['warn'][2])
    t(ax, 56, y + 280, '연습문제가 시험지만큼 어렵다는 근거는 아님 — 평가로만 판단.', 14.5, PAL['warn'][2])
    fig.savefig(os.path.join(OUT, 'fig5_증류_파일럿.png'))
    plt.close(fig)


# ───────────────── 6. 코랩을 GPU 일꾼으로 ─────────────────
def fig6():
    H = 1500
    fig, ax = canvas(H)
    head(ax, '코랩을 GPU 일꾼으로 쓰는 방법', '무료 서버는 접수만, 코랩은 일감을 가져가 계산하고 결과를 돌려준다')
    for x, k, a, b in ((40, 'done', '고객·에이전트', '채팅·API 요청'), (390, 'now', '무료 서버', '접수 · 대기줄 · 앱'), (740, 'gpu', '코랩 일꾼', 'GPU 계산')):
        box(ax, x, 180, 300, 120, k, 18, 2.4)
        t(ax, x + 150, 222, a, 20, PAL[k][2], True, 'center')
        t(ax, x + 150, 264, b, 15, PAL[k][2], False, 'center')
    ax.annotate('', xy=(390, 240), xytext=(340, 240), arrowprops=dict(arrowstyle='-|>', color=SUB, lw=2.4, mutation_scale=22))
    ax.annotate('', xy=(690, 214), xytext=(740, 214), arrowprops=dict(arrowstyle='-|>', color='#534ab7', lw=2.4, mutation_scale=22))
    ax.annotate('', xy=(690, 266), xytext=(740, 266), arrowprops=dict(arrowstyle='-|>', color='#534ab7', lw=2.4, mutation_scale=22))
    t(ax, 715, 330, '① 코랩이 먼저 「일감 있나요?」 하고 가져감', 14.5, '#534ab7', True, 'center')
    t(ax, 715, 362, '② 계산한 결과를 서버에 올림', 14.5, '#534ab7', True, 'center')
    t(ax, 40, 420, '코랩은 밖으로만 연락하므로 공개 주소·터널이 필요 없다 (이 점은 약관의 「웹 서비스 제공」과 다름)', 14.5, SUB)
    box(ax, 30, 470, 1020, 200, 'now', 18, 2.4)
    t(ax, 56, 508, '되는 점', 19, PAL['now'][2], True)
    for i, s in enumerate(['· 비용: T4 기준 시간당 약 0.12달러 → 상시 흉내 내면 월 약 12만원', '  (RunPod 상시 약 24.5만원의 절반 정도)', '· 우리 앱은 무료 서버 하나에 그대로 두면 됨', '· 코랩이 끊겨도 일감은 서버 대기줄에 남음']):
        t(ax, 56, 548 + i * 33, s, 14.5, PAL['now'][2])
    box(ax, 30, 700, 1020, 430, 'bad', 18, 2.4)
    t(ax, 56, 738, '막히는 점 (공식 FAQ 확인)', 19, PAL['bad'][2], True)
    items = ['· 하루마다 끊김: 무료 최대 12시간, Pro+ 연속 최대 24시간', '  끊길 때마다 노트북을 다시 열어 실행해야 함 (자동 재시작은 못 찾음)', '· GPU 종류 보장 없음: T4가 걸리면 속도가 달라지고 바뀔 수 있음',
             '· 잔액이 떨어지면 무료 정책으로 돌아가 시간·사용량이 더 줄어듦', '· 약관 회색지대: 「웹 서비스 제공」 금지에는 안 걸리지만,', '  무료는 「분산 컴퓨팅 일꾼」이 명시 금지, 상시 고객 처리용은 취지와 어긋남', '· 끊기는 동안 고객 요청이 쌓임 → 「멈추면 서버를 끈다」는 결정과 충돌']
    for i, s in enumerate(items):
        t(ax, 56, 780 + i * 44, s, 14.5, PAL['bad'][2])
    box(ax, 30, 1160, 500, 300, 'gpu', 18, 2.4)
    t(ax, 56, 1198, '어울리는 일', 18, PAL['gpu'][2], True)
    for i, s in enumerate(['· 평가·학습 같은 배치', '  (끊겨도 이어서 하면 됨)', '· 우리 연구 시험을 코랩에', '  나눠 맡기는 것']):
        t(ax, 56, 1250 + i * 38, s, 14.5, PAL['gpu'][2])
    t(ax, 280, 1425, '→ 보조 용도 추천', 17, PAL['gpu'][2], True, 'center')
    box(ax, 550, 1160, 500, 300, 'warn', 18, 2.4)
    t(ax, 576, 1198, '어울리지 않는 일', 18, PAL['warn'][2], True)
    for i, s in enumerate(['· 고객 요청을 실시간으로', '  분류하는 경로', '· 하루 24시간 끊김 없이', '  돌아야 하는 서비스']):
        t(ax, 576, 1250 + i * 38, s, 14.5, PAL['warn'][2])
    t(ax, 800, 1425, '→ 쓰지 않기 추천', 17, PAL['warn'][2], True, 'center')
    fig.savefig(os.path.join(OUT, 'fig6_코랩_일꾼_방식.png'))
    plt.close(fig)


# ───────────────── 7. GPU 한 대가 감당하는 양을 넣은 비용 ─────────────────
def fig7():
    apis = {'Luna': ('#1d9e75', 0.25, 0.06), 'Sol': ('#ba7517', 4.93, 1.15), 'Astra': ('#c0392b', 24.64, 5.74)}
    fig = plt.figure(figsize=(10.8, 12.4), dpi=100)
    fig.patch.set_facecolor('white')
    fig.text(0.037, 0.972, 'GPU 한 대로 그 사용량을 감당할 수 있나?', fontsize=26, fontweight='bold', color=INK, va='center')
    fig.text(0.037, 0.943, '한 대는 월 약 100만 건까지 → 넘으면 대수가 늘어 비용이 계단처럼 오른다', fontsize=15, color=SUB, va='center')
    ax = fig.add_axes([0.13, 0.46, 0.82, 0.455])
    n = np.logspace(4, 7, 400)
    for name, (c, hi, lo) in apis.items():
        ax.fill_between(n, n * lo / 1e4, n * hi / 1e4, color=c, alpha=0.16, lw=0)
        ax.plot(n, n * hi / 1e4, color=c, lw=2.2)
        ax.plot(n, n * lo / 1e4, color=c, lw=2.2, ls='--')
    cost = np.ceil(n / 1e6) * 24.5
    ax.step(n, cost, where='pre', color='#534ab7', lw=4.2)
    ax.axvline(1e6, color='#534ab7', lw=1.4, ls=':')
    ax.axvline(2e6, color='#9aa3ad', lw=1.4, ls=':')
    ax.axvline(1e4, color='#374151', lw=1.4, ls='--')
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlim(1e4, 1e7)
    ax.set_ylim(0.1, 1000)
    ax.set_xticks([1e4, 1e5, 1e6, 1e7])
    ax.set_xticklabels(['1만', '10만', '100만', '1,000만'], fontsize=15)
    ax.set_yticks([0.1, 1, 10, 100, 1000])
    ax.set_yticklabels(['0.1', '1', '10', '100', '1,000'], fontsize=14)
    ax.set_xlabel('월 질문 수 (건)', fontsize=15, labelpad=6)
    ax.set_ylabel('월 비용 (만원)', fontsize=15, labelpad=6)
    ax.grid(True, which='major', color='#e5e7eb', lw=1)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    bb = dict(fc='white', ec='none', pad=2, alpha=0.9)
    ax.text(1.1e4, 38, 'GPU: 1대 24.5만원 → 2대 49만 → 3대 73.5만…', color='#534ab7', fontsize=13.5, fontweight='bold', zorder=6, bbox=bb)
    ax.text(1.04e6, 0.14, '한 대 안전선\n100만', color='#534ab7', fontsize=12.5, zorder=6, bbox=bb)
    ax.text(2.08e6, 0.14, '이론 최대\n200만', color='#6b7280', fontsize=12.5, zorder=6, bbox=bb)
    ax.text(1.1e4, 0.14, '가정\n월 1만 건', color='#374151', fontsize=12.5, zorder=6, bbox=bb)
    ax.text(3.2e6, 2.2, 'Luna', color='#1d9e75', fontsize=16, fontweight='bold')
    ax.text(2.4e5, 14, 'Sol', color='#ba7517', fontsize=16, fontweight='bold')
    ax.text(3.0e4, 150, 'Astra', color='#c0392b', fontsize=16, fontweight='bold')
    fig.text(0.037, 0.405, '월 질문 수별로 GPU 한 대가 얼마나 바쁜가', fontsize=17, fontweight='bold', color=INK)
    rows = [('Astra 손익분기', '월 1만~4.3만 건', '0.5~2%', '여유'), ('Sol 손익분기', '월 5만~21만 건', '2.5~10%', '여유'), ('Luna 손익분기', '월 100만 건', '약 50%', '안전선 끝'), ('Luna(캐시) 손익분기', '월 427만 건', '약 211%', '한 대로 불가')]
    y = 0.368
    cols = (0.04, 0.34, 0.64, 0.80)
    for h, x in zip(('구간', '질문 수', '가동률', '감당'), cols):
        fig.text(x, y, h, fontsize=14, color=SUB, fontweight='bold')
    y -= 0.032
    for r in rows:
        col = '#c0392b' if r[3] == '한 대로 불가' else INK
        for v, x in zip(r, cols):
            fig.text(x, y, v, fontsize=15.5, color=col, fontweight='bold' if x == cols[3] else 'normal')
        y -= 0.036
    fig.text(0.037, 0.178, '근거와 가정', fontsize=15.5, fontweight='bold', color=INK)
    for i, s in enumerate(['· 처리 속도: Gemma E4B 문제당 1.17~1.42초 (RTX 2000 Ada, 한 번에 한 건, 실측)',
                           '  → 24시간 풀가동 시 월 약 200만 건이 이론 최대',
                           '· 안전선 100만 = 가동률 50% (낮·밤 편차와 몰리는 시간 대비, 가정)',
                           '· 여러 건을 묶어 처리하면 더 늘 수 있음 (측정 안 함)',
                           '· 질문 수가 100만을 넘으면 Luna API가 GPU보다 싸짐 (정확도는 별개, 미측정)']):
        fig.text(0.037, 0.148 - i * 0.029, s, fontsize=13.5, color=SUB)
    fig.savefig(os.path.join(OUT, 'fig7_GPU_한_대_감당량.png'))
    plt.close(fig)


# ───────────────── 8. 증류 중간 결과 ─────────────────
def fig8():
    H = 1380
    fig, ax = canvas(H)
    head(ax, '가르친 결과 (중간)', '같은 작은 모델(Gemma E4B)을 가르치기 전과 후에 같은 문제로 채점 · 시험지 5세트 중 1세트까지')
    groups = [('새 여행자 일정 검증 325문제', 265 / 325 * 100, 320 / 325 * 100, '기준선만 맞음 1 · 가르친 쪽만 맞음 56', 'p < 0.0001'),
              ('시험지 mix10 160문제 (Codex가 쓴 문제)', 147 / 160 * 100, 158 / 160 * 100, '기준선만 맞음 0 · 가르친 쪽만 맞음 11', 'p = 0.001')]
    y = 190
    for name, b, l, d, p in groups:
        t(ax, 40, y, name, 19, INK, True)
        sc, x0 = 7.5, 190
        t(ax, 40, y + 62, '가르치기 전', 15.5, SUB)
        box(ax, x0, y + 38, b * sc, 50, 'done', 8, 2)
        t(ax, x0 + b * sc + 12, y + 63, f'{b:.1f}%', 17, INK, True)
        t(ax, 40, y + 128, '가르친 후', 15.5, SUB)
        box(ax, x0, y + 104, l * sc, 50, 'now', 8, 2)
        t(ax, x0 + l * sc + 12, y + 129, f'{l:.1f}%', 17, PAL['now'][2], True)
        t(ax, 40, y + 188, f'+{l - b:.1f}%p · {d} · {p}', 14.5, SUB)
        y += 270
    box(ax, 30, y - 10, 1020, 270, 'plain', 18, 2)
    t(ax, 56, y + 28, '같은 mix10에서 다른 모델과 나란히 (Gemma 12B·26B는 올라마)', 17, INK, True)
    refs = [('Gemma E4B 기준선', 91.9, 'done'), ('Gemma 12B', 92.5, 'done'), ('Gemma 26B-A4B', 94.4, 'done'), ('E4B + 가르침', 98.8, 'now')]
    yy = y + 70
    for nm, v, k in refs:
        t(ax, 56, yy + 17, nm, 14.5, INK)
        box(ax, 300, yy, (v - 85) * 40, 34, k, 6, 2)
        t(ax, 300 + (v - 85) * 40 + 10, yy + 17, f'{v:.1f}%', 15, INK, True)
        yy += 48
    box(ax, 30, y + 275, 1020, 300, 'warn', 18, 2)
    t(ax, 56, y + 312, '아직 확정이 아닌 이유', 18, PAL['warn'][2], True)
    for i, s in enumerate(['· 시험지 5세트 중 mix10 한 세트뿐 (mix11·12·8·9 남음)', '· 성공 기준은 769문제(요청 둘 제외) 전체로 판정 — 아직 판정 전',
                           '· 요청 둘 유형은 「먼저 말한 항목」 규칙까지 같이 배움 (제외 점수: mix10 92.7→98.7%)', '· 가르친 자료는 Claude가 만들었고 mix12도 Claude가 씀 → mix12는 유리할 수 있어 따로 봄']):
        t(ax, 56, y + 356 + i * 48, s, 14, PAL['warn'][2])
    fig.savefig(os.path.join(OUT, 'fig8_가르친_결과_중간.png'))
    plt.close(fig)


# ───────────────── 9. 하루 건수 시나리오 ─────────────────
def fig9():
    cap = 86400 / 1.28           # 한 대 하루 이론 최대 ≈ 67,500건 (Gemma E4B 문제당 1.28초 · RTX 2000 Ada · 한 번에 한 건)
    cards = [('Astra', '하루 1,000건', 1000, '월 3만 건', 'now', '한 대로 충분', '24.5만원 (1대)', '73.9만원', '17.2만원'),
             ('Sol', '하루 5,000건', 5000, '월 15만 건', 'now', '한 대로 충분', '24.5만원 (1대)', '73.9만원', '17.2만원'),
             ('Luna', '하루 10만 건', 100000, '월 300만 건', 'bad', '한 대로 불가 — 2대~3대 필요', '49만~73.5만원 (2~3대)', '73.9만원', '17.2만원')]
    H = 190 + 3 * 372 + 330
    fig, ax = canvas(H)
    head(ax, '하루 요청 수 시나리오 — RTX 2000 Ada 한 대로 되나?', '손익분기가 Luna 10만 · Sol 5천 · Astra 1천 건/일이라고 칠 때 (한 달 30일)')
    y = 160
    for name, day, n, mon, kind, verdict, gcost, a_hi, a_lo in cards:
        box(ax, 30, y, 1020, 356, 'plain' if kind != 'bad' else 'bad', 18, 2.2)
        t(ax, 56, y + 38, f'{name} — {day}', 22, INK, True)
        t(ax, 1024, y + 38, mon, 17, SUB, True, 'right')
        pct = 100 * n / cap
        t(ax, 56, y + 90, 'GPU 한 대가 하루 중 일하는 비율', 15, SUB)
        bx, bw, scale = 56, 880, 880 / 160
        ax.add_patch(Rectangle((bx, y + 112), bw, 30, fc='#e5e7eb', ec='none'))
        ax.add_patch(Rectangle((bx, y + 112), min(pct, 160) * scale, 30, fc=PAL[kind][1], ec='none'))
        for mark, lab in ((50, '안전선 50%'), (100, '이론 최대 100%')):
            ax.plot([bx + mark * scale] * 2, [y + 104, y + 150], color='#374151', lw=1.6, ls='--')
            t(ax, bx + mark * scale, y + 164, lab, 12.5, SUB, False, 'center')
        t(ax, (bx + min(pct, 160) * scale + 12) if pct < 30 else bx + 10, y + 127, f'{pct:.1f}%' if pct < 100 else f'{pct:.0f}% (한 대 한계 초과)', 15, INK if pct < 30 else 'white', True)
        box(ax, 56, y + 190, 440, 48, kind, 12, 2)
        t(ax, 276, y + 214, verdict, 16, PAL[kind][2], True, 'center')
        t(ax, 56, y + 276, f'GPU 월 비용   {gcost}', 16, INK, True)
        t(ax, 56, y + 314, f'API 월 비용   {a_hi} (캐시 없음) ~ {a_lo} (캐시 있음)', 16, INK, True)
        y += 372
    box(ax, 30, y + 4, 1020, 300, 'warn', 18, 2.2)
    t(ax, 56, y + 40, '읽는 법과 주의', 18, PAL['warn'][2], True)
    for i, s in enumerate(['· 세 시나리오는 API 비용이 모두 같음(질문 수 × 단가가 같아짐): 약 74만원 / 캐시가 걸리면 약 17만원', '· Astra·Sol 규모는 한 대로 충분, Luna 규모(하루 10만)는 한 대로는 밀림',
                           '· 한 대 한계: 문제당 1.28초로 하루 86,400초 → 최대 6.75만 건 (이론). 평균 초당 1.16건이 넘으면 대기줄이 계속 쌓임', '· 캐시는 같은 일정이 몇 분 안에 다시 올 때만 걸림 → 팀당 질문이 드물면 「캐시 없음」이 현실에 가까움',
                           '· 정확도는 비교 밖: 가르친 E4B는 mix10 98.8%, Luna·Sol·Astra는 문제별로 못 잼']):
        t(ax, 56, y + 82 + i * 40, s, 13.5, PAL['warn'][2])
    fig.savefig(os.path.join(OUT, 'fig9_하루_건수_시나리오.png'))
    plt.close(fig)


# ───────────────── 11. 가르친 결과 (최종) ─────────────────
def fig11():
    H = 1790
    fig, ax = canvas(H)
    head(ax, '가르친 결과 (최종) — 기준 통과', '시험지 5세트 769문제(요청 둘 유형 제외) · 같은 모델의 가르치기 전·후를 같은 문제로 채점')
    t(ax, 40, 190, '한 줄 결과', 20, INK, True)
    sc = 7.5
    t(ax, 40, 252, '가르치기 전', 16, SUB)
    box(ax, 190, 226, 89.47 * sc, 54, 'done', 8, 2)
    t(ax, 190 + 89.47 * sc + 12, 253, '89.5%', 18, INK, True)
    t(ax, 40, 322, '가르친 후', 16, SUB)
    box(ax, 190, 296, 97.53 * sc, 54, 'now', 8, 2)
    t(ax, 190 + 97.53 * sc + 12, 323, '97.5%', 18, PAL['now'][2], True)
    box(ax, 30, 376, 1020, 96, 'now', 16, 2.2)
    t(ax, 56, 408, '사전 등록 기준: +3%p 이상 · p < 0.05  →  통과', 18, PAL['now'][2], True)
    t(ax, 56, 444, '+8.1%p · 가르친 쪽만 맞음 69 / 기준선만 맞음 7 · p = 6e-14', 15.5, PAL['now'][2])
    t(ax, 40, 530, '세트별 (요청 둘 제외)', 20, INK, True)
    rows = [('mix8 (Codex)', 90.4, 97.5), ('mix9 (Codex)', 90.8, 98.0), ('mix10 (Codex)', 92.7, 98.7), ('mix11 (Codex)', 85.9, 94.6), ('mix12 (Claude)', 87.5, 98.8)]
    y = 570
    for nm, b, l in rows:
        t(ax, 40, y + 20, nm, 15, INK)
        box(ax, 250, y, b * 6.6, 18, 'done', 4, 1.5)
        box(ax, 250, y + 22, l * 6.6, 18, 'now', 4, 1.5)
        t(ax, 250 + l * 6.6 + 10, y + 22, f'{b:.1f} → {l:.1f}%', 14, INK, True, 'left', 'top')
        y += 62
    t(ax, 40, y + 24, '회색 = 가르치기 전, 초록 = 후. 모든 세트에서 p < 0.01', 13.5, SUB)
    y += 80
    t(ax, 40, y + 20, '같은 769문제에서 다른 모델과', 20, INK, True)
    refs = [('Gemma E4B (올라마)', 91.16, 'done'), ('Gemma 12B (올라마)', 91.42, 'done'), ('Gemma 26B-A4B (올라마)', 95.19, 'done'), ('가르친 E4B', 97.53, 'now'), ('Claude Fable · Opus', 99.35, 'gpu')]
    yy = y + 62
    for nm, v, k in refs:
        t(ax, 40, yy + 22, nm, 15, INK)
        box(ax, 300, yy, (v - 85) * 46, 44, k, 6, 2)
        t(ax, 300 + (v - 85) * 46 + 12, yy + 22, f'{v:.1f}%', 16, INK, True)
        yy += 58
    box(ax, 30, yy + 14, 1020, 110, 'plain', 16, 2)
    t(ax, 56, yy + 46, '짝비교 검정', 16, INK, True)
    t(ax, 56, yy + 76, '가르친 E4B는 26B-A4B보다 위 (p=0.01), Claude보다는 아래 (p=0.003)', 14.5, SUB)
    t(ax, 56, yy + 102, '올라마 E4B보다는 크게 위 (p=1e-9)', 14.5, SUB)
    yy += 150
    box(ax, 30, yy, 1020, 270, 'warn', 18, 2.2)
    t(ax, 56, yy + 36, '주의', 18, PAL['warn'][2], True)
    for i, s in enumerate(['· 학습 1회·평가 1회 — 반복 편차는 모름', '· 같은 4비트 하네스의 기준선(89.5%)이 올라마(91.2%)보다 낮음 → 올라마 기준 +6.4%p',
                           '· 학습 자료와 mix12의 저자가 같음(Claude): 이득이 더 큼 (+11.2%p)', '· 실제 고객 질문 분포는 아직 못 잼 · CPU 4코어에선 4B도 느려 따로 시험 필요']):
        t(ax, 56, yy + 78 + i * 44, s, 14, PAL['warn'][2])
    fig.savefig(os.path.join(OUT, 'fig11_가르친_결과_최종.png'))
    plt.close(fig)


# ───────────────── 12. 성능·금액·부하 한눈에 (v2 — API 점수 반영) ─────────────────
def fig12():
    H = 1400
    fig, ax = canvas(H)
    head(ax, '성능·금액·부하 한눈에 (v2)', '성능 = 요청 둘 제외 311문제(mix10+mix12)를 모두 같은 문제로 채점 · 금액 = 월(30일) 환산, 만원')
    cols = [('선택지', 40, 'left'), ('성능', 330, 'center'), ('하루 1천 건\n(월 3만)', 520, 'center'), ('하루 5천 건\n(월 15만)', 720, 'center'), ('하루 10만 건\n(월 300만)', 930, 'center')]
    for nm, x, ha in cols:
        t(ax, x, 190, nm, 14.5, SUB, True, ha)
    ax.plot([40, 1040], [226, 226], color=LINE, lw=2)
    rows = [
        ('자체 GPU', '가르친 E4B · RunPod', 98.7, 'gpu', [('24.5', '가동 1.5%', 'good'), ('24.5', '가동 7.4%', 'good'), ('49~73.5', '2~3대 · 148%', 'bad')]),
        ('Luna', 'API · 가장 쌈', 97.7, 'now', [('0.7', '캐시 0.2', 'best'), ('3.7', '캐시 0.9', 'best'), ('73.9', '캐시 17.2', 'warn')]),
        ('Sol', 'API', 99.0, 'now', [('14.8', '캐시 3.4', 'warn'), ('73.9', '캐시 17.2', 'warn'), ('1,478', '캐시 344', 'bad')]),
        ('Astra', 'API · 가장 비쌈', 99.7, 'now', [('73.9', '캐시 17.2', 'warn'), ('370', '캐시 86', 'bad'), ('7,392', '캐시 1,722', 'bad')]),
    ]
    tint = {'best': 'now', 'good': 'now', 'warn': 'warn', 'bad': 'bad'}
    y = 246
    for nm, sub, acc, k, cells in rows:
        box(ax, 30, y, 1020, 128, 'plain', 14, 1.6)
        t(ax, 46, y + 40, nm, 21, INK, True)
        t(ax, 46, y + 80, sub, 13.5, SUB)
        t(ax, 330, y + 46, f'{acc:.1f}%', 22, INK, True, 'center')
        t(ax, 330, y + 90, '311문제', 12.5, SUB, False, 'center')
        for (val, small, st), x in zip(cells, (520, 720, 930)):
            box(ax, x - 88, y + 16, 176, 96, tint[st], 12, 2)
            t(ax, x, y + 52, val, 21, PAL[tint[st]][2], True, 'center')
            t(ax, x, y + 90, small, 13, PAL[tint[st]][2], False, 'center')
        y += 142
    t(ax, 40, y + 14, '초록 = 비교적 쌈 · 노랑 = 비쌈 · 빨강 = 매우 비쌈 또는 한 대로 불가', 13, SUB)
    y += 56
    box(ax, 30, y, 1020, 200, 'now', 16, 2.2)
    t(ax, 56, y + 36, '읽는 법', 18, PAL['now'][2], True)
    for i, s in enumerate(['· 성능은 사실상 같다: 가르친 E4B(98.7%)와 Luna 97.7% · Sol 99.0% · Astra 99.7%는', '  같은 문제에서 서로 구분되지 않음 (짝비교 p = 0.4~1.0, 311문제로는 힘이 약함)',
                           '· 성능이 같다면 가장 싼 API(Luna)가 하루 5천 건까지 이기고, 하루 10만 건에서는', '  Luna(캐시 17만)·GPU(49~73만)가 비슷 → 자체 GPU는 하루 3만 건쯤부터 의미']):
        t(ax, 56, y + 76 + i * 30, s, 14, PAL['now'][2])
    y += 222
    box(ax, 30, y, 1020, 270, 'warn', 16, 2.2)
    t(ax, 56, y + 36, '숫자를 믿기 전에', 18, PAL['warn'][2], True)
    for i, s in enumerate(['· API 점수는 Codex CLI로 잰 것(에이전트 지시문 포함·생각 낮음) — 공정 비교 아님, 원시 API와 다를 수 있음',
                           '· 금액은 생각(추론) 토큰을 뺀 값: 실제는 출력 요금이 더해져 최대 약 2배 가능 (미측정)', '· Luna는 mix10에서 95.4%, mix12에서 100% — 세트에 따라 흔들림',
                           '· 한도·응답 시간·약관(일정이 외부로 나감)은 API 쪽 미확인', '· 가르친 E4B는 학습 1회·평가 1회, 실제 고객 질문은 아직 못 잼']):
        t(ax, 56, y + 76 + i * 36, s, 13.5, PAL['warn'][2])
    fig.savefig(os.path.join(OUT, 'fig12_성능_금액_부하_한눈에_v2.png'))
    plt.close(fig)


if __name__ == '__main__':
    fig1(); fig2(); fig3(); fig4(); fig5(); fig6(); fig7(); fig8(); fig9(); fig11(); fig12()
    print('done', sorted(f for f in os.listdir(OUT) if f.endswith('.png')))
