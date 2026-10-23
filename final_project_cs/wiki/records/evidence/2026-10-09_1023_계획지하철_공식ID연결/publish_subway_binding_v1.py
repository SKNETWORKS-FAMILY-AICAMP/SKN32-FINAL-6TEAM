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
state = json.loads((scratch / 'subway-binding-work-v2.json').read_text(encoding='utf8'))
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
after = ET.parse(ev / 'after-v1.xml').getroot()
assert len(before.findall('.//testcase')) == 31 and len(before.findall('.//failure')) == 11
assert len(after.findall('.//testcase')) == 91 and not after.findall('.//failure') and not after.findall('.//error')
assert json.loads((ev / 'after-v1.run.json').read_text(encoding='utf8'))['exit_code'] == 0
native = json.loads((ev / 'native-runtime-binding-v1.json').read_text(encoding='utf8'))
assert native['loaded_official_stations'] == 696 and native['coordinate_exact_matches'] == 587
assert native['route_model_verdict'] == 'feasible' and len(native['native_capture_runs']) == 4
files = ['app/domains/travel_ops/instances/mobility/engine/' + x + '.py' for x in
         ['runtime', 'datacheck', 'departure_context', 'departure_observer', 'subway_identity']]
files += ['app/domains/travel_ops/instances/mobility/wiring.py', 'tests/unit/travel/mobility/test_subway_binding_v1.py']
cmd = [sys.executable, '-m', 'ruff', 'check', *files]
lint = subprocess.run(cmd, cwd=cs, capture_output=True, text=True, encoding='utf8')
with (ev / 'ruff-v1.log').open('x', encoding='utf8') as f: f.write(lint.stdout + lint.stderr)
save(ev / 'ruff-v1.run.json', {'command': cmd, 'exit_code': lint.returncode})
assert lint.returncode == 0, lint.stdout
hashes = dict(state['prior_source_test_data_hashes'])
owned = {'final_project_cs/' + name for name in files}
for name, digest in hashes.items():
    if name not in owned: assert sha(root / name) == digest, name
for rel in files: hashes['final_project_cs/' + rel] = sha(cs / rel)
diff = ''
for item in state['backups']:
    if item['source'] in owned and not item['source'].endswith('test_subway_binding_v1.py'):
        old, new = root / item['backup'], root / item['source']
        diff += ''.join(difflib.unified_diff(old.read_text(encoding='utf8').splitlines(True), new.read_text(encoding='utf8').splitlines(True),
            fromfile='before/' + item['source'], tofile='after/' + item['source']))
with (ev / 'owned-source-diff-v1.patch').open('x', encoding='utf8') as f: f.write(diff)
save(ev / 'research-v1.json', {'checked_at': now.isoformat(), 'sources': [
    {'url': 'https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A',
     'scope': 'Full official identifiers/next/previous station/terminal/train type/ETA fields read.'},
    {'url': 'https://gtfs.org/documentation/realtime/reference/',
     'scope': 'TripDescriptor and StopTimeUpdate identity fields; design reference only, Seoul provider is not GTFS.'}],
    'new_route_web_samples': 0, 'map_developer_api_calls': 0, 'new_live_arrival_snapshots': 0,
    'actual_boarding_payment_samples': 0, 'method': 'Exact identity join and content version checks; no new route/prediction algorithm requiring paper implementation.'})
save(ev / 'native-failure-v2.json', {'error': 'Audit v2 iterated station_coords dictionary keys as rows.',
    'product_defect': False, 'resolution': 'Preserved v2 and used v3 dictionary values; native product runtime and ID loading succeeded.'})

assets = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v37'
assets.mkdir(exist_ok=False)
prior_assets = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v36'
catalog = json.loads((prior_assets / 'readiness-catalog.json').read_text(encoding='utf8'))
catalog['created_at'] = now.isoformat()
catalog['scope'] = '공식 역ID의 런타임/출발 문맥/저장 전 판 검사 연결; 열차 선택과 실시간 시각 미연결'
catalog['prior_catalog_sha256'] = sha(prior_assets / 'readiness-catalog.json')
for feature in catalog['features']:
    if '실시간' in feature['name'] or feature['name'] == '지하철 경로 산출':
        feature['need'] += ' 공식 역ID696행을 런타임과 저장 출발 문맥에 연결했습니다. 노선/역명 정확 대응587/793, 같은 수정시각의 내용 교체·삭제/생성·저장ID변조 검사, 신규31/31·관련91/91·보유자료1경로4회 문맥 확인. 실제 열차 선택/지하철 출발/환승 시각 적용·독립 새 경로 검증은 남았습니다.'
