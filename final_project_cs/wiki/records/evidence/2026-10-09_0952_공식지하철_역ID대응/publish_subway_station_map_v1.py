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
state = json.loads((scratch / 'subway-station-map-work-v2.json').read_text(encoding='utf8'))
ev = cs / 'wiki/records/evidence' / state['tag']
now = datetime.now().astimezone()
stamp = now.strftime('%Y-%m-%d_%H%M')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
def save(path, value):
    with path.open('x', encoding='utf8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
def backup(path, purpose):
    dst = path.parent / '_backup' / (stamp + '_' + purpose) / path.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    assert not dst.exists()
    shutil.copy2(path, dst)
    state['backups'].append({'source': path.relative_to(root).as_posix(), 'backup': dst.relative_to(root).as_posix(), 'sha256': sha(path)})

before = ET.parse(ev / 'before-v1.xml').getroot()
after = ET.parse(ev / 'after-v1.xml').getroot()
assert len(before.findall('.//testcase')) == 26 and len(before.findall('.//failure')) == 3
assert len(after.findall('.//testcase')) == 91 and not after.findall('.//failure') and not after.findall('.//error')
assert json.loads((ev / 'after-v1.run.json').read_text(encoding='utf8'))['exit_code'] == 0
audit = json.loads((ev / 'official-row-replay-and-join-v1.json').read_text(encoding='utf8'))
rows = json.loads((ev / 'xlsx-row-verification-v1.json').read_text(encoding='utf8'))
assert rows['exact_source_row_matches'] == 696 and audit['exact_matches'] == 587 and len(audit['unmatched']) == 206
assert [r['retained'] for r in audit['injected_variants']] == [652, 696, 696, 652]
files = ['app/domains/travel_ops/ports/data_sources/seoul_subway.py', 'scripts/mobility/build_subway_realtime_stations.py',
         'tests/unit/travel/test_subway_line_identity_v1.py', 'tests/unit/travel/test_subway_station_extract_v1.py']
cmd = [sys.executable, '-m', 'ruff', 'check', *files]
lint = subprocess.run(cmd, cwd=cs, capture_output=True, text=True, encoding='utf8')
(ev / 'ruff-v1.log').write_text(lint.stdout + lint.stderr, encoding='utf8')
save(ev / 'ruff-v1.run.json', {'command': cmd, 'exit_code': lint.returncode})
assert lint.returncode == 0, lint.stdout
hashes = dict(state['prior_source_test_data_hashes'])
owned = {'final_project_cs/' + name for name in files}
for name, digest in hashes.items():
    if name not in owned:
        assert sha(root / name) == digest, name
for rel in files:
    hashes['final_project_cs/' + rel] = sha(cs / rel)
data_files = ['datasets/mobility/raw/subway_realtime_station_20261009_v1/realtime_station_20260902.xlsx',
              'datasets/mobility/raw/subway_realtime_station_20261009_v1/acquisition-v1.json',
              'datasets/mobility/processed/mobility/subway_realtime_stations_20260902_v1.json']
for rel in data_files:
    hashes[rel] = sha(root / rel)
old = root / next(x['backup'] for x in state['backups'] if x['source'].endswith('/seoul_subway.py'))
source = cs / files[0]
(ev / 'owned-source-diff-v1.patch').write_text(''.join(difflib.unified_diff(old.read_text(encoding='utf8').splitlines(True),
    source.read_text(encoding='utf8').splitlines(True), fromfile='before/' + files[0], tofile='after/' + files[0])), encoding='utf8')
save(ev / 'research-and-acquisition-v1.json', {'checked_at': now.isoformat(), 'sources': [
    {'url': 'https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do',
     'scope': 'full dataset description, official file list, metadata/license and ETA generation-time correction notice',
     'downloaded_file_basis_date': '2026-09-02'},
    {'url': 'https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A',
     'scope': 'official fields previously verified; source file provides Shinlim ID not listed in older enum'},
    {'url': 'https://gtfs.org/documentation/realtime/reference/',
     'scope': 'prior turn unique trip/stop identity requirement; unchanged design reference, Seoul is not GTFS'}],
    'new_route_web_samples': 0, 'map_developer_api_calls': 0, 'actual_arrival_samples': 0,
    'network_limitation': 'Initial sandbox Python page read failed DNS. Authorized read-only escalation fetched official HTML and public xlsx successfully. No authentication key used.',
    'research_requirement': 'This unit fixes authoritative code-table mismatch with source data; no new prediction or routing algorithm adopted.'})
for name in ['subway-station-page-20261009-v1.html', 'subway-station-page-fetch-v1.json']:
    shutil.copy2(scratch / name, ev / name)

assets = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v35'
assets.mkdir(exist_ok=False)
prior_catalog = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v34/readiness-catalog.json'
catalog = json.loads(prior_catalog.read_text(encoding='utf8'))
catalog['created_at'] = now.isoformat()
catalog['scope'] = '공식 실시간 지하철 역ID 696개 확보와 누락3호선 필터 수정; 실시간 출발/환승 미연결'
catalog['prior_catalog_sha256'] = sha(prior_catalog)
for feature in catalog['features']:
    if '실시간' in feature['name'] or feature['name'] == '지하철 경로 산출':
        feature['need'] += ' 공식2026-09-02 역정보696행·19호선 확보, 기존좌표793행 중 정확 노선/역명587행 대응·206행 미대응 보존. 경강선/서해선/신림선 ID누락을 고쳐 주입 호선 필터652/696→696/696을 확인했습니다. 신규26/26·관련91/91. 실제696역 서비스 제공, 열차선택, 실시간 출발/환승 연결은 아직 검증하지 않았습니다.'
assert len(catalog['features']) == 21 and dict(Counter(x['status'] for x in catalog['features'])) == catalog['counts']
save(assets / 'readiness-catalog.json', catalog)
report = cs / 'wiki/records/reports' / (stamp + '_공식지하철_역ID확보와_누락호선_검증.md')
source_backup = next(x['backup'] for x in state['backups'] if x['source'].endswith('/seoul_subway.py'))
report.write_text(f'''# 공식 지하철 역ID 확보와 누락 호선 검증

공식 역ID696개를 새로 확보했고, 경강선·서해선·신림선의 호선 필터가 열차를 버리던 문제를 수정했습니다. 정확 역ID 대응표를 준비했지만 실시간 출발·환승 연결은 아직 남았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 공식 원문 행 추출·대조 | 일치 | 696/696 = 100% |
| 기존 역 좌표와 정확 노선/역명 대응 | 일부 대응 | 587/793 = 74.0% |
| 신규 시험 | 통과 | 26/26 = 100% |
| 기존 동작 포함 관련 시험 | 통과 | 91/91 = 100% |

생성 {now.isoformat()}. 신규26건은 관련91건에 포함됩니다. 공식 정적 자료를 주입한 결과이며 새 실제 열차696건 또는 독립 웹 경로696개로 세지 않습니다.

## 새로 확보한 공식 자료

[서울시 공식 파일 목록](https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do)의 최신 표시 파일은 `실시간도착_역정보(20260902).xlsx`입니다. 무료 공개 내려받기 주소를 실제 HTML의 파일57번·폼 값에서 확인해 인증키 없이 받았습니다. 29,869bytes·Data시트 A2:D697의696행·19호선이며 SHA-256은 `537c1ab9f58b9b4d9bf35c34ac5d9de2e8b24bc25e3058d726f4a5bbae787da8`입니다. 자료 날짜와 이번 수집 시각은 구별합니다. 출처: 서울특별시, 공공누리 제1유형.

[원문과 수집 정보](../../../../datasets/mobility/raw/subway_realtime_station_20261009_v1/)·[추출 JSON](../../../../datasets/mobility/processed/mobility/subway_realtime_stations_20260902_v1.json)을 git 제외 자료 폴더에 새로 보존했습니다. 원문을 편집하거나 기존 시간표/좌표/기동 명세를 덮어쓰지 않았습니다.

[추출 코드](../../../scripts/mobility/build_subway_realtime_stations.py)는 원문 SUBWAY_ID·STATN_ID·STATN_NM·호선이름을 그대로 사용합니다. 역코드에 숫자를 붙여 ID를 생성하지 않습니다. ID/노선·역명 중복, 타입 오류, 동일 호선의 상충 ID는 실패로 표시합니다. 출력이 이미 있으면 읽기 전에 거절합니다. 별도 번들 Python의 읽기 전용 원문 대조로696/696행이 일치함을 확인했습니다. [원문 대조](../evidence/{state['tag']}/xlsx-row-verification-v1.json).

## 정확 대응 범위

현재 역 좌표793행을 분모로 숫자 호선의 선행0만 통일한 노선명+정확 역명으로 대응했습니다.587행 대응,206행 미대응입니다. 미대응 목록 전체를 보존했으며 다른 이름·도시·노선 체계·공개 범위 차이를 검토하기 전 이름 유사도나 접두사 조합으로 채우지 않았습니다. 이것은 서울 서비스 실패율이나206개의 영구 결측을 뜻하지 않습니다. 좌표 자료와 공식 파일의 범위가 다를 수 있습니다.

동명 양평은5호선 `1005000522`와 경의중앙선 `1063075135`로 따로 보존합니다. 노선 없는 역 이름만으로 하나를 고르지 않았습니다. [전체 대응·미대응 목록](../evidence/{state['tag']}/official-row-replay-and-join-v1.json).

## 찾은 결함과 수정

기존 SUBWAY_ID에 경강선1081·서해선1093·신림선1094가 누락됐습니다. 공식 파일 각각12·21·11역, 합계44행입니다. 공개 arrivals(line=호선명)는 숫자를 호선명으로 바꾸지 못해 행을 제외했습니다. 공식 공개 파일의 대응값3개를 기존 이름 표에 추가했고 미등록 번호를 보존하는 기존 동작은 유지했습니다. 요금·속도·ETA를 보정한 변경이 아닙니다. [이번 코드 차이](../evidence/{state['tag']}/owned-source-diff-v1.patch).

수정 전 신규26건 중3실패·23통과였고, 수정 후 관련91/91·종료코드0 및 Ruff4파일 통과입니다. [명령·로그·JUnit](../evidence/{state['tag']}/). 공식696행의 호선/역ID를 가상 도착 응답에 주입해 이전·수정·수정·이전(ABBA)으로 공개 필터를 실행했습니다. 남은 행은652→696→696→652개입니다. 정상 응답을 받은 실제 역 수가 아니며 원문696행을2,784회 반복한 통제 시험입니다. 외부 연결을 차단했고 이 재생에서 연결 시도0회였습니다.

## 실시간 연결 전제와 남은 일

공식 파일은 정적 역ID 자료입니다. 문서에는 서울시 밖 구간 미제공 안내도 있어 파일에 있는 모든 역이 지금 실시간 응답을 준다고 보장하지 않습니다. 응답 생성시각 recptnDt와 조회 시각의 차이를 고려해야 한다는 공식 안내도 확인했습니다. 이번에는 도착시각 선택·보정·출발 관측·환승 재계산을 구현하지 않았습니다.

다음 작업은 정확 대응587행의 계획 역ID 연결과 미대응 사유 분류, 다음 역/방향·종착역·열차 종류·접근 후 탑승 가능 시각을 검증한 선택, 판정기/출발 관측 연결입니다. 특히 과거 ETA를 조회 완료 시각 기준으로 무조건 더하면 안내가 늦어질 수 있어 원 생성시각 기준을 검증해야 합니다. 이번 공개 역ID 표는 새 경로 최적화/예측 알고리즘 변경이 아니며 논문 성능을 적용했다고 쓰지 않습니다. [공식 문서 읽기·수집 범위](../evidence/{state['tag']}/research-and-acquisition-v1.json).

[전체21개 시각화v35](assets/2026-10-09_mobility_readiness_v35/mobility-readiness.html)는 조건부 사용4·개선 필요9·추가 검증8을 유지합니다. 완료율이 아닙니다. 새 경로 웹 표본0개·지도 개발자API 호출0회·실제 도착/탑승/결제 관측0회입니다. 이번에는 공식 웹 페이지와 파일을 확보했습니다.

mock 서버 시험(화면 반응): 안 했음.
실서버 확인(서버 응답): 서울시 공개 파일 내려받기 HTTP200 확인. cs 프로젝트 서버 HTTP와 실시간 지하철 도착 응답은 안 했음.

처음 샌드박스 Python 웹 읽기는 DNS실패였고, 승인된 읽기 전용 실행으로 공식 페이지·파일 확보에 성공했습니다. 자동 승인 심사 거절이나 사용자 조치 대기는 아닙니다. 번들 Python에서 cs 패키지를 불러오는 탐색은 OpenAI 라이브러리 부재로 실패했으며, 자료 분석은 번들 Python의 AST/표준 JSON으로 하고 제품 함수 시험은 기존 프로젝트 Python에서 실행했습니다. 이를 제품 실패나 자료결측으로 세지 않았습니다.

커밋·푸시·배포·외부 메시지·결제를 실행하지 않았으며 브라우저 렌더링은 미확인입니다.

## 백업·재현

[백업 명세](../evidence/{state['tag']}/backup-manifest-v1.json)·[소스 이전 판](../../../{Path(source_backup).relative_to('final_project_cs').as_posix()})에 덮어쓰기 전판을 보존합니다. 새 데이터·보고서·시각화는 새 이름입니다. 재현 명령은 원문 run.json, 정본 스크립트는 워크스페이스 `.tmp/mobility_complete_20261008`, 근거 폴더의 사본은 읽기 보존용입니다.
''', encoding='utf8')

cards = ''.join('<article><h3>' + html.escape(x['name']) + '</h3><p><b>' + html.escape(x['status']) + '</b></p>' + ''.join('<p><b>' + label + '</b> ' + html.escape(x[key]) + '</p>' for label, key in [('범위', 'scope'), ('비교 수치', 'metric'), ('판단 근거', 'reason'), ('더 필요한 일', 'need')]) + '</article>' for x in catalog['features'])
page = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 검증 v35</title><style>body{{margin:0;background:#fbfcfd;color:#161c28;font:16px/1.65 system-ui,sans-serif}}main{{max-width:1120px;margin:auto;padding:32px 20px}}h1{{font-size:28px}}h2{{font-size:22px}}h3{{font-size:19px}}a{{color:#2f5bd8}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr));gap:16px}}article{{background:white;padding:24px;border:1px solid #d8dce2;border-radius:8px}}.note{{padding:16px;background:#faf6eb;border-left:4px solid #a8720c}}svg{{width:100%;height:auto}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #d8dce2}}table{{width:100%;border-collapse:collapse}}@media(max-width:600px){{main{{padding:20px 16px}}article{{padding:16px}}}}</style><main><h1>서울 이동 모듈 검증 v35</h1><p>공식 역 번호696개를 확보하고, 세 호선의 필터 누락을 수정했습니다. 실시간 출발·환승 연결은 남았습니다.</p><p>{now.isoformat()}</p><div class="note">전체21개: 조건부 사용4 · 개선 필요9 · 추가 검증8. 완료율이 아닙니다. 이번 필터 수치는 공식 정적 역정보를 주입한 결과입니다.</div><h2>이번 근거</h2><table><tr><th>검증</th><th>수치와 범위</th></tr><tr><td>공식 원문 대조</td><td>696/696행 일치·19호선, 자료날짜2026-09-02</td></tr><tr><td>기존 좌표와 정확 대응</td><td>587/793행·미대응206행 목록 보존</td></tr><tr><td>누락3호선 필터</td><td>기존652/696 → 수정696/696 (주입 응답)</td></tr><tr><td>시험</td><td>신규26/26·관련91/91</td></tr></table><h2>현재 연결 범위</h2><svg viewBox="0 0 780 180" role="img" aria-labelledby="flow"><title id="flow">공식 역ID 확보와 호선 필터는 검증했고 실시간 열차 선택 및 출발 환승 적용은 남았습니다.</title><rect x="10" y="20" width="220" height="120" fill="#fff" stroke="#161c28"/><text x="120" y="65" text-anchor="middle" font-size="19">공식 역ID696개</text><text x="120" y="104" text-anchor="middle" font-size="16">노선·역명587행 대응</text><path d="M230 80H270" stroke="#161c28" stroke-width="2"/><rect x="270" y="20" width="220" height="120" fill="#faf6eb" stroke="#a8720c"/><text x="380" y="65" text-anchor="middle" font-size="19">3호선 필터 복구</text><text x="380" y="104" text-anchor="middle" font-size="16">주입 응답 검증</text><path d="M490 80H540" stroke="#8a919d" stroke-dasharray="6 5"/><rect x="540" y="20" width="230" height="120" fill="#fff" stroke="#8a919d" stroke-dasharray="6 5"/><text x="655" y="65" text-anchor="middle" font-size="18">열차 선택·출발·환승</text><text x="655" y="104" text-anchor="middle" font-size="16">제품 연결 남음</text></svg><p><a href="../../{report.name}">검증 보고서</a> · <a href="../../../evidence/{state['tag']}/official-row-replay-and-join-v1.json">대응·미대응 전체 목록과 재생 원문</a> · <a href="readiness-catalog.json">21개 기능 원자료</a></p><h2>전체 기능의 근거와 남은 일</h2><div class="grid">{cards}</div><p>실시간 지하철 도착 응답·실탑승·새 경로 웹 표본은 미관측입니다. 기존 비교수치를 전량 재측정한 것으로 쓰지 않습니다. 브라우저 렌더링 미확인. 푸시·배포하지 않았습니다.</p></main></html>'''
(assets / 'mobility-readiness.html').write_text(page, encoding='utf8')
wiki = cs / 'wiki/teams/mobility.md'
backup(wiki, '공식지하철_역ID검증결과')
with wiki.open('a', encoding='utf8') as f:
    f.write(f'\n\n## {stamp} 공식 역ID 확보와 누락3호선 필터 검증 결과\n\n서울시2026-09-02 공개 역정보696행·19호선을 새 원문으로 확보하고696/696행 추출 대조를 확인했습니다. 기존좌표793행 중 정확노선/역명587행 대응·206행 미대응 목록을 보존했습니다. 경강선1081·서해선1093·신림선1094의 필터 누락을 고쳐 주입공식행652/696→696/696, 신규26/26·관련91/91 통과했습니다. [보고서](../records/reports/{report.name})·[시각화v35](../records/reports/assets/2026-10-09_mobility_readiness_v35/mobility-readiness.html). 정적자료·주입검증이며 실제696역 서비스제공·열차선택·출발/환승 적용은 미확인입니다. 새경로웹0개·지도개발자API0회·전체21판단4/9/8 유지·배포하지 않았습니다.\n')
debug = root / state['debug']
backup(debug, '지하철호선누락_결함종료')
debug.write_text(debug.read_text(encoding='utf8').replace('## 미해결', f'## 해결됨 (2026-10-09)\n\n공식표의 세 호선ID를 추가하고 신규26/26·관련91/91 및 공식행 주입 ABBA의652→696→696→652 필터 검증으로 확인했습니다. [보고서](../{report.name}). 실제 서비스 제공·출발/환승 연결은 별도 남습니다.\n\n발견 당시 상태: 미해결', 1), encoding='utf8')
for name, doc, content in [
    ('dataset_report', root / 'datasets/mobility/REPORT.md', f'\n\n## {stamp} 공식 실시간 지하철 역ID 자료 확보\n\n[원문·수집정보](raw/subway_realtime_station_20261009_v1/)는 서울시 공개 파일2026-09-02판696행·19호선이며 인증키 없이2026-10-09에 새로 받았습니다. 출처: 서울특별시, 공공누리 제1유형. [추출 JSON](processed/mobility/subway_realtime_stations_20260902_v1.json)은 원문696/696행과 일치하고 기존좌표793행의 정확노선/역명587행에 대응합니다. 미대응206행은 전체목록으로 보존했고 유사명/접두사로 채우지 않았습니다. 제품시간표·기동자료명세에는 아직 연결하지 않았습니다. 호선필터의 경강선/서해선/신림선 ID누락은 수정했고 공식행 주입652/696→696/696을 확인했습니다. 실제696역의 운행응답이 아닙니다. [보고서](../../final_project_cs/wiki/records/reports/{report.name})에 원문해시·명령·시험91/91과 남은 연결을 기록합니다.\n'),
    ('dataset_readme', root / 'datasets/mobility/README.md', '\n\n## 공식 실시간 지하철 역 번호 (2026-10-09 확보)\n\n[원문·수집 정보](raw/subway_realtime_station_20261009_v1/)와 [역ID 추출값](processed/mobility/subway_realtime_stations_20260902_v1.json)은 실시간 도착 응답을 계획 경로에 연결하기 위한 자료입니다. 원문696행·19호선, 출처: 서울특별시(공공누리 제1유형). [추출 코드](../../final_project_cs/scripts/mobility/build_subway_realtime_stations.py)는 새 출력파일만 생성합니다. 현재 cs 프로젝트 서버의 출발/환승 관측에는 이 대응값을 아직 연결하지 않았습니다. [현재 근거](REPORT.md)의 마지막 기록을 참조합니다.\n')]:
    assert sha(doc) == next(x['sha256'] for x in state['backups'] if x['source'] == doc.relative_to(root).as_posix()), doc
    with doc.open('a', encoding='utf8') as f: f.write(content)
save(ev / 'backup-manifest-v1.json', state['backups'])
proof = {'created_at': now.isoformat(), 'source_test_data_hashes': hashes, 'new_tests': 26, 'related_tests': 91,
         'before_failures': 3, 'official_station_rows': 696, 'official_lines': 19, 'source_row_matches': 696,
         'coordinate_rows': 793, 'exact_coordinate_matches': 587, 'unmatched_coordinates': 206,
         'injected_before_retained': 652, 'injected_after_retained': 696, 'actual_arrival_samples': 0,
         'new_route_web_samples': 0, 'map_developer_api_calls': 0, 'realtime_subway_connected': False,
         'features': 21, 'counts': catalog['counts'], 'deployed': False}
save(ev / 'verification-proof-v1.json', proof)
for script in ['fetch_subway_station_page_v1.py', 'fetch_subway_station_xlsx_v1.py', 'prepare_subway_station_map_v1.py',
               'prepare_subway_line_fix_v1.py', 'run_subway_station_map_v1.py', 'audit_subway_station_map_v1.py',
               'verify_subway_xlsx_extraction_v1.py', 'publish_subway_station_map_v1.py']:
    shutil.copy2(scratch / script, ev / script)
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
for item in state['backups']: assert sha(root / item['backup']) == item['sha256']
artifacts = [report, assets / 'mobility-readiness.html', assets / 'readiness-catalog.json', wiki,
             root / 'datasets/mobility/REPORT.md', root / 'datasets/mobility/README.md',
             ev / 'verification-proof-v1.json', ev / 'backup-manifest-v1.json']
save(ev / 'publication-validation-v1.json', {'source_hash_matches': len(hashes), 'backup_hash_matches': len(state['backups']),
     'local_links': links, 'artifact_hashes': {p.relative_to(root).as_posix(): sha(p) for p in artifacts}, 'browser_render_verified': False})
print(json.dumps({'report': report.relative_to(root).as_posix(), 'sources': len(hashes), 'backups': len(state['backups']),
                  'artifacts': len(artifacts), 'local_links': len(links)}, ensure_ascii=False))
