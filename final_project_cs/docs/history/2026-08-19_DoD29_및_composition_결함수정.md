## 2026-08-19 — DoD-29 사실수집·판정, composition 잠재결함 발견·수정

- 계획: 없음. Response Generation & Review 이식 직후, DoD-29 판정 근거를
  마련하려고 사실수집을 코덱스에 위임(`S-DOD29-FACTS.md`, 판정 금지 —
  사실만)
- 담당: Codex(사실수집) + Claude(판정, 결함 발견·수정)
- 수행: 사실수집 과정에서 `app/composition.py::_instantiate_team()` 이
  단일 인자 생성자를 개수로만 판단해, `ResponseGenerationReviewTeam(llm=None)`
  같은 형태에 `ReadToolbox` 를 `llm` 자리로 잘못 넣는 잠재 결함을 발견
  (등록 전이라 아직 안 터졌지만 등록하는 순간 즉시 `AttributeError`).
  파라미터 이름으로 분기하도록 수정. `docs/evidence/DoD-29_ResponseGenerationReview.md`
  작성 — 판정 부분통과(단위테스트·계약매핑 통과, config 미등록·실LLM
  미검증·golden 배분 없음이 남은 항목).
- 검증: 신규 회귀 테스트 1건(`test_instantiate_team_routes_single_positional_arg_by_name`),
  `pytest -q` **316 passed, 2 deselected, 실패 0**(315→316).
- 리포트: `docs/reports/debugs/2026-08-19_composition_단일인자_Team_llm_오배선.md`,
  `docs/reports/2026-08-19_DoD29-사실수집.md`, `docs/evidence/DoD-29_ResponseGenerationReview.md`
