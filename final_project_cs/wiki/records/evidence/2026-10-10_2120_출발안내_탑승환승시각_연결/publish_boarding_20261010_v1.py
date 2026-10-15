from pathlib import Path
from datetime import datetime
from collections import Counter
from html.parser import HTMLParser
import difflib, hashlib, html, json, os, re, shutil, subprocess, sys

ROOT=Path(__file__).resolve().parents[2]
CS=ROOT/'final_project_cs'
TAG='2026-10-10_2120_출발안내_탑승환승시각_연결'
EV=CS/'wiki/records/evidence'/TAG
REPORT=CS/'wiki/records/reports'/f'{TAG}.md'
ASSETS=CS/'wiki/records/reports/assets/2026-10-10_mobility_readiness_v54'
sys.stdout.reconfigure(encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):return p.relative_to(ROOT).as_posix()
def write(p,text):
    with p.open('x',encoding='utf8') as f:f.write(text)
def save(p,obj):write(p,json.dumps(obj,ensure_ascii=False,indent=2))
state=json.loads((EV/'baseline-v1.json').read_text(encoding='utf8'))
baseline=state['baseline']
allowed=['final_project_cs/app/domains/travel_ops/instances/mobility/engine/departure_observer.py',
         'final_project_cs/app/domains/travel_ops/components/watch/trip_reminders.py',
         'final_project_cs/wiki/teams/mobility.md']
changed=[k for k,v in baseline.items() if sha(ROOT/k)!=v]
assert set(changed)==set(allowed),changed
results=json.loads((EV/'after-all-run-v3.json').read_text(encoding='utf8'))
assert results['cases']==186 and results['exit_code']==0 and not results['failures'] and not results['errors']
replay=json.loads((EV/'stored-seoul-replay-v3.json').read_text(encoding='utf8'))
assert replay['notice_status']=='ok' and replay['blocked_connections']==0
assert replay['observation']['boarding_steps'][0]['board_at']=='2026-10-09T12:59:26+09:00'
assert replay['notice']['values']['boarding_0_board']=='12:59'
previous_replay=json.loads((EV/'stored-seoul-replay-v2.json').read_text(encoding='utf8'))
assert previous_replay['notice']['values']['boarding_0_board']=='13:00'
for key in ('eta_min','arrival_at','worst_arrival_at','leg_results'):
    assert replay['observation'][key]==previous_replay['observation'][key]
save(EV/'seconds-display-comparison-v1.json',{'before_boarding_display':'13:00','after_boarding_display':'12:59','provider_prediction':'2026-10-09T12:59:26+09:00','model_departure_min':780,'eta_and_model_result_preserved':True,'first_replay_clock_failure_preserved':'stored-seoul-replay-v1.json','second_replay_clock':'이전 실제 조회 종료 시각에서 평가','limited_api_calls':0})
lint_files=[allowed[0].removeprefix('final_project_cs/'),allowed[1].removeprefix('final_project_cs/'),'tests/unit/travel/test_departure_boarding_guidance_v1.py']
lint=subprocess.run([sys.executable,'-m','ruff','check',*lint_files],cwd=CS,env=dict(os.environ,PYTHONIOENCODING='utf8'),capture_output=True,text=True,encoding='utf8',errors='replace')
save(EV/'lint-v1.json',{'files':lint_files,'exit_code':lint.returncode,'stdout':lint.stdout,'stderr':lint.stderr})
assert lint.returncode==0
patch=[]
for backup in state['backups']:
    if '/legacy/' not in backup['backup'] and backup['source'].endswith('.py'):
        patch+=list(difflib.unified_diff((ROOT/backup['backup']).read_text(encoding='utf8').splitlines(True),(ROOT/backup['source']).read_text(encoding='utf8').splitlines(True),fromfile=backup['source']+' (before)',tofile=backup['source']+' (after)'))
