from pathlib import Path
from datetime import datetime
import collections
import hashlib
import html
import json
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
scratch = Path(__file__).parent
state = json.loads((scratch / 'transfer-clock-work-v1.json').read_text(encoding='utf8'))
ev = cs / 'wiki/records/evidence' / state['tag']
now = datetime.now().astimezone()
stamp = now.strftime('%Y-%m-%d_%H%M')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def backup(path, purpose):
    dest = path.parent / '_backup' / (stamp + '_' + purpose) / path.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    assert not dest.exists()
    shutil.copy2(path, dest)
    state['backups'].append({'source': path.relative_to(root).as_posix(),
                            'backup': dest.relative_to(root).as_posix(), 'sha256': sha(path)})


before = ET.parse(scratch / 'transfer-clock-before-v1.xml').getroot()
after = ET.parse(scratch / 'transfer-clock-related-v1.xml').getroot()
assert len(before.findall('.//testcase')) == 17
assert len(before.findall('.//failure')) == 11
assert len(after.findall('.//testcase')) == 108
assert not after.findall('.//failure') and not after.findall('.//error')
new_cases = [c for c in after.findall('.//testcase') if 'test_transfer_fare_clock_v1' in c.get('classname', '')]
assert len(new_cases) == 17
for prefix in ('before', 'related'):
    for suffix in ('log', 'xml', 'run.json'):
        name = f'transfer-clock-{prefix}-v1.{suffix}'
        assert not (ev / name).exists()
        shutil.copy2(scratch / name, ev / name)
assert json.loads((ev / 'transfer-clock-related-v1.run.json').read_text())['exit_code'] == 0
ruff_cmd = ['C:/Users/playdata2/anaconda3/python.exe', '-m', 'ruff', 'check',
            'app/domains/travel_ops/instances/mobility/engine/options.py',
            'tests/unit/travel/mobility/test_transfer_fare_clock_v1.py']
ruff = subprocess.run(ruff_cmd, cwd=cs, capture_output=True, text=True, encoding='utf8')
(ev / 'ruff-v1.log').write_text(ruff.stdout + ruff.stderr, encoding='utf8')
save(ev / 'ruff-v1.run.json', {'command': ruff_cmd, 'exit_code': ruff.returncode})
assert ruff.returncode == 0
hashes = json.loads((ev / 'current-source-hashes-v1.json').read_text(encoding='utf8'))
assert len(hashes) == 209
assert all(sha(root / p) == h for p, h in hashes.items())
audit = json.loads((ev / 'bus-distance-audit-v1.json').read_text(encoding='utf8'))
assert audit['adjacent_pairs'] == 41103 and not audit['sequence_gaps'] and not audit['invalid_numeric_lengths']
assets = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v26'
assets.mkdir(exist_ok=False)
old = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v25/readiness-catalog.json'
prior = json.loads(old.read_text(encoding='utf8'))
catalog = {'created_at': now.isoformat(), 'scope': '21개 기능 판단 유지; 통합환승 계산식 시간 경계 수정, 제품 연결은 미완료',
           'counts': prior['counts'], 'features': prior['features'], 'prior_catalog_sha256': sha(old)}
assert len(catalog['features']) == 21
assert dict(collections.Counter(f['status'] for f in catalog['features'])) == catalog['counts']
for feature in catalog['features']:
    if feature['name'] == '버스·혼합 환승 요금':
        feature['need'] += ' 후속 승차 기준 야간창·역전 시간·유한 숫자 검사를 합성17조건과 관련108시험으로 확인했습니다. 이 계산식의 제품 연결, 실제 운임거리/하차 태그/동일 노선/조조 검증은 남았습니다.'
