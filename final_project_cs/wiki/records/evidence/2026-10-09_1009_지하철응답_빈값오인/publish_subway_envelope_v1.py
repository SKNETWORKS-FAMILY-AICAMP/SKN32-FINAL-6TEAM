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
state = json.loads((scratch / 'subway-envelope-work-v1.json').read_text(encoding='utf8'))
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
    state['backups'].append({'source': path.relative_to(root).as_posix(),
                             'backup': dst.relative_to(root).as_posix(), 'sha256': sha(path)})

before = ET.parse(ev / 'before-v1.xml').getroot()
after = ET.parse(ev / 'after-v1.xml').getroot()
assert len(before.findall('.//testcase')) == 28 and len(before.findall('.//failure')) == 16
assert len(after.findall('.//testcase')) == 97 and not after.findall('.//failure') and not after.findall('.//error')
assert json.loads((ev / 'after-v1.run.json').read_text(encoding='utf8'))['exit_code'] == 0
sample = json.loads((ev / 'public-sample-check-v1.json').read_text(encoding='utf8'))
audit = json.loads((ev / 'cache-recovery-abba-v1.json').read_text(encoding='utf8'))
assert sample['http_status'] == 200 and sample['normalized_success'] and sample['train_count'] == 5
assert audit['scenario_count'] == 4 and audit['runs'] == 16 and audit['provider_total'] == 18
files = ['app/domains/travel_ops/ports/data_sources/seoul_subway.py',
         'tests/unit/travel/test_subway_identity_v1.py', 'tests/unit/travel/test_subway_envelope_v1.py']
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
raw = (root / sample['raw_path']).parent
for path in raw.iterdir():
    if path.is_file(): hashes[path.relative_to(root).as_posix()] = sha(path)
for rel in files[:2]:
    old = root / next(x['backup'] for x in state['backups'] if x['source'] == 'final_project_cs/' + rel)
    diff = ''.join(difflib.unified_diff(old.read_text(encoding='utf8').splitlines(True),
        (cs / rel).read_text(encoding='utf8').splitlines(True), fromfile='before/' + rel, tofile='after/' + rel))
    with (ev / (Path(rel).stem + '-diff-v1.patch')).open('x', encoding='utf8') as f: f.write(diff)
save(ev / 'research-v1.json', {'checked_at': now.isoformat(), 'sources': [
    {'url': 'https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A',
     'scope': 'Full official response fields, INFO-000/INFO-200 and paging/sample limit read this turn.'},
    {'url': 'https://data.seoul.go.kr/dataList/OA-12764/A/1/datasetView.do',
     'scope': 'Official generation-time correction notice, file list and metadata read this turn.'}],
    'new_map_web_route_samples': 0, 'map_developer_api_calls': 0, 'public_subway_sample_requests': 1,
    'actual_provider_snapshots': 1, 'actual_boarding_or_payment_samples': 0,
    'method': 'Protocol/envelope and cache recovery fix, no new prediction algorithm. Research paper algorithm not needed to distinguish official result codes.'})

assets = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v36'
assets.mkdir(exist_ok=False)
prior_catalog = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v35/readiness-catalog.json'
catalog = json.loads(prior_catalog.read_text(encoding='utf8'))
catalog['created_at'] = now.isoformat()
catalog['scope'] = '지하철 도착 목록 누락·오류와 정상 빈 결과 구분 및 보관 회복; 실시간 출발/환승 미연결'
catalog['prior_catalog_sha256'] = sha(prior_catalog)
for feature in catalog['features']:
    if '실시간' in feature['name']:
        feature['need'] += ' 누락·잘못된 응답을 보관 전 걸러 정상 빈 결과와 구분했습니다. 신규28/28·관련97/97, 4통제상황 ABBA16회, 공개 서울역 샘플 HTTP200 1회·5행 정규화 확인. 샘플 전체18행 중5행이며 독립 경로/탑승 표본이 아닙니다. 열차선택·실시간 지하철 출발/환승 적용은 남았습니다.'
