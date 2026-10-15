from pathlib import Path
from datetime import datetime
from collections import Counter
from html import escape as e
import hashlib,json,shutil,os,re,sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2];CS=ROOT/'final_project_cs';NOW=datetime.now().astimezone();sys.stdout.reconfigure(encoding='utf8')
state=json.loads((Path(__file__).parent/'dmc-published-state-v1.json').read_text(encoding='utf8'));EV=ROOT/state['evidence'];DEBUG=ROOT/state['debug'];RAW=ROOT/state['raw']
def rel(p):return p.relative_to(ROOT).as_posix()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
 with p.open('x',encoding='utf8') as f:json.dump(v,f,ensure_ascii=False,indent=2)
def link(p,q):return os.path.relpath(q,p.parent).replace('\\','/')
suite=ET.parse(EV/'related-v1.xml').getroot();tests=sum(int(s.attrib['tests']) for s in suite.iter('testsuite'))
assert tests==97 and all(int(s.attrib.get('failures',0))+int(s.attrib.get('errors',0))==0 for s in suite.iter('testsuite'))
assert json.loads((EV/'related-v1-run.json').read_text(encoding='utf8'))['exit_code']==0
replay=json.loads((EV/'product-replay-v1.json').read_text(encoding='utf8'));assert len(replay['replays'])==16
baseline=json.loads((EV/'baseline-v1.json').read_text(encoding='utf8'))['hashes']
owned={'datasets/mobility/processed/mobility/published_boarding_timetable_v1.json','datasets/mobility/processed/mobility/MANIFEST_git_v1.json','datasets/mobility/REPORT.md','final_project_cs/wiki/teams/mobility.md'}
preserved={p:sha(ROOT/p)==h for p,h in baseline.items() if p not in owned};assert all(preserved.values())
save(EV/'prior-preservation-v1.json',{'checked':len(preserved),'matched':sum(preserved.values()),'intentionally_updated':sorted(owned)})
initial=json.loads((EV/'backup-manifest-v1.json').read_text(encoding='utf8'));backups=[]
for p in [DEBUG,CS/'wiki/teams/mobility.md',ROOT/'datasets/mobility/REPORT.md']:
 b=p.parent/'_backup'/NOW.strftime('%Y-%m-%d_%H%M%S_DMC결과기록')/p.name;b.parent.mkdir(parents=True);shutil.copy2(p,b);backups.append({'path':rel(p),'backup':rel(b),'sha256':sha(p)})
save(EV/'publication-backups-v1.json',backups)
REPORT=CS/'wiki/records/reports'/(NOW.strftime('%Y-%m-%d_%H%M')+'_디지털미디어시티_공식승차시간_확대검증.md')
ASSETS=CS/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v49';ASSETS.mkdir()
catalogpath=CS/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v48/readiness-catalog.json'
catalog=json.loads(catalogpath.read_text(encoding='utf8'));catalog['created_at']=NOW.isoformat();catalog['scope']='디지털미디어시티 공식 승차시간 대조 확대·21개 기존 판단 보존';catalog['prior_catalog_sha256']=sha(catalogpath)
update='디지털미디어시티 공식4그룹682분 추가 대조·공표 밖104행 승차 후보 제외. 홍대입구와 합계8그룹1364분·제외208행. 원자료 보존·실제 ETA/탑승 검증 아님. 통제 시각 교대16회·관련97건 통과.'
for feature in catalog['features']:
 if feature['name'] in ('지하철 경로 산출','첫차·막차·출발 역산'):
  feature['current_update_v49']=update