save(assets / 'readiness-catalog.json', catalog)
report_name = stamp + '_통합환승_승차기준_시간경계_검증.md'
report = cs / 'wiki/records/reports' / report_name
e = html.escape
rows = ''.join('<tr>' + ''.join('<td>' + e(str(f[k])) + '</td>' for k in ('name', 'status', 'scope', 'metric', 'reason', 'need')) + '</tr>' for f in catalog['features'])
viz = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 검증 v26</title><style>
body{{margin:0;background:#fbfcfd;color:#161c28;font:16px/1.65 'Malgun Gothic',sans-serif}}main{{max-width:1280px;margin:auto;padding:24px}}section{{border:1px solid #dbe0ea;padding:24px;margin:24px 0}}h1{{font-size:30px}}.scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:700px}}th,td{{padding:12px;text-align:left;vertical-align:top;border-bottom:1px solid #dbe0ea}}th{{background:#f1f4f8}}.notice{{border-left:4px solid #a8720c;padding-left:16px}}a{{color:#2f5bd8}}button{{padding:8px 16px;margin:4px;background:#fbfcfd;border:1px solid #6d83a8;cursor:pointer}}button:focus-visible{{outline:3px solid #2f5bd8}}@media(max-width:600px){{main,section{{padding:12px}}h1{{font-size:24px}}}}
</style></head><body><main><h1>환승 시간 경계를 고쳤습니다. 제품 혼합 운임 연결은 남았습니다.</h1><p>생성 {e(now.isoformat())}. 공식 규칙의 야간 판정 기준을 다음 승차 시각에 맞췄습니다. 신규 시험17/17, 관련 시험108/108 통과. 신규17은 관련108에 포함됩니다.</p><p class="notice">합성 계산 시험이며 실제 탑승·결제 측정이 아닙니다. 제품 혼합 요금의 정확도와 기존21기능 판단을 승격하지 않습니다.</p>
<section><h2>시간 경계의 전후 변화</h2><p>거리·요율을 같은 값으로 고정한 합성 사례입니다. 두 탑승의 합산 거리6km·최고 기본액1,550원.</p><div class="scroll"><table><thead><tr><th>이전 하차 → 다음 승차</th><th>수정 전</th><th>수정 후</th><th>공식 기준</th></tr></thead><tbody><tr><td>20:40 → 21:20 (40분)</td><td>계산하지 못함</td><td>1,550원</td><td>21시 이후 승차: 60분 창</td></tr><tr><td>06:40 → 07:20 (40분)</td><td>1,550원</td><td>통합 할인 계산에서 제외</td><td>07시 이후 승차: 30분 창</td></tr><tr><td>이전 하차보다 이른 다음 승차</td><td>할인 계산에 포함 가능</td><td>제외</td><td>시간 순서 검증</td></tr></tbody></table></div><p>제외는 실제 결제액0원이라는 뜻이 아닙니다. 이 계산식의 통합 할인 적용 전제를 충족하지 않는 입력입니다.</p></section>
<section><h2>버스 거리 자료의 확인 범위</h2><p>717노선·41,820행에서 연속 구간41,103/41,103의 숫자·순서 검사를 통과했습니다. 실제 운임거리임을 확인한 것이 아닙니다. 구간 길이가 직선 거리의10배를 넘는55개는 진단 후보로 보존했으며 삭제하지 않았습니다. 10배는 제품 배제 기준이 아닙니다.</p><p>새 웹 경로0개 · 지도 개발자 API 직접 호출0회 · 실제 탑승/결제0회. 요금 계산의 제품 연결과 실제 거리·태그·노선·조조 검증이 다음 작업입니다.</p></section>
<section><h2>21개 기능의 현재 판단</h2><p>조건부 사용4/21 · 개선 필요9/21 · 추가 검증8/21. 기능 분류이며 전체 완료율이 아닙니다. 기존 웹 표시값은 실제 탑승·결제 측정이 아닙니다.</p><div role="group" aria-label="기능 필터"><button data-filter="전체" aria-pressed="true">전체 보기</button><button data-filter="조건부 사용" aria-pressed="false">조건부 사용 보기</button><button data-filter="개선 필요" aria-pressed="false">개선 필요 보기</button><button data-filter="추가 검증" aria-pressed="false">추가 검증 보기</button></div><p id="visible" aria-live="polite">21/21개 표시</p><div class="scroll"><table id="features"><thead><tr><th>기능</th><th>판단</th><th>사용 범위</th><th>비교 수치</th><th>근거</th><th>더 필요한 부분</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<p><a href="../../{e(report_name)}">검증 보고서·백업</a> · <a href="../2026-10-09_mobility_readiness_v25/mobility-readiness.html">이전 도보 검증</a> · <a href="https://news.seoul.go.kr/traffic/transfer_discount">서울시 공식 환승 안내</a></p><p>mock 서버 시험(화면 반응): 안 했음. 실서버 확인(서버 응답): 안 했음. 실제 브라우저 렌더링 미확인.</p></main><script>const rows=[...document.querySelectorAll('#features tbody tr')];for(const b of document.querySelectorAll('[data-filter]'))b.addEventListener('click',()=>{{for(const x of document.querySelectorAll('[data-filter]'))x.setAttribute('aria-pressed',String(x===b));for(const r of rows)r.hidden=b.dataset.filter!=='전체'&&r.cells[1].textContent!==b.dataset.filter;document.querySelector('#visible').textContent=rows.filter(r=>!r.hidden).length+'/21개 표시';}});</script></body></html>'''
with (assets / 'mobility-readiness.html').open('x', encoding='utf8') as f:
    f.write(viz)
debug = cs / state['debug']
backup(debug, '통합환승_부분해결기록')
debug_text = debug.read_text(encoding='utf8').replace('## 미해결', '## 해결됨 (부분) — 계산식 시간 경계·역전 입력')
debug.write_text(debug_text + f'\n\n신규17/17·관련108/108 통과. 최초11실패를 보존했습니다. 후속 승차 기준 야간창과 유한 숫자·시간 순서를 검사합니다. 제품 혼합 운임 연결 및 운임거리·태그·조조 검증은 미해결입니다. [보고서](../{report_name}).\n', encoding='utf8')
wiki = cs / 'wiki/teams/mobility.md'
backup(wiki, '통합환승_검증결과')
with wiki.open('a', encoding='utf8') as f:
    f.write(f'\n\n## {stamp} 통합환승 계산식 시간 경계 검증 결과\n\n후속 승차 기준 야간창과 역전 시간·유한 숫자 검사를 보강했습니다. 신규17/17·관련108/108 통과, 수정 전11실패를 보존했습니다. 아직 fare_of 혼합 제품 경로에 연결하지 않았습니다. 버스717노선의 연속41,103구간 숫자/순서 검사는 실제 운임거리 검증과 다릅니다. 직선 대비10배 초과55구간은 진단 후보이며 삭제하지 않았습니다. [보고서](../records/reports/{report_name})·[시각화v26](../records/reports/assets/2026-10-09_mobility_readiness_v26/mobility-readiness.html). 21기능 판단4/9/8 유지, 새 웹 경로0·실제 탑승/결제0·배포하지 않았습니다.\n')
save(ev / 'backup-manifest-v1.json', state['backups'])
proof = {'created_at': now.isoformat(), 'report': report.relative_to(root).as_posix(), 'new_tests': 17,
         'related_tests': 108, 'before_failures': 11, 'source_test_data_hashes': hashes,
         'source_hash_matches': 209, 'prior_hash_matches': 208, 'prior_artifact_matches': 7,
         'product_mixed_fare_connected': False, 'data_audit': audit, 'features': 21, 'counts': catalog['counts'],
         'new_web_routes': 0, 'map_developer_api_calls': 0, 'actual_trips_or_payments': 0,
         'http_service_verified': False, 'deployed': False, 'python': '3.12.7',
         'research': [state['source'], {'url': 'https://arxiv.org/abs/2204.01326',
          'version_date': '2024-02-08', 'read_scope': 'abstract and metadata only',
          'application': 'history-dependent fare-state routing candidate; not implemented or Seoul performance proof'}]}
save(ev / 'verification-proof-v1.json', proof)
backup_links = '\n'.join(f'- [{Path(b["backup"]).name}]({Path(os.path.relpath(root / b["backup"], report.parent)).as_posix()})' for b in state['backups'])
report_text = f'''# 통합환승의 승차 기준 시간 경계 검증

통합환승 계산식이 야간 여부를 이전 하차 시각으로 판단하던 오류를 고쳤습니다. 다음 승차 시각으로 판단하고, 겹치는 승하차·잘못된 숫자 입력을 제외합니다. 아직 제품 혼합 요금 경로에 연결되지 않아 고객의 혼합 요금 정확도가 개선됐다고 주장하지 않습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 신규 경계·입력 시험 | 통과 | 17/17 = 100% |
| 관련 운임 회귀 시험 | 통과 | 108/108 = 100% |
| 연속 구간 숫자·순서 검사 | 통과 | 41,103/41,103 = 100% |

생성 {now.isoformat()}. 파일명은 실제 생성시각입니다. 신규17조건은 관련108에 포함됩니다. wiki 계약을 먼저 기록한 뒤 코드·문서를 백업하고 수정했습니다. 수정 전 최신 소스/시험/자료208개와 앞 판 산출물7개의 해시를 확인했고 최종 소스/시험/자료209개 해시를 기록했습니다. 21개 기능의 사용 수준 판단은 조건부4·개선9·추가검증8 그대로입니다.

## 규칙과 수정

[서울시 통합환승 안내](https://news.seoul.go.kr/traffic/transfer_discount)의 전체 본문을 확인했습니다(확인일2026-10-09, 페이지 갱신일2026-02-02). 야간60분 창은 다음 승차 시각으로 적용합니다. 승차21시부터 다음날07시 전까지 야간이며 나머지는30분 창입니다. 기존 규칙 파일의 창·요율을 그대로 사용하고 경로별 보정값이나 새 요율을 넣지 않았습니다.

6km·최고 기본액1,550원을 고정한 합성 사례에서20:40 하차→21:20 승차는 수정 전 계산 불가→수정 후1,550원, 06:40→07:20은 수정 전1,550원→수정 후 통합 할인 계산 제외입니다. 제외는 실제 결제액0원이 아닙니다. 겹치는 두 탑승, 각 탑승의 하차가 승차보다 이른 경우, 음수 거리/기본액, NaN·무한대·참거짓·누락 시각도 계산에서 제외합니다. 자정 넘김은 기존 연장 분 표기를 유지합니다.

현재 `fare_of`의 혼합 후보는 이 계산식에 연결되지 않고 할인 전 개별 요금 합의 상단 안내를 사용합니다. 기존 개발 비교 요금 안내99/100·웹 범위 일치33/99·상단이 웹 최대 이상48/59를 이번 시험 통과로 승격하지 않습니다. 제품 연결 전에 실제 운임거리, 하차 태그, 동일 노선 재승차, 조조 및 별도 철도 운임의 적용 조건을 추가 검증해야 합니다.

## 자료가 근본 전제를 충족하는가

버스 노선 자료41,820행·717노선에서 인접 구간41,103개를 검사했습니다. 순번 누락0·유효하지 않은 구간 길이0·비첫 구간 길이0값0입니다. 구간 길이는 수집 코드의 fullSectDist에서 가져옵니다. 숫자·순서 일관성은 공식 운임거리라는 증거가 아닙니다. 실시간 버스 위치의 sectDist(구간 위치 거리)를 같은 필드로 취급하지 않았습니다.

구간 길이/직선 거리10배 초과55구간은 재확인 후보로 기록했습니다(공항3·마을20·간선7·지선21·광역2·심야2). 도로 우회·순환이 실제 길 수 있어55개 전부 오류라고 판단하거나 자료를 버리지 않았습니다. 10배는 진단용 필터이며 제품 거부 기준이 아닙니다. raw/processed 자료는 변경하지 않았습니다. 실제 운임거리와 카드 승하차 실측 대조는 미완료입니다.

## 논문과 적용 전제

실행일까지 공개된 [Price-Optimal Routing in Public Transportation](https://arxiv.org/abs/2204.01326)의 초록·메타를 확인했습니다(v3:2024-02-08). 환승 운임이 경로 이력에 의존한다는 연구 방향은 운임 상태를 경로 탐색에 전달할 후보입니다. 논문 전체를 구현하거나 서울 성능을 검증한 것은 아닙니다. 이번 수정의 직접 근거는 서울시 공식 시간 규칙이며 연구 논문으로 임의 요율을 만들지 않았습니다.

## 실행 근거와 제한

수정 전 신규17조건 중11실패·6통과, 수정 후 관련108/108 통과(신규17 포함), Python3.12.7·pytest 종료코드0·Ruff 통과입니다. [원문 로그/XML/명령·자료 검사](../evidence/{state['tag']}/)를 보존했습니다. 소스 변경은 [계산식](../../../app/domains/travel_ops/instances/mobility/engine/options.py), 신규 시험은 [시간 경계 시험](../../../tests/unit/travel/mobility/test_transfer_fare_clock_v1.py), 현재 근거는 [이동 wiki](../../teams/mobility.md)입니다. 기존 파일의 다른 작업 내용을 덮어쓰지 않고 해당 함수만 수정했습니다. 이동 전체575·출발 통합136 시험은 이번에 재실행하지 않았고 앞 판 근거로만 유지합니다.

새 웹 경로0개·지도 개발자 API 직접 호출0회·실제 탑승/결제 측정0회입니다. 이번 공식 문서 검색은 경로 수치 표본 수집과 다릅니다.

mock 서버 시험(화면 반응): 안 했음.
실서버 확인(서버 응답): 안 했음 — 단위 계산·로컬 자료 감사는 cs 프로젝트 서버 HTTP 확인이 아닙니다.

[시각화v26](assets/2026-10-09_mobility_readiness_v26/mobility-readiness.html)에 전후 경계 사례와21개 기능의 판단·수치·근거·남은 작업을 보존했습니다. 브라우저 렌더링은 확인하지 않았습니다. 전체 완료를 선언하지 않습니다. 커밋·푸시·배포·외부 메시지를 실행하지 않았습니다.

## 백업

기존 코드·wiki 및 결함 문서를 수정 직전에 보존했습니다. [백업 명세와 SHA-256](../evidence/{state['tag']}/backup-manifest-v1.json).
{backup_links}
'''
with report.open('x', encoding='utf8') as f:
    f.write(report_text)
for b in state['backups']:
    assert sha(root / b['backup']) == b['sha256']
print(json.dumps({'report': report.relative_to(root).as_posix(), 'evidence': ev.relative_to(root).as_posix(),
                  'backups': len(state['backups']), 'features': 21, 'source_hashes': 209}, ensure_ascii=False))
