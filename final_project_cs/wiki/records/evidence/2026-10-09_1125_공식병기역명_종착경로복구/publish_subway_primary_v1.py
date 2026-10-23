from pathlib import Path
from datetime import datetime
from collections import Counter
import difflib
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
scratch = Path(__file__).parent
state = json.loads((scratch / 'subway-primary-work-v2.json').read_text(encoding='utf8'))
ev = cs / 'wiki/records/evidence' / state['tag']
now = datetime.now().astimezone()
stamp = now.strftime('%Y-%m-%d_%H%M')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def save(p, value):
    with p.open('x', encoding='utf8') as f: json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)

def backup(p, purpose):
    dst = p.parent / '_backup' / (stamp + '_' + purpose) / p.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    assert not dst.exists()
    shutil.copy2(p, dst)
    state['backups'].append({'source': p.relative_to(root).as_posix(), 'backup': dst.relative_to(root).as_posix(), 'sha256': sha(p)})

before = ET.parse(ev / 'before-v1.xml').getroot()
after = ET.parse(ev / 'after-v1.xml').getroot()
assert len(before.findall('.//testcase')) == 25 and len(before.findall('.//failure')) == 10
assert len(after.findall('.//testcase')) == 197 and not after.findall('.//failure') and not after.findall('.//error')
assert len([x for x in after.findall('.//testcase') if x.attrib['classname'].endswith('test_subway_primary_name_v1')]) == 25
audit = json.loads((ev / 'native-primary-audit-v1.json').read_text(encoding='utf8'))
assert (audit['before_matches'], audit['after_matches'], audit['remaining']) == (587, 613, 180)
assert (audit['old_service_patterns'], audit['new_service_patterns']) == (21, 43)
assert len(audit['controlled_runs']) == 4 and audit['line5_names_after_missing'] == 0
all_http = []
for p in ('public-retry-v1.json', 'public-retry-v2.json', 'public-control-v3.json'):
    all_http += json.loads((ev / p).read_text(encoding='utf8'))['requests']
assert len(all_http) == 6
normal = [x for x in all_http if x['normalized_rows'] is not None]
assert len(normal) == 1 and normal[0]['normalized_rows'] == 5 and normal[0]['provider_total'] == 22
actual_codes = []
for x in all_http:
    raw = json.loads((root / x['raw_path']).read_text(encoding='utf8'))
    actual_codes.append({'station': x['station'], 'raw_path': x['raw_path'], 'http_status': x['http_status'], 'code': raw.get('errorMessage', raw).get('code')})
save(ev / 'public-response-summary-v1.json', {'created_at': now.isoformat(), 'http_responses': actual_codes, 'http_count': 6, 'normal_snapshots': 1, 'normal_rows': 5, 'provider_total': 22, 'preconnection_failures': 2, 'metadata_note': '最初 retry v1의 response_code=null은 검사 스크립트가 top-level code를 놓친 것. 원문을 고치지 않고 여기서 재대조했다.'.replace('最初', '첫'), 'claim': 'HTTP200 자체는 정상 자료가 아니다. 오류5개를 운행 없음 또는 정상 표본으로 세지 않음.'})
owned = ['app/domains/travel_ops/instances/mobility/engine/subway_identity.py', 'tests/unit/travel/mobility/test_subway_primary_name_v1.py']
cmd = [sys.executable, '-m', 'ruff', 'check', *owned]
lint = subprocess.run(cmd, cwd=cs, capture_output=True, text=True, encoding='utf8')
with (ev / 'ruff-v1.log').open('x', encoding='utf8') as f: f.write(lint.stdout + lint.stderr)
save(ev / 'ruff-v1.run.json', {'command': cmd, 'exit_code': lint.returncode})
assert lint.returncode == 0, lint.stdout
hashes = dict(state['prior_source_test_data_hashes'])
owned_full = {'final_project_cs/' + p for p in owned}
for rel, value in hashes.items():
    if rel not in owned_full: assert sha(root / rel) == value, rel
for rel in owned_full: hashes[rel] = sha(root / rel)
data_paths = [root / audit['processed_path'] / 'station-crosswalk-v1.json']
for suffix in ('_public_sample', '_public_retry', '_public_retry_v2', '_public_control_v3'):
    data_paths += list((root / 'datasets/mobility/raw' / (state['tag'] + suffix)).glob('*.json'))
