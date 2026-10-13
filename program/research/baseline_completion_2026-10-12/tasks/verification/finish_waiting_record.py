"""전체 실행과 후속 실패를 보존하고 자기 담당 상태만 대기로 기록한다."""
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
CS=ROOT/'final_project_cs'
now=datetime.now(ZoneInfo('Asia/Seoul'))
run=HERE/'runs/2026-10-12_final_hash_1'
backup=HERE/'_backup'/now.strftime('%Y-%m-%d_%H%M%S_waiting_record')
backup.mkdir(parents=True)
for name in ('status.json','report.md','failure-handoff.md'):
    shutil.copy2(HERE/name,backup/name)

def result(folder,label):
    p=HERE/'runs'/folder
    value=json.loads((p/(label+'-outcomes.json')).read_text(encoding='utf-8'))
    collection=json.loads((p/(label+'-collection.json')).read_text(encoding='utf-8'))
    return {'label':label,'exit':value['exit'],'selected':len(collection['common_nodeids'])+len(collection['travel_nodeids']),
            'counts':dict(Counter(row['outcome'] for row in value['reports'] if row['when']=='call' or row['when']=='setup' and row['outcome']=='skipped')),
            'setup_teardown_errors':sum(row['outcome']=='failed' and row['when']!='call' for row in value['reports']),
            'finished_at_kst':value['finished_at_kst'],'junit':(p/(label+'.xml')).relative_to(ROOT).as_posix()}

common=result('2026-10-12_final_hash_1','common-final-v4')
native=result('2026-10-12_final_hash_1','operations-native-v1')
travel=result('2026-10-12_clean_travel','travel-v3c')
prior=result('2026-10-12_common_final_1','prior167-recheck')
recheck=result('2026-10-12_final_hash_1','travel-failures-recheck-v2')
remaining=json.loads((run/'remaining-failures.json').read_text(encoding='utf-8'))
families=Counter(row['nodeid'].split('::')[0] for row in remaining['failures'])
collection=json.loads((run/'travel-final-collection-collection.json').read_text(encoding='utf-8'))
manifest=json.loads((CS/'tests/test-suites.json').read_text(encoding='utf-8'))
registered=set(manifest['common'])|set(manifest['travel'])
disk={p.relative_to(CS).as_posix() for folder in ('tests','eval/tests') for p in (CS/folder).rglob('test_*.py')
      if not {'legacy','_backup','__pycache__'}&set(p.parts)}
assert disk==registered
assert not set(manifest['common'])&set(manifest['travel'])
assert common['selected']==899 and common['counts']=={'passed':891,'skipped':8}
assert native['counts']=={'passed':8} and native['exit']==0
assert recheck['counts']=={'passed':31,'failed':22}
assert json.loads((run/'cluster-stopped.json').read_text(encoding='utf-8'))['postmaster_pid_absent']
snapshot=sorted(run.glob('validation-snapshot-*.json'))[-1].name

