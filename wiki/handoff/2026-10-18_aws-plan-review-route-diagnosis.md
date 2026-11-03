# AWS 계획 확인·지도 경로 진단 인계 — 2026-10-18

## 한 일

- 운영 시작·실패 기록에서 이동 계산기 꺼짐과 `engine_unavailable`을 확인했다.
- API·worker의 이동 자료 경로와 볼륨 연결 누락을 확인했다.
- 실제 여행·수정 접수의 저장 검사와 경로 0개를 읽기 전용으로 확인했다. 운영 관련 코드 9/9 해시와 로컬 자료 명세·도로 그래프 무결성을 확인했다.
- [상세 진단·확인 한계·조치](../records/reports/2026-10-18_aws-plan-review-route-diagnosis.md)를 작성했다.

## 남은 일

- 자료 배포·읽기 전용 연결·적재 메모리/실제 경로 검증 후 API·worker의 운영 반영을 별도 작업으로 진행해야 한다.
- 기존 여행에 빠진 이동 정보는 자동 복구된다고 확인하지 않았다. 수정 접수 재검사와 고객 지도 화면을 함께 검증해야 한다.
- 이번 요청은 진단이며 운영 배포·재시작·고객 일정 변경·자료 업로드·예약 설정·커밋·푸시는 하지 않았다.

## 백업

- [wiki/records/reports/_backup/2026-10-18_132959_aws-route-diagnosis](../../wiki/records/reports/_backup/2026-10-18_132959_aws-route-diagnosis/)
- [wiki/_backup/2026-10-18_132959_aws-route-diagnosis](../../wiki/_backup/2026-10-18_132959_aws-route-diagnosis/)
- [wiki/handoff/_backup/2026-10-18_132959_aws-route-diagnosis](../../wiki/handoff/_backup/2026-10-18_132959_aws-route-diagnosis/)
