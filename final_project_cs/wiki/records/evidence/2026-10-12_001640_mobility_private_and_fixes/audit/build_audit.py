from pathlib import Path
import ast
import datetime
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
CS = ROOT / 'final_project_cs'
BASE = 'app/domains/travel_ops/instances/mobility/'
SRC = 'app/domains/travel_ops/ports/data_sources/'
WATCH = 'app/domains/travel_ops/components/watch/'
NAMES = ['택시 예상 요금','택시 예산 여유 계산','자동차 소요 시간','자동차 경로 거리','대중교통 전체 소요 시간','지하철 경로 산출','버스 직행·환승 경로','지하철 요금','버스·지하철 환승 요금','장소 사이 도보 거리','도보·역 접근 시간','자전거 경로','자전거 소요 시간','첫차·막차·출발 시각','환승·역 출구·승차 칸','실시간 도착정보','혼잡 안내','무정차·도로 사고 감시','따릉이 대여·반납·재고','사건 후 일정 자동 조정','지도 경로 표시']
# 경로 존재를 확인한 정적 감사이며 함수 존재가 요구 동작의 통과를 뜻하지 않습니다.
ROWS = [
('engine/car.py','taxi_fare','test_car_fare','공식 요율+도로 속도 모델. 별도 미터 자료 대체와 호출료는 미완료','개발 대조 ±1,000원; 실결제 허용 기준 확정 필요','실제 미터·호출 옵션 구분 검증'),
('engine/car.py','taxi_planning_fare','test_taxi_budget','37% 여유 모델; 실제 상한 보장 대체 소스 아님','초과율·과다 여유 허용 기준 확정 필요','독립 실제 결제 초과율 검증'),
('engine/car.py','CarGraph.compute','test_car','링크 속도→도로급 속도→기본 속도, 출처 등급 보존','개발 웹 ±5분; 실제 운행 기준 미확정','교통 반영 경로 선택과 시간대별 실주행 대조'),
('engine/car_turn_search.py','pieces','test_car_turn','회전 제약 로컬 도로망; 차량 대체 경로 독립 검증 필요','개발 웹 ±10%; 형상 정렬 필요','복잡한 회전·유턴·시간 예외·실제 형상 검증'),
('engine/verify_time.py','Verifier.verify_case','test_mixed','첫 승차 현재 도착정보 불가 시 시간표 모델, 실패 이유 보존','개발 웹 ±5분; 실탑승 오차 허용 기준 미확정','여정 전체 실탑승·후속 환승 실시간 검증'),
('engine/candidates.py','CandidateGraph','test_partial_loop','시간표·역간 거리·공식 역ID 자료; 독립 대체 검증 필요','경로 성립·요일·급행·순환선 경계 기준','급행·순환선·종착·노선 전체 새 표본 검증'),
('engine/plan.py','Planner._bus_direct','test_bus','버스 구간 프로파일 불가 시 표정속도 모델, 근거 구분','노선·정류장 순서와 다중 환승 성립','다중 환승·누락 경로·실탑승 검증'),
('engine/options.py','subway_fare','test_subway_fare','실제 운임거리·추정거리 상하단, 별도철도 운임 구분','거리 경계와 실제 결제 일치','실제 교통카드 결제·장거리 경계 검증'),
('engine/options.py','mixed_fare_estimate','test_transfer','할인 조건 불명확 시 할인 전 상단 예상액 유지','30/60분 후승 시각 경계; 실제 결제 기준 필요','하차 태그·승차 시간 폭·실결제 검증'),
('engine/plan.py','Planner._walk_path','test_walk','보행망 경로→명시된 도보 모델 근거','직선 1.2km 정책, 개발 거리 ±10%','같은 출입점·형상·시각 새 웹/실보행 검증'),
('engine/graph_router.py','GraphRouter','test_walk','보행망 계단 시간·명시된 대체 모델','개발 시간 ±5분; 실보행 기준 미확정','역 입구·계단·환승 실보행 측정'),
('engine/bike.py','BikeRouter.route','test_plan_bike','도로망 라우터; 실패 시 근거없음, 독립 대체 미확인','개발 거리 ±10%; 안전·허용 도로 기준 필요','교량·강변 연결·자전거 허용 도로 검증'),
('engine/verify_time.py','Verifier.verify_leg_bike','test_plan_bike','주행 속도 모델+대여 단계; 실제 총여정 대체 미확인','개발 시간 ±5분; 전체 이용 기준 미확정','경사·정지·대여·반납 시간 실측'),
('engine/verify_time.py','Verifier._last_feasible_depart','test_published_boarding','시간표·공식 공표 승차시간·요일 달력','공표 범위 안·환승 막차·자정 경계','전체 운행 그룹·휴일·자정·막차 새 표본'),
('engine/options.py','transfer_cars','test_transfer','동일 경로 승차 칸 자료와 OSM 역 출구; 대체 검증 필요','같은 노선·방향·경유 경로 정확 일치','역 출구·승차 칸 현장 대조'),
('engine/departure_observer.py','observe','test_departure','공식 실시간 소스→이유 보존 후 시간표 재검증','신선도 30/90/2초는 ETA 오차 보장 아님','실제 도착 오차·탑승 상태·후속 환승 예측'),
('engine/congestion.py','Congestion.lookup','test_congestion','통계 혼잡 자료; 실제 차량 혼잡 대체 미확인','실제 일치율·누락률 허용 기준 미확정','일반/급행 실제 혼잡 관측'),
('../..//ports/data_sources/subway_notice.py','mentions_station','test_subway_notice','교통 ITS+UTIC 합침·부분 실패 표시; 무정차 별도 대체 미확인','사건 없음/조회 실패 구분; 탐지율 기준 미확정','다역 공지 파싱·실제 사건 회수율·동시 실패'),
('engine/bike.py','BikeLive.get','test_bike_live','실시간 재고 소스+대여소 자료; 장애 대체 검증 필요','대여/반납 가능한 재고·만차·마감 조건','재고 변동·대체 대여소·전체 여정 실이용'),
('wiring.py','observe_departure','test_departure','현재 출발 관측→재계획→공통 일정 쓰기; 근거 실패 중단','멱등성·동시성·입력판 검사·최신 계획 링크','cs 프로젝트 서버 저장·배달·최신 링크 전체 재생'),
('route_shape.py','build_shape','test_route_shape','도로망 선·역 경유선·근사 직선은 출처 구분','실제 경로 형상·휴대폰 화면·클릭 연동','실제 cs 프로젝트 서버 응답과 휴대폰 경로 확인'),
]

