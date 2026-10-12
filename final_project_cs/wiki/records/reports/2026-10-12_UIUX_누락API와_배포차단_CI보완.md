# UIUX 누락 API · 자동 반영 차단 · 전체 웹 CI 보완

최신 완료 화면 통합에 이어 누락된 준비 계획 API와 자동 배포 차단 원인을 보완했습니다. 관련 로컬 검증은 통과했고 전체 GitHub CI 및 공개 운영 반영은 푸시 후 확인합니다. 기존 팀·개인 이력을 보존하며 role-manager 다음 develop에 같은 변경을 반영합니다. main은 변경하지 않습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 계약·보안·준비 계획 실제 API 경로 | 통과 | 416/416 = 100% |
| 배포 복원 안전 회귀 | 통과 | 21/21 = 100% |
| 웹 단위시험 | 통과 | 712/712 = 100% |
| 관련 브라우저 | 통과 | 68/68 = 100% |

준비된 계획은15개·목적 분류7개를 API에서 반환하고 접수 메타데이터를 유지합니다. 기존12개의 원문·실제 검증은 유지합니다. 배포 표시값만 달라지는 운영 구성에서 현재 실행값을 복원해 해시를 비교하고, 기능 설정 차이는 그대로 차단합니다. Docker Compose 해시는 서비스별로 각각 확인합니다.

전체 웹 CI 실패는 팀21개·개인19개였으며 차이2개는 완료 전 초기화·탐색하는 시험 경쟁 조건입니다. 로딩 중 전체 제목 유지 요구와 옛 시험을 맞추면서 지도 마커의 순차 공개 검사를 유지했습니다. 실제 시각 경계·시각 범위 간격·하단 여백·실패 안내 재발은 코드로 고쳤고, 식당 뱃지만 있는 일정의 표시 조건도 보완했습니다. 실패를 건너뛰거나 허용치를 늘리지 않았습니다.

공유 작업본과 통합본의 src 차이20개는 누락20개가 아닙니다. 앞선 CI에서 검증한 안내 인계·알림 대상 조회·초점 복구를 보존했습니다. 공백·선언/시험 순서 차이는 동작 차이가 아니며, 다른 채팅의 택시 요금/이동 후보 갱신·급행 표시·하루 요약·신고 기록 페이지 후속 변경을 무작정 섞지 않았습니다. 전체 작업 폴더를 복사하지 않았습니다. 식당 표시의 출처 공개 정책 변경도 이번 단순 뱃지 표시 결함 수정과 구분합니다.

검증은 전용 PostgreSQL과 외부망 차단 환경에서 진행했습니다. 업무 DB는 접근하지 않았습니다. 준비 계획 접수 HTTP 경로는 실제 앱을 실행했고 장소·이동 자료는 mock 제공자입니다. 프로덕션 빌드·타입 검사·변경 파일 정적 검사도 통과했습니다.

mock 서버 시험68/68 = 100% (화면 반응).

실서버 확인 (공개 cs 프로젝트 서버 응답): 이번 수정 후 새 API·화면은 아직 확인 안 했음. 공개 배포의 실행 이미지·건강 상태·실제 Docker Compose 해시는 읽기 전용으로 확인했습니다. 새 공개 배포 완료를 뜻하지 않습니다.

검증 명령: 전용 DB 실행기로 `pytest tests/contract tests/security tests/unit/core/test_migration_safe_deploy.py tests/unit/travel/test_intake_test_plans.py tests/e2e/test_intake_test_plans.py -m "not live"`; 웹 `vitest run --pool=threads --maxWorkers=1`, `tsc --noEmit`, 변경 파일 `eslint`, `next build --webpack`, 변경 관련 Playwright8개 파일68개. 자원 제한용 빌드 설정은 복원했고 원본·실패 기록은 비공개 백업에 보존했습니다. 공개 JUnit의 보안 검사 입력 예시 이름만 해시로 치환했으며 결과·개수는 바꾸지 않았습니다.

[전체 실행 요약](../evidence/2026-10-12_uiux-ci-deployment-repair/result.json) · [브라우저68개](../evidence/2026-10-12_uiux-ci-deployment-repair/browser-results.json) · [계약·보안 JUnit](../evidence/2026-10-12_uiux-ci-deployment-repair/backend-junit.xml) · [배포 회귀 JUnit](../evidence/2026-10-12_uiux-ci-deployment-repair/deployment-guard-junit.xml).