for p in data_paths: hashes[p.relative_to(root).as_posix()] = sha(p)
original = root / next(x['backup'] for x in state['backups'] if x['source'].endswith('/subway_identity.py'))
with (ev / 'owned-source-diff-v1.patch').open('x', encoding='utf8') as f:
    f.writelines(difflib.unified_diff(original.read_text(encoding='utf8').splitlines(True), (cs / owned[0]).read_text(encoding='utf8').splitlines(True), fromfile='before/' + owned[0], tofile='after/' + owned[0]))
save(ev / 'research-v1.json', {'checked_at': now.isoformat(), 'sources': [
    {'url': 'https://mediahub.seoul.go.kr/archives/2001681', 'scope': '서울시 2021-05-20 공식 안내의 주역명 옆/밑 괄호 부역명 설명, 1~8호선 범위'},
    {'url': 'https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do', 'scope': '기존 원문2026-09-02 실제 병기 이름/공식ID와 조회 예외. 기존 XLSX/추출물 해시 유지'},
    {'url': 'https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A', 'scope': '현재/다음/종착역ID·일반열차와 sample 최대5행, 오류코드 정의'}], 'applied_assumptions': '공식1~8호선의 주역명(단일 괄호 부역명), 동일 노선 유일하며 정확 이름과 충돌하지 않는 것만 파생 대응. 다른 노선/역 접미사/유사도는 확장하지 않음.', 'paper_algorithm_applied': False, 'reason': '역 이름의 의미/식별 문제를 공식 원자료와 운영기관 설명으로 해결. 새로운 최적화·예측 알고리즘이나 논문 효과를 주장하지 않음.', 'new_map_web_routes': 0, 'map_developer_api_calls': 0, 'actual_boarding_payment': 0})

assets = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v40'
assets.mkdir(exist_ok=False)
prior = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v39'
catalog = json.loads((prior / 'readiness-catalog.json').read_text(encoding='utf8'))
catalog.update(created_at=now.isoformat(), scope='공식 병기 역명의 주역명 대응으로 실제 종착 경로 ID 연결 복구; 정적·통제 검증과 공개 샘플 구분', prior_catalog_sha256=sha(prior / 'readiness-catalog.json'))
for x in catalog['features']:
    if x['name'] in ('실시간 지하철·버스 도착', '지하철 경로 산출'):
        x['prior_need_v39'] = x['need']
        x['need'] = 'v40: 서울시 공식 주역명(괄호 부역명)을 유일한 동일 노선 대응으로 연결. 보유793역587→613대응(26추가), 미대응180보존. 양평→영등포구청 종착 식별조합21→43; 하남검단산/마천 통제4/4재계산. 신규25/25·관련197/197. 정상 공개서울역1응답/5행(total22), 양평/군자 샘플 오류5회는 운행 없음으로 처리하지 않음. 실제 병기 승차역 API 조회·급행/순환선·나머지180대응·서울역/서울·실탑승·새 웹 오차는 남음. 정적 조합43개를 실제43개 운행 경로로 세지 않음.'
        x['identity_basis_v40'] = '공식1~8호선 단일 괄호 표기의 주역명. 같은 노선 중복/정확 이름 충돌 시 자동 대응 제외; 공식 ID/조회명 원값 유지.'