def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

def defs(p):
    result = {}
    tree = ast.parse(p.read_text(encoding='utf-8-sig'))
    def walk(node, prefix=''):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + child.name
                result[name] = child.lineno
                walk(child, name + '.')
            else:
                walk(child, prefix)
    walk(tree)
    return result

log = (OUT / 'collection-v2.log').read_text(encoding='utf-8',errors='replace')
nodeids = [x for x in log.splitlines() if x.startswith('tests/') and '::' in x]
collection_exit = int((OUT / 'collection-v2-exit.txt').read_text())
rows = []
for idx,(name,entry) in enumerate(zip(NAMES,ROWS),1):
    file,symbol,test_prefix,alternate,tolerance,remaining = entry
    p = (CS / BASE / file).resolve() if idx != 18 else CS / SRC / 'subway_notice.py'
    symbols = defs(p)
    found = symbol in symbols
    related = [x for x in nodeids if test_prefix in x.split('::')[0]]
    rows.append(dict(id=idx,name=name,product_code=p.relative_to(CS).as_posix(),symbol=symbol,line=symbols.get(symbol),symbol_found=found,code_path={'numerator':int(found),'denominator':1},tests_collected=related,tests_executed_this_audit=0,alternate=alternate,tolerance=tolerance,remaining=remaining,new_independent_real_world_validation='이번 감사 0건; 기존 자료는 해당 날짜 기록 범위',environment_verification='이번 감사에서 cs 프로젝트 서버 HTTP·배포·실사용 환경 확인 안 함',real_use_complete={'numerator':0,'denominator':1},real_use_complete_reason='제품 전체 경로·대체·허용오차·새 표본·환경 확인을 모두 입증하지 못함'))
