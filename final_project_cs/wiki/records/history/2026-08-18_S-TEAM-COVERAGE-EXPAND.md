## 2026-08-18 — Team 모듈 시나리오 커버리지 확장 (order 취소, exchange 구분)

- 계획: 없음. 사용자가 "팀모듈 코드들도 다 안 짜둔 상황"이라고 직접
  지적 — 실제로 `order_shipping.py`/`return_exchange.py` 가 시나리오
  하나씩만 하드코딩 분기하고 있었음을 확인, `knowledge/documents/08`·`15`
  근거로 두 가지 실제 결함을 좁혀 계약(`S-TEAM-COVERAGE-EXPAND.md`) 작성
- 담당: Claude(정책 문서 근거 확정·계약 설계·독립검증) + Codex(구현)
- 수행: `order_shipping.py` 에 `order_change_or_cancel` 분기(출고 전만
  취소 제안, 출고 후는 기존 반품 경로로 pass-through) 추가.
  `return_exchange.py` 에 `EXCHANGE_REASON_CODES` 로 진짜 교환 요청을
  구분해 `exchange.request` 제안(항상 risk_level=high, 재고 미확인
  evidence 명시) 생성 — 재고 데이터가 DB 에 없어 지어내지 않고 정직하게
  "확인 불가"로 남김. 기존 `return.accept`/`refund.request` 경로 회귀 없음.
  신규 테스트 4건.
- 검증: `git diff` 전수 대조로 계약 준수 확인. 계약 자체의 오류
  (`Evidence.source_type="policy_chunk"` — 실제는 `"policy"`만 허용)를
  Codex 가 스스로 고쳐 구현했음을 확인. Codex 자체 리포트의 "3 failed,
  1 error"는 샌드박스 환경 제약(외부망 차단·임시디렉터리 권한)임을
  확인 — Claude 가 실 환경에서 재실행해 `pytest tests/unit/teams -v`
  8 passed, `pytest -q` **299 passed, 2 deselected, 실패 0** 확인.
- 리포트: `wiki/records/reports/2026-08-18_S-TEAM-COVERAGE-EXPAND_리포트.md`
