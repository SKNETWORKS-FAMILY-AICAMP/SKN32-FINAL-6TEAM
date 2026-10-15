from pathlib import Path
from datetime import datetime
from collections import Counter
from html import escape
import difflib,hashlib,json,os,re,shutil,subprocess,xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2];CS=ROOT/'final_project_cs';SCRATCH=Path(__file__).parent
S=json.loads((SCRATCH/'subway-direction-work-v1.json').read_text(encoding='utf8'));EV=ROOT/S['evidence']
NOW=datetime.now().astimezone();stamp=NOW.strftime('%Y-%m-%d_%H%M%S')
REPORT=CS/'wiki/records/reports'/(NOW.strftime('%Y-%m-%d_%H%M')+'_지하철_방면_ID대조와_공식이름_연결검증.md')
ASSETS=CS/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v45'
PRIOR=CS/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v44'
WIKI=CS/'wiki/teams/mobility.md';DATA=ROOT/'datasets/mobility/REPORT.md';DEBUG=ROOT/S['debug']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();rel=lambda p:p.relative_to(ROOT).as_posix()
lnk=lambda source,dest:Path(os.path.relpath(dest,source.parent)).as_posix()


def save(p,d):
    with p.open('x',encoding='utf8') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False)


backups=list(S['backups'])
for name in ['extra-backups-v1.json','source-alias-backups-v1.json']:
    backups.extend(json.loads((EV/name).read_text(encoding='utf8'))['backups'])
backups.append(json.loads((EV/'test-backup-v1.json').read_text(encoding='utf8')))
order=json.loads((EV/'alias-edit-order-correction-v1.json').read_text(encoding='utf8'))
for dst,role in [(order['verified_original_backup'],'직전 원본·해시 일치'),(order['draft_backup'],'작성 중 판')]:
    backups.append({'source':order['source'],'backup':dst,'sha256':sha(ROOT/dst),'role':role})


def backup(p):
    dest=p.parent/'_backup'/(stamp+'_방면대조_결과기록전')/p.name;dest.parent.mkdir(parents=True)
    shutil.copy2(p,dest);backups.append({'source':rel(p),'backup':rel(dest),'sha256':sha(dest)})
    return sha(p)


paths=[CS/x for x in ['app/domains/travel_ops/ports/subway_route_identity.py',
    'app/domains/travel_ops/ports/data_sources/subway_boarding.py',
    'app/domains/travel_ops/instances/mobility/engine/subway_departure.py',
    'app/domains/travel_ops/instances/mobility/engine/departure_observer.py',
    'app/domains/travel_ops/instances/mobility/engine/subway_identity.py',
    'tests/unit/travel/test_subway_direction_v1.py','tests/unit/travel/test_subway_source_alias_v1.py']]
station_file=ROOT/'datasets/mobility/processed/mobility/subway_realtime_stations_20260902_v1.json'
owned={rel(p) for p in paths}|{rel(station_file)}
hashes=dict(S['source_test_data_hashes'])
for p,h in hashes.items():
    if p not in owned:assert sha(ROOT/p)==h,('다른 작업 변경',p)
for p in [*paths,station_file]:hashes[rel(p)]=sha(p)
assert len(hashes)==265
after=ET.parse(EV/'after-v3.xml').getroot();before=ET.parse(EV/'before-v1.xml').getroot()
assert len(after.findall('.//testcase'))==370 and not after.findall('.//failure') and not after.findall('.//error')
assert len(before.findall('.//testcase'))==22 and len(before.findall('.//failure'))==9
new_counts={name:sum(name in t.attrib.get('classname','') for t in after.findall('.//testcase'))
            for name in ('test_subway_direction_v1','test_subway_source_alias_v1')}
