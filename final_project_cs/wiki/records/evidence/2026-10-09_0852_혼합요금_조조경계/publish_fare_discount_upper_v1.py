from pathlib import Path
from datetime import datetime
import collections
import difflib
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
scratch = Path(__file__).parent
state = json.loads((scratch / 'fare-discount-upper-work-v1.json').read_text(encoding='utf8'))
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


before = ET.parse(ev / 'before-v1.xml').getroot()
after = ET.parse(ev / 'after-v1.xml').getroot()
assert len(before.findall('.//testcase')) == 25 and len(before.findall('.//failure')) == 23
assert len(after.findall('.//testcase')) == 84 and not after.findall('.//failure') and not after.findall('.//error')
assert json.loads((ev / 'after-v1.run.json').read_text(encoding='utf8'))['exit_code'] == 0
audit = json.loads((ev / 'existing-route-rate-audit-v1.json').read_text(encoding='utf8'))
assert audit['supported_routes'] == 674 and audit['stored_routes'] == 717 and not audit['mismatches']
files = ['app/domains/travel_ops/instances/mobility/engine/options.py',
         'app/domains/travel_ops/instances/mobility/engine/plan.py',
         'tests/unit/travel/mobility/test_fare_discount_upper_v1.py']
cmd = [sys.executable, '-m', 'ruff', 'check', *files]
r = subprocess.run(cmd, cwd=cs, capture_output=True, text=True, encoding='utf8')
with (ev / 'ruff-v1.log').open('x', encoding='utf8') as f:
    f.write(r.stdout + r.stderr)
save(ev / 'ruff-v1.run.json', {'command': cmd, 'exit_code': r.returncode})
assert r.returncode == 0
prior_ev = cs / 'wiki/records/evidence/2026-10-09_0836_버스거리_완전구간'
hashes = dict(json.loads((prior_ev / 'verification-proof-v1.json').read_text(encoding='utf8'))['source_test_data_hashes'])
owned = {'final_project_cs/' + p for p in files}
assert all(sha(root / p) == h for p, h in hashes.items() if p not in owned)
for p in files:
    hashes['final_project_cs/' + p] = sha(cs / p)
for p, h in audit['inputs'].items():
    assert sha(root / p) == h
    hashes[p] = h
save(ev / 'source-test-data-hashes-v1.json', hashes)
diff = ''
for rel in files[:2]:
    b = next(x for x in state['backups'] if x['source'] == 'final_project_cs/' + rel)
    diff += ''.join(difflib.unified_diff((root / b['backup']).read_text(encoding='utf8').splitlines(True),
                  (cs / rel).read_text(encoding='utf8').splitlines(True), fromfile='before/' + rel, tofile='after/' + rel))
with (ev / 'owned-source-diff-v1.patch').open('x', encoding='utf8') as f:
    f.write(diff)
save(ev / 'research-v1.json', {'checked_at': now.isoformat(), 'sources': [
    {'url': 'https://sftc.seoul.go.kr/seoul/mulga/main/contents.do?menuNo=200022',
     'scope': 'Full HTML fare table and rules: 6 ordinary adult type rates, flat single bus ride, early-bird discount.'},
    {'url': 'https://news.seoul.go.kr/traffic/traffic_price',
     'scope': 'First boarding early-bird rule and ordinary fare difference on following transfers; body 239-258.'},
    {'url': 'https://news.seoul.go.kr/traffic/transfer_discount',
     'scope': 'Fare overview, window, tag, same route/vehicle and maximum duration conditions; body 226-276.'},
    {'url': 'https://arxiv.org/abs/2204.01326',
     'scope': 'Abstract and metadata of Price Optimal Routing in Public Transportation, version3 revised2024-02-08.',
     'applied': False},
    {'url': 'https://drops.dagstuhl.de/entities/document/10.4230/OASIcs.ATMOS.2019.12',
     'scope': 'Publication metadata and ticket-state framework abstract; implementation not applied.', 'applied': False}],
    'interpretation': 'Independent ordinary fare sum is an estimated upper amount, not integrated fare or optimal-fare routing.',
    'new_web_routes': 0, 'map_developer_api_calls': 0})
