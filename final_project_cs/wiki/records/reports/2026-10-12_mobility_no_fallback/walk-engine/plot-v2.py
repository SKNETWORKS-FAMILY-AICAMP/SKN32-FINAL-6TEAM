"""실제 반환 형상과 출입점 붙임을 좌표 그대로 시각화합니다."""
from pathlib import Path
import json,math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
P=Path(__file__).resolve().parent
d=json.loads((P/'diagnosis-v1.json').read_text(encoding='utf-8'))
plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':10})
s=d['snaps'][0]['input'];e=d['snaps'][1]['input']
kx=math.cos(math.radians(s[1]))*111320;ky=110540
def xy(pts):return [(p[0]-s[0])*kx for p in pts],[(p[1]-s[1])*ky for p in pts]
fig,ax=plt.subplots(figsize=(10,9),facecolor='white')
for ed in d['nearby_edges']:
    if not ed['foot']:continue
    x,y=xy(ed['coordinates'])
    ax.plot(x,y,color='#c3cbd4' if ed['fmain'] else '#a96ac8',lw=1 if ed['fmain'] else 2,alpha=.8,zorder=1)
for sn in d['snaps']:
    x,y=xy([sn['input'],sn['snap']]);ax.plot(x,y,'--',color='#d77c18',lw=3,zorder=4)
x,y=xy(d['astar']['points']['coordinates']);ax.plot(x,y,color='#176eb6',lw=3,zorder=3)
for name,p,color in [('출발',s,'#14724c'),('도착',e,'#b53b3b')]:
    x,y=xy([p]);ax.scatter(x,y,color=color,s=65,zorder=5)
    ax.annotate(name,(x[0],y[0]),xytext=(8,9),textcoords='offset points',color=color,weight='bold')
ax.annotate('도착 접근 직선 40.99m',xy=tuple(z[0] for z in xy([d['snaps'][1]['snap']])),xytext=(250,270),textcoords='data',
            arrowprops={'arrowstyle':'->','color':'#d77c18'},color='#a35a00')
ax.set_xlim(-120,520);ax.set_ylim(-100,440);ax.set_aspect('equal',adjustable='box')
ax.set_xlabel('출발점 기준 동쪽 거리(m)');ax.set_ylabel('출발점 기준 북쪽 거리(m)')
ax.grid(color='#eceff2',lw=.7)
ax.set_title('도보 거리 차이 진단: 실제 OSM 반환 형상\n요청 좌표 동일 · 카카오 최단 672m / 제품 742.65m',loc='left',fontsize=14,pad=17)
ax.legend(handles=[Line2D([0],[0],color='#176eb6',lw=3,label='제품 도로 형상 693.20m'),
                   Line2D([0],[0],color='#d77c18',lw=3,ls='--',label='도로까지 접근 직선 합계 49.45m'),
                   Line2D([0],[0],color='#c3cbd4',lw=2,label='주변 연결된 도보 길'),
                   Line2D([0],[0],color='#a96ac8',lw=2,label='큰 도로망과 분리된 도보 길')],loc='lower right',frameon=True)
fig.text(.11,.03,'회색·보라색은 보유 OSM 그래프입니다. 카카오 상세 형상은 아직 좌표로 확보하지 않아 그리지 않았습니다.\nA*와 다익스트라 결과는 742.65m로 같습니다. 실제 보행 측정이나 전체 기능 완료 판정이 아닙니다.',fontsize=9,color='#4c535b')
fig.subplots_adjust(bottom=.14,top=.86)
for name in ['route-diagnosis-v2.svg','route-diagnosis-v2.png']:
    path=P/name
    if path.exists():raise FileExistsError(path)
    fig.savefig(path,dpi=160)
print('route-diagnosis-v2.svg / route-diagnosis-v2.png 저장 완료')
