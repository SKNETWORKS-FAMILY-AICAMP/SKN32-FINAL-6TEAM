import json, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
for f in ("Malgun Gothic", "NanumGothic"):
    if any(f in x.name for x in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = f; break
plt.rcParams["axes.unicode_minus"] = False
d = json.load(open(sys.argv[1], encoding='utf-8'))
rows = [r for r in d['rows'] if r['kind'] != 'dev']
ids = [r['id'] for r in rows]
def val(r, n):
    v = r[n]
    return None if 'm' not in v else (r[n + '_pct'], v['opt'])
fig, ax = plt.subplots(figsize=(12, 5.6))
x = range(len(rows)); wdt = 0.27
series = [('osm', 'OSM 지도만', '#8c959f', -wdt), ('seoul', '서울시 도보 자료만', '#d1242f', 0), ('min', '두 자료 중 검증된 짧은 길(새 규칙)', '#1f6feb', wdt)]
for key, label, col, off in series:
    xs, ys, hatch = [], [], []
    for i, r in enumerate(rows):
        if key == 'min':
            v = r['min_pct']; opt = False
        else:
            vv = val(r, key); v, opt = (vv if vv else (None, False))
        if v is None: continue
        xs.append(i + off); ys.append(max(min(v, 60), -60)); hatch.append(opt)
    bars = ax.bar(xs, ys, width=wdt, color=col, label=label)
    for b, h in zip(bars, hatch):
        if h: b.set_hatch('///'); b.set_alpha(0.45)
ax.axhspan(-10, 10, color='#2da44e', alpha=0.08, label='카카오 ±10% 안')
ax.axhline(0, color='black', lw=0.8)
ax.set_xticks(list(x)); ax.set_xticklabels(ids)
ax.set_ylabel('카카오 최단거리 대비 차이(%) · ±60% 에서 자름')
s = d['summary']['frozen_all']
ax.set_title(f"제품 계산 전에 고정한 15쌍 — ±10% 안: OSM {s['osm']['within10_of_all']}/15 · 서울시 {s['seoul']['within10_of_all']}/15 · 새 규칙 {s['min_rule']['within10_of_all']}/15  (빗금 = 접근 미검증으로 제품이 막는 값)", fontsize=10.5)
ax.legend(fontsize=9, loc='upper left', ncol=2)
fig.text(0.01, 0.01, "자료: 카카오맵 공개 웹(2026-10-12~13 관측, API 0회) · OSM road_graph_v2(© OpenStreetMap contributors) · 서울특별시 도보 네트워크(공공누리 1유형)", fontsize=8)
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(sys.argv[2], dpi=110); print(sys.argv[2])
