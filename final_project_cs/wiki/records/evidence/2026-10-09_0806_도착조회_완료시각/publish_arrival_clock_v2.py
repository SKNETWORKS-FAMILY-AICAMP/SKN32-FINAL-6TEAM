from pathlib import Path
from datetime import datetime
import collections
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
scratch = Path(__file__).parent
state = json.loads((scratch / 'arrival-clock-work-v1.json').read_text(encoding='utf8'))
ev = cs / 'wiki/records/evidence' / state['tag']
now = datetime.now().astimezone()
stamp = now.strftime('%Y-%m-%d_%H%M')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def backup(path, purpose):
    b = path.parent / '_backup' / (stamp + '_' + purpose) / path.name
    b.parent.mkdir(parents=True, exist_ok=True)
    assert not b.exists()
    shutil.copy2(path, b)
    state['backups'].append({'source': path.relative_to(root).as_posix(), 'backup': b.relative_to(root).as_posix(), 'sha256': sha(path)})


before = ET.parse(scratch / 'arrival-clock-before-v1.xml').getroot()
after = ET.parse(scratch / 'arrival-clock-related-v3.xml').getroot()
assert len(before.findall('.//testcase')) == 8 and len(before.findall('.//failure')) == 6
assert len(after.findall('.//testcase')) == 118
assert not after.findall('.//failure') and not after.findall('.//error')
new_count = sum('test_arrival_query_' in c.get('classname', '') for c in after.findall('.//testcase'))
assert new_count == 10
for prefix in ('arrival-clock-before-v1', 'arrival-clock-related-v1', 'arrival-clock-related-v2', 'arrival-clock-related-v3'):
    for ext in ('log', 'xml', 'run.json'):
        name = prefix + '.' + ext
        if (ev / name).exists():
            assert sha(ev / name) == sha(scratch / name)
        else:
            shutil.copy2(scratch / name, ev / name)
assert json.loads((ev / 'arrival-clock-related-v3.run.json').read_text())['exit_code'] == 0
files = ['app/domains/travel_ops/ports/data_sources/seoul_bus.py',
         'app/domains/travel_ops/instances/mobility/engine/departure_observer.py',
         'tests/unit/travel/mobility/test_arrival_query_clock_v1.py',
         'tests/unit/travel/mobility/test_arrival_query_assembly_v1.py']
cmd = ['C:/Users/playdata2/anaconda3/python.exe', '-m', 'ruff', 'check', *files]
run = subprocess.run(cmd, cwd=cs, capture_output=True, text=True, encoding='utf8')
(ev / 'ruff-v2.log').write_text(run.stdout + run.stderr, encoding='utf8')
save(ev / 'ruff-v2.run.json', {'command': cmd, 'exit_code': run.returncode})
assert run.returncode == 0
previous = cs / 'wiki/records/evidence/2026-10-09_0751_혼합운임_거리범위연결'
prior_proof = json.loads((previous / 'verification-proof-v1.json').read_text(encoding='utf8'))
hashes = dict(prior_proof['source_test_data_hashes'])
owned = {'final_project_cs/' + p for p in files}
assert all(sha(root / p) == h for p, h in hashes.items() if p not in owned)
for p in files:
    hashes['final_project_cs/' + p] = sha(cs / p)
assert len(hashes) == 213
save(ev / 'publication-attempt-v1.json', {'outcome': 'stopped before report and document mutations', 'reason': 'expected 212 hashes, actual 213; prior coverage excluded seoul_bus.py', 'prior_count': 210, 'new_source_and_tests': 3, 'preserved_evidence_verified_before_resume': True})
save(ev / 'source-test-data-hashes-v1.json', hashes)
report_name = stamp + '_버스조회_완료시각과_출발접근_재검증.md'
report = cs / 'wiki/records/reports' / report_name
assets = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v28'
assets.mkdir(exist_ok=False)
old_catalog = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v27/readiness-catalog.json'
prior = json.loads(old_catalog.read_text(encoding='utf8'))
catalog = {'created_at': now.isoformat(), 'scope': '도착 조회 대기 뒤 현재 출발·접근 재검증; 실제 운행 정확도 미측정',
           'counts': prior['counts'], 'features': prior['features'], 'prior_catalog_sha256': sha(old_catalog)}
