# Oracle ARM 상시 작업자의 HTTP 건강 검사 비활성화와 배포 대기 실패

## 해결됨 (2026-10-10)

2026-10-10 01:23 KST 실제 배포에서 API는 `/health` HTTP 200, 이동 자료 적재 성공, Docker healthy 상태였지만 배포 명령은 종료 코드 1을 냈습니다. 상시 작업자는 실행 중이며 재시작·OOM 없이 실제 작업 로그를 남겼습니다.

위치: `deploy/arm/deploy.py`의 전체 서비스 `compose up --wait`, `deploy/arm/compose.yml`의 worker `healthcheck.disable: true`.

원문 오류: `container tripilot-arm-worker-1 has no healthcheck configured`.
Docker Compose 2.40.3에서 HTTP 건강 검사를 비활성화한 같은 API 이미지의 상시 작업자까지 `--wait` 대상으로 넣었습니다. 이 명령 실패를 실제 앱 건강 실패와 구분해야 합니다.

수정 방향: DB·모델 연결기·API·웹은 `--wait`로 확인하고, HTTP 입구가 없는 상시 작업자는 별도로 실행한 뒤 기존 전체 컨테이너 검사(실행·재시작·건강 상태)로 확인합니다. 이미지 실패 복구도 같은 순서를 사용합니다. 검증을 삭제하거나 앱 건강 상태를 추정 성공으로 바꾸지 않습니다.

위험: 배포 상태가 실패로 남아 질의 대기열이 시작하지 못합니다. 전송 자체는 67/67개 SHA-256 일치로 성공했습니다. 기존 모델 추론 시험은 중단하지 않았습니다. 수정·실제 재확인 전에는 앱 전체 배포 완료라고 보고하지 않습니다.

해결 검증: DB·모델 연결기·API·웹 대기 후 상시 작업자 실행으로 수정했습니다. 회귀 검사 19/19 통과, 실제 배포 상태에 현재 SHA·ARM64 이미지 2개 저장, 컨테이너 5/5 실행·재시작/OOM 0, API·웹 HTTP 200, 기존 HTTP 대기열의 첫 회차 시작을 확인했습니다. [수정 후 근거](../2026-10-10_0130_arm-approved-mobility-transfer-and-deployment.md). 위의 초기 실패 관측은 당시 기록으로 보존합니다.
