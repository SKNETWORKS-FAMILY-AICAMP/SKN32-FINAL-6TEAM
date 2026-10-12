from pathlib import Path
from datetime import datetime
from collections import Counter
from html import escape
import hashlib,json,os,re,shutil,sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]; CS=ROOT/'final_project_cs';NOW=datetime.now().astimezone()
sys.stdout.reconfigure(encoding='utf8')
state=json.loads((Path(__file__).parent/'gimpo-published-state-v1.json').read_text(encoding='utf8'))
EV=ROOT/state['evidence'];RAW=ROOT/state['raw'];DEBUG=ROOT/state['debug'];WIKI=CS/'wiki/teams/mobility.md';DATAREPORT=ROOT/'datasets/mobility/REPORT.md'
def rel(p):return p.relative_to(ROOT).as_posix()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf8'))
def save(p,v):
 with p.open('x',encoding='utf8') as f:json.dump(v,f,ensure_ascii=False,indent=2)
def link(p,q):return os.path.relpath(q,p.parent).replace('\\','/')
replay=read(EV/'product-replay-v1.json'); baseline=read(EV/'resume-baseline-v1.json')
assert len(replay['replays'])==16 and replay['same_group_count']==1746 and not replay['network_attempts']
suite=ET.parse(EV/'related-v1.xml').getroot();suites=list(suite.iter('testsuite'))
tests=sum(int(s.attrib['tests']) for s in suites);skipped=sum(int(s.attrib.get('skipped',0)) for s in suites)
assert tests==97 and skipped==0 and all(int(s.attrib.get('failures',0))+int(s.attrib.get('errors',0))==0 for s in suites)
assert read(EV/'related-v1-run.json')['exit_code']==0
assert all(sha(ROOT/p)==h for p,h in baseline['hashes'].items()),'再開後の他作業変更'
REPORT=CS/'wiki/records/reports'/(NOW.strftime('%Y-%m-%d_%H%M')+'_김포공항_공식승차시간_재개검증.md')
ASSETS=CS/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v50'
assert not REPORT.exists() and not ASSETS.exists()
backups=[]
for p in (DEBUG,WIKI,DATAREPORT):
 h=sha(p);b=p.parent/'_backup'/NOW.strftime('%Y-%m-%d_%H%M%S_김포공항결과기록')/p.name
 b.parent.mkdir(parents=True,exist_ok=False);shutil.copy2(p,b)
 assert sha(b)==h and sha(p)==h
 backups.append({'path':rel(p),'backup':rel(b),'sha256':h})
save(EV/'publication-backups-v1.json',backups)
ASSETS.mkdir()
catalogpath=CS/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v49/readiness-catalog.json'
catalog=read(catalogpath);catalog.update(created_at=NOW.isoformat(),scope='김포공항 공식 승차시간 확대 재개 검증·21개 기존 판단 유지',prior_catalog_sha256=sha(catalogpath))
update='김포공항 공식 4그룹 680분 추가 대조·공표 밖 104행 후보 제외. 세 역 합계 12그룹 2044분/제외 312행. 통제 재생 16/16·관련 97/97·다른 1746그룹 유지. 실제 ETA·탑승 검증 아님.'
for f in catalog['features']:
 if f['name'] in ('지하철 경로 산출','첫차·막차·출발 역산'):f['current_update_v50']=update
