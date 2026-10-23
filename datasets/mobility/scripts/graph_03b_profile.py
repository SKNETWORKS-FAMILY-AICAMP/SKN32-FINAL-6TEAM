# datasets/mobility/scripts/graph_03b_profile.py — 택시·자동차 소요의 도로 구간별 시간대 속도(graph/ 5파일) 만들기 ③b · 인자 fix34(정본)
#   원래 이름 03b_profile_test.py · 원래 자리 DATA_DIR\travel\processed\mobility\graph\_build\ (2026-09-19 · 9/30 저장소 사본 · 82 에서 이 자리로)
#   ★ **작업 폴더를 cwd 로 두고** 실행한다 — 입력·중간 산출을 전부 cwd 상대경로로 읽고 쓴다(원래 방식 그대로 · 코드 무변경):
#       cd <DATA_DIR>\travel\processed\mobility\graph\_build ;  python <저장소>\datasets\mobility\scripts\graph_03b_profile.py
#   입력(cwd 기준): speed/*.npz · osm_way_seg_topis_link_v1.csv · osm_way_geom_v1.csv   →   출력(cwd): topis_link_profile_v1.jsonl(→ gz) · topis_class_factor_v1.json · daytype_calendar_v1.csv(판정기가 읽음)
#   순서·결과를 판정기 자리로 옮기는 법은 README 「갱신 순서」.
"""③ 링크×요일형×시간대 프로파일(학습 2025-09~2026-05) + 도로급 계수 + 그래프측 시험(2026-06~08, OSM 세그먼트 길이 기준 도로 단위 오차)."""
import numpy as np, pandas as pd, json, time, datetime as dt, holidays, sys
t0=time.time(); CAL=sys.argv[1] if len(sys.argv)>1 else 'fix34'   # 34번(9/21): 정본은 fix34 — pkg·fix 는 18번 기록 재현용
months=['202509','202510','202511','202512','202601','202602','202603','202604','202605','202606','202607','202608']
parts=[np.load(f'speed/topis_{m}.npz',allow_pickle=True) for m in months]
link=np.concatenate([p['link'] for p in parts]); date=np.concatenate([p['date'] for p in parts]); dist=np.concatenate([p['dist'] for p in parts]); cls=np.concatenate([p['cls'] for p in parts]); V=np.concatenate([p['v'] for p in parts])
print('rows',len(link),'sec',round(time.time()-t0))
# 요일형
ud=np.unique(date); hk=holidays.KR(years=[2025,2026])
hol=set(d for d in hk)
if CAL=='fix':    # 18번 판(9/20) — ★틀렸다: 2026-01 법 개정으로 2026-07-17 제헌절은 공휴일이다(25번 확인 · 34번 정정). 기록 재현용으로만 남긴다
    hol.discard(dt.date(2026,7,17)); hol.add(dt.date(2025,10,2))
if CAL=='fix34':  # 정본(34번 · 2026-09-21) — 패키지 그대로(07-17 공휴일) + 2025-10-02 임시공휴일
    hol.add(dt.date(2026,7,17)); hol.add(dt.date(2025,10,2))