assert len(catalog['features']) == 21 and dict(Counter(x['status'] for x in catalog['features'])) == catalog['counts']
save(assets / 'readiness-catalog.json', catalog)
report = cs / 'wiki/records/reports' / (stamp + '_계획지하철_공식역ID와_내용판_연결검증.md')
source_backup = next(x['backup'] for x in state['backups'] if x['source'].endswith('/runtime.py'))
with report.open('x', encoding='utf8') as f:
    f.write(f'''# 계획 지하철의 공식 역ID와 내용 판 연결 검증

계획한 승차역·하차역을 공식 역ID로 연결했습니다. 동명이역은 호선별로 구분하며, 역ID 자료의 내용이 바뀌면 이전 계획 문맥을 다시 계산하게 합니다. 실제 열차 선택·실시간 출발/환승 시간 적용은 다음 연결 단위입니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 신규 연결·변경 시험 | 통과 | 31/31 = 100% |
| 관련 회귀 시험 | 통과 | 91/91 = 100% |
| 실제 자료 공식 역ID 적재 | 확인 | 696/696 = 100% |
| 기존 좌표와 정확 노선/역명 대응 | 일부 대응 | 587/793 = 74.0% |
| 보유 자료의 경로 문맥 확인 | 확인 | 1/1 = 100% |

31은 통제 파일·문맥 시험 건수, 91은 이를 포함한 관련 pytest 건수입니다. 696은 이미 확보한 공식2026-09-02 파일의 행 수, 793은 기존 역 좌표의 행 수입니다. 보유 자료로 양평→영등포구청 한 경로를4회 저장했으며 새 독립 경로4개로 세지 않습니다. 실시간 ETA 정확도·실탑승 성능을 측정한 결과가 아닙니다.

## 제품 코드의 변경

공식 역정보를 선택 입력으로 적재합니다. 없으면 시간표 계산은 유지하지만 저장 지하철 연결은 unavailable로 명시합니다. 존재하는 파일의 잘못된 스키마·타입·역/노선 건수·중복ID·중복노선/역명·노선 대응 충돌은 적재 실패입니다. 조회는 노선+정확 역명이며 숫자1~9호선의 선행0만 통일합니다. 경의선을 경의중앙선으로 임의 변경하거나 역 접미사를 추정해 연결하지 않습니다. 양평은5호선1005000522와 경의중앙선1063075135를 구분합니다.

내부 출발 문맥은 첫 지하철 구간의 line_id·station_id·target_station_id·공식 조회명을 복사하고 입력 판에 공식 파일의 SHA256을 저장합니다. 외부 고객 case JSON과 공개 route 옵션의 구조는 바꾸지 않습니다. 자료 생성·삭제·같은 수정시각의 내용 교체를 감지하고, 계산기 구성 중 내용이 달라지면 적재를 거부합니다. 출발 관측은 현재 연결과 저장ID가 다르면 재계산을 요구합니다. 안내 저장 직전 판 검사도 현재 파일의 해시와 비교하며 시간표 적재/API 호출 없이 판을 확인합니다.

관련 코드: runtime.py·datacheck.py·departure_context.py·departure_observer.py·wiring.py, 새 subway_identity.py와 test_subway_binding_v1.py. Ruff7파일 통과. 수정 전 신규31건은11실패·20통과였고 수정 후 관련91건은 전부 통과했습니다. 기존 급행 자료 판 검사·버스 관측·수동 런타임 문맥 호환을 함께 확인했습니다. 신규 시험을 만든 뒤 사용하지 않는 import 하나를 백업 후 제거했으며 동작은 바꾸지 않았습니다.

## 실제 보유 자료 검증

로컬 파일만 읽는 실제 이동 계산기 구성으로 공식 역정보696개·19호선을 적재했습니다. 같은 런타임의 정확 조회로 기존 좌표793개 중587개가 맞았고206개는 대응시키지 않았습니다. 이206개는 자료 범위·노선 이름·역명 버전 차이가 포함될 수 있어 서울에서 경로가 없는206개라고 부르지 않습니다.

실제 시간표로5호선 양평→영등포구청10:00 출발 경로가 모델상 feasible인 것을 확인했고, 같은 경로 문맥4회 모두 승차ID1005000522·하차ID1005000523을 보존했습니다. 자료 파일이 변하지 않은 상태에서 changed_sources가 비어 있음을 확인했습니다. 이 한 경로의 적재·문맥 확인을 모집단 품질로 일반화하지 않습니다.

검증 스크립트 첫 판은 data_dir에 processed가 아닌 상위 폴더를 주어 적재 전에 실패했고, 둘째 판은 좌표 dict의 key를 행처럼 읽어 실패했습니다. 오류·옛 스크립트를 보존하고 문서의 processed 구조와 dict.values를 적용한 셋째 판으로 검증했습니다. cs 프로젝트 코드 결함으로 분류하지 않습니다.

## 현재 연결 범위와 다음 작업

현재 런타임 적재→계획 문맥→출발 전 문맥 대조→안내 저장 직전 판 검사까지 공식ID가 연결됩니다. 지하철 도착 API 호출·방향/종착/열차 종류 선택·recptnDt 시차 보정·지하철 승차 시각 대체는 아직 연결하지 않았습니다. 버스가 첫 구간이면 기존 실시간 도착을 쓰고, 지하철은 시간표 모델 재계산이라는 점은 같습니다. 공식 자료 ID가 있다고 그 역의 실시간 서비스가 제공된다고 주장하지 않습니다.

앞 보고서v36의 “현재 소비 중인 공개 도착 소스”는 소스 메서드 시험을 가리키는 표현이었으나 제품 소비로 읽힐 수 있습니다. app 전체 *.py의 정적 참조를 확인하면 지하철 소스는 설정으로 구성될 뿐 현재 출발 안내에서 호출하지 않습니다. 실제 지하철 알림 소비까지 연결했다는 의미로 정정합니다: 아직 호출·시각 적용은 미연결입니다. 동적 외부 주입의 모든 가능성을 부정한 것이 아닙니다.

새 웹 지도 경로0개·지도 개발자API0회·새 실제 도착 스냅샷0개·실제 탑승/결제0개입니다. 전체21개 판단은 조건부 사용4·개선 필요9·추가 검증8을 유지합니다. 커밋·푸시·배포·외부 메시지·고객 안내 전송을 하지 않았습니다. 전체 완료를 선언하지 않습니다.

mock 서버 시험(화면 반응): 안 했음.

실서버 확인(서버 응답): 이번 단위는 안 했음. 보유 자료의 실제 계산기 적재·시간표 판정·문맥 저장을 확인했으며 외부 API·로컬 개발 서버·cs 프로젝트 서버 HTTP 시험이 아닙니다.

## 원문·백업·시각화

- [시각화와21기능](assets/{assets.name}/mobility-readiness.html) — 연결한 단계와 기능별 근거.
- [검증 원문](../evidence/{state['tag']}/) — pytest·명령·Ruff·실제 자료 적재 결과·실패 스크립트 기록.
- [변경 전 계산기 백업](../../../{source_backup.removeprefix('final_project_cs/')}) — 원본 코드.
- [백업 명세](../evidence/{state['tag']}/backup-manifest-v1.json) — 원본과 백업의 해시.
- [결함 기록](debugs/{Path(state['debug']).name}) — 연결 결함과 닫은 범위.
- [공식 역ID 자료](../../../../datasets/mobility/processed/mobility/subway_realtime_stations_20260902_v1.json) — 보유 데이터의 정적 식별정보.
- [서울시 공식 도착 명세](https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A) — 역/노선/종착/열차 식별 필드.
- [GTFS Realtime 식별 규칙](https://gtfs.org/documentation/realtime/reference/) — 정적 경로와 실시간 입력의 식별을 연결하는 설계 참고이며 서울시가 GTFS를 제공한다는 뜻은 아닙니다.

입력 원문의 해시·코드·시험 해시는 verification-proof-v1.json, 명령은 before/after-v1.run.json에 보존했습니다. 이번 단위는 새 예측/경로 알고리즘 도입이 아니라 공식 식별정보와 자료 판 연결이므로 논문의 알고리즘을 적용했다는 주장을 하지 않습니다. v11의 지속 이동 관리와 사용자 요청에 해당하며 DoD 전체 완료 판정이 아닙니다.
''')