report_name = stamp + '_혼합경로_조조경계와_할인미적용_예상액_검증.md'
report = cs / 'wiki/records/reports' / report_name
assets = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v31'
assets.mkdir(exist_ok=False)
old_catalog = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v30/readiness-catalog.json'
catalog = json.loads(old_catalog.read_text(encoding='utf8'))
catalog['created_at'] = now.isoformat()
catalog['scope'] = '혼합 경로 할인 미적용 예상액 상단; 실제 환승 할인 운임·결제·새 웹 정확도 검증 아님'
catalog['prior_catalog_sha256'] = sha(old_catalog)
for f in catalog['features']:
    if f['name'] == '버스·혼합 환승 요금':
        f['need'] += ' 조조 승차 창의 불확실성으로 상단 금액까지 빠지는 결함을 고쳤습니다. 혼합 상단은 버스 기본요금·지하철 승인 거리 범위로 조조 할인을 적용하지 않고 표시합니다. 신규25/25·관련84/84, 공개 옵션2/2 확인. 저장 노선의 지원 유형674개 기본요금 대조이며 새 경로/결제 검증이 아닙니다. 앞선 웹99/100·33/99·48/59는 새 정책으로 재측정하지 않았습니다.'
assert len(catalog['features']) == 21
assert dict(collections.Counter(f['status'] for f in catalog['features'])) == catalog['counts']
save(assets / 'readiness-catalog.json', catalog)
e = html.escape
rows = ''.join('<tr>' + ''.join('<td>' + e(str(f[k])) + '</td>'
       for k in ('name', 'status', 'scope', 'metric', 'reason', 'need')) + '</tr>' for f in catalog['features'])
