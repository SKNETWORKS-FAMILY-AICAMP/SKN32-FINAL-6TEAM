# DoD-29 — Response Generation & Review 검증

- v8 §27 신설 항목 / 근거: `wiki/records/reports/2026-08-19_DoD29-사실수집.md`(사실 수집,
  Codex) + 이 문서(판정, Claude)
- 판정: **통과** (2026-08-20 배선·golden/holdout 커버리지 완료로 갱신 —
  근거: `wiki/records/reports/2026-08-20_S-DOD29-COMPLETE_리포트.md`.
  2026-09-01 GEN→REV 2호출 흐름 실제 실행 검증으로 재갱신, 아래 참고)

## 재현 명령과 실제 출력

```powershell
python -m pytest tests/unit/teams/test_response_review.py -v
```
```
6 passed in 1.17s
```

## ★2026-09-01 재검증 — 3개 세부 기준(a)(b)(c) 개별 확인

v8 §27 의 DoD-29 원문은 세 세부 기준을 요구한다: (a) GEN→REV 두 호출 흐름이
**실제로 실행**되는지, (b) REV 반려 시 재시도 상한이 적용되는지, (c) 개인정보가
섞인 응답을 REV 자체 검증이 차단하는지. 위 "통과로 갱신된 이유" 표는 이 셋을
개별적으로 대조하지 않고 "단위 테스트 통과" 로 뭉뚱그렸다 — 실제로 대조해보니
(a)에 구멍이 있었다.

### (a) GEN→REV 두 호출 흐름 — 재검증 전엔 실제로 실행되지 않았다

`app/modules/customer_ops/response_review.py::execute()` 는 `response.generate`
(GEN) 응답에 `tone_ok` 필드가 없을 때만 `response.review_tone`(REV) 를
두 번째 LLM 호출로 실제 실행한다(96~132행). 그런데 `tests/unit/teams/test_response_review.py`
와 `tests/unit/teams/test_response_review_team.py` 의 **기존 테스트 전부**가
GEN 응답 fixture 에 `"tone_ok": True/False` 를 미리 인라인해 REV 호출을 건너뛰게
만들고 있었다 — 심지어 `test_response_review_team.py::test_deterministic_review_runs_before_tone_llm`
는 `assert "response.review_tone" not in llm.calls` 로 REV 미호출을 **명시적으로
단언**하는 테스트였다. 즉 fixture/contract test 로는 두 호출 흐름이 실제로
이어지는 경로를 아무도 밟지 않고 있었다(실 LLM 을 쓰는 `tests/live/test_response_review_live_smoke.py`
만 이 경로를 우연히 통과했을 수 있으나, `live` 마크로 API 키가 있어야 돌고
DoD-29 가 요구하는 "fixture와 contract test" 범주 밖이다).

재검증에서 `tests/unit/teams/test_response_review_team.py` 에 2건을 추가해 이
구멍을 닫았다 — 기존 `FakeLLM` fixture 패턴을 그대로 재사용:

```powershell
python -m pytest tests/unit/teams/test_response_review_team.py -v
```
```
tests/unit/teams/test_response_review_team.py::test_manifest_and_protocol PASSED
tests/unit/teams/test_response_review_team.py::test_normal_generation_review_returns_contract_result PASSED
tests/unit/teams/test_response_review_team.py::test_negative_sentiment_decides_empathetic_tone_before_generation PASSED
tests/unit/teams/test_response_review_team.py::test_missing_sentiment_defaults_to_professional_tone PASSED
tests/unit/teams/test_response_review_team.py::test_forbidden_word_retries_then_escalates PASSED
tests/unit/teams/test_response_review_team.py::test_fact_mismatch_retries_and_later_pass_is_recorded PASSED
tests/unit/teams/test_response_review_team.py::test_return_quantity_over_item_count_is_fact_mismatch PASSED
tests/unit/teams/test_response_review_team.py::test_pii_escalates_without_retry PASSED
tests/unit/teams/test_response_review_team.py::test_deterministic_review_runs_before_tone_llm PASSED
tests/unit/teams/test_response_review_team.py::test_tone_only_failure_is_warning_without_retry PASSED
tests/unit/teams/test_response_review_team.py::test_status_escalated_is_mapped_to_escalation_contract PASSED
tests/unit/teams/test_response_review_team.py::test_gen_then_rev_two_call_flow_actually_executes PASSED
tests/unit/teams/test_response_review_team.py::test_gen_then_rev_two_call_flow_records_rejection_as_warning PASSED
13 passed in 2.72s
```

