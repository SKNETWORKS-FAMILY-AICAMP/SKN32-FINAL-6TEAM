from pathlib import Path
from datetime import datetime
from collections import Counter
import json,hashlib,shutil,re,html,os,xml.etree.ElementTree as ET,difflib
ROOT=Path(__file__).resolve().parents[2];CS=ROOT/'final_project_cs';w=json.loads((Path(__file__).parent/'subway-completeness-work-v4.json').read_text(encoding='utf8'));ev=ROOT/w['evidence'];raw=ROOT/w['raw'];created=datetime.now().astimezone();stamp=created.strftime('%Y-%m-%d_%H%M');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):
 with p.open('x',encoding='utf8') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False)
source=w['baseline_source_hashes'];owned={'final_project_cs/app/domains/travel_ops/ports/data_sources/seoul_subway.py','final_project_cs/app/domains/travel_ops/ports/data_sources/subway_boarding.py','final_project_cs/tests/unit/travel/test_subway_boardable_v1.py','final_project_cs/tests/unit/travel/test_seoul_subway_arrival.py'};changed=[p for p,h in source.items() if sha(ROOT/p)!=h];assert set(changed)==owned.intersection(source),changed
newtest='final_project_cs/tests/unit/travel/test_subway_completeness_v1.py';source={p:sha(ROOT/p) for p in source};source[newtest]=sha(ROOT/newtest); source.update({p:sha(ROOT/p) for p in owned if p not in source})
xml=ET.parse(ev/'after-v2.xml');cases=xml.findall('.//testcase');assert len(cases)==284 and not xml.findall('.//failure') and not xml.findall('.//error');new=sum(x.get('classname','').endswith('test_subway_completeness_v1') for x in cases);assert new==32
first=json.loads((ev/'page-size-live-v1.json').read_text(encoding='utf8'));after=json.loads((ev/'after-live-v1.json').read_text(encoding='utf8'));a,b,c,last=first['requests'];assert [x['returned_rows'] for x in first['requests']]==[20,22,22,20];assert a['row_identities']==b['row_identities'][:20]==c['row_identities'][:20]==last['row_identities'];assert b['row_identities']==c['row_identities']
for x in first['requests']+after['requests']:assert sha(ROOT/x['raw_path'])==x['raw_sha256'] and x.get('code')=='INFO-000'
for x in after['requests']:assert x['snapshot']['coverage_complete'] is True and x['raw_rows']==x['provider_total'] and x['actual_http_responses']==1
assert after['requests'][1]['product_result']['status']=='realtime'
for p in [CS/'wiki/teams/mobility.md',ROOT/'datasets/mobility/REPORT.md']:
 # 백업 이름도 한국어로 생성한다.
 bpath=p.parent/'_backup'/(stamp+'_부분응답_검증기록')/p.name;bpath.parent.mkdir(parents=True,exist_ok=True);assert not bpath.exists();shutil.copy2(p,bpath);w['backups'].append({'source':p.relative_to(ROOT).as_posix(),'backup':bpath.relative_to(ROOT).as_posix(),'sha256':sha(bpath),'created_at':datetime.fromtimestamp(bpath.stat().st_ctime).astimezone().isoformat()})