style = re.search(r'<style>(.*?)</style>', (prior_assets / 'mobility-readiness.html').read_text(encoding='utf8'), re.S).group(1)
cards = ''.join(f'<article data-status="{html.escape(x["status"])}"><span class="status">{html.escape(x["status"])}</span>'
    f'<h3>{html.escape(x["name"])}</h3><p>{html.escape(x["scope"])}</p><p><b>비교 근거</b> {html.escape(x["metric"])}</p>'
    f'<details><summary>판단 근거와 필요한 검증 보기</summary><p>{html.escape(x["reason"])}</p><p>{html.escape(x["need"])}</p></details></article>'
    for x in catalog['features'])
page = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 검증v37 — 공식 역ID 연결</title><style>{style}</style><main>
<p>서울 이동 검증 · v37 · {now.isoformat()}</p><h1>계획한 승차역을<br>공식 역ID로 연결합니다.</h1>
<p class="lead">같은 이름의 역은 호선별로 구분합니다. 자료 내용이 달라지거나 저장ID가 바뀌면 이전 문맥을 다시 계산합니다. 열차 선택·실시간 출발/환승 시각 적용은 다음 단계입니다.</p>
<section class="metrics"><p><b>696/696</b>공식 역ID 적재</p><p><b>587/793</b>기존 좌표 정확 대응</p><p><b>91/91</b>관련 회귀 시험 통과</p></section>
<h2>현재 연결된 단계</h2><div class="scroll"><table><thead><tr><th>단계</th><th>상태</th><th>확인 근거</th></tr></thead><tbody>
<tr><td>공식 역정보 적재</td><td>연결</td><td>696행·19호선, 오류 자료는 실패</td></tr><tr><td>계획한 승차/하차역 연결</td><td>연결</td><td>정확 노선+역명, 동명이역 구분</td></tr><tr><td>출발 전·저장 전 자료 판 대조</td><td>연결</td><td>내용 교체/삭제/생성·저장ID 변조 시험</td></tr><tr><td>도착 API와 실제 열차 선택</td><td>남음</td><td>방향·종착·열차 종류·자료 시각 검증 필요</td></tr><tr><td>실시간 출발·환승 시간 적용</td><td>남음</td><td>현재 지하철은 시간표 모델 재검증</td></tr></tbody></table></div>
<p>신규31/31·관련91/91. 보유 시간표의1개 경로를4회 저장했습니다. 실제 운행·탑승 관측과 독립 경로4개의 검증으로 세지 않습니다. 206개 미대응 좌표는 보존했습니다.</p>
<h2>전체21개 기능의 현재 판단</h2><p>조건부 사용4개 · 개선 필요9개 · 추가 검증8개. 새 웹 경로0개·지도 개발자API0회·새 실시간 스냅샷0개·실제 탑승/결제0개.</p>
<label for="filter">판단별 보기</label><select id="filter"><option value="all">전체21개</option><option>조건부 사용</option><option>개선 필요</option><option>추가 검증</option></select><section class="grid" aria-label="기능별 판단">{cards}</section>
<footer><a href="../../{report.name}">검증 보고서 열기</a> · <a href="readiness-catalog.json">판단 원본 열기</a><p>원본 백업·내용 해시 보존. 커밋·푸시·배포 없음. 브라우저 화면 렌더링 미확인.</p></footer></main>
<script>document.getElementById('filter').addEventListener('change',function(){{document.querySelectorAll('article').forEach(x=>{{x.hidden=this.value!=='all'&&x.dataset.status!==this.value}})}})</script></html>'''
with (assets / 'mobility-readiness.html').open('x', encoding='utf8') as f: f.write(page)
debug = root / state['debug']
backup(debug, '공식ID연결_상태갱신')
debug.write_text(debug.read_text(encoding='utf8').replace('## 미해결', '## 해결됨 (2026-10-09, 부분) — 공식ID 적재·문맥·자료 판 연결', 1)
    + f'\n신규31/31·관련91/91·보유자료696ID 적재/1경로4회 문맥 확인으로 검증했습니다. [보고서](../{report.name}). 열차선택/API호출/실시간 출발·환승 시각 적용은 남았습니다.\n', encoding='utf8')
wiki = cs / 'wiki/teams/mobility.md'
backup(wiki, '공식ID연결_결과기록')
with wiki.open('a', encoding='utf8') as f:
    f.write(f'\n\n## {stamp} 계획 지하철 공식ID와 자료 판 연결 검증 결과\n\n공식 역ID696개를 런타임·첫 지하철 승차/하차 문맥·출발 대조·저장 직전 내용 판 검사에 연결했습니다. 신규31/31·관련91/91·보유자료1경로4회 문맥 확인, 정확 좌표 대응587/793·미대응206보존을 확인했습니다. [보고서](../records/reports/{report.name})·[시각화v37](../records/reports/assets/{assets.name}/mobility-readiness.html). 지하철 소스는 아직 출발 안내에서 호출하지 않으며 열차선택/실시간 시각 적용은 남았습니다. 새웹/지도개발자API/실탑승0, 전체21판단4/9/8 유지·배포하지 않았습니다.\n')
for name in ['README.md', 'REPORT.md']:
    doc = root / 'datasets/mobility' / name
    backup(doc, '공식역ID_런타임연결')
    with doc.open('a', encoding='utf8') as f:
        f.write(f'\n\n## {stamp} 공식 역ID 자료의 런타임 연결\n\n[공식 역ID 추출물](processed/mobility/subway_realtime_stations_20260902_v1.json)을 이제 선택 입력으로 적재하며696행·19호선과 내용SHA256을 확인합니다. 첫 지하철 승차/하차 문맥·출발 대조·저장 직전 판 검사에 사용합니다. 없으면 ID 연결unavailable, 잘못된 파일은 적재 실패입니다. 정확 좌표 대응587/793·미대응206개를 보존하며 넓은 역명 별칭은 추정하지 않습니다. 추출물의 connected_to_departure=false는 실시간 운행 시각 적용 미연결이라는 의미로 유지합니다. 이전 “런타임 미연결” 기록은 당시 상태이며 현재 ID 적재/문맥은 연결됐습니다. 원문/가공물/기동 명세를 덮어쓰지 않았습니다. [보고서](../../final_project_cs/wiki/records/reports/{report.name}).\n')
save(ev / 'backup-manifest-v1.json', {'created_at': now.isoformat(), 'backups': state['backups']})
save(ev / 'verification-proof-v1.json', {'created_at': now.isoformat(), 'source_test_data_hashes': hashes,
    'new_tests': {'passed': 31, 'total': 31}, 'related_tests': {'passed': 91, 'total': 91},
    'before_failures': 11, 'before_total': 31, 'native_unique_routes': 1, 'native_capture_runs': 4,
    'features': 21, 'counts': catalog['counts'], 'deployed': False, 'browser_render_verified': False})
for name in ['prepare_subway_binding_v1.py', 'prepare_subway_binding_checks_v1.py', 'run_subway_binding_v1.py',
             'audit_subway_binding_v1.py', 'audit_subway_binding_v2.py', 'audit_subway_binding_v3.py', 'publish_subway_binding_v1.py']:
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
for name, digest in hashes.items(): assert sha(root / name) == digest, name
for item in state['backups']: assert sha(root / item['backup']) == item['sha256'], item['backup']
assert page.count('<article ') == 21
artifacts = [report, assets / 'mobility-readiness.html', assets / 'readiness-catalog.json', wiki, debug,
             root / 'datasets/mobility/README.md', root / 'datasets/mobility/REPORT.md',
             ev / 'verification-proof-v1.json', ev / 'backup-manifest-v1.json']
save(ev / 'publication-validation-v1.json', {'source_hash_matches': len(hashes), 'backup_hash_matches': len(state['backups']),
    'local_links': links, 'artifact_hashes': {p.relative_to(root).as_posix(): sha(p) for p in artifacts},
    'feature_count': 21, 'browser_render_verified': False})
print(json.dumps({'report': report.relative_to(root).as_posix(), 'sources': len(hashes), 'backups': len(state['backups']),
                  'artifacts': len(artifacts), 'links': len(links)}, ensure_ascii=False))
