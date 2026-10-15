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
state = json.loads((scratch / 'subway-identity-work-v1.json').read_text(encoding='utf8'))
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
assert len(before.findall('.//testcase')) == 43 and len(before.findall('.//failure')) == 43
assert len(after.findall('.//testcase')) == 65 and not after.findall('.//failure') and not after.findall('.//error')
assert json.loads((ev / 'after-v1.run.json').read_text(encoding='utf8'))['exit_code'] == 0
replay = json.loads((ev / 'controlled-replay-v1.json').read_text(encoding='utf8'))
assert replay['old_fields_preserved'] == 11 and not replay['network_attempts']
source_rel = 'app/domains/travel_ops/ports/data_sources/seoul_subway.py'
test_rel = 'tests/unit/travel/test_subway_identity_v1.py'
cmd = [sys.executable, '-m', 'ruff', 'check', source_rel, test_rel]
lint = subprocess.run(cmd, cwd=cs, capture_output=True, text=True, encoding='utf8')
(ev / 'ruff-v1.log').write_text(lint.stdout + lint.stderr, encoding='utf8')
save(ev / 'ruff-v1.run.json', {'command': cmd, 'exit_code': lint.returncode})
assert lint.returncode == 0, lint.stdout
hashes = dict(state['prior_source_test_data_hashes'])
owned = {'final_project_cs/' + source_rel, 'final_project_cs/' + test_rel}
for name, digest in hashes.items():
    if name not in owned:
        assert sha(root / name) == digest, name
for rel in [source_rel, test_rel]:
    hashes['final_project_cs/' + rel] = sha(cs / rel)
old = root / state['backups'][0]['backup']
(ev / 'owned-source-diff-v1.patch').write_text(''.join(difflib.unified_diff(
    old.read_text(encoding='utf8').splitlines(True), (cs / source_rel).read_text(encoding='utf8').splitlines(True),
    fromfile='before/' + source_rel, tofile='after/' + source_rel)), encoding='utf8')
save(ev / 'research-v1.json', {'checked_at': now.isoformat(), 'sources': [
    {'url': 'https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A',
     'scope': 'official output field table; station/previous/next/terminal IDs, train number, order, seconds ETA'},
    {'url': 'https://gtfs.org/documentation/realtime/reference/',
     'scope': 'TripDescriptor unique trip resolution and StopTimeUpdate stop identity/sequence sections; design reference only, Seoul feed is not GTFS'},
    {'url': 'https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ESA.2026.9',
     'scope': 'publication metadata and abstract only; published 2026-08-25, dynamic timetable routing research; algorithm not applied'},
    {'url': 'https://arxiv.org/html/2603.12592v4',
     'scope': 'abstract/introduction/network model revisited; not the implementation basis for this parsing fix'}],
    'new_route_web_samples': 0, 'map_developer_api_calls': 0, 'actual_trips': 0})