assert len(catalog['features']) == 21 and dict(Counter(x['status'] for x in catalog['features'])) == catalog['counts']
save(assets / 'readiness-catalog.json', catalog)
report = cs / 'wiki/records/reports' / (stamp + '_공식병기역명_지하철종착경로_복구검증.md')
with report.open('x', encoding='utf8') as f:
    f.write(f'''# 공식 병기 역명 대응과 지하철 종착 경로 복구

괄호 부역명 때문에 빠지던 공식 역 번호 대응을 보강해 하남검단산·마천 방향의 현재 출발 재계산 경로를 복구했습니다. 공식1~8호선에서 같은 노선의 유일한 주역명만 대응하고 원래 조회명·역 번호를 유지합니다. 실제 탑승 정확도나 전체 완료 판정은 아닙니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 새 주역명·모호성·출발 연결 시험 | 통과 | 25/25 = 100% |
| 관련 회귀 시험 | 통과 | 197/197 = 100% |
| 보유 역 이름 대응 | 26개 추가 | 587/793 = 74.0% → 613/793 = 77.3% |
| 보유 두 종착 방향 통제 재계산 | 통과 | 4/4 = 100% |

25는 신규 통제 pytest 건수이고197에 포함됩니다. 보유793행은 기존 국가철도공단 등 역 좌표 목록이며 대응613개는 같은 실제 운행 응답을 확인한 수가 아닙니다. 통제4회는 두 종착 방향×동일 입력2회이고 독립 정확도 표본이 아닙니다. 작업 시작 시 직전 코드·시험·자료·산출물285/285해시를 대조했고 다른 작업 중인 채팅의 해당 코드 변경은 발견하지 않았습니다.

## 문제와 공식 근거

계획 자료에는 군자, 공식 도착 자료에는 군자(능동)가 있어 목적지 뒤쪽 역도 연결하지 못했고 긴 종착 경로 전체가 제외됐습니다. 5호선의 신정·오목교·군자·아차산·광나루·천호·굽은다리·올림픽공원8곳이 같은 원인이었습니다. [서울시 공식 역명병기 안내](https://mediahub.seoul.go.kr/archives/2001681)는 주역명 옆 또는 밑 괄호에 부역명을 추가한다고 설명합니다. [공식2026-09-02 역정보](https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do)의 원문 ID/이름을 그대로 사용하는 대응을 만들었습니다.

공식1~8호선의 단일 괄호 표기에서 주역명을 추출하되, 동일 노선에서 여러 역과 겹치거나 정확 이름과 다른 ID가 충돌하면 별칭을 만들지 않습니다. 정확 공식 이름은 먼저 찾습니다. 중첩/다중 괄호·빈 괄호·괄호 앞 공백, 역 접미사 추가/삭제·부분 문자열·유사도·부역명만 입력한 경우를 확장하지 않습니다. 9호선·철도기관 노선의 다른 표기는 이 근거 범위에서 자동 확장하지 않았습니다. 예: 군자 입력이 공식 군자(능동)의 원 ID/조회명으로 이어집니다. 서로 다른 군자(능동)·군자(다른곳)가 있으면 군자는 미대응으로 남깁니다.

자료 파일은 변경하지 않았으며 기존 내용 해시·조회명·공식ID를 유지했습니다. 런타임 lookup·첫 승차 문맥·종착 경로 생성이 같은 대응을 사용합니다. 이전 문맥에서 ID가 미대응이었다가 현재 대응되면 기존 비교가 재계산을 요구하며 조회를 실행하지 않습니다. 선택한 현재 열차가 바뀌면 앞 판의 요청별 판정기에서 실제 승차 구간 모델과 후속 환승을 재계산합니다.

## 전후 결과와 확인 범위

신규25건 중10건이 변경 전 실패했고15건은 이미 통과했습니다. 수정 후 신규25/25·관련197/197, Ruff2파일 통과입니다. 공식 자료에서 유일한 파생 주역명28개를 만들었고 보유 좌표의26개가 추가 대응했습니다. 대상 자료에서 충돌0개지만 충돌 입력 자체는 별도 통제 시험으로 제외 동작을 확인했습니다. 미대응180개 전체 목록을 보존했습니다. 이를 원천 제공 불가로 단정하지 않습니다. 서울역/서울, 신·구 역명, 기관별 표기, 노선 범위 차이는 별도 코드/운영기관 근거가 필요합니다.

보유5호선8개 표기 차이는8/8해소됐고 양평→영등포구청의 일반·비순환 종착 식별 조합은21→43개로 늘었습니다.43은 그래프에서 식별 가능하게 만든 종착 조합 수로, 실제43종 열차가 운행했다는 뜻이 아닙니다. 하남검단산·마천 각 방향의 통제 현재도착을11:09로 주어 첫 승차669분과 전체 구간 재계산을 각2회 확인했습니다. 공식 역/시간표/노선 자료를 사용했지만 열차번호·도착·접근6분/퇴장2분·장소 좌표는 통제 입력이며 웹·실탑승 독립 검증으로 세지 않습니다.

## 새 공개 응답과 실패 기록

로컬 환경2조회는 연결 전 ConnectError였고, 네트워크 허용 후6HTTP조회 중1건만 INFO-000 정상 자료입니다. 나머지5건은 ERROR-336을 받은 제공처 응답이며 정상0열차로 바꾸지 않았습니다. 양평·군자(능동)에0/5와1/5페이지로 조회했고 이전에 성공한 서울/0/5를 대조군으로 확인했습니다. 서울은2026-10-09T11:33:11.020247+09:00에 HTTP200·INFO-000, 전체22행 중5행을 받았습니다. 양평은 같은 시점 같은0/5범위에서 ERROR-336을 받았습니다. 이 확인만으로 실제 키를 사용하는 모든 역 조회가 불가하다고 말하지 않습니다. 개인 지하철 키로의 해당 역 조회, 제공처 샘플 제한/역 이름 처리 원인 확인은 아직 하지 않았습니다.

ERROR-336은 [공식 오류 명세](https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A)에서 요청 범위 설명을 주지만 실제 요청 차이는4~5이므로 원인을 문구 그대로 확정하지 않았습니다. 재시도1판의 수집 메타 response_code=null은 검증 스크립트가 최상위 code를 놓친 것이며 원문은 ERROR-336입니다. 원문을 수정하지 않고 후속 메타와 응답 요약에서 재대조했습니다. 입력 오류를 막는 본 소스가 body_error로 기록한 것도 보존했습니다.

새 정상 스냅샷1개5행과 오류 원문·수집 시각·해시를 보존했습니다. 공개원문은 실제 HTTP로 읽었고 정규화는 그 원문을 transport로 재생했습니다. 원문5행을 내부20행 조회의 완전 결과로 부르지 않습니다. 서울역의 새 응답은 두 복구 종착 방향의 실제 응답 검증이 아닙니다. 지도 개발자API0회·새 지도 웹 경로0개·실제 ETA오차/탑승/결제0개입니다.

mock 서버 시험(화면 반응): 안 했음.

실서버 확인(서버 응답): 서울시 공개 도착HTTP6회 확인, 정상1개/오류5개. cs 프로젝트 서버·로컬 개발 서버 HTTP와 고객 알림 전송은 안 했습니다. 커밋·푸시·배포·외부 메시지·결제는 하지 않았습니다.

## 남은 검증과 보존 자료

전체21개 판단은 조건부 사용4·개선 필요9·추가 검증8을 유지합니다. 병기 승차역의 실제 조회, 남은180개 이름/코드 대응, 급행/순환선, 탑승 후 위치 갱신, 1.2km이내 새 웹 대조와 실제 ETA/결제 검증은 남습니다. 이번 문제는 공식 명칭의 식별 문제로 해결했으며 새로운 논문 알고리즘을 적용하거나 정확도 효과를 주장하지 않습니다.

- [시각화v40·21기능](assets/{assets.name}/mobility-readiness.html) — 주역명 대응과 종착 복구·기능별 기존 수치.
- [검증 원문](../evidence/{state['tag']}/) — 전후 시험·보유 노선·공개 응답 검사·해시.
- [백업 명세](../evidence/{state['tag']}/backup-manifest-v1.json) — 수정 직전 코드·시험·문서 사본.
- [결함 기록](debugs/{state['tag']}.md) — 병기 이름 문제의 부분 해결과 미검증 범위.

시각화21카드·파일 링크·JavaScript 구문은 검사했으며 브라우저 렌더링은 확인하지 않았습니다. 저장된 원래 공식 파일과 앞 판 산출물을 덮어쓰지 않았습니다. v11 이동관리 한 개선 단위로 DoD 전체 판정이 아닙니다.
''')