cases = ''.join('<tr><td>' + str(x['first_board_min'] // 60) + ':' + f"{x['first_board_min'] % 60:02d}" +
               (' 지하철→버스' if x['rail_first'] else ' 버스→지하철') + '</td><td>' +
               ('금액 누락' if x['before'] is None else f"{x['before']:,}원") + '</td><td>' +
               f"{x['after']:,}원" + '</td></tr>' for x in audit['controlled_mixed_cases'])
page = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 검증 v31</title><style>body{{margin:0;background:#fbfcfd;color:#161c28;font:16px/1.65 'Malgun Gothic',sans-serif}}main{{max-width:1280px;margin:auto;padding:24px}}section{{border:1px solid #dbe0ea;padding:24px;margin:24px 0}}h1{{font-size:30px}}table{{width:100%;border-collapse:collapse;min-width:720px}}th,td{{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #dbe0ea}}th{{background:#f1f4f8}}.scroll{{overflow:auto}}.notice{{border-left:4px solid #a8720c;padding-left:16px}}a{{color:#2f5bd8}}button{{padding:8px 16px;margin:4px;border:1px solid #6b7488;background:#fbfcfd;cursor:pointer}}button:focus-visible{{outline:3px solid #2f5bd8}}@media(max-width:600px){{main,section{{padding:12px}}h1{{font-size:24px}}}}</style></head><body><main>
<h1>조조 할인 여부가 애매해도 알려진 예상액 상단을 안내합니다</h1><p>생성 {e(now.isoformat())}. 혼합 경로 상단은 버스 일반 기본요금과 지하철 승인 거리 범위를 더하며 조조 할인을 적용하지 않습니다.</p><p class="notice">신규25/25 · 관련84/84 통과(신규25 포함). 공개 옵션2/2는 통제 후보 시험입니다. 할인 후 실제 결제액이나 새 웹 대조 정확도를 측정한 것이 아닙니다.</p>
<section><h2>같은 통제 경로의 전후</h2><div class="scroll"><table><thead><tr><th>첫 승차 시각·순서</th><th>이전 예상액 상단</th><th>수정 후</th></tr></thead><tbody>{cases}</tbody></table></div><p>금액이 커진 것은 할인 미적용 조건으로 맞췄기 때문입니다. 실제 비용이 늘었다는 뜻은 아닙니다. 간선 기본1,500원 + 지하철 거리 범위 상단1,650원 = 3,150원인 합성 후보입니다. 정확액 계산과 지하철 단독 조조 정책은 유지했습니다.</p></section>
<section><h2>저장 노선 유형의 기본요금 대조</h2><p>717개 노선 중 일반 기본요금 표가 있는674개에서674/674 일치했습니다. 공항38·투어5, 합계43개는 이번 범위 밖입니다.</p><p>06:25 승차·대기5분·저장된 배차 간격을 넣은 계산에서 기존 단일 요금182개와 새 상단674개를 확인했습니다.492개는 이 고정 시각에서 새로 상단이 나온 노선 유형 조회이며 실제492개 경로를 확보한 수치가 아닙니다.</p><p>원래 자료나 요율을 바꾸지 않았고 임의 보정률도 넣지 않았습니다. 청소년·어린이·미태그 추가요금·할인 후 운임은 별도 관문입니다.</p></section>
<section><h2>21개 기능의 현재 판단</h2><p>조건부 사용4/21 · 개선 필요9/21 · 추가 검증8/21. 전체 완료율이 아닙니다. 과거 웹 비교 수치는 새 정책으로 재측정하지 않았습니다.</p><div role="group" aria-label="기능 필터"><button data-filter="전체" aria-pressed="true">전체 보기</button><button data-filter="조건부 사용" aria-pressed="false">조건부 사용 보기</button><button data-filter="개선 필요" aria-pressed="false">개선 필요 보기</button><button data-filter="추가 검증" aria-pressed="false">추가 검증 보기</button></div><p id="visible" aria-live="polite">21/21개 표시</p><div class="scroll"><table id="features"><thead><tr><th>기능</th><th>판단</th><th>범위</th><th>비교 수치</th><th>근거</th><th>더 필요한 부분</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<p>혼합 할인 후 운임·누락 경로 복구·출입점/시각이 맞는 새 웹 표본은 남았습니다. 지도 개발자 API 직접 호출0회 · 실제 탑승/결제0회 · 커밋·푸시·배포하지 않았습니다. 브라우저 렌더링 미확인.</p><p><a href="../../{e(report_name)}">검증 보고서·공식 근거·백업</a> · <a href="../2026-10-09_mobility_readiness_v30/mobility-readiness.html">이전 버스 구간 검증</a></p></main><script>const rows=[...document.querySelectorAll('#features tbody tr')];for(const b of document.querySelectorAll('[data-filter]'))b.addEventListener('click',()=>{{for(const x of document.querySelectorAll('[data-filter]'))x.setAttribute('aria-pressed',String(x===b));for(const r of rows)r.hidden=b.dataset.filter!=='전체'&&r.cells[1].textContent!==b.dataset.filter;document.querySelector('#visible').textContent=rows.filter(r=>!r.hidden).length+'/21개 표시';}});</script></body></html>'''
with (assets / 'mobility-readiness.html').open('x', encoding='utf8') as f:
    f.write(page)
wiki = cs / 'wiki/teams/mobility.md'
debug = cs / state['debug']
backup(wiki, '혼합조조_상단검증결과')
backup(debug, '혼합조조_결함종료')
with wiki.open('a', encoding='utf8') as f:
    f.write(f'\n\n## {stamp} 혼합 경로 조조 경계와 할인 미적용 예상액 상단 검증 결과\n\n조조 승차 창이 불확실해도 알려진 버스 기본요금 상단을 사용하고 혼합 지하철 묶음에도 조조 할인을 적용하지 않으며 공개 문구에 표시합니다. 정확액과 지하철 단독 조조 정책은 유지했습니다. 신규25/25·관련84/84·포함 공개 옵션2/2 통과, 저장717노선 중 지원 유형674/674 기본요금 일치(고정 시각 조회이며 실제 경로/결제 아님). [보고서](../records/reports/{report_name})·[시각화v31](../records/reports/assets/2026-10-09_mobility_readiness_v31/mobility-readiness.html). 기존 웹 요금 지표를 새 정책으로 재측정하지 않았으며 실제 할인 후 혼합 요금·운임거리/태그·새 웹 표본·누락 경로 복구는 남았습니다. 전체21 판단4/9/8 유지, 배포하지 않았습니다.\n')
debug.write_text(debug.read_text(encoding='utf8').replace('## 미해결',
    '## 해결됨 (2026-10-09) — 혼합 경로 할인 미적용 예상액 상단') +
    f'\n\n신규25/25·관련84/84 및 포함 공개 옵션2/2 통과. 새 함수 부재에 따른 실패도 포함한 수정 전23실패/2통과를 보존했습니다. 기존 정확액·지하철 단독 조조 정책은 유지했고 알려진 유형의 기본요금으로 상단만 안내합니다. 할인 후 실제 운임은 해결 완료로 세지 않습니다. [검증 보고서](../{report_name}).\n', encoding='utf8')
save(ev / 'backup-manifest-v1.json', state['backups'])
save(ev / 'verification-proof-v1.json', {'created_at': now.isoformat(), 'source_test_data_hashes': hashes,
    'new_tests': 25, 'related_tests': 84, 'before_failures': 23, 'public_controlled_options': 2,
    'initial_source_matches': 218, 'initial_artifact_matches': 6, 'stored_routes': 717,
    'supported_route_rates': 674, 'rate_mismatches': 0, 'features': 21, 'counts': catalog['counts'],
    'new_web_routes': 0, 'map_developer_api_calls': 0, 'actual_trips_or_payments': 0,
    'http_service_verified': False, 'deployed': False,
    'scope': 'ordinary adult undiscounted estimated upper amount, not integrated exact fare or payment guarantee'})
backs = '\n'.join(f'- [{Path(b["backup"]).name}]({Path(os.path.relpath(root / b["backup"], report.parent)).as_posix()})' for b in state['backups'])
body = f'''# 혼합 경로 조조 경계와 할인 미적용 예상액 상단 검증

조조 할인 금액을 확정하지 못하면 혼합 경로의 예상액 상단까지 빠지는 결함을 고쳤습니다. 알려진 일반 기본요금과 승인된 지하철 거리 범위를 사용하고 조조 할인 미적용을 안내에 표시합니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 신규 요금 시험 | 통과 | 25/25 = 100% |
| 관련 시험 | 통과 | 84/84 = 100% |
| 지원 유형 기본요금 대조 | 일치 | 674/674 = 100% |

생성 {now.isoformat()}. 파일명은 생성 시각입니다. 신규25와 통제 공개 옵션2는 관련84에 포함됩니다. 시작 때 앞선 코드·시험·자료218개·산출물6개 해시를 확인하고 최종{len(hashes)}개 코드·시험·자료 해시를 보존했습니다.

## 원인과 변경

기존bus_fare는 배차로 계산한 승차 창이06:30을 가로지르면 정확 금액을 내지 않습니다. 혼합 예상액 상단도 이 함수를 그대로 불러 기본요금을 알고도 값을 뺐습니다. 또한 각 묶음을 첫 승차처럼 조조 할인하는 계산을 상단에 사용했습니다. 이 표본에서 실제 결제보다 부족했다고 측정한 것은 아닙니다.

혼합 상단의 버스는 규칙의 지원 유형 일반 기본요금만 사용합니다. 조조 창·배차가 기본요금 조회를 막지 않으며 미등록 노선·지원 밖 유형·비정상 요율·승차 결과 불일치는 값을 만들지 않습니다. 지하철 묶음은subway_fare_upper의 기존 거리·별도 운임 확인을 재사용하면서 조조 미적용을 명시적으로 선택합니다. 지하철 단독 기본 동작·정확액 판정·요율은 바꾸지 않았습니다. 공개label에는 기존 환승 할인 전 예상액 상단에 조조 할인 미적용을 더했습니다. 원문 자료나 상수를 바꾸거나 임의 보정률을 넣지 않았습니다.

06:15 버스→지하철 합성 후보는2,540→3,150원, 반대 순서는 누락→3,150원이었습니다.06:25 버스→지하철은 누락→3,150원, 반대 순서는2,840→3,150원입니다. 낮11:40 두 순서는3,150원으로 유지됐습니다. 간선1,500원과 지하철 승인 범위 상단1,650원의 합이며 실제 경로·카드 결제액을 확인한 값이 아닙니다. [같은 통제 입력과 저장 노선 유형 대조](../evidence/{state['tag']}/existing-route-rate-audit-v1.json).

## 검증 범위

신규25조건은 혼합 시각·순서4, 낮 유지1, 유형별 기본요금6, 지원 밖 유형4, 잘못된 요율6, 노선/결과 불일치1, 공개 옵션2, 지하철 단독 조조 유지1입니다. 수정 전23실패/2통과에는 새 함수 부재로 인한 실패가 포함되므로23개 실운영 결함으로 세지 않습니다. 관련84/84·pytest 종료코드0·Ruff3파일 통과입니다. 콘솔 정리의pyreadline3 OSError와 시험 XML·종료코드는 구분했습니다. [실행 원문·명령·해시](../evidence/{state['tag']}/).

공개 옵션2건은 실제 제품Planner.leg를 실행하되 후보 탐색을 통제 후보로 주입한 시험입니다. 새 실제 경로 탐색·HTTP 응답·실제 탑승 검증으로 세지 않습니다. 원본 후보를 바꾸지 않았고 기존 혼합 거리 누락·별도 운임·지하철 단독 경계 시험도 통과했습니다.

실제 저장717노선의 유형은 공항38·마을247·간선152·지선243·순환4·광역13·투어5·심야15입니다. 기본요금 표가 있는674개는674/674 일치하고 공항·투어43개는 지원 밖으로 유지됐습니다.06:25 승차·대기5분·저장 배차를 넣은 고정 계산에서 종전 단일 요금182개, 새 상단674개를 얻었습니다.492개는 이 고정 시각에서 상단을 새로 낼 수 있는 유형 조회이며492개의 실제 이동 경로·독립 표본을 확보했다는 뜻이 아닙니다.

## 공식 기준과 논문 확인

실행일2026-10-09에 [서울시 물가정보 버스 요금](https://sftc.seoul.go.kr/seoul/mulga/main/contents.do?menuNo=200022)의 전체 HTML 표에서 성인 일반 요금과 단독 버스 균일요금 규칙을 확인했습니다. [서울시 교통 요금 안내](https://news.seoul.go.kr/traffic/traffic_price)는 조조가 첫 승차 기본요금에 적용되고 다음 수단의 기본요금 차액은 평소 요금으로 계산됨을 설명합니다. [통합환승 할인 안내](https://news.seoul.go.kr/traffic/transfer_discount)의 태그·동일 노선/차량·환승 창·최대 이용시간도 확인했으며 이번 상단 계산을 이 조건들을 갖춘 실제 환승 요금으로 승격하지 않았습니다.

[Price Optimal Routing in Public Transportation](https://arxiv.org/abs/2204.01326),2024-02-08 수정v3의 초록·메타와 [ATMOS2019 요금 상태 기반 경로 연구](https://drops.dagstuhl.de/entities/document/10.4230/OASIcs.ATMOS.2019.12)를 확인했습니다. 두 자료는 단순 간선 요금 합만으로 복합 요금 체계를 표현하기 어렵고 요금 상태를 별도로 다루는 접근을 설명합니다. 이번 개별 일반 요금 합은 예상액 상단이며 최적 요금 탐색이 아니라는 적용 한계를 확인하는 데 사용했습니다. 본문 알고리즘 구현·논문 성능·서울 실제 요금 개선의 근거로 사용하지 않았습니다.

## 남은 부분과 산출물

[요금 계산](../../../app/domains/travel_ops/instances/mobility/engine/options.py), [공개 안내](../../../app/domains/travel_ops/instances/mobility/engine/plan.py), [새 검증 시험](../../../tests/unit/travel/mobility/test_fare_discount_upper_v1.py)을 보강했습니다. 수정 전 스냅샷과의 전체 차이는[변경 원문](../evidence/{state['tag']}/owned-source-diff-v1.patch)에 보존했습니다. 기존 변경을 되돌리거나 다른 파일의 작업을 덮어쓰지 않았습니다.

혼합 할인 후 운임·운임거리/태그·동일 노선/조조 상태 연결, 누락 경로 복구와 출입점·시각이 맞는 새 웹 대조는 남았습니다. 기존 웹 요금99/100 안내·33/99 범위 일치·48/59 상단 비교를 새 정책으로 다시 측정하지 않았습니다.21개 판단은 조건부 사용4·개선 필요9·추가 검증8 유지입니다. [시각화v31](assets/2026-10-09_mobility_readiness_v31/mobility-readiness.html)에 전후 수치와21개 기능 근거를 보존했습니다. 브라우저 렌더링은 미확인입니다.

mock 서버 시험(화면 반응): 안 했음.
실서버 확인(서버 응답): 안 했음 — 로컬 제품 계산과 주입한 후보를 확인했으며 cs 프로젝트 서버 HTTP 응답은 확인하지 않았습니다.

새 웹 경로0개·지도 개발자 API 직접 호출0회·실제 탑승/결제0회입니다. 커밋·푸시·배포·외부 메시지·결제를 실행하지 않았습니다. 전체 완료를 선언하지 않습니다.

## 백업

[백업 명세](../evidence/{state['tag']}/backup-manifest-v1.json)에 덮어쓰기 전 판을 보존했습니다.
{backs}
'''
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
for name in ['prepare_fare_discount_upper_v1.py', 'run_fare_discount_upper_v1.py',
             'audit_fare_discount_upper_v1.py', 'publish_fare_discount_upper_v1.py']:
    shutil.copy2(scratch / name, ev / name)
save(ev / 'publication-validation-v1.json', {'source_hash_matches': len(hashes),
    'backup_hash_matches': len(state['backups']), 'local_links': checked,
    'artifact_hashes': {p.relative_to(root).as_posix(): sha(p) for p in artifacts},
    'browser_render_verified': False, 'scan_scope': [p.relative_to(root).as_posix() for p in artifacts]})
print(json.dumps({'report': report.relative_to(root).as_posix(), 'hashes': len(hashes),
                  'backups': len(state['backups']), 'links': len(checked)}, ensure_ascii=False))