assets = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v34'
assets.mkdir(exist_ok=False)
catalog = json.loads((cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v33/readiness-catalog.json').read_text(encoding='utf8'))
catalog['created_at'] = now.isoformat()
catalog['scope'] = '실시간 지하철 식별정보 보존과 잘못된 ETA 입력 처리; 출발·환승 적용은 아직 미연결'
catalog['prior_catalog_sha256'] = sha(cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v33/readiness-catalog.json')
names = [f['name'] for f in catalog['features']]
for f in catalog['features']:
    if '실시간' in f['name'] or f['name'] == '지하철 경로 산출':
        f['need'] += ' 도착 소스에서 역·다음 역·종착역·열차 번호 등 8개 필드를 보존하고 잘못된 ETA와 응답 목록을 구분했습니다. 신규43/43·관련65/65, 주입 ABBA에서 기존11필드 유지·제곱숫자 예외 해소를 확인했습니다. 정확 ID 대응과 열차/방향 선택 및 출발·환승 시각 반영은 여전히 미연결입니다. 실제 운행 관측이나 정확도 승격 근거가 아닙니다.'
assert len(catalog['features']) == 21 and dict(Counter(f['status'] for f in catalog['features'])) == catalog['counts']
save(assets / 'readiness-catalog.json', catalog)
report = cs / 'wiki/records/reports' / (stamp + '_지하철도착_식별정보보존과_입력오류_검증.md')
mapping = [('subwayId', 'line_id'), ('statnId', 'station_id'), ('statnFid', 'previous_station_id'),
           ('statnTid', 'next_station_id'), ('bstatnId', 'terminal_station_id'), ('bstatnNm', 'terminal_station'),
           ('btrainNo', 'train_number'), ('ordkey', 'arrival_order')]
table = '\n'.join(f'| `{a}` | `{b}` |' for a, b in mapping)
text = f'''# 지하철 도착 식별정보 보존과 입력 오류 검증

역·종착역·열차 번호를 버리던 읽기 과정을 고쳤습니다. 잘못된 도착시간과 응답 목록도 정상 결과와 구분합니다. 실제 출발·환승 시각에 지하철 도착정보를 적용한 것은 아닙니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 신규 통제 시험 | 통과 | 43/43 = 100% |
| 기존 동작 포함 관련 시험 | 통과 | 65/65 = 100% |
| 주입 응답 전후 재생 | 검증 | 8/8 = 100% |

생성 {now.isoformat()}. 신규43건은 관련65건에 포함됩니다. 재생8회는 정상/제곱숫자 2개 통제 입력을 이전·수정·수정·이전 순서로 반복한 것입니다. 새 운행 관측이나 독립 웹 표본8개로 세지 않습니다.

## 원인과 구현

서울 지하철 소스는 도착시간·메시지만 정규화하고 공식 역ID·열차 번호를 버렸습니다. 앞으로 계획 경로에 맞는 열차를 고르는 데 필요한 정보를 잃는 문제입니다. `str(value).isdigit()` 검사도 충분하지 않았습니다. 제곱숫자 U+00B2는 이 검사를 통과하지만 정수 변환이 실패합니다. Python의 긴 숫자 문자열 제한도 동일하게 예외를 냈습니다.

내부 도착 소스 응답 v1.1에 다음8필드를 추가했습니다. 기존 필드를 삭제하거나 Core 계약을 바꾸지 않았습니다.

| 원 응답 | 보존 필드 |
|---|---|
{table}

문자열 식별정보는 선행0까지 그대로 보존합니다. 비음수 정수는 문자열로 바꾸고 논리값·실수·객체·빈 문자열은 None으로 남깁니다. ID를 임의 생성하거나 지도 API를 부르지 않습니다. ETA는 비음수 정수 또는 ASCII 숫자 문자열만 받으며0초는 보존합니다. `eta_status`가 valid/missing/invalid를 구별합니다. 잘못된 목록 또는 잘못된 행은 `malformed_arrivals` 실패로 기록하며 빈 열차 목록으로 위장하지 않습니다. 기존 INFO-200·호선 필터·소스 관측시각·키 가림은 유지합니다.

## 실제 실행 근거

수정 전 신규43/43이 실패했고 수정 후 관련65/65가 통과했습니다. 신규 계약 필드 검사도 포함하므로43개의 실운영 사고로 해석하지 않습니다. [명령·원문 로그](../evidence/{state['tag']}/)에 종료코드·JUnit·Ruff 결과를 보존했습니다. [이번 소스 변경](../evidence/{state['tag']}/owned-source-diff-v1.patch)과 [신규 시험](../../../{test_rel})이 재현 근거입니다.

주입한 정상 응답과 잘못된 제곱숫자 응답을 이전·수정·수정·이전 순서로 재생했습니다. 정상 응답의 기존11필드는 전후 동일하며 식별정보가 추가됩니다. 제곱숫자는 이전2/2회 ValueError에서 수정2/2회 `eta_seconds=None, eta_status=invalid`로 바뀝니다. 외부 네트워크 연결을 차단했고 연결 시도0회였습니다. [재생 원문](../evidence/{state['tag']}/controlled-replay-v1.json). 실제 공급처에서 같은 오류가 관측됐다고 주장하지 않습니다.

초기 콘솔 점검은 PowerShell 파이프 인코딩 영향을 받을 수 있어 최종 근거로 쓰지 않았습니다. UTF-8 파일에 Unicode escape로 정의한 pytest와 재생 스크립트 결과만 사용했습니다.

## 공식 문서와 실행일까지 공개된 연구

[서울시 공식 명세](https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A)의 출력 필드 표를 확인해 승차 역·다음 역·종착역ID·열차번호·순번과 초 단위 ETA를 대응했습니다. [GTFS Realtime 명세](https://gtfs.org/documentation/realtime/reference/)는 특정 운행과 정차 지점을 식별해야 예측을 연결할 수 있음을 확인하는 설계 참고입니다. 서울 응답을 GTFS라고 해석하거나 두 체계의 ID를 같다고 가정하지 않았습니다.

2026-08-25 공개된 [T-REX](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ESA.2026.9)의 공개 초록·발행정보를 확인했습니다. 동적 시간표 갱신을 다루지만 이번 입력 정규화 문제는 공식 명세와 직접 재현으로 해결했습니다. 논문 본문 알고리즘을 적용하거나 성능을 검증했다고 쓰지 않습니다. [검색·읽기 범위](../evidence/{state['tag']}/research-v1.json).

## 제품 연결과 남은 일

현재 출발 관측의 콜백은 버스 도착정보만 연결돼 있습니다. 이번에는 그 관측기·조립·시간표 판정기를 변경하지 않았습니다. 계획 경로 역ID와 응답 역ID의 검증된 대응표, 방향/다음 역, 단축 운행의 종착역, 일반/급행 정차 여부, 생성시각·접근시간을 대조한 열차 선택이 먼저 필요합니다. 실제 탑승·위치 관측, 미래 환승 차량의 재계산은 별도 남습니다. 빠른 첫 열차를 무조건 덮어쓰지 않았습니다.

[전체21개 시각화v34](assets/2026-10-09_mobility_readiness_v34/mobility-readiness.html)는 조건부 사용4·개선 필요9·추가 검증8을 유지합니다. 이 수는 완료율이 아닙니다. 브라우저 렌더링은 미확인입니다. 새 경로 웹 표본0개·지도 개발자 API 호출0회·실제 탑승/결제0회입니다.

mock 서버 시험(화면 반응): 안 했음.
실서버 확인(서버 응답): 안 했음 — 주입 HTTP 응답의 읽기와 로컬 계산 시험이며 cs 프로젝트 서버 HTTP를 확인하지 않았습니다.

커밋·푸시·배포·외부 메시지·결제를 실행하지 않았습니다.

## 백업과 재현

[백업 명세](../evidence/{state['tag']}/backup-manifest-v1.json)에 변경 전 코드·wiki·결함 기록을 보존합니다. 소스 원본은 [백업 파일](../../../{Path(state['backups'][0]['backup']).relative_to('final_project_cs').as_posix()})입니다. 근거 폴더의 실행 스크립트는 보존용 사본이고 재현 정본은 워크스페이스 `.tmp/mobility_complete_20261008`입니다. 기록된 명령을 그대로 사용하며 수정 전 검증에는 소스 백업판을 사용합니다.
'''
with report.open('x', encoding='utf8') as f:
    f.write(text)

cards = ''.join('<article data-status="' + html.escape(f['status']) + '"><h3>' + html.escape(f['name']) + '</h3><p class="status">' + html.escape(f['status']) + '</p>' + ''.join('<p><b>' + label + '</b> ' + html.escape(f[key]) + '</p>' for label, key in [('범위', 'scope'), ('비교 수치', 'metric'), ('판단 근거', 'reason'), ('더 필요한 일', 'need')]) + '</article>' for f in catalog['features'])
page = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 검증 v34</title>
<style>body{{margin:0;background:#fbfcfd;color:#161c28;font:16px/1.65 system-ui,sans-serif}}main{{max-width:1120px;margin:auto;padding:32px 20px}}h1{{font-size:28px}}h2{{font-size:22px}}h3{{font-size:19px;margin-top:0}}a{{color:#2f5bd8}}.note{{border-left:4px solid #a8720c;padding:12px 20px;background:#faf6eb}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr));gap:16px}}article{{padding:24px;border:1px solid #d8dce2;border-radius:8px;background:#fff}}.status{{font-weight:600;color:#8a5900}}b{{font-weight:600}}svg{{width:100%;height:auto}}button{{font:inherit;border:1px solid #8a919d;background:white;padding:8px 14px;border-radius:4px;cursor:pointer;margin:0 8px 12px 0}}button[aria-pressed=true]{{border:2px solid #2f5bd8}}button:focus-visible{{outline:3px solid #2f5bd8;outline-offset:3px}}table{{width:100%;border-collapse:collapse}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #d8dce2}}[hidden]{{display:none}}@media(max-width:600px){{main{{padding:20px 16px}}article{{padding:16px}}}}</style>
<main><h1>서울 이동 모듈 검증 v34</h1><p>열차를 구별할 정보를 보존했습니다. 실시간 지하철을 출발·환승 계산에 적용하는 작업은 남아 있습니다.</p><p>{now.isoformat()}</p>
<div class="note">조건부 사용4 · 개선 필요9 · 추가 검증8 / 전체21개. 완료율이 아닙니다. 이번에는 새 경로 웹 표본과 실제 탑승 관측을 추가하지 않았습니다.</div>
<h2>이번 검증</h2><table><tr><th>대상</th><th>전후 결과</th></tr><tr><td>신규 통제 시험</td><td>수정 전43실패 → 수정 후43/43 통과</td></tr><tr><td>기존 동작 포함 시험</td><td>65/65 통과</td></tr><tr><td>정상 응답</td><td>기존11필드 유지 + 식별정보8필드 추가</td></tr><tr><td>제곱숫자 ETA</td><td>이전 예외2/2 → 수정 invalid 처리2/2</td></tr></table>
<h2>정보가 이어지는 범위</h2><svg viewBox="0 0 780 180" role="img" aria-labelledby="flowtitle"><title id="flowtitle">공식 응답의 식별정보 보존까지 수정했고, 정확 열차 선택과 출발 환승 연결은 남았습니다.</title><rect x="10" y="20" width="220" height="120" fill="#fff" stroke="#161c28"/><text x="120" y="65" text-anchor="middle" font-size="19">역·종착·열차 정보</text><text x="120" y="104" text-anchor="middle" font-size="16">공식 응답</text><path d="M230 80H270" stroke="#161c28" stroke-width="2"/><rect x="270" y="20" width="220" height="120" fill="#faf6eb" stroke="#a8720c"/><text x="380" y="65" text-anchor="middle" font-size="19">보존·입력 오류 구분</text><text x="380" y="104" text-anchor="middle" font-size="16">이번 수정·통제 시험</text><path d="M490 80H540" stroke="#8a919d" stroke-width="2" stroke-dasharray="6 5"/><rect x="540" y="20" width="230" height="120" fill="#fff" stroke="#8a919d" stroke-dasharray="6 5"/><text x="655" y="65" text-anchor="middle" font-size="18">열차 선택·출발·환승</text><text x="655" y="104" text-anchor="middle" font-size="16">제품 연결 남음</text></svg>
<p><a href="../../{report.name}">이번 검증 보고서</a> · <a href="../../../evidence/{state['tag']}/controlled-replay-v1.json">주입 응답 재생 원문</a> · <a href="readiness-catalog.json">21개 기능 원자료</a></p>
<h2>전체 기능별 근거와 남은 일</h2><nav aria-label="판정 필터">{''.join('<button type="button" data-filter="'+s+'" aria-pressed="'+('true' if s=='전체' else 'false')+'">'+s+'</button>' for s in ['전체', '조건부 사용', '개선 필요', '추가 검증'])}</nav><div class="grid">{cards}</div>
<p>예상·개발 비교·독립 검증·실제 탑승은 구별합니다. 기존 비교 수치는 새 정책으로 전량 재측정한 것이 아닙니다. 브라우저 렌더링 미확인. 커밋·푸시·배포하지 않았습니다.</p></main>
<script>document.querySelectorAll('[data-filter]').forEach(b=>b.addEventListener('click',()=>{{document.querySelectorAll('[data-filter]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));document.querySelectorAll('article[data-status]').forEach(a=>a.hidden=b.dataset.filter!=='전체'&&a.dataset.status!==b.dataset.filter)}}));</script></html>'''
with (assets / 'mobility-readiness.html').open('x', encoding='utf8') as f:
    f.write(page)

wiki = cs / 'wiki/teams/mobility.md'
backup(wiki, '지하철식별_검증결과')
with wiki.open('a', encoding='utf8') as f:
    f.write(f'\n\n## {stamp} 지하철 식별정보 보존과 입력 오류 검증 결과\n\n공식 역·종착역·열차 식별8필드를 보존하고 ETA 정상/누락/오류와 잘못된 목록을 구분했습니다. 신규43/43·관련65/65 통과, 주입2입력 ABBA8회에서 기존11필드 유지와 제곱숫자 예외 해소를 확인했습니다. [보고서](../records/reports/{report.name})·[시각화v34](../records/reports/assets/2026-10-09_mobility_readiness_v34/mobility-readiness.html). 정확 ID 대응·열차 선택·출발/환승 시각 적용은 미연결이며 새 웹·운행 관측은0개, 전체21판단4/9/8 유지·배포하지 않았습니다.\n')
debug = root / state['debug']
backup(debug, '지하철입력_부분해결')
original = debug.read_text(encoding='utf8')
debug.write_text(original.replace('## 미해결', f'## 해결됨 (2026-10-09, 부분) — 식별정보 소실·잘못된 입력 처리\n\n신규43/43·관련65/65 및 controlled-replay-v1.json의 이전·수정·수정·이전 재생으로 검증했습니다. 정확 열차 선택·출발/환승 연결은 여전히 남습니다. 명령·원문: [보고서](../{report.name}).\n\n발견 당시 상태: 미해결', 1), encoding='utf8')
save(ev / 'backup-manifest-v1.json', state['backups'])
proof = {'created_at': now.isoformat(), 'source_test_data_hashes': hashes, 'new_tests': 43, 'related_tests': 65,
         'before_failures': 43, 'controlled_cases': 2, 'controlled_replays': 8, 'old_fields_preserved': 11,
         'new_identity_fields': 8, 'map_developer_api_calls': 0, 'new_web_samples': 0, 'actual_trips': 0,
         'network_attempts': 0, 'http_service_verified': False, 'realtime_subway_connected': False,
         'features': 21, 'counts': catalog['counts'], 'deployed': False}
save(ev / 'verification-proof-v1.json', proof)
for name in ['prepare_subway_identity_v1.py', 'run_subway_identity_v1.py', 'audit_subway_identity_v1.py', 'publish_subway_identity_v1.py']:
    shutil.copy2(scratch / name, ev / name)
links = []
for source in [report, assets / 'mobility-readiness.html']:
    content = source.read_text(encoding='utf8')
    hrefs = re.findall(r'\]\(([^)]+)\)', content) if source.suffix == '.md' else re.findall(r'href="([^"]+)"', content)
    for href in hrefs:
        if href.startswith(('https://', 'http://', '#')):
            continue
        target = (source.parent / href).resolve()
        assert target.exists(), href
        links.append(target.relative_to(root).as_posix())
for name, digest in hashes.items():
    assert sha(root / name) == digest, name
for item in state['backups']:
    assert sha(root / item['backup']) == item['sha256']
artifacts = [report, assets / 'mobility-readiness.html', assets / 'readiness-catalog.json', wiki,
             ev / 'verification-proof-v1.json', ev / 'backup-manifest-v1.json']
save(ev / 'publication-validation-v1.json', {'source_hash_matches': len(hashes), 'backup_hash_matches': len(state['backups']),
     'local_links': links, 'artifact_hashes': {p.relative_to(root).as_posix(): sha(p) for p in artifacts}, 'browser_render_verified': False})
print(json.dumps({'report': report.relative_to(root).as_posix(), 'sources': len(hashes), 'backups': len(state['backups']),
                  'artifacts': len(artifacts), 'local_links': len(links), 'features': 21}, ensure_ascii=False))
