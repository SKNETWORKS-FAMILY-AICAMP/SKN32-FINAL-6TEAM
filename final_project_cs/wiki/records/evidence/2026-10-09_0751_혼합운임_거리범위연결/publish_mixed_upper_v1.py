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
state = json.loads((scratch / 'mixed-upper-work-v1.json').read_text(encoding='utf8'))
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


before = ET.parse(scratch / 'mixed-upper-before-v1.xml').getroot()
after = ET.parse(scratch / 'mixed-upper-related-v1.xml').getroot()
assert len(before.findall('.//testcase')) == 7 and len(before.findall('.//failure')) == 4
assert not after.findall('.//failure') and not after.findall('.//error')
new_count = sum('test_mixed_fare_upper_v1' in c.get('classname', '') for c in after.findall('.//testcase'))
assert new_count == 7
related = len(after.findall('.//testcase'))
assert related == 115
for mode in ('before', 'related'):
    for ext in ('log', 'xml', 'run.json'):
        name = f'mixed-upper-{mode}-v1.{ext}'
        assert not (ev / name).exists()
        shutil.copy2(scratch / name, ev / name)
assert json.loads((ev / 'mixed-upper-related-v1.run.json').read_text())['exit_code'] == 0
files = ['app/domains/travel_ops/instances/mobility/engine/options.py',
         'app/domains/travel_ops/instances/mobility/engine/plan.py',
         'tests/unit/travel/mobility/test_mixed_fare_upper_v1.py']
cmd = ['C:/Users/playdata2/anaconda3/python.exe', '-m', 'ruff', 'check', *files]
run = subprocess.run(cmd, cwd=cs, capture_output=True, text=True, encoding='utf8')
(ev / 'ruff-v1.log').write_text(run.stdout + run.stderr, encoding='utf8')
save(ev / 'ruff-v1.run.json', {'command': cmd, 'exit_code': run.returncode})
assert run.returncode == 0
prev = cs / 'wiki/records/evidence/2026-10-09_0737_환승운임_시간경계'
old_proof = json.loads((prev / 'verification-proof-v1.json').read_text(encoding='utf8'))
hashes = dict(old_proof['source_test_data_hashes'])
owned = {'final_project_cs/' + p for p in files}
assert all(sha(root / p) == h for p, h in hashes.items() if p not in owned)
for p in files:
    hashes['final_project_cs/' + p] = sha(cs / p)
assert len(hashes) == 210
save(ev / 'source-test-data-hashes-v1.json', hashes)
assets = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v27'
assets.mkdir(exist_ok=False)
old_catalog = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v26/readiness-catalog.json'
prior = json.loads(old_catalog.read_text(encoding='utf8'))
catalog = {'created_at': now.isoformat(), 'scope': '混合 경로의 승인 거리 범위 상단 연결; 전체 판단 유지'.replace('混合', '혼합'),
           'counts': prior['counts'], 'features': prior['features'], 'prior_catalog_sha256': sha(old_catalog)}
for feature in catalog['features']:
    if feature['name'] == '버스·혼합 환승 요금':
        feature['scope'] = '환승 할인 전 예상액 상단 표시'
        feature['reason'] = '개별 요금 합의 예상액 상단. 지하철 확정액이 없으면 기존 승인 거리 범위 상단도 전달한다. 할인 후 실제 요금 계산은 남음.'
        feature['need'] += ' 혼합 공개 옵션까지 범위 상단을 전달하는 통제 시험1개·신규7개·관련115개를 확인했습니다. 기존 웹 일치율 수치는 이번에 재측정하지 않았습니다.'