source_paths = set()
for folder in [CS/BASE, CS/SRC, CS/WATCH]:
    source_paths.update(p for p in folder.rglob('*.py') if '_backup' not in p.parts and '__pycache__' not in p.parts)
source_paths.add(CS/'app/composition.py')
source_hashes = {p.relative_to(ROOT).as_posix():digest(p) for p in sorted(source_paths)}
data_folder = ROOT/'datasets/mobility/processed/mobility'
data_paths = [p for p in data_folder.iterdir() if p.is_file() and p.suffix in ('.json','.jsonl','.gz')]
data_paths += [p for p in (data_folder/'graph').iterdir() if p.is_file() and p.suffix in ('.json','.csv','.gz')]
data_paths += [p for p in (CS/BASE/'engine/rules').iterdir() if p.is_file()]
data_hashes = {p.relative_to(ROOT).as_posix():digest(p) for p in sorted(data_paths)}
prior = CS/'wiki/records/reports/assets/2026-10-11_mobility_readiness_v55/readiness-catalog.json'
prior_catalog = json.loads(prior.read_text(encoding='utf-8'))
audit = dict(created_at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),scope='읽기 전용 정적 제품경로 감사·현재 pytest collection. 영수증/개인자료 접근 없음. 소스 수정 없음.',definitions={'code_path':'정적 파일·지정 함수/클래스 존재; 동작 완료나 배포의 증거 아님','real_use_completion':'제품 실행경로·대체 소스·허용오차·새 표본·환경 검증을 모두 충족한 기능 수/21','tests_collected':'pytest collection으로 발견한 항목; 실행 통과와 구분','source_hash_scope':'mobility 현재 py·data_sources 현재 py·watch 현재 py·composition; _backup 제외','data_hash_scope':'processed/mobility 루트 json/jsonl/gz + graph json/csv/gz + 현재 engine/rules. 사용자 영수증 폴더 접근 안 함'},counts={'code_paths_found':sum(x['symbol_found'] for x in rows),'features':21,'real_use_complete':0,'tests_collected':len(nodeids),'collection_exit':collection_exit,'tests_passed_this_audit':None,'source_files_hashed':len(source_hashes),'data_files_hashed':len(data_hashes),'external_api_calls':0},features=rows,prior_development_catalog={'path':prior.relative_to(ROOT).as_posix(),'sha256':digest(prior),'created_at':prior_catalog.get('created_at'),'historical_counts':prior_catalog.get('counts'),'caution':'과거 개발 대조 수치는 현재 실사용 정확도/시험 통과로 재사용하지 않음'},duplicate_work_notes=['10/11 택시 출발 역산·후속 버스 환승 할인 경계·택시 안내 연결의 결함3개는 기존 수정/회귀 기록 있음. 같은 수정 반복 금지.','10/11 대중교통 접근 시간 43조건 경계 수정·관련160시험 기록 있음. 현재 코드는 별도 해시만 확인.','10/11 지도 마커 가림 수정은 UI 작업자의 15개 mock 서버 시험과 28개 단위 기록. 실제 경로 형상/실서버 검증 완료로 세지 않음.','root가 별도 privacy/transit 작업 분담 중. 감사는 소스 변경하지 않음.'],priority_next=[{'feature_ids':[10,11,12,13],'action':'BikeRouter.route 비유한/논리값 거리·시간 응답 입력을 오프라인 재현 후 fail-closed 처리','reason':'현재 float 변환 뒤 음수만 검사하므로 NaN/inf가 round/int 예외 또는 잘못된 수치가 됨','status':'root에 전달; 구현 담당과 중복 방지'}, {'feature_ids':[18],'action':'무정차 다역 공지에서 앞 역이 누락되는 mentions_station 보강','reason':'현재 단일 역명+역 패턴은 혜화, 한성대입구역에서 혜화를 못 읽음; 코드 주석에 과거실공지 한계명시'}, {'feature_ids':[5,6,16,20],'action':'보유 응답을 사용한 현재 출발→후속 환승→재계획→최신 계획 링크 로컬 통합 재생','reason':'실시간·안내·저장 단위를 전체 제품경로로 확인; 새 현장측정/운영 배포와 분리'}],source_hashes=source_hashes,data_hashes=data_hashes)
existing = [p for p in [OUT/'readiness-current.json',OUT/'readiness-current.md'] if p.exists()]
backup = OUT/'_backup'/datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S_audit_regeneration')
if existing:
    backup.mkdir(parents=True,exist_ok=False)
    for p in existing:
        shutil.copy2(p,backup/p.name)