for f in catalog['features']:
    if f['name'] in ('실시간 지하철·버스 도착', '첫차·막차·출발 역산'):
        f['need'] += ' 조회 완료 시각을 출발·접근·운행일·마감에 반영하고 정상 신규 응답을 미래로 거절하는 오류를 수정했습니다. 신규10·관련118통과, 지연 조립2조건은 통제 응답이며 실운행 검증이 아닙니다.'
assert len(catalog['features']) == 21
assert dict(collections.Counter(f['status'] for f in catalog['features'])) == catalog['counts']
save(assets / 'readiness-catalog.json', catalog)
e = html.escape
rows = ''.join('<tr>' + ''.join('<td>' + e(str(f[k])) + '</td>' for k in ('name', 'status', 'scope', 'metric', 'reason', 'need')) + '</tr>' for f in catalog['features'])
viz = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 검증 v28</title><style>
body{{margin:0;background:#fbfcfd;color:#161c28;font:16px/1.65 'Malgun Gothic',sans-serif}}main{{max-width:1280px;margin:auto;padding:24px}}section{{margin:24px 0;padding:24px;border:1px solid #dbe0ea}}h1{{font-size:30px}}.scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:720px}}th,td{{text-align:left;padding:12px;vertical-align:top;border-bottom:1px solid #dbe0ea}}th{{background:#f1f4f8}}.notice{{border-left:4px solid #a8720c;padding-left:16px}}a{{color:#2f5bd8}}button{{padding:8px 16px;margin:4px;border:1px solid #6d83a8;background:#fbfcfd;cursor:pointer}}button:focus-visible{{outline:3px solid #2f5bd8}}@media(max-width:600px){{main,section{{padding:12px}}h1{{font-size:24px}}}}
</style></head><body><main><h1>버스 응답을 기다린 뒤의 출발·접근 시간을 계산합니다</h1><p>생성 {e(now.isoformat())}. 새 응답의 확인시각이 조회 시작보다 늦다는 이유로 정상 예측을 거절하던 오류를 고쳤습니다.</p><p class="notice">시계를 진행시킨 HTTP 주입 응답입니다. 실제 지도 API·버스 탑승·도착 오차 측정이 아닙니다. 신규10/10·관련118/118 통과(신규10 포함). 전체21 기능 판단을 승격하지 않았습니다.</p>
<section><h2>2초 조회 지연을 넣은 같은 입력</h2><div class="scroll"><table><thead><tr><th>시간·조건</th><th>수정 전</th><th>수정 후</th></tr></thead><tbody><tr><td>조회 시작10:00:00 / 정상 응답10:00:02</td><td>확인시각이 미래라 예측 거절</td><td>확인시각 보존, 완료시각으로 검사</td></tr><tr><td>응답 뒤 출발 분 올림 / 접근6분</td><td>옛10:00 출발 모델 사용 가능</td><td>10:01 출발 / 10:07 준비 완료</td></tr><tr><td>응답의 7분 후 차량</td><td>모델 재검증16분</td><td>10:08 승차 분 / 10:13 도착 / 약13분 예상</td></tr><tr><td>통제 지연 때문에 방문 마감 불가능</td><td>옛 시각 사용 위험</td><td>출발 안내 보류</td></tr></tbody></table></div><p>마지막 행은120초를 시계에 더한 별도 통제 조건입니다. 실제 HTTP 지연을120초 측정한 것이 아닙니다. 13분은 합성 경로의 모델 예상이며 실제 도착 시간이 아닙니다. 처리 전후의 예상 차이를 정확도 향상으로 해석하지 않습니다.</p></section>
<section><h2>소스→제품 조립→안내 소비</h2><p>실제 버스 어댑터에 HTTP 응답을 주입해 조립과 관측 계산을 거쳤습니다. 신규 조립2/2에서 새 출발·예상 소요 문구와 마감 실패 시 안내 보류를 확인했습니다. 별도 로컬 개발 DB 공유 캐시 시험도 포함했으며 공급 API 실제 호출은0회입니다.</p><p>confirmed_at은 처음 응답 시각, evaluated_at은 이번 검사 시각입니다. 캐시 값의 원 확인시각을 새 시각으로 덮지 않고 공급 mkTm도 ETA에서 다시 차감하지 않습니다. 미래 환승 버스와 실제 탑승/위치 입력은 남았습니다.</p></section>
<section><h2>21개 기능의 현재 판단</h2><p>조건부 사용4/21 · 개선 필요9/21 · 추가 검증8/21. 기능 분류이며 전체 완료율이 아닙니다. 기존 웹 비교 수치는 이번 수정 뒤 재측정하지 않았습니다.</p><div role="group" aria-label="기능 필터"><button data-filter="전체" aria-pressed="true">전체 보기</button><button data-filter="조건부 사용" aria-pressed="false">조건부 사용 보기</button><button data-filter="개선 필요" aria-pressed="false">개선 필요 보기</button><button data-filter="추가 검증" aria-pressed="false">추가 검증 보기</button></div><p id="visible" aria-live="polite">21/21개 표시</p><div class="scroll"><table id="features"><thead><tr><th>기능</th><th>판단</th><th>범위</th><th>比較 수치</th><th>근거</th><th>더 필요한 부분</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<p>새 웹 경로0개 · 지도 개발자 API 직접 호출0회 · 실제 탑승/결제0회 · 배포하지 않았습니다. mock 서버 시험(화면 반응): 안 했음. 실서버 확인(서버 응답): 안 했음. 로컬 개발 DB/통제 HTTP 입력 시험을 cs 프로젝트 서버 응답 확인으로 부르지 않습니다. 브라우저 렌더링 미확인.</p><p><a href="../../{e(report_name)}">검증 보고서·백업</a> · <a href="../2026-10-09_mobility_readiness_v27/mobility-readiness.html">이전 혼합 예상액 검증</a></p></main><script>const rows=[...document.querySelectorAll('#features tbody tr')];for(const b of document.querySelectorAll('[data-filter]'))b.addEventListener('click',()=>{{for(const x of document.querySelectorAll('[data-filter]'))x.setAttribute('aria-pressed',String(x===b));for(const r of rows)r.hidden=b.dataset.filter!=='전체'&&r.cells[1].textContent!==b.dataset.filter;document.querySelector('#visible').textContent=rows.filter(r=>!r.hidden).length+'/21개 표시';}});</script></body></html>'''.replace('比較', '비교')
with (assets / 'mobility-readiness.html').open('x', encoding='utf8') as f:
    f.write(viz)
debug = cs / state['debug']
backup(debug, '도착조회_해결기록')
debug.write_text(debug.read_text(encoding='utf8').replace('## 미해결', '## 해결됨 (2026-10-09, 부분) — 조회 완료 시각·접근 재검증') + f'\n\n수정 전8조건 중6실패·2통과를 보존했습니다. 수정 후 신규10/10·관련118/118 통과, 통제 HTTP 어댑터의 제품 조립2조건에서 새 안내와 보류를 확인했습니다. 첫 확대97통과·DB권한으로1실패 및정리1오류 후 허용된 로컬 개발 DB 시험을 재실행해 통과했습니다. 실운행·실탑승·미래 환승 예측은 미해결입니다. [보고서](../{report_name}).\n', encoding='utf8')
wiki = cs / 'wiki/teams/mobility.md'
backup(wiki, '도착조회_검증결과')
with wiki.open('a', encoding='utf8') as f:
    f.write(f'\n\n## {stamp} 버스 조회 완료 시각·출발 접근 재검증 결과\n\n정상 신규 응답을 조회 시작보다 늦다는 이유로 거절하지 않고, 응답을 기다린 뒤 출발 분·접근 시간·운행일·마감을 다시 계산했습니다. 확인/공급/평가 시각은 구분합니다. 신규10/10·관련118/118 통과, 제품 조립2/2는 통제 응답이며 로컬 개발 DB 공유 캐시도 확인했습니다. [보고서](../records/reports/{report_name})·[시각화v28](../records/reports/assets/2026-10-09_mobility_readiness_v28/mobility-readiness.html). 실제 버스 오차/탑승·지하철 연결·독립 웹 표본은 남았고21기능 판단4/9/8 유지, 배포하지 않았습니다.\n')
save(ev / 'backup-manifest-v1.json', state['backups'])
proof = {'created_at': now.isoformat(), 'report': report.relative_to(root).as_posix(), 'new_tests': 10,
         'related_tests': 118, 'before_tests': 8, 'before_failures': 6, 'controlled_assembly_tests': 2,
         'source_test_data_hashes': hashes, 'initial_prior_source_matches': 210, 'initial_prior_artifact_matches': 6,
         'local_db_shared_cache_verified': True, 'sandbox_attempt': {'passed': 97, 'failed': 1, 'teardown_errors': 1},
         'permitted_retry_tests': [116, 118], 'features': 21, 'counts': catalog['counts'],
         'map_developer_api_calls': 0, 'new_web_routes': 0, 'provider_api_live_calls': 0,
         'actual_trips_or_payments': 0, 'http_service_verified': False, 'deployed': False, 'python': '3.12.7',
         'scope': 'clock advancement with injected HTTP transport; no actual response latency or arrival accuracy measured',
         'research': [{'url': 'https://gtfs.org/documentation/realtime/realtime-best-practices/',
                       'read_scope': 'document body; timestamp and freshness recommendations; Seoul is not GTFS feed'},
                      {'url': 'https://arxiv.org/abs/2106.13576', 'read_scope': 'abstract and metadata only; predictive uncertainty candidate'}]}
save(ev / 'verification-proof-v1.json', proof)
backup_links = '\n'.join(f'- [{Path(b["backup"]).name}]({Path(os.path.relpath(root / b["backup"], report.parent)).as_posix()})' for b in state['backups'])
report_text = f'''# 버스 조회 완료 시각과 출발·접근 재검증

정상 신규 버스 응답을 조회 시작 시각보다 늦다는 이유로 거절하던 오류를 고쳤습니다. 응답 대기 뒤 출발과 정류장 접근을 다시 계산하고, 방문 마감에 맞지 않으면 출발 안내를 보류합니다. 실제 버스 도착 오차·탑승 성공률을 검증한 것은 아닙니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 신규 시각·조립 조건 | 통과 | 10/10 = 100% |
| DB 포함 관련 시험 | 통과 | 118/118 = 100% |
| 지연 응답의 제품 조립 | 통과 | 2/2 = 100% |

생성 {now.isoformat()}. 파일명은 생성시각입니다. 신규10은 관련118에 포함되며 조립2도 신규10에 포함됩니다. 최초 코드/시험/자료210개·산출물6개 해시 일치를 확인했고 최종213개 해시를 보존했습니다. 이전 산출물은 그대로 두고 기존 코드·wiki를 백업한 뒤 계약부터 기록했습니다.

## 원인과 수정

버스 어댑터는 조회 시작 now로 선택했고, 공통 TravelSource._remember/stamp는 응답 뒤 confirmed_at을 찍습니다. 통제2초 지연에서 경과시간−2초가 되어 confirmation_in_future로 정상 예측을 거절했습니다. 출발 관측도 원 시작 시각보다 늦은 confirmed_at을 허용하지 않았습니다. 대체 모델로 넘어간 뒤 옛10:00 출발 문구를 만들 수 있었습니다.

소스는 응답을 마친 뒤 evaluated_at을 다시 읽고 다음 출발 분으로 올림한 뒤 접근 시간을 온전히 보존합니다. 원 confirmed_at을 바꾸지 않습니다. 관측은 그 완료 시각으로 출발·접근·운행일·마감을 계산하고 확인 시각이 완료 시각보다 뒤면 여전히 거절합니다. 평가 시각 역전·시간대 누락도 치명 상태로 판정합니다. 예측이 없어 대체 모델로 가는 경우도 알려진 조회 대기 뒤 계산합니다. evaluated_at 없는 기존 낮은 수준 콜백은 전달 now 기준의 호환 동작을 유지합니다.

합성 입력10:00:00 조회→10:00:02 응답→10:01 출발→6분 접근 후10:07 준비 완료에서7분 후 차량은10:07:02 예측이며 분 올림 승차는10:08,3분 모델 이동·2분 이탈로10:13 예상 도착입니다. 수정 전 같은 입력은 예측을 거절하고 모델16분으로 계산했고 수정 후 안내는 약13분·현재 버스 대기 반영입니다. 이3분 차이는 예측 적용 여부의 차이이지 실제 오차가3분 줄었다는 증거가 아닙니다.

6분30초 후 첫 차량이 접근보다 먼저 도착하면 둘째 차량을 고릅니다. 별도120초 시계 진행 조건은 접근·방문 마감이 겹쳐 안내를 보류했습니다. 실제 HTTP 응답을120초 기다린 측정은 아니며 주입 transport는 실제 HTTP timeout 동작을 재현하지 않습니다. 첫차/막차의 실제 운행 오차·현재 위치·탑승 관측·먼 미래 환승 버스 예측은 별도 남습니다.

## 시험 근거와 환경 실패 구분

수정 전8조건은6실패·2통과였습니다. 새 시험의 UTC와 KST를 같은 순간으로 비교하도록 표현을 고친 뒤, 기존8과 추가 제품 조립2까지 신규10/10·관련118/118을 확인했습니다. 최초 신규 응답 거절은 시각 문자열 비교 전 status에서 실패했으므로 표현 수정으로 재현을 숨긴 것이 아닙니다. 수정 전 시험도 백업했습니다.

첫 확대는97통과·1실패 및DB 정리1오류였고 로컬 개발 DB 접속이 실행 환경 권한에 막혔습니다. 코드 실패로 해석하거나 기록을 지우지 않았습니다. 허용된 실행 환경에서116/116을 재확인하고, 지연 응답 제품 조립2조건 추가 뒤 최종118/118·pytest 종료코드0·Python3.12.7·Ruff 통과입니다. pyreadline 콘솔 정리 오류가 첫 제한 실행에 출력됐으며 최종 허용 실행은 별도 로그로 보존했습니다. 원문 [로그·XML·명령·해시](../evidence/{state['tag']}/).

실제 SeoulBusArrival 어댑터에는 HTTP 응답만 주입했습니다. 조립 시험의 전달 정책도 같은지 확인했습니다. 제품 조립→현재 관측→출발 안내의 새 문구와 보류를 확인했고 기존 DB 공유 캐시 시험도 포함했습니다. 공유 캐시 시험은 시험용 키·행을 만든 뒤 자체 정리하며 실제 제공처를 호출하지 않습니다. 이동 전체575·출발 통합136을 이번에 다시 실행한 것은 아닙니다.

## 공식 문서·논문 확인

실행일2026-10-09에 [GTFS Realtime Best Practices](https://gtfs.org/documentation/realtime/realtime-best-practices/) 본문에서 피드 확인 시각과 개별 예측 시각·신선도를 구분하는 권고를 확인했습니다. 서울 API를 GTFS 피드라고 가정하지 않았고 기존 cache/provider 정책 수치를 바꾸지 않았습니다. 공급 mkTm을 ETA 기준으로 검증한 것은 아니므로 cache 경과와 함께 다시 차감하지 않습니다.

[Robust Real-Time Delay Predictions in a Network of High-Frequency Urban Buses](https://arxiv.org/abs/2106.13576)의 초록·메타도 확인했습니다. 예측 불확실성을 실제 검증에서 다룰 후보이며 전체 논문 구현·새 모델 학습·서울 성능 증거는 아닙니다. 이번 오류의 직접 증거는 수신 시각을 진행시킨 코드 재현입니다.

## 범위와 남은 일

변경: [버스 소스](../../../app/domains/travel_ops/ports/data_sources/seoul_bus.py), [출발 관측](../../../app/domains/travel_ops/instances/mobility/engine/departure_observer.py), [지연 시각 시험](../../../tests/unit/travel/mobility/test_arrival_query_clock_v1.py), [지연 제품 조립 시험](../../../tests/unit/travel/mobility/test_arrival_query_assembly_v1.py), [현재 이동 wiki](../../teams/mobility.md). 자료 파일·다른 작업자의 소스는 변경하지 않았습니다.

새 웹 경로0개·지도 개발자 API 직접 호출0회·버스 제공처 실제 호출0회·실제 탑승/결제0회입니다. 수치가 정렬된 새1.2km 안의 도보 표본, 혼합 할인 후 운임, 실시간 지하철 연결·실운행 오차·현재 탑승/위치 입력이 남았습니다. 전체21개 판단은 조건부4·개선9·추가검증8로 유지합니다. 커밋·푸시·배포·외부 메시지를 실행하지 않았습니다.

mock 서버 시험(화면 반응): 안 했음.
실서버 확인(서버 응답): 안 했음 — 로컬 개발 DB와 주입 HTTP 계산을 cs 프로젝트 서버 HTTP 응답 확인으로 부르지 않습니다.

[시각화v28](assets/2026-10-09_mobility_readiness_v28/mobility-readiness.html)는 전후 시간표와21개 기능의 수치·판단 근거·남은 작업을 보존합니다. 브라우저 렌더링은 미확인입니다. 전체 완료를 선언하지 않습니다.

## 백업

기존 코드·wiki·결함 문서와 시험 수정 전 판을 보존했습니다. [전체 백업 명세](../evidence/{state['tag']}/backup-manifest-v1.json).
{backup_links}
'''
with report.open('x', encoding='utf8') as f:
    f.write(report_text)
assert all(sha(root / p) == h for p, h in hashes.items())
assert all(sha(root / b['backup']) == b['sha256'] for b in state['backups'])
checked = []
for p in (report, assets / 'mobility-readiness.html'):
    data = p.read_text(encoding='utf8')
    refs = re.findall(r'\]\(([^)]+)\)', data) if p.suffix == '.md' else re.findall(r'href="([^"]+)"', data)
    for ref in refs:
        ref = html.unescape(ref)
        if ref.startswith(('http:', 'https:', '#')):
            continue
        target = (p.parent / ref).resolve()
        assert target.exists(), (p, ref)
        checked.append(target.relative_to(root).as_posix())
artifacts = [report, assets / 'mobility-readiness.html', assets / 'readiness-catalog.json',
             wiki, ev / 'verification-proof-v1.json', ev / 'backup-manifest-v1.json']
for p in artifacts:
    assert not re.search(r'(?:\d{1,3}\.){3}\d{1,3}|webhooks/|@[0-9]', p.read_text(encoding='utf8')), p
for name in ('prepare_arrival_clock_v1.py', 'run_arrival_clock_v1.py', 'run_arrival_clock_v2.py',
             'run_arrival_clock_v3.py', 'publish_arrival_clock_v1.py', 'publish_arrival_clock_v2.py'):
    assert not (ev / name).exists()
    shutil.copy2(scratch / name, ev / name)
save(ev / 'publication-validation-v1.json', {'created_at': now.isoformat(), 'source_hash_matches': len(hashes),
     'backup_hash_matches': len(state['backups']), 'local_links': checked,
     'artifact_hashes': {p.relative_to(root).as_posix(): sha(p) for p in artifacts},
     'browser_render_verified': False, 'scan_scope': [p.relative_to(root).as_posix() for p in artifacts]})
print(json.dumps({'report': report.relative_to(root).as_posix(), 'tag': state['tag'],
                  'new': 10, 'related': 118, 'hashes': len(hashes),
                  'backups': len(state['backups']), 'local_links': len(checked)}, ensure_ascii=False))
