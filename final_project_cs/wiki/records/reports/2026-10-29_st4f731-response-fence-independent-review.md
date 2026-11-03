---
type: report
title: ST4F-731 corrected response fence 독립 검토
status: draft
domain: travel
impl_scope: cs
---

# ST4F-731 응답 fence 독립 검토

2026-10-29T05:54:22.046015+09:00. **해당 수정 경로에서 추가 차단 결함을 발견하지 못했습니다. 필수 security HOLD는 유지합니다.** 필수 관문은 2/3 = **66.7%**이며 병합·push·배포 승인이나 전체 제품 수락이 아닙니다. 원본 제품 코드·보안 탐지기·기존 보고서/증거·운영/고객 DB를 수정하지 않았고 커밋·push·배포·트래커 쓰기·파일 삭제는 0건입니다.

검토 대상은 [수정 후보 보고서](2026-10-29_st4f731-response-fence.md)와 그 누적 6파일 패치입니다. 구현 세션의 자가 검토와 별개의 세션에서 코드·시험을 읽고 새 사본·새 PostgreSQL로 반복했습니다. 사람 매니저/API 소비자 검토자의 수령·승인을 대신 주장하지 않습니다.

## 결론과 보완 사항

기존 반례인 마지막 current_review 이후 실제 edit가 커밋한 경우를 두 모드에서 HTTP **409 stale_revision**으로 엄격하게 확인했습니다. coherent 200을 허용하는 기존 반례 시험의 느슨한 단언을 독립 보강했습니다. 바깥 revision을 최신 판으로 바꿔 결과를 합법화하지 않습니다.

비차단 문서 보완 1건: 후보 `pipeline.py`의 autofix 설명에는 여전히 「세이브포인트 안의 edit만 잠그고 롤백하면 풀린다」고 적혀 있습니다. 새 `_autofix_fence`의 잠금은 savepoint 밖에서 잡으므로 **응답용 view를 확보하고 API 연결이 커밋/롤백할 때까지 유지**됩니다. 기존 설계 evidence와 보고서 끝부분 일부는 물음표로 손상되어 있습니다. 이 검토에서는 보존 지시에 따라 원문을 고치지 않았으며 아래에 실제 의미를 명확히 기록합니다. 추천 계산 자체는 접수 잠금을 새로 추가하지 않지만, 기존 current_review의 cache miss·risk schema 갱신·식사 판정 만료 저장은 별도로 접수 잠금을 잡을 수 있습니다. 따라서 모든 초기 캐시 상태에서 무조건 무잠금이라는 주장은 하지 않습니다.

## 최신 기준선과 원본 보존

시작과 최종 재확인에서 안전 진입점으로 팀·개인 role-manager를 실시간 조회했습니다. 양쪽 모두 `fab3da50ab970a7d8c79ed65c1df2e666abc1cd0`이며 후보 HEAD와 같습니다([조회 시각·해시](../evidence/2026-10-29_st4f731-response-fence-independent-review/remote-heads.json)). 새 통합이 필요한 원격 차이는 관측하지 않았고 원격 쓰기는 하지 않았습니다. 패치의 제품 2파일·시험 4파일이 후보와 검토 사본에서 **6/6 = 100%** 바이트 일치하며 reverse apply --check가 통과했습니다. 원본 Git 색인·sparse·설정은 변경하지 않았습니다.

원본 보고서·기존 후보 evidence·원본/후보 탐지기·기존 보안 XML의 보호 목록 **18/18 = 100%** 해시가 전후 같습니다. 기존 XML 해시는 `4139dd065887867094dd053a5e9de007697efe039a57a64b200dd15584bd3a0a`입니다. 원본 탐지기와 후보의 원격 탐지기는 시작부터 서로 다른 버전이며 각각 보존했습니다. 검증에는 후보의 탐지기를 그대로 썼고 XML 수정·가림·이동·추적 해제·허용 예외·탐지기 약화는 없습니다.

## 트랜잭션·잠금·실제 동시성

