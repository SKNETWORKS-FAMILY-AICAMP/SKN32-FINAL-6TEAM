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
state = json.loads((scratch / 'subway-departure-work-v9.json').read_text(encoding='utf8'))
ev = cs / 'wiki/records/evidence' / state['tag']
now = datetime.now().astimezone()
stamp = now.strftime('%Y-%m-%d_%H%M')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def save(p, value):
    with p.open('x', encoding='utf8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)

def backup(p, why):
    dest = p.parent / '_backup' / (stamp + '_' + why) / p.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    assert not dest.exists()
    shutil.copy2(p, dest)
    state['backups'].append({'source': p.relative_to(root).as_posix(), 'backup': dest.relative_to(root).as_posix(), 'sha256': sha(p)})

after = ET.parse(ev / 'after-v7.xml').getroot()
extra = ET.parse(ev / 'supplemental-v1.xml').getroot()
assert len(after.findall('.//testcase')) == 201 and not after.findall('.//failure') and not after.findall('.//error')
assert len(extra.findall('.//testcase')) == 61 and not extra.findall('.//failure') and not extra.findall('.//error')
new = len([x for x in after.findall('.//testcase') if x.attrib['classname'].endswith('test_subway_departure_v1')])
assert new == 33
native = json.loads((ev / 'native-route-controlled-v2.json').read_text(encoding='utf8'))
assert len(native['controlled_runs']) == 2 and native['controlled_runs'][0] == native['controlled_runs'][1]
assert native['baseline']['eta_min'] == 12 and native['controlled_runs'][0]['eta_min'] == 13
owned = [p for p in state['owned'] if not p.startswith('wiki/')]
owned += ['app/domains/travel_ops/instances/mobility/engine/subway_departure.py', 'tests/unit/travel/mobility/test_subway_departure_v1.py']
lint_cmd = [sys.executable, '-m', 'ruff', 'check', *[p for p in owned if p.endswith('.py')]]
lint = subprocess.run(lint_cmd, cwd=cs, capture_output=True, text=True, encoding='utf8')
with (ev / 'ruff-v1.log').open('x', encoding='utf8') as f: f.write(lint.stdout + lint.stderr)
save(ev / 'ruff-v1.run.json', {'command': lint_cmd, 'exit_code': lint.returncode})
assert lint.returncode == 0, lint.stdout
hashes = dict(state['prior_source_test_data_hashes'])
owned_full = {'final_project_cs/' + p for p in owned}
for rel, value in hashes.items():
    if rel not in owned_full: assert sha(root / rel) == value, rel
for rel in owned_full: hashes[rel] = sha(root / rel)
diffs = []
for rel in owned:
    full = 'final_project_cs/' + rel
    originals = [x for x in state['backups'] if x['source'] == full]
    before = (root / originals[0]['backup']).read_text(encoding='utf8').splitlines(True) if originals else []
    diffs += difflib.unified_diff(before, (cs / rel).read_text(encoding='utf8').splitlines(True), fromfile='before/' + rel, tofile='after/' + rel)
with (ev / 'owned-source-diff-v1.patch').open('x', encoding='utf8') as f: f.writelines(diffs)
save(ev / 'research-v1.json', {'checked_at': now.isoformat(), 'sources': [
    {'url': 'https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A', 'use': '公式 필드: 현재역·다음역·종착역ID, 일반열차 종류, 생성시각과 초단위 ETA'.replace('公式', '공식')},
    {'url': 'https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do', 'use': '2026-09-02 공식 역정보와 명시적 역 조회명 예외; 전체 역명 별칭을 추정하지 않음'},
    {'url': 'https://arxiv.org/abs/2505.14193', 'use': '2025 동적 재계획 초록/서지: 현재 스냅샷은 미래 지연을 알지 못함. 이번 재계산은 기존 구간열 재검증이며 논문의 push 시스템 구현/효과 재현 아님'},
    {'url': 'https://arxiv.org/abs/2605.18778', 'use': '2026 T-REX 초록/서지: trip/transfer와 시간표 업데이트 전제. 현재 ID-열차운행표 대응이 불완전하여 알고리즘 이식/속도 주장 보류'}],
    'paper_read_scope': '제목·초록·서지와 공개일. 논문 본문 알고리즘을 구현하거나 그 성능을 차용하지 않음',
    'new_web_route_samples': 0, 'map_developer_api_calls': 0, 'new_live_arrival_snapshots': 0, 'actual_boarding_payment': 0})

assets = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v39'
assets.mkdir(exist_ok=False)
prior = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v38'
catalog = json.loads((prior / 'readiness-catalog.json').read_text(encoding='utf8'))
catalog.update(created_at=now.isoformat(), scope='일반 비순환 첫 지하철 승차의 현재 도착 예측→후속 구간/환승 모델 재계산→출발 안내 연결', prior_catalog_sha256=sha(prior / 'readiness-catalog.json'))
for item in catalog['features']:
    if item['name'] in ('실시간 지하철·버스 도착', '지하철 경로 산출'):
        item['prior_need_v38'] = item['need']
        item['need'] = 'v39: 일반 비순환 첫 지하철 승차는 공식 ID 경로 생성→현재 접근 이후 도착→역간 소요→후속 환승→안내에 연결. 신규33/33·관련201/201·추가61/61 통제 회귀. 보유 양평→영등포구청 경로에서 통제 도착을 10:08→10:09로 바꾸면 전체 모델12→13분, 2회 동일. 실제 ETA 오차·실탑승 아님. 공식 이름/코드206개 미대응과 목적지 이후 역ID 공백이 실제 종착 조합을 제외하는 문제, 급행/순환선, 탑승 이후 위치 갱신, 새 웹·현장 표본은 남음. 기존 카카오·네이버 수치를 이번에 재측정하지 않음.'
        item['product_path_v39'] = 'composition → mobility departure hook → observer → Runtime/Verifier → trip_reminders'
        item['fallback_v39'] = '소스 미설정/오래됨/예측 없음/ID 미대응은 이유 보존 후 시간표 모델 재검증. 모델 불성립은 재계산, 근거 누락은 기존 치명 처리.'
        item['tolerance_v39'] = '보관30초·공급시각 나이90초·미래 시계2초는 선택 정책이며 실측 ETA 허용오차/성능 보장이 아님.'
assert len(catalog['features']) == 21 and dict(Counter(x['status'] for x in catalog['features'])) == catalog['counts']
save(assets / 'readiness-catalog.json', catalog)
report = cs / 'wiki/records/reports' / (stamp + '_지하철_현재승차_출발안내와환승_연결검증.md')
with report.open('x', encoding='utf8') as f:
    f.write(f'''# 현재 지하철 승차 예측의 출발 안내·환승 연결

일반 비순환 첫 지하철 승차의 현재 도착 예측을 출발 안내에 연결했습니다. 첫 승차 시각이 달라지면 이후 구간과 환승을 다시 계산합니다. 첫 승차 대기만 현재 예측이며 탑승 소요와 미래 환승은 모델값입니다. 배포하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 새 제품 연결 시험 | 통과 | 33/33 = 100% |
| 관련 회귀 시험 | 통과 | 201/201 = 100% |
| 추가 시간·환승·감시 회귀 | 통과 | 61/61 = 100% |
| 보유 노선의 통제 도착 재계산 | 동일 결과 | 2/2 = 100% |

33은 새 파일의 통제 pytest 건수이고 201에 포함됩니다. 추가61건은 별도 파일 집합입니다. 2회는 같은 보유 경로와 통제 도착의 반복이며 독립 정확도 표본으로 세지 않습니다. 최초 사전 해시244개 대조 후 소유한 변경을 갱신하고 다른 작업자의 파일을 덮어쓰지 않았습니다.

## 적용 범위와 대체 경로

정확 공식 노선·승차역·하차역으로 일반·비순환의 정적 경로를 생성합니다. 현재 응답의 다음역/종착역/열차번호/종류/경로와 생성시각 기준 도착을 다시 대조한 뒤 요청별 복사 판정기에 첫 승차 분만 전달합니다. 공유 판정기나 저장된 일정은 이 관측으로 바꾸지 않습니다. 다른 열차의 운행표 소요를 현재 열차에 붙이지 않고 검증한 경로의 역간 모델을 사용합니다.

제품 조립에서 지하철 도착 소스를 출발 관측 훅에 전달하고 변경된 도착으로 안내 문구를 계산합니다. 지하철 표시는 ‘현재 지하철 대기 반영’입니다. 이후 구간은 바뀐 도착 시각부터 시간표·환승 시간·혼잡을 재검증하며 미래 열차를 현재 실시간이라고 부르지 않습니다. line_closed/station_skip/edge_closed 등 기존 차단은 유지합니다. 현재 승차가 버스일 때 뒤의 지하철을 미리 현재 승차로 조회하지 않습니다.

소스 미설정·오래됨·예측 없음·정확ID 미대응은 상태 근거를 남기고 시간표 모델로 다시 검증합니다. 시간표 모델도 불성립이면 기존 재계산 경로, 근거를 못 계산하면 기존 치명 처리입니다. 응답이 비었음을 실제 전체 운행 종료라고 말하지 않습니다. 지하철 보관30초 정책을 소스 저장과 현재 승차 신선도 검사에 연결하며 예전에 길게 보관한 응답도30초가 지나면 갱신합니다. 공급 시각90초/미래2초는 기존 출발 관측 정책을 사용합니다. 이 값은 ETA 오차율을 맞추는 보정 계수나 실제 정확도 보장이 아닙니다.

## 실제 자료로 확인한 추가 결함

보유 양평→영등포구청 노선·시간표·공식ID에 통제 도착응답을 넣었습니다. 처음에는 시간표에 같은 종착 열차가 있어야 한다는 조건으로 no_data가 됐습니다. 현재 열차가 목적지에서 단축 종착해도 타는 구간이 같으면 그 구간 모델을 쓸 수 있으므로, 전체 종착 경로를 정적으로 확인하고 목적지까지 구간이 같은 일반 후보와 대조하도록 고쳤습니다. 원인 재현2/2 실패→수정 후2/2 통과이며 혼잡 때문에 다음 시간표 후보로 미루는 경우도 해당 승차 구간으로 비교합니다. 현재 도착을 다른 열차 run 소요에 붙이지 않습니다.

보유 자료의 기존 모델12분, 통제 승차10:09를 넣으면13분으로 재계산됐고2회 같았습니다. 역간 모델과 통제 접근6분/퇴장2분 및 좌표 입력을 사용했습니다. 첫 재생의10:08 입력은 기존 시간표 승차와 같아12분이 유지됐습니다. 재생1·2판 실패와3·4판 스크립트/출력을 보존했습니다. 이 통제 열차번호·종착은 실제 해당 시각에 운행한 열차라고 주장하지 않습니다.

중요한 공백도 확인했습니다. 정적 노선의 목적지 이후 중간 역명에 공식ID 대응이 빠지면 실제 긴 종착 경로 전체가 선택 조합에서 제외됩니다. 이번 양평 구간에서 생성된 식별 조합은21개이고 실제 하남검단산/마천 종착까지 모두 지원한다는 뜻이 아닙니다. 정확 이름 대응587/793·미대응206개라는 이전 결과를 전량 재집계하지 않았습니다. 임의 역명 별칭/ID나 가상의 노선 연결로 덮지 않았으며 이 대응 공백을 다음 개선 단위로 남깁니다.

## 검증과 연구 확인

초기18건은 새 콜백이 없어서 실패했습니다. 구현 중 SERVICE_DAY_MAX_MIN import 누락과 현재 예측 하나를 첫차 시각으로 오인하는 분기를 고쳤습니다. 후속 시험 실패에는 환승 시험 자료 필드 누락과 첫 버스 뒤 지하철의 저장ID를 잘못 넣은 시험 설정도 포함됐으며 실제 Walk 자료형으로 바로잡았습니다. 전후 모든 로그/XML을 보존했습니다. 최종33/33·관련201/201·추가61/61, Ruff10 Python 파일 통과입니다.

[서울시 공식 필드](https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A)의 다음역·종착역ID/일반열차/초 ETA/생성시각 계약을 적용했습니다. [공식 역정보와 조회명 예외](https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do)도 확인했습니다. 도착 시각은 생성시각+ETA이며 보관 나이를 두 번 빼지 않습니다.

2026-10-09까지 공개된 연구 검색에서 [Dynamic Replanning(2025)](https://arxiv.org/abs/2505.14193)의 초록·서지를 확인했습니다. 현재 스냅샷이 미래 지연을 알지 못한다는 문제 구분을 참고하여 현재 승차와 미래 모델을 구분했습니다. [T-REX(2026)](https://arxiv.org/abs/2605.18778) 초록·서지도 확인했지만 trip/transfer 및 시간표 업데이트를 갖춘 전제를 지금 대응 공백이 충족하지 않습니다. 두 논문의 전체 알고리즘을 구현·성능 재현했다고 주장하지 않습니다. 현재 수정은 기존 구간열을 바뀐 승차 시각으로 재검증하는 연결입니다.

새 웹 경로0개·지도 개발자API0회·새 실제 도착 스냅샷0개·실제 탑승/결제0개입니다. 전체21개 판단은 조건부 사용4·개선 필요9·추가 검증8을 유지합니다. 공식 이름·코드 대응, 급행/순환선, 실제 탑승 후 위치 갱신, 1.2km 안의 새 웹 대조, 실제 ETA/결제 검증은 남아 전체 완료를 선언하지 않습니다.

mock 서버 시험(화면 반응): 안 했음.

실서버 확인(서버 응답): 안 했음. 보유 자료 계산기와 주입 HTTP transport·제품 조립 함수 시험이며 cs 프로젝트 서버·로컬 개발 서버의 HTTP 확인이나 새 외부 도착 조회가 아닙니다. 고객 알림 전송·커밋·푸시·배포·외부 메시지를 하지 않았습니다.

## 보존 자료

- [21개 기능 시각화v39](assets/{assets.name}/mobility-readiness.html) — 현재 첫 승차와 미래 모델의 구분 및 기능별 비교 수치.
- [검증 원문](../evidence/{state['tag']}/) — 실행·재현·보유 노선 재생·소유 코드 차이·해시.
- [백업 명세](../evidence/{state['tag']}/backup-manifest-v1.json) — 수정 직전 코드·시험·문서 사본의 위치와 해시.
- [결함 기록](debugs/{state['tag']}.md) — 연결 해결 범위와 공식ID 공백.

시각화는21카드·연결 흐름과 JavaScript 구문을 검사했습니다. 브라우저 렌더링/휴대폰 화면은 확인하지 않았습니다. v11 지속 이동관리의 한 개선 단위이며 DoD 전체 판정이 아닙니다.
''')

style = re.search(r'<style>(.*?)</style>', (prior / 'mobility-readiness.html').read_text(encoding='utf8'), re.S).group(1)
cards = ''.join(f'<article data-status="{html.escape(x["status"])}"><span class="status">{html.escape(x["status"])}</span><h3>{html.escape(x["name"])}</h3><p>{html.escape(x["scope"])}</p><p><b>기존 비교 수치</b> {html.escape(x["metric"])}</p><details><summary>판단 근거와 남은 검증</summary><p>{html.escape(x["reason"])}</p><p>{html.escape(x["need"])}</p></details></article>' for x in catalog['features'])
page = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 검증v39 — 현재 지하철 출발 연결</title><style>{style}</style><main>
<p>서울 이동 검증 · v39 · {now.isoformat()}</p><h1>현재 첫 승차를 반영하고<br>뒤의 환승을 다시 계산합니다.</h1><p class="lead">일반·비순환·정확 공식ID 경로의 첫 지하철 승차에 적용했습니다. 이후 소요와 미래 환승은 모델입니다. 배포·실탑승·독립 정확도 검증은 남았습니다.</p>
<section class="metrics"><p><b>33/33</b>새 연결 시험</p><p><b>201/201 + 61/61</b>관련·추가 회귀</p><p><b>12→13분</b>보유 경로 + 통제 도착</p></section>
<h2>어느 값이 현재 예측인가</h2><div class="scroll"><svg viewBox="0 0 800 190" role="img" aria-label="공식ID 확인 다음 현재 첫 승차 예측을 적용. 이후 역간 소요와 환승을 모델로 재계산하여 출발 안내에 반영" style="min-width:650px;width:100%;background:#fff;border:1px solid #ddd"><g stroke="#354052" fill="none"><rect x="20" y="50" width="170" height="75"/><rect x="220" y="50" width="170" height="75"/><rect x="420" y="50" width="170" height="75"/><rect x="620" y="50" width="160" height="75"/><path d="M190 87h30m170 0h30m170 0h30"/></g><g font-family="sans-serif" font-size="17" fill="#161c28" text-anchor="middle"><text x="105" y="80">정확 역·방향ID</text><text x="105" y="107">검증한 일반 경로</text><text x="305" y="80">현재 첫 승차</text><text x="305" y="107">생성시각 + ETA</text><text x="505" y="80">역간 소요·환승</text><text x="505" y="107">모델 재계산</text><text x="700" y="80">출발 안내</text><text x="700" y="107">예측 적용 표시</text><text x="400" y="166">전체 여정이 실시간이라는 뜻은 아닙니다.</text></g></svg></div>
<p>통제 예: 보유 양평→영등포구청 노선에서 승차10:08→10:09 입력이면 전체 모델12→13분. 동일 입력2/2회 같음. 실제 열차 도착 오차를 잰 수치가 아닙니다.</p>
<h2>남은 핵심 공백</h2><p>목적지 이후 역명·공식ID 공백이 실제 긴 종착 조합을 제외합니다. 이전 정확 이름 대응587/793·미대응206. 급행·순환선·탑승 후 위치 갱신·1.2km 이내 새 웹 대조·실제 탑승/결제 검증은 남습니다.</p>
<h2>전체21개 기능의 현재 판단</h2><p>조건부 사용4 · 개선 필요9 · 추가 검증8. 기능별 기존 비교 수치는 이번에 재측정하지 않았습니다. 새 웹/지도 개발자API/실제 도착/탑승/결제0개.</p><label for="filter">판단별 보기</label><select id="filter"><option value="all">전체21개</option><option>조건부 사용</option><option>개선 필요</option><option>추가 검증</option></select><section class="grid">{cards}</section>
<footer><a href="../../{report.name}">검증 보고서 열기</a> · <a href="readiness-catalog.json">판단 원본 열기</a><p>코드·자료·백업 해시 보존. 브라우저 렌더링 미확인.</p></footer></main><script>document.getElementById('filter').addEventListener('change',function(){{document.querySelectorAll('article').forEach(x=>{{x.hidden=this.value!=='all'&&x.dataset.status!==this.value}})}})</script></html>'''
with (assets / 'mobility-readiness.html').open('x', encoding='utf8') as f: f.write(page)
debug = cs / 'wiki/records/reports/debugs' / (state['tag'] + '.md')
backup(debug, '현재지하철_검증결과')
debug.write_text(debug.read_text(encoding='utf8').replace('## 미해결', '## 부분 해결 — 일반 비순환 첫 승차의 제품 연결', 1) + f'\n\n신규33/33·관련201/201·추가61/61. 보유 노선 통제 재생2/2. 같은 종착 시간표를 요구하던 조건은 실제 승차 구간 대조로 수정했습니다. 목적지 이후 ID 미대응에 따른 실제 종착 조합 제외와 공식 이름/급행/순환선/실탑승은 남습니다. [보고서](../{report.name}).\n', encoding='utf8')
wiki = cs / 'wiki/teams/mobility.md'
backup(wiki, '현재지하철_검증결과')
with wiki.open('a', encoding='utf8') as f:
    f.write(f'\n\n## {stamp} 현재 첫 지하철 승차의 출발 안내 연결\n\n일반 비순환 정확 공식ID 첫 승차의 현재 예측을 제품 조립→출발 관측→후속 구간/환승 모델→안내 문구에 연결했습니다. 신규33/33·관련201/201·추가61/61, 보유 양평→영등포구청 + 통제 도착2/2회 모델12→13분 확인. 단축 종착이 시간표에 없어도 타는 구간이 같으면 모델 소요를 계산하도록 고쳤습니다. [보고서](../records/reports/{report.name})·[시각화v39](../records/reports/assets/{assets.name}/mobility-readiness.html). 목적지 이후 공식 역ID 공백으로 실제 긴 종착 조합이 제외되는 문제·공식 이름 대응206개·급행/순환선·실탑승은 남습니다. 보관30초/공급시각90초/미래2초는 신선도 정책이며 ETA 정확도 보장이 아닙니다. 미래 환승은 모델. 새웹/개발자API/실탑승0·21개판단4/9/8 유지·배포하지 않았습니다.\n')
save(ev / 'backup-manifest-v1.json', {'created_at': now.isoformat(), 'backups': state['backups']})
save(ev / 'verification-proof-v1.json', {'created_at': now.isoformat(), 'source_test_data_hashes': hashes, 'new_tests': {'passed': 33, 'total': 33}, 'related_tests': {'passed': 201, 'total': 201}, 'supplemental_tests': {'passed': 61, 'total': 61}, 'controlled_native_runs': 2, 'controlled_native_path_count': 1, 'native_input_claim': native['claim'], 'source_configuration': {'cache_seconds': 30, 'provider_age_seconds': 90, 'future_clock_seconds': 2}, 'new_independent_samples': 0, 'features': 21, 'counts': catalog['counts'], 'deployed': False, 'browser_render_verified': False})
for pattern in ('*subway_departure_v*.py', '*subway-departure-work-v*.json'):
    for p in scratch.glob(pattern): shutil.copy2(p, ev / p.name)
links = []
for doc in (report, assets / 'mobility-readiness.html'):
    content = doc.read_text(encoding='utf8')
    hrefs = re.findall(r'\]\(([^)]+)\)', content) if doc.suffix == '.md' else re.findall(r'href="([^"]+)"', content)
    for href in hrefs:
        if href.startswith(('http://', 'https://', '#')): continue
        path = (doc.parent / href).resolve(); assert path.exists(), href
        links.append(path.relative_to(root).as_posix())
for rel, value in hashes.items(): assert sha(root / rel) == value, rel
for item in state['backups']: assert sha(root / item['backup']) == item['sha256']
assert page.count('<article ') == 21
js = scratch / 'subway-departure-visual-script-v1.js'
with js.open('x', encoding='utf8') as f: f.write('\n'.join(re.findall(r'<script>(.*?)</script>', page, re.S)))
node = 'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1007-641-0_26.1007.641.0_x64__3k8sg7r9htsxt/dependencies/node/bin/node.exe'
syntax = subprocess.run([node, '--check', str(js)], capture_output=True, text=True, encoding='utf8')
with (ev / 'visual-script-syntax-v1.log').open('x', encoding='utf8') as f: f.write(syntax.stdout + syntax.stderr)
assert syntax.returncode == 0, syntax.stderr
artifacts = [report, assets / 'readiness-catalog.json', assets / 'mobility-readiness.html', wiki, debug, ev / 'verification-proof-v1.json', ev / 'backup-manifest-v1.json']
artifacts += [p for p in ev.iterdir() if p.suffix in ('.log', '.xml', '.py') or p.name.startswith('native-route-controlled')]
save(ev / 'publication-validation-v1.json', {'source_hash_matches': len(hashes), 'backup_hash_matches': len(state['backups']), 'artifact_hashes': {p.relative_to(root).as_posix(): sha(p) for p in artifacts}, 'local_links': links, 'visual_cards': 21, 'syntax_exit_code': syntax.returncode, 'browser_render_verified': False})
print(json.dumps({'report': str(report), 'assets': str(assets), 'source_hashes': len(hashes), 'backups': len(state['backups']), 'new_tests': 33, 'related_tests': 201, 'supplemental': 61}, ensure_ascii=False))