write(EV/'code-change-v1.patch',''.join(patch))
save(EV/'source-assessment-v1.json',{'checked_at':datetime.now().astimezone().isoformat(),'source':'https://gtfs.org/documentation/realtime/feed-entities/trip-updates/','applied_principle':'도착 예측/시간표/실제 관측을 구분하며 미제공을 정시 운행으로 가정하지 않음','not_applied':'서울 응답을 GTFS 피드로 간주하거나 첫 열차 지연을 다른 열차에 고정 전파하지 않음','algorithm_change':False,'paper_performance_claim':False,'process_overlap_scope':'관련 Python 명령 이름 필터 조회에 한정. 해당 필터 결과0이며 전체 작업자 부재를 단정하지 않음','quota_total_before':'미확인','quota_total_after':'미확인','quota_remaining':'미확인','quota_reset_at':'미확인','limited_api_calls':0,'network_attempts_in_replay':0,'minimum_daily_reserve_percent':20,'runtime_api_limits_changed':False})
debug=CS/'wiki/records/reports/debugs'/f'{TAG}_승차시각올림.md'
write(debug,'''# 현재 도착 예측을 분 단위로 올려 표시하는 문제

보유 서울 응답의 실제 생성시각+ETA는 12:59:26인데, 보수적 분 단위 재검증 결과 13:00을 새 고객 상세 승차 안내에 그대로 썼습니다. 안내만 보고 13:00에 승차 위치에 닿으면 예측 열차를 놓칠 수 있습니다. 이번 상세 안내 구현 중 발견했으며 배포하지 않았습니다.

원인은 검증기의 보수적 분 단위 시간과 고객에게 보이는 도착 예측 원시각을 같은 값으로 취급한 것입니다. 첫 승차의 board_at만 정확히 검증된 공급자 arrival_at을 보존하고, 모델의 승차·환승·총 소요 계산은 유지했습니다. 1/26/59초 경계3건은 수정 전3실패, 수정 후3통과입니다. 보유 응답 비교에서도 13:00→12:59 표시 변경, 나머지 모델 시각·총 소요 보존을 확인했습니다. 실제 열차를 놓친 사건을 측정한 것은 아닙니다.
''')
ASSETS.mkdir(exist_ok=False)
catalog=json.loads((CS/'wiki/records/reports/assets/2026-10-10_mobility_readiness_v53/readiness-catalog.json').read_text(encoding='utf8'))
assert len(catalog['features'])==21 and dict(Counter(f['status'] for f in catalog['features']))==catalog['counts']
catalog['created_at']=datetime.now().astimezone().isoformat()
catalog['scope']='로컬 개발판 구간별 승차/환승 안내 연결; 현재 운행·실탑승·전체21개 완료 아님'
catalog['latest_boarding_guidance']={'new_tests_passed':20,'related_tests_passed':166,'total_tests_passed':186,'stored_response_seoul_replay_pairs':1,'current_live_measurements':0,'deployed':False}
for i in (4,15,19):
    catalog['features'][i]['latest_evidence']='첫 승차의 현재 도착 예측과 후속 시간표 재계산을 구간별 출발 안내 문구틀/원값에 연결. 신규20/20·기존166/166·보유서울응답1쌍. 첫 승차 초 보존·자정 날짜 표시. 현재 실운행·실탑승·진행 중 위치 기반 재탐색·배포는 미확인.'
