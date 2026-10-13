from pathlib import Path
from datetime import datetime
from collections import Counter
import json, hashlib, shutil, os, re, difflib
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]; CS=ROOT/'final_project_cs'; NOW=datetime.now().astimezone()
state=json.loads((Path(__file__).parent/'collection-integrity-state-v1.json').read_text(encoding='utf8')); EV=ROOT/state['evidence']; DEBUG=ROOT/state['debug']
def rel(p): return p.relative_to(ROOT).as_posix()
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,obj):
    with p.open('x',encoding='utf8') as f: json.dump(obj,f,ensure_ascii=False,indent=2)
def link(p,q): return os.path.relpath(q,p.parent).replace('\\','/')
suite=ET.parse(EV/'related-v2.xml').getroot()
tests=sum(int(s.attrib['tests']) for s in suite.iter('testsuite'))
assert tests==505 and all(int(s.attrib.get('failures',0))+int(s.attrib.get('errors',0))==0 for s in suite.iter('testsuite'))
assert json.loads((EV/'ruff-v2-run.json').read_text(encoding='utf8'))['exit_code']==0
prior=json.loads((EV/'prior-manifest-v1.json').read_text(encoding='utf8'))
owned={'final_project_cs/wiki/teams/mobility.md','datasets/mobility/REPORT.md'}
prior_status={p:sha(ROOT/p)==h for section in ('source_test_data_hashes','artifact_hashes') for p,h in prior[section].items() if p not in owned}
assert all(prior_status.values())
save(EV/'prior-preservation-v1.json',{'checked':len(prior_status),'matched':sum(prior_status.values()),'intentionally_updated':sorted(owned)})
initial=json.loads((EV/'backup-manifest-v1.json').read_text(encoding='utf8'))
follow=json.loads((EV/'followup-backups-v1.json').read_text(encoding='utf-8-sig'))
# 途中のバックアップ名ではなく韓国語のファイル名へ統一する。
shutil.copy2(EV/'followup-backups-v1.json',EV/'followup-backups-original-v1.json')
for item in follow:
    b=ROOT/item['backup']; olddir=b.parent
    if olddir.exists() and '収集検証修正' in olddir.name:
        newdir=olddir.with_name(olddir.name.replace('収集検証修正','수집검증수정'))
        assert olddir.resolve().is_relative_to(ROOT.resolve()) and newdir.resolve().is_relative_to(ROOT.resolve())
        olddir.rename(newdir)
    item['backup']=str(Path(item['backup']).parent.with_name(Path(item['backup']).parent.name.replace('収集検証修正','수집검증수정'))/Path(item['backup']).name)
(EV/'followup-backups-v1.json').write_text(json.dumps(follow,ensure_ascii=False,indent=2),encoding='utf8')
final_backups=[]
for p in [DEBUG,CS/'wiki/teams/mobility.md',ROOT/'datasets/mobility/REPORT.md',ROOT/'datasets/mobility/scripts/README.md']:
    b=p.parent/'_backup'/NOW.strftime('%Y-%m-%d_%H%M%S_수집결과기록')/p.name
    b.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,b)
    final_backups.append({'path':rel(p),'backup':rel(b),'sha256':sha(p)})
