from pathlib import Path
from datetime import datetime
from collections import Counter
import json,hashlib,shutil,re,html
ROOT=Path(__file__).resolve().parents[2];CS=ROOT/'final_project_cs';work=json.loads((Path(__file__).parent/'subway-real-key-work-v1.json').read_text(encoding='utf8'));ev=ROOT/work['evidence'];rawdir=ROOT/work['raw'];created=datetime.now().astimezone();stamp=created.strftime('%Y-%m-%d_%H%M')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):
 with p.open('x',encoding='utf8') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False)
proof=json.loads((ev/'real-key-verification-v1.json').read_text(encoding='utf8'));source_hashes=proof['source_test_data_hashes'];assert all(sha(ROOT/p)==h for p,h in source_hashes.items())
prior=CS/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v40';assets=CS/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v41';assets.mkdir(exist_ok=False)
catalog=json.loads((prior/'readiness-catalog.json').read_text(encoding='utf8'));catalog.update(created_at=created.isoformat(),scope='기존 전용 인증키로 실제 지하철 응답과 현재 출발·후속 환승 계산 연결 확인. 실제 ETA오차·탑승 정확도 미측정.',prior_catalog_sha256=sha(prior/'readiness-catalog.json'))
newneed='v41: 양평·군자 실제 전용 인증키 HTTP4/4정상·30행 확보, 원문 행수=제공 total4/4. 현재 출발 observe→실제 소스→요청별 판정기2/2연결. 통제 접근2분에서 양평→영등포구청→당산21→13분·군자→아차산8→9분 재계산, 동일 저장 응답 재생4/4일치. 병기 대응 전에는 같은 응답의 해당 방향4행0개 연결, 대응 후4개 연결. 첫 승차만 현재 예측, 이후 승차/환승은 모델. 2역4스냅샷·장소 좌표/접근/퇴장 통제이며 실제 ETA오차·독립 웹 경로·탑승/결제 표본0. 급행/순환선·180역명 대응·운행시간대/장애 대체·실제 이동 검증·cs 프로젝트 서버 HTTP 연결/배포 확인은 남음. 신선도30/90/2초는 오차 보장이 아님.'
for feature in catalog['features']:
 if feature['name'] in ('지하철 경로 산출','실시간 지하철·버스 도착'):
  feature['prior_need_v40']=feature['need'];feature['need']=newneed;feature['real_http_evidence_v41']={'requests':4,'snapshots':4,'station_names':2,'rows':30,'product_paths':2,'actual_eta_error_samples':0,'actual_boarding_payment_samples':0}
assert Counter(x['status'] for x in catalog['features'])==catalog['counts'];assert len(catalog['features'])==21
save(assets/'readiness-catalog.json',catalog)
report=CS/'wiki/records/reports'/f'{stamp}_지하철_실제인증키_출발환승_연결검증.md';debug=CS/'wiki/records/reports/debugs'/f"{work['tag']}.md";backups=[]
for path in [CS/'wiki/teams/mobility.md',ROOT/'datasets/mobility/REPORT.md']:
 b=path.parent/'_backup'/f'{stamp}_실제지하철_출발환승검증'/path.name;b.parent.mkdir(parents=True,exist_ok=False);shutil.copy2(path,b);assert sha(path)==sha(b);backups.append({'source':path.relative_to(ROOT).as_posix(),'backup':b.relative_to(ROOT).as_posix(),'sha256':sha(b)})
