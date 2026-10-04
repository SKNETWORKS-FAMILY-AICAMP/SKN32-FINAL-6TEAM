# datasets/mobility/scripts/graph_02b_match.py — 택시·자동차 소요의 도로 구간별 시간대 속도(graph/ 5파일) 만들기 ②b
#   원래 이름 02b_match.py · 원래 자리 DATA_DIR\travel\processed\mobility\graph\_build\ (2026-09-19 · 9/30 저장소 사본 · 82 에서 이 자리로)
#   ★ **작업 폴더를 cwd 로 두고** 실행한다 — 입력·중간 산출을 전부 cwd 상대경로로 읽고 쓴다(원래 방식 그대로 · 코드 무변경):
#       cd <DATA_DIR>\travel\processed\mobility\graph\_build ;  python <저장소>\datasets\mobility\scripts\graph_02b_match.py
#   입력(cwd 기준): osm_car_ways.pkl · topis_link_geom_v1.geojson   →   출력(cwd): osm_way_seg_topis_link_v1.csv(판정기가 읽음) 외
#   순서·결과를 판정기 자리로 옮기는 법은 README 「갱신 순서」.
"""② TOPIS 폴리라인 ↔ OSM way 공간 매칭. 표본점 10 m 마다 25 m 안 · 진행방향 ±30°(일방통행은 방향 일치, 양방향은 어느 쪽이든) 후보 중 최적. 출력: 링크별 매칭률, way×방향 → link_id 표."""
import pickle, json, re, numpy as np, pandas as pd, shapely, time, collections
from shapely import LineString
from shapely.strtree import STRtree
from pyproj import Transformer
t0=time.time()
BUF=25.0; STEP=10.0; ANG=30.0
tr=Transformer.from_crs('EPSG:4326','EPSG:5186',always_xy=True)
ways=pickle.load(open('osm_car_ways.pkl','rb'))
CLS_PEN={'motorway':0,'trunk':0,'primary':0,'secondary':0,'tertiary':0,'unclassified':2,'residential':3,'living_street':6,'service':8,
         'motorway_link':2,'trunk_link':2,'primary_link':2,'secondary_link':2,'tertiary_link':2}
# 세그먼트 배열
seg_way=[];seg_idx=[];seg_geom=[];seg_bear=[];seg_ow=[];seg_pen=[];seg_tb=[];seg_name=[]
wayinfo={}
for wid,tags,pts,refs in ways:
    x,y=tr.transform([p[0] for p in pts],[p[1] for p in pts]); x=np.asarray(x); y=np.asarray(y)
    ow=tags.get('oneway','no'); hw=tags['highway']
    if tags.get('junction') in ('roundabout','circular') or hw=='motorway': ow = ow if ow in('yes','-1') else 'yes'
    if ow in ('yes','true','1'): owc=1
    elif ow=='-1': owc=-1
    else: owc=0
    tb=1 if (tags.get('tunnel') not in (None,'no')) else (2 if (tags.get('bridge') not in (None,'no')) else 0)
    wayinfo[wid]=(hw,owc,tags.get('name'),tags.get('maxspeed'),float(np.hypot(np.diff(x),np.diff(y)).sum()),tb)
    for i in range(len(x)-1):
        dx,dy=x[i+1]-x[i],y[i+1]-y[i]
        if dx==0 and dy==0: continue
        seg_way.append(wid);seg_idx.append(i);seg_geom.append(LineString([(x[i],y[i]),(x[i+1],y[i+1])]))
        seg_bear.append(np.degrees(np.arctan2(dx,dy))%360);seg_ow.append(owc);seg_pen.append(CLS_PEN[hw]);seg_tb.append(tb);seg_name.append(re.sub(r'\s','',tags.get('name','')))
