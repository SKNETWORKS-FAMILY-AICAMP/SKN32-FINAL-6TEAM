# EKS 브라우저 시험 80.7초 · 연결 끊김 읽기 전용 추적 — 인계

## 현재 결론

시험 서버는 EKS(main `e88e01925`, A·B 포함)다. 서버 쪽 DB · 로그는 AWS 자격증명 무효로 못 읽었다. 「연결이 끊겼어요」는 웹 7초 감시 + 서버 SSE 가 DB 회차가 끝나야 beat 를 내는 구조에서 나오는 것으로 보이며, 접수 처리가 API pod 안에서 돌아 같은 CPU 를 나누는 것이 유력 정황이다(미측정). [보고서](../records/reports/2026-10-28_eks-browser-80s-reading-latency-readonly.md)

## 한 일 목록

- 규칙 · 인계 · 10-27 속도 보고서 · skill 을 읽고 `tools/safe_git.py fetch team` 만 실행.
- 서버 판별: DNS · 응답 헤더 · x600 Caddy/DB(읽기 전용) · CD (AWS) run `40488146501`.
- main 코드 경로 추적(접수 SSE · 웹 watchdog · pipeline.process · 위험 점검 · 배포 스크립트).
- 공개 미인증 GET 30회 측정, x600 기준선 SQL 재실행(after 0건).
- 이 접수 전용 EKS 읽기 전용 SQL 준비(실행 안 함): scratch `speed-80s-20261028/q_eks_intake_40c50259.sql`.
- 바뀐 파일: 이 인계 · 보고서 · 인계 목차 한 줄. 코드 · 설정 · DB · 서비스 변경 0.

## 남은 일

1. 사용자가 AWS 자격증명을 직접 설정 → SQL + api pod 지표로 80.7초 분할 · 끊김 원인 확정.
2. 후보 1(SSE beat 를 DB 회차와 분리) TDD — 부모 승인 뒤.
3. 후보 2(접수 처리를 API 밖으로) · 3(EKS 용량) · 10-27 순위 1·2·5 는 사용자 결정.