assert new_counts=={'test_subway_direction_v1':23,'test_subway_source_alias_v1':8}
assert json.loads((EV/'ruff-run-v1.json').read_text(encoding='utf8'))['exit_code']==0
abba=json.loads((EV/'same-snapshot-abba-v2.json').read_text(encoding='utf8'))
assert len(abba['runs'])==8
assert [x['result']['status'] for x in abba['runs'][4:]]==['no_boardable_prediction','predicted','predicted','no_boardable_prediction']
assert next(x for x in abba['runs'][1]['result']['excluded'] if x['train_number']=='A3013')['reason']=='departed_or_unknown_state'
live=json.loads((EV/'live-product-v1.json').read_text(encoding='utf8'))
assert live['actual_http_responses']==2 and len(live['requests'])==2
assert len({x['raw_sha256'] for x in live['raw_responses']})==1
old_stations=ROOT/next(x['backup'] for x in backups if x['source']==rel(station_file))
old_doc=json.loads(old_stations.read_text(encoding='utf8'));new_doc=json.loads(station_file.read_text(encoding='utf8'))
assert new_doc['stations']==old_doc['stations'] and len(new_doc['stations'])==696
assert {k:v for k,v in new_doc.items() if k!='source_aliases'}==old_doc
save(EV/'source-assessment-v1.json',{'created_at':NOW.isoformat(),'actual_http_responses':2,
    'unique_response_contents':1,'rows_per_response':[18,18],'unique_content_rows':18,
    'actual_live_product_paths':2,'live_realtime_connected_paths':1,
    'fresh_accuracy_or_boarding_samples':0,'controlled_tests':new_counts,
    'same_input_abba_runs':8,'actual_api_request_attempts':2,'map_developer_api_calls':0,
    'correction':'수집 원본의 예상1회/보관 재사용 claim은 틀렸습니다. 해당 인스턴스에 cache를 주입하지 않아 실제HTTP2회이며 바이트는 같습니다. 포착 계수와 원문SHA256을 우선합니다.',
    'alias_edit_order_correction':order,'prior_raw_abba_v1':'이름 대응 수정 전8재생은 모두 미선택이었습니다. 원본을 보존하고 수정 후v2와 구분합니다.'})
save(EV/'research-v1.json',{'checked_at':NOW.isoformat(),'cutoff':'2026-10-09','sources':[
    {'url':'https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A',
     'finding':'trainLineNm은 도착지/다음역 방면이며 역ID·종착ID·열차종류는 별도 필드. 실제 원문의 방면과 F/Tid 불일치를 분리 확인.'},
    {'url':'https://www.airportrailroad.com/train/normal/info/030/0',
     'finding':'공항철도 공식 홍대입구 페이지는 같은 종착을 서울역 방면과 서울(일반열차)로 표기. 정확 이름1쌍을 공식 서울ID에 대응.'}],
    'method':'관측 식별 계약·공식 이름 대응 수정. 예측 알고리즘이나 논문 계수 보정은 적용하지 않음.'})
for p in paths[1:5]:
    if p.name=='subway_identity.py':old=ROOT/order['verified_original_backup']
    else:old=ROOT/next(x['backup'] for x in backups if x['source']==rel(p))
    with (EV/(p.stem+'-diff-v1.patch')).open('x',encoding='utf8') as f:
        f.write(''.join(difflib.unified_diff(old.read_text(encoding='utf8').splitlines(True),p.read_text(encoding='utf8').splitlines(True),fromfile='before/'+rel(p),tofile='after/'+rel(p))))
assert not ASSETS.exists() and not REPORT.exists();ASSETS.mkdir()
catalog=json.loads((PRIOR/'readiness-catalog.json').read_text(encoding='utf8'))
for f in catalog['features']:
    if '실시간' in f['name']:
        f['prior_need_v44']=f['need']
        f['need']='v45: 공식 방면 이름·종착ID·인접ID쌍을 함께 대조하고 제품 콜백에 근거를 전달. 서울역/서울 공식 이름1쌍을 자료로 등록해 기존696행은 보존했습니다. 새31/31·관련370/370(구조2포함). 기존 A3013은 경로 불일치→이미 출발로 정확히 제외, 시각/상태를 바꾼 통제 입력은 선택 성공. ABBA8회는 독립 검증이 아닙니다. 새 실제HTTP2응답의 바이트는 같고18행 내용1개입니다. 실제 제품2경로 중5호선 공덕→마포는10→13분 예상 재계산 연결, 공항철도는 미연결입니다. 최신 공항철도 도착0초·이미 출발/방향 조건은 지어내지 않고 모델로 재검증합니다. 새 실제ETA오차/탑승/지도웹0; 후속환승 모델·운영 배달·급행/순환·대체 ETA 소스 확보가 남았습니다.'
        f['direction_evidence_v45']={'new_tests':31,'related_tests':370,'raw_http_responses':2,
            'unique_content_snapshots':1,'live_realtime_product_paths':1,'live_paths_attempted':2,
            'actual_eta_accuracy_samples':0,'station_rows_preserved':696,'source_aliases_added':1}
