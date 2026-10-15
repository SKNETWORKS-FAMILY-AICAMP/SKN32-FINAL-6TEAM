from pathlib import Path
from datetime import datetime
from collections import Counter
from html import escape
import difflib,gzip,hashlib,json,os,re,shutil,subprocess,xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2];CS=ROOT/'final_project_cs';NOW=datetime.now().astimezone()
state=json.loads((Path(__file__).parent/'published-boarding-state-v1.json').read_text(encoding='utf8'))
TAG=NOW.strftime('%Y-%m-%d_%H%M')+'_공항철도_공표승차시간_복구검증'
EV=ROOT/state['evidence'];RAW=ROOT/state['raw'];DEBUG=ROOT/state['debug']
REPORT=CS/'wiki/records/reports'/f'{TAG}.md';ASSETS=CS/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v47';ASSETS.mkdir(exist_ok=False)
WIKI=CS/'wiki/teams/mobility.md';DATA=ROOT/'datasets/mobility/REPORT.md';BASE=ROOT/'datasets/mobility/processed/mobility'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):return p.relative_to(ROOT).as_posix()
def link(p,q):return os.path.relpath(q,p.parent).replace('\\','/')
def save(p,d):
 with p.open('x',encoding='utf8') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False)
prior=json.loads((ROOT/state['base_manifest']).read_text(encoding='utf8'))
owned={rel(CS/'app/domains/travel_ops/instances/mobility/engine'/n) for n in ['runtime.py','verify_time.py','datacheck.py']}|{rel(BASE/'MANIFEST_git_v1.json')}
prior_source={p:sha(ROOT/p)==h for p,h in prior['source_test_data_hashes'].items() if p not in owned}
prior_artifacts={p:sha(ROOT/p)==h for p,h in prior['artifact_hashes'].items() if p not in {rel(WIKI),rel(DATA)}}
assert all(prior_source.values()) and all(prior_artifacts.values())
save(EV/'unchanged-baseline-v1.json',{'sources':prior_source,'artifacts':prior_artifacts,'owned_changes':sorted(owned)})
replay=json.loads((EV/'product-replay-v1.json').read_text(encoding='utf8'))
suite=ET.parse(EV/'related-v1.xml');cases=list(suite.iter('testcase'))
assert len(cases)==467 and not list(suite.iter('failure')) and not list(suite.iter('error')) and not list(suite.iter('skipped'))
new_count=sum(t.get('classname','').endswith('test_published_boarding_v1') for t in cases);assert new_count==26
assert json.loads((EV/'ruff-v1-run.json').read_text(encoding='utf8'))['exit_code']==0
express=json.loads((Path(__file__).parent/'arex-express-published-v1.json').read_text(encoding='utf8'));save(RAW/'express-published-times-v1.json',express)
facts=json.loads((RAW/'published-minutes-v1.json').read_text(encoding='utf8'))
allowed={(g['day_type'],g['dir']):{int(h)*60+m for h,ms in g['hours'].items() for m in ms} for g in facts['groups']}
unsupported=[]
with gzip.open(BASE/'timetable_v1.jsonl.gz','rt',encoding='utf8') as f:
 for line in f:
  r=json.loads(line)
  if r.get('line')==facts['line'] and r.get('station_nm')==facts['station']:
   h,m,s=map(int,r['dep_time'].split(':'))
   if h*60+m not in allowed[(r['day_type'],r['dir'])]:unsupported.append(r)
def sec(time):h,m=map(int,time.split(':'));return h*3600+m*60
pattern=[]
for day in ['weekday','holiday']:
 for direction in ['U','D']:
  observed=sorted(sum(x*y for x,y in zip(map(int,r['dep_time'].split(':')),[3600,60,1])) for r in unsupported if r['day_type']==day and r['dir']==direction)
  published=sorted(sec(r['seoul_arrive' if direction=='U' else 'seoul_depart']) for r in express['rows'] if r['day_type']==day)
  offsets=[a-b for a,b in zip(observed,published)]
  assert len(observed)==len(published)==26 and len(set(offsets))==1
  pattern.append({'day_type':day,'dir':direction,'paired_by_sorted_order':26,'offset_seconds':offsets[0],
   'inference':'공식 직통열차 서울역 도착/출발 시각에서 일정한 이동시간 차이. 운행ID를 잃어 같은 열차임을 개별 확정하지는 않음.'})
