import json, sys
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
for f in ("Malgun Gothic", "NanumGothic"):
    if any(f in x.name for x in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = f; break
plt.rcParams["axes.unicode_minus"] = False
T = sys.argv[1]
fr = json.load(open(T + '/td-fresh-v1.json', encoding='utf-8'))
tr = json.load(open(T + '/td-training-v1.json', encoding='utf-8'))['summary']
va = json.load(open(T + '/td-validation-v1.json', encoding='utf-8'))['summary']
fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 5.4), gridspec_kw={'width_ratios': [1.6, 1]})
rows = fr['rows']; x = range(len(rows)); w = 0.38
a1.bar([i - w/2 for i in x], [r['static']['err'] for r in rows], w, color='#8c959f', label='지금 방식(고정 속도로 길 고르기)')
a1.bar([i + w/2 for i in x], [r['td']['err'] for r in rows], w, color='#1f6feb', label='새 방식(교통 속도로 길 고르기)')
a1.axhspan(-1000, 1000, color='#2da44e', alpha=0.08, label='±1,000원')
a1.axhline(0, color='black', lw=0.8)
a1.set_xticks(list(x)); a1.set_xticklabels([r['id'] for r in rows])
a1.set_ylabel('제품 미터 추정 - 카카오 웹 택시비(원)')
a1.set_title('새로 고정한 12쌍(2026-10-13 02:09 카카오 웹 관측)', fontsize=11)
a1.legend(fontsize=9, loc='lower left')
sets = [('학습 153', tr), ('검증 40', va), ('새 12', {'old': fr['summary']['static'], 'new': fr['summary']['td']})]
labels = [s[0] for s in sets]
old = [s[1]['old']['mae'] for s in sets]; new = [s[1]['new']['mae'] for s in sets]
xx = range(len(sets))
b1 = a2.bar([i - w/2 for i in xx], old, w, color='#8c959f', label='지금 방식')
b2 = a2.bar([i + w/2 for i in xx], new, w, color='#1f6feb', label='새 방식')
for b in list(b1) + list(b2):
    a2.text(b.get_x() + b.get_width()/2, b.get_height() + 30, f'{int(b.get_height()):,}', ha='center', fontsize=9)
a2.set_xticks(list(xx)); a2.set_xticklabels(labels)
a2.set_ylabel('평균 절대오차(원)'); a2.set_title('세 묶음 평균 오차', fontsize=11); a2.legend(fontsize=9)
fig.text(0.01, 0.01, '기준: 카카오 길찾기 택시 예상 요금(학습·검증은 2026-10-07 API 기록 재사용, 새 12쌍은 공개 웹 관측 · 개발자 API 0회). 실제 결제 금액이 아니다. 통행료 제외.', fontsize=8)
fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(sys.argv[2], dpi=110); print(sys.argv[2])
