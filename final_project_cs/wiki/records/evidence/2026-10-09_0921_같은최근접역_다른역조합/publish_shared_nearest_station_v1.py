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
cs = root/'final_project_cs'
scratch = Path(__file__).parent
state = json.loads((scratch/'shared-nearest-station-work-v1.json').read_text(encoding='utf8'))
ev = cs/'wiki/records/evidence'/state['tag']
now = datetime.now().astimezone()
stamp = now.strftime('%Y-%m-%d_%H%M')
sha = lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def save(path,value):
    with path.open('x',encoding='utf8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)


def backup(path,purpose):
    target = path.parent/'_backup'/(stamp+'_'+purpose)/path.name
    target.parent.mkdir(parents=True,exist_ok=True)
    assert not target.exists()
    shutil.copy2(path,target)
    state['backups'].append({'source':path.relative_to(root).as_posix(),
        'backup':target.relative_to(root).as_posix(),'sha256':sha(path)})


before = ET.parse(ev/'before-v1.xml').getroot()
after = ET.parse(ev/'after-v2.xml').getroot()
assert len(before.findall('.//testcase'))==12 and len(before.findall('.//failure'))==8
assert len(after.findall('.//testcase'))==118 and not after.findall('.//failure') and not after.findall('.//error')
assert json.loads((ev/'after-v2.run.json').read_text(encoding='utf8'))['exit_code']==0
audit = json.loads((ev/'native-path-replay-v1.json').read_text(encoding='utf8'))
extra = json.loads((ev/'native-default-and-earliest-v2.json').read_text(encoding='utf8'))
assert audit['stored_pairs']==200 and audit['same_first_station_pairs']==1 and audit['opened_pairs']==1
assert not audit['network_attempts'] and not extra['network_attempts']
variants = audit['replays'][0]['variants']
assert [x['available'] for x in variants]==[False,True,True,False]
assert [x['available'] for x in extra['earliest']]==[False,True]
assert all(x['planned']['id']=='walk' and x['planned']['eta_min']==8 for x in extra['default'])
files = ['app/domains/travel_ops/instances/mobility/engine/plan.py',
    'tests/unit/travel/mobility/test_station_fallback_v1.py','tests/unit/travel/mobility/test_shared_nearest_station_v1.py']
cmd = [sys.executable,'-m','ruff','check',*files]
r = subprocess.run(cmd,cwd=cs,capture_output=True,text=True,encoding='utf8')
(ev/'ruff-v1.log').write_text(r.stdout+r.stderr,encoding='utf8')
save(ev/'ruff-v1.run.json',{'command':cmd,'exit_code':r.returncode})
assert r.returncode==0
prior_state = json.loads((scratch/'estimate-walk-network-work-v1.json').read_text(encoding='utf8'))
prior_ev = cs/'wiki/records/evidence'/prior_state['tag']
hashes = dict(json.loads((prior_ev/'verification-proof-v1.json').read_text(encoding='utf8'))['source_test_data_hashes'])
owned = {'final_project_cs/'+x for x in files}
assert all(sha(root/p)==h for p,h in hashes.items() if p not in owned)
for file in files:
    hashes['final_project_cs/'+file] = sha(cs/file)
hashes.update(audit['inputs'])
save(ev/'source-test-data-hashes-v1.json',hashes)
patch = ''
for rel in files[:2]:
    original = root/next(x['backup'] for x in state['backups'] if x['source']=='final_project_cs/'+rel)
    patch += ''.join(difflib.unified_diff(original.read_text(encoding='utf8').splitlines(True),
        (cs/rel).read_text(encoding='utf8').splitlines(True),fromfile='before/'+rel,tofile='after/'+rel))
(ev/'owned-source-diff-v1.patch').write_text(patch,encoding='utf8')
save(ev/'research-v1.json',{'checked_at':now.isoformat(),'sources':[
    {'url':'https://arxiv.org/html/2603.12592v4','scope':'abstract, introduction and section3; missing transfer connections can omit journeys, pruning requires specific ordering/monotonic assumptions','algorithm_applied':False},
    {'url':'https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A',
     'scope':'official subway arrival field table: next stationID, terminalID, train type, generated timestamp and arrival seconds',
     'purpose':'Prerequisite check for pending realtime subway matching; no subway selector or arrival override implemented'}],
    'reason_for_unit':'Existing nearest-equal guard removes all otherwise valid station pairs before timetable validation.',
    'new_web_samples':0,'map_developer_api_calls':0,'actual_trips':0})

assets = cs/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v33'
assets.mkdir(exist_ok=False)
report_name = stamp+'_같은최근접역의_다른역조합_경로복구_검증.md'
report = cs/'wiki/records/reports'/report_name
previous_catalog = cs/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v32/readiness-catalog.json'
catalog = json.loads(previous_catalog.read_text(encoding='utf8'))
catalog['created_at'] = now.isoformat()
catalog['scope'] = '최근접역이 같은 장소에서 다른 역 조합을 복구; 기존 개발 좌표·시간표 검증, 새 웹·실제 탑승 정확도 아님'
catalog['prior_catalog_sha256'] = sha(previous_catalog)
for feature in catalog['features']:
    if feature['name']=='지하철 경로 산출':
        feature['need'] += ' 최근접역이 같은 두 장소에서 다른 물리적 역 조합까지 모두 버리던 조기 종료를 제거했습니다. 신규12/12·관련118/118, 저장200좌표쌍의 해당1구간에서 조합0→7개. 지하철만 선택한 기존 잠실1구간은경로없음→32분모델경로,수정2/2회같음. 도보포함기존선택8분유지와가장이른도착탐색의복구도확인했습니다. 기존94/96지표를전량재측정하지않았고전체최적성·독립웹·실탑승은남았습니다.'
assert len(catalog['features'])==21
assert dict(collections.Counter(x['status'] for x in catalog['features']))==catalog['counts']
save(assets/'readiness-catalog.json',catalog)
e = html.escape
rows = ''.join('<tr data-status="'+e(x['status'])+'">'+''.join('<td>'+e(str(x[k]))+'</td>'
    for k in ('name','status','scope','metric','reason','need'))+'</tr>' for x in catalog['features'])
page = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 검증 v33</title><style>
body{{margin:0;background:#fbfcfd;color:#161c28;font:16px/1.65 'Malgun Gothic',sans-serif}}main{{max-width:1280px;margin:auto;padding:24px}}section{{border:1px solid #dbe0ea;padding:24px;margin:24px 0}}h1{{font-size:30px}}table{{width:100%;border-collapse:collapse;min-width:720px}}th,td{{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #dbe0ea}}th{{background:#f1f4f8}}.scroll{{overflow:auto}}.notice{{border-left:4px solid #a8720c;padding-left:16px}}a{{color:#2f5bd8}}button{{padding:8px 16px;margin:4px;border:1px solid #6b7488;background:#fbfcfd;cursor:pointer}}button:focus-visible{{outline:3px solid #2f5bd8}}@media(max-width:600px){{main,section{{padding:12px}}h1{{font-size:24px}}}}</style></head><body><main>
<h1>가장 가까운 역이 같아도 다른 역 조합을 검증합니다</h1><p>생성 {e(now.isoformat())}. 신규12/12 · 관련118/118시험 통과. 실데이터표시 시험16개는 수집에서 제외했습니다.</p><p class="notice">지하철만 선택했을 때 누락되던 기존 잠실1구간을 복구했습니다. 모델경로32분은 기존8분도보보다 빠르지 않습니다. 새 웹표본이나 실제 탑승 측정은 아닙니다.</p>
<section><h2>탐색 흐름의 수정</h2><div class="scroll"><table><thead><tr><th>단계</th><th>이전</th><th>수정 후</th></tr></thead><tbody><tr><td>양쪽 최근접역이 같음</td><td>역 조합을 전부 버림</td><td>다른 물리적 역 조합은 유지</td></tr><tr><td>역 조합 판정</td><td>시간표를 확인하지 못함</td><td>기존 사고·시간표·출발 하한 확인</td></tr><tr><td>이동 선택</td><td>다른 수단만 확인</td><td>기존 수단 비교로 선택</td></tr></tbody></table></div></section>
<section><h2>같은 저장 자료의 전후</h2><div class="scroll"><table><thead><tr><th>범위</th><th>이전</th><th>수정 후</th></tr></thead><tbody><tr><td>저장200쌍 중 같은 최근접역인1쌍</td><td>역 조합0개</td><td>다른 역 조합7개</td></tr><tr><td>잠실1구간 · 지하철만 허용</td><td>경로 없음2/2회</td><td>모델32분 경로2/2회</td></tr><tr><td>잠실1구간 · 지하철·도보 허용</td><td>도보8분</td><td>도보8분유지</td></tr><tr><td>잠실1구간 · 지하철 이른 도착 탐색</td><td>경로 없음</td><td>경로 산출</td></tr></tbody></table></div><p>지하철 전용 재생은이전·수정·수정·이전순서입니다. 반복4회는1개구간이며4개독립표본이 아닙니다. 저장200쌍전체의길찾기·94/96지표를재측정한결과가아닙니다. 기존첫성립조합중단규칙은유지해전역최단경로를보장하지않습니다.</p></section>
<section><h2>전체21기능의 현재 판단</h2><p>조건부 사용4 · 개선 필요9 · 추가 검증8. 완료율이 아닙니다. 실시간지하철·탑승/환승재계산·혼합할인후운임·누락경로추가확보·독립웹대조가남았습니다.</p><div aria-label="판단별 표 필터"><button type="button" data-filter="전체">전체21개 보기</button><button type="button" data-filter="조건부 사용">조건부 사용4개 보기</button><button type="button" data-filter="개선 필요">개선 필요9개 보기</button><button type="button" data-filter="추가 검증">추가 검증8개 보기</button></div><div class="scroll"><table id="features"><thead><tr><th>기능</th><th>판단</th><th>확인범위</th><th>비교수치</th><th>근거</th><th>더필요한부분</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<p><a href="../../{e(report_name)}">검증보고서·백업</a> · <a href="../../../evidence/{e(state['tag'])}/native-path-replay-v1.json">기존좌표·시간표재생</a></p><p>외부네트워크연결시도0회. mock 서버화면시험·cs 프로젝트 서버HTTP확인·실제탑승·푸시·배포는하지않았습니다. 브라우저렌더링미확인.</p></main><script>document.querySelectorAll('button[data-filter]').forEach(b=>b.addEventListener('click',()=>{{document.querySelectorAll('#features tbody tr').forEach(r=>{{r.hidden=b.dataset.filter!=='전체'&&r.dataset.status!==b.dataset.filter}})}}));</script></body></html>'''
(assets/'mobility-readiness.html').write_text(page,encoding='utf8')

wiki = cs/'wiki/teams/mobility.md'
debug = root/state['debug']
backup(wiki,'최근접역_경로검증결과')
backup(debug,'최근접역_결함종료')
wiki.write_text(wiki.read_text(encoding='utf8')+f'\n\n## {stamp} 같은 최근접역의 다른 역 조합 경로 복구 검증 결과\n\n최근접역이 같아도 다른 물리적 역 조합을 기존 시간표·사고·출발 하한 판정에 넘깁니다. 신규12/12·관련118/118통과(실데이터16개제외). 저장200쌍의 해당1구간에서 조합0→7개, 지하철만 허용한 잠실1구간이 경로없음→모델32분경로로 수정후2/2회 같습니다. 도보포함8분선택은 유지됐고 지하철의 이른도착탐색도 복구됐습니다. [보고서](../records/reports/{report_name})·[시각화v33](../records/reports/assets/2026-10-09_mobility_readiness_v33/mobility-readiness.html). 새웹·실제탑승·전체최적성·기존94/96재측정·실시간지하철연결 완료는 아니며전체21판단4/9/8유지,배포하지않았습니다.\n',encoding='utf8')
debug.write_text(debug.read_text(encoding='utf8').replace('## 미해결','## 해결됨 (2026-10-09) — 같은 최근접역의 다른 역 조합 탐색 복구')+f'\n신규12/12·관련118/118통과, 기존잠실1구간지하철전용모델경로수정후2/2회·이른도착복구·도보8분선택유지를확인했습니다. 수정전8실패/4통과에는표현차이시험도포함되어8개의실운영결함으로세지않습니다. 모든누락경로나최적성을해결한것은아닙니다. [검증보고서](../{report_name}).\n',encoding='utf8')
save(ev/'backup-manifest-v1.json',state['backups'])
save(ev/'verification-proof-v1.json',{'created_at':now.isoformat(),'source_test_data_hashes':hashes,
    'new_tests':12,'related_tests':118,'before_failures':8,'deselected_data_tests':16,
    'scanned_existing_pairs':200,'same_nearest_pairs':1,'opened_pairs':1,'native_unique_pairs':1,
    'native_after_successes':2,'default_choice_preserved':True,'earliest_restored':True,
    'new_web_samples':0,'actual_trips':0,'network_attempts':0,'http_service_verified':False,'deployed':False,
    'features':21,'counts':catalog['counts']})
backs = '\n'.join('- ['+Path(x['backup']).name+']('+Path(os.path.relpath(root/x['backup'],report.parent)).as_posix()+')' for x in state['backups'])
body = f'''# 同じ最近接駅の別駅組合せを戻す検証

最も近い駅が同じという理由で他の駅の組合せも全て捨てていた条件を取り除きました。既存の潜室1区間で地下鉄だけを選んだ場合の経路が戻り、徒歩を許す場合は元の8分徒歩が選ばれます。

| 할 일 | 상태 | 진행 |
|---|---|---|
| 신규 시험 | 통과 | 12/12 = 100% |
| 확대 관련 시험 | 통과 | 118/118 = 100% |
| 지하철 전용 모델 경로 재생 | 산출 | 2/2 = 100% |

생성 {now.isoformat()}, 파일명은 생성 시각입니다. 신규12건은 관련118건 안에 있으며 실데이터표시16개는 이번 수집에서 제외했습니다. 기존 저장좌표1구간을 반복한 것이며 독립표본2개로 세지 않습니다.

## 원인과 변경

기존Planner._station_pairs는 양쪽 첫 역이 같으면 빈목록을 반환했습니다. 각 장소에 허용된 두번째·세번째 역이 있어도 시간표 판정에 넘기지 못했습니다. 이제 같은 물리적 역끼리만 제외하고 다른 조합은 기존 순서·상한대로 반환합니다. 동명이역의 노선군 구분·사고 역 제외·첫성립조합 중단·출발하한·시간표판정·선택기준은 유지했습니다. [변경원문](../evidence/{state['tag']}/owned-source-diff-v1.patch).

같은 최근접역으로 전체 조합을 버리는 기존시험은 옛판을백업하고 새계약에 맞춰 다른역을확인하도록 바꿨습니다. 더 많은 역을 하드코딩하거나 도보상한·요금·속도 보정값을 늘리지 않았습니다. 다른역조합이 하나도 없을때의이유도 실제로 확인한 범위로 좁혔습니다.

## 통제 시험

수정전8실패/4통과, 수정후74/74, 이른도착·동명이역시험을 포함한 확대118/118·종료코드0입니다.8실패에는 반환목록·설명문구 검사도 포함되므로8개의실운영결함으로세지않습니다. 신규12건은역목록조합6,동명이역1,공개구간호출의첫성립조합3,모든조합실패이유1,동일역빈승차제외1입니다. 공개구간호출3건은 실제Planner.leg를실행하지만 구간판정후보는주입한통제후보입니다. [원문로그·명령·Ruff](../evidence/{state['tag']}/).

## 저장 좌표·시간표 재생

기존200좌표쌍의최근접역을직선상한과기존물리적역규칙으로확인했습니다. 최근접역이같은것은G04잠실1쌍이고, 이구간의역목록을실제보행망접근거리로얻어전후대조했습니다. 접근목록은같고역조합만0→7개입니다.200구간의전체길찾기나기존지하철94/96성능지표를재측정한것은아닙니다.

지하철만허용한같은G04좌표와10:30도착목표·09:00출발하한에서이전·수정·수정·이전(ABBA)순으로시간표를재생했습니다. 이전2/2회경로없음,수정2/2회32분모델경로를얻었습니다. 경로는잠실→석촌→송파나루이며모델접근/이탈도보1,229m·예상요금1,550원입니다. 실제탑승·결제액이나웹최적경로가아닙니다. [재생원문](../evidence/{state['tag']}/native-path-replay-v1.json).

도보·지하철을함께허용한경우전후모두8분도보가선택됐습니다. 지하철만허용한이른도착탐색도이전경로없음에서경로산출로바뀌었습니다. 복구한32분지하철경로는8분도보보다빠르지않습니다. 기존첫성립조합중단정책이남아전체최단경로를보장하지않습니다. [선택유지·이른도착](../evidence/{state['tag']}/native-default-and-earliest-v2.json).

추가재생v1은계산검사후결과JSON에날짜객체를저장하다실패했습니다. 부분파일과실패메타를보존하고새스크립트v2에서날짜/시각을명시적으로ISO문자열로바꾸어다시검증·저장했습니다. 제품코드가실패한것으로세지않았고v2의완성된JSON만최종근거로사용합니다. 외부네트워크연결을차단했고연결시도0회입니다. 원자료와보행망해시는유지했습니다.

## 공식 문서·논문 확인

실행일2026-10-09에[Early Pruning for Public Transport Routing v4](https://arxiv.org/html/2603.12592v4)의초록·소개·3장네트워크모형을확인했습니다. 빠뜨린보행연결이경로를놓칠수있고안전한가지치기는정렬·단조성같은전제가필요함을확인했습니다. 이번최근접역동일조건제거는직접재현으로판정했으며논문의RAPTOR/가지치기알고리즘이나성능을적용·검증했다고쓰지않습니다.

[서울시 실시간지하철도착 공식명세](https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A)의다음역ID·종착역ID·열차종류·정보생성시각·초단위ETA를확인했습니다. 실제출발안내에연결하려면타려는열차와이항목을대조해야합니다. 이번에는지하철실시간선택기나시각덮어쓰기를구현하지않았으며그연결은남았습니다. [확인범위](../evidence/{state['tag']}/research-v1.json).

## 산출물과 남은 일

[제품 구간계산](../../../app/domains/travel_ops/instances/mobility/engine/plan.py),[새 시험](../../../tests/unit/travel/mobility/test_shared_nearest_station_v1.py),[변경된 기존시험](../../../tests/unit/travel/mobility/test_station_fallback_v1.py),[전체21개시각화v33](assets/2026-10-09_mobility_readiness_v33/mobility-readiness.html)에근거를보존했습니다. 조건부사용4·개선필요9·추가검증8은그대로이며완료율이아닙니다. 브라우저렌더링은미확인입니다.

실시간지하철의정확한열차/방향대조·실제탑승/환승재계산,회전제약의조건부/다중구간,혼합할인후운임,독립웹표본과나머지누락경로확보는남았습니다. 이번1구간복구를모든경로또는21개전체완료라고쓰지않습니다.

mock 서버 시험(화면 반응): 안 했음.
실서버 확인(서버 응답): 안 했음 — 로컬 엔진·시간표를 실행했으며 cs 프로젝트 서버 HTTP응답은확인하지않았습니다.

새 웹표본0개·지도 개발자API호출0회·실제탑승/결제0회입니다. 커밋·푸시·배포·외부메시지·결제를실행하지않았습니다.

## 백업과 재현

[백업 명세](../evidence/{state['tag']}/backup-manifest-v1.json)에덮어쓰기전판을보존했습니다.
{backs}

재현스크립트의정본은워크스페이스.tmp/mobility_complete_20261008안이며근거폴더에는읽기용사본을보존했습니다. after-v2원문에118개시험의실행명령·시각·종료코드가있습니다. 수정전은해당코드백업판으로재현해야합니다.
'''
body = body.replace('# 同じ最近接駅の別駅組合せを戻す検証','# 같은 최근접역의 다른 역 조합 경로 복구 검증').replace('最も近い駅が同じという理由で他の駅の組合せも全て捨てていた条件を取り除きました。既存の潜室1区間で地下鉄だけを選んだ場合の経路が戻り、徒歩を許す場合は元の8分徒歩が選ばれます。','가장 가까운 역이 같다는 이유로 다른 역 조합도 전부 버리던 조건을 제거했습니다. 기존 잠실1구간에서 지하철만 선택하면 경로가 나오며 도보도 허용하면 기존8분도보가 선택됩니다.')
report.write_text(body,encoding='utf8')
assert all(sha(root/p)==h for p,h in hashes.items())
assert all(sha(root/x['backup'])==x['sha256'] for x in state['backups'])
links = []
for p in [report,assets/'mobility-readiness.html']:
    txt = p.read_text(encoding='utf8')
    refs = re.findall(r'\]\(([^)]+)\)',txt) if p.suffix=='.md' else re.findall(r'href="([^"]+)"',txt)
    for ref in refs:
        ref = html.unescape(ref)
        if ref.startswith(('https:','http:','#')):
            continue
        target = (p.parent/ref).resolve()
        assert target.exists(),ref
        links.append(target.relative_to(root).as_posix())
artifacts = [report,assets/'mobility-readiness.html',assets/'readiness-catalog.json',wiki,
             ev/'verification-proof-v1.json',ev/'backup-manifest-v1.json']
for p in artifacts[:3]:
    assert not re.search(r'(?:\d{1,3}\.){3}\d{1,3}|webhooks/|@[0-9]',p.read_text(encoding='utf8')),p
for name in ['prepare_shared_nearest_station_v1.py','run_shared_nearest_station_v1.py','run_shared_nearest_station_v2.py',
             'audit_shared_nearest_station_v1.py','check_shared_station_default_v1.py','check_shared_station_default_v2.py',
             'publish_shared_nearest_station_v1.py']:
    shutil.copy2(scratch/name,ev/name)
save(ev/'publication-validation-v1.json',{'source_hash_matches':len(hashes),'backup_hash_matches':len(state['backups']),
     'local_links':links,'artifact_hashes':{p.relative_to(root).as_posix():sha(p) for p in artifacts},
     'browser_render_verified':False})
print(json.dumps({'report':report.relative_to(root).as_posix(),'hashes':len(hashes),
    'backups':len(state['backups']),'links':len(links)},ensure_ascii=False))