seg_way=np.array(seg_way);seg_bear=np.array(seg_bear);seg_ow=np.array(seg_ow);seg_pen=np.array(seg_pen,dtype=float);seg_tb=np.array(seg_tb);seg_name=np.array(seg_name,dtype=object);seg_idx=np.array(seg_idx)
tree=STRtree(seg_geom); print('segments',len(seg_geom),'sec',round(time.time()-t0))
# TOPIS 표본점
gj=json.load(open('topis_link_geom_v1.geojson'))
P=[];PB=[];PL=[];PS=[];LNAME=[];LTB=[]  # 점, 진행방향, 링크 index, 표본 순번
links=[]
for li,f in enumerate(gj['features']):
    c=np.array(f['geometry']['coordinates']); x,y=tr.transform(c[:,0],c[:,1]); x=np.asarray(x);y=np.asarray(y)
    ls=LineString(np.c_[x,y]); L=ls.length; n=max(2,int(L//STEP)+1)
    d=np.linspace(0,L,n)
    for k,dd in enumerate(d):
        p=ls.interpolate(dd); q=ls.interpolate(min(dd+5,L)); q0=ls.interpolate(max(dd-5,0))
        P.append(p); PB.append(np.degrees(np.arctan2(q.x-q0.x,q.y-q0.y))%360); PL.append(li); PS.append(k)
    links.append((f['properties'],L,n)); rn=re.sub(r'\s','',str(f['properties'].get('road_name') or ''))
    LNAME.append(rn); LTB.append(1 if re.search('지하|터널',rn) else (2 if re.search('고가|대교|교$|순환로|간선도로|간선로|올림픽대로|강변북로',rn) else 0))
P_geom=np.array(P,dtype=object); PB=np.array(PB); PL=np.array(PL); PS=np.array(PS)
print('sample points',len(P),'sec',round(time.time()-t0))
pi,si=tree.query(P_geom,predicate='dwithin',distance=BUF)
dist=shapely.distance(P_geom[pi],np.array(seg_geom,dtype=object)[si])
diff=(seg_bear[si]-PB[pi]+180)%360-180  # -180..180
ow=seg_ow[si]
fwd_ok=np.abs(diff)<=ANG; bwd_ok=np.abs(np.abs(diff)-180)<=ANG
ok=np.where(ow==1,fwd_ok,np.where(ow==-1,bwd_ok,fwd_ok|bwd_ok))
pi,si,dist,diff,fwd_ok=pi[ok],si[ok],dist[ok],diff[ok],fwd_ok[ok]
score=dist+seg_pen[si]+np.minimum(np.abs(diff),np.abs(np.abs(diff)-180))*0.2
ln=np.array([LNAME[l] for l in PL[pi]],dtype=object); ltb=np.array([LTB[l] for l in PL[pi]]); sn=seg_name[si]; stb=seg_tb[si]
name_hit=np.array([bool(a) and bool(b) and (a in b or b in a) for a,b in zip(ln,sn)])
score=score-8*name_hit
score=score+np.where((stb==1)&(ltb!=1),12,0)+np.where((ltb==1)&(stb!=1),12,0)+np.where((stb==2)&(ltb==0)&~name_hit,6,0)
# 점마다 최적 후보(연속성 보너스: 앞 점과 같은 way 면 -5)
order=np.lexsort((score,pi)); pi,si,dist,fwd_ok,score=pi[order],si[order],dist[order],fwd_ok[order],score[order]
best_way=np.full(len(P),-1,dtype=np.int64); best_seg=np.full(len(P),-1,dtype=np.int64); best_fwd=np.zeros(len(P),dtype=bool); best_d=np.full(len(P),np.nan)
starts=np.searchsorted(pi,np.arange(len(P)))
ends=np.searchsorted(pi,np.arange(len(P)),side='right')
prev=-1; prev_link=-1
for p in range(len(P)):
    a,b=starts[p],ends[p]
    if a==b: prev=-1; continue
    if PL[p]!=prev_link: prev=-1; prev_link=PL[p]
    sc=score[a:b].copy()
    if prev>=0: sc[seg_way[si[a:b]]==prev]-=5
    j=a+int(np.argmin(sc)); best_way[p]=seg_way[si[j]]; best_seg[p]=seg_idx[si[j]]; best_fwd[p]=fwd_ok[j]; best_d[p]=dist[j]; prev=best_way[p]
print('matched points',(best_way>=0).sum(),'/',len(P),'sec',round(time.time()-t0))
# 링크별 집계
rows=[]; way_dir_link=collections.defaultdict(lambda: collections.Counter())
for li,(props,L,n) in enumerate(links):
    m=PL==li; bw=best_way[m]; hit=bw>=0
    frac=hit.mean(); ws=collections.Counter(bw[hit]).most_common()
    cls=collections.Counter(wayinfo[w][0] for w in bw[hit])
    names=collections.Counter(wayinfo[w][2] for w in bw[hit] if wayinfo[w][2])
    rows.append({'link_id':props['link_id'],'road_name':props['road_name'],'dir':props['dir'],'cls':props['cls'],'len_m':round(L,1),'n_pts':n,
                 'match_frac':round(frac,3),'matched_m':round(frac*L,1),'n_ways':len(ws),'mean_dist_m':round(float(np.nanmean(best_d[m])),1) if hit.any() else None,
                 'osm_cls_top':cls.most_common(1)[0][0] if cls else None,'osm_name_top':names.most_common(1)[0][0] if names else None,
                 'osm_ways':' '.join(f'{w}:{c}' for w,c in ws[:12])})
    for w,f in zip(bw[hit],best_fwd[m][hit]):
        way_dir_link[(int(w),'fwd' if f else 'bwd')][props['link_id']]+=1
df=pd.DataFrame(rows); df.to_csv('topis_osm_match_v1.csv',index=False)
tot=df['len_m'].sum(); mt=df['matched_m'].sum()
print(f'[매칭률 길이기준] {mt/1000:.1f} / {tot/1000:.1f} km = {mt/tot*100:.1f}%')
for th in (.9,.8,.7,.5):
    print(f'  링크 match_frac ≥{th}: {(df.match_frac>=th).sum()} / {len(df)} ({(df.match_frac>=th).mean()*100:.1f}%)')
print(df.groupby('cls')[['len_m','matched_m']].sum().assign(pct=lambda d:(d.matched_m/d.len_m*100).round(1)))
print('OSM 급별 매칭 길이 분포'); print(df.groupby('osm_cls_top')['matched_m'].sum().sort_values(ascending=False).round(0))
print('평균 이격 중앙값', df['mean_dist_m'].median())
print('--- 매칭 < 50% 링크 (상위 30) ---'); print(df[df.match_frac<.5].sort_values('len_m',ascending=False).head(30)[['link_id','road_name','dir','cls','len_m','match_frac','osm_cls_top','osm_name_top']].to_string())
# way×방향 → link (최다 표본 링크 채택, 표본 ≥2)
wl=[]
for (w,d),cnt in way_dir_link.items():
    lid,c=cnt.most_common(1)[0]; tot_c=sum(cnt.values())
    hw,owc,name,ms,wlen,tb=wayinfo[w]
    wl.append({'osm_way_id':w,'dir':d,'link_id':lid,'n_pts':c,'share':round(c/tot_c,2),'n_links':len(cnt),'highway':hw,'oneway':owc,'osm_name':name,'osm_len_m':round(wlen,1)})
wl=pd.DataFrame(wl).sort_values(['osm_way_id','dir']); wl.to_csv('osm_way_topis_link_v1.csv',index=False)
print('way×방향 매핑', len(wl), 'ways', wl.osm_way_id.nunique(), '다중링크 way×dir', (wl.n_links>1).sum())
# way 세그먼트×방향 → link (GraphHopper edge 소요 계산용)
segrows=collections.defaultdict(collections.Counter)
for p in np.where(best_way>=0)[0]:
    segrows[(int(best_way[p]),int(best_seg[p]),'fwd' if best_fwd[p] else 'bwd')][links[PL[p]][0]['link_id']]+=1
sg=pd.DataFrame([{'osm_way_id':w,'seg_idx':i,'dir':d,'link_id':c.most_common(1)[0][0],'n_pts':c.most_common(1)[0][1]} for (w,i,d),c in segrows.items()]).sort_values(['osm_way_id','seg_idx','dir'])
sg.to_csv('osm_way_seg_topis_link_v1.csv',index=False); print('way 세그먼트×방향', len(sg))
print('sec',round(time.time()-t0))
