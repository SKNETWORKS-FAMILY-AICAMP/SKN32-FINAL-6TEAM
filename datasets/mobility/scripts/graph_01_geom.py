# datasets/mobility/scripts/graph_01_geom.py — 택시·자동차 소요의 도로 구간별 시간대 속도(graph/ 5파일) 만들기 ①
#   원래 이름 01_geom.py · 원래 자리 DATA_DIR\travel\processed\mobility\graph\_build\ (2026-09-19 · 9/30 저장소 사본 · 82 에서 이 자리로)
#   ★ **작업 폴더를 cwd 로 두고** 실행한다 — 입력·중간 산출을 전부 cwd 상대경로로 읽고 쓴다(원래 방식 그대로 · 코드 무변경):
#       cd <DATA_DIR>\travel\processed\mobility\graph\_build ;  python <저장소>\datasets\mobility\scripts\graph_01_geom.py
#   입력(cwd 기준): raw/topis/*.xlsx · raw/topis/_check/*.csv   →   출력(cwd): topis_link_geom_v1.geojson
#   순서·결과를 판정기 자리로 옮기는 법은 README 「갱신 순서」.
"""① TOPIS 보간점(EPSG:5181) → 폴리라인 → EPSG:4326 · 길이 회귀(±5%) → topis_link_geom_v1.geojson"""
import pandas as pd, numpy as np, json, time
from pyproj import Transformer, Geod
t0=time.time()
pt = pd.read_excel('raw/topis/topis_servicelink_points_202603.xlsx', dtype={'LINK_ID': str})
pt['VER_SEQ']=pt['VER_SEQ'].astype(int); pt=pt.sort_values(['LINK_ID','VER_SEQ'])
print('points', len(pt), 'links', pt['LINK_ID'].nunique(), 'cols', list(pt.columns))
ref = pd.read_csv('raw/topis/_check/servicelink_polyline_len_202603.csv', dtype={'LINK_ID': str}).set_index('LINK_ID')['plen_m']
master = pd.read_csv('raw/topis/_check/link_master_20250901_20260831.csv', dtype={'링크아이디': str}, encoding='utf-8-sig').set_index('링크아이디')
print('master cols', list(master.columns))
sl = pd.read_excel('raw/topis/topis_servicelink_202603.xlsx', dtype=str); print('sl cols', list(sl.columns))
tr = Transformer.from_crs('EPSG:5181','EPSG:4326', always_xy=True); geod=Geod(ellps='WGS84')
feats=[]; rows=[]
for lid, g in pt.groupby('LINK_ID', sort=False):
    x=g['GRS80TM_X'].astype(float).to_numpy(); y=g['GRS80TM_Y'].astype(float).to_numpy()
    len5181=float(np.sqrt(np.diff(x)**2+np.diff(y)**2).sum())
    lon,lat=tr.transform(x,y)
    len4326=float(geod.line_length(lon,lat)) if len(lon)>1 else 0.0
    m = master.loc[lid] if lid in master.index else None
    props={'link_id':lid,'n_pts':int(len(g)),'len_5181_m':round(len5181,1),'len_4326_m':round(len4326,1),
           'len_ref_m':round(float(ref[lid]),1) if lid in ref.index else None,
           'dist_file_m':float(m['거리']) if m is not None else None,
           'road_name':m['도로명'] if m is not None else None,'dir':m['방향'] if m is not None else None,
           'from_nm':m['시점명'] if m is not None else None,'to_nm':m['종점명'] if m is not None else None,
           'cls':m['기능유형구분'] if m is not None else None,'gu':m['권역구분'] if m is not None else None,
           'crs_src':'EPSG:5181','src':'topis_servicelink_points_202603'}
    feats.append({'type':'Feature','properties':props,'geometry':{'type':'LineString','coordinates':[[round(a,7),round(b,7)] for a,b in zip(lon,lat)]}})
    rows.append(props)
df=pd.DataFrame(rows)
# 회귀 1: 5181 길이 == 14번 csv (같은 계산이라 동일해야)
d=df.dropna(subset=['len_ref_m']); r1=(d['len_5181_m']-d['len_ref_m']).abs()
print(f'[R1] 5181 길이 vs 14번 csv: n={len(d)} 최대차 {r1.max():.2f} m · 0.5m 초과 {(r1>0.5).sum()}')
# 회귀 2: 4326 측지 길이 / 14번 csv 길이 ±5%
r2=d['len_4326_m']/d['len_ref_m']; ok5=(r2.sub(1).abs()<=.05).sum()
print(f'[R2] 4326 측지길이/ref: 중앙값 {r2.median():.4f} min {r2.min():.4f} max {r2.max():.4f} ±5% {ok5}/{len(d)} ±1% {(r2.sub(1).abs()<=.01).sum()}')
# 회귀 3: 4326 길이 / 일별파일 거리 (14번: ±5% 5,033/5,082)
d3=df.dropna(subset=['dist_file_m']); r3=d3['len_4326_m']/d3['dist_file_m']
print(f'[R3] 4326/파일거리: n={len(d3)} 중앙값 {r3.median():.3f} ±5% {(r3.sub(1).abs()<=.05).sum()} ±10% {(r3.sub(1).abs()<=.1).sum()} >20% {(r3.sub(1).abs()>.2).sum()}')
print(d3[r3.sub(1).abs()>.2][['link_id','road_name','from_nm','to_nm','dist_file_m','len_4326_m']].to_string())
# bbox
allc=np.array([c for f in feats for c in f['geometry']['coordinates']])
print('bbox lon', allc[:,0].min(), allc[:,0].max(), 'lat', allc[:,1].min(), allc[:,1].max())
print('1점 링크', (df['n_pts']<2).sum(), '점 분포', df['n_pts'].describe()[['min','50%','max']].to_dict())
# 좌표 확인점: 새문안로 서울역사박물관 197521/452291 → 37.5702/126.9719
print('확인점', tr.transform(197521,452291))
gj={'type':'FeatureCollection','name':'topis_link_geom_v1','crs_note':'EPSG:4326 (converted from EPSG:5181 TOPIS points 2026-03)','generated':time.strftime('%Y-%m-%dT%H:%M:%S'),'features':feats}
json.dump(gj, open('topis_link_geom_v1.geojson','w'), ensure_ascii=False)
df.to_csv('topis_link_geom_v1_len_check.csv', index=False)
print('sec', round(time.time()-t0,1))