save(EV/'source-assessment-v1.json',{'created_at':NOW.isoformat(),'stored_hongik_rows':786,'published_minutes':682,'unsupported_rows':unsupported,
 'express_pattern':pattern,'express_url':express['source_url'],'normal_url':facts['source_url'],
 'mechanism':'원래 종류/정차 정보가 통합·축소 자료에서 비어 있고 적재기는 모든 dep_time을 승차 후보로 읽음. 공표 일반열차 정차 시각 집합과 전체 대조하는 방법으로 해결.',
 'research':[{'url':'https://gtfs.org/documentation/schedule/reference/#stop_timestxt','checked_at':NOW.isoformat(),
   'application':'stop_times의 pickup_type/drop_off_type은 승하차 가능 여부이며 시간 필드만으로 승차를 보장하지 않는다. timepoint는 보간/예정 시각을 구분한다. TAGO/AREX가 GTFS라는 주장이 아님.'},
   {'url':'https://www.kasa.go.kr/prog/bbsArticle/BBSMSTR_000000000010/view.do?bbsId=B000000000010&nttId=B000000001860Pe2zT3','application':'2026-10-09 한글날 휴일. 현재 휴일 달력은 이미 맞으며 수정 안 함.'}],
 'source_trace':'설정된 raw 경로 data/travel/raw/mobility와 datasets/mobility 전수 파일명 검색에서는 원 TAGO 시간표를 확보하지 못함. 다른 저장 기기의 원자료는 이번 검색 범위 밖.',
 'limits':'104행을 직통열차 통과 시각으로 보는 것은 전체 시각 패턴에 근거한 추론. 시각 블랙리스트나 이 추론을 필터 조건으로 쓰지 않고 공식 일반열차 전체 시각을 대조함. 공식 시각도 실제 도착 오차 측정이 아님.',
 'browser_schedule_rendered':False,'map_developer_api_calls':0,'actual_eta_error_samples':0,'actual_boardings':0})
backups=[]
for p in (DEBUG,WIKI,DATA):
 dest=p.parent/'_backup'/TAG/p.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest);assert sha(p)==sha(dest)
 backups.append({'source':rel(p),'backup':rel(dest),'sha256':sha(p)})
