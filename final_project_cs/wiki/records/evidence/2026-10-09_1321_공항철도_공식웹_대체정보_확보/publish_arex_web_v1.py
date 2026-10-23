from pathlib import Path
from datetime import datetime
from html import escape
from collections import Counter
import hashlib, json, os, re, shutil, subprocess

ROOT=Path(__file__).resolve().parents[2]; CS=ROOT/'final_project_cs'
NOW=datetime.now().astimezone(); TAG=NOW.strftime('%Y-%m-%d_%H%M')+'_공항철도_공식웹_대체정보_확보'
EV=CS/'wiki/records/evidence'/TAG; EV.mkdir(exist_ok=False)
ASSETS=CS/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v46'; ASSETS.mkdir(exist_ok=False)
REPORT=CS/'wiki/records/reports'/f'{TAG}.md'
DEBUG=CS/'wiki/records/reports/debugs'/f'{TAG}.md'
WIKI=CS/'wiki/teams/mobility.md'; DATA=ROOT/'datasets/mobility/REPORT.md'
PRIOR=CS/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v45'
BASE=CS/'wiki/records/evidence/2026-10-09_1248_지하철_방면과_인접역ID_대조/final-integrity-v1.json'
state=json.loads((Path(__file__).parent/'arex-gap-state-v1.json').read_text(encoding='utf8'))
RAW=ROOT/state['raw']; LIVE=json.loads((RAW/'acquisition-v1.json').read_text(encoding='utf8'))
URL='https://www.airportrailroad.com/train/normal/live'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p): return p.relative_to(ROOT).as_posix()
def link(p,q): return os.path.relpath(q,p.parent).replace('\\','/')
def save(p,d):
    with p.open('x',encoding='utf8') as f: json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False)
baseline=json.loads(BASE.read_text(encoding='utf8'))
preserved={p:sha(ROOT/p)==h for p,h in {**baseline['source_test_data_hashes'],**baseline['artifact_hashes']}.items()}
assert len(preserved)==309 and all(preserved.values())
save(EV/'baseline-verification-v1.json', {'checked_at':NOW.isoformat(),'matches':preserved,'count':309})

def snapshot(station,code,start,end,up,down):
    def group(direction,origin,items):
        return {'direction':direction,'rows':[{'kind':'일반','eta_text':f'{mins}분 후 도착 예정',
            'departure_text':f'{time} 출발 ({orig or origin} 출발)','location_text':location}
            for mins,time,location,orig in items]}
    return {'source_url':URL,'capture_method':'CUA 화면 DOM의 표시값 추출; 도구 결과에서 JSON 직렬화',
        'observed_between':[start,end],'station':station,'station_code':code,
        'provider_generated_at':None,'train_identity_visible':False,'full_response_count_visible':False,
        'groups':[group('서울역 방면','인천공항2터미널',up),group('인천공항2터미널 방면','서울역',down)]}
observations=[
 snapshot('공덕','020','2026-10-09T13:13:54+09:00','2026-10-09T13:14:07+09:00',
    [(2,'13:16','1개역 전',None),(8,'13:22','3개역 전',None),(14,'13:29','4개역 전',None),(22,'13:36','5개역 전',None),(27,'13:42','6개역 전','검암')],
    [(2,'13:16','1개역 전',None),(10,'13:24','출발 전',None),(16,'13:30','출발 전',None),(25,'13:39','출발 전',None),(32,'13:46','출발 전',None)]),
 snapshot('홍대입구','030','2026-10-09T13:14:07+09:00','2026-10-09T13:15:05+09:00',
    [(4,'13:19','2개역 전',None),(10,'13:25','2개역 전',None),(18,'13:33','4개역 전',None),(23,'13:38','5개역 전','검암'),(27,'13:42','6개역 전',None)],
    [(0,'13:15','출발 전',None),(5,'13:20','2개역 전',None),(12,'13:27','출발 전',None),(19,'13:34','출발 전',None),(27,'13:42','출발 전',None)]),
 snapshot('공덕','020','2026-10-09T13:17:49+09:00','2026-10-09T13:18:24+09:00',
    [(4,'13:22','2개역 전',None),(11,'13:29','3개역 전',None),(18,'13:36','4개역 전',None),(24,'13:42','5개역 전','검암'),(28,'13:46','6개역 전',None)],
    [(6,'13:24','1개역 전',None),(12,'13:30','출발 전',None),(21,'13:39','출발 전',None),(28,'13:46','출발 전',None),(36,'13:54','출발 전',None)])]