assert len(catalog['features'])==21 and Counter(f['status'] for f in catalog['features'])==Counter({'조건부 사용':3,'개선 필요':9,'추가 검증':9})
save(ASSETS/'readiness-catalog.json',catalog)
body=f'''# 김포공항 공식 승차시간 확대 작업을 재개해 검증했습니다

공식 표에 없는 출발을 선택하던 김포공항 구간의 자료 반영과 검증을 마쳤습니다. 같은 준비 시각에서 서울 방향은 13:19→13:24, 공항 방향은 평일 13:06→13:09·휴일 13:06→13:10으로 바뀌었습니다. 보유 자료로 계산한 예정 출발이며 실제 열차 관측값은 아닙니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 새 공식 시각 대조 | 일치 | 680/680개 = 100% |
| 변경 전후 교대 재생 | 통과 | 16/16회 = 100% |
| 다른 시간표 그룹 보존 | 일치 | 1,746/1,746그룹 = 100% |
| 관련 회귀 검사 | 통과 | {tests}/{tests}건 = 100% |

## 무엇이 달라졌는가

[AREX 김포공항 공식 일반열차 표](https://www.airportrailroad.com/train/normal/info/050)의 평일·휴일, 서울·공항 양방향 5~24시 전체 4개 표를 다시 읽었습니다. 기존에 확보한 680분·현재 대조 자료와 680/680개가 같았습니다. 평일 각 방향 182개, 휴일 각 방향 158개입니다. 시간표 원자료 784행에는 공식 표 밖 104행(조건마다 26행)이 섞여 있었고, 공식 시각의 누락·중복은 각각 0개였습니다. [재확인 숫자]({link(REPORT,RAW/'official-minute-facts-rechecked-v1.json')})·[출처 대조]({link(REPORT,EV/'official-recheck-v1.json')})·[원행 검사]({link(REPORT,EV/'resume-data-audit-v1.json')}).

이번 재개에서는 이미 반영된 자료를 다시 쓰지 않고 검증과 기록을 마쳤습니다. 런타임은 김포공항의 이 104행을 승차 후보에서 제외합니다. 홍대입구·디지털미디어시티와 합계 12그룹 2,044분을 대조하고 312행을 제외합니다. 기존 8그룹 내용과 원시간표 453,668행·수집일·해시는 보존했습니다. 제외 행의 개별 열차종류나 통과 여부까지 확인한 것은 아닙니다.

## 어떻게 확인했는가

중단 전의 8그룹 백업을 A, 현재 12그룹 자료를 B로 읽었습니다. 현재 자료를 되돌리거나 이전 반영 스크립트를 재실행하지 않았습니다. A는 승차 대조 파일 경로만 검증된 백업으로 바꾸고 나머지 입력은 B와 같게 했습니다. 경로 지정이 기본 명세 검사를 건너뛰므로 백업 명세의 파일 크기·SHA256을 따로 확인했습니다. B는 현재 기본 자료의 전체 명세 해시 검사를 통과했습니다.

| 조건 | 준비 시각 | 이전 A | 현재 B |
|---|---|---|---|
| 평일 서울 방향 → 마곡나루 | 13:18 | 13:19 | 13:24 |
| 휴일 서울 방향 → 마곡나루 | 13:18 | 13:19 | 13:24 |
| 평일 공항 방향 → 계양 | 13:05 | 13:06 | 13:09 |
| 휴일 공항 방향 → 계양 | 13:05 | 13:06 | 13:10 |

각 조건 A·B·B·A 순서로 총 16/16회 같은 결과를 얻었습니다. 계양은 양방향 계산을 검사하기 위한 내부 목적지이며 서울 상품 범위 확대 근거가 아닙니다. 김포공항 평일·휴일 두 시간표 그룹만 달라졌고, 나머지 1,746그룹의 출발분·방향·종착·추정표시·열차번호·급행표시는 동일했습니다. 입력 내용 판은 새 대조 파일의 해시를 반영했고, 원자료 날짜를 새 수집일처럼 바꾸지 않았습니다. [계산 원문]({link(REPORT,EV/'product-replay-v1.json')}). 반복한 개발 재생이며 독립 표본이나 정확도 향상률로 해석하지 않습니다.

관련 6개 시험 파일에서 97/97건 통과, 전체층 165건 선택 제외입니다. [명령]({link(REPORT,EV/'related-v1-run.json')})·[로그]({link(REPORT,EV/'related-v1.log')})·[JUnit 결과]({link(REPORT,EV/'related-v1.xml')}). 이번 재개에서 제품 코드나 시험 코드는 수정하지 않았습니다.

mock 서버 시험 0건 (화면 반응): 안 했음.

실서버 확인 (서버 응답): cs 프로젝트 서버 HTTP 확인 안 했음. 실제 ETA 오차·탑승·결제 표본은 각각 0건입니다.

## API 예비량과 변경 보존

이번 제한 있는 API 호출은 0회입니다. 공유 누적 사용량·잔여량·공급자 갱신 시각을 확인하지 않았으므로 수치로 추정하지 않고 해당 API를 호출하지 않았습니다. 재생에서는 네트워크 연결을 차단했으며 연결 시도도 0회였습니다. 실패·재시도에 따른 추가 차감도 0회입니다. 공식 웹 열기와 이미 보관한 사실값을 사용했습니다. 일일 한도의 최소 20% 예비량 정책과 운영 서비스 설정은 그대로입니다. [예비량 정책 기록]({link(REPORT,CS/'wiki/records/reports/2026-10-09_1508_이동API예비량20퍼센트.md')}).

직전 완료본 310개 해시 중 304개는 같고 6개는 달랐습니다. 2개는 이미 반영된 김포공항 자료·명세, 1개는 인계·예비량 기록이 추가된 현재 wiki, 3개는 다른 작업의 코드·설정 변경입니다. 다른 작업의 3개 변경을 현재 기준으로 보존했습니다. 재개 시점 310/310개 파일 해시가 재생·관련 시험 뒤에도 같음을 확인한 다음 기록 파일만 갱신했습니다. [시작 해시]({link(REPORT,EV/'resume-baseline-v1.json')})·[보존 검사]({link(REPORT,EV/'prior-preservation-v1.json')}).

변경 전 자료의 [기존 백업 목록]({link(REPORT,EV/'backup-manifest-v1.json')})과 이번 기록을 쓰기 직전의 [추가 백업 목록]({link(REPORT,EV/'publication-backups-v1.json')})을 보존했습니다. 제품 자료·코드는 이번 재개에서 덮어쓰지 않았습니다. [원인 기록]({link(REPORT,DEBUG)})·[실행 스크립트와 검증 폴더]({link(REPORT,EV)}/).

## 남은 범위

전체 21개 기능은 조건부 사용 3개·개선 필요 9개·추가 검증 9개를 유지합니다. 이 분류는 완료율이 아닙니다. [시각화 v50]({link(REPORT,ASSETS/'mobility-readiness.html')})·[21개 판단 근거]({link(REPORT,ASSETS/'readiness-catalog.json')}). 브라우저 렌더링은 미확인이며 HTML 구조·연결 대상만 검사했습니다.

다음 최소 단위는 공항철도 대체 도착정보의 운행ID·관측 시각·역귀속을 확인해 실제 출발 안내에 연결할 수 있는 범위를 확정하는 것입니다. 이번 정적 시간표 대조를 실시간 연결 성공으로 세지 않습니다. 다른 역의 완전 표·개별 열차 정차 식별, 1.2km 도보 정책 안 새 웹 표본, 혼합 운임·누락 경로 검증도 남았습니다. 새 논문 알고리즘을 적용한 변경은 없으며, 이 단위는 공식 시간표 사실값의 대조와 기존 제품 계산 경로 검증입니다. 커밋·푸시·배포·외부 메시지 전송은 하지 않았습니다.
'''
# 기록 쓰기 직전에 다시 확인하여 다른 작업이 끼어들었으면 중단합니다.
assert all(sha(ROOT/p)==h for p,h in baseline['hashes'].items())
save(EV/'prior-preservation-v1.json',{'checked_at':NOW.isoformat(),'matched_before_publication':len(baseline['hashes']),'total_before_publication':len(baseline['hashes']),'previous_matches':baseline['previous_matches'],'previous_total':baseline['previous_total'],'previous_changes':baseline['previous_changes'],'product_mutations_in_resume':0,'limited_api_calls':0})
with REPORT.open('x',encoding='utf8') as f:f.write(body)
debugtext=DEBUG.read_text(encoding='utf8').replace('## 미해결','## 해결됨 (2026-10-09, 부분) — 공식 4그룹 승차 후보 혼입')
debugtext+=f'\n재개 결과: 위 내용은 14:26 발견 당시 상태입니다. 21시 재개 시 자료는 이미 12그룹으로 반영되어 있었고 다시 쓰지 않았습니다. 검증된 백업 A/현재 B를 16/16회 교대해 U13:19→13:24, D평일13:06→13:09·휴일13:06→13:10을 확인했습니다. 관련97/97·다른1746그룹 동일. 원행 종류/정차 식별·다른 역·실제 ETA/탑승 검증은 미해결입니다. [보고서]({link(DEBUG,REPORT)})·[실행 원문]({link(DEBUG,EV/"product-replay-v1.json")}).\n'
assert sha(DEBUG)==backups[0]['sha256'];DEBUG.write_text(debugtext,encoding='utf8')
for p,addition,b in [
 (WIKI,f'\n\n## {NOW.strftime("%Y-%m-%d_%H%M")} 김포공항 공식 승차시간 재개 검증\n\n이미 반영된 김포공항 공식4그룹680분을 현재 웹과680/680재대조했습니다. 백업A/현재B 교대16/16에서서울13:19→13:24·공항평일13:06→13:09/휴일13:10. 세역합계12그룹2044분/제외312행, 기존8그룹·원자료·다른1746그룹보존, 관련97/97(165선택제외)·명세해시통과. 재개시점310/310해시유지·다른작업코드/설정3개보존. 이번 제한API0·제품코드/자료재수정0·실제ETA/탑승/결제0·全21분류3/9/9유지·전체미완료. 다음은공항철도대체도착정보의운행ID/관측시각/역귀속·실제출발안내연결범위확인. [보고서]({link(WIKI,REPORT)})·[시각화v50]({link(WIKI,ASSETS/"mobility-readiness.html")})·[검증]({link(WIKI,EV)}/).\n',backups[1]),
 (DATAREPORT,f'\n\n## {NOW.strftime("%Y-%m-%d_%H%M")} 김포공항 공표 승차 대조 재개 검증\n\n김포공항 평일·휴일 양방향4그룹680분을 공식 웹과재대조했습니다. 기존8그룹과합계12그룹2044분/제외312행. 중단전에반영된가공자료는재작성하지않고백업/현재교대16/16·관련97/97·다른1746그룹보존·명세해시를검사했습니다. 원자료453668행·수집일유지·실제ETA/탑승검증아님. [새 사실값]({link(DATAREPORT,RAW/"official-minute-facts-rechecked-v1.json")})·[보고서]({link(DATAREPORT,REPORT)}).\n',backups[2])]:
 assert sha(p)==b['sha256']
 with p.open('a',encoding='utf8') as f:f.write(addition.replace('全21','전체21'))
