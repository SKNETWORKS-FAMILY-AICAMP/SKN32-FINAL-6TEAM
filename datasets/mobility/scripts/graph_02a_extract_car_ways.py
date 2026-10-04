# datasets/mobility/scripts/graph_02a_extract_car_ways.py — 택시·자동차 소요의 도로 구간별 시간대 속도(graph/ 5파일) 만들기 ②a
#   원래 이름 02a_extract_car_ways.py · 원래 자리 DATA_DIR\travel\processed\mobility\graph\_build\ (2026-09-19 · 9/30 저장소 사본 · 82 에서 이 자리로)
#   ★ **작업 폴더를 cwd 로 두고** 실행한다 — 입력·중간 산출을 전부 cwd 상대경로로 읽고 쓴다(원래 방식 그대로 · 코드 무변경):
#       cd <DATA_DIR>\travel\processed\mobility\graph\_build ;  python <저장소>\datasets\mobility\scripts\graph_02a_extract_car_ways.py
#   입력(cwd 기준): seoul_bbox.osm.pbf   →   출력(cwd): osm_car_ways.pkl
#   순서·결과를 판정기 자리로 옮기는 법은 README 「갱신 순서」.
"""서울 클립 PBF → 자동차 통행급 way 형상·태그 추출(pickle). 매칭용."""
import osmium, pickle, time, collections
CAR = {'motorway','motorway_link','trunk','trunk_link','primary','primary_link','secondary','secondary_link','tertiary','tertiary_link','unclassified','residential','living_street','service'}
KEEP=['highway','oneway','name','name:en','maxspeed','lanes','junction','access','motor_vehicle','ref','bridge','tunnel','layer']
class H(osmium.SimpleHandler):
    def __init__(s): super().__init__(); s.ways=[]; s.cnt=collections.Counter()
    def way(s,w):
        hw=w.tags.get('highway')
        if hw not in CAR: return
        pts=[]
        for nd in w.nodes:
            if nd.location.valid(): pts.append((nd.lon,nd.lat))
        if len(pts)<2: return
        s.cnt[hw]+=1
        s.ways.append((w.id,{k:w.tags[k] for k in KEEP if k in w.tags},pts,[nd.ref for nd in w.nodes]))
t0=time.time(); h=H(); h.apply_file('seoul_bbox.osm.pbf',locations=True,idx='flex_mem')
pickle.dump(h.ways,open('osm_car_ways.pkl','wb'))
print(len(h.ways), dict(h.cnt), 'sec', round(time.time()-t0))
