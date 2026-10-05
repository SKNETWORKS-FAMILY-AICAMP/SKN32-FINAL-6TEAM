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


if __name__ == '__main__':
    fig1(); fig2(); fig3(); fig4(); fig5(); fig6()
    print('done', sorted(f for f in os.listdir(OUT) if f.endswith('.png')))