save(RAW/'web-observations-v1.json',{'created_at':NOW.isoformat(),'source':'AREX 공항철도','source_url':URL,
    'snapshots':observations,'snapshot_count':3,'unique_stations':2,'rows':30,
    'claim':'公式 화면의 사실값만 로컬 진단용 보존. 실제 차량 도착·탑승이나 30개 독립 운행 표본이 아님.'.replace('公式','공식')})
rows=[r for s in observations for g in s['groups'] for r in g['rows']]
assert len(rows)==30
numeric=[]
for r in rows:
    match=re.fullmatch(r'([0-9]+)분 후 도착 예정',r['eta_text'])
    assert match and re.fullmatch(r'[0-2][0-9]:[0-5][0-9] 출발 \(.+ 출발\)',r['departure_text'])
    numeric.append(int(match[1]))
raw_doc=json.loads((RAW/'response-v1.json').read_text(encoding='utf8'))
assert len(raw_doc['realtimeArrivalList'])==raw_doc['errorMessage']['total']==17
assert len(LIVE['airport_rows'])==5 and all(r['eta_seconds']==0 for r in LIVE['airport_rows'])
assessment={'created_at':NOW.isoformat(),'browser_snapshots':3,'unique_stations':2,'direction_groups':6,
    'display_rows':30,'numeric_minute_rows':len(numeric),'positive_minute_rows':sum(m>0 for m in numeric),
    'zero_minute_rows':sum(m==0 for m in numeric),'api_actual_success_responses':1,'api_raw_rows':17,
    'api_airport_filtered_rows':5,'api_airport_zero_eta_rows':5,
    'current_product_selection':LIVE['selection'],'web_current_airport_direction_minutes':[6,12,21,28,36],
    'same_train_paired_rows':0,'actual_eta_error_samples':0,'actual_boardings':0,'automated_fallback_connected':False,
    'missing_for_product':['공급자 예측 생성시각','열차/운행 식별자','응답 역 귀속 및 전체 범위 근거','분 단위 반올림/절삭 정의'],
    'transition_observations':[{'new_selection':'홍대입구','previous_station_first_last':['05:37','00:34','05:24','00:04'],
        'updated_first_last':['05:34','00:31','05:28','00:08']},
        {'new_selection':'공덕','previous_station_first_last':['05:34','00:31','05:28','00:08'],
         'updated_first_last':['05:37','00:34','05:24','00:04']}],
    'limits':'웹3스냅샷은 같은 시간대 반복이며 독립 운행/정확도 표본이 아니다. API와 웹의 열차 식별자가 대응하지 않아 ETA 오차를 계산하지 않는다. 두 UI 전환은 선택값만으로 목록 귀속을 보장할 수 없다는 근거이며 공급자 내부 원인은 미확인.',
    'research_sources':[URL,'https://gtfs.org/documentation/realtime/feed-entities/trip-updates/',
        'https://old.gtfs.org/realtime/best-practices/'],
    'research_application':'GTFS의 안정적 운행 식별·개별 예측 생성시각 분리 원칙을 참고. AREX가 GTFS를 제공하거나 같은 정확도를 보장한다고 추정하지 않는다.',
    'collection_failures':[{'script':'collect_arex_gap_v1.py','reason':'arrivals에 line_id 인자를 잘못 전달; HTTP 이전 TypeError'},
        {'script':'collect_arex_gap_v2.py','reason':'정상 정규화 자료 미확보; assert 실패·HTTP 응답 계수 미기록'},
        {'script':'collect_arex_gap_v3.py','reason':'권한 검토 후 정상 응답1개; 계수/원문 보존'}],
    'screenshot_captured':False,'screenshot_limit':'CUA 화면 캡처 호출은 실패했고 DOM 표시값으로 관측했다.'}
save(EV/'source-assessment-v1.json',assessment)
backups=[]
for p in (WIKI,DATA):
    before=sha(p); dest=p.parent/'_backup'/TAG/p.name; dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(p,dest); assert sha(dest)==before
    backups.append({'source':rel(p),'backup':rel(dest),'sha256':before})
