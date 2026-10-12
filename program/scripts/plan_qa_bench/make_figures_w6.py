# 6주차 「서비스 테스트 계획 및 결과 보고서」에 넣을 그림 4장 — 값은 이 저장소의 측정 결과에서 그대로 옮겼다(출처는 그림 아래 한 줄).
#  출력: program/산출물양식/w6/서비스테스트보고서/_재료/그림/*.png (기존 파일이 있으면 _backup 폴더로 먼저 복사한다)
import os
import shutil
import time

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, '..', '..', '산출물양식', 'w6', '서비스테스트보고서', '_재료', '그림'))
os.makedirs(OUT, exist_ok=True)
BK = os.path.join(OUT, '_backup', time.strftime('%Y-%m-%d_%H%M') + '_그림')
if any(f.endswith('.png') for f in os.listdir(OUT)):
    os.makedirs(BK, exist_ok=True)
    for f in os.listdir(OUT):
        if f.endswith('.png'):
            shutil.copy2(os.path.join(OUT, f), BK)
BLUE, GRAY, TEAL, AMBER, RED = '#2f6fb3', '#9aa3ad', '#1d9e75', '#d98e1f', '#c0392b'


def save(fig, name):
    fig.savefig(os.path.join(OUT, name), dpi=170, bbox_inches='tight', facecolor='white')
    plt.close(fig)


# ① 가르치기 전후 + 시드 변동 (769문제, 요청 둘 제외, 엄격 계수)
fig, ax = plt.subplots(figsize=(7.2, 3.6))
labels = ['파인튜닝 전 E4B', '파인튜닝한 E4B (시드 1)', '파인튜닝한 E4B (시드 2)', 'Winnow-E4B\n(Jev 계열, 파인튜닝 전)', '파인튜닝한 Winnow-E4B\n(Jev 계열, 시드 1개)']
vals = [688, 750, 760, 655, 756]
cols = [GRAY, BLUE, BLUE, GRAY, TEAL]
y = range(len(vals))[::-1]
ax.barh(list(y), vals, color=cols, height=0.62)
for yi, v in zip(y, vals):
    ax.text(v + 3, yi, f'{v}/769 = {100 * v / 769:.1f}%', va='center', fontsize=9)
ax.set_yticks(list(y))
ax.set_yticklabels(labels, fontsize=9)
ax.set_xlim(600, 850)
ax.set_xlabel('정답 수 (769문제)', fontsize=9)
ax.set_title('파인튜닝하면 크게 오르지만, 학습 한 번의 차이(750~760)도 크다', fontsize=11)
ax.spines[['top', 'right']].set_visible(False)
fig.text(0.01, -0.04, '출처: 마스터 문서 §92-6·§92-9 (시드 1개씩의 모델 사이 비교는 순위를 매기지 않는다)', fontsize=7.5, color='#555')
save(fig, 'fig_가르치기_전후와_시드.png')

# ② 규정 검색 개선 전후 — Recall@k (독립 B 48문제 · A 100문제)
fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.3), sharey=True)
data = {'블라인드 평가셋 B (48문제)': ([0.375, 0.625, 0.667], [0.521, 0.729, 0.792]), '개발 평가셋 A (100문제)': ([0.660, 0.820, 0.850], [0.820, 0.930, 0.960])}
for ax, (title, (b, a)) in zip(axes, data.items()):
    xs = range(3)
    ax.bar([x - 0.2 for x in xs], b, 0.38, color=GRAY, label='현행 인덱싱(본문, 개선 전)')
    ax.bar([x + 0.2 for x in xs], a, 0.38, color=BLUE, label='인덱스 E(개선 후)')
    for x, v in zip(xs, b):
        ax.text(x - 0.2, v + 0.015, f'{v:.2f}', ha='center', fontsize=8)
    for x, v in zip(xs, a):
        ax.text(x + 0.2, v + 0.015, f'{v:.2f}', ha='center', fontsize=8)
    ax.axhline(0.90, color=RED, lw=1, ls='--')
    ax.text(-0.48, 0.915, '양식 목표 0.90', color=RED, fontsize=7.5, ha='left', va='bottom')
    ax.set_xticks(list(xs))
    ax.set_xticklabels(['Recall@1', 'Recall@3', 'Recall@5'], fontsize=9)
    ax.set_title(title, fontsize=10)
    ax.set_ylim(0, 1.05)
    ax.spines[['top', 'right']].set_visible(False)
