# S-EVAL-RUNNER-TEAM-AGNOSTIC — eval 러너를 하드코딩 2팀에서 Registry 기반으로

## 0. 배경 (읽기만)

- `eval/runners/common.py:245-282` 의 `_team_context()` 가 지금
  `OrderShippingTeam`/`ReturnExchangeTeam` 두 클래스를 **직접 import**해서
  `intent in ("order","shipping")` 여부로 양자택일한다. 이 두 클래스는
  이미 `legacy/final_project_cs/team_modules_v1/` 로 옮겨졌고
  `config/project.yaml` 에도 없다 — 그래서 이 함수는 지금 100% 깨져 있다
  (`docs/reports/2026-08-20_S-DOD28-DEFENSE-METRICS-GOLDEN-RUN_리포트.md`
  에서 이미 확인된 사실).
- 오늘 별도 작업으로 Return&Refund, Procurement+Order&Payment,
  Fulfillment&Logistics Team 이 새로 만들어지고 있다(병렬 진행 중, 아직
  `config/project.yaml` 등록 전). **이 작업은 그 Team 들의 정확한 이름을
  몰라도 되게 만드는 게 목적이다** — 하드코딩을 없애고 Registry 를 실제
  진실의 원천으로 삼는다.

## 1. 할 일

1. `_team_context()` 를 다음 방식으로 다시 짜라:
   - 특정 Team 클래스를 import 하지 않는다.
   - `app/composition.py` 의 `build_registry()`(또는 동등한 조립 함수 —
     정확한 이름을 코드에서 확인해라) 를 이용해 `config/project.yaml`
     로부터 **실제 등록된 Team 들**을 로드한다.
   - `TeamRegistry.resolve(case_type=..., intent=...)` 로 이 case 를
     처리할 Team 을 찾는다. `case["expected_intent"]`(또는 동등한 필드)
     를 사용해라 — 정확한 필드명은 golden.jsonl 스키마를 확인해라.
   - **매칭되는 Team 이 없으면 조용히 스킵하지 마라.** 이 프로젝트 원칙
     (`CLAUDE.md` §3 "조용한 스킵을 만들지 않는다")대로, 명시적인 예외를
     던지거나 결과에 `"routing_failed"` 류의 명확한 상태를 남겨서 나중에
     "몇 건이 라우팅 자체가 안 됐는지" 셀 수 있게 해라.
2. `module = team(ReadToolbox(get_connection), llm=_OpenAITeamLLM())` 처럼
   생성자를 고정 가정하지 마라 — `app/composition.py` 의 `_instantiate_team()`
   이 이미 이 문제(단일/이중 인자 생성자 구분)를 해결해 놨다 — **그 함수를
   재사용해라, 새로 만들지 마라.**
3. `no_team_split` ablation 은 기존 의미(여러 case_type 을 한 Team 이 다
   처리하는지 보는 실험)를 유지하되, 지금 Registry 구조에서 이게 여전히
   말이 되는 개념인지 확인해라. 말이 안 되면(예: 지금은 애초에 여러
   Team 이 나뉘어 있는 게 구조 자체라 이 ablation 이 무의미해졌다면)
   그 사실을 리포트에 정직하게 적어라 — 억지로 옛 의미를 유지하려
   코드를 왜곡하지 마라.

## 2. golden/holdout 매핑 갭 — 고치지 말고 보고만 해라

`golden.jsonl`/`holdout.jsonl` 의 케이스들(`g-order-*`, `g-shipping-*`,
`g-return-*`, `g-exchange-*`)은 옛 2-Team(order_shipping/return_exchange)
체제로 작성됐다. v8 §8-B 의 새 6-Team 분할에서는:
- `order` intent 가 Procurement+Order&Payment **와** Catalog&Verification
  (A2A) 양쪽에 걸칠 수 있다(설계문서가 명시적으로 경고한 충돌 지점)
- `shipping` → Fulfillment&Logistics
- `return`/`exchange` → Return&Refund 하나로 합쳐짐

**이 매핑을 네가 임의로 확정하지 마라.** 대신:
- 지금 Registry 에 등록된 Team 들 기준으로 각 golden/holdout case 가
  라우팅되는지 안 되는지만 실행해서 세고 리포트에 남겨라(몇 건 성공,
  몇 건 `routing_failed`, 어떤 case_id 들인지).
- "이 갭을 메우려면 데이터셋을 어떻게 재작업해야 하는지"에 대한 네
  의견을 리포트 끝에 제안으로 남기되, **직접 golden.jsonl/holdout.jsonl
  을 고치지 마라** — 이건 Claude/사람이 결정할 사안이다.

## 3. 쓰기 대상

- `eval/runners/common.py` (`_team_context()` 및 관련 헬퍼만 — 파일의
  다른 함수는 건드리지 마라)
- `docs/reports/2026-08-20_S-EVAL-RUNNER-TEAM-AGNOSTIC_리포트.md` (신규)

## 4. 하지 말 것

- `eval/datasets/golden.jsonl`, `holdout.jsonl` 수정 금지
- `config/project.yaml` 수정 금지 — 지금 등록된 Team 이 `voc_store_manager`,
  `response_generation_review` 뿐이어도 그대로 둬라, 이 작업은 코드가
  Registry 를 올바르게 참조하게 만드는 것까지다
- `app/composition.py`, `app/core/registry.py` 의 기존 로직 수정 금지
  (재사용만 해라)
- 새 Team 클래스를 만들지 마라(다른 세션이 병렬로 하고 있다)

## 5. 검증

- `python -m pytest -q -m "not live"` 결과를 리포트에 붙여라(현재 338
  passed 기준 변화 명시). 이 파일은 pytest 로 직접 실행되진 않겠지만,
  import 가능한지(문법 오류 없는지)는 확인해라 —
  `python -c "import eval.runners.common"` 류로.
- 가능하면(API 키 있으면) golden.jsonl 몇 건으로 실제 라우팅 시도까지
  해보고 결과를 리포트에 남겨라. API 호출 자체가 안 되면 "라우팅 로직만
  검증, 실행은 미확인"이라고 정직하게 적어라.