assert all(sha(ROOT/x['backup'])==x['sha256'] for x in w['backups'])
save(ev/'backup-manifest-v1.json',{'created_at':created.isoformat(),'backups':w['backups']})
report=CS/'wiki/records/reports'/f'{stamp}_지하철_20행누락_해소와_응답완전성_검증.md';assets=CS/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v42';assets.mkdir(exist_ok=False);prior=assets.parent/'2026-10-09_mobility_readiness_v41';catalog=json.loads((prior/'readiness-catalog.json').read_text(encoding='utf8'));catalog.update(created_at=created.isoformat(),scope='서울역 실제 교대 조회에서20/22행 절단 재현, 공식최대1000행 한 번 조회와 완전성 검사 적용. 실제ETA정확도 미측정.',prior_catalog_sha256=sha(prior/'readiness-catalog.json'))
need='v42: 서울역 실제20→1000→1000→20 교대4회에서20/22→22/22→22/22→20/22행, 동일22행 식별순서 확인. 일반키공식1000행·sample5행 단일조회와 전체/반환건수·완전여부를 소스에 보존. 일부/건수미확인은 현재승차선택unavailable근거로 시간표모델 재검증. 신규32/32·관련284/284. 수정제품실HTTP서울19/19·양평7/7, 현재출발/후속환승모델1/1연결. 잘렸던2행은오래됨/0ETA라탈수있는열차로세지않음. 독립웹/실제ETA오차/탑승0, 전체21판정4/9/8유지. 실제후속환승예측·180역명대응·급행/순환선·장애대체·1.2km안새정렬웹·cs프로젝트HTTP/배달/배포검증남음.'
for feature in catalog['features']:
 if feature['name'] in ('지하철 경로 산출','실시간 지하철·버스 도착'):
  feature['prior_need_v41']=feature['need'];feature['need']=need;feature['response_coverage_v42']={'before':{'rows':20,'total':22},'after_same_snapshot':{'rows':22,'total':22},'abba_requests':4,'new_tests':32,'related_tests':284,'actual_after_requests':2,'actual_eta_error_samples':0}