assert len(catalog['features']) == 21 and dict(Counter(x['status'] for x in catalog['features'])) == catalog['counts']
save(assets / 'readiness-catalog.json', catalog)
report = cs / 'wiki/records/reports' / (stamp + '_지하철_빈결과오인과_보관회복_검증.md')
source_backup = next(x['backup'] for x in state['backups'] if x['source'].endswith('/seoul_subway.py'))
with report.open('x', encoding='utf8') as f:
    f.write(f'''# 지하철 빈 결과 오인과 보관 회복 검증

도착 목록이 빠진 응답을 “열차가 없다”로 처리하던 결함을 수정했습니다. 오류를 보관하지 않으므로 다음 조회에서 회복된 응답을 읽습니다. 정상적인 열차 없음 결과는 계속 재사용합니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 신규 오류·회복 시험 | 통과 | 28/28 = 100% |
| 관련 회귀 시험 | 통과 | 97/97 = 100% |
| 통제 상황 교대 재생 | 확인 | 16/16 = 100% |
| 서울역 공개 샘플 HTTP 응답 | 확인 | 1/1 = 100% |

분모28은 10개 잘못된 응답의 신규조회/기존보관 각10건과 정상 빈 결과8건입니다. 97은 이를 포함한 관련 pytest의 실행 건수이며 오류 발생률·제품 정확도가 아닙니다. 16은 같은 입력4상황을 수정 전·후·후·전 순서로 실행한 횟수입니다.

## 바뀐 동작과 근거

서울시 공식 문서의 INFO-000(정상 처리)과 INFO-200(해당 데이터 없음)을 구분했습니다. 목록 누락·null을 허용하는 경우는 INFO-200뿐이고, 명시적 []는 기존 호환을 유지합니다. 목록이 아닌 값·dict가 아닌 행·INFO-200과 비어 있지 않은 목록이 함께 온 모순은 실패입니다. HTTP 응답 검사 위치를 보관 전으로 옮겨 body_error와 실제 호출 실패를 기록합니다. 기존 보관 응답도 공개 arrivals에서 검사하지만 외부 호출을 추가하지 않으므로 제공처 실패 수는 늘리지 않습니다.

| 통제 상황 | 수정 전 첫째→둘째 열차 수 / HTTP 횟수 | 수정 후 첫째→둘째 열차 수 / HTTP 횟수 |
|---|---|---|
| 목록 누락 후 정상 원문으로 회복 | 0→0 / 1회 | 실패→5 / 2회 |
| 잘못된 목록 후 정상 원문으로 회복 | 실패→실패 / 1회 | 실패→5 / 2회 |
| 정상 원문 재사용 | 5→5 / 1회 | 5→5 / 1회 |
| 공식 데이터 없음 재사용 | 0→0 / 1회 | 0→0 / 1회 |

신규 시험의 수정 전 결과는16실패·12통과, 수정 후 관련97건은 모두 통과했습니다. 기존 입력 형식 시험5건은 실패 집계 시점이 보관 전으로 옮겨져 기대 이유를 body_error로 바꾸었고 거부해야 한다는 조건은 유지했습니다. Ruff3파일 통과. 새 API 예측·임의 시간 보정·요금 보정은 하지 않았습니다.

## 실제 응답의 확인 범위

{sample['started_at']}부터 {sample['finished_at']}까지 서울시 공개 sample 요청을1회 수행했습니다. HTTP200·INFO-000, 원문3616바이트의5행을 공개 arrivals로 정규화했습니다. provider total은18이며 이번 요청은5행만 반환했습니다. 5/18은 수신 범위이고 모든 서울역 열차의 실시간 품질을 검증한 비율이 아닙니다. 원문 해시 `{sample['raw_sha256']}`. 원문과 정규화 결과는 git 밖 데이터 폴더에 그대로 보존했습니다.

mock 서버 시험(화면 반응): 안 했음.

실서버 확인(서버 응답): 서울시 공개 지하철 도착 API의 HTTP 응답1회 확인. 로컬 개발 서버·cs 프로젝트 서버의 출발 알림 응답은 안 했음.

새 네이버·다음·구글 경로 대조 표본0개, 지도 개발자 API0회, 실제 탑승·결제 측정0개입니다. 1개 공급자 스냅샷을 반복 재생한 것이므로 독립 검증16개로 부르지 않습니다. 공식 안내의 recptnDt 시차 보정은 열차 선택/출발 적용에서 따로 연결해야 합니다.

## 제품 경로와 남은 작업

현재 소비 중인 공개 도착 소스에서 빈 결과와 소스 실패를 잘못 섞는 원인을 제거했습니다. 실시간 출발 재검증의 차량 시각 대체는 아직 첫 버스만 연결되고 지하철은 모델 재계산입니다. 공식 역ID696행을 계획한 역/노선/방향/종착/열차 종류에 정확히 연결한 뒤, 접근 후 탑승할 열차 선택·지하철 시간 대체·환승 재계산을 검증해야 합니다. 누락 응답을 실패로 인식하는 것은 대체 소스까지 확보했다는 뜻이 아닙니다.

전체21개 기능의 판단은 조건부 사용4·개선 필요9·추가 검증8로 유지했습니다. 커밋·푸시·배포·외부 메시지 전송·알림 전송을 수행하지 않았습니다. HTML은 파일/링크/내용 검사만 하며 브라우저 화면 렌더링은 확인하지 못했습니다.

## 파일과 원문

- [시각화와21개 기능](assets/{assets.name}/mobility-readiness.html) — 이번 수정과 기능별 남은 근거.
- [검증 원문](../../records/evidence/{state['tag']}/) — before/after pytest·명령·Ruff·ABBA·공개 샘플 확인.
- [코드 백업](../../../{source_backup.removeprefix('final_project_cs/')}) — 변경 전 원본.
- [백업 명세](../../records/evidence/{state['tag']}/backup-manifest-v1.json) — 원본·백업 해시.
- [공개 샘플 원문 폴더](../../../../{raw.relative_to(root).as_posix()}/) — 원문·정규화·수집 정보.
- [결함 기록](debugs/{Path(state['debug']).name}) — 재현과 해결 범위.
- [서울시 공식 응답 명세](https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A) — 결과 코드·행·샘플 제한.
- [서울시 데이터 설명](https://data.seoul.go.kr/dataList/OA-12764/A/1/datasetView.do) — 생성 시각 시차 안내.

재현 명령은 검증 폴더의 before-v1.run.json·after-v1.run.json에 있습니다. 코드 해시와 데이터 해시는 verification-proof-v1.json에 보존했습니다. v11 지속 이동 관리와 사용자 요청의 최소 개선 단위이며 DoD 전체 완료 판정이 아닙니다.
''')