assert Counter(f['status'] for f in catalog['features'])==Counter({'조건부 사용':3,'개선 필요':9,'추가 검증':9})
save(ASSETS/'readiness-catalog.json',catalog)
save(EV/'source-assessment-v1.json',{'checked_at':NOW.isoformat(),'official_schedule_url':'https://www.airportrailroad.com/train/normal/info/040/0','facts':rel(RAW/'official-minute-facts-v1.json'),'acquired_groups':4,'expected_groups':4,'search_recovery':'공덕 검색 결과에 표시된 DMC 공식 결과 참조를 열어 전체334줄을 읽음. 직접 URL 열기는 오류였음. 5~24시 모든 시간 행과 평일/휴일 양방향을 구분함.','gtfs_reference':'https://gtfs.org/documentation/schedule/reference/#stop_timestxt','research_application':'GTFS는 출발시각과 승차 허용(pickup_type)을 구분한다. TAGO가 GTFS라는 뜻이 아니며, 종류/정차 식별 없는 보유 행을 전부 승차 가능으로 간주하지 않는 전제만 참고. 이번 별도 논문 알고리즘 적용 없음.','raw_source_search':{'exact_names':['tago_timetable.jsonl','tago_timetable_done.json','tago_station_ids.json','tago_empty_confirmed.json'],'scope':'workspace rg --files --no-ignore, _backup 및 .git 제외','matches':0,'DATA_DIR_set':False,'fallback_exists':False,'documented_old_raw_exists':False,'documented_old_backup_exists':False,'limits':'다른 기계·클라우드·제외한 백업 전체의 부재를 뜻하지 않음. 현재 DATA_DIR 미설정 환경에서 전체수집을 실행하지 않음.'},'actual_tago_api_calls':0,'map_developer_api_calls':0,'new_aligned_map_routes':0,'actual_boarding_payment_samples':0})
body=f'''# 디지털미디어시티의 공식 일반열차 시각을 승차 후보에 연결했습니다

공식 표에 없는 출발을 고르던 범위를 한 역 더 수정했습니다. 서울방향은13:27→13:29, 공항방향은13:38→13:39로 바뀌었습니다. 보유 자료와 공표 예정값의 통제 재생 결과입니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 새 공식 시각 대조 | 일치 | 682/682 = 100% |
| 변경 전후 교대 재생 | 통과 | 16/16 = 100% |
| 다른 시간표 그룹 보존 | 일치 | 1,746/1,746 = 100% |
| 관련 회귀 검사 | 통과 | {tests}/{tests} = 100% |

## 문제와 해결 범위

디지털미디어시티 저장 시간표786행 중 공식 일반열차 표 밖104행이 승차 후보로 남아 있었습니다. 이번 [AREX 공식 표](https://www.airportrailroad.com/train/normal/info/040/0)는 평일·휴일, 서울·공항 양방향의5~24시 전체4그룹입니다. 공식 분 누락/중복은 각각0건이며682분이 원자료와 정확히1대1 대응했습니다. [숫자 사실값]({link(REPORT,RAW/'official-minute-facts-v1.json')})·[사전 대조와104행]({link(REPORT,EV/'before-data-audit-v1.json')}).

승차 대조 자료에 이4그룹만 추가했습니다. 기존 홍대입구4그룹은 내용이 같고 원시간표453,668행·수집일·해시는 보존했습니다. 합계8그룹의 공식1364분이 대응하고208행을 적재 후보에서 제외합니다. 제외 행의 열차종류/통과 여부를 개별 운행ID로 확인한 것은 아닙니다. 임의 시간 보정이나 새 열차 생성 없이 확보한 집합만 사용합니다. 자료 변경은 기존 런타임 입력 판과 출발 안내 재검증 근거에 반영됩니다.

## 검증과 한계

평일·휴일×양방향4조건을 A·B·B·A 순으로16회 재생했습니다. 준비시각은 서울13:26/공항13:37, 목적지는 홍대입구/마곡나루로 고정했습니다. 기존13:27/13:38 대신 공식13:29/13:39를 선택합니다. 대조 범위 밖1,746그룹의 출발분·방향·종착·추정표시·열차번호·급행표시는 동일합니다. [제품 계산 원문]({link(REPORT,EV/'product-replay-v1.json')}). 반복은 결정적 개발 재생이며 독립 새 표본이나 실제 정확도 향상률이 아닙니다.

관련97/97 통과·전체층165건 선택 제외. [명령]({link(REPORT,EV/'related-v1-run.json')})·[로그]({link(REPORT,EV/'related-v1.log')}). 새 코드/시험을 작성하지 않은 자료 확대입니다. 실제자료 명세 해시 검사도 통과했습니다. 기존9건의 문서 상태 표기 결함은 이번 별도로 재검사/수정하지 않았습니다.

mock 서버 시험(화면 반응): 안 했음, 0건.

실서버 확인(서버 응답): cs 프로젝트 서버 HTTP 확인 안 했음. 이번 TAGO·지도 개발자 API 호출0회, 실제 ETA 오차·탑승·결제 표본0건.

[GTFS 공식 명세](https://gtfs.org/documentation/schedule/reference/#stop_timestxt)는 시각과 승차 허용을 별도 필드로 구분합니다. 보유 TAGO 행을 GTFS로 단정하지 않고, 시각만으로 승차 가능을 확정하지 않는 전제에 참고했습니다. 새로운 논문 알고리즘은 이번 적용하지 않았습니다. 공식 웹 직접 열기는 실패했지만 검색 결과 참조를 열어 완전 표를 확보했습니다.

## 보존과 다음 작업

시작 해시326/326 일치, 허용 변경4파일을 뺀 이전 파일{len(preserved)}/{len(preserved)} 동일. [보존 검사]({link(REPORT,EV/'prior-preservation-v1.json')})·[변경 전 백업]({link(REPORT,EV/'backup-manifest-v1.json')})·[기록 전 백업]({link(REPORT,EV/'publication-backups-v1.json')}).

전체21개 판단은 조건부3·개선9·추가검증9로 유지하며 완료율이 아닙니다. [시각화v49]({link(REPORT,ASSETS/'mobility-readiness.html')})·[21개 판단 근거]({link(REPORT,ASSETS/'readiness-catalog.json')}). 브라우저 렌더링은 미확인입니다. 커밋·푸시·배포·외부 메시지는 하지 않았습니다.

다음은 공덕과 나머지 역의 완전 표, 원자료의 열차번호/정차 식별, 실제 실시간 대체 정보 연결입니다. 기존 TAGO 원자료 이름4종은 작업 폴더 검색(백업·git 제외)0건, 문서의 옛 원자료/백업 위치도 이 PC에서 확인되지 않았습니다. 다른 기계의 존재까지 부정하지 않습니다. [조회 범위]({link(REPORT,EV/'source-assessment-v1.json')}). 정책 안 도보 웹 대조와 혼합 운임 검증도 남아 전체 완료를 선언하지 않습니다.
'''
with REPORT.open('x',encoding='utf8') as f:f.write(body)
text=DEBUG.read_text(encoding='utf8').replace('## 미해결','## 해결됨 (2026-10-09, 부분) — 확보한 공식4그룹의 승차 후보')
text+=f'\n검증: 통제 교대16/16·관련97/97, 다른1,746그룹 보존. 원행 종류/정차 식별·다른 역·실제 ETA/탑승 검증은 미해결입니다. [보고서]({link(DEBUG,REPORT)})·[실행 원문]({link(DEBUG,EV/"product-replay-v1.json")}).\n';DEBUG.write_text(text,encoding='utf8')
wiki=CS/'wiki/teams/mobility.md'
with wiki.open('a',encoding='utf8') as f:f.write(f'\n\n## {NOW.strftime("%Y-%m-%d_%H%M")} 디지털미디어시티 공식 승차시간 확대 결과\n\n공식4그룹682분 추가1대1 대조·공표 밖104행 후보 제외·기존홍대4그룹 보존. 합계8그룹1364분/제외208행이며 원시간표와수집일유지. 통제시각4조건ABBA16/16에서U13:27→13:29/D13:38→13:39·다른1746그룹동일·관련97/97(165선택제외)·명세해시통과. 실제ETA/탑승/결제/새정렬웹경로0·지도개발자API0·21분류3/9/9유지·전체미완료. 공덕/다른역·개별정차식별·실시간대체자동연결남음. [보고서]({link(wiki,REPORT)})·[시각화v49]({link(wiki,ASSETS/"mobility-readiness.html")})·[검증]({link(wiki,EV)}/).\n')
p=ROOT/'datasets/mobility/REPORT.md'
with p.open('a',encoding='utf8') as f:f.write(f'\n\n## {NOW.strftime("%Y-%m-%d_%H%M")} 공항철도 공표 승차 대조 확대\n\n디지털미디어시티 공식 평일·휴일 양방향4그룹682분을 추가했습니다. 기존홍대입구와합계8그룹1364분/제외208행, 원시간표·수집일·기존그룹보존. 숫자원자료는 raw/{state["tag"]}/official-minute-facts-v1.json, 가공자료 published_boarding_timetable_v1.json과MANIFEST_git_v1.json의해시/크기만갱신. 통제교대16/16·관련97/97·실자료명세통과이며실제ETA/탑승검증아님. [보고서]({link(p,REPORT)}).\n')
cards=''.join(f'<article><h3>{e(f["name"])}</h3><p><b>{e(f["status"])}</b> · {e(f["scope"])}</p><p>{e(f["metric"])}</p><details><summary>근거와 남은 부분</summary><p>{e(f["reason"])}</p><p>{e(f["need"])}</p><p>{e(f.get("current_update_v49",f.get("current_update_v48",f.get("current_update_v47",""))))}</p></details></article>' for f in catalog['features'])
svg='''<svg viewBox="0 0 960 272" role="img" aria-labelledby="dmc-title dmc-desc"><title id="dmc-title">디지털미디어시티 승차 후보의 변경 전후</title><desc id="dmc-desc">준비 시각을 고정한 재생에서 서울 방향 출발은13시27분에서13시29분, 공항 방향은13시38분에서13시39분으로 바뀌었습니다.</desc><defs><marker id="dmc-arrow" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#193a56"/></marker></defs><g stroke="#193a56" stroke-width="2" fill="none" marker-end="url(#dmc-arrow)"><path d="M300 72 H370"/><path d="M610 72 H680"/><path d="M300 184 H370"/><path d="M610 184 H680"/></g><g fill="white" stroke="#193a56"><rect x="30" y="30" width="270" height="84" rx="6"/><rect x="370" y="30" width="240" height="84" rx="6"/><rect x="680" y="30" width="240" height="84" rx="6"/><rect x="30" y="142" width="270" height="84" rx="6"/><rect x="370" y="142" width="240" height="84" rx="6"/><rect x="680" y="142" width="240" height="84" rx="6"/></g><g fill="#193a56" font-size="20" text-anchor="middle"><text x="165" y="65">서울 방향 · 준비13:26</text><text x="165" y="93">목적지 홍대입구</text><text x="490" y="80">기존13:27</text><text x="800" y="80">공식대조13:29</text><text x="165" y="177">공항 방향 · 준비13:37</text><text x="165" y="205">목적지 마곡나루</text><text x="490" y="192">기존13:38</text><text x="800" y="192">공식대조13:39</text></g><text x="30" y="260" fill="#193a56" font-size="16">평일·휴일×양방향4조건의 통제 재생이며 실제 운행 오차 측정이 아닙니다.</text></svg>'''
page=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 준비도 v49 — 공식 승차시간 확대</title><style>body{{margin:0;background:#f5f7fa;color:#193a56;font-family:system-ui,sans-serif;line-height:1.65}}main{{max-width:1120px;margin:auto;padding:24px}}h1{{font-size:32px;line-height:1.3}}h2{{margin-top:40px}}a,summary{{color:#126b67}}svg{{width:100%;height:auto}}.scroll{{overflow-x:auto}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:12px;border-bottom:1px solid #cdd6df}}.notice{{border-left:4px solid #a05a00;padding:16px;background:#fff1da}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:16px}}article{{padding:20px;background:white;border:1px solid #cdd6df;border-radius:8px;overflow-wrap:anywhere}}summary{{cursor:pointer}}</style><main><p>triPilot · {NOW.strftime('%Y-%m-%d %H:%M')} · v49</p><h1>공식 표에 없는 출발을 승차 후보에서 제외했습니다</h1><p>디지털미디어시티 공식4그룹을 추가했습니다. 기존 홍대입구와 합계8그룹만 적용하며 원시간표를 보존했습니다.</p><div class="scroll"><table><thead><tr><th>할 일</th><th>상태</th><th>진행</th></tr></thead><tbody><tr><td>새 공식 시각 대조</td><td>일치</td><td>682/682 = 100%</td></tr><tr><td>교대 재생</td><td>통과</td><td>16/16 = 100%</td></tr><tr><td>관련 검사</td><td>통과</td><td>97/97 = 100%</td></tr></tbody></table></div>{svg}<div class="notice">실제 ETA 오차·탑승·결제 표본0건. 다른 역의 완전 표와 정차 식별·실시간 대체 정보 연결은 남았습니다.</div><h2>21개 기능의 현재 판단</h2><p>조건부 사용3/21 · 개선 필요9/21 · 추가 검증9/21. 분류 비중이며 완료율이 아닙니다. 기존 비교 수치를 유지했습니다.</p><div class="grid">{cards}</div><p><a href="{link(ASSETS/'mobility-readiness.html',REPORT)}">이번 보고서</a> · <a href="{link(ASSETS/'mobility-readiness.html',EV/'product-replay-v1.json')}">계산 원문</a> · <a href="readiness-catalog.json">21개 근거</a> · <a href="{link(ASSETS/'mobility-readiness.html',EV/'backup-manifest-v1.json')}">변경 전 백업</a></p><p>브라우저 렌더링 미확인. mock 서버 화면 시험·cs 프로젝트 서버 HTTP 확인·배포는 하지 않았습니다.</p></main></html>'''
with (ASSETS/'mobility-readiness.html').open('x',encoding='utf8') as f:f.write(page)
assert page.count('<article>')==21 and '<script' not in page
for dest in re.findall('href="([^"]+)"',page):assert (ASSETS/dest).resolve().exists(),dest
for dest in re.findall(r'\]\(([^)]+)\)',body):
 if not dest.startswith('http'):assert (REPORT.parent/dest).resolve().exists(),dest
save(EV/'visual-validation-v1.json',{'cards':21,'local_links_exist':True,'accessible_svg_title_desc':True,'static_no_javascript':True,'browser_rendered':False})
for name in ('prepare_dmc_boarding_v1.py','apply_replay_dmc_boarding_v1.py','verify_dmc_boarding_v1.py',Path(__file__).name):shutil.copy2(Path(__file__).parent/name,EV/name)
prior=json.loads((ROOT/state['previous_integrity']).read_text(encoding='utf8'));sourcehashes={p:sha(ROOT/p) for p in prior['source_test_data_hashes']};sourcehashes[rel(RAW/'official-minute-facts-v1.json')]=sha(RAW/'official-minute-facts-v1.json')
allbackups=initial+backups;assert all(sha(ROOT[b['backup']])==b['sha256'] for b in allbackups)
files=[p for d in (EV,ASSETS) for p in d.iterdir() if p.is_file()]+[REPORT,DEBUG,wiki,ROOT/'datasets/mobility/REPORT.md']
save(EV/'final-integrity-v1.json',{'created_at':NOW.isoformat(),'source_test_data_hashes':sourcehashes,'artifact_hashes':{rel(p):sha(p) for p in files},'backups':allbackups,'full_feature_completion':False,'report':rel(REPORT),'assets':rel(ASSETS),'evidence':rel(EV)})
print(json.dumps({'report':rel(REPORT),'assets':rel(ASSETS),'tests':tests,'source_hashes':len(sourcehashes),'artifacts':len(files),'backups':len(allbackups)},ensure_ascii=False))