assert len(catalog['features'])==21 and Counter(x['status'] for x in catalog['features'])==catalog['counts'];save(assets/'readiness-catalog.json',catalog)
rawlink=Path(os.path.relpath(raw,report.parent)).as_posix()+'/'
text=f'''# 지하철20행 누락 해소와 응답 완전성 검증

환승역의 도착정보를 앞20행에서 자르던 문제를 고쳤습니다. 공식 최대1000행을 한 번에 조회하며, 전체건수와 실제 반환건수를 확인해 일부 응답을 현재 승차의 완전한 근거로 쓰지 않습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 최신 코드·자료·산출물 대조 | 일치 | 282/282 = 100% |
| 새 누락·완전성 시험 | 통과 | 32/32 = 100% |
| 관련 회귀 시험 | 통과 | 284/284 = 100% |
| 수정 코드의 실제 조회 | 정상 | 2/2 = 100% |

282는 직전 코드·시험·데이터254개+산출물28개입니다. 신규32는 관련284에 포함됩니다. 실제 조회는 수정 전 네 번의 교대조회와 수정 후 두 번으로 총6회이며 서로 다른 시각의 응답입니다. 실제 ETA오차·탑승·결제·새 독립 웹 경로 표본은0개입니다.

## 원인과 실제 재현

기존 소스는 한 역에20행이면 충분하다고 가정했고 제공 total을 보존하지 않았습니다. 환승역의 뒤쪽 호선이나 열차가 잘려도 선택기가 정상 목록과 구별하지 못했습니다. [서울시 공식 도착정보 명세](https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A)를2026-10-09에 다시 읽어 한 번 조회의 최대1000건과 공개sample최대5건을 확인했습니다.1000은 공식 프로토콜 상한이며 정확도에 맞춰 조정한 상수가 아닙니다.

서울역을20→1000→1000→20으로 교대해 네 번 실제 조회했습니다. 전체22행 중20→22→22→20행이 반환됐고, 두 큰 범위의22행 식별순서는 같았으며 네 응답의 앞20행 식별순서도 같았습니다. 최소 두 번의 범위별 반복으로 해당 시각의 절단을 재현했습니다. 독립 경로 정확도 실험이나 여러 날짜의 제공처 가용성 측정은 아닙니다.

| 조회 순서 | 요청 종료위치 | 원문 반환/제공 total | 상태 |
|---|---:|---:|---|
| A | 20 | 20/22 = 90.9% | 2행 절단 |
| B | 1000 | 22/22 = 100% | 선언된 전체행 반환 |
| B | 1000 | 22/22 = 100% | 같은 식별순서 |
| A | 20 | 20/22 = 90.9% | 같은 앞20행 |

빠진2행은 공항철도 문자형 열차번호A1020(생성11:38:21)과 경의중앙선5057(생성11:54:24)이었습니다. 둘 다 원문ETA0·운행중코드99였고 조회시각에는 신선도/0ETA 조건에서 바로 탑승할 열차로 볼 수 없습니다. 이번 복구를 두 대의 실제 탑승 가능 열차 증가로 세지 않습니다. 문자형 열차번호를 받는 노선의 현재승차 지원은 기존 숫자형 ID 정책과 별도 대조가 필요합니다.

## 수정 내용과 실패 시 경로

일반 전용키는0/1000, 공개sample키는0/5로 한 번 조회합니다. 여러 페이지의 다른 생성시각을 합치거나 자동 재시도하지 않습니다. source.py의 PAGE_SIZE 상수와 같은 공식 한도를 이름 붙여 사용하며 별도 요금·시간 보정값을 만들지 않았습니다.

도착 정규화에 provider_total(제공 전체건수), response_row_count(필터 전 반환행수), coverage_complete(완전여부)를 추가합니다. 호선 필터를 적용하기 전 원문 전체행수를 기준으로 대조하므로 필요한 호선만 남았다고 전체건수를 바꾸지 않습니다. 공식 JSON total과 공통명세 list_total_count가 함께 있으면 같아야 합니다. 논리값·음수·소수·빈값·문자·초대형 숫자문자열 오류, 서로다른 두건수, 전체보다많은행은 정상으로 받아들이지 않습니다.

전체보다 적게 반환되거나 전체건수가 빠지면 표시용 자료는 보존하되 현재승차선택은 incomplete_arrivals 또는 arrival_total_unknown 이유의 unavailable로 반환합니다. 출발 관측기는 이 이유를 남기고 기존 시간표 모델로 재검증합니다. 모델도 계산되지 않으면 기존 재계산/치명 경로를 유지합니다. INFO-200 공식빈결과는 전체0으로 구분하며 정상코드의 건수미확인을 무운행으로 바꾸지 않습니다. 기존 통제 선택 입력의 필드부재는 호환으로 유지하지만 제품 소스는 새 완전성 필드를 항상 보냅니다. 공개 Core/고객JSON 계약은 변경하지 않습니다.

## 시험과 실제 수정 코드 확인

변경 전 신규32/32가 실패했습니다. 수정 후 첫 관련실행은283통과·1실패였으며 기존 시험의 요청주소가20행에 고정돼 있었습니다. 기존 시험을 백업하고 공식1000행 요청으로 기대조건을 바꾼 뒤 신규32포함284/284가 통과했습니다. Ruff5개파일 검사도 통과했습니다. 원래 실패로그와 수정후로그를 모두 보존했습니다. 21번째에만 유효한 열차가 있는 통제 응답에서 한 번 조회로 그 열차를 선택하고, 부분응답이면 해당 후보가 있어도 선택하지 않으며 제품 시간표 모델 재검증까지 확인합니다.

수정 제품 소스 실제 조회 두 번은 서울역19/19행·양평7/7행 모두 HTTP200 INFO-000, coverage_complete=true였습니다. 이전11:56대22행과 이후 조회19행은 다른시각의 운행응답이므로 같은분모로 정확도 효과를 계산하지 않습니다. 양평은 기존 전용 키로 실제 출발관측기→boardable_arrival→현재첫승차/후속2호선 모델 경로까지 realtime을 반환했습니다. 장소좌표·접근/퇴장2분은 앞 판의 통제 문맥입니다. 예상15분은 이 시각의 모델결과이고 실탑승 오차 측정이 아닙니다.

mock 서버 시험(화면 반응): 안 했음.

실서버 확인(서버 응답): 서울시무료지하철API6/6HTTP정상. 그중수정소스2회·양평제품출발관측기1회 연결. cs 프로젝트 서버/로컬 개발 서버 HTTP와 일정저장·고객알림 배달은 이번에 확인하지 않았습니다. 지도개발자API0회, 커밋·푸시·배포·외부메시지·결제는 하지 않았습니다.

## 보존과 남은 검증

전체21개는 조건부사용4·개선필요9·추가검증8을 유지합니다. 20행 절단과 부분응답의 무조건 선택은 고쳤지만 공급자가 선언한 total 자체의 모든 운행정보 완전성은 보장하지 않습니다. 오래된 정보·일반/급행·숫자/문자 열차번호·180역명 대응·장애 대체·실제 위치/탑승 갱신·미래 환승 정확도·1.2km안의 새 정렬 웹 대조·cs프로젝트HTTP/안내배달/배포 증거는 남습니다. 신선도30/90/2초는 오차 허용치 측정이 아닙니다. 공식 프로토콜과 실제 재현으로 원인을 해결했으며 새 논문 알고리즘은 적용하지 않았습니다.

- [시각화v42·21기능](assets/{assets.name}/mobility-readiness.html) — 실제 누락과 전체행 확인 흐름.
- [실행 근거](../evidence/{ev.name}/) — 교대원문·전후시험·수정소스실조회·내용해시.
- [원문·수집정보]({rawlink}) — 실제응답6개, 자료는git제외.
- [백업 명세](../evidence/{ev.name}/backup-manifest-v1.json) — 코드·기존시험·문서·수집설명 수정직전사본.

보고파일명은 생성시각{created.isoformat()}에서 정했습니다. 시각화는 정적 링크·구문을 검사하며, 앞 판에서 브라우저file:URL이 차단돼 이번에는 우회하거나 렌더링을 재시도하지 않습니다.
'''
text=text.replace('source.py의 PAGE_SIZE','지하철 소스의 PAGE_SIZE')
with report.open('x',encoding='utf8') as f:f.write(text)
wiki=CS/'wiki/teams/mobility.md';wiki.write_text(wiki.read_text(encoding='utf8')+f'''\n\n## {stamp} 지하철20행 절단과 부분응답 선택 해소

서울역20→1000→1000→20교대실HTTP4회에서20/22→22/22→22/22→20/22행·동일식별순서를확인해공식상한1000행단일조회(sample5행)와전체/반환건수·완전성검사를연결했습니다. 일부/건수미확인은현재승차선택unavailable이유로시간표모델재검증합니다. 신규32/32·관련284/284·Ruff5파일,수정소스서울19/19·양평7/7실조회와출발/환승모델1/1연결. [보고서](../records/reports/{report.name})·[시각화v42](../records/reports/assets/{assets.name}/mobility-readiness.html). 잘린2행은오래됨/0ETA여서실탑승가능열차증가로세지않음. 지도개발자API/실제ETA오차/탑승0·전체21판단4/9/8유지·cs프로젝트HTTP/배달/배포미확인.
''',encoding='utf8')
dreport=ROOT/'datasets/mobility/REPORT.md';dreport.write_text(dreport.read_text(encoding='utf8')+f'''\n\n## {stamp} 지하철조회범위 교대원문과 수정제품응답

[원문·수집정보](raw/{raw.name}/)는서울특별시OA-12764·공공누리제1유형(출처서울특별시)입니다. 서울역20/1000/1000/20교대4회응답20/22/22/20행(total22)과수정제품서울19행(total19)·양평7행(total7)을새파일6개로보존했습니다. 조회시각/원문SHA256/범위/행식별을기록하며키나인증URL은저장하지않았습니다. 첫교대4회는실제HTTP대조,후속2회는수정제품소스직접조회이고양평은출발관측기와후속환승모델연결입니다. 장소/접근/퇴장통제·실제ETA오차/탑승/결제/독립웹경로0·지도개발자API0. 수집설명오탈자수정은원래메타와스크립트를백업했고실응답바이트를바꾸지않았습니다. [보고서](../../final_project_cs/wiki/records/reports/{report.name})와백업/해시명세를잇습니다. 선언된total은제공처응답범위이며현실의전체운행보장은아닙니다.
''',encoding='utf8')
styles=re.search(r'<style>(.*?)</style>',(prior/'mobility-readiness.html').read_text(encoding='utf8'),re.S).group(1);cards=''.join(f'<article data-status="{html.escape(x["status"])}"><span class="status">{html.escape(x["status"])}</span><h3>{html.escape(x["name"])}</h3><p>{html.escape(x["scope"])}</p><p><b>기존 비교 수치</b> {html.escape(x["metric"])}</p><details><summary>판단 근거와 필요한 검증</summary><p>{html.escape(x["reason"])}</p><p>{html.escape(x["need"])}</p></details></article>' for x in catalog['features'])
flow='''<svg viewBox="0 0 820 175" role="img" aria-label="공식 최대범위로 한 번 조회한 뒤 전체건수와 반환건수를 비교하고 완전한 응답만 현재승차 선택에 사용" style="width:100%;min-width:630px;background:white;border:1px solid #d6dce5"><g stroke="#354052" fill="none"><rect x="20" y="30" width="220" height="105"/><rect x="300" y="30" width="220" height="105"/><rect x="580" y="30" width="220" height="105"/><path d="M240 82h60m220 0h60"/></g><g fill="#161c28" font-family="sans-serif" font-size="17" text-anchor="middle"><text x="130" y="66">공식 최대1000행</text><text x="130" y="102">한 번 조회</text><text x="410" y="66">전체 / 반환 건수</text><text x="410" y="102">필터 전에 대조</text><text x="690" y="66">완전: 현재 승차 선택</text><text x="690" y="102">일부: 모델 재검증</text></g></svg>'''
visual=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 검증v42 — 도착정보20행 누락 해소</title><style>{styles}</style><main><p>서울 이동 검증 · v42 · {created.isoformat()}</p><h1>앞20행에서 잘리던<br>지하철 도착정보를 복구했습니다.</h1><p class="lead">공식 최대1000행을 한 번에 받고 전체건수·반환건수를 대조합니다. 일부응답·건수미확인은 현재승차 선택에 쓰지 않고 근거를 남겨 시간표 모델로 재검증합니다.</p><section class="metrics"><p><b>20/22→22/22행</b>같은 역 교대 실제 응답</p><p><b>32/32 ·284/284</b>신규·관련 통제 시험</p><p><b>2/2 실제 조회</b>수정 소스 서울19/19·양평7/7</p></section><h2>응답 범위와 현재 승차의 경계</h2><div class="scroll">{flow}</div><p>1000은 공식 요청 상한이고 호출 건수는 한 번입니다. 공개sample만 공식5행 범위를 사용합니다. 서로 다른 생성시각의 페이지를 합치지 않습니다.</p><h2>서울역 같은 시각의 교대 대조</h2><div class="scroll"><table><thead><tr><th>순서</th><th>조회 범위</th><th>반환 / total</th><th>판정</th></tr></thead><tbody><tr><td>A</td><td>0/20</td><td>20/22 =90.9%</td><td>2행 절단</td></tr><tr><td>B</td><td>0/1000</td><td>22/22 =100%</td><td>전체 반환</td></tr><tr><td>B</td><td>0/1000</td><td>22/22 =100%</td><td>같은 식별순서</td></tr><tr><td>A</td><td>0/20</td><td>20/22 =90.9%</td><td>같은 앞20행</td></tr></tbody></table></div><p>네 응답의 앞20행·두 전체22행 식별순서가 일치했습니다. 빠진2행은 오래된 정보/0ETA여서 실제 탑승가능 열차 증가로 세지 않습니다. 현실의 전체 운행이나 실제 ETA 정확도를 보장하는 표가 아닙니다.</p><h2>수정 제품의 실제 조회</h2><p>새 시각의 서울19/19·양평7/7행 모두완전. 양평 실제소스→현재첫승차→후속환승모델1/1연결·예상15분입니다. 장소좌표·접근/퇴장2분은통제이며 실탑승오차/결제표본0개입니다. 첫교대4회+수정2회=서울시무료API6회,지도개발자API0회.</p><h2>전체21개 기능의 판단</h2><p>조건부사용4 · 개선필요9 · 추가검증8 유지. 나머지카드의기존비교수치는이번에재측정하지않았습니다.180역명대응·급행/순환선·문자열열차번호·오래된정보·장애대체·1.2km안새정렬웹·실제위치/탑승·cs프로젝트HTTP/배달/배포는남습니다.</p><label for="filter">판단별 보기</label><select id="filter"><option value="all">전체21개</option><option>조건부 사용</option><option>개선 필요</option><option>추가 검증</option></select><section class="grid">{cards}</section><footer><a href="../../{report.name}">검증 보고서</a> · <a href="../../../evidence/{ev.name}/verification-proof-v1.json">검증 원문</a> · <a href="../../../evidence/{ev.name}/backup-manifest-v1.json">백업 명세</a> · <a href="../{prior.name}/mobility-readiness.html">이전 판v41</a><p>출처: 서울특별시 OA-12764 · 공공누리 제1유형. 브라우저 로컬파일 주소 차단으로 화면 렌더링은 확인하지 않았습니다.</p></footer></main><script>document.querySelector('#filter').addEventListener('change',e=>{{document.querySelectorAll('article').forEach(a=>{{a.hidden=e.target.value!=='all'&&a.dataset.status!==e.target.value;}});}});</script></html>'''
with (assets/'mobility-readiness.html').open('x',encoding='utf8') as f:f.write(visual)
debug=CS/'wiki/records/reports/debugs'/f'{w["tag"]}.md'
with debug.open('x',encoding='utf8') as f:f.write(f'''# 지하철20행 절단과 부분응답의 현재승차 선택