save(ev/'backup-manifest-v1.json',{'created_at':created.isoformat(),'backups':backups})
reporttext=f'''# 실제 지하철 인증키 조회와 현재 출발·환승 계산 검증

양평·군자의 실제 도착정보를 받아 현재 첫 승차와 뒤쪽 환승 계산까지 연결했습니다. 앞 판의 공개 예제 오류와 실제 인증키 동작을 구분했고, 병기 역명 수정이 실제 하남검단산·마천 방향 열차를 연결하는 것도 확인했습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 직전 코드·데이터·보고서 대조 | 일치 | 283/283 = 100% |
| 실제 인증키 도착 조회 | 정상 | 4/4 = 100% |
| 현재 출발 제품 경로 연결 | 확인 | 2/2 = 100% |
| 같은 응답의 재계산 재생 | 일치 | 4/4 = 100% |

283은 앞 판의 코드·시험·데이터254개와 산출물29개입니다. 4조회는 두 역×두 시각의 실제 HTTP 응답이며 총30행입니다. 2제품 경로는 통제한 장소 좌표·접근/퇴장 시간을 사용한 엔진 출발 계산입니다. 4재생은 같은 저장 관측을 경로별2회 재생한 것으로 새 독립 표본이 아닙니다.

## 문제와 구분한 원인

공개 sample 키로 양평·군자(능동)를 요청했을 때 ERROR-336이 나왔지만, 요청 범위는0/5와1/5였으므로 오류 문구만으로 원인을 확정할 수 없었습니다. 로컬 파일에 기존 지하철 전용 키가 있는지만 확인한 뒤 제품 도착 소스의 실제 네트워크 호출로 두 역을 읽었습니다. 실제 키0/20 조회는 모두 HTTP200·INFO-000이었고 각7행·8행이 반환됐습니다. 같은 소스·역명으로 실제 키에서는 작동한다는 증거이며, 공개 sample 오류의 제공처 내부 원인을 확정하거나 모든 역·시각의 가용성을 일반화하지 않습니다.

[서울시 공식 도착 API 명세](https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A)를 실행일2026-10-09에 다시 읽었습니다. 현재/다음/종착 역ID·열차 번호/종류·초 단위 ETA·정보 생성시각을 사용하며, 도착코드2는 출발입니다. sample 최대5건과 ERROR-336의 최대1000건 설명도 구분했습니다. 이번 문제는 실제 키·이름·경로 연결 확인으로 해결했으며 논문 알고리즘을 새로 적용하거나 정확도 효과를 주장하지 않습니다.

인증키는 로컬 환경 파일에서 메모리로 읽고 기록·출력·수집 URL에 넣지 않았습니다. 원문4개에도 키가 반사되지 않았음을 검사했습니다. 지도 개발자 API 호출은0회이고 서울시 무료 도착API 호출은4회입니다.

## 실제 확보 자료와 출발 연결

11:43:28대 두 역의 도착정보를 실제 제품 소스 arrivals로 조회해7+8=15행을 확보했습니다. 이어11:44:49대 출발 관측기 observe가 실제 boardable_arrival 소스를 호출해 다시7+8=15행을 받았습니다. 이 두 번째 조회는 저장 원문을 transport로 재생한 시험이 아닙니다. 수집을 계측한 transport는 원래 HTTP 호출을 그대로 실행하고 응답을 보존했습니다. 네 응답 모두 원문 행수와 제공처 total이 일치했습니다. 이는 해당 시각의 페이지 확인이고 공급자 자체가 모든 예정 열차를 보장한다는 의미는 아닙니다.

| 제품 계산 경로 | 같은 완료시각 시간표 모델 | 현재 첫 승차 반영 | 뒤쪽 구간 |
|---|---:|---:|---|
| 양평→영등포구청→당산 | 예상21분 | 예상13분 | 2호선 환승·승차는 모델 |
| 군자→아차산 | 예상8분 | 예상9분 | 승차 소요는 역간 모델 |

접근2분·퇴장2분과 장소 좌표는 통제 입력입니다. 그 장소에서 해당 역까지 실제 걸어서2분임을 확인한 자료가 아닙니다. 첫 승차의 공급자 생성시각+ETA로부터 양평11:47:14·군자11:48:14의 도착 예측을 얻고, 분 단위 제품 계산에서는11:48·11:49에 승차합니다. 이후 승차 소요와 환승은 보유 노선·시간표 모델로 계산합니다. 양평 경로의 후속2호선 모델 승차는12:01→11:53으로 다시 계산됐습니다. 경로별 시간표 대조는 실제 조회 완료시각에 맞췄고 입력·자료판·마감시각을 유지했습니다. 이21→13·8→9분은 계산 결과의 변화이며 실제 오차가 줄었다는 측정이 아닙니다.

첫 번째 양평 스냅샷에서 접근0/2분은 마천 방향 열차를 선택했고6분이면 그 열차를 제외하고 하남검단산 방향 뒤 열차를 선택했습니다. 군자는 접근6분 뒤에는 제공된 열차 중 탈 수 있는 예측이 없어 no_boardable_prediction이었습니다. 이를 무운행/조회 실패로 바꾸지 않았습니다. 실제 문맥의 접근 시간 대신 이 통제6분 결과를 제품 소요로 사용하지 않았습니다.

## 병기 역명 수정의 실응답 대조

같은11:43:28 응답·공식 역 번호·정적 노선으로 앞 판 수정 전 클래스를 사본에서 적재해 비교했습니다. 양평의 해당 방향 실제2행은 긴 종착 경로의 군자 등 표기 공백 때문에0개 연결됐고, 수정 후2개가 연결됐습니다. 군자는 승차역 자체가 미대응이어서0개였고 수정 후 해당 방향2개가 연결됐습니다. 두 역에서0/4→4/4의 식별 연결 확인입니다. 분모4는 실제 응답에서 현재/다음/종착ID·일반열차 방향이 맞는4행이며 전체30행의 정확도 분모가 아닙니다. 각 방향의 종착ID는 하남검단산1005000558·마천1005080555였습니다. 다른 호선/반대 방향을 넣지 않았습니다.

신규 코드 변경은 하지 않았습니다. 앞 판 관련 시험197/197은11:37판의 기존 실행 결과이며 이번에 다시 실행한 수가 아닙니다. 코드·시험·데이터254개가 그대로임을 다시 대조했고, 새 실응답 원문4/4해시·행수4/4·실제 제품 연결2/2·저장 관측 재생4/4를 별도 검사했습니다. 실제 ETA·탑승·결제 오차 표본은0개입니다.

mock 서버 시험(화면 반응): 안 했음.

실서버 확인(서버 응답): 서울시 지하철 도착HTTP4회·모두정상, 그중2회는 엔진 출발 관측기→실제 소스 호출입니다. cs 프로젝트 서버·로컬 개발 서버 HTTP, 일정 저장·고객 알림 배달은 이번에 확인하지 않았습니다. 커밋·푸시·배포·외부 메시지·결제는 하지 않았습니다.

## 남은 작업과 보존

전체21개는 조건부 사용4·개선 필요9·추가 검증8로 유지합니다. 이제 병기 역명 승차역의 실제 소스 조회와 두 제품 계산 연결은 확인했습니다. 남은180개 표기 대응·급행/순환선·현재 탑승/위치 갱신·운행 시간대 반복·소스 장애 시 대체·후속 환승의 미래 예측 정확도·1.2km안의 새 정렬 웹 표본·실탑승/결제·cs 프로젝트 서버HTTP 연결과 배포 증거는 남습니다. 보관30초/공급시각90초/미래2초는 신선도 정책이고 실제 ETA 오차 허용치를 검증한 수치가 아닙니다.

- [시각화v41·21기능](assets/{assets.name}/mobility-readiness.html) — 실제/모델 경계와 계산 변화, 기능별 기존 비교·남은 검증.
- [새 실행 근거](../evidence/{ev.name}/) — 실응답 수집·제품 계산·동일 응답 재생·원문/코드 해시.
- [원문·수집시각](../../../.. /../datasets/mobility/raw/{rawdir.name}/) — 실제 응답4개와 정규화·수집정보. 상대 경로는 아래 정본 자료에서 확인할 수 있습니다.
- [백업 명세](../evidence/{ev.name}/backup-manifest-v1.json) — 기존 이동 정본·자료 설명의 수정 직전 사본.

앞 판 산출물과 원문은 덮어쓰지 않았습니다. 보고 파일명은 생성시각{created.isoformat()}에서 정했습니다.
'''
# 저장소 문서의 실제 데이터 경로까지 상대 링크를 계산한다.
import os
reporttext=reporttext.replace(f'../../../.. /../datasets/mobility/raw/{rawdir.name}/',Path(os.path.relpath(rawdir,report.parent)).as_posix()+'/').replace('상대 경로는 아래 정본 자료에서 확인할 수 있습니다.','')
with report.open('x',encoding='utf8') as f:f.write(reporttext)
with debug.open('x',encoding='utf8') as f:f.write(f'''# 공개 지하철 sample 오류와 실제 키 가용성 구분

공개 sample 양평·군자 ERROR-336은 제공처 오류 원문을 보존하고 원인을 미확정으로 남겼습니다. 기존 전용 인증키를 사용하는 제품 소스로는 같은 이름 두 역×두 시각4/4HTTP정상·30행을 확보했고 출발 계산2/2와 실제 종착 방향4/4ID연결을 확인했습니다. 앞 판 병기 이름 수정 전에는 해당 방향4행0개 연결입니다. 제품 비교21→13·8→9분은 통제 접근 입력의 모델 변화이며 실탑승 정확도 아님. [검증 보고서](../{report.name})에 시각·분모·실제/재생 구분을 기록합니다. 공개 예제 내부 원인·전체 운행 가용성·실제 ETA 오차는 미확정입니다.
''')
wiki=CS/'wiki/teams/mobility.md';wiki.write_text(wiki.read_text(encoding='utf8')+f'''\n\n## {stamp} 지하철 실제 인증키의 현재 출발·환승 연결 검증

기존 전용 키로 양평·군자 두 역×두 시각4/4HTTP정상·30행을 확보했고 출발 관측기→실제 소스→현재 첫 승차/뒤쪽 환승 모델2/2연결을 확인했습니다. 통제 접근2분에서 양평→영등포구청→당산21→13분·군자→아차산8→9분 예상 재계산, 같은 저장 관측 재생4/4. 병기 이름 수정 전에는 같은 실응답의 해당 방향4행0개, 현재4개 연결입니다. [보고서](../records/reports/{report.name})·[시각화v41](../records/reports/assets/{assets.name}/mobility-readiness.html). 공개 sample 오류와 실제 키 동작을 구분했으며 sample 내부 원인은 미확정입니다. 실제 ETA오차/탑승0·장소/접근/퇴장 통제·미래환승모델·cs 프로젝트 서버HTTP/배달/배포 미확인. 코드/시험/데이터254해시 유지·지도개발자API0·전체21판단4/9/8유지.
''',encoding='utf8')
dreport=ROOT/'datasets/mobility/REPORT.md';dreport.write_text(dreport.read_text(encoding='utf8')+f'''\n\n## {stamp} 실제 지하철 전용 인증키 응답4개

[실제 응답·수집정보](raw/{rawdir.name}/)는 서울시OA-12764·공공누리제1유형(출처 서울특별시)입니다. 두 역(양평·군자(능동))을11:43:28/11:44:49에 기존 전용키0/20범위로 실제 조회해4/4HTTP200 INFO-000, 각7/8행으로총30행을 보존했습니다. 네 원문은 제공total과행수일치·키반사없음 검사, 키/인증URL은 저장하지 않았습니다. 초기2조회는제품소스정규화,후속2조회는제품출발관측기→실제소스호출입니다. 공개sample재생아님. 문맥좌표/접근2분/퇴장2분은통제이며21→13·8→9분은모델계산변화,실제ETA정확도/독립웹경로/탑승/결제0개입니다. 같은저장관측4회재생은새표본아님. 지도개발자API0회·서울시무료도착API4회. [보고서](../../final_project_cs/wiki/records/reports/{report.name})와해시검증근거를잇습니다. 원문/정규화는git제외인자료이며운영적재물아닙니다.
''',encoding='utf8')
style=re.search(r'<style>(.*?)</style>',(prior/'mobility-readiness.html').read_text(encoding='utf8'),re.S).group(1)
cards=''.join(f'<article data-status="{html.escape(x["status"])}"><span class="status">{html.escape(x["status"])}</span><h3>{html.escape(x["name"])}</h3><p>{html.escape(x["scope"])}</p><p><b>기존 비교 수치</b> {html.escape(x["metric"])}</p><details><summary>판단 근거와 필요한 검증</summary><p>{html.escape(x["reason"])}</p><p>{html.escape(x["need"])}</p></details></article>' for x in catalog['features'])
flow='''<svg viewBox="0 0 840 210" role="img" aria-label="서울시 실제 첫 열차 응답으로 첫 승차시각을 계산하고 이후 구간과 환승은 시간표 모델로 재계산" style="width:100%;min-width:650px;background:white;border:1px solid #d6dce5"><g fill="none" stroke="#354052"><rect x="20" y="30" width="220" height="135"/><rect x="310" y="30" width="220" height="135"/><rect x="600" y="30" width="220" height="135"/><path d="M240 97h70m220 0h70"/></g><g fill="#161c28" font-family="sans-serif" font-size="17" text-anchor="middle"><text x="130" y="65">서울시 실제 응답</text><text x="130" y="94">생성시각 + ETA</text><text x="130" y="130">4조회·30행</text><text x="420" y="65">현재 첫 승차</text><text x="420" y="94">접근 이후 열차 선택</text><text x="420" y="130">11:48 / 11:49</text><text x="710" y="65">승차 이후·환승</text><text x="710" y="94">노선·시간표 모델</text><text x="710" y="130">실시간 예측 아님</text></g></svg>'''
visual=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 검증v41 — 실제 지하철 도착의 출발·환승 연결</title><style>{style}</style><main>
<p>서울 이동 검증 · v41 · {created.isoformat()}</p><h1>실제 도착정보가<br>출발·환승 계산까지 이어집니다.</h1><p class="lead">양평·군자에서 기존 전용 인증키로 실제 응답을 받았습니다. 현재 첫 승차는 공급자 예측을 쓰고, 승차 소요·뒤쪽 환승은 모델로 다시 계산합니다. 실제 탑승 정확도는 아직 측정하지 않았습니다.</p>
<section class="metrics"><p><b>4/4 정상 ·30행</b>두 역×두 시각 실제 HTTP</p><p><b>2/2 연결</b>통제 접근의 제품 계산</p><p><b>0→4/4행</b>같은 실응답의 종착 식별 연결</p></section>
<h2>실제 값과 모델의 경계</h2><div class="scroll">{flow}</div><p>장소 좌표·접근2분·퇴장2분은 통제 입력입니다. 실제 걸어서2분이나 탑승 성공을 관측한 것이 아닙니다.</p>
<h2>같은 조회 완료시각에서 다시 계산한 예상 시간</h2><div class="scroll"><table><thead><tr><th>경로</th><th>시간표 모델</th><th>첫 승차 예측 반영</th><th>후속 계산</th></tr></thead><tbody><tr><td>양평→영등포구청→당산</td><td>21분</td><td>13분</td><td>2호선 승차12:01→11:53</td></tr><tr><td>군자→아차산</td><td>8분</td><td>9분</td><td>역간 승차시간 모델</td></tr></tbody></table></div><p>시각2026-10-09 11:44:49대. 계산 변화이며 실제 오차 감소 측정은 아닙니다. 동일 저장 관측을 경로별2회 재생해4/4일치했습니다.</p>
<h2>공개 예제 오류와 실제 키 구분</h2><p>앞 판 sample 양평·군자 ERROR-336과 달리 실제 키0/20은4/4정상이었습니다. sample 제공처 내부 원인은 미확정입니다. 첫 승차 양평2행·군자2행의 하남검단산/마천 종착ID는 수정 전0/4→수정 후4/4로 연결됩니다. 전체30행의 정확도 비율로 쓰지 않습니다.</p><p>원문 행수=제공total4/4, 코드·시험·데이터254해시 유지. 지도 개발자API0회·실제 ETA오차/탑승/결제0개·새 독립 웹 경로0개. 이번 코드 변경과197시험 재실행은 하지 않았습니다.</p>
<h2>전체21개 기능의 판단</h2><p>조건부 사용4 · 개선 필요9 · 추가 검증8을 유지합니다. 나머지 카드의 기존 비교 수치를 이번에 재측정하지 않았습니다. 급행/순환선·180역명 대응·1.2km안의 새 정렬 웹 표본·실제 탑승 오차·장애 대체·cs 프로젝트 서버 HTTP/알림 배달/배포 확인은 남습니다.</p><label for="filter">판단별 보기</label><select id="filter"><option value="all">전체21개</option><option>조건부 사용</option><option>개선 필요</option><option>추가 검증</option></select><section class="grid">{cards}</section>
<footer><a href="../../{report.name}">검증 보고서</a> · <a href="../../../evidence/{ev.name}/real-key-verification-v1.json">검증 원문</a> · <a href="../../../evidence/{ev.name}/backup-manifest-v1.json">백업 명세</a> · <a href="../{prior.name}/mobility-readiness.html">이전 판v40</a><p>출처: 서울특별시 OA-12764 · 공공누리 제1유형. 확인은 엔진 출발 경로와 서울시 실제 응답까지이며 일정 저장·고객 알림 전송·배포는 이번 범위에서 하지 않았습니다.</p></footer></main><script>document.querySelector('#filter').addEventListener('change',e=>{{document.querySelectorAll('article').forEach(a=>{{a.hidden=e.target.value!=='all'&&a.dataset.status!==e.target.value;}});}});</script></html>'''
with (assets/'mobility-readiness.html').open('x',encoding='utf8') as f:f.write(visual)
for name in ['collect_subway_real_key_v1.py','audit_subway_real_key_product_v1.py','verify_subway_real_key_v1.py',Path(__file__).name]:
 shutil.copy2(Path(__file__).parent/name,ev/name)
save(ev/'research-v1.json',{'checked_at':created.isoformat(),'source':'https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A','fields_used':['statnId','statnTid','bstatnId','btrainNo','btrainSttus','barvlDt','recptnDt','arvlCd'],'sample_max_rows':5,'error_336_doc_max_rows':1000,'inference':'실제 키에서 동일 역·조회명 정상. 공개 sample 내부 오류 원인은 확정하지 않음.','new_paper_algorithm_applied':False})
save(ev/'publication-state-v1.json',{'created_at':created.isoformat(),'report':report.relative_to(ROOT).as_posix(),'assets':assets.relative_to(ROOT).as_posix(),'evidence':ev.relative_to(ROOT).as_posix(),'source_code_changed':False,'tests_reexecuted':False,'prior_test_count':197,'previous_tests_timestamp':'2026-10-09 11:37 KST','full_feature_completion':False})
allpaths=[report,debug,wiki,dreport,*assets.iterdir(),*ev.iterdir(),*rawdir.iterdir()];hashes={p.relative_to(ROOT).as_posix():sha(p) for p in allpaths if p.is_file()}
save(ev/'publication-validation-v1.json',{'created_at':created.isoformat(),'source_test_data_hashes':source_hashes,'artifact_hashes':hashes,'backup_hash_matches':len(backups),'browser_render_checked':False,'syntax_links_check_pending':True})
print(json.dumps({'report':report.relative_to(ROOT).as_posix(),'assets':assets.relative_to(ROOT).as_posix(),'hashes':len(hashes),'backups':len(backups),'features':len(catalog['features'])},ensure_ascii=False))