def dtype(d):
    dd=dt.date(d//10000,(d//100)%100,d%100)
    if dd in hol or dd.weekday()==6: return '휴일'
    if dd.weekday()==5: return '토요일'
    return '평일'
dmap={int(d):dtype(int(d)) for d in ud}
cal=pd.DataFrame({'date':ud,'daytype':[dmap[int(d)] for d in ud]}); cal['is_holiday']=[dt.date(int(d)//10000,(int(d)//100)%100,int(d)%100) in hol for d in ud]
daytype=np.array([dmap[int(d)] for d in date])
test=date>=20260601
# 프로파일: link×daytype×hour 평균 (학습기간)
lc=pd.Categorical(link); dc=pd.Categorical(daytype,categories=['평일','토요일','휴일'])
def prof(mask, keys_link=True):
    n=mask.sum(); Ls=np.repeat(lc.codes[mask],24); Ds=np.repeat(dc.codes[mask],24); Hs=np.tile(np.arange(24,dtype=np.int8),n); Vs=V[mask].ravel()
    ok=~np.isnan(Vs)
    df=pd.DataFrame({'l':Ls[ok],'d':Ds[ok],'h':Hs[ok],'v':Vs[ok]})
    g=df.groupby(['l','d','h'])['v'].agg(['mean','count','std',lambda s:s.quantile(.1),lambda s:s.quantile(.9)]); g.columns=['mean','n','std','p10','p90']
    return g
P=prof(~test); print('프로파일 셀', len(P), '셀당 관측일 중앙값', P['n'].median(), 'sec',round(time.time()-t0))
# 링크 속성
lm=pd.DataFrame({'l':lc.codes,'dist':dist,'cls':cls}).drop_duplicates('l').set_index('l')
# 도로급 계수: cls×daytype×hour 평균속도(학습) 및 야간 자유속도 대비 비율
tr=~test; Cs=np.repeat(pd.Categorical(cls[tr]).codes,24); ccat=pd.Categorical(cls[tr]).categories
Ds=np.repeat(dc.codes[tr],24); Hs=np.tile(np.arange(24,dtype=np.int8),tr.sum()); Vs=V[tr].ravel(); ok=~np.isnan(Vs)
CF=pd.DataFrame({'c':Cs[ok],'d':Ds[ok],'h':Hs[ok],'v':Vs[ok]}).groupby(['c','d','h'])['v'].mean()
# 시험: 링크 단위 (analyze2 B 재현)
te=test; n=te.sum(); Ls=np.repeat(lc.codes[te],24); Ds=np.repeat(dc.codes[te],24); Hs=np.tile(np.arange(24,dtype=np.int8),n); Vs=V[te].ravel(); Dd=np.repeat(date[te],24); Cs=np.repeat(pd.Categorical(cls[te],categories=ccat).codes,24)
ok=~np.isnan(Vs); T=pd.DataFrame({'l':Ls[ok],'d':Ds[ok],'h':Hs[ok],'v':Vs[ok],'date':Dd[ok],'c':Cs[ok]})
T=T.join(P['mean'].rename('pB'),on=['l','d','h']).join(CF.rename('pA'),on=['c','d','h'])
x=T.dropna(subset=['pB']); ape=((x.v-x.pB).abs()/x.v)
print(f'[링크 B] n={len(x):,} MAPE {ape.mean()*100:.1f}% ±20% {(ape<=.2).mean()*100:.1f}%  (14번: 8.7% / 91.0%)')
x=T.dropna(subset=['pA']); ape=((x.v-x.pA).abs()/x.v); print(f'[링크 A] MAPE {ape.mean()*100:.1f}% (14번: 27.9%)')
# 도로 단위 (14번 analyze2 방식 재현: 도로명×방향 링크≥5, 길이≥2km)
master=pd.read_csv('raw/topis/_check/link_master_20250901_20260831.csv',dtype={'링크아이디':str},encoding='utf-8-sig').set_index('링크아이디')
lid=np.array(lc.categories); road=pd.Series(master['도로명']+'|'+master['방향']).reindex(lid).to_numpy()
T['road']=pd.Categorical(road[T['l'].to_numpy()]); T['dist']=lm['dist'].reindex(T['l']).to_numpy()
nl=T.groupby('road',observed=True)['l'].nunique(); big=nl[nl>=5].index
def road_test(T, dcol, label):
    x=T[T['road'].isin(big)].dropna(subset=['pA','pB']).copy()
    for c in ['v','pA','pB']: x['t_'+c]=x[dcol]/x[c]*3.6
    g=x.groupby(['road','date','h'],observed=True)[['t_v','t_pA','t_pB','dist']].sum(); g=g[g['dist']>=2000]
    out={}
    for c in ['pA','pB']:
        ape=(g['t_v']-g['t_'+c]).abs()/g['t_v']; out[c]=dict(MAPE=round(float(ape.mean())*100,2),med=round(float(ape.median())*100,2),in20=round((ape<=.2).mean()*100,1),p90=round(ape.quantile(.9)*100,1))
        print(f'[{label} {c}] 도로 {g.index.get_level_values(0).nunique()} 표본 {len(g):,} MAPE {out[c]["MAPE"]}% med {out[c]["med"]}% ±20% {out[c]["in20"]}% p90 {out[c]["p90"]}%')
    return out
res_link=road_test(T,'dist','TOPIS길이')
# 그래프측: OSM 세그먼트 길이로 치환 (매칭 결과) — 링크마다 매칭된 OSM 세그먼트 길이 합
sg=pd.read_csv('osm_way_seg_topis_link_v1.csv',dtype={'link_id':str})
# 34번: 클라우드 임시 파일 osm_car_ways.pkl 대신 산출물 osm_way_geom_v1.csv 에서 세그먼트 길이를 잰다(결과 동일 — fix 재현 4.43% 확인)
from pyproj import Geod; geod=Geod(ellps='WGS84')
seglen={}
for r_ in pd.read_csv('osm_way_geom_v1.csv').itertuples(index=False):
    wid=r_.osm_way_id; pts=[tuple(map(float,q.split(','))) for q in r_.pts.split()]
    lon=[p[0] for p in pts]; lat=[p[1] for p in pts]
    for i in range(len(pts)-1): seglen[(wid,i)]=geod.inv(lon[i],lat[i],lon[i+1],lat[i+1])[2]
sg['len']=[seglen[(w,i)] for w,i in zip(sg.osm_way_id,sg.seg_idx)]
osm_len=sg.groupby('link_id')['len'].sum()
T['osm_dist']=osm_len.reindex(lid[T['l'].to_numpy()]).to_numpy()
r=(osm_len.reindex(lm.index.map(lambda i: lid[i]))/lm['dist'].to_numpy()); print('OSM 세그길이/TOPIS 거리 중앙값', round(float(np.nanmedian(r)),3), '±10% 안', int((np.abs(r-1)<=.1).sum()),'/',int(r.notna().sum()))
T2=T.dropna(subset=['osm_dist']); res_graph=road_test(T2,'osm_dist','OSM길이')
# 산출
P2=P.reset_index(); P2['link_id']=lid[P2['l']]; P2['daytype']=np.array(['평일','토요일','휴일'])[P2['d']]; P2['hour']=P2['h'].astype(int)
P2=P2[['link_id','daytype','hour','mean','n','std','p10','p90']].rename(columns={'mean':'mean_kmh','n':'n_days'})
with open('topis_link_profile_v1.jsonl','w') as f:
    for r_ in P2.itertuples(index=False):
        f.write(json.dumps({'link_id':r_.link_id,'daytype':r_.daytype,'hour':int(r_.hour),'mean_kmh':round(float(r_.mean_kmh),2),'n_days':int(r_.n_days),'std':round(float(r_.std),2) if r_.std==r_.std else None,'p10':round(float(r_.p10),1),'p90':round(float(r_.p90),1)},ensure_ascii=False)+'\n')
CF2=CF.reset_index(); CF2['cls']=np.array(ccat)[CF2['c']]; CF2['daytype']=np.array(['평일','토요일','휴일'])[CF2['d']]
cf={}
for c in ccat:
    ff=CF2[(CF2.cls==c)&(CF2.h.isin([3,4]))]['v'].mean()
    cf[c]={'free_flow_kmh_0304':round(float(ff),1),'factor':{d:[round(float(CF2[(CF2.cls==c)&(CF2.daytype==d)&(CF2.h==h)]['v'].iloc[0]/ff),3) for h in range(24)] for d in ['평일','토요일','휴일']},'mean_kmh':{d:[round(float(CF2[(CF2.cls==c)&(CF2.daytype==d)&(CF2.h==h)]['v'].iloc[0]),1) for h in range(24)] for d in ['평일','토요일','휴일']}}
json.dump({'source':'topis_speed_daily 2025-09~2026-05 (train)','hour_index':'0=00:00-01:00 (원 열 ~01시)','daytype':['평일','토요일','휴일'],'osm_class_map':{'motorway':'도시고속도로','trunk':'도시고속도로','primary':'주간선도로','secondary':'보조간선도로','tertiary':'기타도로','*_link':'상위 급과 동일','unclassified/residential/living_street/service':'근거없음 → OSM 기본속도'},'classes':cf,'test_2026_06_08':{'link_MAPE_A':None},'calendar':CAL},open('topis_class_factor_v1.json','w'),ensure_ascii=False,indent=1)
cal.to_csv('daytype_calendar_v1.csv',index=False)
json.dump({'calendar':CAL,'road_test_topis_len':res_link,'road_test_osm_len':res_graph,'profile_cells':len(P),'train':'2025-09~2026-05','test':'2026-06~08'},open(f'step3_result_{CAL}.json','w'),ensure_ascii=False,indent=1)
print('sec',round(time.time()-t0))
