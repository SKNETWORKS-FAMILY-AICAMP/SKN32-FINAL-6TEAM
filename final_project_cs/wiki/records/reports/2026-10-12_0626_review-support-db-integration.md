# 검토 문서·신고 화면·추가 DB 시험 접합

공통 기본 실행에서 건너뛴 PGlite12개를 기존 로컬 패키지로 다시 실행하고 PostgreSQL8개도 함께 확인했습니다. 결과는20/20입니다. 고객 신고 화면의 상담 답변을 암시하는 제목·메뉴를 문제 신고·건의 기록으로 맞췄으며 과거 안내 이력은 그대로 보여 줍니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 추가 격리 DB 시험 | 통과 | 20/20 = 100% |
| 신고 화면 단위 시험 | 통과 | 6/6 = 100% |
| mock 서버 화면 시험 | 통과 | 5/5 = 100% |
| 문서 Chromium 화면 검사 | 통과 | 4/4 = 100% |

## 실행 원본

- [DB JUnit](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/2026-10-12_061303_591088_isolated_integration/junit.xml), [소스·차단 결과](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/2026-10-12_061303_591088_isolated_integration/result.json), [정리](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/2026-10-12_061303_591088_isolated_integration/cleanup.json)
- [단위 시험 JSON](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/support-unit-2026-10-12_0621.json)
- [화면 시험 JSON](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/support-screen-2026-10-12_0623.json), [스크린샷](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/support-screen-2026-10-12_0623/)
- [문서 화면 원본](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/review-screens-2026-10-11T21-14-46-218Z/render-checks.json), [문서 내용·링크·해시 감사](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/review-audit-2026-10-12_061441.json)

DB 명령은 통합 전용 격리 실행기로 tests/integration/db/test_unattended_operations.py를 선택했습니다. OPS_PGLITE_MODULE은 이미 설치된 로컬0.3.14 패키지를 지정했습니다. 패키지를 새로 받거나 업무 DB를 열지 않았습니다. 원본 공통892통과·12건너뜀 결과는 보존하며 단일 실행904통과라고 바꾸지 않습니다.

웹 명령은 npm run test로 support.test.ts·client.test.ts를, npm run test:live로 support.spec.ts·uiux-sonnet-trip-20261012.spec.ts 중 관련5개를 선택했습니다. 전용 mock 포트·새 빌드 폴더를 사용하고 외부 지도 타일도 mock 응답을 사용했습니다. 첫 단위 실행은 Windows 임시 파일 접근 오류로 화면 모듈을 수집하지 못했으며4통과·모듈 오류1입니다. 작업 폴더 임시 경로의 재실행6/6으로 확인했습니다. 제품 코드 문제로 단정하지 않습니다.

문서2개를1440px·375px에서 렌더링해 넘침·SVG 글자 범위·중복 ID·오류·외부 요청을 검사했습니다. 문서 상단과 흐름 그림2장을 육안으로 확인했습니다. 표와 흐름 그림은 좁은 화면에서 해당 영역 안에서 가로 스크롤합니다. 이것은 고객 제품 화면 검증과 별도입니다.

mock 서버 시험5/5 (화면 반응): 재전송 요청 번호·CSRF·기록 완료·이전 안내·공지·목록 재시도·영어 빈 상태·키보드 초점을 확인했습니다.

실서버 확인 (서버 응답): 안 했음 — x600 서버의 cs 프로젝트 서버·외부 자료·고객 전송은 호출하지 않았습니다. 새 전용 PostgreSQL과 PGlite만 사용했습니다.

## 아직 닫지 않은 문제

여행 전체 실행 중 제품 소스는 바꾸지 않았습니다. 검증 담당의 단독22개 실행에서 발견된 시나리오 초기화4실패는 확장210개 실행에서는 통과했지만 단독 준비 문제는 남습니다. 프로세스 이동 설정 보호를 낮추지 않고 시험의 조립 준비를 맞춘 뒤 재검증합니다. 차단 계정의 API 안내에는 운영자 상담 문구가 남아 있어 전체 실행 종료 후 수정·관련 검증이 필요합니다.

여행 규정12문서130청크는 아직 적재하지 않았습니다. 기존 본문에는 자체72시간 무료 취소·24시간 되돌림·상담원 인계 문장이 있어 현재 확정 계약과의 적합성 확인이 먼저입니다. ARM의 안내11청크는 이것을 대체하지 않습니다. 구글 영업 판정 정책과 별개로 기존 가격 경로에는09-30 사용자 결정이라는 주석과 상한 예외가 있습니다. 원문 결정 연결을 확보하기 전에는 새벽 규칙으로 임의 축소하거나 예산을 늘리지 않습니다.

문서2개는 최종 인수 전 검토본입니다. 최신 여행 전체·실자료·외부 개인 AI 종단·배포 인수는 미완료이며 heartbeat를 종료하지 않습니다.

## 백업

[화면 문구 변경 전](../../../_backup/2026-10-12_061946_support_copy_integration/), [스크린샷 검사 보강 전](../../../_backup/2026-10-12_0623_support_screen_evidence/), [문서 재생성 전 안내서](../../../../program/plan/_backup/2026-10-12_061217_review_documents/), [기준선](../../../../program/baseline/_backup/2026-10-12_061217_review_documents/)에 이전 판을 보존했습니다. 소스 변경의 실제 해시와 현재 관측은 최종 통합 목록에서 다시 대조합니다.
