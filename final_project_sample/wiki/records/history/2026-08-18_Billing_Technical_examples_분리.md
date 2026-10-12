## 2026-08-18 — Billing/Technical 예시 모듈 분리

- 계획: A-COP v8 §10의 착수 목록 제외 Team을 프로덕션 경로 밖 examples로 분리
- 담당: Codex
- 수행: Billing/Technical 모듈과 업무 로직 테스트를 `examples/`로 이동하고 config/export/Docker 제외 규칙/상태 문서 갱신. 현재 production Team인 Feedback Analytics와 Response Review는 보존.
- 검증: 범위 회귀 `125 passed, 1 warning`; 전체 `360 passed, 3 failed, 1 deselected, 1 error`. 실패 3건은 OpenAI embeddings 네트워크 차단, 오류 1건은 pytest 임시 디렉터리 권한 거부.
- 리포트: `wiki/records/reports/2026-08-18_Billing_Technical_examples_분리_리포트.md`