style = re.search(r'<style>(.*?)</style>', (prior / 'mobility-readiness.html').read_text(encoding='utf8'), re.S).group(1)
cards = ''.join(f'<article data-status="{html.escape(x["status"])}"><span class="status">{html.escape(x["status"])}</span><h3>{html.escape(x["name"])}</h3><p>{html.escape(x["scope"])}</p><p><b>기존 비교 수치</b> {html.escape(x["metric"])}</p><details><summary>판단 근거와 필요한 검증</summary><p>{html.escape(x["reason"])}</p><p>{html.escape(x["need"])}</p></details></article>' for x in catalog['features'])
page = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 검증v40 — 병기 역명과 종착 복구</title><style>{style}</style><main>
<p>서울 이동 검증 · v40 · {now.isoformat()}</p><h1>역 이름 표기 차이를 풀어<br>빠진 종착 경로를 복구했습니다.</h1><p class="lead">공식 주역명과 괄호 부역명을 같은 노선의 유일한 역ID로 대응합니다. 원래 이름·조회명·ID는 유지하며 모호한 이름은 자동 연결하지 않습니다.</p>
<section class="metrics"><p><b>587→613 /793</b>보유 역 이름 대응</p><p><b>21→43개</b>종착 식별 조합</p><p><b>25/25 ·197/197</b>신규·관련 통제 시험</p></section>
<h2>표기 차이가 경로를 끊던 원인</h2><div class="scroll"><svg viewBox="0 0 780 170" role="img" aria-label="계획 이름 군자를 공식 이름 군자(능동)의 원래 역 번호로 대응하여 하남검단산과 마천 종착 경로를 복구" style="min-width:600px;width:100%;background:#fff;border:1px solid #ddd"><g stroke="#354052" fill="none"><rect x="20" y="40" width="200" height="80"/><rect x="290" y="40" width="200" height="80"/><rect x="560" y="40" width="200" height="80"/><path d="M220 80h70m200 0h70"/></g><g font-family="sans-serif" font-size="17" fill="#161c28" text-anchor="middle"><text x="120" y="72">계획 이름 ‘군자’</text><text x="120" y="99">같은5호선</text><text x="390" y="72">공식 ‘군자(능동)’</text><text x="390" y="99">원래ID·조회명 유지</text><text x="660" y="72">하남검단산 / 마천</text><text x="660" y="99">현재 승차 재계산 연결</text></g></svg></div>
<p>두 종착 방향×통제2회 =4/4동일 결과. 이 그림과43개 조합은 실제 열차 운행/ETA오차 측정이 아닙니다.</p>
<h2>실제 확보한 것과 남은 것</h2><p>새 서울역 공개 정상 응답1개·5행(total22). 실제 HTTP6회 중5회는 양평/군자의 ERROR-336이며 운행 없음으로 바꾸지 않았습니다. 개인 키의 해당 역 실제 조회·실제 탑승은 미확인입니다.</p><p>1~8호선 병기 주역명26개 추가 대응·180개 미대응 목록 보존. 서울역/서울, 기관별 표기, 급행/순환선과1.2km내 새 웹 대조는 남습니다. 기존 비교 수치를 이번에 다시 측정하지 않았습니다.</p>
<h2>전체21개 기능의 판단</h2><p>조건부 사용4 · 개선 필요9 · 추가 검증8. 배포하지 않았으며 전체 완료 판정을 올리지 않았습니다.</p><label for="filter">판단별 보기</label><select id="filter"><option value="all">전체21개</option><option>조건부 사용</option><option>개선 필요</option><option>추가 검증</option></select><section class="grid">{cards}</section><footer><a href="../../{report.name}">검증 보고서 열기</a> · <a href="readiness-catalog.json">판단 원본 열기</a><p>원문·코드·백업 해시 보존. 브라우저 렌더링 미확인.</p></footer></main><script>document.getElementById('filter').addEventListener('change',function(){{document.querySelectorAll('article').forEach(x=>{{x.hidden=this.value!=='all'&&x.dataset.status!==this.value}})}})</script></html>'''
with (assets / 'mobility-readiness.html').open('x', encoding='utf8') as f: f.write(page)
debug = cs / 'wiki/records/reports/debugs' / (state['tag'] + '.md')
backup(debug, '병기역명_검증결과')
debug.write_text(debug.read_text(encoding='utf8').replace('## 미해결', '## 부분 해결 — 공식1~8호선 유일한 주역명 대응', 1) + f'\n\n신규25/25·관련197/197, 대응587→613/793,5호선8/8·종착21→43개·두종착 통제4/4. 실제 해당역 도착API는 sample ERROR-336이라 미확인이고 서울역1개5행 정상 수집을 따로 보존했습니다. 남은180개·급행/순환선·실탑승은 남습니다. [보고서](../{report.name}).\n', encoding='utf8')
wiki = cs / 'wiki/teams/mobility.md'
backup(wiki, '병기역명_검증결과')
with wiki.open('a', encoding='utf8') as f:
    f.write(f'\n\n## {stamp} 공식 병기 주역명과 종착 경로 복구 검증\n\n공식1~8호선 단일 괄호의 유일한 주역명 대응으로 보유 역587→613/793(26추가·180미대응보존),5호선8/8표기해소·양평→영등포구청 종착 식별조합21→43개·하남검단산/마천 통제4/4재계산을 확인했습니다. 신규25/25·관련197/197. [보고서](../records/reports/{report.name})·[시각화v40](../records/reports/assets/{assets.name}/mobility-readiness.html). 원ID/조회명/파일해시 유지·모호성 제외. 공개실HTTP6회중서울역1개5행정상(total22),양평/군자ERROR-3365회는 운행없음으로 처리하지 않음. 병기승차역 실제API/180개 대응/급행·순환선/실탑승·새웹은남음·21판단4/9/8 유지·배포없음.\n')
data_report = root / 'datasets/mobility/REPORT.md'
backup(data_report, '병기역명_자료기록')
with data_report.open('a', encoding='utf8') as f:
    f.write(f'\n\n## {stamp} 공식 병기 주역명 대응 감사와 공개 샘플\n\n[대응 감사](processed/{Path(audit["processed_path"]).name}/station-crosswalk-v1.json)는 기존 공식696역·좌표793행의 원자료 해시를 유지하며587→613대응과180미대응 목록·26추가를 기록합니다. 공식1~8호선 유일한 주역명(단일 괄호 부역명)만 대응하며 이 감사 파일은 운영 적재물이 아닙니다. [공개응답 대조](raw/{state["tag"]}_public_control_v3/)에는서울역2026-10-09T11:33:11.020247+09:00 HTTP200 INFO-0005행(total22)과양평ERROR-336원문을 보존했습니다. _public_sample 연결실패2회·_public_retry/_public_retry_v2 오류원문4회도 같은 접두 새 폴더로 보존했습니다. 정규화는 실제원문transport재생이며5행을완전응답으로부르지않습니다. 출처서울특별시OA-12764·공공누리제1유형. 지도개발자API/실탑승0. [검증 보고서](../../final_project_cs/wiki/records/reports/{report.name}).\n')
save(ev / 'backup-manifest-v1.json', {'created_at': now.isoformat(), 'backups': state['backups']})
save(ev / 'verification-proof-v1.json', {'created_at': now.isoformat(), 'source_test_data_hashes': hashes, 'new_tests': {'passed': 25, 'total': 25}, 'related_tests': {'passed': 197, 'total': 197}, 'before': {'failed': 10, 'passed': 15, 'total': 25}, 'static_station_matches': {'before': 587, 'after': 613, 'total': 793, 'unmapped': 180}, 'static_service_patterns': {'before': 21, 'after': 43}, 'controlled_native_runs': 4, 'http_requests': 6, 'preconnection_failures': 2, 'normal_snapshots': 1, 'normal_rows': 5, 'normal_total': 22, 'actual_boarding_payment': 0, 'map_developer_api_calls': 0, 'new_map_web_routes': 0, 'features': 21, 'counts': catalog['counts'], 'deployed': False, 'browser_render_verified': False})
for pattern in ('*subway_primary_v*.py', '*subway-primary-work-v*.json'):
    for p in scratch.glob(pattern): shutil.copy2(p, ev / p.name)
links = []
for doc in (report, assets / 'mobility-readiness.html'):
    t = doc.read_text(encoding='utf8')
    hrefs = re.findall(r'\]\(([^)]+)\)', t) if doc.suffix == '.md' else re.findall(r'href="([^"]+)"', t)
    for href in hrefs:
        if href.startswith(('http://', 'https://', '#')): continue
        p = (doc.parent / href).resolve(); assert p.exists(), href; links.append(p.relative_to(root).as_posix())
for rel, value in hashes.items(): assert sha(root / rel) == value, rel
for x in state['backups']: assert sha(root / x['backup']) == x['sha256']
assert page.count('<article ') == 21
js = scratch / 'subway-primary-visual-script-v1.js'
with js.open('x', encoding='utf8') as f: f.write('\n'.join(re.findall(r'<script>(.*?)</script>', page, re.S)))
node = 'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1007-641-0_26.1007.641.0_x64__3k8sg7r9htsxt/dependencies/node/bin/node.exe'
syntax = subprocess.run([node, '--check', str(js)], capture_output=True, text=True, encoding='utf8')
with (ev / 'visual-script-syntax-v1.log').open('x', encoding='utf8') as f: f.write(syntax.stdout + syntax.stderr)
assert syntax.returncode == 0, syntax.stderr
artifacts = [report, assets / 'mobility-readiness.html', assets / 'readiness-catalog.json', wiki, debug, data_report]
artifacts += list(ev.glob('*'))
save(ev / 'publication-validation-v1.json', {'source_hash_matches': len(hashes), 'backup_hash_matches': len(state['backups']), 'artifact_hashes': {p.relative_to(root).as_posix(): sha(p) for p in artifacts if p.is_file()}, 'local_links': links, 'visual_cards': 21, 'syntax_exit_code': syntax.returncode, 'browser_render_verified': False})
print(json.dumps({'report': str(report), 'assets': str(assets), 'source_hashes': len(hashes), 'backups': len(state['backups']), 'new_tests': 25, 'related_tests': 197}, ensure_ascii=False))
