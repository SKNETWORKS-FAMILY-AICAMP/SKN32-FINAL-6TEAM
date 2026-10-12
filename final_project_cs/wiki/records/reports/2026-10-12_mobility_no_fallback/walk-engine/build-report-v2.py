from pathlib import Path
import json,hashlib,difflib,xml.etree.ElementTree as ET
W=Path(__file__).resolve().parents[3];P=Path(__file__).resolve().parent
def read(name):return json.loads((P/name).read_text(encoding='utf-8'))
d=read('diagnosis-v1.json');a=read('pbf-audit-v1.json');n=read('new-pbf-targeted-v1.json')
b=read('backup-before-goal-fix-v1.json');c=read('paired-counterexample-v2.json');post=read('postfix-w01-v1.json')
source=W/'final_project_cs/app/domains/travel_ops/instances/mobility/engine/graph_router.py'
test=W/'final_project_cs/tests/unit/travel/mobility/test_graph_router_goal_heuristic_v1.py'
assert hashlib.sha256(source.read_bytes()).hexdigest()==c['source_after_sha256']==post['source_after']
success=set();runs=[]
for name in ['graph-router-final-v3.xml','goal-boundary-final-v4.xml']:
    xml=ET.parse(P/name).getroot();cases=list(xml.iter('testcase'));passed=[];errors=[]
    for case in cases:
        key=(case.attrib.get('classname'),case.attrib['name'])
        if any(case.find(k) is not None for k in ['failure','error','skipped']):errors.append(key)
        else:passed.append(key);success.add(key)
    runs.append({'log':name,'passed':len(passed),'not_passed':len(errors),'total':len(cases)})
assert len(success)==58
before=W/b['backup']/'graph_router.py'
patch=''.join(difflib.unified_diff(before.read_text(encoding='utf-8').splitlines(True),source.read_text(encoding='utf-8').splitlines(True),fromfile='graph_router.py.before',tofile='graph_router.py.after'))
with (P/'goal-heuristic-change-v2.diff').open('x',encoding='utf-8') as f:f.write(patch)
summary={'walk':{'web_shortest_m':672,'product_before_m':d['astar']['distance'],'product_after_m':post['after_distance_m'],
                'relative_error_pct':(post['after_distance_m']-672)/672*100,'network_geometry_m':d['network_geometry_m'],
                'access_m':d['straight_access_m'],'same_astar_dijkstra':d['same_astar_dijkstra_distance'],
                'same_postfix_distance':post['same_distance'],'same_postfix_geometry':post['same_geometry'],
                'tolerance_changed':False,'resolved':False},
         'car_general_fix':{'synthetic_before_seconds':c['before_seconds'],'synthetic_after_seconds':c['after_seconds'],
                            'synthetic_dijkstra_seconds':c['dijkstra_seconds'],'regression_passed':len(success),'regression_total':len(success),
                            'runs':runs,'not_actual_trip':True},
         'old_pbf_same_snapshot':a['same_snapshot'],'new_targeted_way_matched':n['new_matched_way_count'],
         'new_targeted_way_total':n['old_way_count'],'new_changed_way_count':len(n['changed_ways']),
         'new_changed_existing_node_coordinates':len(n['changed_node_coordinates']),
         'source_before_sha256':c['source_before_sha256'],'source_after_sha256':c['source_after_sha256'],
         'test_sha256':hashlib.sha256(test.read_bytes()).hexdigest(),'developer_api_calls':0,'private_data_access':0,
         'official_reference':'https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.shortest_paths.astar.astar_path.html'}
with (P/'summary-v2.json').open('x',encoding='utf-8') as f:json.dump(summary,f,ensure_ascii=False,indent=2)
def link(path,label=None):
    path=Path(path)
    if not path.is_absolute():path=P/path
    return f'[{label or path.name}](<{path.as_posix()}>)'
