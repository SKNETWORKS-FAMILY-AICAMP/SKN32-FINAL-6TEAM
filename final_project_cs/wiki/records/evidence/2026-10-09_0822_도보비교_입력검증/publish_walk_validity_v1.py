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
state = json.loads((scratch / 'walk-validity-work-v1.json').read_text(encoding='utf8'))
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
assert len(before.findall('.//testcase')) == len(before.findall('.//failure')) == 27
assert len(after.findall('.//testcase')) == 36 and not after.findall('.//failure') and not after.findall('.//error')
assert json.loads((ev / 'after-v1.run.json').read_text())['exit_code'] == 0
audit = json.loads((ev / 'existing-data-audit-v1.json').read_text(encoding='utf8'))
assert [a['rows'] for a in audit['audits']] == [200, 1]
assert all(a['prior_metrics_equal'] for a in audit['audits'])
files = ['scripts/mobility/compare_kakao_golden.py', 'tests/unit/travel/mobility/test_walk_comparison_values_v1.py']
cmd = ['C:/Users/playdata2/anaconda3/python.exe', '-m', 'ruff', 'check', *files]
r = subprocess.run(cmd, cwd=cs, capture_output=True, text=True, encoding='utf8')
with (ev / 'ruff-v1.log').open('x', encoding='utf8') as f:
    f.write(r.stdout + r.stderr)
save(ev / 'ruff-v1.run.json', {'command': cmd, 'exit_code': r.returncode})
assert r.returncode == 0
prior_ev = cs / 'wiki/records/evidence/2026-10-09_0806_도착조회_완료시각'
hashes = dict(json.loads((prior_ev / 'verification-proof-v1.json').read_text(encoding='utf8'))['source_test_data_hashes'])
owned = {'final_project_cs/' + p for p in files}
assert all(sha(root / p) == h for p, h in hashes.items() if p not in owned)
for p in files:
    hashes['final_project_cs/' + p] = sha(cs / p)
for a in audit['audits']:
    assert sha(root / a['input']) == a['sha256']
    hashes[a['input']] = a['sha256']
save(ev / 'source-test-data-hashes-v1.json', hashes)
report_name = stamp + '_도보比較_유효입력과_개발표본_집계_검증.md'
report_name = report_name.replace('比較', '비교')
report = cs / 'wiki/records/reports' / report_name
assets = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v29'
assets.mkdir(exist_ok=False)
old_catalog = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v28/readiness-catalog.json'
catalog = json.loads(old_catalog.read_text(encoding='utf8'))
catalog['created_at'] = now.isoformat()
catalog['scope'] = '도보 개발 비교의 숫자·상태 검증; 새 웹 표본/실보행 정확도 개선 아님'
catalog['prior_catalog_sha256'] = sha(old_catalog)
for f in catalog['features']:
    if '도보' in f['name']:
        f['need'] += ' 도보 비교에 논리값·음수·0·NaN·무한대·문자열을 정상 수치로 넣지 않도록 입력 검증을 보강했습니다. 신규27/27·관련36/36, 기존200쌍 및 그 안G04 재집계 수치는 유지했습니다. 새 웹/정렬/실보행 검증은 늘지 않았습니다.'
