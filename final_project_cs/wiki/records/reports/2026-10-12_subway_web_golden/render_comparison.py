"""보존한 실제 계산 결과로 지하철 웹 대조 그림을 새로 만든다."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

here = Path(__file__).resolve().parent
root = here.parents[4]
data = root / 'datasets/mobility/raw/subway_web_golden_20261012_v1'
gold = json.loads((data / 'golden-v3.json').read_text(encoding='utf-8'))['rows']
result = json.loads((data / 'comparison-v3.json').read_text(encoding='utf-8'))['rows']
for name in ('comparison.png', 'comparison.svg'):
    if (here / name).exists():
        raise SystemExit('기존 그림이 있습니다. 백업 후 새 이름으로 생성하세요.')
plt.rcParams.update({'font.family': 'Malgun Gothic', 'axes.unicode_minus': False,
                     'font.size': 11})
labels = ['홍대입구→을지로입구', '서울역→고속터미널 (노량진 환승)',
          '신논현→김포공항 (9호선 급행)', '강남→양재 (신분당선)',
          '강남→양재 (교대 환승)', '공덕→홍대입구 (공항철도)']
fig, axes = plt.subplots(1, 2, figsize=(13, 5.7), sharey=True)
for ax, key, title, unit in zip(axes, ['fare_krw', 'duration_min'],
                              ['요금: 6/6 일치', '소요 시간: ±5분 기준 5/6 충족'], ['원', '분']):
    for i, (g, r) in enumerate(zip(gold, result)):
        ax.barh(i-.18, g[key], height=.32, color='#275c98', label='웹 골든셋' if i == 0 else None)
        ax.barh(i+.18, r[key], height=.32, color='#d77b2f', label='우리 계산' if i == 0 else None)
        for delta, value in [(-.18, g[key]), (.18, r[key])]:
            ax.text(value + (25 if unit == '원' else .6), i+delta, f'{value:,}', va='center', fontsize=10)
    ax.set_title(title, loc='left', fontsize=14, pad=18)
    ax.set_xlabel(unit)
    ax.set_xlim(0, 3200 if unit == '원' else 45)
    ax.spines[['top', 'right', 'left']].set_visible(False)
    ax.grid(axis='x', alpha=.13)
axes[0].set_yticks(range(len(labels)), labels)
axes[0].invert_yaxis()
axes[0].legend(loc='lower right', frameon=False)
fig.suptitle('지하철 웹 골든셋 · 2026-10-12', x=.04, ha='left', fontsize=18)
fig.text(.04, .02, '성인 교통카드 · 첫 승차~최종 하차 · 초기 대기 제외, 환승 대기 포함 · 5개 역쌍 / 6개 경로', fontsize=10)
fig.tight_layout(rect=[0, .07, 1, .92])
fig.savefig(here / 'comparison.png', dpi=160)
fig.savefig(here / 'comparison.svg')
print('그림 2개 저장')