실제 제품 호출자는 `trip_api.web_intake_autofix` 한 곳입니다. `get_connection`은 psycopg 기본 autocommit=false 연결이며 첫 current_review SELECT가 연 트랜잭션이 계획 계산 → fence → edit → view까지 이어집니다. autofix 함수 자체가 별도 커밋하지 않습니다. API는 연결 컨텍스트를 성공적으로 나간 뒤에만 후속 작업을 예약합니다. 이 계약은 autocommit=true 연결이나 임의 외부 호출자까지 보장한다는 뜻이 아닙니다.

최종 fence의 WHERE는 tenant·customer·intake를 함께 제한하고 잠금 뒤 status와 요청 revision을 검증합니다. READ COMMITTED에서 계산 중 revision/state/customer/tenant 커밋은 각각 409/409/404/404로 거부됩니다. 최종 재확인 뒤의 실제 edit도 엄격한 409입니다. REPEATABLE READ·SERIALIZABLE의 동시 변경으로 fence SELECT가 40001을 받으면 stale_revision으로 전파되고 연결 경계 밖으로 빠져나가 롤백합니다. 커밋 시점 등 모든 40001 위치의 일반 정책을 시험하거나 추가하지 않았고 자동 재시도도 없습니다.

정상 저장의 순서는 접수 행 잠금 → claims/review 쓰기입니다. 기존 edit·review._store_read·dining_review.refresh/finish도 저장 시 접수 행을 먼저 잠그는 경로를 확인했습니다. fence는 같은 행을 먼저 잠그므로 그 순서를 뒤집지 않습니다. 전역 모든 테이블·모든 호출의 교착 부재를 입증했다는 주장은 아닙니다.

미리 보기는 fence 이후에 만든 savepoint 안에서 edit와 view를 실행하고 `_DryRunRollback`으로 새 claims/review/revision을 되돌립니다. fence는 그 바깥에 있어 preview rollback 뒤에도 연결 종료까지 살아 있습니다. 변경 미리 보기는 요청 revision과 가상 다음 view.revision이 의도적으로 다르며 preview=true입니다. 빈 추천은 두 revision이 같습니다. API는 pipeline의 이미 확보한 view를 그대로 사용하며 늦은 view 재조회·or 폴백이 없습니다.

후보의 4가지 변경 유무×두 모드 writer 시험뿐 아니라, 독립 시험에서는 시험용 사전 FOR UPDATE 없이 **실제 pipeline.edit가 다른 스레드/연결에서 실행되어 PostgreSQL의 Lock 대기 상태가 됨**을 pg_stat_activity로 확인했습니다. 응답 구성 동안 writer가 완료되지 않고 연결 커밋 뒤 새 판을 저장함을 확인했습니다. 계획 중 먼저 커밋한 실제 edit는 낡은 추천에 덮이지 않습니다. 서비스 호출은 fixture double이며 실모델·외부 서버·화면·부하 수락이 아닙니다.

## 부수효과와 실행 결과

독립 view 실패 주입은 적용/미리 보기 양쪽에서 revision·claims·reviews의 전후 동일과 후속 작업 0건을 확인했습니다. 정상 미리 보기·빈 추천도 같은 저장 항목이 유지되고 BackgroundTasks.add_task가 호출되지 않습니다. 변경 적용만 커밋된 새 revision을 다른 연결에서 확인한 뒤 작업이 예약됩니다. 계획·view의 기존 캐시 갱신 전체나 사용량 기록까지 무변경이라고 확대하지 않습니다. API의 `_count(place_search)`는 작업 전에 별도 연결로 web_usage를 기록하므로 dry_run·stale 실패에도 계수할 수 있는 기존 계약입니다. 해당 수정 경로에 업체 예약·결제·outbox 발송을 새로 추가하지 않았습니다.

전용 PostgreSQL 16.15, loopback 55528, DB `st4f731_review`와 data_directory가 이번 `scratch/st4f731-review2-20261029/pgdata`인 것을 실조회했습니다. 이전 55518 클러스터·공유/운영 DB는 사용하지 않았습니다. 한 번에 하나의 pytest 프로세스만 이 전용 DB에서 실행했고 변이와 정상 관문은 겹치지 않았습니다.