catalog.update(created_at=NOW.isoformat(),scope='방면/인접ID 대조·콜백 근거 보존·공식 이름 대응과 실제 응답 제한',prior_catalog_sha256=sha(PRIOR/'readiness-catalog.json'),full_feature_completion=False)
assert len(catalog['features'])==21 and dict(Counter(x['status'] for x in catalog['features']))=={'조건부 사용':3,'개선 필요':9,'추가 검증':9}
save(ASSETS/'readiness-catalog.json',catalog)
text=f'''# 지하철 방면·인접역ID와 공식 이름의 제품 연결 검증

공식 방면과 다른 인접역ID를 진행 방향으로 읽던 문제를 고치고, 출발 관측기에서 방향 근거가 빠지는 연결도 수정했습니다. 공항철도 이름 대응1쌍을 추가했으며 실제5호선 경로는 현재 응답으로 재계산됐습니다. 실제 공항철도 승차 안내 성공은 아직 확인하지 못했습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 신규 방향·공식 이름 시험 | 통과 | 31/31 = 100% |
| 관련 시험·구조 경계 | 통과 | 370/370 = 100% |
| 같은 입력 전후 교대 대조 | 확인 | 8/8 = 100% |
| 새 실제 조회 경로 연결 | 1경로 확인 | 1/2 = 50% |

생성시각 {NOW.isoformat()}. 기준 v11 §5 이동·§6-B 출발 안내입니다. 분모31은23개 방향/제품 연결과8개 공식 이름 시험이며370에 포함됩니다. 370에는 구조 경계2개가 포함됩니다. 8은2상황×ABBA4회이고 독립 표본 수가 아닙니다. 마지막2는 이번 통제 장소/접근 조건의 실제 소스 조회 경로 수이며 서울 전체 성공률이나 실제 ETA 정확도가 아닙니다. 전체21분류는 조건부3/21·개선9/21·추가검증9/21 유지이고 완료율이 아닙니다.

## 원인과 수정

저장된 공덕 A3013 원문은 검암행·홍대입구방면인데 statnFid는홍대입구ID, statnTid는서울ID였습니다. [서울시 공식 명세](https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A)의 방면/종착/인접ID 필드를 실제 원문과 대조했습니다. 이 사례에서 필드 이름만으로 Tid를 열차의 진행 다음역으로 고정하는 것은 틀렸습니다. 모든 노선에서 두 ID가 반대라고 일반화하지 않았습니다.

정적 경로의 공식 다음역·종착역 이름을 방면 문구와 정확히 대조하고, 원문 인접ID가 검증된 정적 간선의 공식ID에 포함되는지 확인해 다음역ID를 선택합니다. 원문ID·방면 문구를 결과에 보존하며 출발 콜백에서도 같은 순수 검사를 다시 수행합니다. 임의 상하행 뒤집기·유사명·열차번호 접두사 추정은 하지 않습니다. 출발 관측기가 경로ID만 전달해 새 근거를 버리던 지점도 수정해 이름/인접ID를 깊은 사본으로 넘깁니다. 급행·중복·응답 완전성·생성시각·접근 이후·이미 출발 제외 조건은 유지합니다. 이전 통제 입력에 이름 증거가 없으면 기존 직접 다음역ID 비교만 유지합니다.

공덕 인접역의 정적 이름서울역과 서울시 이름서울이 달라 양쪽 인접ID가 완성되지 않았습니다. [공항철도 공식 시간표](https://www.airportrailroad.com/train/normal/info/030/0)가 같은 방향을 서울역 방면/서울(일반열차)로 표시하는 근거로, 공식서울ID에 서울역 별명1개만 자료에 등록했습니다. 기존696역 행과 원자료는 그대로 보존했습니다. 코드에 특정 역명 목록을 넣거나 일반적으로 역 접미사를 제거하지 않았습니다. 별명/역ID/노선/출처·기존 이름 충돌·중복을 적재 시 검사합니다. 내용 해시 변화는 기존 입력 판 검사에 반영됩니다.

## 재현·시험·순서 정정

수정 전 방향 시험22건은9실패·13통과였습니다. 첫 관련 실행은356통과·1실패였고, 통제 제품 시험이 콜백의 근거 누락을 잡았습니다. 수정 후357통과, 공식 이름 대응8건과 기존서울 소스5건을 포함한 최종370건은 모두 통과했습니다. Ruff7파일 통과. 기존 구문 경고1개를 로그에 보존했습니다.

공식 이름 코드의 초안 적용이 계약 기록보다 먼저 진행된 순서 오류가 있었습니다. 이전 보존본 검색은 일치 파일을 찾지 못했고, 내 추가 구간만 되돌린 원문 바이트가 직전 SHA256과 정확히 같은지 확인해 원본을 보존·복원했습니다. 이름 계약을 먼저 기록한 뒤 최종 코드를 다시 적용했습니다. 최초 이름 백업 중 코드 사본은 작성 중 판이며 검증된 직전 원본의 별도 경로가 [순서 정정 기록]({lnk(REPORT,EV/'alias-edit-order-correction-v1.json')})에 있습니다. 기존 파일·실패 로그·초안도 지우지 않았습니다.

저장 원문1개와 상태/도착시간을 바꾼 통제1상황을 전·후·후·전으로 재생했습니다. 원문의 A3013은 수정 전 경로 불일치, 수정 후 이미 출발로 제외됩니다. 통제 미래 응답은 수정 전 제외·수정 후 선택됩니다. 첫8회는 이름 대응이 없어서 모두 제외됐고, 이름 수정 후v2의8회를 따로 보존했습니다. ETA480초·생성시각·운행상태 변경은 명시된 통제값이며 실제 신선 응답이나 탑승자료가 아닙니다.

## 새 실제 응답과 비교 조건

{live['requests'][0]['started_at']}~{live['requests'][-1]['finished_at']} 제품 출발 관측기에서 공덕역 무료 서울시 도착API를 실제HTTP2회 조회했습니다. 두 응답 모두HTTP200 INFO-000·18/18행이고 바이트SHA256은 같습니다. 실제HTTP2응답과 고유내용1개18행을 구분합니다. 수집 스크립트의 예상1회/보관 응답 재사용 설명은 틀렸습니다. 해당 독립 소스 인스턴스에는 cache를 주입하지 않아 실제2회 호출됐으며 [정정 판정]({lnk(REPORT,EV/'source-assessment-v1.json')})에 실제 계수와 원문 해시를 우선하도록 기록했습니다. 원본 수집 메타는 당시 기록으로 보존합니다.

같은 조회시각 기준 시간표 모델과 현재 도착 적용을 비교했습니다. 5호선공덕→마포는 모델10분→현재13분 예상, 열차5562·방화행 마포방면·제공시각12:54:15·도착예측13:03:15로 실제 소스→제품 관측→출발 대조에 연결됐습니다. 공항철도공덕→홍대입구는 적합 예측이 없어 모델10분 재검증입니다. 이 새 실조회는 이름 대응을 추가하기 전 실행이며, 최종 이름 대응은 저장응답과 통제 재생으로 검증했습니다. 최종 공항철도 실제 승차 연결이 성공했다고 부르지 않습니다.

장소 좌표·접근2분·퇴장2분은 통제입니다. 실제ETA오차·탑승·결제·새지도웹경로0개·지도 개발자API0회입니다. 두 예상시간 차이는 실제 주행시간 오차가 아닙니다. 원문키반사0·인증키/인증URL 비저장 확인. [원문과 수집정보]({lnk(REPORT,ROOT/'datasets/mobility/raw'/S['tag'])}/)·[공식 이름 사실 기록]({lnk(REPORT,ROOT/'datasets/mobility/raw/subway_source_name_alias_20261009_v1')}/)은 git 제외 자료이며 출처는 서울특별시·AREX입니다.

mock 서버 시험(화면 반응): 이번 턴 안 했음.

실서버 확인(서버 응답): 서울시 무료 도착API HTTP2응답 확인. cs 프로젝트 서버HTTP·출발 알림 배달·배포 확인 안 했음.

## 제품 경로·대체·남은 검증

공식 이름/ID→정적 경로→출발 관측기의 이름/인접ID 전달→실시간 소스 선택→같은 근거로 콜백 재대조→후속 구간 모델 계산입니다. 신선도30/90/2초는 보관/제공시각/미래시각 정책이며 ETA 허용 오차가 아닙니다. 적합 응답이 없으면 기존 시간표 모델을 재검증하고 그 근거도 실패하면 기존 치명 결함 처리를 유지합니다. 후속 환승은 현재 운행정보가 아니라 모델입니다.

다음 최소 단위는 공항철도 실제0초 예측에서 출발·전역 운행 상태를 구분하고, 공식 실시간 웹 정보/운영자 시간표 등 대체 ETA 근거를 확보해 출발 안내를 검증하는 일입니다. 틀린 방면/시각을 느슨하게 받아 수치를 맞추지 않습니다. 급행·순환·남은 이름 대응·혼합 운임/누락 경로·1.2km 안 동일 출입점 웹 비교·실제ETA/탑승은 미완료입니다. 새 논문 알고리즘을 적용한 턴이 아니라 공식 관측/이름 계약을 바로잡은 턴입니다.

[새21개 기능 시각화]({lnk(REPORT,ASSETS/'mobility-readiness.html')})·[검증 원문]({lnk(REPORT,EV)}/)·[백업 명세]({lnk(REPORT,EV/'backup-manifest-v1.json')})·[이동 정본]({lnk(REPORT,WIKI)})에 연결합니다. 시각화는 내용/카드/링크/JS 구문만 검사하며 브라우저 렌더링은 미확인입니다. 커밋·푸시·배포·외부 메시지 전송을 하지 않았고 전21개 완료 판정을 내리지 않았습니다.

변경 파일: {', '.join('['+p.name+']('+lnk(REPORT,p)+')' for p in paths)}와 [공식ID 가공물]({lnk(REPORT,station_file)}). 기존696행 보존 검증과 원문 해시는 검증 폴더에 있습니다.
'''
with REPORT.open('x',encoding='utf8') as f:f.write(text)
for p,extra in [(WIKI,f'''\n\n## {NOW.strftime('%Y-%m-%d_%H%M')} 지하철 방면·인접ID와 공식 이름 연결 결과

공식 방면/종착 이름과 검증된 인접ID쌍을 대조하고 출발 관측기의 근거 누락을 수정했습니다. 공항철도서울역/서울 공식 이름1쌍만 자료에 추가·기존696행 보존. 신규31/31·관련370/370(구조2포함)·Ruff7파일, 저장응답/통제ABBA8회에서 실제 이미 출발한A3013은 계속 제외·통제 미래입력은 선택됩니다. 새HTTP2응답은 바이트가같고18행내용1개입니다. 실제5호선공덕→마포10→13분 예상 연결, 공항철도현재 예측 미연결·시간표10분 재검증. 장소/접근통제·실제ETA오차/탑승/새지도웹0·지도개발자API0. 수집메타의1회/보관재사용 설명과 초안 적용 순서는 정정 기록에 보존했습니다. 전21분류3/9/9 유지·전체미완료·배포안함. [보고서]({lnk(WIKI,REPORT)})·[시각화v45]({lnk(WIKI,ASSETS/'mobility-readiness.html')})·[검증]({lnk(WIKI,EV)}/).
'''),(DATA,f'''\n\n## {NOW.strftime('%Y-%m-%d_%H%M')} 공식 이름 대응과 공덕 제품 조회

[공식 이름 사실 기록]({lnk(DATA,ROOT/'datasets/mobility/raw/subway_source_name_alias_20261009_v1')}/)은 AREX 서울역방면/서울(일반열차)와 서울시 공식공항철도서울ID의 정확 대응1쌍입니다. 가공물source_aliases만 추가하고696역 행/원문은 보존했습니다. 역 접미사를 일반적으로 제거하지 않습니다.

[새 공덕 원문]({lnk(DATA,ROOT/'datasets/mobility/raw'/S['tag'])}/)은12:55 실제HTTP2회·각18/18행·같은바이트해시로 고유내용1개입니다. 수집메타의1회/보관재사용설명은틀려별도판정으로정정했습니다. 제품2경로중5호선공덕→마포현재13분·기준모델10분 예상연결, 공항철도미연결입니다. 장소/접근통제·실제ETA오차/탑승/지도웹0·지도개발자API0·키비저장. 원문은git제외이며운영적재물아닙니다. [보고서]({lnk(DATA,REPORT)})에370/370·교대8회·원문/이름 근거를 기록합니다.
''')]:
    expected=backup(p);old=p.read_text(encoding='utf8');assert sha(p)==expected;p.write_text(old+extra,encoding='utf8')
