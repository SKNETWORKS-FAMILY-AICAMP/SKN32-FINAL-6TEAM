from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
tag = '2026-10-11_0421_혼합환승_제품운임_연결'
ev = cs / 'wiki/records/evidence' / tag
data = json.loads((ev / 'seoul-product-replay-v3.json').read_text(encoding='utf8'))
out = cs / 'wiki/records/reports/assets/2026-10-11_transfer_fare_product'
out.mkdir(parents=True, exist_ok=False)
font = FontProperties(fname='C:/Windows/Fonts/malgun.ttf')
plt.rcParams.update({'font.family': font.get_name(), 'axes.unicode_minus': False})
fig = plt.figure(figsize=(10.4, 7.4), facecolor='#f7f7f3')
fig.text(.07, .93, '혼합 환승 할인 예상액을 실제 안내에 연결했습니다', fontsize=20, fontweight='bold', color='#182c32')
fig.text(.07, .885, '기존 서울 좌표 12쌍에서 다시 찾은 혼합 경로 16개 · 로컬 제품 계산', fontsize=11, color='#526369')
fig.text(.07, .81, '할인 예상액이 표시되는 후보', fontsize=13, fontweight='bold', color='#182c32')
ax = fig.add_axes([.07, .65, .86, .12], facecolor='#f7f7f3')
ax.barh([1, 0], [16, 16], color='#e1e5e4', height=.55)
ax.barh([1, 0], [0, 16], color='#087f76', height=.55)
ax.text(.3, 1, '연결 전  0/16 = 0%', va='center', color='#526369', fontsize=12)
ax.text(.3, 0, '연결 후  16/16 = 100%', va='center', color='white', fontsize=12, fontweight='bold')
ax.set_xlim(0, 16)
ax.set_ylim(-.5, 1.5)
ax.axis('off')
ax = fig.add_axes([.31, .19, .62, .35], facecolor='#f7f7f3')
chosen = []
for ident in ('N020', 'N053', 'N015', 'N060'):
    row = next(r for r in data['rows'] if r['id'] == ident)
    option = next(o for o in row['options'] if len(o['legs']) == 2) if ident != 'N015' else row['options'][0]
    chosen.append((row, option))
labels = [r['from']['name'] + ' → ' + r['to']['name'] for r, _ in chosen]
old = [o['discount_before_sum'] for _, o in chosen]
new = [o['public']['fare_krw'] for _, o in chosen]
for i, (a, b) in enumerate(zip(old, new)):
    ax.plot([b, a], [i, i], color='#c1c9c8', linewidth=4)
    ax.scatter(a, i, s=85, color='#788788', zorder=3)
    ax.scatter(b, i, s=85, color='#087f76', zorder=3)
    ax.text(a + 90, i, f'{a:,}원', va='center', fontsize=11, color='#59696e')
    ax.text(b - 90, i, f'{b:,}원', va='center', ha='right', fontsize=11, color='#087f76', fontweight='bold')
ax.set_yticks(range(4), labels, fontsize=11)
ax.invert_yaxis()
ax.set_xlim(500, 5200)
ax.set_xticks([1000, 2000, 3000, 4000, 5000], ['1천', '2천', '3천', '4천', '5천 원'])
ax.tick_params(axis='both', length=0, pad=9, colors='#526369')
for spine in ax.spines.values():
    spine.set_visible(False)
ax.grid(axis='x', color='#e1e5e4', linewidth=.8)
ax.set_axisbelow(True)
fig.text(.07, .59, '같은 후보의 안내 금액 예시 4개', fontsize=13, fontweight='bold', color='#182c32')
fig.text(.59, .59, '● 기존 개별 요금 합', fontsize=10, color='#788788')
fig.text(.78, .59, '● 할인 예상액', fontsize=10, color='#087f76')
fig.text(.07, .095, '성인 1인 1카드·승하차 태그 조건 / 거리 모델 사용 / 조조 할인 미적용', fontsize=11, color='#182c32')
fig.text(.07, .052, '표시 연결 검증이며 요금 정확도 100%가 아닙니다. 신규 독립 웹 대조·실제 탑승·결제 측정은 아닙니다.', fontsize=10, color='#526369')
path = out / 'transfer-fare-before-after-v1.png'
assert not path.exists()
fig.savefig(path, dpi=160, facecolor=fig.get_facecolor())
with (out / 'chart-data-v1.json').open('x', encoding='utf8') as f:
    json.dump({'pairs': 12, 'options': 16, 'connected_before': 0, 'connected_after': 16,
               'examples': [{'label': label, 'before': a, 'after': b} for label, a, b in zip(labels, old, new)],
               'meaning': '연결된 후보 수, 정확도나 전체21개 기능 완료율이 아님'}, f, ensure_ascii=False, indent=2)
print(path)