| 직접 재실행한 묶음 | 결과 |
|---|---|
| 후보 실DB 회귀 | 29/29 = 100% |
| 독립 트랜잭션·실제 writer·부수효과 | 14/14 = 100% |
| 독립 엄격 stale HTTP 반례 | 2/2 = 100% |
| 합계 실DB 표본 | 45/45 = 100%, 실패·오류·skip 0 |
| 결함 변이 탐지 | 3/3 = 100%, 기대한 실패 단언 5/5 = 100%, fixture 오류 0 |
| 정상 후보 복귀 후 intake 단위 | 1,063/1,063 = 100% |
| 계약 | 367/367 = 100% |
| 보안 | 124/125 = 99.2%, 기존 XML에 대한 동일 검사 1실패 |
| DoD | 26/26 = 100% |
| 필수 관문 | 2/3 = 66.7%, **HOLD** |

최종 fence 호출 제거·revision 비교 제거·FOR UPDATE 제거는 각각 실제 재확인 후 edit 2건·2건과 lock probe 1건의 AssertionError/기대 예외 부재로 탐지됐습니다. 매번 후보 SHA256 `bdcb24ec15e5e46191f8164923c6a1c788c5dae95c69e6397dd1790900d4c7bc`로 복귀했습니다. [집계](../evidence/2026-10-29_st4f731-response-fence-independent-review/summary.json)·[변이와 복귀 해시](../evidence/2026-10-29_st4f731-response-fence-independent-review/mutations.json)·[원본 보존 목록](../evidence/2026-10-29_st4f731-response-fence-independent-review/preservation-end.json)을 함께 보존합니다. 제품 전체 수락 분모는 모릅니다.

## 재현·한계·인계

최종 실행 helper·검토용 사본·시험 원문·시험 원시 로그·JUnit·pgdata는 `C:/_proj/final_workspace/scratch/st4f731-review2-20261029/`에 보존합니다. 전용 DB는 정상 종료했고 포트 연결 거부를 확인했습니다([종료 영수증](../evidence/2026-10-29_st4f731-response-fence-independent-review/pg-stop.json)). 보안 원시 로그/XML은 scratch에만 남기고 새 wiki evidence에 다시 복제하지 않았습니다. [증거 manifest](../evidence/2026-10-29_st4f731-response-fence-independent-review/manifest.json).

준비 실패도 숨기지 않습니다. shallow local clone이 pack 생성 전에 멈춰 이 세션의 해당 프로세스만 중단하고 실패 폴더를 보존했습니다. 이후 후보 폴더와 독립 .git을 새 `repo-copy`로 복사했고 원본을 대상으로 역복사하지 않았습니다. 초기 DB identity helper의 문자열 인용 SyntaxError를 수정한 뒤 실조회했습니다. 기본 Git/credential helper의 접근 거부는 기존 portable Git/gh를 프로세스 환경에서 지정해 해결했습니다. 초기 접근 오류와 SyntaxError는 세션 도구 출력에 남았고 별도 원시 파일로 복제하지 않았습니다. 전체 및 대상 한정 git diff --check는 이 호스트에서 멈춰 완료로 세지 않았습니다. 별도의 바이트 일치·reverse apply 검사는 완료했습니다. 기존 후보 보고서의 diff/ruff 통과는 이번 직접 실행 결과로 재사용하지 않습니다.

재실행은 이 새 전용 클러스터만 재시작하고 identity를 확인한 뒤 `run.py <새 로그명> -m pytest ...`로 수행합니다. 이미 존재하는 로그명은 helper가 거부합니다. 실행 목록은 `continue_tests.py`, 엄격 stale 명령은 `strict-stale.log`와 JUnit에 대응하며 추가 시험 원문을 새 evidence에 보존합니다.

다음 담당은 보존 원칙과 기존 검사기를 유지한 채 보안 차단을 정당하게 해소하고, 문서의 잠금 수명 설명을 보완하며, 반영 시점의 최신 role-manager와 필수 관문을 다시 확인해야 합니다. 이 검토 결과로 security HOLD를 해제하거나 ST4F-731을 종결하지 않습니다.