text=f"""# 전체 검증 실행 완료·후속 통합 대기

공통·여행 시험을 실제로 나눠 실행했고 실패·준비 오류·건너뜀을 보존했습니다. 제품 전체 통과·배포 완료를 선언하지 않습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 시험 파일 목록 | 현재 디스크와 일치 | {len(disk)}/{len(disk)} = 100% |
| 최신 공통 기본 실행 | 정상 종료 | 899/899 = 100% |
| 운영 DB 동시성 별도 시험 | 통과 | 8/8 = 100% |
| 여행 재개분 | 실행 완료 | 6,746/6,746 = 100% |
| 최초 실패 선택 재검증 | 실행 완료 | 53/53 = 100% |

기록 시각: {now.isoformat()}. 위 진행률은 선택한 시험의 실행 완료율입니다. 제품 기능 통과율이 아닙니다.

## 판정 원본

- 공통: **891통과·8건너뜀**, 총 899. [JUnit](runs/2026-10-12_final_hash_1/common-final-v4.xml). 실행 전후 기존 소스 해시 변경 0개였습니다. 새 파일까지 포함하는 별도 전체 대조도 보존했습니다. 건너뜀 8개는 전용 PostgreSQL opt-in 조건이며 별도 실행에서 [8/8 통과](runs/2026-10-12_final_hash_1/operations-native-v1.xml)했습니다. 기본 건너뜀을 지우지 않습니다.
- 여행 재개분: **6,662통과·49실패·20준비 오류·15건너뜀**, 총 6,746. [JUnit](runs/2026-10-12_clean_travel/travel-v3c.xml). 앞선 중단 전 항목 167개는 [별도 최신 실행 167/167 통과](runs/2026-10-12_common_final_1/prior167-recheck.xml)입니다. 두 목록의 중복은 0개입니다. 공유 소스가 바뀐 여러 실행을 단일 안정된 전체 실행으로 부르지 않습니다.
- 후속 실패 재검증: 자료 조건 16개를 제외한 최초 실패·준비 오류 53개에서 **31통과·22실패**입니다. [JUnit](runs/2026-10-12_final_hash_1/travel-failures-recheck-v2.xml)·[남은 실패 22개와 해시 변경](runs/2026-10-12_final_hash_1/remaining-failures.json). 시험 이름 변경 3개는 선택 입력에 대응했습니다. 실행 중 연결 코드 5개가 바뀌었으므로 현재 소스 전체의 최종 인수 결과가 아닙니다.

최신 여행 재수집은 {len(collection['travel_nodeids']):,}개이며 **수집만 한 결과**입니다. 이전 기준선 6,913개보다 11개 늘었습니다. 이름 정정 3개와 UUID를 포함하는 동적 매개변수 식별자 1개를 단순 누락·신규로 세지 않습니다. [현재 수집 원본](runs/2026-10-12_final_hash_1/travel-final-collection-collection.json)·[실행별 분리 집계](runs/2026-10-12_final_hash_1/{snapshot}).

## 통합 담당에게 남긴 것

남은 22실패는 출발 재계산 4개·출발 실패 진단 1개·식당 대안 접합 7개·이동 재판정 2개·플러그인 HTTP 경계 6개·여행 평가 문구 1개·택시 검산 1개입니다. 시험용 대역의 필드·서비스 경계 불일치가 포함되므로 전부 제품 결함이라고 단정하지 않습니다. 정확한 함수·오류·접합안은 [실패 인계](failure-handoff.md)와 원본에 있습니다. 기능·시험 본문은 이 검증 담당이 수정하지 않았습니다.

자료 전제는 여행 규정 검색 2실패·14준비 오류, 실제 요식 자료 5건너뜀·택시 계획 자료 2건너뜀입니다. 새 자료 수집·모델 추론·업무 DB 복사를 하지 않았습니다. 기본 OAuth 8건너뜀은 [별도 격리 실행 8통과](runs/2026-10-12_common_final_1/oauth-enabled-v1.xml)로 연결합니다. 합성 조직 누락 6준비 오류는 준비 후 선택 실행에서 6통과했습니다.

실제 조회 정책·공통 오류 수집 접합 및 현재 소스 검증은 통합 담당의 진행 결과를 기다립니다. 운영 담당의 04:44 기록과 통합 담당의 05:30 후속 접합 기록을 같은 시점으로 섞지 않습니다. 인증 외부 연결·독립 검토·원격 가동·실제 알림은 미확인입니다.

## 재현·보존

시험 helper의 import 시각 고정 마감은 [수정 전/후 교대 재현](runs/2026-10-12_final_hash_1/fixture-deadline-comparison.json)으로 확인했습니다. 수정 전 만료 3/3 실패, 수정 후 같은 조건 3/3 정상이며 제품 제한을 늘리지 않았습니다. 삭제 뒤 남던 조회 기록은 [최신 실제 함수 재현](runs/2026-10-12_final_hash_1/trip-delete-latest.json)과 관련 18시험에서 정리됨을 확인했습니다.

Windows 비정상 종료 두 번은 원본으로 보존합니다. 여행 167통과 뒤 종료·공통 835통과 뒤 종료를 전체 통과로 합산하지 않습니다. 최신 공통 전체는 정상 종료했지만 런타임 비정상 종료의 근본 원인은 확정하지 않았습니다.

검증 전용 PostgreSQL 클러스터는 다른 연결 0개를 확인하고 종료했습니다. [종료 확인](runs/2026-10-12_final_hash_1/cluster-stopped.json). 새 동시성 전용 DB·역할도 [정리 확인](runs/2026-10-12_final_hash_1/native-postgres-cleaned.json)했습니다. 임시 자료 폴더·로그는 보존했고 실제 업무 DB·배포·고객 알림·커밋·push는 수행하지 않았습니다.

기존 원본·모델·환경·ODsay 대조는 [상세 보고서](report.md)에 있습니다. 이번 갱신 전 사본은 [백업]({backup.relative_to(HERE).as_posix()}/)에 보존했습니다. 자기 담당 상태는 `waiting_dependency`입니다.
"""
target=HERE/'current-results.md'
if target.exists():
    raise SystemExit('현재 결과 파일이 이미 있습니다. 새 이름이 필요합니다.')
