# DoD-24 — ActionProposal 근거 대조·실행 차단

- v7 §27 항목 24 / §9-E / 검증 방법: 지어낸 `order_id`·불일치 금액 fixture 에서 실행 차단·`escalated`·감사 로그
- 실행: 2026-08-16
- 판정: 통과 (★한계는 §한계 참조)

## 재현 명령

```powershell
python -m pytest tests/unit/core/test_proposal_verification.py -q          # 13 passed
python -m pytest tests/integration/controller/test_proposal_guard_blocks.py -q  # 5 passed
python -m pytest tests -q                                                  # 190 passed
```

## 실제 출력

```
tests/unit/core/test_proposal_verification.py ............. 13 passed
tests/integration/controller/test_proposal_guard_blocks.py ..... 5 passed
tests/integration/api/test_recheck_before_execution.py .... 4 passed
전체: 196 passed, 0 skipped, 0 failed

차단된 제안의 감사 기록 (case_events 실측):
  event_type = guardrail_escalated
  guardrail  = action_proposal_verification_failed
  observed   = ['amount: 실제 결제액보다 큰 금액을 제안했다']
  mismatches = [{'field': 'amount', 'reason': '실제 결제액보다 큰 금액을 제안했다',
                 'expected_digest': '40510175845988f1',
                 'actual_digest':   '5973b7b8afbd2cbe'}]
  → action_requests 행 수 = 0

승인 직전 재검증 차단 (HTTP 실측):
  POST /v1/cases/{id}/actions/{id}/approve  →  409
  error.code = verification_failed
  action_approvals 행 수 = 0
```

★`expected_digest`·`actual_digest` 만 남고 **금액 원문은 없다**.

## 무엇이 없었나

`app/application/controller.py` 가 `proposal.arguments` 를 **대조 없이** 저장했다:

```python
self.repository.create_action_request(
    conn, ..., arguments=proposal.arguments, ...)   # ← 그대로
```

기존 `contracts.py:283` 의 검사는 **내부 정합성**뿐이었다 —
"제안이 자기 결과 안의 evidence 를 가리키는가". **현실과 맞는지는 보지 않았다.**

★**실제 결제액이 30,000원인데 "50,000원 환불" 을 제안하면 통과했다.**
v7 §9-E 가 예시로 든 바로 그 상황이다.

## 만든 것

| 파일 | 역할 |
|---|---|
| `app/core/verification.py` | **순수** 대조 함수. DB 를 모른다 → Core 가 인프라를 import 하지 않고 테스트가 DB 없이 돈다 |
| `app/application/proposal_guard.py` | tenant/customer 범위로 사실 **재조회** + 대조 실행 |
| `Controller._reject_unverified()` | 실행 경로 진입 전 차단 |

## 판정 근거

| 요구 (v7 §9-E) | 결과 |
|---|---|
| `payment_id`·`subscription_id`·`entitlement_id` 실재·소유권 | **통과** — tenant/customer 조건으로 조회된 것만 사실 |
| `amount` 가 실제 결제액을 넘지 않음 | **통과** — 3만원 결제에 5만원 제안 거부 |
| `quantity`·`order_id` 등 **대조 불가 필드** | **통과** — 이 MVP 에 `orders` 테이블이 없다. ★**확인 못 하면 거부**한다 |
| `evidence_ids` 가 ContextPack 에 실재 | **통과** |
| 거부 시 `escalated` | **통과** — `guardrail_escalated` / `action_proposal_verification_failed` |
| 감사 로그에 실패 필드 + 기대·실제 **hash** | **통과** — 원문 금액·식별자 미기록 (설계 원칙 §1) |
| 조용히 무시하지 않음 | **통과** |
| ★**과잉 차단 없음** | **통과** — 정상 제안·부분 환불·단위 구분 통과 (13건 중 4건이 "막으면 안 되는 것") |

## ★대조는 위조할 수 없는 쪽으로 한다

처음엔 `result.evidence`(Team 이 돌려준 것)로 근거를 셌다. **순환이다** —
Team 이 근거와 제안을 **둘 다** 지어낼 수 있다.
`task.context`(Controller 가 만든 ContextPack)로 바꿨다.

★그리고 폴백을 지웠다. `pack_evidence or result.evidence` 로 짰더니
**ContextPack 에 근거가 하나도 없을 때 Team 이 만든 근거로 넘어가 방어가 통째로 풀렸다.**
테스트가 그것을 잡았다. 근거 없는 Context 면 근거를 든 제안은 전부 거부가 맞다.