save(EV/'backup-manifest-v1.json',{'created_at':NOW.isoformat(),'backups':backups})
body=f'''# 공항철도 공식 웹 대체 도착정보 확보

공식 웹에서 공덕·홍대입구 양방향 도착예측을 확보했습니다. 현재 서울시 API에 없는 미래 도착값을 확인했지만 제품 자동 연결은 아직 완료하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 기존 코드·시험·자료 보존 확인 | 일치 | 309/309 = 100% |
| 공식 웹 관측 | 확보 | 3/3 = 100% |
| 화면 숫자·시각 형식 검사 | 통과 | 30/30 = 100% |
| 대체 도착정보 자동 연결 | 미완료 | 0/1 = 0% |

생성시각 {NOW.isoformat()}. v11 §5 이동·§6-B 출발 안내의 대체 정보 조사입니다. 분모3은 두 역을 공덕→홍대입구→공덕으로 선택해 갱신 후 보존한 화면 관측 수입니다. 30은 그 화면의 표시행이며 독립 열차 수나 정확도 표본 수가 아닙니다. 기존21개 판정은 조건부3·개선9·추가검증9로 유지합니다.

## 확보한 사실과 비교 제한

[공항철도 공식 실시간 페이지]({URL})에서 일반열차·공덕020/홍대입구030을 직접 선택했습니다. 정적 웹 읽기에는 ETA가 없었으나 실제 브라우저 DOM에는 두 방향 각5개씩 예측이 나타났습니다. 3관측30행 중 양수29행·0분1행입니다. 전체 HTML·사진·소개글을 저장하지 않고 시간/방향/역 등 사실값을 로컬 진단 자료로 보존했습니다. 출처 AREX 공항철도, 운영 적재·외부 재배포 안 했음.

공덕 최신 웹 관측구간13:17:49~13:18:24의 공항 방향은6·12·21·28·36분 후였습니다. 서울시API13:17:25.252339~13:17:25.411426 실제HTTP200 INFO-000 원문은17/17행이며 공항철도 필터 후5행입니다. 5행 전부ETA0, 일반 공항 방향A2119는13:16:09생성·도착상태1이라 접근2분 뒤보다 이른 것으로 제외됐습니다. 나머지는 반대 방향/급행 등 경로 조건으로 제외됐습니다. 현재 제품 선택기는 예측을 고르지 않았습니다.

웹 열차번호가 표시되지 않아 API A2119와 웹13:24출발 표기를 같은 열차로 연결할 수 없습니다. 같은 역의 비슷한 시간대 자료가 다르게 미래 후보를 보여준다는 관측이며, 동일 열차의6분 오차나 웹 정확도 우위로 계산하지 않습니다. 웹 `13:24 출발 (서울역 출발)`은 표시 문자열 그대로 보존하며 선택역 출발시각/기점 출발시각 의미를 단정하지 않습니다. 실제ETA오차·탑승·결제·독립 웹 경로 비교0건입니다.

## 자동 연결 전에 해결할 원인

역 선택 직후 선택창은 홍대입구인데 첫차/막차와 도착목록은 이전 공덕 값이 남았습니다. 다음 DOM 관측에서 홍대입구의 첫차/막차로 바뀌었습니다. 공덕으로 돌아오는 전환에서도 같은 현상을 관측했습니다. 선택값만 읽어 목록에 역ID를 붙이면 다른 역의 ETA를 연결할 수 있습니다. 표시 목록 갱신 확인과 응답의 역 귀속을 함께 검증해야 하며 UI 갱신 완료와 공급자 예측 신선도도 구분해야 합니다.

화면 표시 범위에서 공급자 생성시각·안정적 열차/운행ID·전체 반환건수·분 단위 절삭/반올림 정의는 확인하지 못했습니다. DOM에 안 보이는 필드·문서화된 별도 제공 경로가 있을 수 있으므로 소스가 영구 불가능하다고 판정하지 않습니다. [GTFS 운행 갱신 명세](https://gtfs.org/documentation/realtime/feed-entities/trip-updates/)는 정보 부재를 정시 운행으로 추정하지 않고, 운행을 유일하게 대응하도록 정합니다. [공식 권장 관행](https://old.gtfs.org/realtime/best-practices/)은 개별 예측 갱신시각과 전체 feed 갱신시각을 분리합니다. 이 원칙을 검증 조건으로 참고하며 AREX가 GTFS라는 뜻은 아닙니다.

다음 최소 단위는 공식 시간표의 운행ID/역별 시각 및 문서화된 실시간 제공 경로를 확인해 정확한 운행 대응·예측시각 계약을 만드는 것입니다. `분×60`을 서울시 생성시각에 더하거나 웹 조회시각을 공급자 생성시각으로 바꾸지 않습니다. 화면0분을 정확0초로 바꾸지 않습니다. 새 논문 예측모델을 적용한 턴이 아니며 자료 의미와 결합 조건을 먼저 확보했습니다.

## 실행과 보존

첫 수집 스크립트는 인자명을 잘못 전달해 HTTP 이전에 실패했습니다. 둘째는 정상 정규화 자료를 얻지 못했고 HTTP응답 계수를 보존하지 못했습니다. 실패를 성공 건수로 세지 않습니다. 셋째는 권한 검토 후 실제 정상응답1개를 원문과 해시로 보존했습니다. 인증키·인증URL 비저장, 원문에 인증키 반사 없음 확인. 지도 개발자API 직접 호출0회. 실제 성공HTTP1개와 미계수 실패시도를 구분합니다. 기존 제품 코드·시험은 바꾸지 않아 기존370시험을 다시 실행하지 않았습니다. 이번 검사는 보존309개와 새30행 자료 구조입니다.

mock 서버 시험(화면 반응): 이번 턴 안 했음.

실서버 확인(서버 응답): 서울시 무료 도착API 정상1응답17행, AREX 공식 웹3관측 확인. cs 프로젝트 서버HTTP·출발 알림 배달·배포 확인 안 했음.

[관측 원문 자료]({link(REPORT,RAW)}/)·[판정과 실패 기록]({link(REPORT,EV/'source-assessment-v1.json')})·[백업 명세]({link(REPORT,EV/'backup-manifest-v1.json')})·[21개 기능 시각화]({link(REPORT,ASSETS/'mobility-readiness.html')})를 보존합니다. 화면 캡처 호출은 실패했고 DOM 관측을 사용했습니다. 커밋·푸시·배포·외부 메시지 전송은 안 했습니다.
'''
with REPORT.open('x',encoding='utf8') as f:f.write(body)
with DEBUG.open('x',encoding='utf8') as f:f.write(f'''# 공항철도 공식 웹 도착정보의 자동 연결 근거 공백

## 미해결

공식 웹 미래 도착정보는 확보했지만 역 선택/목록 갱신의 비동기 차이·운행ID/예측 생성시각 공백을 자동 연결 계약으로 해결하지 못했습니다. 현재 제품은 기존 시간표 모델 재검증을 유지합니다.

실측: 웹3관측30표시행·API1정상응답17행(공항철도5행 ETA0)·UI역 전환2회에서 이전 목록 표시. 공급자 내부 원인은 미확인입니다. 운행ID가 대응되지 않아 동일열차 ETA오차0쌍입니다.

위험: 조회한 역 이름만으로 남아 있는 목록에 새 역ID를 붙이거나 수집시각을 생성시각으로 대체하면 잘못된 승차 안내가 생깁니다. 기존 상품 코드·도착 선택 조건을 느슨하게 바꾸지 않았습니다.

재현: 공식페이지의 역선택에서 공덕→홍대입구→공덕을 선택하고 직후/갱신 뒤 표시를 비교합니다. 이번 자료의 검사는 보존된 publisher 스크립트와 [판정]({link(DEBUG,EV/'source-assessment-v1.json')})에 있습니다. 동적 웹 현상이 항상 재현된다고 보장하지 않습니다.

[보고서]({link(DEBUG,REPORT)})·[자료]({link(DEBUG,RAW)}/).
''')
for p,txt in [(WIKI,f'\n\n## {NOW.strftime("%Y-%m-%d_%H%M")} 공항철도 공식 웹 대체정보 확보\n\n공식 웹 공덕/홍대입구 양방향3관측30행(양수29·0분1) 확보. 최신 공덕 공항방향6분 이후5후보, 비슷한 시각 서울시 정상1응답17행의 공항철도5행은ETA0이며 제품 선택 없음. 동일 열차ID 미대응으로 오차 대조가 아닙니다. 역 선택 직후 이전 목록이 남는 전환2회를 관측했고 공급자 생성시각/운행ID/목록 귀속 계약 해결이 남았습니다. 자동 대체소스 연결·실제ETA/탑승 미완료. 전21분류3/9/9 유지. [보고서]({link(WIKI,REPORT)})·[시각화v46]({link(WIKI,ASSETS/"mobility-readiness.html")})·[검증]({link(WIKI,EV)}/).\n'),
    (DATA,f'\n\n## {NOW.strftime("%Y-%m-%d_%H%M")} 공항철도 공식 웹 도착정보\n\n[자료]({link(DATA,RAW)}/)의 web-observations-v1.json은 AREX 공덕/홍대입구 표시값3관측30행이며 CUA DOM 추출 결과에서 직렬화했습니다. 전체 HTML/사진/소개글은 비저장·로컬 사실값 진단·운영 적재/재배포 안함. 두 역의 같은 시간대 반복이며 독립30열차가 아닙니다. 무료 서울시 실제 정상1응답17행(공항철도 필터5행 ETA0)과 비교했지만 열차ID/생성시각이 웹에 안 보여 동일열차 오차 계산0쌍입니다. 1차 인자 오류와2차 정상자료 미확보/계수 누락 실패는 판정 기록에 보존. 지도개발자API0·실제탑승0. [보고서]({link(DATA,REPORT)}).\n')]:
    expected=next(b['sha256'] for b in backups if b['source']==rel(p));assert sha(p)==expected
    p.write_text(p.read_text(encoding='utf8')+txt,encoding='utf8')