expected=backup(DEBUG);old=DEBUG.read_text(encoding='utf8');assert sha(DEBUG)==expected
DEBUG.write_text(f'''# 지하철 방면·인접역ID 대조와 이름 대응 누락

## 해결됨 (2026-10-09, 부분) — 방향 대조·근거 전달·공식 이름 연결

신규31/31·관련370/370으로 방면/종착/인접ID 대조와 제품 콜백 근거 전달, 공식 이름 대응1쌍을 검증했습니다. 저장A3013은 경로 불일치→이미 출발로 제외, 통제 미래입력은 선택됩니다. 실제5호선 제품 연결1/2·공항철도 적합 시각 미확인·실제ETA오차/탑승은 남습니다. [보고서]({lnk(DEBUG,REPORT)})·[시험 원문]({lnk(DEBUG,EV)}/).

발견 당시 기록:

{old.replace('## 미해결','발견 당시 상태: 미해결')}
''',encoding='utf8')
save(EV/'backup-manifest-v1.json',{'created_at':NOW.isoformat(),'backups':backups,'order_correction':order})
assert all(sha(ROOT/x['backup'])==x['sha256'] for x in backups)
cards=''.join(f'<article data-status="{escape(f["status"])}"><p class="tag">{escape(f["status"])}</p><h3>{escape(f["name"])}</h3><p>{escape(f["scope"])}</p><p>{escape(f["metric"])}</p><details><summary>근거와 남은 검증 보기</summary><p>{escape(f["reason"])}</p><p>{escape(f["need"])}</p></details></article>' for f in catalog['features'])
old_html=(PRIOR/'mobility-readiness.html').read_text(encoding='utf8');style=re.search('<style>(.*?)</style>',old_html,re.S).group(1);js=re.search('<script>(.*?)</script>',old_html,re.S).group(1)
page=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 v45 — 방면과 인접역 대조</title><style>{style}</style><main><p>triPilot / 서울 이동 / v45 / {NOW.isoformat()}</p><h1>열차의 실제 방면과 인접역을 함께 대조합니다</h1><p class="lead">방향 근거를 출발 관측까지 연결했습니다. 공항철도 실제 승차 안내는 아직 확인되지 않았습니다.</p><div class="notice">새31/31 · 관련370/370 통과. 실제 조회2경로 중1경로 연결은 서울 전체 정확도나 실탑승 성공률이 아닙니다.</div>
<svg viewBox="0 0 840 190" role="img" aria-labelledby="title desc"><title id="title">방향 근거를 보존하는 경로</title><desc id="desc">공식 다음역 방면과 종착 이름을 정적 경로, 인접ID와 대조한 뒤 그 근거를 출발 관측과 콜백에 전달합니다. 이미 출발한 열차는 계속 제외합니다.</desc><g font-size="17" fill="#193a56"><rect x="10" y="20" width="245" height="130" fill="#eef3f8"/><text x="25" y="55">공식 방면 · 종착 이름</text><text x="25" y="88">정적 경로 · 인접ID쌍</text><text x="25" y="121">정확 이름1쌍 추가</text><text x="270" y="88">→</text><rect x="300" y="20" width="245" height="130" fill="#eaf4f1"/><text x="315" y="55">선택 · 출발 관측 전달</text><text x="315" y="88">같은 근거로 콜백 대조</text><text x="315" y="121">새31개 통제 시험 통과</text><text x="560" y="88">→</text><rect x="590" y="20" width="240" height="130" fill="#fff1da"/><text x="605" y="55">이미 출발 · 오래됨 제외</text><text x="605" y="88">실제5호선 연결 확인</text><text x="605" y="121">공항철도 ETA 검증 남음</text></g></svg>
<table><thead><tr><th>자료</th><th>결과</th><th>해석</th></tr></thead><tbody><tr><td>실제HTTP 응답</td><td>2개 · 각18행</td><td>동일 바이트 · 고유내용1개</td></tr><tr><td>5호선 공덕→마포</td><td>모델10→현재13분</td><td>예상 재계산 · 접근/퇴장 통제</td></tr><tr><td>공항철도 공덕→홍대입구</td><td>모델10분 재검증</td><td>실제 승차 연결 미확인</td></tr><tr><td>기존A3013·통제 재생</td><td>교대8/8 확인</td><td>이미 출발 제외 · 통제 미래 선택</td></tr></tbody></table>
<h2>21개 기능의 현재 분류</h2><p>조건부3/21 · 개선9/21 · 추가검증9/21. 완료율이 아닙니다. 다른20개 기능의 수치는 이전 근거이며 이번 재측정이 아닙니다.</p><label for="filter">판정별 보기</label><select id="filter"><option>전체</option><option>조건부 사용</option><option>개선 필요</option><option>추가 검증</option></select><div class="grid">{cards}</div><p>실제ETA오차/탑승/결제0개 · 새지도웹0개 · 지도 개발자API0회. 통제 자료는 독립 검증이 아닙니다.</p><p><a href="{lnk(ASSETS/'mobility-readiness.html',REPORT)}">보고서 읽기</a> · <a href="{lnk(ASSETS/'mobility-readiness.html',EV)}">시험·원문 판정 보기</a> · <a href="readiness-catalog.json">21개 기능 근거 보기</a> · <a href="{lnk(ASSETS/'mobility-readiness.html',EV/'backup-manifest-v1.json')}">백업 보기</a></p><p>브라우저 렌더링 미확인 · 내용/링크/스크립트 검증.</p></main><script>{js}</script></html>'''
with (ASSETS/'mobility-readiness.html').open('x',encoding='utf8') as f:f.write(page)
assert len(re.findall('<article data-status=',page))==21
links=[]
for dest in re.findall('href="([^"]+)"',page):assert (ASSETS/dest).resolve().exists(),dest;links.append(dest)
with (EV/'visual-script-v1.js').open('x',encoding='utf8') as f:f.write(js)
cmd=[shutil.which('node'),'--check',str(EV/'visual-script-v1.js')];n=subprocess.run(cmd,capture_output=True,text=True)
assert n.returncode==0
save(EV/'visual-validation-v1.json',{'command':cmd,'exit_code':n.returncode,'stdout':n.stdout,'stderr':n.stderr,'cards':21,'local_links':links,'counts':catalog['counts'],'browser_render_checked':False})
for folder in [ROOT/'datasets/mobility/raw'/S['tag'],ROOT/'datasets/mobility/raw/subway_source_name_alias_20261009_v1']:
    for p in folder.iterdir():
        if p.is_file():hashes[rel(p)]=sha(p)
assert len(hashes)==269 and all(sha(ROOT/p)==h for p,h in hashes.items())
preserved={p:sha(ROOT/p)==h for p,h in S['prior_artifact_hashes'].items() if p not in {rel(WIKI),rel(DATA)}}
assert all(preserved.values())
save(EV/'verification-proof-v1.json',{'created_at':NOW.isoformat(),'source_test_data_hashes':hashes,'new_tests':31,'related_tests':370,'abba_runs':8,'prior_artifacts_preserved':preserved,'station_rows_unchanged':696,'source_aliases_added':1,'full_feature_completion':False})
shutil.copy2(Path(__file__),EV/Path(__file__).name)
files=[p for folder in (EV,ASSETS) for p in folder.iterdir() if p.is_file()]+[REPORT,WIKI,DATA,DEBUG]
save(EV/'final-integrity-v1.json',{'created_at':NOW.isoformat(),'source_test_data_hashes':hashes,'artifact_hashes':{rel(p):sha(p) for p in files},'backups':backups,'report':rel(REPORT),'assets':rel(ASSETS),'evidence':rel(EV),'full_feature_completion':False})
print(json.dumps({'report':rel(REPORT),'assets':rel(ASSETS),'evidence':rel(EV),'source_hashes':len(hashes),'artifact_hashes':len(files),'backups':len(backups),'tests':370,'new_tests':31,'preserved_prior_artifacts':len(preserved)},ensure_ascii=False))