audit['artifact_backup'] = backup.relative_to(ROOT).as_posix() if existing else None
(OUT/'readiness-current.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
text = ['# 이동 실사용 21개 항목 현재 근거 감사','', '현재 코드 경로가 있는 것과 실사용 검증 완료를 구분했습니다. 0/21은 구현률이 아닙니다. 이번 감사는 소스 수정·외부 API·개인 영수증 접근을 하지 않았습니다.','', '| 할 일 | 상태 | 진행 |','|---|---|---|',f'| 정적 제품 코드 경로 확인 | 확인 | {audit["counts"]["code_paths_found"]}/21 = {audit["counts"]["code_paths_found"]/21:.1%} |','| 실사용 전체 관문 완료 | 미입증 | 0/21 = 0% |',f'| 현재 시험 수집 | 실행 안 함 | {len(nodeids)}개 수집, 종료코드 {collection_exit} |','', '아래 코드 확인 1/1은 함수/클래스 존재만 세며 그 기능 전체 구현 완료율이 아닙니다. 새 현장 표본·환경 확인은 이번 감사에서 0건입니다. 분모가 확정되지 않은 정확도·남은 공수는 퍼센트로 바꾸지 않습니다.','', '| 작업 | 코드 경로 | 현재 수집 시험(통과 아님) | 실사용 완료 | 남은 검증 |','|---|---|---:|---|---|']
for row in rows:
    text.append(f'| {row["name"]} | {int(row["symbol_found"])}/1 | {len(row["tests_collected"])} | 0/1 = 0% | {row["remaining"]} |')
text += ['', '시험 연결은 파일 이름 접두로 찾은 참고 목록이며 일부 파일이 여러 기능을 검사합니다. 기능별 시험 수를 합산하지 않습니다. collection은 최초 임시 폴더 권한 문제로 종료2였고 작업 폴더 TEMP/TMP로 재실행했습니다. 두 로그를 보존했습니다.','', '## 완료 근거와 남은 조건','']
for row in rows:
    text += [f'### {row["id"]}. {row["name"]}',f'- 코드: `{row["product_code"]}:{row["line"]}` · `{row["symbol"]}`',f'- 대체/한계: {row["alternate"]}',f'- 허용오차/관문: {row["tolerance"]}',f'- 남은 조건: {row["remaining"]}','']
text += ['## 최소 개선 우선순위',''] + [f'{i}. {x["action"]} — {x["reason"]}' for i,x in enumerate(audit['priority_next'],1)]
text += ['', '## 보존 및 주의','',f'- 현재 source 해시 {len(source_hashes)}개, 데이터/규칙 해시 {len(data_hashes)}개를 JSON에 보존했습니다. 전체 저장소·전체 데이터 해시라는 주장이 아닙니다.',f'- 제품 소스와 기존 공유 산출물은 수정하지 않았습니다. 감사 산출물의 정정 전 판은 `{audit["artifact_backup"]}`에 보존했습니다.','- 코드·데이터는 공유 작업 중 계속 바뀔 수 있습니다. 이 해시는 감사시점 스냅샷이며 부모 작업의 최종 재검증과 구분합니다.','- 기존 기록: 10/11 2054의 283개, 2129의 160개는 과거 실행이며 서로 중복이 있습니다. 이번 실행 통과수로 합산하지 않습니다.','- 실사용 HTTP·배포·실제 이동/결제 확인은 이번 감사에서 하지 않았습니다. mock 서버 화면 시험도 하지 않았습니다.']
(OUT/'readiness-current.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
print(json.dumps(audit['counts'],ensure_ascii=False))
print('Unresolved symbols:',[(x['name'],x['symbol']) for x in rows if not x['symbol_found']])