counts = catalog['counts']
cards = ''.join(f'<article data-status="{html.escape(x["status"])}"><span class="status">{html.escape(x["status"])}</span>'
    f'<h3>{html.escape(x["name"])}</h3><p>{html.escape(x["scope"])}</p><p><b>비교 근거</b> {html.escape(x["metric"])}</p>'
    f'<details><summary>판단 근거와 필요한 검증 보기</summary><p>{html.escape(x["reason"])}</p><p>{html.escape(x["need"])}</p></details></article>'
    for x in catalog['features'])
page = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>서울 이동 검증 v36 — 응답 오류와 열차 없음 구분</title>
<style>:root{--paper:#fbfcfd;--ink:#161c28;--accent:#a8720c;--link:#2f5bd8}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.65 system-ui,sans-serif}main{max-width:1100px;margin:auto;padding:32px 24px}h1{font-size:clamp(26px,4vw,40px);line-height:1.3}h2{margin-top:40px}a{color:var(--link)}.lead{max-width:75ch}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.metrics p{border-top:3px solid var(--accent);padding:12px 0}.metrics b{font-size:25px;display:block}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}article{padding:24px;border:1px solid #d6dce5;border-radius:4px}.status{color:var(--accent);font-weight:700}h3{margin:8px 0}details{border-top:1px solid #d6dce5;padding-top:12px}summary{cursor:pointer;font-weight:650}:focus-visible{outline:3px solid var(--link);outline-offset:4px}table{width:100%;border-collapse:collapse}th,td{text-align:left;border-bottom:1px solid #d6dce5;padding:12px 8px}.scroll{overflow-x:auto}select{font:inherit;max-width:100%;padding:8px;margin-left:8px}footer{border-top:1px solid #d6dce5;margin-top:32px;padding-top:16px}@media(max-width:600px){main{padding:24px 16px}.grid,.metrics{grid-template-columns:1fr}th,td{padding:8px 6px}article{padding:16px}}</style>
<main><p>서울 이동 검증 · v36 · __DATE__</p><h1>누락 응답을<br>“열차 없음”으로 처리하지 않습니다.</h1>
<p class="lead">잘못된 응답은 보관 전에 실패로 기록합니다. 다음 조회에서 회복된 응답을 읽고 정상 빈 결과는 재사용합니다. 지하철의 실제 열차 선택·출발·환승 시간 적용은 아직 남아 있습니다.</p>
<section class="metrics"><p><b>28/28</b>신규 통제 시험 통과</p><p><b>97/97</b>관련 회귀 시험 통과</p><p><b>1회 · 5행</b>서울시 공개 샘플 응답</p></section>
<h2>같은 입력을 수정 전·후·후·전으로 재생</h2><p>4가지 상황 × 4회 =16회입니다. 실제 스냅샷은1개이며 실제 탑승을 측정한 결과가 아닙니다.</p>
<div class="scroll"><table><thead><tr><th>상황</th><th>수정 전</th><th>수정 후</th></tr></thead><tbody>
<tr><td>목록 누락 뒤 회복</td><td>0→0 · 조회1회</td><td>실패→5 · 조회2회</td></tr><tr><td>잘못된 목록 뒤 회복</td><td>실패→실패 · 조회1회</td><td>실패→5 · 조회2회</td></tr><tr><td>정상 응답 재사용</td><td>5→5 · 조회1회</td><td>5→5 · 조회1회</td></tr><tr><td>공식 열차 없음 재사용</td><td>0→0 · 조회1회</td><td>0→0 · 조회1회</td></tr></tbody></table></div>
<p>공개 샘플은 total18건 중5건만 수신했습니다. 전체 역의 열차 품질·ETA 정확도 검증으로 세지 않습니다. 지도 개발자 API0회, 새 지도 웹 경로0개, 실제 탑승·결제0개.</p>
<h2>전체21개 기능의 현재 판단</h2><p>조건부 사용4개 · 개선 필요9개 · 추가 검증8개. 아래 숫자는 이전에 기록된 웹 대조·모델 검증이며 이번1개 샘플이 정확도를 높였다는 뜻이 아닙니다.</p>
<label for="filter">판단별 보기</label><select id="filter"><option value="all">전체21개</option><option>조건부 사용</option><option>개선 필요</option><option>추가 검증</option></select>
<section class="grid" aria-label="기능별 판단">__CARDS__</section>
<footer><a href="__REPORT__">검증 보고서 열기</a> · <a href="readiness-catalog.json">판단 원본 열기</a> · <a href="https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&amp;srvType=A">서울시 공식 명세</a><p>코드·원문 해시 보존. 커밋·푸시·배포 없음. 브라우저 화면 렌더링 미확인.</p></footer></main>
<script>document.getElementById('filter').addEventListener('change',function(){document.querySelectorAll('article').forEach(x=>{x.hidden=this.value!=='all'&&x.dataset.status!==this.value})})</script></html>'''
page = page.replace('__DATE__', now.isoformat()).replace('__CARDS__', cards).replace('__REPORT__', '../../' + report.name)
with (assets / 'mobility-readiness.html').open('x', encoding='utf8') as f: f.write(page)

debug = root / state['debug']
backup(debug, '응답오인_상태갱신')
debug.write_text(debug.read_text(encoding='utf8').replace('## 미해결', '## 해결됨 (2026-10-09) — 빈 결과/오류 및 보관 구분 범위', 1)
    + f'\n검증: 신규28/28·관련97/97, 공개 sample HTTP200 1회5행, 통제4상황 ABBA16회. 명령과 로그: 같은 이름의 evidence 폴더. [보고서](../{report.name}). 실시간 열차 선택/출발/환승 연결은 미해결이며 이번 결함의 응답·보관 구분 범위만 닫았습니다.\n', encoding='utf8')
wiki = cs / 'wiki/teams/mobility.md'
backup(wiki, '응답오인_결과기록')
with wiki.open('a', encoding='utf8') as f:
    f.write(f'\n\n## {stamp} 지하철 빈 결과 오인과 보관 회복 검증 결과\n\n목록 누락·오류를 정상 빈 결과로 바꾸던 결함을 고치고 보관 전 검사와 기존 보관 응답 재검사를 연결했습니다. 신규28/28·관련97/97·통제4상황 ABBA16회, 서울시 공개 sample HTTP200 1회5행 정규화를 확인했습니다. 샘플 total18 중5행이며 전체 역·ETA·탑승 검증이 아닙니다. [보고서](../records/reports/{report.name})·[시각화v36](../records/reports/assets/{assets.name}/mobility-readiness.html). 새 지도웹0개·지도개발자API0회, 실시간 지하철 출발/환승 미연결, 전체21판단4/9/8 유지·배포하지 않았습니다.\n')
for name in ['README.md', 'REPORT.md']:
    doc = root / 'datasets/mobility' / name
    backup(doc, '공개지하철샘플_기록')
    with doc.open('a', encoding='utf8') as f:
        f.write(f'\n\n## {stamp} 서울역 공개 도착 샘플1개\n\n[{raw.name}](raw/{raw.name}/)에 서울시 공개 sample HTTP200·INFO-000 원문3616바이트, 정규화5행과 수집정보를 보존했습니다. {sample["started_at"]} 조회1회이며 total18행 중5행만 반환했습니다. 원문SHA256 `{sample["raw_sha256"]}`. 4통제상황 ABBA16회 재생은 독립 표본이 아닙니다. 오류/정상빈결과/보관회복 검증에만 사용하고 실제ETA정확도·열차선택·탑승관측·출발/환승 연결을 주장하지 않습니다. 출처 서울특별시 OA-12764. 지도개발자API0회. [보고서](../../final_project_cs/wiki/records/reports/{report.name}).\n')
save(ev / 'backup-manifest-v1.json', {'created_at': now.isoformat(), 'backups': state['backups']})
proof = {'created_at': now.isoformat(), 'source_test_data_hashes': hashes,
         'new_tests': {'passed': 28, 'total': 28}, 'related_tests': {'passed': 97, 'total': 97},
         'before_failures': 16, 'before_total': 28, 'actual_provider_snapshots': 1, 'actual_provider_rows': 5,
         'features': 21, 'counts': counts, 'deployed': False, 'browser_render_verified': False}
save(ev / 'verification-proof-v1.json', proof)
scripts = ['prepare_subway_envelope_v1.py', 'run_subway_envelope_v1.py',
           'check_subway_envelope_sample_v1.py', 'audit_subway_envelope_v1.py', 'publish_subway_envelope_v1.py']
for script in scripts: shutil.copy2(scratch / script, ev / script)
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
artifacts = [report, assets / 'mobility-readiness.html', assets / 'readiness-catalog.json', wiki, debug,
             root / 'datasets/mobility/REPORT.md', root / 'datasets/mobility/README.md',
             ev / 'verification-proof-v1.json', ev / 'backup-manifest-v1.json']
save(ev / 'publication-validation-v1.json', {'source_hash_matches': len(hashes), 'backup_hash_matches': len(state['backups']),
     'local_links': links, 'artifact_hashes': {p.relative_to(root).as_posix(): sha(p) for p in artifacts},
     'feature_count': 21, 'browser_render_verified': False})
print(json.dumps({'report': report.relative_to(root).as_posix(), 'sources': len(hashes), 'backups': len(state['backups']),
                  'artifacts': len(artifacts), 'local_links': len(links)}, ensure_ascii=False))