새 테스트 2건은 GEN fixture 에서 `tone_ok` 를 빼서 REV 호출을 강제하고,
`llm.calls == ["response.generate", "response.review_tone"]` 로 호출 **순서와
개수**를 직접 단언한다. 두 번째 테스트는 REV 가 `tone_ok: False` 를 돌려줄 때
그 결과가 `warnings == ["tone_review_failed"]` 로 실제 반영되는지까지 확인한다
(호출만 되고 결과가 버려지면 검증이 아니므로).

### (b) REV 반려 시 재시도 상한 — 기존 커버리지로 이미 충분, 재확인만 함

- `test_response_review_team.py::test_forbidden_word_retries_then_escalates` —
  4회 재시도 후 `outcome == "escalated"`, `llm.calls.count("response.generate") == 4`.
- `test_response_review_team.py::test_return_quantity_over_item_count_is_fact_mismatch` —
  fact mismatch 4회 반복 후 escalate.
- `test_response_review.py::test_refund_amount_above_order_total_is_fact_mismatch`,
  `test_response_review.py::test_four_failed_reviews_escalate_with_retry_code` —
  `failure_code == "review_retries_exhausted"`, `len(result.decisions) == 4`.

`execute()` 의 `for retry in range(4):` 루프(111행)가 상한이며, 위 4개 테스트가
루프 상한·`review_history` 누적·`review_retries_exhausted` 코드를 모두 실측한다.
새로 추가할 것이 없어 손대지 않았다.

### (c) 개인정보 섞인 응답 차단 — 기존 커버리지로 이미 충분, 재확인만 함

- `test_response_review.py::test_pii_escalates_without_retry` (이메일),
  `test_response_review_team.py::test_pii_escalates_without_retry`(이메일),
  `test_response_review.py::test_verified_name_with_honorific_escalates_without_retry`
  (이름+존칭) — 전부 `outcome == "escalated"`, `failure_code == "pii_detected"`,
  `len(llm.calls) == 1`(재시도 없이 즉시 차단, LLM 호출 전 결정론 검사
  `_deterministic()` 85~87행에서 걸림)을 단언한다.
- `test_response_review.py::test_surname_without_name_context_does_not_escalate` —
  오탐 방지(성씨만으로는 PII 로 보지 않음)까지 반증 확인.

REV 자체 검증은 `response_review_policy.py::PII_PATTERNS`(이메일/전화/카드번호
정규식)와 `detect_person_name_pii()`(존칭 문맥의 검증된 성씨)로 구성되며, LLM 을
거치지 않는 결정론적 REV 단계라 재현성이 100% 다. 새로 추가할 것이 없어
손대지 않았다.

### 재검증 결론

| 세부 기준 | 재검증 전 | 재검증 후 |
|---|---|---|
| (a) GEN→REV 2호출 실제 실행 | **미검증** (전 테스트가 우회) | **통과** — 신규 2건 |
| (b) REV 반려 시 재시도 상한 | 통과 (기존 4건) | 통과 (변경 없음) |
| (c) PII 섞인 응답 REV 차단 | 통과 (기존 4건) | 통과 (변경 없음) |

전체 회귀: `python -m pytest -q -m "not live"` 재검증 전 **508 passed, 4
deselected, 1 xfailed** → 신규 테스트 2건 추가 후 **510 passed, 4 deselected,
1 xfailed** (실패 0, 회귀 0).

## 통과한 것

