# 구현 지시 — VOC & Store Manager Team 신설 (1단계: 추가만, 기존 팀 안 건드림)

## 0. 배경

`program/plan/A-COP_구현계획서_v8.md` §8-B/§16: VOC & Store Manager 는
**CS Pack 10주 착수 확정 Team**이다. 지금 `feedback.py`/`feedback_job.py`
는 분류기·일일배치일 뿐 Registry 에 등록된 `TeamModule` 이 아니다. v8
원문: "VOC 가 집계·임계값·알림·위임을 판단하기 때문"에 Team 이어야 한다.
v8 906행: "반복 불만은 VOC & Store Manager Team 이 Case event 와 일일
집계를 사용해 alert 와 위임 제안을 만든다."

이번 1단계는 **새 Team 을 추가만 한다.** `order_shipping`/`return_exchange`
는 이번 계약에서 절대 건드리지 않는다(별도 2단계 계약으로 진행).

## 1. 소유 범위

```
쓰기 대상:
  app/modules/customer_ops/voc_store_manager.py   (신규)
  app/modules/customer_ops/__init__.py            (export 추가만, 기존 줄 삭제 금지)
  config/project.yaml                             (teams 목록에 추가만, 기존 두 줄 삭제 금지)
  tests/unit/teams/test_voc_store_manager.py       (신규)

★금지: `order_shipping.py`·`return_exchange.py`·`verification_policy.py`·
  `app/core/**`·`app/application/**`·`app/presentation/**`·
  `app/tools/read_tools.py`·`prompts/**` — 전부 건드리지 않는다.
```

## 2. 설계 (확정 — 재량 없음)

```python
class VocStoreManagerTeam:
    manifest = TeamManifest(
        team_id="voc_store_manager", display_name="VOC & Store Manager Team",
        contract_name="a_cop.team_task", supported_contract_versions=["1.0"],
        capabilities=["voc.aggregate", "voc.escalate"],
        accepted_case_types=["other"],
        required_context=["case_state", "policy", "db_facts", "history"],
        allowed_tools=["read.policy"],
        knowledge_scope=["order", "shipping", "return", "exchange"],
        max_steps=6, active=True, implementation_revision="2026-08-19",
    )
```

★`accepted_case_types=["other"]` 이유: `feedback.py::INTENTS` 는
`order/shipping/return/exchange/other` 5종뿐이고, `other` 가 "특정
주문·배송·반품 건과 안 엮인 일반 피드백·불만"에 가장 가깝다. `order` 등
나머지 4종을 이 Team 이 대신 받지 않는다 — 그건 이 Team 의 역할이
아니다(도메인이 다르다). LLM 이 만들지 않은, 이미 있는 값만 쓴다.

### `execute()` 로직

1. `task.context.degraded` 면 기존 두 Team 과 동일하게
   `outcome="escalated", failure_code="degraded_context"`.
2. `read.policy` 를 불러 정책 근거를 확보한다(다른 두 Team 과 동일 패턴).
   정책이 안 나오면 `failure_code="policy_not_found"` 로 escalate(동일 패턴).
3. **반복 불만 판정** — `task.context.similar_cases`(`ContextPack` 의
   기존 필드, `app/core/contracts.py:140`, Context Broker 가 이미
   채워 준다 — 새 조회 안 만든다)의 길이가 **2 이상**이면 "이미 이
   고객에게서 비슷한 Case 가 2건 이상 더 있다"로 판단해 위임 제안을
   만든다:
   ```python
   proposal = ActionProposal(
       action_type="voc.escalate",
       arguments={},   # ★검증 대상 필드 없음 — 금액·재고 등 대조할 게 없다
       idempotency_key=idempotency_key(tenant_id=task.context.tenant_id,
           request_id=str(task.context.current_state.get("request_id") or task.case_id),
           action_type="voc.escalate", business_subject=str(task.case_id)),
       approval_required=True, risk_level="low",
       rationale_evidence_ids=[e.evidence_id for e in evidence],
   )
   return TeamResult(..., outcome="waiting", confidence=0.8, evidence=evidence,
                      next_action=NextAction.WAIT_FOR_APPROVAL, wait_reason="human_approval",
                      action_proposals=[proposal],
                      decisions=[{"classification": "repeated_complaint_escalation",
                                  "similar_case_count": len(task.context.similar_cases)}])
   ```
4. 그 외(반복 불만 아님)는 **LLM 을 부르지 않는다** — 이번 1단계는 범위를
   최소로 둔다. 고정 문자열로 응답한다:
   ```python
   answer = "피드백을 확인했습니다. 접수된 의견은 운영 개선에 반영됩니다."
   return TeamResult(..., outcome="completed", confidence=0.7, answer=answer,
                      evidence=evidence, next_action=NextAction.RESPOND)
   ```
   `self.llm` 파라미터는 생성자에 받되(다른 Team 과 시그니처 통일 —
   `__init__(self, tools, llm=None)`), 이번 1단계에선 실제로 호출하지 않는다.

`_evidence()` 는 다른 두 Team 과 같은 패턴으로 `task.context.evidence` +
policy 조회 결과를 합쳐 구성한다(`order_shipping.py`/`return_exchange.py`
의 `_evidence`/evidence 조합 코드를 참고해 같은 스타일로 작성 — 읽기만,
그 파일들은 고치지 않는다).

## 3. `app/modules/customer_ops/__init__.py`

기존 두 줄을 **지우지 말고** `VocStoreManagerTeam` import/export 를
추가한다. 최종적으로 `__all__` 에 셋 다 있어야 한다.

## 4. `config/project.yaml`

`teams:` 목록에 아래를 **추가**한다(기존 두 항목은 그대로 둔다):
```yaml
- team_id: voc_store_manager
  active: true
  implementation_ref: app.modules.customer_ops:VocStoreManagerTeam
```

## 5. 테스트 — `tests/unit/teams/test_voc_store_manager.py` (신규)

`tests/unit/teams/test_team_scenarios.py` 의 fixture 패턴(`FakeTools`,
`pack()`, `task()` 헬퍼)을 참고해 최소 4건:
- `similar_cases` 2건 이상 → `voc.escalate` 제안, `WAIT_FOR_APPROVAL`
- `similar_cases` 0~1건 → `completed`, 고정 응답 문자열
- `degraded=True` → `escalated`, `degraded_context`
- policy 조회 결과 없음 → `escalated`, `policy_not_found`

## 6. 검증

```powershell
python -m pytest tests/unit/teams/test_voc_store_manager.py -v
python -m pytest -q
```

★기대: 새 테스트 전부 통과, **전체 테스트 수가 늘어나고 실패 0**(기존
307 이상이어야 한다 — 정확한 시작 값은 직접 `pytest -q` 로 재확인해라,
다른 작업이 동시에 진행 중일 수 있다). `order_shipping`/`return_exchange`
관련 기존 테스트는 **하나도 안 깨져야 한다** — 이번 계약은 순수 추가다.

## 7. 리포트

`docs/reports/2026-08-19_S-VOC-STORE-MANAGER-TEAM_리포트.md` — 만든 파일,
설계 결정 근거(§2 그대로 구현했는지), `pytest -q` 원문, 신규/전체 테스트 수.
