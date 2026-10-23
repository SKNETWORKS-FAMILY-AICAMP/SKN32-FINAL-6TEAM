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
state = json.loads((scratch / 'subway-selection-work-v2.json').read_text(encoding='utf8'))
ev = cs / 'wiki/records/evidence' / state['tag']
now = datetime.now().astimezone()
stamp = now.strftime('%Y-%m-%d_%H%M')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def save(path, value):
    with path.open('x', encoding='utf8') as f: json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)

def backup(path, purpose):
    dst = path.parent / '_backup' / (stamp + '_' + purpose) / path.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    assert not dst.exists()
    shutil.copy2(path, dst)
    state['backups'].append({'source': path.relative_to(root).as_posix(), 'backup': dst.relative_to(root).as_posix(), 'sha256': sha(path)})

before = ET.parse(ev / 'before-v1.xml').getroot()
after = ET.parse(ev / 'after-v2.xml').getroot()
assert len(before.findall('.//testcase')) == len(before.findall('.//failure')) == 39
assert len(after.findall('.//testcase')) == 144 and not after.findall('.//failure') and not after.findall('.//error')
assert len([t for t in after.findall('.//testcase') if t.attrib['classname'].endswith('test_subway_boardable_v1')]) == 63
native = json.loads((ev / 'native-source-replay-v3.json').read_text(encoding='utf8'))
assert native['historical_selection']['status'] == 'no_boardable_prediction'
assert len(native['controlled_abba_runs']) == 12
owned = ['app/domains/travel_ops/ports/data_sources/seoul_subway.py',
         'app/domains/travel_ops/ports/data_sources/subway_boarding.py',
         'tests/unit/travel/test_subway_boardable_v1.py']
cmd = [sys.executable, '-m', 'ruff', 'check', *owned]
lint = subprocess.run(cmd, cwd=cs, capture_output=True, text=True, encoding='utf8')
with (ev / 'ruff-v1.log').open('x', encoding='utf8') as f: f.write(lint.stdout + lint.stderr)
save(ev / 'ruff-v1.run.json', {'command': cmd, 'exit_code': lint.returncode})
assert lint.returncode == 0, lint.stdout
hashes = dict(state['prior_source_test_data_hashes'])
owned_full = {'final_project_cs/' + p for p in owned}
for rel, digest in hashes.items():
    if rel not in owned_full: assert sha(root / rel) == digest, rel
for rel in owned_full: hashes[rel] = sha(root / rel)
original = next(x for x in state['backups'] if x['source'].endswith('/seoul_subway.py'))
diff = ''.join(difflib.unified_diff((root / original['backup']).read_text(encoding='utf8').splitlines(True),
    (root / original['source']).read_text(encoding='utf8').splitlines(True), fromfile='before/' + original['source'], tofile='after/' + original['source']))
with (ev / 'owned-source-diff-v1.patch').open('x', encoding='utf8') as f: f.write(diff)
save(ev / 'research-v1.json', {'checked_at': now.isoformat(), 'sources': [
    {'url': 'https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A',
     'scope': 'Full fields and result codes: line/current/next/terminal IDs, train number/type, ETA seconds, generation timestamp, departure state.'},
    {'url': 'https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do',
     'scope': 'Official search text states ETA should be corrected by current time minus recptnDt; opened A-view lacked this dynamic description, official indexed F-view confirmed it.'}],
    'applied_formula': 'arrival_at = provider_generation_at + ETA_seconds; cache elapsed is freshness only',
    'new_map_web_samples': 0, 'map_developer_api_calls': 0, 'new_live_arrival_snapshots': 0,
    'actual_boarding_payment_samples': 0, 'paper_algorithm_applied': False,
    'reason': 'The time-origin gap is explicitly resolved by the provider specification; no new research algorithm is asserted.'})

assets = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v38'
assets.mkdir(exist_ok=False)
prior = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v37'
catalog = json.loads((prior / 'readiness-catalog.json').read_text(encoding='utf8'))
catalog.update(created_at=now.isoformat(), scope='지하철 소스의 일반열차 선택·생성시각 기준 도착 계산; 출발 안내/환승 적용은 미연결',
               prior_catalog_sha256=sha(prior / 'readiness-catalog.json'))
for item in catalog['features']:
    if '실시간' in item['name'] or item['name'] == '지하철 경로 산출':
        item['need'] += ' v38: 정확 호선/역/다음역/종착역·일반열차 경로 및 생성시각 기준 현재 승차 선택기를 소스에 추가. 신규63/63·관련144/144 통제 시험. 보유 공개 부분응답1개/5행 재생은 현재 승차 예측 없음이며 독립 오차 검증 아님. 서울역(시간표)↔서울(공식)의 이름 대응 공백을 확인했고 재생에서만 명시적으로 대응; 제품 별칭은 미변경. 출발 관측/환승 시각 적용·급행/순환선·새 웹/실탑승 표본은 남음.'
