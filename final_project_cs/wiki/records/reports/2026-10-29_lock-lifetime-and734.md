---
type: report
title: ST4F-731 후보 잠금 설명 정정과 ST4F-734 독립 회귀
status: draft
domain: travel
impl_scope: cs
---

# 후보 잠금 설명 정정과 ST4F-734 후속

2026-10-29 KST. ST4F-731의 security HOLD를 유지합니다. [최신 독립 검토](2026-10-29_st4f731-response-fence-independent-review.md)의 비차단 문서 지적을 격리 후보에서만 정정하고, 별도의 고우선순위 미완료 ST4F-734를 회귀 검증했습니다. 구현·자가 검증 담당은 이번 Codex 세션이며 독립 사람 검토자의 승인을 대신 주장하지 않습니다. 제품 전체 수락 분모는 모릅니다.

격리 후보 `scratch/st4f731-correction-20261029/repo`의 `pipeline.py` autofix·_pushed 설명과 현재 API 문서 `wiki/external/rest-endpoints/web-intakes.md`만 정정했습니다. 계산 자체가 잠금을 추가하지 않는다는 것과 current_review 캐시 갱신 등이 별도로 잠글 수 있다는 것을 구분합니다. 최종 fence는 미리 보기 savepoint 밖에 있으므로 preview rollback 뒤에도 응답용 view 확보와 API 연결의 바깥 트랜잭션 종료까지 유지됩니다. autocommit=false인 실제 API 호출을 전제로 하며 autofix 자체는 커밋하지 않습니다. docstring을 제거한 AST가 수정 전과 같아 실행 로직 변경이 없음을 확인했습니다. 기존 설계 evidence·보고서·XML을 고치지 않았습니다.

새 실제 PostgreSQL 시험은 변경 미리 보기 반환 후 원래 revision이 보존되는 동안 별도 연결의 FOR UPDATE NOWAIT가 거부되고, 바깥 commit 또는 rollback 후에는 잠금 획득과 실제 pipeline.edit가 성공하는지 검사합니다. 두 종료 경로 2/2 = **100%**, 기존 응답 fence 포함 8/8 = **100%**입니다. 서비스 조회는 fixture double이며 실모델·운영·브라우저 수락이 아닙니다.

새 TeamFlow GET은 상태×유형 16묶음을 받아 중복 id가 없음을 확인했습니다. ST4F-734는 high·review·미배정이고 읽은 조정 NOTICE에서 해당 키를 점유한 기록을 발견하지 못했습니다. 이는 사람의 인계 수락이나 담당자 배정이 아닙니다. 589·597·S3·EKS 작업을 변경하지 않았습니다. 트래커 쓰기와 다른 작업자에게 메시지 발송은 하지 않았습니다.

ST4F-734의 현재 keep_times 계약과 질문 칸 flow → editIntake keepTimes → API IntakeEditIn → pipeline.edit 호출을 대조했습니다. 후보 사본의 실제 DB 회귀 `test_intake_keep_times.py` 2/2 = **100%**로 장소 변경 저장·다른 일정 시각 유지·검사 수행·기본 재배치 경로를 확인했습니다. 별도 기존 격리 사본 `scratch/st4f729-policy-review-20261029/repo708`에서 `use-server-review-deferred.test.ts` 14/14 = **100%**도 재실행했습니다. 이 웹 사본의 기존 708 시험은 이번 집계에 넣지 않았습니다. 734 제품 코드 변경은 없고, 731 수정이 734의 전제라는 뜻도 아닙니다. 실서버·실기기 수락이 남아 ST4F-734를 종결하지 않습니다.

작업 파일·백업·원시 로그·JUnit·조회 원문은 `scratch/teamflow-lockdocs-20261029/`에 보존합니다. 실행 진입점은 `prepare.py`, `execute.py`, `followup.py`, `check_remotes_corrected.py`입니다. 기존 로그명을 재사용하지 않으며 보안 원시 XML은 새 wiki evidence로 복제하지 않습니다. [추가 문서 패치·시험 원문·집계](../evidence/2026-10-29_lock-lifetime-and734/summary.json)를 함께 봅니다.

준비 오류도 보존했습니다. 최초 identity helper가 get_connection 컨텍스트를 직접 연결로 오인한 AttributeError를 수정했습니다. 다음 재시작에서 포트 옵션 누락을 발견하고 이 세션의 identity 프로세스만 중단·전용 클러스터 정상 종료 후 55518로 재시작했습니다. DB명 st4f731·포트55518·실제 data_directory가 보존된 후보 pgdata임을 실조회했습니다. DB 회귀 종료 시 보안 묶음도 DB를 사용한다는 점을 놓쳐 먼저 종료한 순서 오류가 있었고, 해당 미완료 보안 프로세스를 중단한 뒤 DB를 유지한 새 실행으로 재검증했습니다. 이 중단 실행을 통과로 세지 않습니다. 첫 개인 원격 URL 오기를 수정한 뒤 안전 진입점 재조회로 팀·개인 role-manager 모두 `fab3da50ab970a7d8c79ed65c1df2e666abc1cd0`임을 확인했습니다. 원본 Git 설정·색인은 수정하지 않았습니다.

기존 독립 검토의 보호 목록 18/18 = **100%**가 이번 검산에서도 일치합니다. 원본/후보의 기존 탐지기와 보존 XML, 과거 보고서와 패치는 그대로입니다. 예외 추가·검사기 약화·증거 가림·이동·추적 해제·삭제가 없습니다. 원본 제품 코드·운영/고객 DB·공유 서비스 변경, 커밋·push·배포·이슈 종결도 0건입니다.

최종 필수 관문은 계약 367/367 = **100%**, 보안 124/125 = **99.2%**(동일 보존 XML 1실패), DoD 26/26 = **100%**로 **2/3 = 66.7%, HOLD**입니다. DoD의 하위 pytest와 보안 재실행 시간 일부가 겹쳤으므로 단일 프로세스 실행이라고 주장하지 않습니다. 관련 신규 DB 회귀 8건과 734 DB 회귀 2건은 순서대로 실행했습니다. 보안·DoD 종료 후 격리 클러스터를 정상 종료하고 55518 연결 거부를 확인했습니다. pgdata는 보존했습니다.

다음 작업은 734의 배포 환경에서 기존 시각 유지와 도착 질문 표시를 실제로 수락하는 것입니다. 731은 기존 보존 경계와 필수 보안 관문을 충족하기 전 통합하지 않습니다. 이번 새 시험이 보안 관문을 대신하지 않습니다.