report=f'''자동차 도착 후보를 비교할 때 더 느린 경로를 선택하던 일반 결함을 수정했습니다. 도보 웹 표본의 거리 차이는 남아 있습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 자동차 일반 반례 수정 | 수정 전 실패 → 수정 후 성공 | 1/1 = 100% |
| 새 시험과 기존 관련 회귀 | 서로 다른 시험 성공 | 58/58 = 100% |
| 같은 좌표 도보 재생 | 수정 전후 거리·형상 동일 | 1/1 = 100% |
| 카카오 도보 거리 기존 오차 기준 통과 | 742.65m 대 672m, +10.51% | 0/1 = 0% |

도보 재생 성공은 정확도 통과와 다른 분모입니다. 첫 표의 완료율은 이번 진단·수정 범위이며 21개 기능의 전체 실사용 완료율이 아닙니다.

자동차 결함은 하차 후보의 요청 좌표까지 거리 차이가 12m 안이라고 해서 후보끼리도 12m 안이라고 가정한 데서 발생했습니다. 합성 반례에서 두 후보는 서로 222m 가량 떨어졌지만 요청 좌표까지 거리 차이는 약0.11m였습니다. 기존 A*는 14.462초 경로를 선택했고 독립 비교용 다익스트라는 11.593초 경로를 선택했습니다. 이제 실제 하차 후보의 모든 그래프 끝점까지 직선거리 하한과 그 끝점에서 목표까지 남은 실제 비용을 더한 값 중 최솟값을 사용합니다. 수정 후11.593초로 일치합니다. 간선 끝1m 이내에서 잔여 비용을0으로 보는 기존 규칙도 같은 목표 표에 반영됩니다. 실제 이용 시간을 잰 결과가 아니라 같은 합성 도로에서 계산한 수치입니다.

변경은 {link(source)}의 목표 후보 휴리스틱과 {link(test)}의 새 반례 시험입니다. 고정12m 빼기를 제거했고 폴백·표본 보정·허용 오차 확대를 추가하지 않았습니다. 현재 속도 해석은 `_maxspeed`에서100km/h로 제한하므로 `1/28`초/m는 그 상한보다 빠른28m/s를 가정한 보수적 하한입니다. 110/120km/h 허용 도로를 그대로 처리한다는 주장은 현재 코드에 적용되지 않아 이번에 근거로 사용하지 않았습니다.

[NetworkX 공식 A* 문서]({summary['official_reference']})는 남은 비용을 과대평가하는 휴리스틱으로 최단 경로가 보장되지 않을 수 있음을 명시합니다. 이 전제를 실제 코드의 복수 목표 처리와 합성 반례로 확인한 뒤 수정했습니다. 보행 계단 비용은 기존 계약에 있으므로 거리 최단과 다를 수 있다는 점을 기록하며 변경하지 않았습니다. A* 거리 하한은 저장 간선 길이와 형상 길이가 같은 척도라는 전제에 의존합니다. 간선 길이 소수1자리 반올림·좌표 양자화로 미세한 차이가 생길 수 있어 모든 입력의 엄밀한 최적성을 이번 시험만으로 보장하지 않습니다. 이번 수정은 재현한 복수 목표와 끝점0비용 경계에 한정합니다.

시험 근거는 {link('goal-heuristic-before-v1.xml','수정 전 반례 실패')}, {link('paired-counterexample-v2.json','같은 반례 수정 전후 수치')}, {link('graph-router-final-v3.xml','최종판 기존 관련57건 성공')}, {link('goal-boundary-final-v4.xml','복수 목표·끝점1m 경계2건 성공')}입니다. 초기 묶음의 metadata/atomic11건은 임시 폴더 생성 권한 문제로 시험 본문 전에 오류가 났고, 작업 폴더 안의 새 임시 폴더로 재실행해 통과했습니다. 최초 오류 로그도 보존했습니다.

도보는 GraphRouter만 적재하고 네트워크를 차단해 실행했습니다. A*와 다익스트라 모두742.65m이며 도로 형상693.20m와 출발·도착 접근 직선49.45m(8.46m+40.99m)의 합입니다. 요청 좌표는 위도/경도37.5665,126.9780→37.56948,126.98222입니다. 제품은 무교로291.64m와 청계천로242.82m를 길게 진행하고, 카카오 상세는 무교로151m 뒤 골목41m·을지로1길61m·오른쪽98m·교량을 안내합니다. 제품에도 교량 way1062619345가 있어 단순히 교량이 전부 누락됐다고 판단하지 않습니다. 카카오 원본 경로 좌표는 확보되지 않아 픽셀로 역산하거나 임의 구간을 추가하지 않았습니다.

도착점에 가장 가까운28.57m 거리의계단 way360147780는 보유 도보망의 최대 연결 성분 밖에 있고, 선택된 청계천로는40.99m입니다. 이를 강제로 연결하지 않았습니다. 주변533간선을 그대로 읽은 별도 부분망 진단은 도로 비용693.29m를 구했고, 계단 가중치를 없애도 같았습니다. 을지로1길을 최소1간선 경유하는 조건에서는751.84m로 늘었습니다. 부분망 계산은 제품 재실행이나 새로운 웹 정확도 표본으로 세지 않습니다.

기존 OSM 원본은 그래프의 원본 MD5와일치합니다({a['pbf_md5']}). 주변5060노드·330도로 way를 확인했습니다. 을지로1길233651317/1002205328은 기존 OSM과 그래프에 존재합니다. 최신 공개 OSM({n['new_md5']})에서는 기존 주변261/261way가 유지됐고30way의태그·노드 목록이 달랐으며 기존 노드 좌표 변화는0건입니다. 선택 경로와 을지로1길의 노드 목록은 유지됐습니다. 이 조사는 기존 주변 way와 같은 도로명을 표적으로 삼았으며 새 무명 도로 전체의 부재를 증명하지 않습니다.

{link('route-diagnosis-v2.png','실제 도로 형상과 접근 구간 그림')} · {link('diagnosis-v1.json','실제 경로·구간·주변533간선')} · {link('pbf-audit-v1.json','기존 OSM 원자료 대조')} · {link('new-pbf-targeted-v1.json','최신 OSM 표적 대조')} · {link('local-topology-v1.json','부분망 연결 진단')} · {link('postfix-w01-v1.json','수정 후 도보1OD 재생')}.

백업은 {link(W/b['backup'],'수정 직전 백업 폴더')}입니다. 실제 변경 비교는 {link('goal-heuristic-change-v2.diff')}입니다. 코드SHA256은 수정 전`{c['source_before_sha256']}`, 수정 후`{c['source_after_sha256']}`입니다. 산출물 해시는 {link('MANIFEST-v2.json')}에 보존합니다.

이 담당 범위에서 지도 개발자API호출0회, 개인정보 자료 접근0회이며 커밋·푸시·배포·외부 메시지 전송은 수행하지 않았습니다. 공개 웹은 공식 A* 문서 확인에만 사용했습니다.
'''
with (P/'REPORT-v2.md').open('x',encoding='utf-8') as f:f.write(report)
files=[p for p in P.iterdir() if p.is_file() and p.name!='MANIFEST-v2.json']
manifest={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files}
with (P/'MANIFEST-v2.json').open('x',encoding='utf-8') as f:json.dump(manifest,f,ensure_ascii=False,indent=2)
print(json.dumps({'distinct_passed':len(success),'walk_after':post['after_distance_m'],'report_sha256':manifest['REPORT-v2.md']['sha256'],'source_after':c['source_after_sha256']},ensure_ascii=False,indent=2))