assert len(catalog['features']) == 21 and dict(Counter(x['status'] for x in catalog['features'])) == catalog['counts']
save(assets / 'readiness-catalog.json', catalog)
report = cs / 'wiki/records/reports' / (stamp + '_지하철_접근후열차선택과_생성시각_계산검증.md')
with report.open('x', encoding='utf8') as f:
    f.write(f'''# 지하철 접근 이후 열차 선택과 생성 시각 계산 검증

지하철 도착 소스에서 역 접근 이후에 오는 일반열차를 고르는 기능을 추가했습니다. 호선·역·다음역·종착역이 맞는지 검사하며 정보 생성 시각으로 도착을 계산합니다. 출발 안내와 환승 시간에 적용하는 제품 연결은 아직 남습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 새 선택·입력 시험 | 통과 | 63/63 = 100% |
| 관련 회귀 시험 | 통과 | 144/144 = 100% |
| 기존 코드·자료·산출물 사전 대조 | 일치 | 244/244 = 100% |
| 보유 공개 부분응답 재생 | 확인 | 1/1 = 100% |

63은 통제 입력 pytest 건수,144는 이를 포함한 관련 시험 수입니다. 사전244개는 직전v37 해시 목록입니다. 재생1개는10:10에 이미 받은 공개 부분응답5행이며 새5개 표본으로 세지 않습니다. 실제 ETA 오차·실탑승 성공률을 측정하지 않았습니다.

## 구현과 계산 근거

현재 승차역·하차역과 검증된 일반열차 경로의 역ID 순서를 받습니다. 노선/현재 역/다음 역/종착 역/열차 종류를 정확히 대조합니다. 경로가 목적지를 지나지 않거나 같은 식별 조합의 경로가 여러 개, 같은 열차 번호가 중복이면 추정 선택을 하지 않습니다. 급행·ITX·특급, 반복역이 있는 순환 경로는 이번 입력 계약에서 지원하지 않습니다. 이것이 실제 운행 없음이라는 뜻은 아닙니다.

서울시 공식 설명에 따라 도착시각은 recptnDt+barvlDt입니다. 예를 들어 생성20초 전, ETA200초, HTTP보관5초이면 현재 남은 시간180초이며175초로 다시 줄이지 않습니다. 보관 시간은 신선도 판정만 하고 공급 자료 나이는 별도로 검사합니다. 시간대 없는 공급 문자열은 KST로 해석하며 너무 오래된 공급 시각·정책 허용보다 미래인 시각·미래 HTTP확인·잘못된 숫자는 제외합니다. 출발 상태2는 제외하고0초 ETA는 진입/도착 상태0/1에서만 허용하며 접근 이후 조건도 지켜야 합니다.

소스 어댑터는 먼저 입력을 검사한 뒤 조회하고, 조회 완료 시각으로 출발 분을 올림한 뒤 접근 시간을 온전히 유지합니다. 시간이 지나간 열차·목적지 앞 종착 열차·반대 다음역·다른 호선·확인 못 한 열차 종류를 쓰지 않습니다. 상태 predicted는 예상 승차 가능이며 혼잡·출입문·실탑승 보장이 아닙니다. 목록에 후보가 없다는 결과는 전체 노선의 운행 종료 판정이 아닙니다. 페이지20개만 조회하는 기존 범위도 유지됩니다.

변경: seoul_subway.py에 boardable_arrival, 새 subway_boarding.py에 선택/입력 검사, test_subway_boardable_v1.py. 표본값을 맞추는 요금/시간 계수는 추가하지 않았고 신선도 상한은 호출자가 정책으로 주도록 했습니다. 공개 고객 JSON과 Core 계약은 바꾸지 않았습니다. 제품 조립·출발 관측은 이 새 메서드를 아직 호출하지 않습니다.

## 전후 실행·보유 자료 재생

최초39건은 선택기 부재로39실패, 구현 후 관련120건 통과였습니다. 추가24건의 잘못된 응답·경로·엄청나게 큰 신선도 정수·조회 완료 시각·정규화 HTTP응답 연결 검사를 더한 뒤144/144 통과했습니다. 큰 정책 정수의 math.isfinite 변환 오류도 명시된 입력 오류로 처리합니다. Ruff3파일 통과, 원문 명령/로그/XML을 보존했습니다. HTTP시험은 통제 transport를 주입하며 외부 호출을 하지 않았습니다.

보유 공식 역ID/시간표로1호선 서울→시청의 경로 식별 조합 {native['static_service_patterns']}개를 만들고10:10 공개 부분응답을 그때 시각으로 재생했습니다. 후보5행의 제외 이유는 {json.dumps(native['historical_exclusion_counts'], ensure_ascii=False)}입니다. 선택할 예측이 없었고 보관시각30초 뒤 재생은 stale입니다. 제외를 실제 결행·탑승 실패로 부르지 않습니다. HTTP확인 시각을 새로 만들거나 공급 ETA를 바꾸지 않았습니다.

검증 스크립트1·2판은 실패했습니다. 시간표의 역명은 서울역, 공식 역명은 서울이며 저장 요일값은 weekday/holiday입니다. 첫 판은 공식 이름을 시간표에도 사용했고 둘째 판은 한글 평일을 내부 저장값으로 사용했습니다. 셋째 판은 정확한 내부 요일값과 재생에만 명시한 서울역→서울 대응으로 실행했습니다. 제품의 일반 별칭은 추가하지 않았습니다. 이 이름 공백은 실시간 제품 연결 전에 공식 코드 대응 근거로 해결해야 하며 기존 정확 노선/역명206개 미대응 중 한 사례입니다. 옛 실패 스크립트와 실패 기록을 보존했습니다.

통제 계산3조건(보관 나이0/5/15초)×A/B/A/B=12회도 보존했습니다. A는 생성시각+ETA, B는 보관 나이를 추가 차감하는 잘못된 식입니다. A6회 모두180초로 같고 B는 보관 나이에 따라 달라집니다. 결정적 산술 재생이므로 평균 성능 개선·신뢰구간·독립 정확도 검증으로 해석하지 않습니다.

## 남은 제품 연결과 상태

다음은 정적 경로에서 공급자의 다음역/종착역 조합을 자동 생성하고 선택한 일반열차 도착시각을 첫 승차 및 뒤 환승 재계산에 연결하는 일입니다. 서울역→서울 등 공식 이름/코드 대응, 급행 정차·실제 열차번호와 운행표 대응, 순환선 방향, 실제 승차 이후 위치 변화도 남았습니다. 현재 버스 관측 연결은 유지되고 지하철은 시간표 모델 재계산입니다.

전체21개 판단은 조건부 사용4·개선 필요9·추가 검증8을 유지합니다. 새 웹 경로0개·지도 개발자API0회·새 실제 도착 스냅샷0개·실제 탑승/결제0개입니다. 커밋·푸시·배포·외부 메시지·고객 알림 전송을 하지 않았습니다. 전체 완료를 선언하지 않습니다.

mock 서버 시험(화면 반응): 안 했음.

실서버 확인(서버 응답): 이번 단위는 안 했음. 로컬 보유 자료 계산기·이미 확보한 공개 응답 재생과 주입 HTTP transport를 시험했으며 cs 프로젝트 서버·로컬 개발 서버 HTTP나 새 외부 호출이 아닙니다.

## 기록·백업·시각화

- [시각화v38와21기능](assets/{assets.name}/mobility-readiness.html) — 공식 시각 계산과 미연결 단계.
- [검증 원문](../evidence/{state['tag']}/) — 전후 pytest, 보유 응답 재생, ABBA 산술, 해시, 실패 기록.
- [원본 도착 소스 백업](../../../{original['backup'].removeprefix('final_project_cs/')}) — 수정 전 코드.
- [백업 명세](../evidence/{state['tag']}/backup-manifest-v1.json) — 코드/시험/문서의 원본 해시.
- [결함 기록](debugs/{state['tag']}.md) — 선택기 단위만 부분 해결; 제품 적용은 남음.
- [서울시 공식 도착 필드](https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A) — 공식 식별·열차 종류·초 단위 ETA·생성시각·상태 코드.
- [서울시 공식 시차 보정 안내](https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do) — 현재시각과 recptnDt 차이만큼 보정한다는 원문 근거.

이번 문제는 공식 명세의 생성시각 기준 식으로 해결했습니다. 논문 알고리즘을 새로 적용했다는 주장을 하지 않습니다. v11의 지속 이동 관리 및 사용자 요청 범위의 최소 단위이며 DoD 전체 판정이 아닙니다.
''')