assert len(catalog['features']) == 21
assert dict(collections.Counter(f['status'] for f in catalog['features'])) == catalog['counts']
save(assets / 'readiness-catalog.json', catalog)
e = html.escape
rows = ''.join('<tr>' + ''.join('<td>' + e(str(f[k])) + '</td>' for k in ('name', 'status', 'scope', 'metric', 'reason', 'need')) + '</tr>' for f in catalog['features'])
page = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 검증 v29</title><style>body{{margin:0;background:#fbfcfd;color:#161c28;font:16px/1.65 'Malgun Gothic',sans-serif}}main{{max-width:1280px;margin:auto;padding:24px}}section{{border:1px solid #dbe0ea;padding:24px;margin:24px 0}}h1{{font-size:30px}}table{{width:100%;border-collapse:collapse;min-width:720px}}th,td{{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #dbe0ea}}th{{background:#f1f4f8}}.scroll{{overflow:auto}}.notice{{border-left:4px solid #a8720c;padding-left:16px}}a{{color:#2f5bd8}}button{{padding:8px 16px;margin:4px;border:1px solid #6d83a8;background:#fbfcfd;cursor:pointer}}button:focus-visible{{outline:3px solid #2f5bd8}}@media(max-width:600px){{main,section{{padding:12px}}h1{{font-size:24px}}}}</style></head><body><main>
<h1>잘못된 도보 값을 성공 표본으로 세지 않습니다</h1><p>생성 {e(now.isoformat())}. 거리와 소요가 모두 유한한 양수이고 숫자일 때만 제공 수·개발 오차에 넣습니다. 오류 상태와 원시 진단은 구분합니다.</p><p class="notice">비교 도구 입력 검증 개선입니다. 제품 보행 경로와 시간 계산은 바꾸지 않았고 새 웹 표본·실보행 정확도 측정은0개입니다. 신규27/27·관련36/36 통과(신규27 포함).</p>
<section><h2>같은 잘못된 입력의 전후</h2><div class="scroll"><table><thead><tr><th>입력</th><th>이전</th><th>수정 후</th></tr></thead><tbody><tr><td>거리300m / 소요true</td><td>제공1/1 · 비교1/1로 집계</td><td>제공0/1 · 비교0/1 · 입력 오류1/1</td></tr><tr><td>NaN·무한대·음수·0·문자열·누락값</td><td>값 존재만 확인하거나 통계 계산 실패</td><td>오류를 별도 기록하고 통계에서 제외</td></tr><tr><td>오류 상태인데 숫자가 남아 있음</td><td>성공 표본으로 집계 가능</td><td>성공으로 집계하지 않음</td></tr></tbody></table></div><p>true는1분이 아닙니다. 이 표는 통제 입력 재현이며 실제 웹 오류를 발견했다는 뜻이 아닙니다. 원문 자료를 지우거나 숫자로 채우지 않았습니다.</p></section>
<section><h2>기존 자료의 영향 확인</h2><p>저장된200행 파일과 그 안의G04 구간 재계산1행 파일을 재집계했습니다. 파일2/2에서 기존 통계가 같았고 새 입력 검사 오류0개였습니다. 두 파일을201개의 독립 구간으로 세지 않습니다. 제품 제공·원시 진단·미관측 분모는 유지했습니다.</p><p>새 지도 수집은 구글 브라우저 탭 읽기 시간 초과, 네이버·다음·구글 경로 페이지 웹 읽기 접근 실패로0개입니다. 소개글의 도보 시간을 경로 표본으로 쓰지 않았습니다. 실제 경로 확보·동일 출입점과 형상·조회 시각 정렬은 남았습니다.</p></section>
<section><h2>21개 기능의 현재 판단</h2><p>조건부 사용4/21 · 개선 필요9/21 · 추가 검증8/21. 기능 분류이며 전체 완료율이 아닙니다.</p><div role="group" aria-label="기능 필터"><button data-filter="전체" aria-pressed="true">전체 보기</button><button data-filter="조건부 사용" aria-pressed="false">조건부 사용 보기</button><button data-filter="개선 필요" aria-pressed="false">개선 필요 보기</button><button data-filter="추가 검증" aria-pressed="false">추가 검증 보기</button></div><p id="visible" aria-live="polite">21/21개 표시</p><div class="scroll"><table id="features"><thead><tr><th>기능</th><th>판단</th><th>범위</th><th>비교 수치</th><th>근거</th><th>더 필요한 부분</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<p>지도 개발자 API 직접 호출0회 · 실제 탑승/보행/결제0회 · 커밋·푸시·배포하지 않았습니다. 브라우저 렌더링 미확인.</p><p><a href="../../{e(report_name)}">검증 보고서·백업</a> · <a href="../2026-10-09_mobility_readiness_v28/mobility-readiness.html">이전 실시간 출발 검증</a></p></main><script>const rows=[...document.querySelectorAll('#features tbody tr')];for(const b of document.querySelectorAll('[data-filter]'))b.addEventListener('click',()=>{{for(const x of document.querySelectorAll('[data-filter]'))x.setAttribute('aria-pressed',String(x===b));for(const r of rows)r.hidden=b.dataset.filter!=='전체'&&r.cells[1].textContent!==b.dataset.filter;document.querySelector('#visible').textContent=rows.filter(r=>!r.hidden).length+'/21개 표시';}});</script></body></html>'''
with (assets / 'mobility-readiness.html').open('x', encoding='utf8') as f:
    f.write(page)
wiki = cs / 'wiki/teams/mobility.md'
debug = cs / state['debug']
backup(wiki, '도보입력_검증결과')
backup(debug, '도보입력_결함종료')
with wiki.open('a', encoding='utf8') as f:
    f.write(f'\n\n## {stamp} 도보 개발 비교 유효 입력 검증 결과\n\n잘못된 숫자·논리값·오류 상태를 제품 제공 수와 개발 오차 분모에서 제외하고 오류 수를 별도로 보존했습니다. 신규27/27·관련36/36 통과, 기존200행과 포함G04 재계산1행의 두 파일2/2에서 기존 통계가 같습니다. [보고서](../records/reports/{report_name})·[시각화v29](../records/reports/assets/2026-10-09_mobility_readiness_v29/mobility-readiness.html). 웹 지도 탭 시간 초과와 경로 페이지 접근 실패로 신규 웹0개, 실제 제품 계산·정확도 개선·전체21완료가 아니며 판단4/9/8 유지, 배포하지 않았습니다.\n')
debug.write_text(debug.read_text(encoding='utf8').replace('## 미해결', '## 해결됨 (2026-10-09) — 도보 비교 숫자·상태 검증') + f'\n\n신규27/27·관련36/36 통과, 수정 전27실패를 보존했습니다. 기존 자료 두 파일에서 이전 집계가 유지됐으므로 기존 보고 수치를 잘못됐다고 정정하지 않습니다. 실제 웹 입력의 오류 발견/오차 개선이 아닌 통제 재현입니다. [검증 보고서](../{report_name}).\n', encoding='utf8')
save(ev / 'backup-manifest-v1.json', state['backups'])
save(ev / 'verification-proof-v1.json', {'created_at': now.isoformat(), 'source_test_data_hashes': hashes,
    'new_tests': 27, 'related_tests': 36, 'before_failures': 27, 'files_reaggregated': 2,
    'initial_source_matches': 213, 'initial_artifact_matches': 6, 'prior_metrics_equal': True,
    'features': 21, 'counts': catalog['counts'], 'new_web_routes': 0, 'map_developer_api_calls': 0,
    'actual_trips_or_payments': 0, 'http_service_verified': False, 'deployed': False,
    'scope': 'comparison input validation only; no product route or time formula change'})
backs = '\n'.join(f'- [{Path(b["backup"]).name}]({Path(os.path.relpath(root / b["backup"], report.parent)).as_posix()})' for b in state['backups'])
body = f'''# 도보 비교 유효 입력과 개발 표본 집계 검증

잘못된 도보 거리·소요가 성공 표본과 오차 통계에 들어가는 결함을 고쳤습니다. 제품 경로·시간 계산은 변경하지 않았고 기존 자료의 수치도 유지됐습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 신규 수치·상태 시험 | 통과 | 27/27 = 100% |
| 관련 시험 | 통과 | 36/36 = 100% |
| 기존 파일 통계 유지 | 확인 | 2/2 = 100% |

생성 {now.isoformat()}, 파일명은 생성시각입니다. 신규27은 관련36에 포함됩니다. 시작 때 앞선 코드·시험·자료213개와 산출물6개 해시를 확인했습니다. 최종 코드·시험·입력 {len(hashes)}개 해시를 보존했습니다.

## 원인과 수정

제품 추출은 walk_m·eta_min을 검사하지 않고 available로 반환했고, 집계는 None 여부만 확인했습니다. Python의True를1분으로 셈하거나 음수·NaN·무한대가 들어가거나 문자열/누락에 통계가 실패할 수 있었습니다. 오류 상태인데 숫자가 남아 있어도 성공으로 셌습니다.

거리·소요가 모두 실제 int/float이고 bool이 아니며 유한한 양수일 때만 제품 제공·개발 비교에 넣습니다. 원시 진단도 같은 검사로 오류를 명시합니다. 제품 입력 오류·기준 입력 오류 수를 별도로 노출하며 기존 원문을 삭제하거나 정상값으로 채우지 않습니다. 옛 status 없는 기록은 숫자가 유효할 때만 원래 호환 의미로 집계합니다. 도보 허용 오차·제품 상수는 변경하지 않았습니다.

통제 입력300m·소요true는 수정 전 제공1/1·비교1/1이고 수정 후 제공0/1·비교0/1·입력 오류1/1입니다. 실제 웹 자료에 이 오류가 있었다는 주장이 아닙니다. 신규27조건은 제품 추출7·제품 집계7·기준 소요7·진단4·오류 상태1·정상/오류 혼합1입니다. 수정 전27실패는 신규 오류 집계 필드 부재에 의한 실패도 포함하므로 실제 운영 결함27개로 세지 않습니다.

## 검증 범위

저장된200행 개발 비교와 그 안의G04 제품 재계산1행을 다시 집계했습니다. 두 파일2/2에서 모든 기존 통계·이전coverage키가 동일했습니다. 새 숫자 검사에서 제품/기준 오류 수0개였으며 원문SHA-256도 보존했습니다. 한 구간이 겹치므로201개 독립 표본으로 세지 않습니다. 실제 제품 계산을 다시 돌리거나 기존 시각화 수치를 향상된 정확도로 승격하지 않았습니다. [재집계·통제 재현·웹 시도](../evidence/{state['tag']}/existing-data-audit-v1.json).

pytest 관련36/36·종료코드0와 Ruff 통과입니다. 수정 전27실패 로그·XML을 보존했습니다. 실행 끝의 pyreadline3 콘솔 정리 OSError는 수정 전/후에 별도로 출력됐으며 시험 XML에 실패/오류가 있다는 뜻은 아닙니다. [실행 원문·명령·해시](../evidence/{state['tag']}/). 이동 전체·실시간 출발118조건·로컬 개발 DB를 이번에 다시 시험한 것은 아닙니다.

## 웹·논문 확인과 한계

브라우저 목록은 읽었지만 기존 구글 도보 탭 내용 읽기는22.9초 뒤 timeout·kernel reset으로 끝났습니다. 구글·네이버·다음 도보 경로 페이지의 웹 읽기도 접근 실패였습니다. 이번 신규 웹 표본0개, 지도 개발자 API 직접 호출0회입니다. 소개글의 도보 수치나 URL에 넣은 요청 좌표를 지도에서 확인한 출입점 좌표라고 부르지 않았습니다. 이 시도 범위에서 확보하지 못했으며 지도 서비스 전체에서 경로를 얻을 수 없다고 단정하지 않습니다.

실행일2026-10-09에 [Python 공식 math 문서](https://docs.python.org/3/library/math.html#math.isfinite)에서 isfinite의NaN·무한대 판정을 확인했습니다. 실행 Python은3.12.7이고 문서 기본판3.14와 새 기능을 혼용하지 않았습니다.

[Dynamic Replanning for Improved Public Transport Routing](https://arxiv.org/abs/2505.14193), IJCAI2025 채택 논문의 초록·메타를 확인했습니다. 현재 지연만 쓰는 재탐색과 진행 중 지속 재탐색을 구분하는 연구이며, 서울 실제 탑승 상태와 이후 구간 지연 자료를 확보해야 적용 성능을 검증할 수 있습니다. 본문 알고리즘 구현·한국 성능·현재 코드 효과의 근거로 쓰지 않았습니다.

## 변경·남은 일

[비교 도구](../../../scripts/mobility/compare_kakao_golden.py), [새 입력 검증 시험](../../../tests/unit/travel/mobility/test_walk_comparison_values_v1.py), [현재 이동 wiki](../../teams/mobility.md)를 수정했습니다. 자료 파일·제품 경로 소스는 그대로 유지했습니다. 실제 출입점·경로·조회 시각을 맞춘1.2km 안의 새 표본, 실시간 지하철·탑승/위치 연결, 혼합 할인 후 운임, 누락 경로 해결은 남았습니다.21개 기능 판단4/9/8은 유지했습니다.

mock 서버 시험(화면 반응): 안 했음.
실서버 확인(서버 응답): 안 했음 — 이번 검증은 로컬 비교 집계이며 cs 프로젝트 서버 HTTP 응답을 확인하지 않았습니다.

커밋·푸시·배포·외부 메시지·결제를 실행하지 않았습니다. [시각화v29](assets/2026-10-09_mobility_readiness_v29/mobility-readiness.html)는 입력 전후와21개 판단 근거를 보존하며 브라우저 렌더링은 미확인입니다. 전체 완료를 선언하지 않습니다.

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
for name in ['audit_walk_validity_v1.py', 'publish_walk_validity_v1.py']:
    shutil.copy2(scratch / name, ev / name)
save(ev / 'publication-validation-v1.json', {'source_hash_matches': len(hashes),
    'backup_hash_matches': len(state['backups']), 'local_links': checked,
    'artifact_hashes': {p.relative_to(root).as_posix(): sha(p) for p in artifacts},
    'browser_render_verified': False, 'scan_scope': [p.relative_to(root).as_posix() for p in artifacts]})
print(json.dumps({'report': report.relative_to(root).as_posix(), 'hashes': len(hashes),
                  'backups': len(state['backups']), 'links': len(checked)}, ensure_ascii=False))