cards=''.join(f'<article><h3>{escape(f["name"])}</h3><p><b>{escape(f["status"])}</b> · {escape(f["scope"])}</p><p>{escape(f["metric"])}</p><details><summary>근거와 남은 부분</summary><p>{escape(f["reason"])}</p><p>{escape(f["need"])}</p><p>{escape(f.get("current_update_v50",f.get("current_update_v49","")))}</p></details></article>' for f in catalog['features'])
page=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 준비도 v50 — 김포공항 승차시간 검증</title><style>body{{margin:0;background:#f5f7fa;color:#193a56;font-family:system-ui,sans-serif;line-height:1.65}}main{{max-width:1120px;margin:auto;padding:24px}}h1{{font-size:30px;line-height:1.4}}h2{{margin-top:32px}}a,summary{{color:#126b67}}.scroll{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;background:white}}td,th{{text-align:left;padding:12px;border-bottom:1px solid #cdd6df}}.notice{{border-left:4px solid #a05a00;padding:16px;background:#fff1da}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:16px}}article{{padding:20px;background:white;border:1px solid #cdd6df;border-radius:8px;overflow-wrap:anywhere}}summary{{cursor:pointer}}a:focus-visible,summary:focus-visible{{outline:3px solid #126b67;outline-offset:3px}}</style><main><p>triPilot · {NOW.strftime('%Y-%m-%d %H:%M')} · v50</p><h1>김포공항의 공식 표 밖 출발을 후보에서 제외했습니다</h1><p>공식 시각 680/680개 일치 · 교대 재생 16/16회 통과 · 관련 검사 97/97건 통과</p><div class="scroll"><table><caption>같은 준비 시각으로 비교한 예정 출발</caption><thead><tr><th scope="col">조건</th><th scope="col">준비</th><th scope="col">이전</th><th scope="col">현재</th></tr></thead><tbody><tr><th scope="row">평일·휴일 서울 방향</th><td>13:18</td><td>13:19</td><td>13:24</td></tr><tr><th scope="row">평일 공항 방향</th><td>13:05</td><td>13:06</td><td>13:09</td></tr><tr><th scope="row">휴일 공항 방향</th><td>13:05</td><td>13:06</td><td>13:10</td></tr></tbody></table></div><p>세 역 합계 12그룹·2,044분 대조 / 312행 제외. 다른 1,746그룹과 원자료를 보존했습니다.</p><p class="notice">통제된 개발 재생입니다. 실제 ETA 오차·탑승·결제 표본은 각각 0건이며 전체 완료가 아닙니다. 제한 있는 API 호출은 0회입니다.</p><h2>21개 기능의 현재 판단</h2><p>조건부 사용 3개 · 개선 필요 9개 · 추가 검증 9개. 분류는 완료율이 아닙니다.</p><div class="grid">{cards}</div><p><a href="{link(ASSETS/'mobility-readiness.html',REPORT)}">이번 보고서</a> · <a href="{link(ASSETS/'mobility-readiness.html',EV/'product-replay-v1.json')}">계산 원문</a> · <a href="readiness-catalog.json">21개 근거</a> · <a href="{link(ASSETS/'mobility-readiness.html',EV/'publication-backups-v1.json')}">기록 변경 전 백업</a></p><p>브라우저 렌더링 미확인. cs 프로젝트 서버 HTTP 확인·배포는 하지 않았습니다.</p></main></html>'''
with (ASSETS/'mobility-readiness.html').open('x',encoding='utf8') as f:f.write(page)
assert page.count('<article>')==21 and '<script' not in page
for dest in re.findall('href="([^"]+)"',page):assert (ASSETS/dest).resolve().exists(),dest
for dest in re.findall(r'\]\(([^)]+)\)',body):
 if not dest.startswith('http'):assert (REPORT.parent/dest).resolve().exists(),dest
save(EV/'visual-validation-v1.json',{'cards':21,'local_links_exist':True,'static_no_javascript':True,'table_headers_scoped':True,'browser_rendered':False})
for name in ('resume_replay_gimpo_boarding_v3.py','verify_gimpo_boarding_v1.py',Path(__file__).name):shutil.copy2(Path(__file__).parent/name,EV/name)
save(EV/'publication-state-v1.json',{'report':rel(REPORT),'assets':rel(ASSETS),'tests':tests,'replays':16,'full_feature_completion':False,'mutated_product_files':0})
print(json.dumps({'report':rel(REPORT),'assets':rel(ASSETS),'tests':tests,'backups':len(backups)},ensure_ascii=False))
