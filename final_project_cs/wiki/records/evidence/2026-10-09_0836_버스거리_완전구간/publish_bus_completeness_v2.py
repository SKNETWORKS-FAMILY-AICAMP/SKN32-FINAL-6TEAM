from pathlib import Path
from datetime import datetime
import collections
import hashlib
import html
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
sys.path.insert(0, str(cs))
scratch = Path(__file__).parent
state = json.loads((scratch / 'bus-distance-work-v3.json').read_text(encoding='utf8'))
ev = cs / 'wiki/records/evidence' / state['tag']
now = datetime.now().astimezone()
stamp = now.strftime('%Y-%m-%d_%H%M')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def save(p, value):
    with p.open('x', encoding='utf8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def backup(p, purpose):
    b = p.parent / '_backup' / (stamp + '_' + purpose) / p.name
    b.parent.mkdir(parents=True, exist_ok=True)
    assert not b.exists()
    shutil.copy2(p, b)
    state['backups'].append({'source': p.relative_to(root).as_posix(),
                            'backup': b.relative_to(root).as_posix(), 'sha256': sha(p)})


def result(name):
    t = ET.parse(ev / (name + '.xml')).getroot()
    return {'tests': len(t.findall('.//testcase')), 'failures': len(t.findall('.//failure')),
            'errors': len(t.findall('.//error')),
            'exit_code': json.loads((ev / (name + '.run.json')).read_text(encoding='utf8'))['exit_code']}


test_results = {n: result(n) for n in ['before-v1', 'after-v1', 'after-v2',
                                     'profile-before-v1', 'combined-after-v1']}
assert test_results['combined-after-v1'] == {'tests': 112, 'failures': 0, 'errors': 0, 'exit_code': 0}
assert test_results['before-v1']['failures'] == 18
assert test_results['profile-before-v1']['failures'] == 15
distance = json.loads((ev / 'existing-distance-audit-v2.json').read_text(encoding='utf8'))
profile = json.loads((ev / 'existing-profile-audit-v1.json').read_text(encoding='utf8'))
assert not distance['differences'] and not profile['differences']
assert distance['equal_adjacent'] == distance['adjacent_queries'] == 41103
assert profile['equal_adjacent'] == profile['adjacent_queries'] == 82206
files = ['app/domains/travel_ops/instances/mobility/engine/bus.py',
         'app/domains/travel_ops/instances/mobility/engine/bus_profile.py',
         'tests/unit/travel/mobility/test_bus_distance_completeness_v1.py',
         'tests/unit/travel/mobility/test_bus_profile_completeness_v1.py']
cmd = [sys.executable, '-m', 'ruff', 'check', *files]
r = subprocess.run(cmd, cwd=cs, capture_output=True, text=True, encoding='utf8')
with (ev / 'ruff-v1.log').open('x', encoding='utf8') as f:
    f.write(r.stdout + r.stderr)
save(ev / 'ruff-v1.run.json', {'command': cmd, 'exit_code': r.returncode})
assert r.returncode == 0
prior_ev = cs / 'wiki/records/evidence/2026-10-09_0822_도보비교_입력검증'
hashes = dict(json.loads((prior_ev / 'verification-proof-v1.json').read_text(encoding='utf8'))['source_test_data_hashes'])
owned = {'final_project_cs/' + p for p in files}
assert all(sha(root / p) == h for p, h in hashes.items() if p not in owned)
for p in files:
    hashes['final_project_cs/' + p] = sha(cs / p)
for audit in (distance, profile):
    for p, h in audit['inputs'].items():
        assert sha(root / p) == h
        hashes[p] = h
save(ev / 'source-test-data-hashes-v1.json', hashes)

# 같은 합성 누락 입력으로 출발 관측의 전후를 재현한다.
from tests.unit.travel.mobility.test_departure_observer_v1 import scene, call, prediction
from tests.unit.travel.mobility.test_bus_profile_unit import build
from app.domains.travel_ops.instances.mobility.engine.bus_profile import BusSegProfile


def old_module(filename, name):
    b = next(x for x in state['backups'] if x['source'].endswith('/' + filename))
    spec = importlib.util.spec_from_file_location(name, root / b['backup'])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


old_bus = old_module('bus.py', 'app.domains.travel_ops.instances.mobility.engine.bus_before_complete')
old_prof = old_module('bus_profile.py', 'bus_profile_before_publish')
traces = []
for mode in ('distance', 'profile'):
    values = {}
    for version in ('before', 'after'):
        runtime, context = scene()
        runtime._v.bus.stops['100'] = [s for s in runtime._v.bus.stops['100'] if s['seq'] != 6]
        if version == 'before':
            runtime._v.bus.distance_m = old_bus.BusRoutes.distance_m.__get__(runtime._v.bus)
        if mode == 'profile':
            p = build([])
            cls = old_prof.BusSegProfile if version == 'before' else BusSegProfile
            runtime._v.bus_prof = cls(p.index, p.ends, p.arr, p.meta)
        got = call(runtime, context, bus_arrival=prediction)
        values[version] = {'status': got['status'], 'reason': got.get('reason'),
                           'departure_at': got.get('departure_at'), 'eta_min': got.get('eta_min'),
                           'leg_results': got.get('leg_results')}
    assert values['before']['status'] == 'realtime' and values['after']['status'] == 'fatal'
    assert values['after']['eta_min'] is None and values['after']['departure_at'] is None
    traces.append(dict(mode=mode, **values))
save(ev / 'controlled-departure-traces-v1.json', {'traces': traces,
     'scope': 'synthetic missing seq6, not actual missing source data or passenger observation'})
save(ev / 'audit-attempt-v1.json', {'status': 'failed_before_data_read',
    'reason': 'The audit used PROCESSED before CLI environment initialization.',
    'recovery': 'v2 uses cli_processed(); no path configuration or data changed.',
    'original_failed_script_preserved': 'audit_bus_distance_v1.py'})
save(ev / 'research-v1.json', {'checked_at': now.isoformat(), 'sources': [
    {'url': 'https://www.data.go.kr/data/15000193/openapi.do',
     'scope': 'HTML response field table names fullSectDist as 구간거리 and marks it optional; full guide not read.',
     'not_established': 'Unit convention, measured road coverage, equivalence to card charging distance.'},
    {'url': 'https://news.seoul.go.kr/traffic/transfer_discount',
     'scope': 'Official integrated fare overview; no fare rule change in this unit.'}],
    'papers_applied': [], 'reason': 'Continuous sequence and numeric validity are input invariants; no new research algorithm applied.'})

report_name = stamp + '_버스거리와_통행시간_완전구간_검증.md'
report = cs / 'wiki/records/reports' / report_name
assets = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v30'
assets.mkdir(exist_ok=False)
old_catalog = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v29/readiness-catalog.json'
catalog = json.loads(old_catalog.read_text(encoding='utf8'))
catalog['created_at'] = now.isoformat()
catalog['scope'] = '버스 거리·통행시간 사슬 검증; 새 웹/실제 운행/혼합 할인 운임 검증 아님'
catalog['prior_catalog_sha256'] = sha(old_catalog)
for f in catalog['features']:
    if f['name'] in ('버스 직행·환승 산출', '대중교통 전체 소요'):
        f['need'] += ' 중간 정류장 누락·중복을 짧은 승차 시간으로 합산하지 않도록 거리·프로파일 경로를 보강했습니다. 신규40/40·관련112/112, 기존 인접 거리41,103건과 프로파일82,206계산의 이전 결과를 유지했습니다. 누락 시 대체 경로 확보 자체와 실제 탑승 검증은 남았습니다.'
assert len(catalog['features']) == 21
assert dict(collections.Counter(f['status'] for f in catalog['features'])) == catalog['counts']
save(assets / 'readiness-catalog.json', catalog)
e = html.escape
rows = ''.join('<tr>' + ''.join('<td>' + e(str(f[k])) + '</td>'
       for k in ('name', 'status', 'scope', 'metric', 'reason', 'need')) + '</tr>' for f in catalog['features'])
page = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 검증 v30</title><style>body{{margin:0;background:#fbfcfd;color:#161c28;font:16px/1.65 'Malgun Gothic',sans-serif}}main{{max-width:1280px;margin:auto;padding:24px}}section{{border:1px solid #dbe0ea;padding:24px;margin:24px 0}}h1{{font-size:30px}}table{{width:100%;border-collapse:collapse;min-width:720px}}th,td{{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #dbe0ea}}th{{background:#f1f4f8}}.scroll{{overflow:auto}}.notice{{border-left:4px solid #a8720c;padding-left:16px}}a{{color:#2f5bd8}}button{{padding:8px 16px;margin:4px;border:1px solid #6b7488;background:#fbfcfd;cursor:pointer}}button:focus-visible{{outline:3px solid #2f5bd8}}@media(max-width:600px){{main,section{{padding:12px}}h1{{font-size:24px}}}}</style></head><body><main>
<h1>빠진 버스 구간을 짧은 이동 시간으로 안내하지 않습니다</h1><p>생성 {e(now.isoformat())}. 거리 합산과 정류장별 통행시간 계산에서 양 끝·중간 순번·중복을 확인합니다.</p><p class="notice">신규40/40 · 관련112/112 통과(신규40 포함). 기존 정상 자료의 값은 유지됐습니다. 새 웹 경로·실제 탑승·결제 검증은0건입니다.</p>
<section><h2>같은 누락 입력의 전후</h2><div class="scroll"><table><thead><tr><th>통제 입력</th><th>이전</th><th>수정 후</th></tr></thead><tbody><tr><td>5→8 정류장, 중간6 누락</td><td>3km 중 남은2km만 계산</td><td>완전한 구간이 아니므로 거리 합을 내지 않음</td></tr><tr><td>같은 누락 + 통행시간 자료의 거리 대체</td><td>5→7을 인접 구간으로 취급</td><td>빠진 사슬을 검사하고 소요를 내지 않음</td></tr><tr><td>현재 출발 안내에 연결</td><td>짧아진 승차 시간을 포함해 안내 성공</td><td>자료 결함 상태로 안내 보류, 출발·ETA 출력 안 함</td></tr><tr><td>유효 통행시간이 있고 거리 칸만 비어 있음</td><td>통행시간 사용</td><td>통행시간 사용 유지; 불필요한 거리 대체 없음</td></tr></tbody></table></div><p>합성 입력의 전후입니다. 현재 저장 자료에서 중간 누락이 발견됐다는 뜻은 아닙니다. 안내 보류는 기존 fatal 규칙이며 대체 경로 확보가 완료됐다는 뜻도 아닙니다.</p></section>
<section><h2>기존 자료 전수 대조</h2><div class="scroll"><table><thead><tr><th>대조 범위</th><th>이전 결과 유지</th><th>조건</th></tr></thead><tbody><tr><td>인접 구간 거리</td><td>41,103/41,103</td><td>717노선·정류장41,820행</td></tr><tr><td>노선 전체 거리</td><td>717/717</td><td>각 노선 처음→마지막</td></tr><tr><td>인접 구간 통행시간</td><td>82,206/82,206</td><td>41,103구간 × p50/p90</td></tr><tr><td>노선 전체 통행시간</td><td>1,434/1,434</td><td>717노선 × p50/p90</td></tr></tbody></table></div><p>통행시간 대조는 평일10시·최소5일 자료·거리 대체20km/h를 고정한 계산 재생입니다. 실제 운행 속도나 새로운 독립 표본을 측정한 것이 아닙니다.</p></section>
<section><h2>21개 기능의 현재 판단</h2><p>조건부 사용4/21 · 개선 필요9/21 · 추가 검증8/21. 전체 완료율이 아닙니다.</p><div role="group" aria-label="기능 필터"><button data-filter="전체" aria-pressed="true">전체 보기</button><button data-filter="조건부 사용" aria-pressed="false">조건부 사용 보기</button><button data-filter="개선 필요" aria-pressed="false">개선 필요 보기</button><button data-filter="추가 검증" aria-pressed="false">추가 검증 보기</button></div><p id="visible" aria-live="polite">21/21개 표시</p><div class="scroll"><table id="features"><thead><tr><th>기능</th><th>판단</th><th>범위</th><th>비교 수치</th><th>근거</th><th>더 필요한 부분</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<p>누락 자료 복구·대체 경로 확보·혼합 할인 후 운임·新 웹 대조 표본은 남았습니다.</p><p>지도 개발자 API 직접 호출0회 · 실제 탑승/결제0회 · 커밋·푸시·배포하지 않았습니다. 브라우저 렌더링 미확인.</p><p><a href="../../{e(report_name)}">검증 보고서·백업</a> · <a href="../2026-10-09_mobility_readiness_v29/mobility-readiness.html">이전 도보 비교 검증</a></p></main><script>const rows=[...document.querySelectorAll('#features tbody tr')];for(const b of document.querySelectorAll('[data-filter]'))b.addEventListener('click',()=>{{for(const x of document.querySelectorAll('[data-filter]'))x.setAttribute('aria-pressed',String(x===b));for(const r of rows)r.hidden=b.dataset.filter!=='전체'&&r.cells[1].textContent!==b.dataset.filter;document.querySelector('#visible').textContent=rows.filter(r=>!r.hidden).length+'/21개 표시';}});</script></body></html>'''.replace('新 웹', '새 웹')
with (assets / 'mobility-readiness.html').open('x', encoding='utf8') as f:
    f.write(page)
wiki = cs / 'wiki/teams/mobility.md'
debug = cs / state['debug']
backup(wiki, '버스완전구간_검증결과')
backup(debug, '버스완전구간_결함종료')
with wiki.open('a', encoding='utf8') as f:
    f.write(f'\n\n## {stamp} 버스 거리·통행시간 완전 구간 검증 결과\n\n중간 정류장 누락·중복·잘못된 순번을 일부 거리/통행시간으로 누적하는 두 계산 경로를 고쳤습니다. 신규40/40·관련112/112 통과, 현재 출발 재검증도 누락 시 기존 fatal 규칙으로 안내를 보류합니다. 유효 프로파일은 거리 누락만으로 버리지 않습니다. 기존 인접 거리41,103/41,103·노선717/717, 통행시간 고정 조건 재생82,206/82,206·노선1,434/1,434에서 이전 결과가 같습니다. [보고서](../records/reports/{report_name})·[시각화v30](../records/reports/assets/2026-10-09_mobility_readiness_v30/mobility-readiness.html). 실제 데이터 누락/운행 오차 개선·새 웹 검증·누락 시 대체 경로 확보·혼합 할인 후 요금 완료가 아니며21개 판단4/9/8 유지, 배포하지 않았습니다.\n')
debug.write_text(debug.read_text(encoding='utf8').replace('## 미해결',
    '## 해결됨 (2026-10-09) — 거리·통행시간의 완전 구간 검사') +
    f'\n\n신규40/40·관련112/112 통과. 거리 경로 수정 전18실패·프로파일 경로 수정 전15실패를 보존했습니다. 정상 데이터의 전후 값 유지와 누락 시 안내 보류를 확인했습니다. 실제 누락 경로의 복구·대체 소스 확보는 별도 남은 과제입니다. [검증 보고서](../{report_name}).\n', encoding='utf8')
save(ev / 'backup-manifest-v1.json', state['backups'])
save(ev / 'verification-proof-v1.json', {'created_at': now.isoformat(), 'source_test_data_hashes': hashes,
    'new_tests': 40, 'related_tests': 112, 'test_results': test_results,
    'distance_queries': distance['adjacent_queries'], 'profile_queries': profile['adjacent_queries'],
    'initial_source_matches': 216, 'initial_artifact_matches': 6,
    'features': 21, 'counts': catalog['counts'], 'new_web_routes': 0, 'map_developer_api_calls': 0,
    'actual_trips_or_payments': 0, 'http_service_verified': False, 'deployed': False,
    'scope': 'complete stop sequence and valid fallback distance; not missing route acquisition or fare accuracy'})
backs = '\n'.join(f'- [{Path(b["backup"]).name}]({Path(os.path.relpath(root / b["backup"], report.parent)).as_posix()})' for b in state['backups'])
body = f'''# バス距離と通行時間の完全区間検証

중간 정류장이 빠졌는데도 남은 거리와 통행시간만 더해 이동 시간을 짧게 안내하는 결함을 고쳤습니다. 거리 계산과 정류장별 통행시간 계산 모두 요청 구간이 완전한지 확인합니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 신규 누락·중복·수치 시험 | 통과 | 40/40 = 100% |
| 관련 시험 | 통과 | 112/112 = 100% |
| 기존 인접 거리 유지 | 확인 | 41,103/41,103 = 100% |
| 기존 인접 통행시간 유지 | 확인 | 82,206/82,206 = 100% |

생성 {now.isoformat()}. 파일명은 생성 시각입니다. 신규40은 관련112에 포함됩니다. 시작 시 앞선 코드·시험·자료216개와 산출물6개 해시를 확인했고 최종 {len(hashes)}개 코드·시험·자료 해시를 보존했습니다.

## 원인과 수정

거리 계산은 있는 행만 더했습니다. 미등록 노선·역방향·동일 순번은0, 중간 누락은 일부 합, 중복은 중복 합으로 처리할 수 있었습니다. 통행시간 계산도 중간 정류장 순번이 빠지면 실제 이웃하지 않은 두 행을 인접 구간으로 취급하고 다음 행의 단일 구간 거리로 대신할 수 있었습니다.

두 계산 경로 모두 양 끝과 중간의 연속 순번·중복·순번 형식을 확인합니다. 거리 합은 노선 등록과 행의 노선 ID도 확인합니다. 통행시간 계산은 행에 노선 ID가 있으면 요청 노선과 일치해야 하며, 기존 ID 없는 시험/내부 호출의 형태는 유지합니다. 거리를 사용할 때는 논리값·문자열·음수·NaN·무한대·누락값을 거부합니다. 유효 통행시간 자료가 있으면 거리 칸이 없더라도 그대로 사용하고, 정상0m 거리 칸도 막지 않습니다. 기점 통과 계산의 같은 순번0분 계약은 유지했습니다.

합성5→8 구간에서 중간6행을 빼면 종전 거리는3km 중2km만 더했습니다. 수정 후 거리/통행시간은 값을 내지 않으며 현재 출발 관측도 짧은 ETA를 출력하지 않습니다. [동일 입력 출발 관측 전후](../evidence/{state['tag']}/controlled-departure-traces-v1.json). 기존 결과불명 계약의 fatal 상태를 사용했으며 cs 프로젝트 서버를 실제로 종료하지 않았습니다. 현재 저장 자료에서 이 누락이 발견됐다는 주장도 아닙니다.

## 검증과 영향

신규 시험은 거리20조건·통행시간20조건입니다. 수정 전 거리18실패/2통과, 통행시간15실패/5통과를 보존했습니다. 첫 거리 수정 후91/92에서 새 시험이 needs_replan을 기대했으나 기존 결과불명 계약은fatal이므로 시험의 기대를 고쳤습니다. 제품 상태 규칙을 시험에 맞춰 완화하지 않았습니다. 이후 거리 관련92/92, 통행시간 추가 후112/112·종료코드0, Ruff4개 파일 통과입니다. pyreadline3 콘솔 정리 OSError가 일부 실행 뒤 별도로 출력됐으며 시험 XML과 종료코드를 함께 확인했습니다. [실행 원문·명령·해시](../evidence/{state['tag']}/).

저장된717노선·정류장41,820행에서 인접 거리41,103건과 노선 처음→마지막 거리717건은 전후 모두 같았습니다. [거리 전수 대조](../evidence/{state['tag']}/existing-distance-audit-v2.json). 감사 스크립트 첫 시도는 CLI 환경 초기화 전 자료 경로를 사용해 자료 읽기 전에 실패했습니다. 원본 실패 스크립트를 보존하고 cli_processed()를 쓰는v2로 복구했으며 제품 설정·자료를 변경하지 않았습니다.

실제 저장 통행시간 자료로도 인접 구간41,103개를p50/p90 각각 재계산한82,206건, 전체 노선717개를 각각 재계산한1,434건에서 소요와 사용/대체/실패 상태가 모두 유지됐습니다. [통행시간 자료 전수 대조](../evidence/{state['tag']}/existing-profile-audit-v1.json). 평일10시·최소5일 자료·거리 대체20km/h를 고정한 모델 재생입니다.20km/h는 이 감사의 고정 조건이며 제품 속도를 바꾸지 않았습니다. 두 지표 계산을 두 독립 구간으로 세지 않으며 실제 운행 오차·새 지도 표본 검증도 아닙니다.

## 공식 자료와 적용 전제

실행일2026-10-09에 [공공데이터포털 서울시 버스 노선정보 조회](https://www.data.go.kr/data/15000193/openapi.do)의 응답 항목 표에서fullSectDist가 선택 항목이며 구간거리라고 명시된 것을 확인했습니다. 이 HTML 항목 표만으로 단위의 원천 관례·실제 도로의 완전성·교통카드 청구 운임거리와 동일함을 확정하지 않았습니다. 전체 안내서 파일은 이번에 읽지 않았습니다.

[서울시 통합환승 할인제 안내](https://news.seoul.go.kr/traffic/transfer_discount)도 확인했지만 이번 수정에서 할인 계산식이나 요율을 변경하지 않았습니다. 정류장 사슬과 수치의 유효성을 확인하는 입력 계약에 새 논문 알고리즘을 적용했다고 주장하지 않습니다. 혼합 운임 구현에는 운임거리·태그·동일 노선/조조 조건을 별도로 연결해야 합니다.

## 남은 범위

[거리 계산](../../../app/domains/travel_ops/instances/mobility/engine/bus.py)·[통행시간 계산](../../../app/domains/travel_ops/instances/mobility/engine/bus_profile.py), [거리 새 시험](../../../tests/unit/travel/mobility/test_bus_distance_completeness_v1.py)·[통행시간 새 시험](../../../tests/unit/travel/mobility/test_bus_profile_completeness_v1.py)을 보강했습니다. 현재 자료의 정상 수치가 유지됐으므로 웹 오차가 줄었다고 보고하지 않습니다.

누락된 사슬을 실제 소스로 복구하고 대체 경로까지 확보하는 작업, 조회 시각·출입점을 맞춘1.2km 이내 새 웹 도보 표본, 실시간 지하철·실제 위치/탑승·혼합 할인 후 운임은 남았습니다. 이번 새 웹 경로0개·지도 개발자 API 직접 호출0회·실제 탑승/결제0회입니다.21개 기능 판단은 조건부 사용4·개선 필요9·추가 검증8로 유지했습니다. [시각화v30](assets/2026-10-09_mobility_readiness_v30/mobility-readiness.html)에 기존 비교 수치·근거·남은 부분을 함께 보존했습니다. 브라우저 렌더링은 미확인입니다.

mock 서버 시험(화면 반응): 안 했음.
실서버 확인(서버 응답): 안 했음 — 이번 확인은 로컬 모델 계산과 주입한 도착 예측이며 cs 프로젝트 서버 HTTP 응답을 확인하지 않았습니다.

커밋·푸시·배포·외부 메시지·결제를 실행하지 않았습니다. 전체 완료를 선언하지 않습니다.

## 백업

[백업 명세](../evidence/{state['tag']}/backup-manifest-v1.json)에 코드·계약·시험 기대 수정 전 판을 보존했습니다.
{backs}
'''.replace('# バス距離と通行時間の完全区間検証', '# 버스 거리와 통행시간의 완전 구간 검증')
with report.open('x', encoding='utf8') as f:
    f.write(body)
assert all(sha(root / p) == h for p, h in hashes.items())
assert all(sha(root / b['backup']) == b['sha256'] for b in state['backups'])
checked = []
for p in [report, assets / 'mobility-readiness.html']:
    text = p.read_text(encoding='utf8')
    refs = re.findall(r'\]\(([^)]+)\)', text) if p.suffix == '.md' else re.findall(r'href="([^"]+)"', text)
    for ref in refs:
        ref = html.unescape(ref)
        if ref.startswith(('https:', 'http:', '#')):
            continue
        target = (p.parent / ref).resolve()
        assert target.exists(), ref
        checked.append(target.relative_to(root).as_posix())
artifacts = [report, assets / 'mobility-readiness.html', assets / 'readiness-catalog.json', wiki,
             ev / 'verification-proof-v1.json', ev / 'backup-manifest-v1.json']
for p in artifacts:
    assert not re.search(r'(?:\d{1,3}\.){3}\d{1,3}|webhooks/|@[0-9]', p.read_text(encoding='utf8')), p
for name in ['audit_bus_distance_v1.py', 'audit_bus_distance_v2.py', 'finish_bus_distance_tests_v1.py',
             'prepare_bus_profile_completeness_v1.py', 'run_bus_profile_completeness_v1.py',
             'audit_bus_profile_completeness_v1.py', 'publish_bus_completeness_v1.py', 'publish_bus_completeness_v2.py', 'recover_bus_publication_v1.py']:
    shutil.copy2(scratch / name, ev / name)
save(ev / 'publication-validation-v1.json', {'source_hash_matches': len(hashes),
    'backup_hash_matches': len(state['backups']), 'local_links': checked,
    'artifact_hashes': {p.relative_to(root).as_posix(): sha(p) for p in artifacts},
    'browser_render_verified': False, 'scan_scope': [p.relative_to(root).as_posix() for p in artifacts]})
print(json.dumps({'report': report.relative_to(root).as_posix(), 'hashes': len(hashes),
                  'backups': len(state['backups']), 'links': len(checked)}, ensure_ascii=False))