catalog=json.loads((PRIOR/'readiness-catalog.json').read_text(encoding='utf8'))
for item in catalog['features']:
    if item['name']=='실시간 지하철·버스 도착':
        item['prior_need_v45']=item['need']
        item['need']='v46: AREX 공식 웹2역3관측30행의 도착분/방향 확보. 같은 시간대 공덕API17행 중공항철도5행 ETA0인데 웹은 공항 방향6분 이후후보5개 표시. 운행ID 대응0쌍이라 같은열차 오차 아님. 선택역과 이전목록이 함께 표시되는 UI전환2회 확인. 공급자 생성시각·운행ID·응답 역귀속·전체범위·분 단위 정의를 확보해 자동대체 연결해야 합니다. 제품 자동 연결·실제ETA오차/탑승 미완료.'
        item['web_alternate_v46']={'snapshots':3,'stations':2,'display_rows':30,'api_raw_rows':17,'same_train_pairs':0,'product_connected':False}
catalog.update(created_at=NOW.isoformat(),scope='공항철도 공식 웹 대체정보 확보·자동 연결 근거 공백',full_feature_completion=False,prior_catalog_sha256=sha(PRIOR/'readiness-catalog.json'))
assert len(catalog['features'])==21 and dict(Counter(x['status'] for x in catalog['features']))==catalog['counts']
save(ASSETS/'readiness-catalog.json',catalog)
old=(PRIOR/'mobility-readiness.html').read_text(encoding='utf8');style=re.search(r'<style>(.*?)</style>',old,re.S)[1];js=re.search(r'<script>(.*?)</script>',old,re.S)[1]
cards=''.join(f'<article data-status="{escape(i["status"])}"><p class="tag">{escape(i["status"])}</p><h3>{escape(i["name"])}</h3><p>{escape(i["scope"])}</p><p>{escape(i["metric"])}</p><details><summary>근거와 남은 검증 보기</summary><p>{escape(i["reason"])}</p><p>{escape(i["need"])}</p></details></article>' for i in catalog['features'])
page=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 v46 — 공식 웹 대체정보</title><style>{style}</style><main><p>triPilot / 서울 이동 / v46 / {NOW.isoformat()}</p><h1>공항철도 대체 도착정보를 확보했습니다</h1><p class="lead">공식 웹은 미래 도착예측을 보여줍니다. 자동 연결에 필요한 운행ID·생성시각 확인은 남았습니다.</p><div class="notice">3화면30표시행은 30개 독립 열차나 정확도 표본이 아닙니다. 전체21개 기능 완료가 아닙니다.</div><svg viewBox="0 0 840 170" role="img" aria-label="대체 소스 검증 순서"><g font-size="18" fill="#193a56"><rect x="10" y="20" width="240" height="125" fill="#eef3f8"/><text x="25" y="55">서울시 실제 조회</text><text x="25" y="90">공항철도5행 ETA0</text><text x="25" y="125">접근 이후 후보 없음</text><text x="265" y="90">→</text><rect x="300" y="20" width="240" height="125" fill="#eaf4f1"/><text x="315" y="55">공식 웹 대체정보</text><text x="315" y="90">2역 · 3관측 · 30행</text><text x="315" y="125">미래 도착분 확보</text><text x="555" y="90">→</text><rect x="590" y="20" width="240" height="125" fill="#fff1da"/><text x="605" y="55">자동 연결 검증 남음</text><text x="605" y="90">역 귀속 · 운행ID</text><text x="605" y="125">예측 생성시각</text></g></svg><table><thead><tr><th>자료</th><th>확보</th><th>해석</th></tr></thead><tbody><tr><td>공식 웹</td><td>30/30 숫자형 표시</td><td>양수29 · 0분1</td></tr><tr><td>새 서울시API</td><td>17/17 원문행</td><td>공항철도 필터5행 ETA0</td></tr><tr><td>동일 열차 대조</td><td>0쌍</td><td>운행ID 미대응 · 오차 계산 안 함</td></tr><tr><td>대체 자동 연결</td><td>0/1</td><td>계약 검증 남음</td></tr></tbody></table><h2>21개 기능의 현재 분류</h2><p>조건부3/21 · 개선9/21 · 추가검증9/21. 분류 비중이며 완료율이 아닙니다. 다른20개 기능은 이번 재측정이 아닙니다.</p><label for="filter">판정별 보기</label><select id="filter"><option>전체</option><option>조건부 사용</option><option>개선 필요</option><option>추가 검증</option></select><div class="grid">{cards}</div><p><a href="{link(ASSETS/'mobility-readiness.html',REPORT)}">보고서 읽기</a> · <a href="{link(ASSETS/'mobility-readiness.html',EV/'source-assessment-v1.json')}">관측 판정 보기</a> · <a href="readiness-catalog.json">21개 기능 근거 보기</a> · <a href="{link(ASSETS/'mobility-readiness.html',EV/'backup-manifest-v1.json')}">백업 보기</a></p><p>실제ETA오차/탑승/결제0개 · 지도개발자API0회 · 자동 연결 미완료. 이 새 시각화 브라우저 렌더링은 미확인입니다.</p></main><script>{js}</script></html>'''
with (ASSETS/'mobility-readiness.html').open('x',encoding='utf8') as f:f.write(page)
with (EV/'visual-script-v1.js').open('x',encoding='utf8') as f:f.write(js)
n=subprocess.run([shutil.which('node'),'--check',str(EV/'visual-script-v1.js')],capture_output=True,text=True); assert n.returncode==0
assert len(re.findall('<article data-status=',page))==21
for dest in re.findall('href="([^"]+)"',page): assert (ASSETS/dest).resolve().exists()
for dest in re.findall(r'\]\(([^)]+)\)',body):
    if not dest.startswith('http'): assert (REPORT.parent/dest).resolve().exists(),dest
for p in (REPORT,DEBUG,WIKI,DATA,ASSETS/'mobility-readiness.html'):
    # 출력 전 외국어 오탈자가 들어가지 않았는지 확인한다.
    assert '公式' not in p.read_text(encoding='utf8')
shutil.copy2(Path(__file__),EV/Path(__file__).name)
for name in ['collect_arex_gap_v1.py','collect_arex_gap_v2.py','collect_arex_gap_v3.py']:
    shutil.copy2(Path(__file__).parent/name,EV/name)
sourcehashes=dict(baseline['source_test_data_hashes'])
for p in RAW.iterdir():
    if p.is_file():sourcehashes[rel(p)]=sha(p)
assert all(sha(ROOT/p)==h for p,h in sourcehashes.items())
old_artifacts={p:sha(ROOT/p)==h for p,h in baseline['artifact_hashes'].items() if p not in {rel(WIKI),rel(DATA)}}
assert len(old_artifacts)==38 and all(old_artifacts.values())
files=[p for d in (EV,ASSETS) for p in d.iterdir() if p.is_file()]+[REPORT,DEBUG,WIKI,DATA]
save(EV/'final-integrity-v1.json',{'created_at':NOW.isoformat(),'source_test_data_hashes':sourcehashes,
    'artifact_hashes':{rel(p):sha(p) for p in files},'prior_artifacts_preserved':old_artifacts,'backups':backups,
    'full_feature_completion':False,'report':rel(REPORT),'assets':rel(ASSETS),'evidence':rel(EV)})
print(json.dumps({'report':rel(REPORT),'assets':rel(ASSETS),'evidence':rel(EV),'rows':30,'snapshots':3,
    'source_hashes':len(sourcehashes),'artifact_hashes':len(files),'backups':len(backups)},ensure_ascii=False))