## ★대조가 본 흐름을 죽이지 않게 한다

`load_facts()` 를 savepoint 없이 짰다가 컬럼명을 하나 틀렸고
(`entitlements` 는 `feature/state` 가 아니라 `plan/source` 였다),
그 한 번의 실패가 트랜잭션을 aborted 로 만들어 **뒤따르는 전이까지 전부 무너졌다**
(`InFailedSqlTransaction`, 2건 실패). `conn.transaction()` 안으로 넣어 격리했다.

**대조는 거들 뿐이지 본 흐름을 망가뜨리면 안 된다.**

## ★실행 직전 재검증 (2회 중 두 번째) — 추가함

`recheck_before_execution()` 을 `POST /v1/cases/…/approve` 에 넣었다.
`tests/integration/api/test_recheck_before_execution.py` **4 passed**.

| 검사 | 결과 |
|---|---|
| 사실이 그대로면 승인 통과 | **통과** — 과잉 차단 없음 |
| ★제안 뒤 결제액이 줄면 승인 **차단** | **통과** — 409 `verification_failed`, `action_approvals` 0행 |
| 거부 사유가 기록되고 원문 값은 없음 | **통과** — `recheck_before_execution_failed` |
| 거절(rejected)은 재검증을 돌지 않음 | **통과** — 아무것도 실행하지 않으므로 |

30,000원 환불 제안을 저장한 **뒤에** 결제액을 10,000원으로 낮추고 승인하면 막힌다.
한 번만 검사했다면 3배를 환불했을 것이다.

### ★이 과정에서 세 가지를 상태기계와 트랜잭션이 잡아 줬다

1. **`waiting_approval --guardrail_escalated-->` 전이가 없었다.**
   재검증 코드를 먼저 쓰고 전이표를 안 열어 본 탓이다. **기계가 설계 구멍을 먼저 잡았다.**
   v7 §9-E 가 "escalated 로 보낸다" 고 했으므로 전이를 **의도적으로 추가**했다.
2. ★**거부 기록이 예외와 함께 롤백돼 사라졌다.** 승인 트랜잭션 안에서 escalated 를 쓰고
   409 를 던졌더니 둘 다 사라졌다 — "조용히 무시하지 않는다" 가 그대로 깨졌다.
   재검증을 트랜잭션 **밖**으로 옮기고 거부 기록만 따로 커밋한다.
3. **존재 확인(404)보다 재검증이 앞서 있었다.** 없는 action 에 재검증이 돌아
   `routing` 상태 Case 에 escalated 를 쓰려다 상태기계에 걸렸다. 순서를 바로잡았다.

## 한계
- **`quantity` 대조 대상이 없다.** line item 테이블이 없어 지금은 "확인 불가 → 거부" 로만 처리
- `action_type` ↔ Registry scope·approval matrix 대조는 기존 Registry 검사에 의존한다.
  이 모듈이 따로 재확인하지는 않는다
- 실제 LLM 이 만든 제안으로 재지 않았다. **fixture 로만 확인했다** — 방어 지표(§9-E)는 P4

## ★2026-08-24 갱신 — 비정상 금액 값이 "거부"가 아니라 "500 크래시"였던 결함 수정

sample 대조에서, `verification.py`의 `_to_decimal()`(정확히는 동등 함수)가
`Decimal("NaN")`/`Decimal("Infinity")`/`Decimal("-Infinity")`를
`.is_finite()`로 걸러내지 않아, 비정상 금액 값이 파싱 단계는 통과했다가
이후 비교 연산(`>`, `int()` 등)에서 `InvalidOperation`/`OverflowError`로
**500 에러**를 내던 결함을 발견·수정했다. 이 파일은 위 표의 근거 그대로
할루시네이션 방어의 핵심이다 — "거부해야 할 제안"이 "서버 에러"가 되면
`escalated`로도 못 가고 감사 로그도 안 남는다, `CLAUDE.md` §0.1 위반이다.
NaN/Infinity/-Infinity 세 값 모두 크래시 대신 안전한 검증 실패로
처리되는지 재현 테스트로 확인했고, 기존 정상 금액 비교 테스트는
회귀 없이 통과했다. 상세: `docs/reports/2026-08-24_S-BASEMENT-02-VERIFICATION-CRASH_리포트.md`