## 해결됨 (2026-10-09, 부분) — 요청범위와 완전성 연결

기존 지하철 소스는20행을 요청하고total을검사하지않아서울역22행의뒤2행이누락됐습니다. 실제ABBA4회와신규32실패로재현하고공식1000행단일조회·부분/미확인선택거부를적용했습니다. 신규32/32·관련284/284,Ruff5파일,수정실조회2/2·출발/환승모델1/1로닫았습니다. 공급자가declaredtotal에포함하지않은현실운행누락·문자열열차번호·실제ETA오차·실탑승·배포는이부분해결밖입니다. [보고서](../{report.name})에전후실행/원문/위험범위를보존합니다.
''')
patch=''
for x in w['backups']:
 if x['source'] in owned:
  before=(ROOT/x['backup']).read_text(encoding='utf8').splitlines(True);aftertext=(ROOT/x['source']).read_text(encoding='utf8').splitlines(True);patch+=''.join(difflib.unified_diff(before,aftertext,fromfile=x['backup'],tofile=x['source']))
with (ev/'owned-source-diff-v1.patch').open('x',encoding='utf8') as f:f.write(patch)
for name in ['collect_subway_completeness_v1.py','collect_subway_completeness_after_v1.py',Path(__file__).name]:shutil.copy2(Path(__file__).parent/name,ev/name)
save(ev/'verification-proof-v1.json',{'created_at':created.isoformat(),'source_test_data_hashes':source,'owned_changed_paths':sorted(owned),'new_test_file':newtest,'before_failed':32,'new_passed':32,'related_passed':284,'actual_abba_requests':4,'actual_after_requests':2,'exact_prefix_and_full_identity_match':True,'map_developer_api_calls':0,'actual_eta_error_boarding_payment':0,'full_feature_completion':False})
save(ev/'research-v1.json',{'checked_at':created.isoformat(),'official_docs':'https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A','protocol_max_rows':1000,'sample_max_rows':5,'applied_assumption':'총건수/응답행수범위만대조,실제운행/ETA정확도는별도.','paper_algorithm_applied':False})
save(ev/'publication-state-v1.json',{'created_at':created.isoformat(),'report':report.relative_to(ROOT).as_posix(),'assets':assets.relative_to(ROOT).as_posix(),'evidence':ev.relative_to(ROOT).as_posix(),'debug':debug.relative_to(ROOT).as_posix(),'backups':len(w['backups'])})
paths=[*ev.iterdir(),*assets.iterdir(),*raw.iterdir(),report,debug,wiki,dreport];hashes={p.relative_to(ROOT).as_posix():sha(p) for p in paths if p.is_file()};save(ev/'publication-validation-v1.json',{'created_at':created.isoformat(),'artifact_hashes':hashes,'source_hash_matches':len(source),'backup_hash_matches':len(w['backups']),'browser_render_checked':False})
print(json.dumps({'report':report.relative_to(ROOT).as_posix(),'source_hashes':len(source),'artifact_hashes':len(hashes),'backups':len(w['backups']),'new_tests':new,'related_tests':len(cases)},ensure_ascii=False))