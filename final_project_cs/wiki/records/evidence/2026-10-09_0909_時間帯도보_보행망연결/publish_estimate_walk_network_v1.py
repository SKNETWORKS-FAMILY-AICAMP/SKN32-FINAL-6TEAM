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
state = json.loads((scratch / 'estimate-walk-network-work-v1.json').read_text(encoding='utf8'))
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


before = ET.parse(ev / 'before-v2.xml').getroot()
after = ET.parse(ev / 'after-v1.xml').getroot()
assert len(before.findall('.//testcase')) == 12 and len(before.findall('.//failure')) == 11
assert len(after.findall('.//testcase')) == 58 and not after.findall('.//failure') and not after.findall('.//error')
assert json.loads((ev / 'after-v1.run.json').read_text(encoding='utf8'))['exit_code'] == 0
audit = json.loads((ev / 'native-replay-v1.json').read_text(encoding='utf8'))
assert audit['after_matches'] == 2 and audit['network_attempts'] == 0
files = ['app/domains/travel_ops/instances/mobility/engine/plan_estimate.py',
         'tests/unit/travel/mobility/test_estimate_walk_network_v1.py']
cmd = [sys.executable, '-m', 'ruff', 'check', *files]
r = subprocess.run(cmd, cwd=cs, capture_output=True, text=True, encoding='utf8')
(ev / 'ruff-v1.log').write_text(r.stdout + r.stderr, encoding='utf8')
save(ev / 'ruff-v1.run.json', {'command': cmd, 'exit_code': r.returncode})
assert r.returncode == 0
prior = cs / 'wiki/records/evidence/2026-10-09_0852_혼합요금_조조경계'
hashes = dict(json.loads((prior / 'verification-proof-v1.json').read_text(encoding='utf8'))['source_test_data_hashes'])
owned = {'final_project_cs/' + p for p in files}
assert all(sha(root/p) == h for p, h in hashes.items() if p not in owned)
for p in files:
    hashes['final_project_cs/' + p] = sha(cs/p)
hashes.update(audit['inputs'])
save(ev / 'source-test-data-hashes-v1.json', hashes)
rel = files[0]
original = root / next(x['backup'] for x in state['backups'] if x['source'] == 'final_project_cs/' + rel)
patch = ''.join(difflib.unified_diff(original.read_text(encoding='utf8').splitlines(True),
        (cs/rel).read_text(encoding='utf8').splitlines(True), fromfile='before/'+rel, tofile='after/'+rel))
(ev / 'owned-source-diff-v1.patch').write_text(patch, encoding='utf8')
save(ev / 'research-and-browser-v1.json', {'checked_at': now.isoformat(),
    'browser': {'inventory': 'Naver tab12, Google tab13 and portal tabs visible in tool inventory',
                'attempt': 'cua.getTab12 browser2', 'result': 'Timed out CDP Emulation.setFocusEmulationEnabled',
                'elapsed_seconds':35.866,'successful_new_route_reads':0},
    'sources': [
        {'url':'https://arxiv.org/abs/2603.11729','scope':'abstract and metadata; transfer buffers and trip sequences','applied':False},
        {'url':'https://arxiv.org/html/2603.12592v4','scope':'abstract, introduction and section3 network/algorithm model, revised2026-05-26; pruning needs ordered durations and monotone criteria','applied':False},
        {'url':'https://arxiv.org/abs/1906.08971','scope':'abstract and metadata; footpaths included in multicriteria journeys','applied':False}],
    'interpretation':'Routing research supports keeping walking connectivity and time in the network; no RAPTOR/TAD/pruning implementation or claimed paper speedup.',
    'new_independent_samples':0,'map_developer_api_calls':0})

assets = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v32'
assets.mkdir(exist_ok=False)
report_name = stamp + '_시간대별_도보추정_보행망시간_연결검증.md'
report = cs / 'wiki/records/reports' / report_name
old_catalog = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v31/readiness-catalog.json'
catalog = json.loads(old_catalog.read_text(encoding='utf8'))
catalog['created_at'] = now.isoformat()
catalog['scope'] = '시간대 추정 엔진의 직접 도보와 일정 계산 일치; 새 웹·실보행 정확도·전체21완료 아님'
catalog['prior_catalog_sha256'] = sha(old_catalog)
for feature in catalog['features']:
    if feature['name'] == '도보 소요·역 접근 시간':
        feature['need'] += ' 시간대별 직접 도보 추정에도 같은 보행망·계단 시간과 명시된 대체 모델 근거를 연결했습니다. 신규12/12·관련58/58, 기존 잠실1구간 수정 후2회8분 일치. 엔진/명령줄 검증이며 고객 API에서 이 시간대 추정의 사용은 이번에 확인하지 않았습니다. 접근·환승 걷기와 새 독립 웹 표본은 남았습니다.'