save(EV/'publication-backups-v1.json',final_backups)
REPORT=CS/'wiki/records/reports'/(NOW.strftime('%Y-%m-%d_%H%M')+'_지하철_수집실패와_페이지누락_복구검증.md')
ASSETS=CS/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v48'; ASSETS.mkdir()
assessment={
 'observed_at':NOW.isoformat(),'official_sources':[
 {'url':'https://www.data.go.kr/data/15098554/openapi.do','updated_on':'2026-03-05','facts':'역별 시간표·페이지 번호/개수 분할·오류코드를 제공. HTTP 응답과 업무 성공을 구분해야 함. 이번에는 안내 페이지만 읽었으며 활용가이드 docx와 실응답 정상코드는 새로 확보하지 않음.'},
 {'url':'https://data.kric.go.kr/rips/M_01_02/detail.do?id=434&operation=subwayTimetableExp&page=1&service=trainUseInfo','registered_on':'2026-03-09','facts':'공식 열차별 시간표 문서에 trnNo와 exptCd 출력변수가 있음. 별도 소스 후보이며 현 보유 TAGO 자료의 개별 운행/정차를 확정하거나 실제 신청/호출한 것이 아님.'}],
 'gongdeok_attempts':{'web_direct':2,'web_result':'InternalError/not accessible','focused_public_search':'홍대입구/서울역 결과만 표시','existing_browser_tab':'홍대입구 본문바로가기 링크만 표시·스크린샷 실패·DOM도 링크 하나','complete_groups_acquired':0,'required_groups':4,'conclusion':'현재 사용한 웹 도구와 브라우저에서 공덕의 완전한 표를 확보하지 못함. 기관 전체 제공 불가 판정 아님.'},
 'actual_api_calls':0,'map_developer_api_calls':0,'new_aligned_web_routes':0,'actual_boarding_or_payment':0,
 'limits':['00/0000 정상코드만 허용하는 기존 공공데이터 어댑터 관례를 엄격히 검사한 통제 시험이며 이번 실제 TAGO 호출 검증은 아님.',
 '기존 잘못된 완료 표시·누락 규모는 원자료/체크포인트 미확보로 미계측. 기존 완료 목록을 비우거나 전체 재수집하지 않음.',
 '행 append와 완료 JSON은 두 파일이므로 전원 장애 사이 중복·동시 수집 exactly-once는 미해결.',
 '정차/통과 식별은 원문 필드 보존만 보강했으며 가공/제품 선택까지 해결한 것이 아님. raw_item에 없는 필드를 추정하지 않음.']}
