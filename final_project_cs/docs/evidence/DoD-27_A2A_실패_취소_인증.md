# DoD-27 — A2A 실패·타임아웃·취소·인증

- v7 §27 항목 27 / 검증 방법: 더미 Remote Agent fixture 에서 각 결과가 `unknown`/`escalated` 또는 `cancelled` 로 기록되는지
- 실행: 2026-08-16
- 판정: 통과 (★한계는 아래 참조)

## 재현 명령

```powershell
python -m pytest tests/integration/a2a/test_remote_round_trip.py -q
python -m pytest tests/integration/controller/test_provider_timeout_unknown.py -q
```

## 실제 출력

```
tests/integration/a2a/test_remote_round_trip.py               10 passed
tests/integration/controller/test_provider_timeout_unknown.py  4 passed

실패:
  원격이 즉시 실패 → outcome=failed / next_action=escalate
                     failure_code=catalog_unavailable

타임아웃(우리 쪽 deadline):
  끝나지 않는 원격 + 지난 deadline
    → outcome=failed / failure_code=remote_deadline_exceeded

취소:
  POST /a2a/tasks/{id}/cancel   → status=cancelled
    → failure_code=cancelled_by_caller       ★remote_task_failed 아님
    → warnings=["원격 Task 가 취소됐다 — 실패와 구분해서 읽어야 한다"]
  이미 끝난 Task 취소 시도       → 409

인증:
  토큰 없음   → failure_code=remote_unauthorized
  토큰 틀림   → failure_code=remote_unauthorized
  Agent Card 는 인증 없이 200 (공개 정보)

outbox 경로 timeout → unknown (DoD-11):
  publisher TimeoutError → status='unknown', 자동 재실행 없음
```

## 항목별 상태

| v7 요구 | 결과 |
|---|---|
| **실패** → `escalated` | **통과** |
| **타임아웃** | **통과** — 우리 쪽 `deadline_at` 이 동작. outbox 쪽 `unknown` 은 DoD-11 |
| **취소** → `cancelled` 로 기록 | **통과** — 아래 참조 |
| **인증** | **통과** — 없음·틀림 둘 다 거부. Card 만 공개 |

## ★취소를 실패와 분리했다

전에는 executor 가 `{"failed", "error", "cancelled"}` 를 한 덩어리로 묶어
`remote_task_failed` 로 뭉갰다. **누가 멈췄는지가 사라진다** —
실패는 원격이 못 한 것이고, 취소는 우리가 그만둔 것이다.

★`outcome` 에 `"cancelled"` 를 **추가하지 않았다.** 계약 Literal 을 늘리면
전이표·리듀서·저장까지 파급된다. v7 이 요구한 것은 "취소로 **기록**되는가" 이므로
`outcome="escalated"` + `failure_code="cancelled_by_caller"` + 경고 문구로 남긴다.

## ★전에 이렇게 잘못 셀 뻔했다

최초 검토에서 `cancel` 검색이 38건 나왔다. 그러나 그것은
`resolved --cancelled_by_user--> cancelled` 즉 **고객이 Case 를 취소**하는 것이었고,
v7 이 요구한 **원격 Task 취소**와는 다른 사건이다.

**코드에 낱말이 있는 것과 그 경로가 밟히는 것은 다르다.**

## 한계

- ★**프로세스 경계를 넘지 않는다** (DoD-26 과 같은 한계).
  네트워크 단절·TCP 리셋·부분 응답은 재현되지 않았다
- 취소가 **원격의 실제 작업을 멈추는지**는 모른다. 상태가 `cancelled` 로 바뀌는 것만 봤다.
  실제 원격이라면 진행 중 작업의 롤백 여부가 별도 문제다
- 인증은 bearer 토큰 한 종류다. 만료·회전·mTLS 는 다루지 않았다

## ★2026-08-24 갱신 — "타임아웃 통과" 가 루프 사이 체크뿐이었던 갭 메움

위 §48 "우리 쪽 `deadline_at` 이 동작" 은 실제로는 **루프 반복 사이에서만**
확인하고 있었다 — 원격 `submit()`/`poll()` 호출 **한 번**이 응답 없이
오래 걸리면(hung) 그 호출 자체는 안 끊겨서 선언된 데드라인을 훨씬 넘길 수
있는 갭이 sample 대조로 발견됐다. `a2a_executor.py`가 각 원격 호출을
`asyncio.wait_for(call, timeout=deadline_at - now())`로 감싸도록 고쳤고,
포기할 때 원격에 best-effort 취소도 시도한다. `submit()`이 10초 hang 하는
mock 에 30ms 데드라인을 줘도 0.5초 안에 `remote_deadline_exceeded`로
끝나는지, `poll()`이 hang할 때도 같은지 + 실제로 `cancel()`이 호출되는지
재현 테스트로 확인했다. 상세: `docs/reports/2026-08-24_S-BASEMENT-06-CONTROLLER-RELIABILITY_리포트.md`
