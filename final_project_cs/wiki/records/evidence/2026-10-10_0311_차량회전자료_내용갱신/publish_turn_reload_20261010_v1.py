from pathlib import Path
from datetime import datetime
from collections import Counter
from html import escape
import hashlib,json,os,re,shutil,sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2];CS=ROOT/'final_project_cs';NOW=datetime.now().astimezone();sys.stdout.reconfigure(encoding='utf8')
state=json.loads((Path(__file__).parent/'turn-reload-state-20261010-v1.json').read_text(encoding='utf8'));EV=ROOT/state['evidence']
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):return p.relative_to(ROOT).as_posix()
def link(p,q):return os.path.relpath(q,p.parent).replace('\\','/')
def save(p,obj):
 with p.open('x',encoding='utf8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
baseline=read(EV/'baseline-v1.json');code=CS/'app/domains/travel_ops/instances/mobility/engine/turn_restrictions.py';WIKI=CS/'wiki/teams/mobility.md';DEBUG=CS/'wiki/records/reports/debugs'/(state['tag']+'.md')
allowed={rel(code),rel(WIKI)};preserved={p:sha(ROOT/p)==h for p,h in baseline['hashes'].items() if p not in allowed}
assert all(preserved.values()),[p for p,ok in preserved.items() if not ok]
root=ET.parse(EV/'after-v1.xml').getroot();suites=list(root.iter('testsuite'));tests=sum(int(s.attrib['tests']) for s in suites)
assert tests==41 and all(int(s.attrib.get('failures',0))+int(s.attrib.get('errors',0))+int(s.attrib.get('skipped',0))==0 for s in suites)
new_tests=[t for t in root.iter('testcase') if 'test_turn_policy_content_reload_v1' in t.attrib.get('classname','')];assert len(new_tests)==5
replay=read(EV/'real-data-replay-v1.json');assert replay['matched']==replay['total']==8
assert all(sha(ROOT/p)==h for p,h in replay['data_hashes'].items())
REPORT=CS/'wiki/records/reports'/(NOW.strftime('%Y-%m-%d_%H%M')+'_차량회전자료_내용교체_복구검증.md');ASSETS=CS/'wiki/records/reports/assets/2026-10-10_mobility_readiness_v51'
assert not REPORT.exists() and not ASSETS.exists();ASSETS.mkdir()
backups=[]
for p in (DEBUG,WIKI):
 h=sha(p);b=p.parent/'_backup'/NOW.strftime('%Y-%m-%d_%H%M%S_회전내용갱신_결과기록')/p.name;b.parent.mkdir(parents=True);shutil.copy2(p,b)
 assert sha(b)==h and sha(p)==h
 backups.append({'path':rel(p),'backup':rel(b),'sha256':h})
save(EV/'publication-backups-v1.json',backups)
save(EV/'preservation-v1.json',{'checked_at':NOW.isoformat(),'matched':sum(preserved.values()),'total':len(preserved),'allowed_changes':sorted(allowed),'prior_matched':baseline['previous_matched'],'prior_total':baseline['previous_total'],'other_changes_retained':baseline['previous_changed'],'data_hashes_matched':len(replay['data_hashes'])})
save(EV/'source-assessment-v1.json',{'official_sources':[
 {'url':'https://www.airportrailroad.com/train/normal/live','finding':'정적 본문은 열림. 열차별 운행ID·생성시각·목록 귀속 추가 확인 미완료.'},
 {'url':'https://gtfs.org/documentation/realtime/feed-entities/trip-updates/','finding':'운행 갱신 부재를 정시로 간주하지 않는 원칙 확인. AREX가 GTFS라는 뜻이 아님.'},
 {'url':'https://wiki.openstreetmap.org/wiki/Relation:restriction','finding':'from/via/to의 금지·강제 회전, 보행자 예외와 조건부 제약의 별도 범위 확인. 이번 정적 단순 2487관계의 의미는 바꾸지 않음.'},
 {'url':'https://docs.python.org/3/library/hashlib.html','finding':'입력 바이트의 SHA256 내용값을 비교함. 새 예측/탐색 논문 알고리즘을 적용하는 변경이 아님.'}],
 'blocked_research':[{'method':'CUA 초기화','result':'kernel assets 경로 오류로 초기화 실패'},{'method':'공개 HTML Python 조회(제한 API 아님)','result':'격리 환경 DNS 실패, 권한 검토 후 조회 SSL 서명 유형 오류. 인증서 검증을 끄지 않았음.'}],
 'limited_api_budget':{'reserve_rate':0.20,'usage_before':'미확인','usage_after':'미확인','remaining':'미확인','reset_at':'미확인','task_calls':0,'task_retries':0,'atomic_budget_reservations':0,'decision':'공유 누적 사용량/갱신 시간 확인 전 제한 API 호출하지 않음. 운영 한도/예약 주기/알림 정책 변경 없음.'},
 'actual_vehicle_boarding_payment_samples':0,'aligned_new_web_routes':0,'browser_rendered':False})
save(EV/'lint-v1.json',{'command':'python -m ruff check app/domains/travel_ops/instances/mobility/engine/turn_restrictions.py tests/unit/travel/mobility/test_turn_policy_content_reload_v1.py','cwd':'final_project_cs','exit_code':0,'output':'All checks passed!'})
catalogpath=CS/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v50/readiness-catalog.json';catalog=read(catalogpath)
catalog.update(created_at=NOW.isoformat(),scope='차량 회전자료 내용 교체 재검증·21개 기존 판단 유지',prior_catalog_sha256=sha(catalogpath))
for f in catalog['features']:
 if f['name'] in ('자동차 소요 시간','자동차 경로 거리'):
  f['current_update_v51']='회전 파일의 크기·수정시각이 같은 내용 교체를 놓치던 캐시 결함 수정. 신규5/5·관련41/41, 보유 도로자료2쌍 ABBA8/8 결과 유지. 정적 단순2487관계 적용 범위 유지·실차/독립웹 검증 아님.'
assert Counter(f['status'] for f in catalog['features'])==Counter({'조건부 사용':3,'개선 필요':9,'추가 검증':9}) and len(catalog['features'])==21
save(ASSETS/'readiness-catalog.json',catalog)
body=f'''# 차량 회전 제한 파일의 내용 교체를 놓치던 결함을 수정했습니다

차량 경로 계산이 갱신된 회전 제한을 다음 요청부터 다시 검사합니다. 파일 크기와 수정시각이 같아도 새 내용이면 반영하고, 손상되거나 도로자료와 맞지 않으면 오류를 냅니다. 내용이 같은 파일 교체는 기존 결과를 유지합니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 신규 결함 검사 | 통과 | 5/5건 = 100% |
| 관련 회귀 검사 | 통과 | {tests}/{tests}건 = 100% |
| 보유 서울 경로 교대 재생 | 일치 | 8/8회 = 100% |
| 다른 기존 파일 보존 | 일치 | {len(preserved)}/{len(preserved)}개 = 100% |

## 원인과 수정

기존 [회전자료 적재 코드]({link(REPORT,code)})는 크기·수정시각만 비교했습니다. 원자적 파일 교체 후 원래 시각을 보존한 개발 재현에서 정상 규칙 변경을 놓쳤고, 손상 JSON·다른 그래프 해시·잘못된 방향 관계도 옛 캐시로 통과시켰습니다. 수정 전 신규 5건 중 4실패·1통과였습니다. [수정 전 JUnit 원문]({link(REPORT,EV/'before-v1.xml')})·[재현 명령]({link(REPORT,EV/'before-v1-run.json')}).

이제 차량 요청마다 회전 파일의 바이트를 한 번 읽고 SHA256으로 내용을 비교합니다. 변경 시 비교했던 그 바이트를 파싱하고 기존 그래프 결합·회전 관계 검사를 거칩니다. 내용이 같으면 기존 테이블을 재사용합니다. 약 21만 바이트({replay['source_bytes_per_vehicle_request']:,}바이트)의 파일 읽기·해시 비용이 요청마다 추가되며 실제 요청 지연은 측정하지 않았습니다. 큰 도로 그래프는 같은 회전 내용에서 재해시하지 않습니다.

[Python 공식 hashlib 문서](https://docs.python.org/3/library/hashlib.html)의 바이트 입력 SHA256을 사용했습니다. [OSM 회전 관계 문서](https://wiki.openstreetmap.org/wiki/Relation:restriction)의 금지·강제 회전 의미와 보행자·조건부 범위는 유지합니다. 새 탐색·예측 논문 알고리즘이나 미지원 복합 제약을 추가한 변경은 아닙니다.

## 검증과 제품 경로

실제 차량 경로는 GraphRouter.route → 회전자료 load → 들어온 유향 간선을 구분하는 기존 탐색으로 이어집니다. CarService는 이 경로의 거리·시간·회전 적용 근거를 기존대로 소비합니다. 공개 고객 JSON이나 운영 정책 수치는 바꾸지 않았습니다.

신규 5/5와 기존 36/36을 합친 관련 41/41 통과입니다. 신규 5건은 정상 규칙 변경, 손상 JSON, 그래프 해시 불일치, 잘못된 방향 관계, 동일 내용 교체입니다. 기존 시험은 유향 회전 탐색과 별도 구현의 최단거리 대조, 부분 출발·도착, 도보·자전거 분리, 파일 삭제·손상 등을 포함합니다. [새 시험 코드]({link(REPORT,CS/'tests/unit/travel/mobility/test_turn_policy_content_reload_v1.py')})·[명령]({link(REPORT,EV/'after-v1-run.json')})·[로그]({link(REPORT,EV/'after-v1.log')}). Ruff는 변경 코드와 새 시험 2개 파일에서 통과했습니다.

보유 서울 도로자료의 좌표 2쌍을 고정하고 백업 코드 A·수정 코드 B·B·A로 8회 재생했습니다. 거리·시간·좌표열·간선·붙임 선택 근거를 포함한 응답 전체가 조건별로 같았습니다. 경로 거리는 각각 10,184.1m와 1,468.71m이며 적용 관계는 기존 2,487개입니다. 이 재생은 자료가 바뀌지 않은 경우의 결과 보존 검사이며 독립 웹 정확도나 실제 통행 검증이 아닙니다. [좌표·해시·재생 원문]({link(REPORT,EV/'real-data-replay-v1.json')}). 그래프 폴더의 기존 파일 {len(replay['data_hashes'])}/{len(replay['data_hashes'])}개 해시도 유지했습니다.

mock 서버 시험 0건 (화면 반응): 안 했음.

실서버 확인 (서버 응답): cs 프로젝트 서버 HTTP·실제 차량 통행·탑승·결제 확인 안 했음.

## 보존과 남은 작업

직전 완료본 해시 411개 중 403개는 같고, 다른 작업의 코드·설정 8개 변경을 이번 시작 기준으로 보존했습니다. 이번에는 회전자료 적재 코드 1개와 wiki를 수정하고 시험·기록을 새로 만들었습니다. 허용한 두 파일을 제외한 {len(preserved)}/{len(preserved)}개 시작 해시가 동일합니다. [보존 검사]({link(REPORT,EV/'preservation-v1.json')})·[코드 수정 전 백업]({link(REPORT,EV/'backup-manifest-v1.json')})·[결과 기록 전 백업]({link(REPORT,EV/'publication-backups-v1.json')})·[결함 상태]({link(REPORT,DEBUG)}).

실시간 대체 정보는 [AREX 공식 페이지](https://www.airportrailroad.com/train/normal/live)의 정적 본문을 열었지만 브라우저 초기화와 공개 HTML 추가 조회가 실패해 열차ID·생성시각·목록의 역 귀속을 추가 확인하지 못했습니다. [GTFS 공식 운행 갱신 문서](https://gtfs.org/documentation/realtime/feed-entities/trip-updates/)의 정보 부재를 정시로 추정하지 않는 원칙을 다시 확인했습니다. AREX가 GTFS라는 뜻은 아닙니다. 그래서 근거 없이 자동 대체 연결을 추가하지 않고 다음 우선순위의 재현된 회전 결함을 수정했습니다.

제한 있는 API 호출·재시도는 각각 0회입니다. 공급자 공유 누적 사용량·잔여량·갱신 시각은 미확인으로 두고 호출하지 않았습니다. 일일 예비율 20%·운영 서비스 한도·예약 주기·알림 정책은 유지했습니다. [출처·실패·예산 기록]({link(REPORT,EV/'source-assessment-v1.json')}).

전체 21개 기능 분류는 조건부 사용 3개·개선 필요 9개·추가 검증 9개이며 완료율이 아닙니다. [시각화 v51]({link(REPORT,ASSETS/'mobility-readiness.html')})·[기능별 기존 근거]({link(REPORT,ASSETS/'readiness-catalog.json')}). 브라우저 렌더링은 도구 오류로 미확인이고 HTML 구조·로컬 연결 대상은 검사했습니다.

회전 파일을 읽은 뒤 탐색 중 교체하는 경우, 도로 그래프 자체를 같은 크기·수정시각으로 바꾸는 경우, 복잡한 유턴·시간/차종 예외는 이번 해결 범위 밖입니다. 실시간 대체 소스의 식별·출발 연결, 1.2km 정책 안 새 웹 대조, 혼합 운임·누락 경로와 실운행 검증도 계속 남습니다. 커밋·푸시·배포·외부 메시지는 하지 않았습니다.
'''
with REPORT.open('x',encoding='utf8') as f:f.write(body)
assert sha(DEBUG)==backups[0]['sha256']
text=DEBUG.read_text(encoding='utf8').replace('## 미해결','## 해결됨 (2026-10-10) — 회전 파일의 내용 교체 검사').replace('../../../../../app/','../../../../app/')
text+=f'\n검증: 수정 전4실패·1통과 → 신규5/5·관련41/41통과, 보유자료교대8/8결과일치. [보고서]({link(DEBUG,REPORT)})·[로그]({link(DEBUG,EV/"after-v1.log")}). 도로 그래프 자체의 같은 메타데이터 변경·탐색 중 교체·실차 검증은 이번 해결 범위가 아닙니다.\n'
DEBUG.write_text(text,encoding='utf8')
assert sha(WIKI)==backups[1]['sha256']
with WIKI.open('a',encoding='utf8') as f:f.write(f'\n\n## {NOW.strftime("%Y-%m-%d_%H%M")} 차량 회전자료 내용 교체 복구 결과\n\n크기·수정시각이 같은 회전 파일 교체를 놓치던 캐시를 바이트1회읽기/SHA256비교로 수정했습니다. 수정전4실패·1통과→신규5/5·관련41/41·Ruff2파일, 보유서울2쌍ABBA8/8응답전체동일·기존그래프6파일보존·정적2487관계범위유지. 다른작업8변경보존·허용수정외409/409해시동일. 제한API0·실차/독립새웹0·21분류3/9/9유지·전체미완료. 공식웹정적본문은열렸지만CUA초기화/공개HTML추가조회실패로실시간목록의ID/시각/역귀속은미확인. [보고서]({link(WIKI,REPORT)})·[시각화v51]({link(WIKI,ASSETS/"mobility-readiness.html")})·[검증]({link(WIKI,EV)}/).\n')
cards=''.join(f'<article><h3>{escape(f["name"])}</h3><p><b>{escape(f["status"])}</b> · {escape(f["scope"])}</p><p>{escape(f["metric"])}</p><details><summary>근거와 남은 부분</summary><p>{escape(f["reason"])}</p><p>{escape(f["need"])}</p><p>{escape(f.get("current_update_v51",f.get("current_update_v50",f.get("current_update_v49",""))))}</p></details></article>' for f in catalog['features'])
page=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 준비도 v51 차량 회전자료 갱신</title><style>body{{margin:0;background:#f5f7fa;color:#193a56;font-family:system-ui,sans-serif;line-height:1.65}}main{{max-width:1120px;margin:auto;padding:24px}}h1{{font-size:30px;line-height:1.4}}h2{{margin-top:32px}}a,summary{{color:#126b67}}.scroll{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;background:white}}td,th{{text-align:left;padding:12px;border-bottom:1px solid #cdd6df}}.notice{{border-left:4px solid #a05a00;padding:16px;background:#fff1da}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:16px}}article{{padding:20px;background:white;border:1px solid #cdd6df;border-radius:8px;overflow-wrap:anywhere}}summary{{cursor:pointer}}a:focus-visible,summary:focus-visible{{outline:3px solid #126b67;outline-offset:3px}}</style><main><p>triPilot · {NOW.strftime('%Y-%m-%d %H:%M')} · v51</p><h1>회전 제한 파일의 새 내용을 다음 차량 요청에 반영합니다</h1><p>크기·수정시각이 같은 교체도 내용으로 검사합니다.</p><div class="scroll"><table><caption>5개 통제 조건의 변경 전후</caption><thead><tr><th scope="col">교체한 내용</th><th scope="col">이전</th><th scope="col">수정 후</th></tr></thead><tbody><tr><th scope="row">정상 회전 규칙 변경</th><td>옛 경로 유지</td><td>새 조건으로 계산</td></tr><tr><th scope="row">손상 JSON</th><td>옛 규칙 사용</td><td>명시적 오류</td></tr><tr><th scope="row">다른 그래프 해시</th><td>옛 규칙 사용</td><td>명시적 오류</td></tr><tr><th scope="row">잘못된 방향 관계</th><td>옛 규칙 사용</td><td>명시적 오류</td></tr><tr><th scope="row">동일 내용 교체</th><td>결과 유지</td><td>결과 유지</td></tr></tbody></table></div><p>신규 5/5 · 관련 41/41 통과. 보유 도로자료 2쌍의 교대 재생 8/8회 결과 일치.</p><p class="notice">개발 통제와 결과 보존 검사입니다. 실제 차량·새 독립 웹 검증은 0건이며 전체 완료가 아닙니다. 제한 API 호출도 0회입니다.</p><h2>21개 기능의 현재 판단</h2><p>조건부 사용 3개 · 개선 필요 9개 · 추가 검증 9개. 분류는 완료율이 아닙니다.</p><div class="grid">{cards}</div><p><a href="{link(ASSETS/'mobility-readiness.html',REPORT)}">이번 보고서</a> · <a href="{link(ASSETS/'mobility-readiness.html',EV/'after-v1.log')}">검증 로그</a> · <a href="readiness-catalog.json">21개 근거</a> · <a href="{link(ASSETS/'mobility-readiness.html',EV/'backup-manifest-v1.json')}">변경 전 백업</a></p><p>브라우저 렌더링 미확인. cs 프로젝트 서버 HTTP 확인·배포는 하지 않았습니다.</p></main></html>'''
with (ASSETS/'mobility-readiness.html').open('x',encoding='utf8') as f:f.write(page)
assert page.count('<article>')==21 and '<script' not in page
for target in re.findall('href="([^"]+)"',page):assert (ASSETS/target).resolve().exists(),target
for target in re.findall(r'\]\(([^)]+)\)',body):
 if not target.startswith('http'):assert (REPORT.parent/target).resolve().exists(),target
save(EV/'visual-validation-v1.json',{'cards':21,'local_links_exist':True,'table_headers_scoped':True,'static_no_javascript':True,'browser_rendered':False})
history=CS/'wiki/records/history'/(state['tag']+'.md')
with history.open('x',encoding='utf8') as f:f.write(f'## {NOW.strftime("%Y-%m-%d %H:%M")} — 車両回転資料の内容更新検査\n'.replace('車両回転資料の内容更新検査','차량 회전자료 내용 갱신 검사')+f'- 계획: [실행계획]({link(history,CS/"wiki/records/plans"/(state["tag"]+".md"))})\n- 담당: Codex\n- 수행: 회전자료 내용 해시 비교·같은 바이트 파싱, 기존 범위 유지\n- 검증: 신규5/5·관련41/41·보유자료교대8/8·Ruff2파일\n- 리포트: [검증 보고서]({link(history,REPORT)})\n')
for name in ('prepare_turn_reload_20261010_v1.py','contract_turn_reload_20261010_v1.py','verify_turn_reload_20261010_v1.py','replay_turn_reload_20261010_v1.py',Path(__file__).name):shutil.copy2(Path(__file__).parent/name,EV/name)
save(EV/'publication-state-v1.json',{'report':rel(REPORT),'assets':rel(ASSETS),'debug':rel(DEBUG),'history':rel(history),'plan':rel(CS/'wiki/records/plans'/(state['tag']+'.md')),'test_count':tests,'full_feature_completion':False})
print(json.dumps({'report':rel(REPORT),'assets':rel(ASSETS),'preserved':len(preserved),'tests':tests},ensure_ascii=False))