save(EV/'source-assessment-v1.json',assessment)
catalog=json.loads((CS/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v47/readiness-catalog.json').read_text(encoding='utf8'))
catalog['created_at']=NOW.isoformat(); catalog['scope']='TAGO 수집 오류와 페이지 완전성·기존 시간표 보존'
update='v48: 기본/빈 조합 재조회 두 진입점에서 API 오류를 정상 빈 시간표로 처리하던 원인을 수정했습니다. 신규38/38·관련505/505(165선택제외), 페이지 전체 건수/번호/반복/누락 검사·원문 보존·조합별 완료 저장 확인. 실제 TAGO 호출/새 시간표 복구/공덕 공표 대조0이며 기존 지표의 재측정이나 정확도 승격이 아닙니다. 전원 장애 사이 두 파일 중복·기존 잘못된 완료 항목 대조·열차 정차 식별은 남았습니다.'
target=next(f for f in catalog['features'] if f['name']=='지하철 경로 산출'); target['current_update_v48']=update
counts=Counter(f['status'] for f in catalog['features']); assert dict(counts)==catalog['counts'] and len(catalog['features'])==21
save(ASSETS/'readiness-catalog.json',catalog)
body=f'''# 지하철 수집 오류·페이지 누락 복구 검증

수집 실패가 정상 빈 시간표로 남는 원인을 두 수집 진입점에서 수정했습니다. 현재 경로 정확도가 좋아졌다는 결과는 아니며 기존 시간표를 보존했습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| API 오류 재현 | 두 진입점 확인 | 2/2 = 100% |
| 새 수집 계약 검사 | 통과 | 38/38 = 100% |
| 기존 포함 관련 검사 | 통과 | 505/505 = 100% |
| 공덕 완전 공식 표 확보 | 조회 장애 | 0/4 = 0% |

## 문제와 원인

기본 수집은 HTTP200 body의 결과코드를 확인하지 않고, 실패도 빈 dict로 돌려준 뒤 완료 목록에 넣었습니다. 재조회도 오류 body를 ok 빈 자료로 처리했습니다. 인증 오류 코드30을 넣은 동일 통제 입력에서 두 함수 모두 잘못 수용한 것을 [수정 전 재현]({link(REPORT,EV/'before-reproduction-v1.json')})에 보존했습니다. 단일 첫 페이지(요청1000행)만 읽던 것도 전체 건수와 대조하지 않았습니다. 실제 보유 자료의 오류/누락 규모는 아직 미계측입니다.

## 해결한 범위

공통 응답 검사는 정상 코드(00/0000)·구조·전체 건수·페이지 번호와 크기·행수·반복 페이지를 검사합니다. 모든 페이지가 맞아야 성공을 반환하며, 오류와 빈 정상 자료를 구분합니다. 일시 오류만 제한 재시도하고 인증/일일 한도 오류는 반복하지 않습니다. 오류 메시지에는 인증값·요청 URL·제공처 본문을 넣지 않습니다.

원문 행은 raw_item에 보존하고 수집시각을 적습니다. 없는 열차 종류/번호/정차 여부는 만들지 않습니다. 기존 출력은 첫 쓰기 전 백업합니다. 검증 성공 조합은 행 flush/fsync 뒤 완료 JSON을 임시 파일 교체로 저장하므로 다음 API 오류 때 앞 성공 항목이 사라지지 않습니다. 두 파일 전체를 한 거래로 기록하는 것은 아니므로 전원 장애 사이 중복·동시 수집은 미해결입니다.

수정 파일: [공통 검사]({link(REPORT,ROOT/'datasets/mobility/scripts/_tago_checked.py')}) · [기본 수집]({link(REPORT,ROOT/'datasets/mobility/scripts/tago_subway_collect.py')}) · [빈 조합 재조회]({link(REPORT,ROOT/'datasets/mobility/scripts/tago_retry_empty.py')}) · [신규 시험]({link(REPORT,CS/'tests/unit/travel/mobility/test_tago_collection_integrity_v1.py')}). 기존 가공 시간표·공표 승차 대조 파일과 제품 계산은 바꾸지 않았습니다.

## 검증과 근거

신규38건은 오류코드·잘못된 JSON/메타·정상0건·공급자 페이지 상한·누락/변경/반복·재시도·인증값 비노출과 실제 수집 스크립트 진입점을 통제 응답으로 검사했습니다. 신규 포함505/505 통과, 전체층165건은 선택 제외입니다. [명령·원문]({link(REPORT,EV/'related-v2-run.json')}) · [로그]({link(REPORT,EV/'related-v2.log')}) · [Ruff2파일]({link(REPORT,EV/'ruff-v2.log')}) · [수집 관련3파일 구문 검사]({link(REPORT,EV/'syntax-v1.json')}). 첫 실행37/37 통과 후 미사용 import의 Ruff 실패1건을 수정했고, 성공 조합 뒤 오류를 다루는 검사1건을 추가했습니다. 기존 정규식 SyntaxWarning1개는 남았습니다. 통제 HTTP 응답 주입 시험이며 독립 운행 검증이 아닙니다.

mock 서버 시험(화면 반응): 안 했음, 0건.

실서버 확인(서버 응답): cs 프로젝트 서버 HTTP 확인 안 했음, 이번 실제 TAGO/지도 개발자 API 호출0회. 전체 수집이나 기존 원자료 가공을 실행하지 않았습니다.

공덕 공식4그룹은 웹 직접 조회 오류, 공식 도메인 검색에서 다른 역 결과만 표시, 기존 브라우저 탭 본문 미표시로 이번 확보0/4입니다. 공급자 전체 불가로 결론 내리지 않았습니다. [조회 범위와 한계]({link(REPORT,EV/'source-assessment-v1.json')}).

공공데이터포털 [TAGO 공식 안내](https://www.data.go.kr/data/15098554/openapi.do)는 역별 시간표의 페이지 분할과 인증/한도/형식 오류를 구분합니다(수정일2026-03-05). 안내 페이지를 확인했으며 이번 정상 실응답과 docx 가이드의 상세 필드는 재확보하지 않았습니다. [철도공단 공식 열차별 시간표 문서](https://data.kric.go.kr/rips/M_01_02/detail.do?id=434&operation=subwayTimetableExp&page=1&service=trainUseInfo)는 열차번호·급행구분 변수를 제공하는 대체 자료 후보입니다(등록일2026-03-09). 현재 열차의 정차를 확정하거나 대체 API를 확보했다는 뜻은 아닙니다.

## 보존과 남은 일

직전 해시308/308 일치를 시작 때 확인했습니다. 이번 허용 문서2개를 제외한 직전 파일 {len(prior_status)}/{len(prior_status)}가 그대로입니다. [보존 검사]({link(REPORT,EV/'prior-preservation-v1.json')}) · [원본 백업]({link(REPORT,EV/'backup-manifest-v1.json')}) · [후속 백업]({link(REPORT,EV/'followup-backups-v1.json')}) · [문서 기록 전 백업]({link(REPORT,EV/'publication-backups-v1.json')}).

전체21개 판정은 조건부3·개선9·추가검증9로 유지하며 완료율이 아닙니다. [현재 시각화]({link(REPORT,ASSETS/'mobility-readiness.html')}) · [21개 근거]({link(REPORT,ASSETS/'readiness-catalog.json')}). 브라우저 렌더링은 확인하지 못했으며 로컬 링크·문법을 검사했습니다. 커밋·푸시·배포·외부 메시지는 하지 않았습니다.

다음은 기존 완료 체크포인트/원자료를 확보해 잘못된 빈 조합을 특정하고, 공덕 공식 평일·휴일 양방향 표와 1대1 대조하는 것입니다. 열차번호/종류가 보존된 새 자료를 실제 정차 판정에 연결하는 일과 실제 ETA·탑승 검증도 남았습니다.
'''
with REPORT.open('x',encoding='utf8') as f:f.write(body)
text=DEBUG.read_text(encoding='utf8').replace('## 미해결','## 해결됨 (2026-10-09, 부분) — 수집 오류·페이지 검사')
text+=f'\n검증: 신규38/38·관련505/505·Ruff2파일 통과. [보고서]({link(DEBUG,REPORT)})·[실행 원문]({link(DEBUG,EV/"related-v2.log")}). 기존 잘못된 완료/누락 규모·전원 장애 사이 중복·정차 식별은 미해결입니다.\n'
DEBUG.write_text(text,encoding='utf8')
wiki=CS/'wiki/teams/mobility.md'; text=wiki.read_text(encoding='utf8').replace('`n수집 계약 보완:','\n수집 계약 보완:')
text+=f'\n\n## {NOW.strftime("%Y-%m-%d_%H%M")} 지하철 수집 오류와 페이지 완전성 결과\n\n수집/빈조합재조회2진입점의 오류→정상빈자료 오인을 수정하고 전체 페이지 검증·원문보존·조합별 완료JSON저장을 연결했습니다. 신규38/38·관련505/505(165선택제외)·Ruff2파일/구문3파일 통과. 실제TAGO호출·새시간표복구·공덕공표4그룹확보0·기존제품자료보존·21분류3/9/9유지·전체미완료. 기존잘못된완료항목·전원장애사이두파일중복·정차식별은남았습니다. [보고서]({link(wiki,REPORT)})·[시각화v48]({link(wiki,ASSETS/"mobility-readiness.html")})·[검증]({link(wiki,EV)}/).\n'
wiki.write_text(text,encoding='utf8')
for p in [ROOT/'datasets/mobility/REPORT.md',ROOT/'datasets/mobility/scripts/README.md']:
    with p.open('a',encoding='utf8') as f:f.write(f'\n\n## {NOW.strftime("%Y-%m-%d_%H%M")} TAGO 수집 성공·빈 자료 구분\n\n기본/빈조합재조회는 `_tago_checked.py`의 정상 결과·페이지 전체검사를 사용합니다. 실패는 기본 완료목록에 넣지 않고 재조회는 error로 보존합니다. 원문행은 raw_item·조회시각과 보존하며 기존 출력은 첫 쓰기 전 백업합니다. 성공 조합마다 완료 JSON을 교체하되 행/완료 두 파일 사이 전원장애 중복은 남았습니다. 신규38/38·관련505/505는 통제 응답 시험, 이번 실제수집0이며 기존 시간표/공표대조/명세는 바꾸지 않았습니다. [검증 보고서]({link(p,REPORT)}).\n')
from html import escape as e
cards=''.join(f'<article data-status="{e(f["status"])}"><h3>{e(f["name"])}</h3><p>{e(f["status"])} · {e(f["scope"])}</p><p>{e(f["metric"])}</p><details><summary>근거와 남은 부분</summary><p>{e(f["reason"])}</p><p>{e(f["need"])}</p><p>{e(f.get("current_update_v48",f.get("current_update_v47","")))}</p></details></article>' for f in catalog['features'])
svg='''<svg viewBox="0 0 960 304" role="img" aria-labelledby="collector-title collector-desc"><title id="collector-title">같은 오류 응답의 수정 전후 처리</title><desc id="collector-desc">수정 전에는 인증 오류를 빈 자료로 완료 처리했고, 수정 후에는 오류로 멈춰 완료 표시를 남기지 않습니다.</desc><defs><marker id="collector-arrow" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#193a56"/></marker></defs><g stroke="#193a56" stroke-width="2" fill="none" marker-end="url(#collector-arrow)"><path d="M272 80 H352"/><path d="M592 80 H672"/><path d="M272 208 H352"/><path d="M592 208 H672"/></g><g fill="#eef3f8" stroke="#193a56"><rect x="32" y="40" width="240" height="80" rx="8"/><rect x="352" y="40" width="240" height="80" rx="8"/><rect x="672" y="40" width="240" height="80" rx="8"/><rect x="32" y="168" width="240" height="80" rx="8"/><rect x="352" y="168" width="240" height="80" rx="8"/><rect x="672" y="168" width="240" height="80" rx="8"/></g><g fill="#193a56" font-size="20" text-anchor="middle"><text x="152" y="72">수정 전</text><text x="152" y="100">인증 오류 응답</text><text x="472" y="88">빈 시간표로 변환</text><text x="792" y="88">완료로 잘못 기록</text><text x="152" y="200">수정 후</text><text x="152" y="228">같은 인증 오류</text><text x="472" y="216">결과코드 검사·중단</text><text x="792" y="216">완료 표시 0건</text></g><text x="32" y="288" fill="#193a56" font-size="16">통제 입력의 처리 비교이며 실제 누락 경로 복구 수치가 아닙니다.</text></svg>'''
page=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 준비도 v48 — 수집 실패 구분</title><style>body{{margin:0;background:#f5f7fa;color:#193a56;font-family:system-ui,sans-serif;line-height:1.65}}main{{max-width:1120px;margin:auto;padding:24px}}h1{{font-size:32px;line-height:1.25}}h2{{margin-top:40px}}a{{color:#126b67}}.notice{{border-left:4px solid #a05a00;padding:16px;background:#fff1da}}svg{{width:100%;height:auto}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:12px;border-bottom:1px solid #cdd6df}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:16px}}article{{padding:20px;background:white;border:1px solid #cdd6df;border-radius:8px;overflow-wrap:anywhere}}summary{{cursor:pointer;color:#126b67}}select{{margin:12px;padding:8px;max-width:100%}}[hidden]{{display:none!important}}.scroll{{overflow-x:auto}}</style><main><p>triPilot · {NOW.strftime('%Y-%m-%d %H:%M')} · v48</p><h1>시간표 수집 실패를 완료로 남기지 않습니다</h1><p>수집기 두 곳의 오류 처리와 전체 페이지 검사를 수정했습니다. 기존 시간표를 교체하거나 경로 정확도를 승격한 결과는 아닙니다.</p><div class="scroll"><table><thead><tr><th>할 일</th><th>상태</th><th>진행</th></tr></thead><tbody><tr><td>신규 수집 검사</td><td>통과</td><td>38/38 = 100%</td></tr><tr><td>기존 포함 검사</td><td>통과</td><td>505/505 = 100%</td></tr><tr><td>공덕 공식 표 확보</td><td>조회 장애</td><td>0/4 = 0%</td></tr></tbody></table></div>{svg}<div class="notice">이번 실제 TAGO 호출·새 정렬 웹 경로·실탑승은 0건입니다. 기존 잘못된 완료 항목의 복구와 정차 열차 식별은 남았습니다.</div><h2>21개 기능의 현재 판단</h2><p>조건부 사용3/21 · 개선 필요9/21 · 추가 검증9/21. 분류 비중이며 완료율이 아닙니다. 아래 비교 수치는 기존 표본 기록입니다.</p><label for="filter">판정별 보기</label><select id="filter"><option>전체</option><option>조건부 사용</option><option>개선 필요</option><option>추가 검증</option></select><div class="grid">{cards}</div><p><a href="{link(ASSETS/'mobility-readiness.html',REPORT)}">보고서</a> · <a href="{link(ASSETS/'mobility-readiness.html',EV/'related-v2.log')}">검사 원문</a> · <a href="readiness-catalog.json">21개 근거</a> · <a href="{link(ASSETS/'mobility-readiness.html',EV/'backup-manifest-v1.json')}">백업</a></p><p>브라우저 렌더링 미확인. mock 서버 화면 시험·cs 프로젝트 서버 HTTP 확인·배포는 하지 않았습니다.</p></main><script>document.getElementById('filter').addEventListener('change',function(){{document.querySelectorAll('article[data-status]').forEach(card=>{{card.hidden=this.value!=='전체'&&card.dataset.status!==this.value;}});}});</script></html>'''
with (ASSETS/'mobility-readiness.html').open('x',encoding='utf8') as f:f.write(page)
assert page.count('<article data-status=')==21
for dest in re.findall('href="([^"]+)"',page):assert (ASSETS/dest).resolve().exists(),dest
for dest in re.findall(r'\]\(([^)]+)\)',body):
    if not dest.startswith('http'):assert (REPORT.parent/dest).resolve().exists(),dest
save(EV/'visual-validation-v1.json',{'cards':21,'local_links_exist':True,'accessible_svg_title_desc':True,'browser_rendered':False})
for name in ['prepare_collection_integrity_v1.py','reproduce_collection_integrity_v1.py','verify_collection_integrity_v1.py','verify_collection_integrity_v2.py',Path(__file__).name]:shutil.copy2(Path(__file__).parent/name,EV/name)
for b in initial:
    p=ROOT/b['path']
    if p.suffix=='.py':
        (EV/(p.stem+'-diff-v1.patch')).write_text(''.join(difflib.unified_diff((ROOT/b['backup']).read_text(encoding='utf8').splitlines(True),p.read_text(encoding='utf8').splitlines(True),fromfile=b['backup'],tofile=b['path'])),encoding='utf8')
sourcehashes={p:sha(ROOT/p) for p in prior['source_test_data_hashes']}
for p in [ROOT/'datasets/mobility/scripts/_tago_checked.py',ROOT/'datasets/mobility/scripts/tago_subway_collect.py',ROOT/'datasets/mobility/scripts/tago_retry_empty.py',CS/'tests/unit/travel/mobility/test_tago_collection_integrity_v1.py']:sourcehashes[rel(p)]=sha(p)
all_backups=initial+follow+final_backups
assert all(sha(ROOT/b['backup'])==b['sha256'] for b in all_backups)
files=[p for d in (EV,ASSETS) for p in d.iterdir() if p.is_file()]+[REPORT,DEBUG,wiki,ROOT/'datasets/mobility/REPORT.md',ROOT/'datasets/mobility/scripts/README.md']
save(EV/'final-integrity-v1.json',{'created_at':NOW.isoformat(),'source_test_data_hashes':sourcehashes,'artifact_hashes':{rel(p):sha(p) for p in files},'backups':all_backups,'full_feature_completion':False,'report':rel(REPORT),'assets':rel(ASSETS),'evidence':rel(EV)})
print(json.dumps({'report':rel(REPORT),'assets':rel(ASSETS),'tests':tests,'new_tests':38,'backups':len(all_backups),'source_hashes':len(sourcehashes),'artifact_hashes':len(files)},ensure_ascii=False))
