from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
root=Path(__file__).resolve().parents[2];cs=root/'final_project_cs'
ev=cs/'wiki/records/evidence/2026-10-11_0918_버스접근방향_진단'
a,b=[json.loads((ev/f'product-{s}.json').read_text(encoding='utf8')) for s in ('before','after')]
old={r['id']:r for r in a['rows']};rows=[]
for r in sorted(b['rows'],key=lambda r:r['id']):
    prev=old[r['id']]
    def planned(row):
        route=row['result'][0]
        return next(o for o in route['options'] if o['id']==route['planned'])
    before,after=planned(prev),planned(r)
    rows.append({'id':r['id'],'from':r['from']['name'],'to':r['to']['name'],
                 'walking_before_m':before['walk_m'],'walking_after_m':after['walk_m'],
                 'eta_before_min':before['eta_min'],'eta_after_min':after['eta_min'],
                 'start_before':prev['result'][1],'start_after':r['result'][1],
                 'before_label':before['label'],'after_label':after['label']})
out=cs/'wiki/records/reports/assets/2026-10-11_bus_access_pairs';out.mkdir(exist_ok=False)
with (out/'chart-data-v1.json').open('x',encoding='utf8') as f:json.dump(rows,f,ensure_ascii=False,indent=2)
font=FontProperties(fname='C:/Windows/Fonts/malgun.ttf');plt.rcParams.update({'font.family':font.get_name(),'axes.unicode_minus':False})
fig,ax=plt.subplots(figsize=(10.2,5.8),facecolor='#fafaf7');ax.set_facecolor('#fafaf7')
fig.subplots_adjust(left=.32,right=.88,top=.72,bottom=.22)
fig.text(.055,.92,'더 가까운 버스 정류장을 실제 경로 탐색에 추가했습니다',fontsize=18,weight='bold',color='#153937')
fig.text(.055,.855,'서울 개발 좌표 4쌍 재생: 1/4쌍에서 도보 감소 · 나머지 3/4쌍 동일',fontsize=12,color='#435654')
for i,r in enumerate(rows):
    before,after=r['walking_before_m'],r['walking_after_m']
    ax.barh(i+.16,before,height=.27,color='#aab5b3',label='수정 전' if i==0 else '')
    ax.barh(i-.16,after,height=.27,color='#187f73',label='수정 후' if i==0 else '')
    ax.text(max(before,after)+22,i,f'{before:,} → {after:,}m',va='center',fontsize=10)
ax.set_yticks(range(len(rows)),[r['from']+' → '+r['to'] for r in rows],fontsize=10)
ax.set_xlim(0,1450);ax.invert_yaxis();ax.set_xlabel('선택된 버스 경로의 승차 전·하차 후 보행망 거리 합 (m)',fontsize=10)
ax.legend(frameon=False,loc='upper right');ax.spines[['top','right','left']].set_visible(False)
ax.grid(axis='x',alpha=.12);ax.set_axisbelow(True)
fig.text(.055,.125,'압구정로데오 → 삼성역: 도보 797 → 438m / 계산 소요 28 → 27분 / 운임 1,500원 유지',fontsize=11,weight='bold',color='#17685e')
fig.text(.055,.06,'버스만 선택한 같은 좌표·목표 시각·자료로 계산 · 실제 탑승·신규 웹 대조 0건 · 운영 미반영',fontsize=10,color='#52605f')
fig.savefig(out/'bus-access-before-after-v1.png',dpi=170)
print(out/'bus-access-before-after-v1.png')
