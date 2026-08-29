# DoD-11 — action proposal · approval · idempotency · unknown 이 동작한다

- v5 §20 항목 11 / 검증 방법: 동일 요청 반복 test
- 최초 판정: 2026-08-12 **부분 통과** (승인·unknown 미검증)
- 재측정: 2026-08-14 · 실측 원문 `docs/evidence/_raw/DoD-11_v3.md`
- 판정: 통과 (★단, 아래 "action 실행 경로는 존재하지 않는다" 를 반드시 함께 읽을 것)

## 재현 명령

```powershell
python -m pytest tests/integration/api tests/integration/controller -q
python  # 동일 생성요청 10회 + approve + Controller 재실행 후 DB 조회
```

## 실제 출력

```
33 passed, 1 warning in 12.21s
DOD11_same_request_statuses = [201] × 10
DOD11_action_requests_count = 2
DOD11_before_approve = ('waiting_approval', 4)
상태·버전 순서 = waiting_approval/4 → resuming/5 → resolved/7
event aggregate_version = 1 … 7
git grep: worker 의 status='unknown' 업데이트 + DB enum 의 unknown 값 존재
```

## 통과한 것

| 요구 | 결과 |
|---|---|
| ★동일 요청 10회 → side effect 1회 | **통과** — `test_same_create_request_ten_times_has_one_action_request` 가 `action_requests` **1행**을 단언하며 통과 |
| ★**승인 종단** | **통과** — `waiting_approval(4) → resuming(5) → resolved(7)` 관측. 최초 판정 때 미검증이던 부분이다 |
| append-only 연속성 | **통과** — `aggregate_version` 1~7 연속 |
| `unknown` 상태 경로 존재 | 코드·DB enum 확인 |

★위 실측의 `action_requests_count = 2` 는 **회귀가 아니다.**
그 측정은 "10회 생성" 과 "승인 후 Controller 재실행" **두 시나리오를 합쳐서** 돌렸다.
10회 생성만 보는 전용 테스트는 **1행**으로 통과한다.

## ★새로 발견한 계약 이탈 — idempotency_key 산식

`app/modules/customer_ops/billing.py`:
```python
idempotency_key = uuid5(NAMESPACE_URL, str(task.task_id) + ":refund").hex
```

**v5 §10-1 이 정한 산식은 다르다:**
```
idempotency_key = sha256(tenant_id + request_id + action_type + business_subject)
```

★차이가 실제로 드러난다. 키가 **`task_id`** 에 걸려 있으면 run 이 바뀔 때마다 키가 달라진다.
그래서 승인 후 Controller 를 재실행하자 **같은 업무 행위(환불 제안)에 새 행이 하나 더 생겼다**
(위 측정의 2행 중 하나). v5 산식이었다면 `tenant_id + request_id + action_type + business_subject`
가 같으므로 **같은 키가 되어 `UNIQUE(tenant_id, idempotency_key)` 가 막았을 것이다.**

즉 **생성 경로의 중복은 막지만, run 을 가로지르는 중복은 막지 못한다.**

★계약 문서에도 이렇게 적어 두었다(`docs/handoff/01_계약_Pydantic.md` §5):
> `idempotency_key` 는 Team 이 제안한 값이 아니라 **서버가 재계산한 값이 최종**이다.

서버 재계산이 실제로 일어나는지 확인되지 않았다.

## 미통과 항목

| 항목 | 상태 |
|---|---|
| 생성 경로 idempotency (10회 → 1행) | 통과 |
| 승인 종단 (`waiting_approval → resolved`) | 통과 |
| ★**run 을 가로지르는 idempotency** | **통과** — v5 §10-1 산식 적용 (커밋 `7a6cf18`) |
| ★**provider timeout → `unknown` 종단 동작** | **통과** (2026-08-14, 아래) |
| `unknown` 자동 재실행 금지 | **통과** (2026-08-14, 아래) |
| ★**action 실행 경로 자체가 없다** | **미해당** — 아래 |

## ★provider timeout → `unknown` 재측정 (2026-08-14)

`tests/integration/controller/test_provider_timeout_unknown.py` **4건 통과.**
`git grep` 이 아니라 **실제로 timeout 을 주입**해서 관측했다.