save(ASSETS/'readiness-catalog.json',catalog)
rows=''.join('<tr><td>'+html.escape(f['name'])+'</td><td>'+html.escape(f['status'])+'</td></tr>' for f in catalog['features'])
text=html.escape(replay['notice']['text'])
write(ASSETS/'mobility-readiness.html',f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>출발 안내 연결 검증 v54</title><style>body{{font:17px/1.6 system-ui;max-width:960px;padding:24px;margin:auto;color:#183044;background:#fafbfc}}table{{width:100%;border-collapse:collapse}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #ccd7dd}}pre{{white-space:pre-wrap;padding:20px;border:1px solid #ccd7dd;background:white;font:inherit}}a{{color:#135c93}}</style><h1>재계산한 승차·환승 시각을 출발 안내에 연결</h1><p>로컬 개발판. 아래는 2026-10-09 보유 공개 응답을 당시 시각으로 재생한 예이며 현재 운행 안내가 아닙니다.</p><table><tr><th>검증</th><th>결과</th></tr><tr><td>신규 연결·오류 차단·초/자정 경계</td><td>20/20 = 100%</td></tr><tr><td>기존 출발 관련 시험</td><td>166/166 = 100%</td></tr><tr><td>보유 서울 응답 연결 재생</td><td>1/1 = 100%</td></tr><tr><td>현재 실운행·실탑승 측정</td><td>0쌍</td></tr></table><h2>고객 출발 안내 예</h2><pre>{text}</pre><p>이전에는 바뀐 총 소요만 표시했습니다. 이제 첫 승차의 예측 시각·열차 번호·방면과 뒤쪽 환승/하차 예상 시각을 구분합니다. 12:59:26 예측을 13:00 승차로 올려 안내하지 않습니다.</p><h2>전체21개 기능 분류 유지</h2><p>조건부 사용3 / 개선 필요9 / 추가 검증9. 완료율이 아닙니다. 제한 API0회, 일일 예비량 최소20% 유지. 배포하지 않았습니다.</p><table><tr><th>기능</th><th>기존 분류</th></tr>{rows}</table><p><a href="../../{REPORT.name}">검증 보고서</a> · <a href="readiness-catalog.json">기능별 근거</a></p></html>''')
write(REPORT,f'''---
type: report
title: 재계산한 승차·환승 시각의 출발 안내 연결
date: 2026-10-10
status: local_verified
---

# 재계산한 승차·환승 시각의 출발 안내 연결

현재 도착 예측으로 다시 계산한 구간별 승차·환승·하차 시각을 고객 출발 안내에 연결했습니다. 첫 승차의 열차 번호·방면을 보존하고, 이후 시각은 모델 예상이라고 구분합니다. 로컬 개발판 검증이며 배포·현재 실운행 확인은 하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 최신 코드·시험·데이터·산출물 해시 | 일치 | 427/427 = 100% |
| 신규 연결·오류 차단·시간 경계 시험 | 통과 | 20/20 = 100% |
| 기존 출발 관련 회귀 시험 | 통과 | 166/166 = 100% |
| 보유 서울 응답 연결 재생 | 통과 | 1/1 = 100% |

분모는 직전 명세427파일, 신규 pytest20사례, 기존17파일 중 신규를 제외한166사례, 고정 서울 지하철 개발 경로1쌍입니다. 전체 21개 기능 완료율이 아니며 기존 조건부 사용3 / 개선 필요9 / 추가 검증9 분류를 유지합니다.

## 무엇이 달라졌나

이전에는 첫 열차 예측으로 후속 구간을 다시 계산하고도 총 소요 시간만 안내했습니다. 이제 구간별 승차·환승·하차 시각, 선택한 첫 일반열차 번호와 종착 방면을 문구틀과 원값으로 함께 전달합니다. 예측은 실제 승차 기록이 아닙니다. 첫 승차는 현재 도착 예측 반영, 하차와 이후 환승은 시간표·이동 모델 예상이라고 표시합니다. 미래 환승에 현재 다른 열차의 ETA를 붙이거나 API 조회 수를 늘리지 않았습니다.

보유 2026-10-09 공덕 응답을 실제 이전 조회 시작/종료 시각으로 재생하면 **12:59 공덕 승차(원 예측12:59:26, 5071열차·하남검단산 방면) → 13:10 종로3가 하차 예상 → 13:15 3호선 환승 예상 → 13:17 안국 하차 예상**이 나옵니다. 최종 장소 도착은13:19 모델 예상입니다. 10월10일 현재 안내로 사용한 것이 아니며, 개발자가 고정한 구간·접근도보를 사용했습니다. 계획기가 추천한 새 경로 또는 출입점 정렬 검증으로 부르지 않습니다.

재생 중 새 상세 안내가 초 단위 예측12:59:26을13:00 승차로 올려 표시하는 문제를 확인했습니다. 고객에게 공급자 원시각을 보존하도록 수정했고 모델의 보수적 분 단위 검증·환승·총 소요 계산은 유지했습니다. 1/26/59초 경계3건은 수정전3실패→수정후3통과입니다. [원인 기록](debugs/{debug.name})·[초 표시 비교](../evidence/{TAG}/seconds-display-comparison-v1.json).

## 검증과 적용 전제

첫 신규16사례는 수정전15실패·호환1통과였고, 연결 후16통과였습니다. 자정 날짜1사례와 초 경계3사례를 추가해 신규20/20·기존166/166·전체186/186을 확인했습니다. 늦어진 첫 열차에 따라 후속 환승10:15→10:20 변경, 조회 실패 시 모델 안내, 잘못된 시각·중복 구간·누락 장소·실시간 근거 오표시 차단, 기존 콜백 호환, 실제 구성기→팀 끼움 자리→출발 문구틀 연결을 포함합니다. 첫 승차 조회1회만 유지합니다. [최종 시험 로그](../evidence/{TAG}/after-all-v3.log)·[명령/개수](../evidence/{TAG}/after-all-run-v3.json)·[수정전 결과](../evidence/{TAG}/before-v1.xml)·[초 경계 수정전](../evidence/{TAG}/seconds-before-v1.xml).

보유 자료 재생은 실제 시간표/역ID/노선 순서/승차 모델을 적재하고 보존된 공개 응답18행을 기존 소스로 정상화했습니다. 처음에는 재생 시계를 수신 전으로 고정해 확인시각 미래 판정으로 모델 대체되었고, 실제 이전 조회 종료 시각을 사용해 다시 실행했습니다. 원 응답·생성시각은 수정하지 않았습니다. 실패 결과도 보존했습니다. [최종 재생 원문](../evidence/{TAG}/stored-seoul-replay-v3.json)·[시계 설정 실패 기록](../evidence/{TAG}/stored-seoul-replay-v1.json)·[표시 수정전 재생](../evidence/{TAG}/stored-seoul-replay-v2.json). 외부 네트워크 연결 시도0회입니다. Ruff3파일 통과입니다. 시험 종료 뒤 pyreadline3 소멸자 경고가 stderr에 남았으나 최종 pytest 종료코드0·실패0·오류0·건너뜀0입니다.

[GTFS 공식 Trip Updates 문서](https://gtfs.org/documentation/realtime/feed-entities/trip-updates/)는 실시간 갱신 미제공을 정시 운행으로 가정하지 않도록 설명합니다. 여기서는 관측 예측·시간표 모델을 구분하는 전제만 확인했습니다. 서울 응답을 GTFS 피드라고 간주하지 않았으며 다른 열차에 첫 지연을 일괄 전파하지 않습니다. 새 탐색 알고리즘이나 논문 성능 주장은 적용하지 않았습니다.

mock 서버 시험: 안 했음 (화면 반응 미확인). 위 결과는 로컬 Python 통제 응답/보유 자료 재생입니다.

실서버 확인 (서버 응답): 안 했음 — cs 프로젝트 서버 HTTP 요청·배포를 하지 않았습니다. 현재 API 도착 오차·실제 도보/탑승/하차·결제 측정0쌍입니다. 현재 위치/탑승 완료 상태를 받는 여행 중 재탐색, 순환선/급행 확대, 운임·도로·독립 웹 대조는 여전히 남습니다.

## 변경·보존·API 예산

제품 변경은 [이동 출발 재검증](../../../app/domains/travel_ops/instances/mobility/engine/departure_observer.py), [출발 안내](../../../app/domains/travel_ops/components/watch/trip_reminders.py), [신규 시험](../../../tests/unit/travel/test_departure_boarding_guidance_v1.py)입니다. 선택 필드 계약을 이동 wiki에 먼저 적었습니다. `boarding_steps`가 없는 기존 콜백은 호환됩니다. 잘못된 상세 시각은 전체 안내 실패로 드러냅니다. 날짜가 바뀌면 다음 날짜를 원값에 포함합니다. [변경 패치](../evidence/{TAG}/code-change-v1.patch).

덮어쓰기 전 [이동 계산기 원본 백업](../../../app/domains/travel_ops/instances/mobility/engine/_backup/{TAG}/departure_observer.py)·[출발 안내 원본 백업](../../../app/domains/travel_ops/components/watch/_backup/{TAG}/trip_reminders.py)·[이동 wiki 원본 백업](../../teams/_backup/{TAG}/mobility.md)을 보존했으며 코드 원본은 [legacy 보존본](../../../legacy/{TAG}/app/)에도 있습니다. 이후 수정 전 판들도 백업했습니다. 기존427파일 중 허용수정3파일 이외424/424를 보존합니다. 원자료·가공자료·운영 설정·예약 주기·알림 정책을 바꾸지 않았습니다. 관련 Python 작업명 필터 조회만 수행하여 전체 작업자 부재를 단정하지 않습니다.

제한 API 호출0회입니다. 공급자/프로젝트/키별 공유 누적량·잔여량·갱신 시각은 조회 전후 미확인으로 기록합니다. 원자 공유 예산을 확보할 수 없어 API를 호출하지 않았으며 최소20% 일일 예비량을 유지합니다. [근거·API 기록](../evidence/{TAG}/source-assessment-v1.json). 커밋·푸시·배포·외부 전송·결제를 하지 않았습니다.

[시각화v54](assets/2026-10-10_mobility_readiness_v54/mobility-readiness.html)·[최종 해시/백업 검사](../evidence/{TAG}/final-integrity-v1.json). 시각화의 정적 구조·링크는 검사했으며 브라우저 렌더링 시험은 하지 않았습니다.
''')
wiki=CS/'wiki/teams/mobility.md'
wiki_before=sha(wiki)
backup=wiki.parent/'_backup'/(TAG+'_결과발행전')/wiki.name
backup.parent.mkdir(parents=True,exist_ok=False)
shutil.copy2(wiki,backup)
assert sha(wiki)==sha(backup)==wiki_before
addition=f'\n\n## 2026-10-10 출발 안내 승차·환승 시각 연결 결과\n\n현재 첫 승차 예측과 후속 재계산 시각을 고객 출발 문구틀/원값에 연결했습니다. 지하철 첫 열차 번호·방면, 모델 환승/하차 구분, 첫 예측 초 보존·자정 날짜 표시. 신규20/20·기존166/166·전체186/186·Ruff3파일·보유서울응답1쌍 연결. 추가API0·실탑승/현재운행/배포확인0·21분류3/9/9유지·전체미완료. [보고서](../records/reports/{REPORT.name})·[시각화v54](../records/reports/assets/2026-10-10_mobility_readiness_v54/mobility-readiness.html)·[검증](../records/evidence/{TAG}/).\n'
wiki.write_text(wiki.read_text(encoding='utf8')+addition,encoding='utf8')
backups=list(state['backups'])+[{'source':rel(wiki),'backup':rel(backup),'sha256':wiki_before}]
extra=[CS/'app/domains/travel_ops/components/watch/_backup/2026-10-10_2125_자정경계안내/trip_reminders.py',CS/'tests/unit/travel/_backup/2026-10-10_2125_자정경계안내/test_departure_boarding_guidance_v1.py',CS/'app/domains/travel_ops/instances/mobility/engine/_backup/2026-10-10_2128_승차예측초보존/departure_observer.py',CS/'wiki/teams/_backup/2026-10-10_2128_승차예측초보존/mobility.md',CS/'tests/unit/travel/_backup/2026-10-10_2128_승차예측초보존/test_departure_boarding_guidance_v1.py']
backups += [{'backup':rel(p),'sha256':sha(p)} for p in extra]
assert all(sha(ROOT/b['backup'])==b['sha256'] for b in backups)
for script in ['prepare_boarding_20261010_v1.py','run_boarding_20261010_v1.py','run_boarding_20261010_v2.py','run_boarding_20261010_v3.py','replay_boarding_20261010_v1.py','replay_boarding_20261010_v2.py','replay_boarding_20261010_v3.py','publish_boarding_20261010_v1.py']:
    shutil.copy2(Path(__file__).parent/script,EV/script)
class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.links += [v for k,v in attrs if k=='href']
parser=Links();parser.feed((ASSETS/'mobility-readiness.html').read_text(encoding='utf8'))
assert all((ASSETS/link).resolve().exists() for link in parser.links)
mdlinks=[v for v in re.findall(r'\]\(([^)]+)\)',REPORT.read_text(encoding='utf8')) if not v.startswith('https://')]
missing=[v for v in mdlinks if not (REPORT.parent/v).resolve().exists() and not v.endswith('/final-integrity-v1.json')]
assert not missing,missing
save(EV/'publication-validation-v1.json',{'catalog_features':21,'counts':catalog['counts'],'visual_local_links':len(parser.links),'report_local_links':len(mdlinks),'missing_links':missing,'browser_render_verified':False,'backup_count':len(backups)})
changed=[k for k,v in baseline.items() if sha(ROOT/k)!=v]
assert set(changed)==set(allowed)
source_hashes={k:sha(ROOT/k) for k in baseline}
source_hashes[rel(CS/'tests/unit/travel/test_departure_boarding_guidance_v1.py')]=sha(CS/'tests/unit/travel/test_departure_boarding_guidance_v1.py')
artifacts={rel(p):sha(p) for folder in (EV,ASSETS) for p in folder.iterdir() if p.is_file()}
for p in (REPORT,debug):artifacts[rel(p)]=sha(p)
save(EV/'final-integrity-v1.json',{'created_at':datetime.now().astimezone().isoformat(),'source_test_data_hashes':source_hashes,'artifact_hashes':artifacts,'allowed_changes':allowed,'unchanged_baseline_files':424,'backups':backups,'full_feature_completion':False,'deployed':False})
print(json.dumps({'tests_passed':186,'preserved_baseline_files':424,'backups':len(backups),'tracked_hashes':len(source_hashes)+len(artifacts),'report':rel(REPORT)},ensure_ascii=False))
