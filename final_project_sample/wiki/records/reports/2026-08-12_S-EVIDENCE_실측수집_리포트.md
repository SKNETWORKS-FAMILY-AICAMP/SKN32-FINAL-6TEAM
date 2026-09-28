# 2026-08-12 S-EVIDENCE 실측수집 리포트

## 수집 항목

`wiki/records/evidence/_raw/`에 다음 12개 파일을 추가했다.

- DoD-04, DoD-05, DoD-07, DoD-08, DoD-09, DoD-10
- DoD-13, DoD-14, DoD-15, DoD-16, DoD-17, DoD-18

## 실행한 명령과 기록

- 계약 테스트: `tests/contract/test_contracts.py`, 팀 계약 및 core isolation
- 보안 테스트: `tests/security`, `tests/integration/api/test_api_runtime.py`
- 일일 피드백: `python -m scripts.run_daily_feedback --date 2026-08-12`
- 통계: bootstrap 10000회, McNemar
- OpenAPI 경로 및 MCP 도구 이름 조회
- `git log --oneline`
- uvicorn 기동 후 네 UI 경로 HTTP 요청
- `scripts.verify_dod`

## 실행하지 못했거나 부분 실행한 명령

- ContextBroker 큰 입력 실측: tiktoken 인코딩 파일을 외부 URL에서 받는 단계에서 WinError 10013 네트워크 권한 오류가 발생해 `estimated_input_tokens`와 `omissions` 출력까지 도달하지 못했다.
- A/B/Proposed 및 holdout 전량 runner 실행: 실행하지 않았다.
- 문서와 OpenAPI/MCP 자동 일치 비교: 실행하지 않았다.
- 리포트 템플릿의 한계 절 확인 명령: 별도 결과를 수집하지 않았다.
- 브라우저 시각 검수: 실행하지 않았다.

## 서버 정리

UI 실측에 사용한 uvicorn 프로세스는 PID 29188 출력 후 종료했다.

## 파일 범위

변경 대상은 `wiki/records/evidence/_raw/`, `wiki/records/reports/`, `wiki/records/history/`로 한정했다.
