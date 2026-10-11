# DoD-29 — Response Generation & Review Team

- v8 §27 항목 29 / 검증 방법: contract test(Protocol·Core 격리) + unit test(GEN→REV 시나리오별 `TeamResult`)
- 실행: 2026-08-18
- 판정: 통과

## 재현 명령

```powershell
python -m pytest tests/contract -q
python -m pytest tests/unit/teams -q
```

## 실제 출력

```text
43 passed in 1.25s
10 passed in 0.12s
```

## 판정 근거

| 요구 (v8 §8-B) | 결과 |
|---|---|
| `TeamModule` Protocol 구현, `TeamResult` 계약 불변 | **통과** — `isinstance(team, TeamModule)`, `extra='forbid'` 위반 없음 |
| GEN 초안 → 결정론 REV → LLM 톤 REV → 완료 | **통과** — `test_normal_generation_review_returns_contract_result` |
| 금칙어 위반 → 최대 3회 재시도 후 `escalated` | **통과** — `test_forbidden_word_retries_then_escalates` (generate 호출 4회 관측) |
| `refund_amount`/`policy_ref` 불일치 → 재시도 후 통과 시 기록 | **통과** — `test_fact_mismatch_retries_and_later_pass_is_recorded`, `app/core/verification.py` 재사용 |
| PII 검출 → 재시도 없이 즉시 `escalated` | **통과** — `test_pii_escalates_without_retry` (retry_count 0, LLM 호출 1회) |
| 결정론 검사가 LLM(톤) 검사보다 먼저 | **통과** — `test_deterministic_review_runs_before_tone_llm` (`response.review_tone` 미호출 관측) |
| 톤 실패는 재시도하지 않고 `warnings[]`만 | **통과** — `test_tone_only_failure_is_warning_without_retry` |
| `accepted_case_types=[]` (Controller 자동 라우팅 대상 아님) | **통과** — `test_manifest_and_protocol` |
| 톤 결정(규칙) → GEN 초안 → REV 검증 → 완료 (v8 §8-B 흐름 1단계) | **통과** — `decide_tone()`(`response_review_policy.py`)이 `case["sentiment"]`(`controller.py`가 채우는 `current_state["sentiment"]`)로 규칙 결정, GEN·톤 REV 양쪽에 같은 값 전달. `test_negative_sentiment_decides_empathetic_tone_before_generation`, `test_missing_sentiment_defaults_to_professional_tone` |

## ★검수 중 발견해 고친 결함 — 고객 원문에 REV 규칙을 잘못 적용

최초 구현은 `execute()` 시작부에서 `task.input_text`(=`case["subject"]`, 즉
`controller.py:87` 이 그대로 넘기는 **고객의 원문 메시지**, `cases.py:86`의
`subject=request.message`)를 금칙어·PII 정규식으로 미리 스캔해 위반이 있으면
GEN 조차 시도하지 않고 즉시 `escalated` 로 보냈다(`preflight`).

문제: REV 의 4항목(과잉약속·근거인용·PII·톤)은 **이 Team 이 생성한 응답**을
검증하는 규칙이지 고객이 쓴 원문을 검열하는 규칙이 아니다(`wiki/records/handoff/04`
§3 "흐름": GEN 초안 → 결정론 REV → LLM 톤 REV). 그런데 고객 문의에는 본인
확인을 위해 전화번호·이메일을 적는 일이 흔하고, "절대 안 돼요"·"항상 이래요"
같은 표현도 일상적이다 — preflight 는 이런 정상적인 고객 메시지를 **응답 생성
시도조차 없이** escalate 시켰다. 이 Team 의 존재 이유(응답 초안을 만들고
검토하는 것)를 무력화하는 결함이었다.

수정: preflight 블록을 제거했다. 결정론 REV는 이제 `_generate()`가 만든
**응답 초안**에만 적용된다 — "결정론 검사가 LLM 검사보다 먼저"라는 요구는
톤 LLM 호출 전에 응답 초안의 결정론 검사가 먼저 도는 것으로 이미 성립한다
(`test_deterministic_review_runs_before_tone_llm` 이 이 순서를 직접 관측한다).
이 결함을 유발했던 테스트(`test_deterministic_input_rejection_happens_before_llm`)도
같은 이름의 테스트로 교체해 올바른 대상(생성된 초안)을 검사하도록 했다.

## ★검수 중 발견해 고친 결함 — 톤 결정(규칙) 단계 자체가 없었다

v8 §8-B 는 내부 흐름을 "**톤 결정(규칙)** → GEN 초안 → REV 검증 → 완료"로
4단계로 명시한다. 그런데 최초 구현은 1단계가 통째로 없었다 —
`response_review_policy.py` 에 `TONE_PROFILES`(`professional`/`empathetic`)
선언은 있었지만 그중 어느 것을 쓸지 정하는 규칙이 없었고, `response_review.py`
는 톤 REV LLM 호출에 `"professional"` 을 하드코딩해 항상 같은 프로파일을
썼다. GEN 호출에는 톤 정보 자체가 전달되지 않았다.

수정: `response_review_policy.py` 에 `decide_tone(sentiment)` 순수 함수를
추가했다 — 이미 인라인 분류가 채워 둔 `case["sentiment"]`(`controller.py`가
`current_state["sentiment"]`로 넘긴다)만 보고, `negative` 면 `empathetic`,
그 외(분류 실패로 없는 경우 포함)는 기본값 `professional`을 규칙으로
고른다. `execute()` 시작부에서 한 번 결정해 GEN 프롬프트 컨텍스트와 톤 REV
호출 양쪽에 같은 값을 전달하고, `decisions[]`에도 남긴다.

## 한계

- **실 LLM 미검증** — `FakeLLM` 만으로 GEN/톤 REV 시나리오를 검증했다. 이
  환경의 Codex 샌드박스는 외부 네트워크가 막혀 있어(`wiki/records/handoff/05` §2-1)
  실제 OpenAI 호출 경로는 이 리포트로 증명하지 않는다.
- **Controller 자동 배선 범위 밖** — `accepted_case_types=[]`로 두어 이
  Team 이 모든 Case 출력에 자동으로 물리지 않는다(v8 §8-B가 말하는 "모든
  Case 검증"의 배선은 별도 결정 필요, 의도적으로 하지 않음).
- **`config/project.yaml` 미등록** — registry 에 등록 가능한 코드까지만
  만들었고 `teams` 배열에 `active: true` 로 실제로 켜는 것은 사용자 판단
  몫이다.