assert len(catalog['features']) == 21
assert dict(collections.Counter(x['status'] for x in catalog['features'])) == catalog['counts']
save(assets / 'readiness-catalog.json', catalog)
e = html.escape
labels = ['짧은 평지', '우회 평지', '경로 미발견', '계단']
cases = ''.join('<tr><td>'+label+'</td><td>'+str(x['before'])+'분</td><td>'+
               (str(x['after'])+'분' if x['after'] is not None else '안내 보류')+'</td></tr>'
               for label, x in zip(labels,audit['controlled_cases']))
rows = ''.join('<tr data-status="'+e(x['status'])+'">'+''.join('<td>'+e(str(x[k]))+'</td>'
        for k in ('name','status','scope','metric','reason','need'))+'</tr>' for x in catalog['features'])
page = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 검증 v32</title><style>
body{{margin:0;background:#fbfcfd;color:#161c28;font:16px/1.65 'Malgun Gothic',sans-serif}}main{{max-width:1280px;margin:auto;padding:24px}}section{{border:1px solid #dbe0ea;padding:24px;margin:24px 0}}h1{{font-size:30px}}table{{width:100%;border-collapse:collapse;min-width:720px}}th,td{{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #dbe0ea}}th{{background:#f1f4f8}}.scroll{{overflow:auto}}.notice{{border-left:4px solid #a8720c;padding-left:16px}}a{{color:#2f5bd8}}button{{padding:8px 16px;margin:4px;border:1px solid #6b7488;background:#fbfcfd;cursor:pointer}}button:focus-visible{{outline:3px solid #2f5bd8}}@media(max-width:600px){{main,section{{padding:12px}}h1{{font-size:24px}}}}</style></head><body><main>
<h1>시간대 추정도 일정과 같은 보행망 시간을 사용합니다</h1><p>생성 {e(now.isoformat())}. 신규12/12 · 관련58/58 시험 통과. 별도 실데이터 시험14개는 수집에서 제외되어 분모에 없습니다.</p>
<p class="notice">합성 계단 경로7→9분은 계산 연결 수정입니다. 실제 보행 오차가2분 줄었다는 측정이 아닙니다. 네이버 탭 읽기 시간 초과로 새 웹 표본0개이며 전체21기능의 판단은 유지합니다.</p>
<section><h2>직접 도보의 계산 연결</h2><p>장소 좌표 → 저장 보행망의 연결·거리·계단 시간 → 동일한 분 올림 → 일정 안내 / 시간대 추정</p><p>경로를 연결하지 못하면 직접 도보를 가능으로 넣지 않습니다. 라우터 장애 시 기존 직선거리 대체 모델과 축소 상태를 표시합니다. 횡단 대기·고도·실보행 오차는 별도 검증이 필요합니다.</p></section>
<section><h2>동일 합성 입력의 전후</h2><div class="scroll"><table><thead><tr><th>통제 조건</th><th>이전 추정</th><th>수정 후</th></tr></thead><tbody>{cases}</tbody></table></div><p>모두 약300m 직선인 합성 입력입니다. 거리 보정 상수나 웹 수치에 맞춘 계수를 추가하지 않았습니다.</p></section>
<section><h2>기존 실제 지도 자료 재생</h2><p>기존 잠실1구간: 이전·수정·수정·이전 순으로4회 재생했고 모두8분입니다. 수정 후2/2회가 공개 일정 도보444m·8분과 같습니다. 외부 네트워크 연결 시도0회. 새 구간·독립 웹 대조·실제 보행 검증으로 세지 않습니다.</p></section>
<section><h2>전체21기능의 현재 판단</h2><p>조건부 사용4 · 개선 필요9 · 추가 검증8. 완료율이 아닙니다. 표의 옛 웹 수치는 새 정책의 독립 검증으로 승격하지 않았습니다.</p><div aria-label="판단별 표 필터"><button type="button" data-filter="전체">전체21개 보기</button><button type="button" data-filter="조건부 사용">조건부 사용4개 보기</button><button type="button" data-filter="개선 필요">개선 필요9개 보기</button><button type="button" data-filter="추가 검증">추가 검증8개 보기</button></div><div class="scroll"><table id="features"><thead><tr><th>기능</th><th>상태</th><th>범위</th><th>비교 수치</th><th>근거</th><th>더 필요한 부분</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<p><a href="../../{e(report_name)}">검증 보고서·백업</a> · <a href="../../../evidence/{e(state['tag'])}/native-replay-v1.json">기존 좌표 재생 기록</a></p><p>mock 서버 화면 시험·cs 프로젝트 서버 HTTP응답 확인·커밋·푸시·배포·실제 탑승은 하지 않았습니다. 브라우저 렌더링 미확인.</p></main><script>document.querySelectorAll('button[data-filter]').forEach(b=>b.addEventListener('click',()=>{{document.querySelectorAll('#features tbody tr').forEach(r=>{{r.hidden=b.dataset.filter!=='전체'&&r.dataset.status!==b.dataset.filter}})}}));</script></body></html>'''
(assets / 'mobility-readiness.html').write_text(page, encoding='utf8')

wiki = cs / 'wiki/teams/mobility.md'
debug = root / state['debug']
backup(wiki, '시간대도보_검증결과')
backup(debug, '시간대도보_결함종료')
wiki.write_text(wiki.read_text(encoding='utf8') + f'\n\n## {stamp} 시간대별 직접 도보 보행망 연결 검증 결과\n\n시간대별 도보도 일정과 같은 보행망·계단 시간 및 경로 미발견/명시된 대체 근거를 사용합니다. 신규12/12·관련58/58통과(실데이터14개 제외), 합성 계단7→9분 일치와 기존 잠실1구간 수정 후2/2회8분 일치를 확인했습니다. [보고서](../records/reports/{report_name})·[시각화v32](../records/reports/assets/2026-10-09_mobility_readiness_v32/mobility-readiness.html). 엔진/명령줄 결과이며 이 시간대 추정의 고객 API 사용은 이번에 확인하지 않았습니다. 접근·환승 걷기·혼합 할인 후 운임·누락 경로 확보·새 웹/실보행 검증은 남았고 전체21판단4/9/8 유지, 배포하지 않았습니다.\n', encoding='utf8')
debug.write_text(debug.read_text(encoding='utf8').replace('## 미해결','## 해결됨 (2026-10-09) — 시간대별 직접 도보의 보행망 시간 연결')+f'\n신규12/12·관련58/58통과, 기존 잠실1구간2/2회일치. 수정 전11실패/1통과 로그는 실제 운영 결함11개로 세지 않습니다. 직접 경로를 찾지 못하면 안내를 보류하지만 대체 경로 확보 완료는 아닙니다. [검증 보고서](../{report_name}).\n', encoding='utf8')
save(ev / 'backup-manifest-v1.json', state['backups'])
save(ev / 'verification-proof-v1.json', {'created_at':now.isoformat(),'source_test_data_hashes':hashes,
    'new_tests':12,'related_tests':58,'before_failures':11,'deselected_data_tests':14,
    'native_unique_pairs':1,'after_native_matches':2,'features':21,'counts':catalog['counts'],
    'new_web_samples':0,'map_developer_api_calls':0,'actual_trips':0,'http_service_verified':False,'deployed':False})
backs = '\n'.join('- ['+Path(b['backup']).name+']('+Path(os.path.relpath(root/b['backup'],report.parent)).as_posix()+')' for b in state['backups'])
body = f'''# 시간대별 직접 도보 추정의 보행망 시간 연결 검증

시간대별 직접 도보 추정이 일정 안내의 보행망·계단 시간을 쓰도록 연결했습니다. 같은 경로에 다른 계산식을 쓰던 문제를 고쳤고, 연결하지 못한 경로는 가능한 직접 도보로 안내하지 않습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 신규 시험 | 통과 | 12/12 = 100% |
| 관련 시험 | 통과 | 58/58 = 100% |
| 기존 한 구간 수정 후 재생 | 일치 | 2/2 = 100% |

생성 {now.isoformat()}, 파일명은 생성 시각입니다. 신규12건은 관련58건에 포함됩니다. 실데이터 표시 시험14개는 이번 pytest 수집에서 제외됐고 통과 분모에 넣지 않았습니다. 전체21기능 완료를 선언하지 않습니다.

## 원인과 수정 범위

시간대별 추정 엔진은 직접 도보를 직선거리와 우회계수로 계산했습니다. 일정 안내는 이미 보행망 경로·계단 시간을 사용하므로 두 출력이 달랐습니다. 직접 도보 분기를 기존Planner._walk_path에 연결하고, 창마다 한 번 경로를 조회한 뒤 소요를 분 올림합니다. 직선1.2km 정책·최소1분·규칙 보행 속도는 그대로이며 임의 보정률을 넣지 않았습니다.

응답walk_basis는 보행망 근거·낙관적 접근 여부 또는 기존 직선거리 대체 모델·축소 이유를 남깁니다. 경로 미발견 상태를 도보 가능으로 채우지 않으며 현실에서 걷기 불가능하다고 단정하지 않습니다. 지하철 등 다른 후보가 있으면 그 판정은 계속합니다. 출력 근거의estimate_version은estimate-v1.2입니다. [변경 원문](../evidence/{state['tag']}/owned-source-diff-v1.patch).

합성 입력의 짧은 평지7→3분, 우회 평지7→11분, 계단7→9분, 경로 미발견7분→안내보류를 확인했습니다. 실제 보행 오차가 이만큼 줄었다는 측정이 아닙니다. [통제 입력·실제 자료 재생](../evidence/{state['tag']}/native-replay-v1.json).

## 실행 증거와 제한

수정 전 유효 재현은11실패/1통과, 수정 후 관련58/58·종료코드0입니다. 새 근거 칸 부재에 따른 실패도 포함되므로11개의 독립 운영 결함으로 세지 않습니다. 첫 재현before-v1은 시험 작성자가 공개함수에 지원하지 않는window를 넘긴1건을 포함했습니다. 시험을 백업하고 해당 호출을 고친before-v2를 수정 전 기준으로 사용했으며 두 원문 모두 남겼습니다.

신규12건은 거리3, 합성 실제 그래프 계단1, 경로 미발견1, 오류 대체 근거3, 낙관적 계단·접근1, 도보 비활성1, 공개 엔진 함수1, 라우터 부재1입니다. 관련58건은 계획 추정 단위·일정 안내·보행망 시간·접근 걷기·기존 거리 상한을 포함합니다. [시험 원문·명령·Ruff](../evidence/{state['tag']}/). 추가로pytest 실패가 없어 다른 단위를 반복 측정하지 않았습니다.

기존200쌍 안의G04 잠실 좌표1쌍을 실제 저장된OSM보행망으로 이전·수정·수정·이전(ABBA) 순서 재생했습니다.4회모두8분이고 수정 후2/2회가 공개 일정도보444m·8분과 일치했습니다. 이 반복은1개의 독립 구간이며4개 새 표본이 아닙니다. 네트워크 연결을 차단해 연결시도0회, 그래프·원본좌표 해시를 확인했습니다. 외부 웹조회일·출입점·경로형상 정렬이나 실제 보행은 측정하지 않았습니다. 이 구간에는 전후 정확도 향상 주장이 없습니다.

저장된 원자료와 다른 작업자의 코드·시험·자료 해시를 유지했습니다. 이번 엔진/명령줄 함수는 검증했지만 고객API에서 시간대 추정을 사용하는 연결은 이번 읽기 범위에서 확인하지 않았습니다. 지하철 접근·환승 걷기는 기존식이며 직접 도보의 이번 연결 완료로 전체 걷기 기능을 완료 처리하지 않습니다.

## 웹 및 논문 확인

네이버·구글 지도 탭은 브라우저 목록에 보였습니다. 네이버tab12 읽기는CDP Emulation.setFocusEmulationEnabled에서35.866초뒤 시간 초과했습니다. 화면의 경로 수치를 얻지 못했으므로 새 웹표본0개입니다. 지도 개발자API는 호출하지 않았고 일반 검색의 장소 소개를 경로 정답으로 대체하지 않았습니다. [시도·연구 읽기 범위](../evidence/{state['tag']}/research-and-browser-v1.json).

실행일2026-10-09에 [Early Pruning for Public Transport Routing v4](https://arxiv.org/html/2603.12592v4)의 초록·소개·3장 네트워크 모형을 확인했습니다. 보행 연결과 이동시간을 탐색에 포함하고 가지치기에는 정렬·기준의 단조성이 필요하다는 적용 전제를 확인했습니다. [Transfer Aware Dijkstra 연구](https://arxiv.org/abs/2603.11729)와 [보행 연결을 포함한 다목적 경로 연구](https://arxiv.org/abs/1906.08971)는 초록·메타만 읽었습니다. 이번에는 기존 보행망 계산의 호출을 연결했으며 해당 논문의RAPTOR/TAD/가지치기 알고리즘·성능을 구현 또는 검증한 것으로 쓰지 않습니다.

## 산출물과 남은 일

[추정 엔진](../../../app/domains/travel_ops/instances/mobility/engine/plan_estimate.py), [신규 시험](../../../tests/unit/travel/mobility/test_estimate_walk_network_v1.py), [전체21개 시각화v32](assets/2026-10-09_mobility_readiness_v32/mobility-readiness.html)에 변경과 근거를 남겼습니다. 조건부 사용4·개선 필요9·추가 검증8은 그대로이며 완료율이 아닙니다. 브라우저 렌더링은 확인하지 못했습니다.

실제 탑승/환승 재계산, 지하철 실시간 연결, 도로 회전의 조건부·다중구간 규칙, 정책 안의 독립 웹 표본, 혼합 할인 후 운임, 누락 경로의 대체 확보가 남았습니다. 이번에는 경로 미발견의 안내를 보류하도록 했을 뿐 대체 경로를 확보했다고 쓰지 않습니다.

mock 서버 시험(화면 반응): 안 했음.
실서버 확인(서버 응답): 안 했음 — 로컬 엔진과 저장 지도 자료를 실행했으며 cs 프로젝트 서버 HTTP응답은 확인하지 않았습니다.

커밋·푸시·배포·외부 메시지·결제를 실행하지 않았습니다.

## 백업과 재현

[백업 명세](../evidence/{state['tag']}/backup-manifest-v1.json)에 덮어쓰기 전 코드·문서·시험·스크립트를 보존했습니다.
{backs}

이번 근거 폴더의run_estimate_walk_network_v1.py와audit_estimate_walk_network_v1.py가 실행 명령·재생 입력을 남깁니다. before-v2는 수정 전백업판으로 재현해야 하며 현재 코드의시험명만으로 이전결과를 다시 만들지 않습니다.
'''
report.write_text(body, encoding='utf8')
assert all(sha(root/p)==h for p,h in hashes.items())
assert all(sha(root/b['backup'])==b['sha256'] for b in state['backups'])
checked = []
for p in [report, assets/'mobility-readiness.html']:
    txt = p.read_text(encoding='utf8')
    refs = re.findall(r'\]\(([^)]+)\)',txt) if p.suffix=='.md' else re.findall(r'href="([^"]+)"',txt)
    for ref in refs:
        ref = html.unescape(ref)
        if ref.startswith(('https:','http:','#')):
            continue
        target = (p.parent/ref).resolve()
        assert target.exists(), ref
        checked.append(target.relative_to(root).as_posix())
artifacts = [report,assets/'mobility-readiness.html',assets/'readiness-catalog.json',wiki,
             ev/'verification-proof-v1.json',ev/'backup-manifest-v1.json']
for p in [report,assets/'mobility-readiness.html',assets/'readiness-catalog.json']:
    assert not re.search(r'(?:\d{1,3}\.){3}\d{1,3}|webhooks/|@[0-9]',p.read_text(encoding='utf8')),p
for name in ['prepare_estimate_walk_network_v1.py','run_estimate_walk_network_v1.py',
             'audit_estimate_walk_network_v1.py','publish_estimate_walk_network_v1.py']:
    shutil.copy2(scratch/name,ev/name)
save(ev/'publication-validation-v1.json',{'source_hash_matches':len(hashes),'backup_hash_matches':len(state['backups']),
     'local_links':checked,'artifact_hashes':{p.relative_to(root).as_posix():sha(p) for p in artifacts},
     'browser_render_verified':False})
print(json.dumps({'report':report.relative_to(root).as_posix(),'hashes':len(hashes),
                  'backups':len(state['backups']),'links':len(checked)},ensure_ascii=False))
