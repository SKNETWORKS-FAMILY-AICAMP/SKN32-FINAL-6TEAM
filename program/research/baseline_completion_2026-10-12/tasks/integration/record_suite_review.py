"""전체 원본과 후속 재시험을 고유 시험별로 대조하고 검토본을 갱신합니다."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter
import hashlib, json, shutil, re
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
CS=ROOT/'final_project_cs'
now=datetime.now(ZoneInfo('Asia/Seoul'))
stamp=now.strftime('%Y-%m-%d_%H%M%S')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
backup=HERE/'_backup'/(stamp+'_suite_review')
def preserve(p):
    target=backup/p.relative_to(ROOT)
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(p,target)
def update(p,text):
    preserve(p)
    p.write_text(text,encoding='utf-8')

runs=[
 ('common','2026-10-12_055926_851705_isolated_integration'),
 ('travel','2026-10-12_060205_589376_isolated_integration'),
 ('pglite_and_postgres','2026-10-12_061303_591088_isolated_integration'),
 ('standalone_scenarios','2026-10-12_063837_727042_isolated_integration'),
 ('db_security_contract','2026-10-12_063901_843730_isolated_integration'),
 ('historical_phase_mapping','2026-10-12_064050_588718_isolated_integration'),
 ('oauth_postgres','2026-10-12_064139_625995_isolated_integration'),
]
evidence=[]
merged={}
provenance={}
base_keys=set()
for index,(label,folder) in enumerate(runs):
    run=HERE/'checks'/folder
    result=read(run/'result.json')
    cleanup=read(run/'cleanup.json')
    assert cleanup['own_cluster_stopped'] and not result['source_changed'],label
    cases=ET.parse(run/'junit.xml').getroot().findall('.//testcase')
    outcomes={}
    for c in cases:
        name=c.attrib['name']
        # 이 한 매개변수만 수집 때 uuid4()를 생성한다. 사례 종류를 유지해 대응한다.
        if c.attrib['classname']=='tests.security.test_personal_ai_oauth':
            name=re.sub(r'^(test_access_record_must_match_its_grant_audience_owner_client_and_scope\[customer-)[0-9a-f-]{36}(\])$',r'\1<generated-uuid>\2',name)
        key=(c.attrib['classname'],name)
        state='failed' if c.find('failure') is not None else 'error' if c.find('error') is not None else 'skipped' if c.find('skipped') is not None else 'passed'
        assert key not in outcomes,(label,key)
        outcomes[key]=state
    if index<2:
        assert not set(outcomes)&base_keys
        base_keys.update(outcomes)
    else:
        assert set(outcomes)<=base_keys,(label,set(outcomes)-base_keys)
        assert set(outcomes.values())=={'passed'},label
    merged.update(outcomes)
    provenance.update({key:label for key in outcomes})
    evidence.append(dict(label=label,path=run.relative_to(ROOT).as_posix(),junit_sha256=sha(run/'junit.xml'),counts=dict(Counter(outcomes.values())),total=len(outcomes),exit=result['exit'],source_changed=result['source_changed'],blocked_attempts=dict(Counter(result['network_blocks'])),own_cluster_stopped=True))
assert len(base_keys)==7850
counts=dict(Counter(merged.values()))
remaining=[dict(classname=k[0],name=k[1],outcome=v,latest_run=provenance[k]) for k,v in merged.items() if v!='passed']
summary=dict(at_kst=now.isoformat(),runs=evidence,unique_tests=len(merged),latest_per_test_counts=counts,remaining=remaining,identity_normalization='test_personal_ai_oauth의 customer 매개변수 한 사례만 수집 시 생성 UUID를 표준화; 다른 매개변수는 합치지 않음',limit='고유 시험별 마지막 관측의 대조이며 단일 전체 실행의 통과 결과가 아님. 자료 전제·실자료·외부 종단·운영 적용 미검증은 남음.')
out=HERE/'checks'/('suite-review-'+stamp+'.json')
out.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

report_path=CS/'wiki/records/reports'/('2026-10-12_'+now.strftime('%H%M')+'_whole-suite-integration-review.md')
lines=['# 전체 회귀와 후속 접합 검토','',f'관측: {now.isoformat()}. 제품 최종 인수·출시 승인이 아닙니다.','',
'| 실행 | 통과/전체 | 실패·오류·건너뜀 |','|---|---|---|']
for row in evidence:
    c=row['counts'];lines.append(f"| {row['label']} | {c.get('passed',0)}/{row['total']} | 실패{c.get('failed',0)}·오류{c.get('error',0)}·건너뜀{c.get('skipped',0)} |")
lines+=['',f"고유 시험별 후속 관측은 {counts.get('passed',0)}/7850 통과입니다. 단일 전체 재실행 결과로 합산하지 않습니다. [원본·해시·시험별 남은 결과](../../../../"+out.relative_to(ROOT).as_posix()+').', '',
'여행 전체 원본은 6,892통과·2실패·37준비 오류·15건너뜀입니다. 격리 실행기가 시험 자체의 임시 DB를 거절한23개는 같은 새 전용 PostgreSQL의 명시적 임시 이름 두 종류만 허용한 뒤 모두 통과했습니다. 업무 DB·외부 연결 제한은 유지했고 접근 규칙10/10을 별도 확인했습니다.', '',
'단독 시나리오4개는 실제 조립의 프로세스 설정 키를 먼저 준비하도록 시험 초기화를 보완한 뒤 새 프로세스4/4로 확인했습니다. 차단 계정 안내는 문제 신고·건의 기록의 범위를 정확히 표시하도록 수정했고 DB·보안·계약404/404로 확인했습니다. 이력 단계 분류의 누락 경로3개를 P10 통합 구성에 연결했고 기존 규칙14/14와 최근20개 이력 strict 검사를 통과했습니다. 현재 팀 소유·출시 판정은 바꾸지 않습니다.', '',
'여행 규정12문서130청크의 실제1024차원 벡터 자료 전제16개, 요식 원장5개와 이동 자료2개는 남습니다. 자료 구조 검사 통과를 현재 정책의 의미 적합성·실제 검색 통과로 바꾸지 않습니다. 빈 벡터·임의 규칙·업무 DB 복사로 닫지 않았습니다.', '',
'전체 실행 중 DB 차단12회와 외부 또는 기존 로컬 서비스 연결 차단4회를 기록했습니다. 목적지는 원 실행기에 수집하지 않았으므로 그4회의 정확한 출처를 단정하지 않습니다. 연결은 차단됐으며 원본을 남깁니다. 후속 선택 실행의 차단 횟수는 각각의 JSON에서 확인합니다.', '',
'공통·여행 고유 수집7,850개, 중복0개를 대조했습니다. 전체 원본의 보안92/92·계약283/283·구조156/156·평가16/16 및 v11 당시 관문 연결26/26을 확인했습니다. 이 관문 연결은 현재 wiki의 실자료·외부 종단·운영 환경 인수를 대체하지 않습니다.', '',
'mock 서버 시험(화면 반응): 이번 후속 DB 검증에는 해당하지 않습니다. 앞선 고객 신고 화면5/5는 별도 원본입니다.', '',
'실서버 확인(서버 응답): 새 전용 PostgreSQL을 실행했고 모두 종료했습니다. 외부 제공처·운영 cs 프로젝트 서버는 새로 호출하지 않았습니다.', '',
f'[문서 변경 전 백업](../../../../{backup.relative_to(ROOT).as_posix()}/). [제품 코드·시험 백업](../../../_backup/2026-10-12_063829_post_suite_integration/), [이력 분류 백업](../../../_backup/2026-10-12_064048_phase_mapping_integration/), [격리 실행기 백업](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/_backup/2026-10-12_063827_scratch_database_guard/)을 보존했습니다.', '',
'실제 개인 AI 등록·공개 HTTPS·쿠키·callback 종단, 현재 적합성이 확인된 검색 자료·벡터, 무료 관측 충족률, 도로 방향 실자료, 택시 미터 정확도 및 운영 영속 볼륨 인수는 남습니다. 업무 DB 변경·배포·재시작·유료 호출·고객 알림·commit·push·다른 채팅 메시지를 수행하지 않았습니다.']
assert not report_path.exists()
report_path.write_text('\n'.join(lines)+'\n',encoding='utf-8')

guide=ROOT/'program/plan/triPilot_구현계획서_v12.md'
baseline=ROOT/'program/baseline/triPilot-baseline-2026-10-12.md'
g=guide.read_text(encoding='utf-8')
g=g.replace('| 최신 여행 전체 시험 | 실행 중 | 분모6,946개 |','| 최신 여행 전체 원본 | 종료·후속 검증 | 6,892/6,946 = 99% |')
g=g.replace('| 인계 실패의 선택 재검증 | 통과 | 22/22 = 100% |','| 단독 시나리오 재검증 | 통과 | 4/4 = 100% |')
g=g.replace('여행 전체 종료·자료 전제','검색·실자료 전제')
g=g.replace('최신 여행 전체 회귀와 계약·보안·관문의 최종 해시 대조를 마칩니다.','공통·여행 전체 원본과 후속 DB·보안·계약 재시험을 대조했습니다. 전체 원본은 통과만 있는 실행이 아니며, 검색·실자료 전제가 남습니다. [최신 통합 검토](../../'+report_path.relative_to(ROOT).as_posix()+')에 원본과 후속 결과를 연결했습니다.')
update(guide,g)
b=baseline.read_text(encoding='utf-8')
b=b.replace('최신 여행 전체 실행과 필수 자료·외부 연결 조건이 남아 있으므로','최신 전체 실행을 마쳤으나 필수 자료·외부 연결 조건이 남아 있으므로')
b=b.replace('| 최신 여행 전체 시험 | 실행 중 | 분모6,946개 |','| 최신 여행 전체 원본 | 종료·후속 검증 | 6,892/6,946 = 99% |')
b=b.replace('| 최신 여행 전체 | 실행 중 | 결과·최종 해시 대기 |','| 최신 여행 전체 원본 | 6,892통과·2실패·37오류·15건너뜀 / 총6,946 | 변경0·전용 PostgreSQL 종료 |')
b=b.replace('단독 준비 보완 전에는 이를 닫지 않습니다.','실제 조립의 설정 키를 준비하도록 시험 초기화를 보완한 뒤 단독4/4를 확인했습니다. [최신 후속 검토](../../'+report_path.relative_to(ROOT).as_posix()+')에서 DB·보안·계약404/404, OAuth 실제 PostgreSQL8/8, 이력 분류14/14와 원본을 연결합니다.')
b=b.replace('최신 전체가 끝난 뒤 새 원본과 현재 코드 해시로 판정합니다.','최신 전체와 후속 실행을 고유 시험별로 대조했으며 단일 전체 통과 실행으로 합치지 않습니다.')
b=b.replace('최종 계약·보안·현재 출시 관문은 이 실행 결과와 정확한 항목 대응을 추가해야 합니다.','전체 원본의 보안92/92·계약283/283·구조156/156·평가16/16 및 v11 당시 관문 연결26/26을 대조했습니다. 고정 파일 변경 검사는 통과했고 이력 분류 누락3개도 보완했습니다. [관문 대조](../research/baseline_completion_2026-10-12/tasks/integration/checks/final-gate-2026-10-12_064132/summary.json)는 현재 wiki의 실자료·외부 종단·운영 인수 통과를 뜻하지 않습니다.')
b=b.replace('최신 여행 전체 및 정확한 보안·계약·관문 대응을 완료하고, 추가 변경이 생기면 영향 시험을 다시 실행합니다.','전체 원본과 후속 재시험을 정확한 시험별로 대조했습니다. 추가 변경이 생기면 영향 시험을 다시 실행합니다.')
b=b.replace('실제 모델·원격 A2A·전체 여행','실제 모델·원격 A2A·검색 자료 전제')
b=b.replace('| 최신 전체 회귀 |','| 검색·실자료 전제 |')
update(baseline,b)

state=read(HERE/'status.json')
preserve(HERE/'status.json')
state.update(updated_at_kst=now.isoformat(),phase='waiting_dependency',latest_review_report=report_path.relative_to(ROOT).as_posix(),latest_suite_review=out.relative_to(ROOT).as_posix(),dependencies_remaining=['실제 개인 AI 등록·공개 HTTPS·쿠키·callback 종단','현재 정책 적합성이 확인된 여행 규정 자료와 실제1024차원 벡터16개 전제','요식 원장5개·이동 자료2개 및 실경보 방향·택시 미터 정확도','무료 관측 충족률·가격 예외 결정·운영 영속 볼륨 인수'],unresolved=['최종 인수 전 검토본 유지; 필수 외부·자료 조건 미충족','고유 시험별 후속 결과와 단일 전체 실행 결과를 구분','기존 추적 datasets57개 인덱스는 미변경'],ready_reason='전체 원본과 후속 선택 회귀·관문을 확인했습니다. 외부 종단·실자료·환경 인수 조건 때문에 최종 완료로 표시하지 않습니다.')
state['tests']+=evidence[1:]
state['changed_files']=sorted(set(state['changed_files']+[report_path.relative_to(ROOT).as_posix(),'final_project_cs/scripts/map_commits_to_phase.py','final_project_cs/app/domains/travel_ops/modules/web_account/web_cookie.py','final_project_cs/tests/scenario/test_departure_express_db_v1.py','final_project_cs/tests/scenario/test_departure_party_db_v1.py']))
(HERE/'status.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
own_report=HERE/'report.md'
update(own_report,own_report.read_text(encoding='utf-8')+'\n\n## 전체 실행 종료 후 검토\n\n'+f"최신 전체 및 후속 재시험 근거: [{report_path.name}](../../../../../{report_path.relative_to(ROOT).as_posix()}). 고유 시험별 마지막 관측 {counts.get('passed',0)}/7850; 단일 전체 통과 실행이 아닙니다. 자료·실환경 조건은 상태 파일에 남겼습니다.\n")
print(json.dumps(dict(summary=out.relative_to(ROOT).as_posix(),counts=counts,report=report_path.relative_to(ROOT).as_posix(),backup=backup.relative_to(ROOT).as_posix()),ensure_ascii=True))