save(EV/'publication-backups-v1.json',backups)
debug_text=DEBUG.read_text(encoding='utf8').replace('## 미해결','## 해결됨 (2026-10-09, 부분) — 홍대입구4그룹',1)
debug_text=debug_text.replace('\n\n홍대입구','\n\n공식682분과 원자료의1대1 대조를 적재 경로에 연결했습니다. 신규26/26·관련467/467·실제 자료 통제 ABBA16/16, 원자료 무변경 및 다른1,746그룹 유지로 확인했습니다. 공덕 등 다른 역의 공표 대조와 실제 ETA오차는 남았습니다. 상세 보고서: '+link(DEBUG,REPORT)+'\n\n홍대입구',1)
DEBUG.write_text(debug_text,encoding='utf8')
body=f'''# 공항철도 공표 승차 시간 복구 검증

홍대입구에서 탈 수 없는 출발을 안내하던 시간표 대체 계산을 수정했습니다. 공식 일반열차 전체 표와 대조해 104행을 승차 후보에서 제외했고 원자료는 보존했습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 평일·휴일 양방향 공표 표 확보 | 완료 | 4/4 = 100% |
| 공표 분과 원자료1대1 대조 | 통과 | 682/682 = 100% |
| 수정 전후 통제 교대 재생 | 통과 | 16/16 = 100% |
| 신규 시험 | 통과 | 26/26 = 100% |
| 관련 시험 | 통과 | 467/467 = 100% |

생성시각 {NOW.isoformat()}. v11 §5 이동·§6-B 출발 안내의 시간표 대체 계산 수정입니다. 범위는 공항철도 홍대입구 한 역의 평일·휴일 양방향입니다. 682는 공표 출발 분 수이며 실제 운행 관측·독립 정확도 표본 수가 아닙니다. 전체21개 기능은 조건부3·개선9·추가검증9이며 완료율이 아닙니다.

## 문제와 원인

실제 런타임은 gzip 시간표453,668행을 읽습니다. 평문472,541행과 행수가 다른 것은 기존 출발 없음 제거 판이며 이번에 두 파일 모두 수정하지 않았습니다. 홍대입구는786출발행 중 공식 표682분에 대응하고104행은 표 밖입니다. 평일U183·D182, 휴일U159·D158분이며 각 그룹마다26행이 더 들어 있었습니다. 공식 분 누락0·공식 분 중복0입니다.

종류/정차 정보는 통합 단계에서 express/train_no가 비고 줄인 판에서 사라집니다. 적재기는 모든 출발 시각을 승차 가능한 열차로 읽었습니다. 따라서 실시간 선택 실패 때 대체 시간표가 고객의 출발·환승을 앞당길 수 있었습니다.

공식 직통열차26편×양방향×평일/휴일 표와 정렬 대조한104시각은 서울역 도착−340초(U), 서울역 출발+340초(D)와 모두 일치합니다. 중간역 통과 시각이 섞였다는 강한 추론이지만 운행ID가 없어 개별 열차 종류를 확정하지 않습니다. 수정은 이 추론이나 특정104시각을 코드에 넣지 않고 [공식 일반열차 전체 표]({facts['source_url']})로 판정합니다. [공식 직통열차 표]({express['source_url']}) 및 [GTFS 승하차·시간 정의](https://gtfs.org/documentation/schedule/reference/#stop_timestxt)를 참고했고 우리 원자료가 GTFS라는 가정은 하지 않았습니다.

## 무엇을 바꿨는가

별도 공표 자료가 원시간표 파일 SHA256, 정확한 노선/역/요일/방향, 전체 분 목록, 조회시각/출처를 가집니다. 모든 공표 분이 원자료와1대1 대응할 때만 그 집합의 출발을 읽습니다. 공식 분 누락·중복·원시간표 판 변경·형식 오류는 적재 실패입니다. 초·행선지·열차 종류를 보정하거나 새 열차를 만들지 않습니다. 원자료·수집일·기존 신선도 계산은 유지합니다.

대조 자료 생성/교체/같은 크기·수정시각의 내용 교체를 런타임 재구성과 저장 출발 안내의 입력 판에 연결했습니다. 사용 중 자료 삭제는 알려진 오류의 무대조 계산으로 돌아가지 않고 실패하며, 기동 명세에 등록된 자료 누락도 실패합니다. 원래 자료를 등록하지 않은 환경은 종전 계산을 유지합니다. 명세에 새 공표 파일과 해시/크기를 등록했습니다.

변경: [공표 대조]({link(REPORT,CS/'app/domains/travel_ops/instances/mobility/engine/published_boarding.py')}) · [적재/선택 근거]({link(REPORT,CS/'app/domains/travel_ops/instances/mobility/engine/verify_time.py')}) · [런타임]({link(REPORT,CS/'app/domains/travel_ops/instances/mobility/engine/runtime.py')}) · [자료 명세 검사]({link(REPORT,CS/'app/domains/travel_ops/instances/mobility/engine/datacheck.py')}) · [신규 시험]({link(REPORT,CS/'tests/unit/travel/mobility/test_published_boarding_v1.py')}) · [공표 자료]({link(REPORT,BASE/'published_boarding_timetable_v1.json')}). 기존 산출물을 덮기 전 [초기 백업]({link(REPORT,EV/'backup-manifest-v1.json')})·[보완 백업]({link(REPORT,EV/'backup-additions-v1.json')})·[문서 갱신 전 백업]({link(REPORT,EV/'publication-backups-v1.json')})을 남겼습니다.

## 재현 결과

| 홍대입구 준비 조건 | 수정 전 출발 | 수정 후 출발 | 공표 다음 출발 |
|---|---|---|---|
| 평일13:29·공덕방향 | 13:30 | 13:33 | 13:33 |
| 휴일13:29·공덕방향 | 13:30 | 13:33 | 13:33 |
| 평일13:35·공항방향 | 13:35 | 13:39 | 13:39 |
| 휴일13:35·공항방향 | 13:35 | 13:42 | 13:42 |

조건을 고정해 각4조건에 A·B·B·A 순서로 재생했습니다(원자료 모델A·공표 대조 모델B). 총16회·4개 통제 조건이며 실제 ETA오차나 독립16경로가 아닙니다. 대조 범위 밖1,746개(노선·역·요일) 그룹의 전체 출발분/방향/종착/추정 여부/급행 정보는 동일합니다. 홍대입구2개 요일 그룹만 바뀌었습니다. 실제자료 해시/명세 검사도 통과했습니다.

[실행 명령·로그]({link(REPORT,EV/'related-v1-run.json')}) · [467시험 원문]({link(REPORT,EV/'related-v1.log')}) · [시험 XML]({link(REPORT,EV/'related-v1.xml')}) · [16회 결과]({link(REPORT,EV/'product-replay-v1.json')}) · [원자료 판정]({link(REPORT,EV/'source-assessment-v1.json')}). 165개 전체층 시험은 선택 제외했고 통과로 세지 않았습니다. 기존 정규식 SyntaxWarning1건과 시험 종료 뒤 pyreadline3 소멸자의 WinError는 원문에 보존했고 시험 프로세스 종료코드는0입니다. Ruff5파일 통과.

mock 서버 시험(화면 반응): 이번에는 실행 안 했습니다.
실서버 확인(서버 응답): 새 서울시/지도 API 조회0회. 공식 웹 시간표는 공개 읽기 도구로 확인했고 cs 프로젝트 서버 HTTP·배달·배포는 확인하지 않았습니다.

## 남은 일

공덕 등 나머지 역에서도 직통/일반·정차 여부를 공식 원문으로 대조해야 합니다. 중간역 공표 조회가 실패한1URL을 전체 자료 부재로 단정하지 않습니다. TAGO 원자료는 설정 raw 경로와 datasets/mobility 파일명 전수검색 범위에서 확보하지 못했고 다른 저장 기기는 검색하지 않았습니다. 원래 운행ID/승하차 가능 정보를 보존하는 수집 계약을 보강해야 같은 시각에 서로 다른 열차가 지나가는 경우까지 해결할 수 있습니다.

실시간 도착 대체 웹의 운행ID/생성시각/역 귀속, 실제 도착·탑승 검증, 1.2km안 좌표·경로·시각이 맞는 새 웹 표본, 혼합 운임/누락 경로의 전체 검증은 남습니다. 이번682분은 공표 예정값입니다. 실탑승·실제 도착오차·결제0개이며 전체21완료를 선언하지 않습니다. 커밋·푸시·배포는 하지 않았습니다. [시각화v47]({link(REPORT,ASSETS/'mobility-readiness.html')})에21개 판단과 이번 수정을 함께 보존했습니다. 시각화 브라우저 렌더링은 미확인입니다.
'''
with REPORT.open('x',encoding='utf8') as f:f.write(body)
with WIKI.open('a',encoding='utf8') as f:f.write(f'\n\n## {TAG} 공표 승차 시간 복구 결과\n\n홍대입구786행 중 공식 일반열차682분을1대1 대조해 공표 밖104행만 적재 제외·원자료 보존.4조건 ABBA16/16에서 U13:30→13:33·D평일13:35→13:39/휴일→13:42, 다른1,746그룹 동일. 신규26/26·관련467/467(전체층165선택제외)·Ruff5파일·실제자료명세통과. 원시간표 해시/공표누락·중복/자료교체·삭제·저장안내입력판 검사 연결. 직통표26편 시각±340초와104행 일치는 통과시각 혼입 추론이며 개별운행ID미확정. 다른 역/실제ETA오차/실탑승/공항철도실시간대체자동연결은 남음·21분류3/9/9유지·배포안함. [보고서]({link(WIKI,REPORT)})·[시각화v47]({link(WIKI,ASSETS/"mobility-readiness.html")})·[검증]({link(WIKI,EV)}/).\n')
with DATA.open('a',encoding='utf8') as f:f.write(f'\n\n## {TAG} 공항철도 공표 승차 분 대조\n\n[새 사실값]({link(DATA,RAW)}/)은 AREX 홍대입구 일반열차 평일/휴일 양방향4그룹682분과 직통열차52행(평일26·휴일26)의 공개 웹 표 숫자입니다. 전체 HTML/사진/소개글 비저장·실제 도착/탑승 자료 아님. [공표 대조 파일]({link(DATA,BASE/"published_boarding_timetable_v1.json")})을 gzip 원시간표SHA256에 묶어 적재하고 공식분 누락/중복은 실패·공식 밖104행은 승차 후보에서 제외합니다. 원시간표gzip/평문/원메타는 변경하지 않았고 새파일만 판명세에 등록했습니다. 실제자료 통제16회·다른1,746그룹동일·신규26/26·관련467/467.104행은직통표시각±340초와일치하나운행ID미확정으로종류단정안함. 운영 배포/실제ETA오차0·지도개발자API0. [보고서]({link(DATA,REPORT)})와백업/검증을잇습니다.\n')
previous=CS/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v46/readiness-catalog.json'
catalog=json.loads(previous.read_text(encoding='utf8'));catalog.update(created_at=NOW.isoformat(),scope='홍대입구 공표 승차 시간 대조·원자료 보존',prior_catalog_sha256=sha(previous))
feature=next(x for x in catalog['features'] if x['name']=='지하철 경로 산출')
feature['current_update_v47']='홍대입구 공표682분 대조·공표밖104행 적재 제외.4조건 ABBA16/16·신규26/26·관련467/467·다른1,746그룹 유지. 원자료·신선도 유지. 공덕 등 다른역/실제ETA오차/실탑승 검증 남음. 기존94/96웹 지표는 이번 전량 재측정이 아님.'
assert Counter(x['status'] for x in catalog['features'])=={'조건부 사용':3,'개선 필요':9,'추가 검증':9}
save(ASSETS/'readiness-catalog.json',catalog)
style="""*{box-sizing:border-box}body{margin:0;background:#f5f7fa;color:#193a56;font-family:'Malgun Gothic',sans-serif;line-height:1.65}main{max-width:1140px;margin:auto;padding:40px 24px}h1{font-size:32px;line-height:1.3}.lead{font-size:20px}article,.notice{padding:20px;background:white;border:1px solid #d7e0e8;border-radius:8px}.notice{border-left:5px solid #a05a00}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:20px 0}a,summary{color:#126b67}select{font:inherit;padding:10px;max-width:100%}label{display:block}summary{cursor:pointer}[hidden]{display:none!important}table{border-collapse:collapse;width:100%;margin:20px 0}th,td{padding:10px;text-align:left;border-bottom:1px solid #d7e0e8}svg{width:100%;height:auto}.scroll{overflow:auto}@media(max-width:650px){.grid{grid-template-columns:1fr}main{padding:24px 16px}h1{font-size:26px}}"""
cards=''.join(f'<article data-status="{escape(x["status"])}"><h3>{escape(x["name"])}</h3><p>{escape(x["status"])} · {escape(x["scope"])}</p><p>{escape(x["metric"])}</p><p>{escape(x.get("current_update_v47",""))}</p><details><summary>근거와 남은 검증</summary><p>{escape(x["reason"])}</p><p>{escape(x["need"])}</p></details></article>' for x in catalog['features'])
js="document.getElementById('filter').addEventListener('change',function(){document.querySelectorAll('article[data-status]').forEach(card=>{card.hidden=this.value!=='전체'&&card.dataset.status!==this.value;});});"
rows=''.join(f'<tr><td>{day} · {direction}</td><td>{n}</td><td>26</td><td>{n+26}</td></tr>' for day,direction,n in [('평일','서울역방면',183),('평일','공항방면',182),('휴일','서울역방면',159),('휴일','공항방면',158)])
page=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 v47 — 공표 승차 시간 복구</title><style>{style}</style><main><p>triPilot / 서울 이동 / v47 / {NOW.isoformat()}</p><h1>탈 수 없는 출발을 고르던 계산을 수정했습니다</h1><p class="lead">홍대입구 공식 시간표 전체와 대조해682개 출발 분만 승차 후보로 읽습니다. 원자료104행은 보존하고 적재에서 제외합니다.</p><div class="notice">수정 범위는 홍대입구 한 역입니다. 예정 시간표 계산이며 실제 도착 오차·실탑승 검증이나 전체21개 기능 완료가 아닙니다.</div><svg viewBox="0 0 840 170" role="img" aria-label="원자료786행을 공식682분과 대조하여 승차 후보682개로 제한하는 흐름"><g font-size="18" fill="#193a56"><rect x="10" y="20" width="240" height="125" fill="#eef3f8"/><text x="25" y="55">저장 출발786행</text><text x="25" y="90">모든 출발을 후보로 읽음</text><text x="25" y="125">휴일13:30 선택</text><text x="265" y="90">→</text><rect x="300" y="20" width="240" height="125" fill="#eaf4f1"/><text x="315" y="55">공식 표682분 대조</text><text x="315" y="90">4그룹 · 모두1대1 대응</text><text x="315" y="125">원자료 판도 확인</text><text x="555" y="90">→</text><rect x="590" y="20" width="240" height="125" fill="#fff1da"/><text x="605" y="55">승차 후보682개</text><text x="605" y="90">공표 밖104행 제외</text><text x="605" y="125">휴일13:33 선택</text></g></svg><div class="scroll"><table><thead><tr><th>공표 범위</th><th>공표 대조 분</th><th>적재 제외 행</th><th>기존 행</th></tr></thead><tbody>{rows}</tbody></table></div><p>신규26/26·관련467/467·ABBA16/16. 다른1,746그룹 동일. 공표104행은 직통표 시각±340초와 일치하지만 개별 열차ID가 없어 종류를 확정하지 않았습니다.</p><h2>21개 기능의 현재 분류</h2><p>조건부3/21 · 개선9/21 · 추가검증9/21. 분류 비중이며 완료율이 아닙니다. 과거 비교 수치는 원래 표본의 기록입니다.</p><label for="filter">판정별 보기</label><select id="filter"><option>전체</option><option>조건부 사용</option><option>개선 필요</option><option>추가 검증</option></select><div class="grid">{cards}</div><p><a href="{link(ASSETS/'mobility-readiness.html',REPORT)}">보고서 읽기</a> · <a href="{link(ASSETS/'mobility-readiness.html',EV/'product-replay-v1.json')}">수정 전후16회 결과</a> · <a href="readiness-catalog.json">21개 근거</a> · <a href="{link(ASSETS/'mobility-readiness.html',EV/'backup-manifest-v1.json')}">백업</a></p><p>mock 서버 화면 시험·cs 프로젝트 서버 HTTP·배달·배포는 이번에 확인하지 않았습니다. 이 시각화의 브라우저 렌더링은 미확인입니다.</p></main><script>{js}</script></html>'''
with (ASSETS/'mobility-readiness.html').open('x',encoding='utf8') as f:f.write(page)
with (EV/'visual-script-v1.js').open('x',encoding='utf8') as f:f.write(js)
node=subprocess.run([shutil.which('node'),'--check',str(EV/'visual-script-v1.js')],capture_output=True,text=True);assert node.returncode==0
assert page.count('<article data-status=')==21
for dest in re.findall('href="([^"]+)"',page):assert (ASSETS/dest).resolve().exists(),dest
for dest in re.findall(r'\]\(([^)]+)\)',body):
 if not dest.startswith('http'):assert (REPORT.parent/dest).resolve().exists(),dest
save(EV/'visual-validation-v1.json',{'script_syntax_ok':True,'cards':21,'local_links_exist':True,'browser_rendered':False})
for name in ('prepare_published_boarding_v1.py','backup_published_boarding_followup_v1.py','build_published_boarding_data_v1.py','verify_published_boarding_v1.py','replay_published_boarding_v1.py',Path(__file__).name):shutil.copy2(Path(__file__).parent/name,EV/name)
initial=json.loads((EV/'backup-manifest-v1.json').read_text(encoding='utf8'))['backups']
for item in initial:
 p=ROOT/item['source']
 if p.suffix=='.py':
  diff=''.join(difflib.unified_diff((ROOT/item['backup']).read_text(encoding='utf8').splitlines(True),p.read_text(encoding='utf8').splitlines(True),fromfile=item['backup'],tofile=item['source']))
  with (EV/(p.stem+'-diff-v1.patch')).open('x',encoding='utf8') as f:f.write(diff)
sourcehashes={p:sha(ROOT/p) for p in prior['source_test_data_hashes']}
for p in [CS/'app/domains/travel_ops/instances/mobility/engine/published_boarding.py',CS/'app/domains/travel_ops/instances/mobility/engine/datacheck.py',CS/'tests/unit/travel/mobility/test_published_boarding_v1.py',BASE/'published_boarding_timetable_v1.json',BASE/'MANIFEST_git_v1.json',BASE/'timetable_v1.jsonl',*RAW.iterdir()]:
 if p.is_file():sourcehashes[rel(p)]=sha(p)
all_backups=initial+json.loads((EV/'backup-additions-v1.json').read_text(encoding='utf8'))+backups
assert all(sha(ROOT/b['backup'])==b['sha256'] for b in all_backups)
files=[p for d in (EV,ASSETS) for p in d.iterdir() if p.is_file()]+[REPORT,DEBUG,WIKI,DATA]
save(EV/'final-integrity-v1.json',{'created_at':NOW.isoformat(),'source_test_data_hashes':sourcehashes,'artifact_hashes':{rel(p):sha(p) for p in files},'backups':all_backups,'prior_artifacts_preserved':prior_artifacts,'full_feature_completion':False,'report':rel(REPORT),'assets':rel(ASSETS),'evidence':rel(EV)})
print(json.dumps({'report':rel(REPORT),'assets':rel(ASSETS),'source_hashes':len(sourcehashes),'artifact_hashes':len(files),'backups':len(all_backups)},ensure_ascii=False))
