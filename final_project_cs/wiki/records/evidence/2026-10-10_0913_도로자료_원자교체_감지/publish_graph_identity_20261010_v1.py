from pathlib import Path
from datetime import datetime
from collections import Counter
import difflib, hashlib, html, json, re, shutil, subprocess, sys, xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
CS = ROOT/'final_project_cs'
SCRATCH = Path(__file__).parent
sys.stdout.reconfigure(encoding='utf8')
state = json.loads((SCRATCH/'graph-identity-state-20261010-v1.json').read_text(encoding='utf8'))
EV = ROOT/state['evidence']
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def rel(path):
    return path.relative_to(ROOT).as_posix()
def save(path, value):
    with path.open('x', encoding='utf8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)

before = ET.parse(EV/'before-v1.xml').getroot().findall('.//testcase')
after = ET.parse(EV/'after-v1.xml').getroot().findall('.//testcase')
assert len(before) == 5 and sum(row.find('failure') is not None for row in before) == 4
assert len(after) == 48 and all(row.find('failure') is None and row.find('error') is None and row.find('skipped') is None for row in after)
replay = json.loads((EV/'real-data-replay-v1.json').read_text(encoding='utf8'))
assert replay['matched'] == replay['total'] == 8
lint_args = [sys.executable, '-m', 'ruff', 'check', 'app/domains/travel_ops/instances/mobility/engine/turn_restrictions.py',
             'tests/unit/travel/mobility/test_graph_atomic_replacement_v1.py']
lint = subprocess.run(lint_args, cwd=CS, capture_output=True, text=True)
assert lint.returncode == 0, lint.stdout+lint.stderr
save(EV/'lint-v1.json', {'command': lint_args, 'exit_code': lint.returncode, 'stdout': lint.stdout, 'stderr': lint.stderr})
code = ROOT/state['backups'][0]['source']
wiki = ROOT/state['backups'][1]['source']
allowed = {rel(code), rel(wiki)}
preserved = {name: sha(ROOT/name) == digest for name, digest in state['baseline'].items() if name not in allowed}
assert all(preserved.values()), [name for name, matched in preserved.items() if not matched]
assert len(preserved) == 411
save(EV/'preservation-v1.json', {'matched': sum(preserved.values()), 'total': len(preserved), 'allowed_changes': sorted(allowed),
                               'unchanged': preserved, 'road_graph_files': replay['data_hashes']})
save(EV/'source-assessment-v1.json', {
    'checked_at': datetime.now().astimezone().isoformat(),
    'official_sources': [{'url': 'https://docs.python.org/3.12/library/os.html#os.stat_result',
                         'basis': '0이 아닌 파일 식별자는 장치 식별자와 함께 파일을 구분합니다. Windows ctime은 생성 시각이므로 내용 변경 감지 근거로 쓰지 않습니다.'}],
    'runtime': sys.version, 'unit': '파일 교체 감지 계약; 새로운 길찾기 알고리즘이나 논문 기반 성능 주장을 적용하지 않음',
    'actual_graph_file_identity_available': all((ROOT/name).stat().st_ino != 0 for name in replay['data_hashes'] if name.endswith(('nodes.jsonl.gz', 'edges.jsonl.gz'))),
    'browser_failure': 'CUA 세션 초기화 후 getState 시간 초과. 현재 공식 실시간 목록의 운행 식별자·시각·역 귀속 추가 확인 실패.',
    'api_budget': {'limited_api_calls': 0, 'provider_usage_before': None, 'provider_usage_after': None, 'remaining': None,
                   'reset_time': None, 'reservation': '미확보', 'decision': '공유 누적 사용량 미확인으로 한도 있는 API 호출 안 함',
                   'reserve_fraction': 0.20}})

assets = CS/'wiki/records/reports/assets/2026-10-10_mobility_readiness_v52'
assets.mkdir()
catalog = json.loads((CS/'wiki/records/reports/assets/2026-10-10_mobility_readiness_v51/readiness-catalog.json').read_text(encoding='utf8'))
assert len(catalog['features']) == 21
counts = Counter(row['status'] for row in catalog['features'])
assert counts == {'조건부 사용': 3, '개선 필요': 9, '추가 검증': 9}
catalog['created_at'] = datetime.now().astimezone().isoformat()
catalog['scope'] = '도로 파일 원자 교체 감지·기존 21개 판단 유지; 전체 완료 아님'
save(assets/'readiness-catalog.json', catalog)
rows = ''.join('<tr><th scope="row">'+html.escape(row['name'])+'</th><td>'+html.escape(row['status'])+'</td></tr>' for row in catalog['features'])
page = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>서울 이동 검증 v52 — 도로 자료 교체</title><style>body{font:17px/1.65 system-ui,sans-serif;color:#183128;background:#f5f7f4;margin:24px auto;padding:0 20px;max-width:920px}h1{font-size:30px}table{border-collapse:collapse;width:100%;margin:24px 0;background:white}th,td{padding:12px;text-align:left;border-bottom:1px solid #bdcbc2}caption{text-align:left;font-weight:700}small{color:#40584a}a{color:#184c82}</style>
<h1>도로 파일 교체 후 이전 차량 경로 사용을 막았습니다</h1>
<p>로컬 코드 검증 결과입니다. 운영 반영·실제 탑승·새 독립 웹 대조를 확인한 결과가 아닙니다.</p>
<table><caption>같은 교체 재현 4건의 수정 전후</caption><thead><tr><th scope="col">검사</th><th scope="col">수정 전</th><th scope="col">수정 후</th></tr></thead><tbody>
<tr><th scope="row">노드·간선 교체 / 회전자료 갱신 유무</th><td>감지 0/4 = 0%</td><td>감지 4/4 = 100%</td></tr>
<tr><th scope="row">변경 없는 자료 재사용</th><td>1/1 = 100%</td><td>1/1 = 100%</td></tr>
<tr><th scope="row">파일 식별자 없는 환경(시험 대역)</th><td>미실행</td><td>2/2 = 100%</td></tr>
</tbody></table><p>관련 시험 48/48 = 100%, 보유 서울 2쌍 교대 재생 응답 8/8 = 100% 동일. 개발 표본입니다.</p>
<p>같은 파일을 제자리 수정하면서 비교 메타데이터를 보존하거나 탐색 도중 교체하는 경우는 보장 범위 밖입니다. 파일 식별자 없는 환경은 요청마다 두 도로 파일을 해시하므로 추가 비용이 있습니다. 실제 HTTP 지연은 측정하지 않았습니다.</p>
<p>일일 제한 API 호출 0회. 공유 사용량·잔여량·갱신 시각은 미확인입니다.</p>
<table><caption>기존 21개 기능 분류 유지 — 완료율 아님 (조건부 3 / 개선 9 / 추가 검증 9)</caption><thead><tr><th scope="col">기능</th><th scope="col">현재 분류</th></tr></thead><tbody>'''+rows+'''</tbody></table>
<p><a href="../../2026-10-10_0913_도로자료_원자교체_감지_복구검증.md">검증 보고서와 백업 근거</a></p></html>'''
with (assets/'mobility-readiness.html').open('x', encoding='utf8') as stream:
    stream.write(page)

debug = CS/'wiki/records/reports/debugs'/f'{state["tag"]}.md'
backups = list(state['backups'])
for path in (debug, wiki):
    target = path.parent/'_backup'/(state['tag']+'_결과기록전')/path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    assert sha(path) == sha(target)
    backups.append({'source': rel(path), 'backup': rel(target), 'sha256': sha(target)})
debug_text = debug.read_text(encoding='utf8').replace('## 미해결', '## 해결됨 (2026-10-10, 부분) — 원자 교체 감지', 1)
debug_text += '\n신규 7/7·관련 48/48 시험으로 복구를 확인했습니다. 수정 전 재현은 5건 중 4실패·1통과이며, 식별자 없는 환경 2건은 수정 후 추가 검사입니다. 제자리 메타데이터 보존 변경·탐색 도중 교체는 미해결 범위입니다. [결과 보고서](../2026-10-10_0913_도로자료_원자교체_감지_복구검증.md).\n'
debug.write_text(debug_text, encoding='utf8')
report = CS/'wiki/records/reports/2026-10-10_0913_도로자료_원자교체_감지_복구검증.md'
backup_links = '\n'.join('- ['+Path(item['backup']).name+']('+Path(__import__('os').path.relpath(ROOT/item['backup'], report.parent)).as_posix()+') — '+item['source']+' 수정 전 사본.' for item in backups)
text = f'''---
type: report
title: 도로 파일 원자 교체 감지 복구 검증
status: verified-local
domain: travel
---

# 도로 파일 원자 교체 감지 복구 검증

도로 자료가 교체됐는데 이전 차량 경로를 계속 반환하던 결함을 로컬 코드에서 고쳤습니다. 교체 후에는 재적재가 필요하다는 오류로 드러납니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 원자 교체 재현 4조건 | 복구 | 4/4 = 100% |
| 신규 시험 | 통과 | 7/7 = 100% |
| 기존 관련 시험 | 통과 | 41/41 = 100% |
| 보유 서울 응답 교대 대조 | 동일 | 8/8 = 100% |

분모는 각각 노드·간선 × 회전자료 갱신 유무 4조건, 신규 pytest 사례 7건, 기존 세 파일 pytest 사례 41건, 고정 서울 OD 2쌍 × A/B/B/A 4회입니다. 전체 21개 기능 완료율이 아닙니다. 기존 분류 조건부 사용 3 / 개선 필요 9 / 추가 검증 9를 유지합니다.

## 목표와 변경

v11의 서울 이동 검증 범위와 이동 wiki의 차량 회전 관계 결합 계약을 보완했습니다. 최신 manifest 413/413 해시가 일치했고 기존 기록 말미가 v51인 것을 확인한 뒤 이 최소 단위를 선택했습니다. 공식 실시간 화면은 CUA 초기화 시간 초과로 추가 확인하지 못했습니다. 진행 중 작업 점검은 Python 프로세스 명령의 해당 이동 스크래치/이전 작업명 필터에 한정하며 전체 작업자 부재를 단정하지 않습니다.

변경 파일은 [회전자료 로더](../../../app/domains/travel_ops/instances/mobility/engine/turn_restrictions.py), [신규 회귀 시험](../../../tests/unit/travel/mobility/test_graph_atomic_replacement_v1.py), [이동 wiki](../../teams/mobility.md)입니다. 큰 도로 파일은 장치·파일 식별자와 크기·수정시각을 비교합니다. 식별자가 0이면 내용 SHA256을 더 비교합니다. 같은 내용의 도로 파일 교체도 재적재를 요구합니다. 회전 파일의 내용 해시 검사는 앞 판 그대로입니다.

## 실제 검증

수정 전 5건은 4실패·1통과였습니다. 같은 재현 4건은 수정 후 모두 감지했습니다. 변경 없는 자료 재사용 1건과 파일 식별자 0인 환경 시험 대역 2건을 합쳐 신규 7/7, 관련 전체 48/48 통과했습니다. 식별자 0인 실제 파일시스템을 측정한 결과는 아닙니다. Ruff 2파일 통과입니다.

원문·재현 명령은 [수정 전 로그](../../evidence/{state['tag']}/before-v1.log), [수정 후 로그](../../evidence/{state['tag']}/after-v1.log), [실행 명령](../../evidence/{state['tag']}/after-v1-run.json), [lint](../../evidence/{state['tag']}/lint-v1.json)에 보존했습니다. 시험용 압축 그래프만 교체했으며 제품 자료 파일은 교체하지 않았습니다.

보유 도로 자료의 두 서울 경로를 백업 A/수정 B/A·B·B·A로 재생했고 전체 응답 8/8이 같았습니다. 거리 10,184.1m 및 1,468.71m, 단순 정적 회전 관계 2,487개 범위입니다. 비교 도중 메모리 기준 서명 형식을 각 로더 판에 맞춰 바꿨으며, 실제 자료 교체 감지는 위 회귀 시험으로 확인했습니다. [재생 원문](../../evidence/{state['tag']}/real-data-replay-v1.json).

기존 baseline에서 허용 수정 2파일을 제외한 411/411 해시와 도로 폴더 6/6 파일을 보존했습니다. 다른 작업자의 변경을 되돌리지 않았습니다. [보존 검사](../../evidence/{state['tag']}/preservation-v1.json).

mock 서버 시험: 안 했음 (화면 반응 미확인).

실서버 확인 (서버 응답): 안 했음 — cs 프로젝트 서버 HTTP 요청·배포를 하지 않았습니다. 실차 탑승·결제·실제 ETA 오차·새 독립 웹 경로 표본은 측정하지 않았습니다.

## 적용 전제와 남은 범위

[Python 공식 os.stat 문서](https://docs.python.org/3.12/library/os.html#os.stat_result)는 0이 아닌 파일 식별자를 장치와 함께 사용하도록 설명하며, Windows ctime은 현재 생성 시각이라고 명시합니다. 따라서 ctime을 Windows 내용 변경 시각으로 가정하지 않았습니다. 현재 두 도로 파일은 0이 아닌 파일 식별자를 제공합니다. 새로운 길찾기 알고리즘·논문 성능 주장은 적용하지 않았습니다.

같은 파일을 제자리 수정하면서 식별자·크기·수정시각을 모두 유지하거나 요청 검사 이후 탐색 도중 교체하는 상황은 보장하지 않습니다. 식별자 없는 환경에서는 도로 파일 전체 해시 비용이 발생합니다. 실제 HTTP 지연·동시 자료 배포의 원자성은 측정하지 않았습니다. 복잡한 U턴·시간/차종 예외·실시간 대체 소스 자동 연결·1.2km 정책 안의 새 웹 표본·혼합 운임은 남았습니다.

## API 예비량과 보존물

이번 일일 제한 API 호출 0회입니다. 공급자 사용량 조회 전후·잔여량·갱신 시각은 미확인이고 공유 예산은 확보하지 않았으므로 호출을 보류했습니다. 최소 20% 예비량 규칙과 운영 설정·예약 주기·알림 정책을 바꾸지 않았습니다. [조사·예산 기록](../../evidence/{state['tag']}/source-assessment-v1.json).

백업은 수정 직전 SHA256 일치를 확인했습니다.

{backup_links}

[시각화 v52](assets/2026-10-10_mobility_readiness_v52/mobility-readiness.html)는 정적 비교 표와 기존 21개 분류를 담습니다. HTML·링크·분류 수는 검사하며 브라우저 렌더링은 미확인입니다. [결함 기록](debugs/{state['tag']}.md)에는 남은 보장 범위를 적었습니다.

커밋·푸시·배포·외부 메시지·결제는 하지 않았습니다. 다음 우선 작업은 실시간 대체 도착정보의 운행 식별자·관측 시각·역 귀속 확인과 실제 출발 안내 연결 검증입니다.
'''
with report.open('x', encoding='utf8') as stream:
    stream.write(text.replace('../../evidence/', '../evidence/'))
with wiki.open('a', encoding='utf8') as stream:
    stream.write('\n\n## 2026-10-10_0913 도로 파일 원자 교체 감지 결과\n\n같은 크기·수정시각의 노드/간선 교체를 놓친 4조건을 파일 식별자 검사로 복구했습니다. 식별자 0은 내용 해시로 검사. 신규7/7·기존41/41·전체48/48·Ruff2파일 통과, 보유서울2쌍ABBA8/8응답동일·도로6파일/허용수정외411파일보존. 제자리 메타데이터 보존 변경·탐색 도중 교체는 남음. 제한API0·실차/새독립웹0·21분류3/9/9유지·배포안함·전체미완료. [보고서](../records/reports/'+report.name+')·[시각화v52](../records/reports/assets/2026-10-10_mobility_readiness_v52/mobility-readiness.html)·[검증](../records/evidence/'+state['tag']+'/).\n')

for path in (report, debug, assets/'mobility-readiness.html'):
    body = path.read_text(encoding='utf8')
    targets = re.findall(r'\]\(([^)]+)\)', body) if path.suffix == '.md' else re.findall(r'href="([^"]+)"', body)
    for target in targets:
        if not target.startswith('http'):
            assert (path.parent/target).resolve().exists(), (rel(path), target)
assert '<script' not in page and page.count('<tr>') == 26
save(EV/'visual-validation-v1.json', {'features': len(catalog['features']), 'counts': dict(counts), 'local_links_valid': True,
                                   'static_html': True, 'browser_rendered': False, 'full_feature_completion': False})
delta = ''.join(difflib.unified_diff((ROOT/state['backups'][0]['backup']).read_text(encoding='utf8').splitlines(True),
                                  code.read_text(encoding='utf8').splitlines(True), fromfile='before/turn_restrictions.py', tofile='after/turn_restrictions.py'))
with (EV/'code-change-v1.patch').open('x', encoding='utf8') as stream:
    stream.write(delta)
for name in ('prepare_graph_identity_20261010_v1.py', 'run_graph_identity_20261010_v1.py',
             'replay_graph_identity_20261010_v1.py', 'publish_graph_identity_20261010_v1.py'):
    shutil.copy2(SCRATCH/name, EV/name)
assert all(sha(ROOT/item['backup']) == item['sha256'] for item in backups)
previous = json.loads((CS/'wiki/records/evidence/2026-10-10_0311_차량회전자료_내용갱신/final-integrity-v1.json').read_text(encoding='utf8'))
sources = set(previous['source_test_data_hashes']) | {rel(CS/'tests/unit/travel/mobility/test_graph_atomic_replacement_v1.py')}
artifacts = [p for folder in (EV, assets) for p in folder.iterdir() if p.is_file()] + [report, debug, wiki]
manifest = {'created_at': datetime.now().astimezone().isoformat(), 'source_test_data_hashes': {name: sha(ROOT/name) for name in sorted(sources)},
            'artifact_hashes': {rel(p): sha(p) for p in artifacts}, 'backups': backups, 'report': rel(report), 'assets': rel(assets),
            'evidence': state['evidence'], 'full_feature_completion': False}
save(EV/'final-integrity-v1.json', manifest)
hashes = manifest['source_test_data_hashes'] | manifest['artifact_hashes']
assert all(sha(ROOT/name) == digest for name, digest in hashes.items())
save(EV/'final-validation-v1.json', {'matched': len(hashes), 'total': len(hashes), 'backups_matched': len(backups),
                                  'backups_total': len(backups), 'preserved': len(preserved), 'tests_passed': len(after),
                                  'limited_api_calls': 0, 'browser_rendered': False, 'full_feature_completion': False})
print(json.dumps({'matched': len(hashes), 'backups': len(backups), 'preserved': len(preserved), 'report': rel(report)}, ensure_ascii=False))