| 검사 | 결과 |
|---|---|
| timeout 이 나면 `status='unknown'` 이 된다 | **통과** — `delivered` 아님 |
| ★timeout 을 **실패로 단정하지 않는다** | **통과** — `dead_letter`·`pending` 아님. 돈이 이미 나갔을 수 있다 |
| ★`unknown` 은 자동 재실행되지 않는다 | **통과** — 다시 돌려도 publisher 호출 0, `attempts` 그대로 1 |
| ★정상 worker 를 붙여도 그 행은 배달되지 않는다 | **통과** — `process_once()` 가 `False`, `delivered == []` |
| timeout 아닌 실패는 재시도 대상으로 **구분**된다 | **통과** — `ValueError` → `pending` |

★마지막 줄이 중요하다. **거절당한 것(안 나갔음)** 과 **응답이 없는 것(나갔는지 모름)** 은 다르다.
둘을 같게 처리하면 이미 나간 돈을 또 보내거나, 안 나간 것을 방치한다.

## ★그런데 이것은 outbox 경로다 — action 실행 경로는 존재하지 않는다

위 실측은 **Message Broker(outbox) 발행 경로**를 잰 것이다.
`action_requests` 를 실제 provider 로 실행하는 코드는 **이 시스템에 없다.**
`app/` 전체에서 `action_requests.status` 를 `executing`/`succeeded`/`failed`/`unknown`
으로 바꾸는 곳은 한 군데도 없다. enum 에만 값이 있다.

★**이것은 결함이 아니라 설계다.** `CLAUDE.md` §0.2 —
> **Team 은 side effect 를 실행하지 않는다.** `ActionProposal` 만 반환한다.

승인 이후 실제 결제사 호출은 MVP 범위 밖이다. 다만 **그 사실을 명시해 둔다** —
"provider timeout 이 `unknown` 으로 남는다" 를 **결제 실행에 대해 증명한 것으로 읽으면 안 된다.**
결제 실행이 붙는 시점에 같은 검사를 그 경로에 다시 해야 한다.
`test_action_status_enum_can_hold_unknown` 이 이 사실을 테스트로 고정해 두었다.

## 남은 한계

- 실제 결제 provider 어댑터가 없으므로 **진짜 결제 timeout 은 겪어 보지 않았다**
- ~~`unknown` 행을 사람이 조회·결론내는 운영 절차(화면·런북)가 없다~~ →
  ★2026-08-24 메움, 아래 참조

## ★2026-08-24 갱신 — idempotency 필드 경계 충돌 수정 + MCP 멱등성 + unknown 해결 화면

1. **idempotency 필드 경계 충돌**. `app/core/idempotency.py`가 여러
   필드를 단순히 이어붙여(`f"{a}{b}{c}{d}"`) 해시했다 — `("ab","c")`와
   `("a","bc")`가 같은 해시가 될 수 있는 결함이었다(이 문서 §"idempotency_key
   산식"이 지적한 v5 §10-1 산식 자체의 취약점). 각 필드를 먼저 개별
   해시한 뒤 결합하도록 고쳤다.
   `test_idempotency_key_preserves_field_boundaries`로 재현·확인.
   상세: `docs/reports/2026-08-24_S-BASEMENT-03-TENANT-DEDUPE_리포트.md`
2. **MCP `open_support_case` 멱등성**. MCP 요청 ID 기반으로 REST와 동일한
   원리의 dedupe key를 계산해 `action_requests`를 먼저 조회, 기존 행이
   있으면 기존 Case를 반환한다. 동일 요청 10회 → Case 1개·action_requests
   1행을 `test_same_mcp_open_request_ten_times_has_one_case_and_action_request`로
   확인. 상세: `docs/reports/2026-08-24_S-BASEMENT-01-AUTH-CONTRACT_리포트.md`
3. **`unknown` 사람 해결 화면·런북이 없던 갭을 메웠다.** `POST
   /v1/outbox/{id}/resolve`(기록만, 자동 재처리 안 함)와 `/ops/outbox`
   UI가 새로 생겼고, `worker.py`가 stale `processing` 행을 `unknown`으로
   회수한다(여전히 자동 재실행은 안 한다). 상세:
   `docs/reports/2026-08-24_S-BASEMENT-05-OUTBOX-RESOLUTION_리포트.md`,
   `docs/manuals/운영_unknown상태_대응절차.md`