- **단위 테스트 6종** — 정상 응답 1회 통과, 금칙어 재시도, PII 즉시
  escalate(재시도 없음), 환불 상한 초과 fact_mismatch, 4회 실패 시
  `review_retries_exhausted`, 정책·톤 결정론 검증. 전부 v8 §8-B 의 설계
  (톤결정→GEN→결정론 REV→LLM 톤 REV, 최대 3~4회, PII 즉시 escalate)와
  일치.
- **기존 할루시네이션 방어 재사용** — `app/core/verification.py` 의
  `verify_proposal`/`Facts` 를 새로 안 만들고 그대로 재사용해 사실대조를
  한다. 검증된 메커니즘 위에 얹었다.
- **`TeamResult` 계약 무변경** — v8 이 요구한 매핑(`final_response_text`→
  `answer`, `retry_count`/`review_history`→`decisions[]`, 반려 사유→
  `warnings[]`, `escalation`→`outcome`/`next_action`)을 계약 스키마
  변경 없이 구현했다(`ConfigDict(extra='forbid')` 위반 없음).
- **잠재 결함 1건을 등록 전에 미리 잡았다** — `app/composition.py` 의
  Team 조립기가 `ResponseGenerationReviewTeam(llm=None)` 처럼 단일 인자
  생성자를 개수만 보고 판단해 `ReadToolbox` 를 `llm` 자리에 잘못 넣는
  결함을 발견·수정했다(`wiki/records/reports/debugs/2026-08-19_composition_단일인자_Team_llm_오배선.md`).
  등록 안 된 상태에서 발견해 실제로 터지기 전에 막았다.

## ★통과로 갱신된 이유 (2026-08-20)

| 항목 | 상태 |
|---|---|
| 단위 테스트(결정론 REV 4종 + 톤 검증) | **통과** |
| `TeamResult` 계약 무변경 매핑 | **통과** |
| ~~`config/project.yaml` 미등록~~ → **통과** | `teams:` 에 등록 완료
  (`implementation_ref: app.modules.customer_ops.response_review:ResponseGenerationReviewTeam`).
  `Controller._maybe_review()` 가 실행 직후 hook 으로 연결됐다 — 다른
  Team 이 만든 `TeamResult.answer` 를 `response_review.enabled` 설정이
  켜져 있을 때만 2차 검증하는 방식. **기본값은 꺼짐**(`enabled: false`) —
  이건 미완성이 아니라 의도된 설계다(안전한 기본값, 팀이 배포 시점에
  켜는 운영 결정). `registry.get()` 경유로 호출해 Core-Team import 금지
  원칙을 지켰다. 근거: `wiki/records/reports/2026-08-20_S-DOD29-COMPLETE_리포트.md`. |
| 실 LLM 호출 검증 | **통과** — `tests/live/test_response_review_live_smoke.py`,
  `1 passed in 10.13s`(2026-08-19 확인). |
| ~~golden/holdout 커버리지 없음~~ → **통과** | v8 §1031 배분(golden 12·
  holdout 4)대로 `eval/datasets/golden.jsonl`·`holdout.jsonl` 에 추가
  완료(`g-response-review-*`/`h-response-review-*`). 전체 golden 72·
  holdout 24, 중복·교집합 없음 확인. 근거: 동 리포트. |
| 배선 통합 테스트 | **통과** — `tests/integration/controller/test_response_review_wiring.py`
  2건(꺼짐 시 회귀 없음, 켜짐 시 검수 결과 반영). 전체 `python -m pytest
  -q -m "not live"` → `329 passed, 3 deselected, 0 failed`(Claude 실
  환경 재확인, 기준선 327 대비 +2). |

## 남은 것 (DoD 판정과 무관, 운영 결정 사안)

- `response_review.enabled` 를 실제로 언제 켤지는 팀의 운영 판단이다 —
  코드·테스트·데이터는 전부 준비됐다.
- 켰을 때 실제 Case 트래픽에서 review pass 의 지연시간·비용 영향은
  아직 측정 안 됨(이번 작업 범위 밖).