target.write_text(text,encoding='utf-8')
with (HERE/'report.md').open('a',encoding='utf-8') as stream:
    stream.write(f'\n\n## 전체 실행 종료와 후속 대기 — {now.isoformat()}\n\n현재 수치·남은 실패·자료 전제·정리 결과는 [최신 결과](current-results.md)가 정본입니다. 공통 891통과·8건너뜀 및 별도 PostgreSQL 8통과, 여행 재개분 6662통과·49실패·20준비 오류·15건너뜀, 후속 실패 선택 31통과·22실패를 분리했습니다. 제품 완료를 선언하지 않습니다.\n')
with (HERE/'failure-handoff.md').open('a',encoding='utf-8') as stream:
    stream.write('\n\n## 최신 남은 실패 22개\n\n[최초 실패 선택 재검증](runs/2026-10-12_final_hash_1/travel-failures-recheck-v2.xml)은 31통과·22실패입니다. 실행 중 소스 5개가 바뀌었으며 [정확한 오류와 변경 목록](runs/2026-10-12_final_hash_1/remaining-failures.json)을 보존합니다.\n\n| 검사 파일 | 실패 수 |\n|---|---|\n')
    for name,count in sorted(families.items()):
        stream.write(f'| [{Path(name).name}](../../../../../final_project_cs/{name}) | {count} |\n')
    stream.write('\n출발 실패 진단은 대역 연결이 `None`인데 알림 저장의 `transaction()`에 도달했습니다. 식당 대안 7건에는 시험용 연결에 `cursor()`가 없는 경우와 가까운 식당 서비스 대역이 호출되지 않은 경우가 있습니다. 이동 2건은 실제 계산기 대역 대신 직선 추정으로 갔습니다. HTTP 경계 6건은 소유 모듈 비활성 상태에서 접수 복원 조회가 추가되고 대역 항목의 `starts_at`에 접근했습니다. 현재 계약·실제 서비스 경계와 시험 대역을 함께 대조해야 하며 assertion만 삭제하지 않습니다.\n')

status=json.loads((HERE/'status.json').read_text(encoding='utf-8'))
status.update(phase='waiting_dependency',updated_at_kst=now.isoformat(),verification_execution_complete=True,
    latest_execution={'manifest_files':len(disk),'common':common,'operations_native':native,'travel_resumed':travel,
        'prior_167_rechecked':prior,'initial_failures_rechecked':recheck,'current_travel_collection_only':len(collection['travel_nodeids'])},
    unresolved=['후속 선택 재검증 22실패: 정확한 오류·9파일·소스 변경 5개를 remaining-failures.json과 failure-handoff.md에 보존.',
                '자료 전제 미확인: 여행 규정 2실패·14준비 오류, 실제 식당 자료 5건너뜀, 택시 계획 자료 2건너뜀.',
                'Windows 비정상 종료 2회 원인 미확정. 최신 공통 전체는 정상 종료했으며 이력을 보존.',
                '현재 여행 수집 6924는 collection-only이며 최신 전체 단일 실행 통과가 아님.'],
    dependencies_remaining=['통합 담당: 남은 22실패의 제품·계약·시험 대역 접합과 변경 코드 영향 재검증',
        '운영·Dining·통합 담당: 실제 호출 정책·공통 오류 수집 접합 결과의 최종 해시와 시험',
        'RAG·Dining·Mobility 담당: 자료 적재 전제의 기존 증거 검토; 이 검증 세션은 새 외부 호출·모델 추론을 하지 않음',
        '최종 통합 담당: 계약·현재 소스·독립 검토·배포 상태를 구분한 최종 인수'],
    ready_reason='공통·여행 전체 실행과 실패 재현을 끝내고 원본·해시를 보존했습니다. 남은 22실패·자료 전제·동시 구현 변경의 최종 통합 결과를 기다립니다. 제품 완료·최신 전체 통과·배포 완료가 아닙니다.',
    report='report.md',current_results='current-results.md',failure_handoff='failure-handoff.md',
    cleanup={'own_postgres_stopped':True,'native_optin_database_dropped':True,'native_optin_role_dropped':True,'evidence_and_data_preserved':True},
    deployment='not_deployed',business_database='not_modified',notifications='not_sent')
status['changed_files']=['final_project_cs/tests/test-suites.json','final_project_cs/wiki/records/reports/2026-10-12_0426_baseline-verification-progress.md']+[p.relative_to(ROOT).as_posix() for p in sorted(HERE.iterdir()) if p.is_file()]
(HERE/'status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'phase':status['phase'],'current_results':str(target),'backup':str(backup),'remaining_failures':len(remaining['failures'])},ensure_ascii=False,indent=2))
