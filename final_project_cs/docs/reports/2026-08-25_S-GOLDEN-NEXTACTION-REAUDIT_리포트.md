# S-GOLDEN-NEXTACTION-REAUDIT — golden.jsonl `call_tool` 15건 재라벨링

★Codex 세션은 판단(15건 각각의 올바른 `expected_next_action`)까지는
정확히 끝냈지만, 샌드박스 계정(`CodexSandboxOffline`)이
`eval/datasets/golden.jsonl`과 그 디렉터리에 쓰기 권한이 없어 실제
파일 수정을 못 했다. Claude가 Codex의 판단을 코드와 대조해 확인한
뒤 직접 적용했다.

## 배경

`app/core/contracts.py`의 `NextAction.CALL_TOOL`은 enum에 존재하지만
실제로는 도달 불가능한 값이다 — 모든 Team이 tool을 `execute()`
내부에서 동기적으로 호출한 뒤 `TeamResult`를 반환하므로,
`CALL_TOOL`이 최종 `next_action`으로 나올 경로가 없다. 어떤 Team
모듈도 이 값을 반환하지 않는다(직접 grep으로 확인).

`eval/datasets/golden.jsonl` 72건 중 15건이
`expected_next_action: "call_tool"`이었다 — 2026-08-24 Proposed arm
재측정에서 judge 사유의 33%가 "next action이 기대와 안 맞는다"였던
것의 주요 원인 중 하나로 지목됐다.

## 판단 근거 (Codex가 각 Team 코드를 직접 읽고 도출, Claude가 대조 확인)

| case_id | 이전 값 | 새 값 | 근거 |
|---|---|---|---|
| g-order-01 | call_tool | respond | `order.verify` — 조회 성공 시 즉시 응답 |
| g-order-04 | call_tool | wait_for_approval | `order.modify` — 변경은 ActionProposal + 승인 필요 |
| g-order-10 | call_tool | respond | `order.verify` — 상태 확인 후 즉시 응답 |
| g-order-12 | call_tool | respond | `order.verify` — 상태 확인 후 즉시 응답 |
| g-shipping-05 | call_tool | respond | `fulfillment.track` — 이행 상태 조회 후 즉시 응답 |
| g-shipping-07 | call_tool | respond | `fulfillment.track` — 이행 상태 조회 후 즉시 응답 |
| g-shipping-10 | call_tool | wait_for_approval | `shipment.exception` — 재배송 등 조치는 승인 필요 |
| g-shipping-14 | call_tool | escalate | `shipment.exception` — 지역명 미확인으로 즉시 판정 불가 |
| g-return-06 | call_tool | wait_for_approval | `refund.calculate` — 계산 결과는 항상 승인 대기로 귀결 |
| g-return-10 | call_tool | wait_for_approval | `return.request` — 반품 요청은 항상 승인 대기 |
| g-return-11 | call_tool | wait_for_approval | `return.request` — 동일 |
| g-exchange-03 | call_tool | wait_for_approval | `return.request` — 동일 |
| g-exchange-06 | call_tool | wait_for_approval | `return.request` — 동일 |
| g-exchange-09 | call_tool | wait_for_approval | `refund.calculate` — 동일 |
| g-exchange-15 | call_tool | respond | `return.check_eligibility` — 근거 충분 시 즉시 응답 |

`return.request`/`refund.calculate`는 `app/modules/customer_ops/return_refund.py`의
실제 코드 경로상 항상 `ActionProposal` + `WAIT_FOR_APPROVAL`로
끝난다(승인 없이는 side effect가 없다는 설계 원칙과 일치) — 이 점을
Claude가 코드를 직접 읽어 재확인했다.

## 검증

```
python -c "... call_tool 개수 확인 ..."   → 0건 (15건 전부 수정 확인)
총 라인 수: 72 (변경 없음)
python -m eval.verify_expected_capability  → allowed_value_check=PASS
holdout.jsonl SHA-256: 3818f612c80abcf7e8b6858a3e2ffdafeda02e2dbf350a84fed82400eb72e692
  (Codex 리포트의 원본 SHA와 동일 — 미변경 확인)
python -m pytest -q -m "not live"  → 404 passed, 0 failed (회귀 없음)
```