style = re.search(r'<style>(.*?)</style>', (prior / 'mobility-readiness.html').read_text(encoding='utf8'), re.S).group(1)
cards = ''.join(f'<article data-status="{html.escape(x["status"])}"><span class="status">{html.escape(x["status"])}</span>'
    f'<h3>{html.escape(x["name"])}</h3><p>{html.escape(x["scope"])}</p><p><b>비교 근거</b> {html.escape(x["metric"])}</p>'
    f'<details><summary>판단 근거와 필요한 검증 보기</summary><p>{html.escape(x["reason"])}</p><p>{html.escape(x["need"])}</p></details></article>'
    for x in catalog['features'])
page = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 검증v38 — 접근 이후 열차 선택</title><style>{style}</style><main>
<p>서울 이동 검증 · v38 · {now.isoformat()}</p><h1>역에 도착한 뒤<br>탈 수 있는 열차를 고릅니다.</h1>
<p class="lead">공식 역·다음역·종착역이 맞는 일반열차를 고르고, 생성시각으로 도착을 계산합니다. 출발 안내와 환승 시간에 적용하는 제품 연결은 아직 남습니다.</p>
<section class="metrics"><p><b>63/63</b>새 선택·입력 시험</p><p><b>144/144</b>관련 회귀 통과</p><p><b>1개/5행</b>보유 부분응답 재생</p></section>
<h2>시간은 한 번만 보정합니다</h2><div class="scroll"><svg viewBox="0 0 720 175" role="img" aria-label="정보 생성20초 전, ETA200초이면 현재 남은 시간180초. HTTP보관5초는 추가로 빼지 않습니다" style="min-width:600px;width:100%;background:#fff;border:1px solid #ddd">
<path d="M55 85H655" stroke="#161c28" stroke-width="2"/><path d="M95 72v26M195 72v26M495 72v26M635 72v26" stroke="#a8720c" stroke-width="3"/>
<g font-family="sans-serif" font-size="15" fill="#161c28" text-anchor="middle"><text x="95" y="48">정보 생성</text><text x="95" y="124">20초 전</text><text x="195" y="48">현재</text><text x="495" y="48">역 접근 완료</text><text x="635" y="48">예상 도착</text><text x="410" y="143">현재부터180초 · 보관5초를 추가 차감하지 않음</text></g></svg></div>
<p>그림은 통제 예시이며 거리나 시간 눈금에 비례하지 않습니다. 실제 열차 도착 오차를 측정한 그림이 아닙니다.</p>
<h2>현재 연결 범위</h2><div class="scroll"><table><thead><tr><th>단계</th><th>상태</th><th>근거</th></tr></thead><tbody>
<tr><td>공식 역ID와 계획 문맥</td><td>연결</td><td>직전v37 검증 유지</td></tr><tr><td>일반열차의 정확 경로·접근·시각 선택</td><td>소스에 추가</td><td>신규63/63·관련144/144</td></tr><tr><td>출발 안내와 환승 시각 적용</td><td>남음</td><td>현재 지하철은 시간표 모델 재계산</td></tr><tr><td>공식 이름·급행·순환선 대응</td><td>남음</td><td>서울역↔서울 공백 확인; 재생에서만 명시 대응</td></tr></tbody></table></div>
<p>보유 공개 스냅샷1개/5행에서 선택 예측 없음,30초 뒤 재생은 오래된 응답으로 판정했습니다. 통제 A/B/A/B 산술12회는 독립 정확도 표본이 아닙니다.</p>
<h2>전체21개 기능의 현재 판단</h2><p>조건부 사용4개 · 개선 필요9개 · 추가 검증8개. 새 웹 경로·지도 개발자API·새 실시간 응답·실제 탑승/결제는 이번 단위0개.</p>
<label for="filter">판단별 보기</label><select id="filter"><option value="all">전체21개</option><option>조건부 사용</option><option>개선 필요</option><option>추가 검증</option></select><section class="grid" aria-label="기능별 판단">{cards}</section>
<footer><a href="../../{report.name}">검증 보고서 열기</a> · <a href="readiness-catalog.json">판단 원본 열기</a><p>백업·입력 해시 보존. 커밋·푸시·배포 없음. 브라우저 렌더링 미확인.</p></footer></main>
<script>document.getElementById('filter').addEventListener('change',function(){{document.querySelectorAll('article').forEach(x=>{{x.hidden=this.value!=='all'&&x.dataset.status!==this.value}})}})</script></html>'''
with (assets / 'mobility-readiness.html').open('x', encoding='utf8') as f: f.write(page)
debug = cs / 'wiki/records/reports/debugs' / (state['tag'] + '.md')
backup(debug, '열차선택_검증종료')
debug.write_text(debug.read_text(encoding='utf8').replace('## 미해결', '## 해결됨 (2026-10-09, 부분) — 일반열차 소스 선택기', 1)
    + f'\n신규63/63·관련144/144·보유부분응답1개5행과 산술12회 재생으로 확인했습니다. [보고서](../{report.name}). 출발/환승 제품 연결·공식 역명 차이(서울역/서울)·급행/순환선은 미해결입니다. 재생 스크립트1·2판의 잘못된 역명/요일 가정은 보존 후3판으로 고쳤으며 제품의 일반 별칭을 임의 변경하지 않았습니다.\n', encoding='utf8')
wiki = cs / 'wiki/teams/mobility.md'
backup(wiki, '열차선택_결과기록')
with wiki.open('a', encoding='utf8') as f:
    f.write(f'\n\n## {stamp} 지하철 접근 이후 일반열차 소스 선택 검증\n\n공식 호선/역/다음역/종착역과 검증된 일반열차 경로·접근 이후 조건을 대조하고 생성시각+ETA로 도착을 계산하는 선택기/소스 어댑터를 추가했습니다. 신규63/63·관련144/144 통제 시험, 보유부분응답1개5행 재생·산술12회 확인. [보고서](../records/reports/{report.name})·[시각화v38](../records/reports/assets/{assets.name}/mobility-readiness.html). 소스는 아직 출발 안내에서 호출하지 않으며 시각/환승 적용과 공식 이름(서울역/서울)·급행/순환선 대응은 남았습니다. 새웹/개발자API/실탑승0, 전체21판단4/9/8 유지·배포하지 않았습니다.\n')
save(ev / 'backup-manifest-v1.json', {'created_at': now.isoformat(), 'backups': state['backups']})
save(ev / 'verification-proof-v1.json', {'created_at': now.isoformat(), 'source_test_data_hashes': hashes,
    'new_tests': {'passed': 63, 'total': 63}, 'related_tests': {'passed': 144, 'total': 144},
    'before_failures': 39, 'before_total': 39, 'historical_unique_snapshots': 1, 'historical_rows': 5,
    'controlled_abba_runs': 12, 'features': 21, 'counts': catalog['counts'], 'deployed': False, 'browser_render_verified': False})
for name in ['prepare_subway_selection_v1.py', 'run_subway_selection_v1.py', 'run_subway_selection_v2.py',
             'audit_subway_selection_v1.py', 'audit_subway_selection_v2.py', 'audit_subway_selection_v3.py', 'publish_subway_selection_v1.py']:
    shutil.copy2(scratch / name, ev / name)
links = []
for doc in [report, assets / 'mobility-readiness.html']:
    content = doc.read_text(encoding='utf8')
    hrefs = re.findall(r'\]\(([^)]+)\)', content) if doc.suffix == '.md' else re.findall(r'href="([^"]+)"', content)
    for href in hrefs:
        if href.startswith(('https://', 'http://', '#')): continue
        path = (doc.parent / href).resolve()
        assert path.exists(), href
        links.append(path.relative_to(root).as_posix())
for rel, digest in hashes.items(): assert sha(root / rel) == digest, rel
for item in state['backups']: assert sha(root / item['backup']) == item['sha256'], item['backup']
assert page.count('<article ') == 21
js = scratch / 'subway-selection-visual-script-v1.js'
with js.open('x', encoding='utf8') as f: f.write('\n'.join(re.findall(r'<script>(.*?)</script>', page, re.S)))
node = 'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1007-641-0_26.1007.641.0_x64__3k8sg7r9htsxt/dependencies/node/bin/node.exe'
syntax_cmd = [node, '--check', str(js)]
syntax = subprocess.run(syntax_cmd, capture_output=True, text=True, encoding='utf8')
with (ev / 'visual-script-syntax-v1.log').open('x', encoding='utf8') as f: f.write(syntax.stdout + syntax.stderr)
assert syntax.returncode == 0, syntax.stderr
artifacts = [report, assets / 'mobility-readiness.html', assets / 'readiness-catalog.json', wiki, debug,
             ev / 'verification-proof-v1.json', ev / 'backup-manifest-v1.json']
save(ev / 'publication-validation-v1.json', {'source_hash_matches': len(hashes), 'backup_hash_matches': len(state['backups']),
    'local_links': links, 'artifact_hashes': {p.relative_to(root).as_posix(): sha(p) for p in artifacts},
    'visual_cards': 21, 'syntax_command': syntax_cmd, 'syntax_exit_code': syntax.returncode, 'browser_render_verified': False})
print(json.dumps({'report': report.relative_to(root).as_posix(), 'assets': assets.relative_to(root).as_posix(),
                  'source_hashes': len(hashes), 'backups': len(state['backups']), 'new_tests': 63, 'related_tests': 144}, ensure_ascii=False))