axes[0].legend(fontsize=8, loc='upper center', bbox_to_anchor=(1.08, -0.1), ncol=2, frameon=False)
fig.suptitle('규정 검색: 인덱싱을 바꾸면 오르지만 블라인드 평가셋은 아직 목표에 못 미친다', fontsize=11, y=1.02)
fig.text(0.01, -0.14, '출처: RAG 평가 지표 리포트 §7 (질문은 모두 합성, 1회 측정)', fontsize=7.5, color='#555')
save(fig, 'fig_규정검색_개선전후.png')

# ③ 섞은 흐름 2,735문제 — 네 구조
fig, axes = plt.subplots(1, 3, figsize=(8.2, 3.7))
names = ['단독', '규칙', '규칙\n+ML', '규칙+ML\n+Jev 계열']
cols = [GRAY, GRAY, BLUE, AMBER]
panels = [('전체 정답 (%)', [90.8, 90.6, 91.9, 89.4], 86, 94, '{:.1f}'), ('정답이 없는데\n항목을 짚음 (%)', [4.5, 4.6, 3.2, 0.5], 0, 6, '{:.1f}'), ('전문가 모델\n호출 (%)', [100, 95, 77, 28], 0, 110, '{:.0f}')]
for ax, (t, v, lo, hi, fmt) in zip(axes, panels):
    ax.bar(range(4), v, color=cols, width=0.62)
    for i, x in enumerate(v):
        ax.text(i, x + (hi - lo) * 0.015, fmt.format(x), ha='center', fontsize=8.5)
    ax.set_ylim(lo, hi)
    ax.set_xticks(range(4))
    ax.set_xticklabels(names, fontsize=8)
    ax.set_title(t, fontsize=9.5)
    ax.spines[['top', 'right']].set_visible(False)
fig.suptitle('혼합 트래픽 테스트: 일정과 무관한 말이 섞이면 ML 앞단이 이득 (단독 대비 37 : 8, p=0.000015)', fontsize=10.5, y=1.12)
fig.text(0.01, -0.12, '단독 = 파인튜닝한 E4B만 · 규칙 = 규칙→파인튜닝한 E4B · 규칙+ML = 규칙→ML 판별기→파인튜닝한 E4B · 규칙+ML+Jev 계열 = 사이에 파인튜닝 전 Winnow-E4B\n출처: 평가 리포트 §3-2, 2,669문제(복수 항목 질의 제외). 파인튜닝 전 Jev 계열 모델은 파인튜닝한 모델과 공정한 비교가 아님', fontsize=7.2, color='#555')
save(fig, 'fig_섞은흐름_네구조.png')

# ④ 긴급도 분류 — 클래스별 F1: 학습 없는 LLM 제로샷 → 학습한 분류기 (CX 400)
fig, ax = plt.subplots(figsize=(7.0, 3.3))
cls = ['low\n(166)', 'medium\n(83)', 'high\n(88)', 'critical\n(16)']
before = [0.79, 0.32, 0.46, 0.55]
after = [0.93, 0.81, 0.87, 0.81]
xs = range(4)
ax.bar([x - 0.2 for x in xs], before, 0.38, color=GRAY, label='파인튜닝하지 않은 LLM(Gemma-4 E4B 제로샷)')
ax.bar([x + 0.2 for x in xs], after, 0.38, color=TEAL, label='파인튜닝한 분류기(e5-base)')
for x, v in zip(xs, before):
    ax.text(x - 0.2, v + 0.015, f'{v:.2f}', ha='center', fontsize=8.5)
for x, v in zip(xs, after):
    ax.text(x + 0.2, v + 0.015, f'{v:.2f}', ha='center', fontsize=8.5)
ax.set_xticks(list(xs))
ax.set_xticklabels(cls, fontsize=9)
ax.set_ylim(0, 1.08)
ax.set_ylabel('클래스별 F1', fontsize=9)
ax.legend(fontsize=8, loc='upper left', ncol=1)
ax.set_title('긴급도: 파인튜닝하면 약한 클래스(medium · high)가 크게 오른다', fontsize=11)
ax.spines[['top', 'right']].set_visible(False)
fig.text(0.01, -0.06, '출처: 평가 리포트 §2, CX 400 (칸 안 숫자 = 정답이 그 클래스인 질문 수) · 파인튜닝한 분류기는 시드 1개', fontsize=7.5, color='#555')
save(fig, 'fig_긴급도_클래스별.png')
print('saved', sorted(f for f in os.listdir(OUT) if f.endswith('.png')))