## ★재측정 결과 (`eval/reports/2026-08-25_reeval_Proposed_v2.jsonl`, 216행)

라벨링 수정 전/후 비교:

| | 수정 전 | 수정 후 |
|---|---|---|
| team_result outcome=completed | 166/216 (77%) | **214/216 (99%)** |
| judge pass (success) | 21/216 (9.7%) | **32/216 (14.8%)** |
| Proposed−A score 평균차 | −2.09 [−2.84,−1.37] | **+1.02 [0.58, 1.47]** |
| Proposed vs A McNemar | b=0,c=21, p≈9.5e-07 | b=0,c=32, p≈4.3e-08 |
| Proposed−B score 평균차 | −7.70 [−8.44,−7.00] | −4.59 [−4.98,−4.20] (여전히 B 우세) |

수정 전엔 raw score(A에 뒤짐)와 binary pass(A를 이김)의 방향이
엇갈렸는데, 수정 후엔 **둘 다 Proposed가 A를 이기는 것으로 일치**한다
— `call_tool` 오라벨이 실제로 이 불일치의 원인이었음을 확인.

exchange 케이스의 `degraded_context` escalation도 이번 재실행에선
거의 재현되지 않았다(escalated 2/216) — 2026-08-24에 봤던 49건은
그날 일시적 인프라 문제였다는 진단이 맞았음을 재확인.

Proposed가 B에 여전히 크게 뒤지는 것은 이 계약 범위 밖의 별도
원인이다(후속 과제).

## ★2026-08-28 갱신 — 진짜 근본 원인 발견·수정: capability 오라우팅 68%

이 재라벨링 이후에도 B와의 격차가 안 좁혀져서 더 파봤다.
`eval/runners/common.py::_team_context()`가 `TeamRegistry.capability_for(registered, intent)`로
capability를 **재계산**하는데, 이 함수는 `intent`가 Team의 어떤
capability 이름과도 prefix-match 안 되면(예: intent="exchange"인데
`return_refund` 팀의 capability가 전부 `return.`/`refund.` 접두어)
조용히 `manifest.capabilities[0]`(항상 첫 번째 값)로 폴백한다.

실측: golden.jsonl의 `expected_capability`가 있는 60건 중 **41건(68%)**이
이 폴백 때문에 라벨과 다른 capability로 라우팅되고 있었다(예:
`return.request`를 기대하는 case가 전부 `return.check_eligibility`로
감). `eval/runners/common.py`에 `case.get("expected_capability")`가
있고 해당 Team의 manifest에 실재하면 그걸 우선 쓰고, 없을 때만
`capability_for()` 휴리스틱으로 폴백하도록 고쳤다(Claude가 직접 수정,
소규모라 계약 없이 진행). 수정 후 불일치 0/60 확인.

### 최종 재측정 (`eval/reports/2026-08-28_reeval_Proposed_v3.jsonl`, 216행)

| | v1(픽스처만) | v2(+next_action) | v3(+capability routing) |
|---|---|---|---|
| judge pass | 21/216(9.7%) | 32/216(14.8%) | **60/216(27.8%)** |
| Proposed−A score | −2.09 | +1.02 | **+1.01 [0.56,1.47]** |
| Proposed vs A McNemar | 21승0패 | 32승0패 | **60승0패, p≈2.6e-14** |
| Proposed−B score | −7.70 | −4.59 | −4.60 [−4.99,−4.22] |
| Proposed vs B McNemar | 194승2패 | 183승2패 | 154승1패(B 우세, 격차는 줄었지만 여전히 큼) |

structural 오염 원인(DB 픽스처 부재·next_action 오라벨·capability
오라우팅) 세 가지를 전부 고친 뒤에도 B가 Proposed를 크게 이긴다 —
이건 이제 측정 아티팩트가 아니라 **실제 시스템 품질 차이로 봐야
한다.** Team 아키텍처(Proposed)가 단순 규칙 기반(B)보다 이 golden
셋에서 실제로 못한다는 뜻일 수 있다 — 왜 그런지는 이 리포트 범위
밖의 별도 조사가 필요하다(예: judge rubric이 Team 스타일 답변에
불리하게 짜여 있는지, 아니면 Team이 실제로 더 자주 완결된 답을
못 내는지).