assert len(catalog['features']) == 21
assert dict(collections.Counter(f['status'] for f in catalog['features'])) == catalog['counts']
save(assets / 'readiness-catalog.json', catalog)
report_name = stamp + '_혼합경로_지하철거리범위_예상액전달_검증.md'
report = cs / 'wiki/records/reports' / report_name
e = html.escape
feature_rows = ''.join('<tr>' + ''.join('<td>' + e(str(f[k])) + '</td>' for k in ('name', 'status', 'scope', 'metric', 'reason', 'need')) + '</tr>' for f in catalog['features'])
viz = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 검증 v27</title><style>
body{{margin:0;background:#fbfcfd;color:#161c28;font:16px/1.65 'Malgun Gothic',sans-serif}}main{{max-width:1280px;margin:auto;padding:24px}}section{{margin:24px 0;padding:24px;border:1px solid #dbe0ea}}h1{{font-size:30px}}.scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:720px}}th,td{{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #dbe0ea}}th{{background:#f1f4f8}}.notice{{border-left:4px solid #a8720c;padding-left:16px}}a{{color:#2f5bd8}}button{{padding:8px 16px;margin:4px;border:1px solid #6d83a8;background:#fbfcfd;cursor:pointer}}button:focus-visible{{outline:3px solid #2f5bd8}}@media(max-width:600px){{main,section{{padding:12px}}h1{{font-size:24px}}}}
</style></head><body><main><h1>혼합 경로에서도 계산 가능한 예상액 상단을 전달합니다</h1><p>생성 {e(now.isoformat())}. 지하철의 승인된 거리 범위 상단이 버스+지하철 경로에서 빠지던 연결을 고쳤습니다.</p><p class="notice">실제 결제 상한 보장이 아닙니다. 환승 할인 후 요금 계산과 실제 탑승 검증은 남았습니다. 신규7/7·관련115/115 통과이며 신규7은 관련115에 포함됩니다.</p>
<section><h2>같은 통제 경로의 수정 전후</h2><p>합성 버스 간선1,500원+9호선 선로 추정10km의 거리 범위 상단1,650원을 사용했습니다. 실제 지도 경로나 탑승·결제 표본이 아닙니다.</p><div class="scroll"><table><thead><tr><th>조건</th><th>수정 전</th><th>수정 후</th><th>판정</th></tr></thead><tbody><tr><td>버스→지하철 / 지하철→버스</td><td>요금 칸 누락</td><td>3,150원 · 예상액 상단</td><td>승인 범위 전달</td></tr><tr><td>연속 지하철2구간+버스</td><td>요금 칸 누락</td><td>3,150원 · 지하철 한 묶음</td><td>중복 기본액 제외</td></tr><tr><td>거리 간선 누락 / 지원 밖 노선 / 알 수 없는 버스</td><td>계산 불가</td><td>계산 불가</td><td>임의 기본요금으로 채우지 않음</td></tr></tbody></table></div><p>실제 Planner.leg 공개 옵션을 확인한 통제 시험1/1에서 fare_krw=3,150원과 ‘환승 할인 전 예상액 상단’ 문구를 확인했습니다. 경로 생성기는 통제 후보를 주입했습니다. 실제 경로 탐색·외부 응답을 검증한 것이 아닙니다.</p></section>
<section><h2>21개 기능의 판단·수치·남은 일</h2><p>조건부 사용4/21 · 개선 필요9/21 · 추가 검증8/21. 전체 완료율이 아닙니다. 아래 웹 비교 수치는 기존 개발 자료이며 이번 연결 수정 뒤 새 웹 오차율로 바꾸지 않았습니다.</p><div role="group" aria-label="기능 필터"><button data-filter="전체" aria-pressed="true">전체 보기</button><button data-filter="조건부 사용" aria-pressed="false">조건부 사용 보기</button><button data-filter="개선 필요" aria-pressed="false">개선 필요 보기</button><button data-filter="추가 검증" aria-pressed="false">추가 검증 보기</button></div><p id="visible" aria-live="polite">21/21개 표시</p><div class="scroll"><table id="features"><thead><tr><th>기능</th><th>판단</th><th>범위</th><th>비교 수치</th><th>근거</th><th>더 필요한 부분</th></tr></thead><tbody>{feature_rows}</tbody></table></div></section>
<p>새 웹 경로0개 · 지도 개발자 API 직접 호출0회 · 실제 탑승/결제0회. 배포하지 않았습니다. mock 서버 시험(화면 반응): 안 했음. 실서버 확인(서버 응답): 안 했음. 브라우저 렌더링 미확인.</p><p><a href="../../{e(report_name)}">검증 보고서·백업</a> · <a href="../2026-10-09_mobility_readiness_v26/mobility-readiness.html">이전 환승 시간 검증</a></p></main><script>const rows=[...document.querySelectorAll('#features tbody tr')];for(const b of document.querySelectorAll('[data-filter]'))b.addEventListener('click',()=>{{for(const x of document.querySelectorAll('[data-filter]'))x.setAttribute('aria-pressed',String(x===b));for(const r of rows)r.hidden=b.dataset.filter!=='전체'&&r.cells[1].textContent!==b.dataset.filter;document.querySelector('#visible').textContent=rows.filter(r=>!r.hidden).length+'/21개 표시';}});</script></body></html>'''
with (assets / 'mobility-readiness.html').open('x', encoding='utf8') as f:
    f.write(viz)
debug = cs / state['debug']
backup(debug, '혼합예상액_해결기록')
debug.write_text(debug.read_text(encoding='utf8').replace('## 미해결', '## 해결됨 (2026-10-09, 부분) — 승인 거리 범위의 상단 연결') + f'\n\n수정 전4실패·3통과, 수정 후 신규7/7·관련115/115 통과. 공개 Planner.leg의 통제 후보도3,150원·예상액 상단 문구를 보존했습니다. 실제 통합 할인·운임거리·태그·실탑승은 미해결입니다. [보고서](../{report_name}).\n', encoding='utf8')
wiki = cs / 'wiki/teams/mobility.md'
backup(wiki, '혼합예상액_검증결과')
with wiki.open('a', encoding='utf8') as f:
    f.write(f'\n\n## {stamp} 혼합 경로의 지하철 거리 범위 상단 전달 결과\n\n지하철 확정액이 없고 승인된 범위 상단이 있는 혼합 후보에 개별 요금 합의 예상액 상단을 전달했습니다. 공개 문구도 실제 결제 보장과 구분했습니다. 신규7/7·관련115/115 통과, 공개 옵션 통제1/1 확인(실제 경로 탐색·탑승 아님). [보고서](../records/reports/{report_name})·[시각화v27](../records/reports/assets/2026-10-09_mobility_readiness_v27/mobility-readiness.html). 할인 후 제품 운임·거리/태그·새 웹 오차 검증은 남았고21기능 판단4/9/8 유지, 배포하지 않았습니다.\n')
save(ev / 'backup-manifest-v1.json', state['backups'])
proof = {'created_at': now.isoformat(), 'report': report.relative_to(root).as_posix(),
         'new_tests': 7, 'related_tests': related, 'before_failures': 4, 'public_option_controlled_tests': 1,
         'source_test_data_hashes': hashes, 'initial_prior_source_matches': 209, 'initial_prior_artifact_matches': 6,
         'features': 21, 'counts': catalog['counts'], 'new_web_routes': 0, 'actual_trips_or_payments': 0,
         'map_developer_api_calls': 0, 'http_service_verified': False, 'deployed': False,
         'discounted_product_fare_connected': False, 'python': '3.12.7',
         'research': [{'url': 'https://news.seoul.go.kr/traffic/transfer_discount', 'page_updated': '2026-02-02',
                       'scope': 'full text; standalone and integrated fares differentiated'},
                      {'url': 'https://arxiv.org/abs/2204.01326', 'scope': 'abstract and metadata; candidate only'}]}
save(ev / 'verification-proof-v1.json', proof)
links = '\n'.join(f'- [{Path(b["backup"]).name}]({Path(os.path.relpath(root / b["backup"], report.parent)).as_posix()})' for b in state['backups'])
text = f'''# 혼합 경로의 지하철 거리 범위 예상액 전달 검증

버스와 지하철을 함께 타는 후보에서 이미 계산 가능한 지하철 요금 범위 상단을 누락하던 연결을 고쳤습니다. 공개 요금과 문구를 보존하며 실제 결제 상한 보장과 구분합니다. 환승 할인 후 정확 요금 계산을 완료한 것은 아닙니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 신규 통제 조건 | 통과 | 7/7 = 100% |
| 관련 운임 회귀 시험 | 통과 | 115/115 = 100% |
| 공개 경로 옵션 전달 | 통과 | 1/1 = 100% |

생성 {now.isoformat()}. 파일명은 생성시각입니다. 신규7은 관련115에 포함되고 공개 옵션1조건도 신규7에 포함됩니다. 초기 최신 코드/시험/자료209개와 앞 판 산출물6개의 해시 일치를 확인했고 최종210개 해시를 보존했습니다. 기존 자료·다른 작업자 변경을 덮어쓰지 않았습니다. 21기능 상태는 조건부4·개선9·추가검증8 그대로입니다.

## 문제와 원인

[options.py:566](../../../app/domains/travel_ops/instances/mobility/engine/options.py:566)의 fare_upper_of는 연속 지하철 구간을 묶되 subway_fare 확정액만 사용했습니다. 같은 묶음에 subway_fare_upper로 승인된 거리 범위 상단을 낼 수 있어도 혼합 후보는 값을 잃었습니다. [plan.py:1695](../../../app/domains/travel_ops/instances/mobility/engine/plan.py:1695)의 공개 문구는 범위 추정을 결제 상한으로 오해할 여지가 있었습니다. 코드/문서 백업과 wiki 계약을 먼저 기록하고 신규 시험의 수정 전4실패를 보존했습니다.

## 수정과 전후 예

지하철 확정액을 우선 사용하고 그것이 없을 때 기존 subway_fare_upper가 허용하는 범위만 사용합니다. 버스 또는 철도 자료가 빠지면 기본액을 지어내지 않습니다. 연속 철도 구간은 한 묶음으로 계산하고 버스→철도/철도→버스 모두 같은 원칙을 적용합니다. 공개 label은 ‘환승 할인 전 예상액 상단’으로 바꿨습니다. API 필드와 계약 판은 그대로입니다.

합성 간선버스1,500원·9호선 추정 거리10km(기존 허용 오차 포함)에서 혼합 예상액 칸은 수정 전누락→수정 후3,150원입니다. 연속 철도2구간도 철도 기본액을 중복하지 않고 같은 값을 전달했습니다. 누락 간선·허용 밖 노선·알 수 없는 버스·순서가 맞지 않는 계산 결과는 값을 산출하지 않았습니다. 3,150원은 실제 탑승·웹 경로 관측값이 아니라 통제 입력의 예상액입니다. 요율·거리 오차·경로별 보정 숫자를 새로 만들지 않았습니다.

## 확인한 범위와 남은 근본 조건

신규7/7·관련115/115 통과, Python3.12.7·pytest 종료코드0·Ruff 통과. [시험 원문·XML·명령](../evidence/{state['tag']}/)을 보존했습니다. pyreadline 콘솔 정리 오류가 출력됐으나 XML 실패0과 pytest 종료코드0을 구분했습니다. [신규 시험](../../../tests/unit/travel/mobility/test_mixed_fare_upper_v1.py)의 공개 전달 조건은 실제 Planner.leg를 실행하되 경로 생성 자리에 통제 혼합 후보를 넣었습니다. 외부 경로 탐색·실시간 교통·HTTP 응답 확인으로 부르지 않습니다.

관련115는 신규7·앞 판 환승 경계17 및 기존 운임·계획91조건입니다. 이동 전체575·출발 통합136을 이번에 다시 실행한 것은 아닙니다. 기존 웹 요금 안내99/100·범위 일치33/99·이전 상한이 웹 최대 이상48/59 수치는 변경 후 재측정하지 않았습니다. 이번 시험으로 정확도·사용 수준을 승격하지 않습니다.

[서울시 공식 안내](https://news.seoul.go.kr/traffic/transfer_discount)(2026-02-02 갱신,2026-10-09 확인)에서 단독 거리 요금과 통합환승 거리 요금·태그·동일 노선 조건을 구분했습니다. 이번 개별액 합은 할인 전 예산 정보이며 통합 거리 요금 자체가 아닙니다. [Price Optimal Routing in Public Transportation](https://arxiv.org/abs/2204.01326)의 초록·메타도 확인했습니다. 이력에 따른 요금 상태를 다루는 연구는 다음 구현 후보이고 전체 논문 구현·서울 성능 증거는 아닙니다.

버스 운임거리의 공식 필드 의미·카드 태그·동일 노선 재승차·조조·별도 철도 운임을 확인한 할인 후 제품 계산, 출발시각/입구/추천 경로가 정렬된 새 웹 표본이 남았습니다. 새 웹 경로0개·지도 개발자 API 직접 호출0회·실제 탑승/결제0회입니다. raw/processed 자료는 변경하지 않았습니다. 커밋·푸시·배포·외부 메시지를 실행하지 않았습니다.

mock 서버 시험(화면 반응): 안 했음.
실서버 확인(서버 응답): 안 했음 — 통제 Planner 계산은 cs 프로젝트 서버 HTTP 확인이 아닙니다.

[시각화v27](assets/2026-10-09_mobility_readiness_v27/mobility-readiness.html)에 전후 사례와21개 기능의 근거·비교 수치·남은 부분을 보존했습니다. 브라우저 렌더링은 미확인입니다. 현재 정본은 [이동 wiki](../../teams/mobility.md)이며 전체 완료를 선언하지 않습니다.

## 백업

기존 코드2개·wiki·결함 문서를 수정 직전에 복사했습니다. [백업 명세와 SHA-256](../evidence/{state['tag']}/backup-manifest-v1.json).
{links}
'''
with report.open('x', encoding='utf8') as f:
    f.write(text)
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
        ref = re.sub(r':\d+$', '', ref)
        target = (p.parent / ref).resolve()
        assert target.exists(), (p, ref)
        checked.append(target.relative_to(root).as_posix())
artifacts = [report, assets / 'mobility-readiness.html', assets / 'readiness-catalog.json',
             wiki, ev / 'verification-proof-v1.json', ev / 'backup-manifest-v1.json']
for p in artifacts:
    assert not re.search(r'(?:\d{1,3}\.){3}\d{1,3}|webhooks/|@[0-9]', p.read_text(encoding='utf8')), p
for name in ('prepare_mixed_upper_v1.py', 'run_mixed_upper_v1.py', 'publish_mixed_upper_v1.py'):
    assert not (ev / name).exists()
    shutil.copy2(scratch / name, ev / name)
save(ev / 'publication-validation-v1.json', {'created_at': now.isoformat(), 'source_hash_matches': len(hashes),
     'backup_hash_matches': len(state['backups']), 'local_links': checked,
     'artifact_hashes': {p.relative_to(root).as_posix(): sha(p) for p in artifacts},
     'browser_render_verified': False, 'scan_scope': [p.relative_to(root).as_posix() for p in artifacts]})
print(json.dumps({'report': report.relative_to(root).as_posix(), 'tag': state['tag'],
                  'new': new_count, 'related': related, 'hashes': len(hashes),
                  'backups': len(state['backups']), 'local_links': len(checked)}, ensure_ascii=False))
