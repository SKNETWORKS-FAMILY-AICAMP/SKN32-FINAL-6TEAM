# 2026-08-17 16:45 — REST API 실 classifier 종단(e2e) 라이브 테스트 추가

- 계획: (계획서 없음 — 직전 S-VOC-CLASSIFIER 작업의 "미해결 이슈"에서 이어짐)
- 담당: Claude(계약설계·발견한 계약 오류 직접 수정·검수) + Codex(S-LIVE-CLASSIFIER-E2E, 초안 작성)
- 수행: `tests/live/test_feedback_classifier_live_e2e.py` 신규(Codex). 실행 중
  Claude 의 계약 설계 실수 2건을 발견해 직접 수정:
  1. `create_app(controller=None)` 이 controller 실행을 막는다는 잘못된 가정 →
     실제로는 항상 진짜 controller 가 실행됨. 단언 대상을 최종 case 상태에서
     `CLASSIFIED` case_event 로 좁힘
  2. teardown 이 `agent_runs`/`team_tasks`/`llm_calls` 를 안 지워 첫 실행이
     `ForeignKeyViolation` 으로 정리 실패 → FK 순서 추가, 잔존 tenant 1개 수동 정리
- 검증: `pytest -m live` 2회 반복 실행 모두 통과, 매번 잔존 데이터 0건 확인.
  `pytest -q` 295 passed, 2 deselected(live 테스트 2건).
- 리포트: `wiki/records/reports/2026-08-17_S-LIVE-CLASSIFIER-E2E_리포트.md`(Codex),
  `wiki/records/evidence/LIVE-CLASSIFIER-E2E_검증.md`(Claude, 계약 오류 발견·수정 기록 포함)
- 의의: 이 세션 최고 심각도 결함(`PROD-CLASSIFIER-DOMAIN-MISMATCH`)의 수동 확인을
  자동화·재실행 가능한 회귀 테스트로 전환함.
