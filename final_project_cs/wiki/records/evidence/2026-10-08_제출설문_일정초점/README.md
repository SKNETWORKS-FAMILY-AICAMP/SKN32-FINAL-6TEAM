# 제출·설문·일정 초점 실행 근거

- 날짜: 2026-10-08. 기준 커밋: 38f9e08cb08cafba6ce2f66ff7b08c19788cf1d1 위 공유 작업 트리 수정 상태.
- 조건: 로컬 개발 PC, Chrome, mock 서버와 별도 Next 빌드. 단위 시험은 Vitest, DB 통합은 기존 로컬 PostgreSQL을 쓰는 pytest TestClient.
- 공개 CS 앱 응답 확인: 안 했음. 공개 배포: 안 했음.
- 화면 시험: plan-focus-loading-final.log 11/11 + plan-focus-regression-final.log 34/34 + plan-focus-layout-release.log 3/3 = 서로 다른 시험 48/48. 촬영 반복 실행은 총계에 더하지 않음.
- 단위 시험: loading-flow-unit-final.log 54/54 + loading-flow-consent-unit-final.log 15/15 + plan-focus-unit.log 7/7 = 76/76.
- DB 통합: loading-survey-backend-final.log 27/27. 실행: python -m pytest tests/e2e/test_intake_survey_questions.py -q.
- 오류 검사: plan-focus-lint-final-fixed.log, plan-focus-type-release.log가 빈 파일인 것은 오류 없이 종료 코드 0으로 완료했기 때문.
- 화면 명령: 웹 폴더에서 node node_modules/@playwright/test/cli.js test -c .tmp/consent-progress.config.ts --reporter=line. 파일명은 각 로그의 첫 시험 줄을 따른다. STUB_PORT/LIVE_PORT 지정, PLAYWRIGHT_CHANNEL=chrome. 마지막 배치 필터: 마커로 연|검증 중 마지막|바꾼 시간에는.
- 정정 근거: plan-focus-shots-final.log는 중앙 정렬 시험의 잘못된 시작 조건으로 1건 실패한 초기 기록이다. 마지막 위치 상한까지 확인한 최종 결과는 plan-focus-layout-release.log이다.
