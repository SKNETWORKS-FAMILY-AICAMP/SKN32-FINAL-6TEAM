from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parents[2];repo=root/'final_project_cs'
ev=repo/'wiki/records/evidence/2026-10-11_1515_단일방향_유턴금지'
out=repo/'wiki/records/reports/assets/2026-10-11_same_way_uturn'
out.mkdir(exist_ok=False)
d=json.loads((ev/'diagnosis.json').read_text(encoding='utf8'))
c=json.loads((ev/'car-comparison.json').read_text(encoding='utf8'))
plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':12})
fig=plt.figure(figsize=(12,7),facecolor='#f8fafc')
fig.text(.07,.94,'차량 경로에서 누락된 유턴 금지 2,219개를 추가했습니다',fontsize=21,weight='bold',color='#102a43')
fig.text(.07,.89,'로컬 수정·오프라인 재생 | OSM 2026-10-03 자료 | 실주행·운영 반영은 미확인',fontsize=12,color='#526577')
ax=fig.add_axes([.17,.57,.75,.22]);ax.set_facecolor('#f8fafc')
total=d['source_relations']
for y,n in [(1,d['old']),(0,d['new'])]:
    ax.barh(y,n,color='#197f79',height=.48)
    ax.barh(y,total-n,left=n,color='#dce3eb',height=.48)
    ax.text(n/2,y,f'{n:,}/{total:,} = {100*n/total:.1f}%',ha='center',va='center',color='white',weight='bold')
    ax.text(n+(total-n)/2,y,f'미적용 {total-n:,}',ha='center',va='center',color='#3e5063')
ax.set_yticks([1,0],['수정 전','수정 후']);ax.set_xlim(0,total);ax.set_xticks([])
ax.set_title('보유 자료의 회전 관계 적용 범위',loc='left',pad=16,weight='bold')
for spine in ax.spines.values():spine.set_visible(False)
fig.text(.07,.48,'서울 개발 좌표 100쌍에서 발견한 유턴 누락 경로',fontsize=15,weight='bold',color='#102a43')
fig.text(.07,.42,'수정 전 2/100쌍 → 수정 후 0/100쌍   ·   경로 계산 성공 100/100쌍',fontsize=14,color='#197f79',weight='bold')
for y,row in zip([.31,.23],c['changed']):
    a,b=row['before'],row['after']
    fig.text(.07,y,f"{a['a']} → {a['b']}",fontsize=13,weight='bold',color='#102a43')
    fig.text(.58,y,f"{a['distance_m']:,.0f}m → {b['distance_m']:,.0f}m  (+{b['distance_m']-a['distance_m']:.0f}m)",fontsize=13,color='#344e63')
fig.text(.07,.12,'새 유턴 관계를 모두 지키며 우회했습니다. 나머지 98쌍의 거리는 동일했습니다.',fontsize=12,color='#344e63')
fig.text(.07,.06,'분모 6,258 = 보유 그래프 관련 OSM 관계 수. 적용 비율은 전체 실사용 준비도·도로 법규 완전성·경로 정확도가 아닙니다.',fontsize=10,color='#526577')
path=out/'uturn-before-after-v1.png';assert not path.exists();fig.savefig(path,dpi=150,facecolor=fig.get_facecolor());plt.close(fig)
with (out/'chart-data-v1.json').open('x',encoding='utf8') as f:json.dump({'diagnosis':d,'comparison':c},f,ensure_ascii=False,indent=2)
print(path)
