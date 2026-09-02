===== FILE: team-contract.md =====
---
type: concept
title: Team 입출력 계약
description: Team이 받는 작업과 반환하는 결과, 그리고 필수 필드를 설명한다.
status: draft
tags: [architecture, contract, api]
---

Team은 `manifest`를 공개하고 `execute(TeamTask) -> TeamResult`를 비동기로 구현하는 객체다. [실측] Core가 요구하는 표면은 이 두 가지뿐이다. (`acop_basement/core/contracts.py:320`)

```python
@runtime_checkable
class TeamModule(Protocol):
    manifest: TeamManifest

    async def execute(self, task: TeamTask) -> TeamResult: ...
```

근거: `acop_basement/core/contracts.py:320`

## Team의 선언

`TeamManifest`는 Team의 식별자, 처리 범위와 실행 한도를 선언한다. 정의되지 않은 추가 필드는 허용되지 않는다. [실측] (`acop_basement/core/contracts.py:303`)

| 구분 | 필드 |
|---|---|
| 생성 시 필수 [실측] | `team_id`, `display_name`, `contract_name`, `supported_contract_versions`, `capabilities`, `accepted_case_types`, `required_context`, `allowed_tools`, `knowledge_scope`, `implementation_revision` |
| 기본값이 있는 필드 [실측] | `max_steps=6`, `active=True` |
| 고정값 [실측] | `contract_name`은 `"a_cop.team_task"` |
| 제한값 [실측] | `capabilities`는 최소 1개, `max_steps`는 1 이상 12 이하 |
| `required_context` 허용값 [실측] | `"case_state"`, `"policy"`, `"db_facts"`, `"history"` |

근거: `acop_basement/core/contracts.py:303`

선언형 구현은 선언값으로 manifest를 만들되 `contract_name="a_cop.team_task"`, 지원 버전 `["1.0"]`, `active=True`, 구현 리비전 `"declarative.v1"`을 직접 채운다. [실측] (`acop_basement/teams/declarative.py:63`)

계약 테스트는 Team 인스턴스가 `TeamModule`로 인식되는지, manifest가 `TeamManifest`인지, 계약 이름·지원 버전·실행 단계·활성 상태가 기대값인지 검사한다. [실측] 이 테스트는 `execute()`를 호출해 반환 형식까지 검사하지는 않는다. (`tests/contract/test_team_contract.py:7`)

## Team이 받는 값

`execute()`의 입력은 `TeamTask` 한 건이다. [실측] (`acop_basement/core/contracts.py:330`)

| 구분 | 필드 |
|---|---|
| 생성 시 필수 [실측] | `task_id`, `run_id`, `case_id`, `team_id`, `capability`, `case_version`, `input_text`, `context`, `allowed_tools`, `deadline_at` |
| 기본값이 있는 필드 [실측] | `contract_name="a_cop.team_task"`, `contract_version="1.0"`, `resume=False`, `resume_node=None` |
| 제한값 [실측] | `input_text`는 1자 이상 12,000자 이하 |

근거: `acop_basement/core/contracts.py:165`

`context`는 `ContextPack`이다. 생성 시 필수 필드는 `pack_id`, `case_id`, `team_id`, `tenant_id`, `knowledge_scope`, `current_state`, `estimated_input_tokens`다. [실측] (`acop_basement/core/contracts.py:122`)

`ContextPack.token_budget`은 `12000`으로 고정된다. `estimated_input_tokens`가 이를 넘으면 검증에 실패하고, `degraded=True`이면 비어 있지 않은 `omissions`가 필요하다. [실측] (`acop_basement/core/contracts.py:141`, `acop_basement/core/contracts.py:146`)

다음 입력 정합성도 모델 생성 시 검사된다. [실측]

- `resume=True`이면 `resume_node`가 있어야 한다. (`acop_basement/core/contracts.py:185`)
- `resume=False`이면 `resume_node`가 없어야 한다. (`acop_basement/core/contracts.py:187`)
- `TeamTask`와 `ContextPack`의 `case_id`가 같아야 한다. (`acop_basement/core/contracts.py:189`)
- `TeamTask`와 `ContextPack`의 `team_id`가 같아야 한다. (`acop_basement/core/contracts.py:191`)

계약 테스트는 빈 `input_text`, 잘못된 resume 조합, 서로 다른 `case_id`를 실제 거부 대상으로 둔다. [실측] (`tests/contract/test_contracts.py:230`, `tests/contract/test_contracts.py:240`, `tests/contract/test_contracts.py:246`)

## Team이 돌려주는 값

`execute()`의 반환값은 `TeamResult`다. [실측] (`acop_basement/core/contracts.py:330`)

| 구분 | 필드 |
|---|---|
| 생성 시 필수 [실측] | `task_id`, `run_id`, `team_id`, `outcome`, `confidence`, `next_action` |
| 기본값이 있는 식별 필드 [실측] | `contract_name="a_cop.team_result"`, `contract_version="1.0"` |
| 기본값이 있는 내용 필드 [실측] | `answer=None`, `evidence=[]`, `decisions=[]`, `action_proposals=[]`, `wait_reason=None`, `required_input_schema=None`, `handoff_capability=None`, `failure_code=None`, `warnings=[]` |
| `outcome` 허용값 [실측] | `"completed"`, `"waiting"`, `"handoff"`, `"escalated"`, `"failed"` |
| 제한값 [실측] | `answer`는 최대 6,000자, `confidence`는 0 이상 1 이하 |

근거: `acop_basement/core/contracts.py:223`

`next_action`에 따라 다음 필드가 조건부로 필요하다. [실측]

- `WAIT_FOR_INPUT`: `wait_reason="customer_input"`과 `required_input_schema`
- `WAIT_FOR_APPROVAL`: `wait_reason="human_approval"`과 하나 이상의 `action_proposals`
- `HANDOFF`: `handoff_capability`
- `RESPOND`: 비어 있지 않은 `answer`
- `ESCALATE`: `failure_code` 또는 하나 이상의 `warnings`

근거: `acop_basement/core/contracts.py:244`

답변이 있으면 하나 이상의 `evidence`가 필요하다. 제안의 `rationale_evidence_ids`는 같은 결과의 evidence를 가리켜야 한다. [실측] (`acop_basement/core/contracts.py:272`, `acop_basement/core/contracts.py:287`)

선언형 구현은 근거가 없거나 초안을 만들지 못하면 `outcome="escalated"`인 결과를 돌려주고, 초안 생성에 성공하면 `outcome="completed"`, `next_action=RESPOND`, `confidence=0.6`인 결과를 돌려준다. [실측] (`acop_basement/teams/declarative.py:128`, `acop_basement/teams/declarative.py:138`, `acop_basement/teams/declarative.py:157`)

## 관계

- [Team 경계](./team-boundary.md)
- [Team 레지스트리](./team-registry.md)

===== FILE: team-boundary.md =====
---
type: concept
title: Team과 Core의 실행 경계
description: Team이 넘지 말아야 할 경계와 코드 및 테스트가 실제로 막는 범위를 설명한다.
status: draft
tags: [architecture, contract, testing, security]
---

Team은 근거 없는 답변이나 승인 대기 없는 승인 대상 제안을 반환하면 안 된다. 선언형 Team은 읽기 작업만 수행하고 `ActionProposal`을 만들지 않는다. [실측] 다만 일반 `TeamModule.execute()` 내부의 직접적인 부수 효과까지 막는 검사는 지정된 코드에서 확보되지 않았다. [미확보]

Core 쪽 경계는 Team 구현을 주입받고 계약을 통해 다루는 구조와 정적 import 검사로 형성된다. [실측] (`acop_basement/core/registry.py:7`, `acop_basement/core/registry.py:32`, `acop_basement/core/contracts.py:320`)

## 결과 계약이 막는 것

`TeamResult`는 다음 출력을 모델 검증 단계에서 거부한다. [실측]

- 답변은 있지만 evidence가 없는 결과 (`acop_basement/core/contracts.py:272`)
- 승인 대상 제안이 있으면서 `next_action`이 `WAIT_FOR_APPROVAL`이 아닌 결과 (`acop_basement/core/contracts.py:278`)
- 결과에 없는 evidence를 제안의 근거로 참조한 결과 (`acop_basement/core/contracts.py:287`)
- `RESPOND`인데 답변이 없는 결과 (`acop_basement/core/contracts.py:264`)
- `WAIT_FOR_INPUT`인데 입력 스키마나 지정된 대기 사유가 없는 결과 (`acop_basement/core/contracts.py:248`)
- `WAIT_FOR_APPROVAL`인데 제안이나 지정된 대기 사유가 없는 결과 (`acop_basement/core/contracts.py:254`)
- `HANDOFF`인데 대상 capability가 없는 결과 (`acop_basement/core/contracts.py:260`)
- `ESCALATE`인데 실패 코드와 경고가 모두 없는 결과 (`acop_basement/core/contracts.py:268`)

계약 테스트는 이 거부 조건을 `ValidationError` 기대값으로 검사한다. [실측] (`tests/contract/test_contracts.py:112`, `tests/contract/test_contracts.py:120`, `tests/contract/test_contracts.py:125`, `tests/contract/test_contracts.py:137`, `tests/contract/test_contracts.py:144`, `tests/contract/test_contracts.py:165`, `tests/contract/test_contracts.py:183`, `tests/contract/test_contracts.py:195`)

`ActionProposal`은 행동의 종류와 인자, 멱등성 키, 승인 필요 여부, 위험도와 근거를 담는 결과 데이터다. [실측] (`acop_basement/core/contracts.py:201`) 이 모델이 존재한다는 사실만으로 임의의 Team 구현이 `execute()` 안에서 외부 부수 효과를 직접 실행하지 못하게 되지는 않는다. 이를 탐지하거나 차단하는 Team 내부 검사도 지정된 소스에서는 확인되지 않았다. [미확보]

## 선언형 Team이 지키는 경계

선언형 구현은 manifest의 `allowed_tools`를 `max_steps`까지만 순회하고, 도구 호출 시 작업에 들어온 `task.allowed_tools`도 함께 전달한다. [실측] (`acop_basement/teams/declarative.py:92`)

도구 호출 실패와 빈 결과는 경고로 남긴다. 근거가 하나도 없으면 답을 생성하지 않고 `failure_code="no_evidence"`로 에스컬레이션한다. [실측] (`acop_basement/teams/declarative.py:93`, `acop_basement/teams/declarative.py:101`, `acop_basement/teams/declarative.py:141`)

LLM이 없거나 빈 답을 반환하면 `no_draft`, LLM 호출이 실패하면 `draft_failed`로 에스컬레이션한다. [실측] (`acop_basement/teams/declarative.py:115`, `acop_basement/teams/declarative.py:145`, `acop_basement/teams/declarative.py:151`)

선언형 구현은 결과를 만들 때 `action_proposals`를 지정하지 않으므로 기본 빈 목록을 사용한다. [실측] (`acop_basement/teams/declarative.py:128`, `acop_basement/teams/declarative.py:157`, `acop_basement/core/contracts.py:236`)

`ReadToolbox`가 허용되지 않은 도구를 실제로 판정하는 내부 로직과 선언 로드 시점의 읽기 전용 제한 구현은 지정된 읽기 범위에 포함되지 않았다. [미확보]

## Core 격리 테스트가 실제로 금지하는 것

`test_core_isolation.py`는 선언문을 문자열로 검색하지 않는다. `acop_basement/core` 아래의 모든 `.py` 파일을 AST로 파싱하고, 트리 전체의 `ast.Import`와 `ast.ImportFrom` 노드를 검사한다. [실측] 함수 내부에 작성된 일반 import도 AST 순회 대상이다. (`tests/contract/test_core_isolation.py:14`)

핵심 검사는 다음과 같다. [실측]

```python
_FORBIDDEN_PREFIXES = (
    "app.modules",
    "acop_basement.presentation",
    "acop_basement.infrastructure",
    "acop_basement.application",
    "app.composition",
)

root = Path("acop_basement/core")
for path in root.rglob("*.py"):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        for name in names:
            if any(
                name == prefix or name.startswith(prefix + ".")
                for prefix in _FORBIDDEN_PREFIXES
            ):
                assert False, (
                    f"Core isolation violation: {path} imports {name}"
                )
```

근거: `tests/contract/test_core_isolation.py:5`, `tests/contract/test_core_isolation.py:14`

따라서 정확히 금지되는 것은 Core 파일의 일반 import 대상이 다음 이름과 같거나 그 하위 이름인 경우다. [실측]

- `app.modules`
- `acop_basement.presentation`
- `acop_basement.infrastructure`
- `acop_basement.application`
- `app.composition`

검출되면 테스트는 해당 Core 파일과 import 이름을 포함한 `Core isolation violation` 메시지로 즉시 실패한다. [실측] (`tests/contract/test_core_isolation.py:25`)

검사 목록에는 `acop_basement.teams`가 없다. [실측] 따라서 “Core가 sample의 teams 패키지를 import하지 않는다”는 규칙은 이 테스트만으로 보장되지 않는다. [미확보] `contracts.py`의 설명은 해당 규칙을 테스트가 강제한다고 적지만, 현재 테스트가 직접 금지하는 Team 경로는 `app.modules`다. (`acop_basement/core/contracts.py:322`, `tests/contract/test_core_isolation.py:5`)

또한 이 검사는 `ast.Import`와 `ast.ImportFrom`만 본다. 문자열로 만든 모듈 이름이나 동적 import 호출을 별도로 검사하는 코드는 없다. [실측] (`tests/contract/test_core_isolation.py:18`)

별도 계약 테스트는 `acop_basement`의 모든 `.py` 파일에서 줄 시작이 `from app.`, `from app import`, `import app.`인 최상위 import를 수집해 실패시킨다. [실측] 들여쓰기된 지연 import는 이 줄 시작 검사에 걸리지 않는다. (`tests/contract/test_module_toggles.py:119`, `tests/contract/test_module_toggles.py:131`)

## 관계

- [Team 입출력 계약](./team-contract.md)
- [Team 레지스트리](./team-registry.md)

===== FILE: team-registry.md =====
---
type: concept
title: capability 기반 Team 탐색
description: 레지스트리가 case type과 capability 의도로 Team을 선택하고 실패를 표현하는 방식을 설명한다.
status: draft
tags: [architecture, contract, api]
---

`TeamRegistry.resolve()`는 capability만으로 Team을 직접 조회하지 않는다. 필수 `case_type`으로 활성 Team 후보를 만든 뒤 선택적인 `intent`를 manifest의 capability와 대조하고, 최종 후보가 정확히 하나일 때만 반환한다. [실측] (`acop_basement/core/registry.py:54`)

반환값은 manifest와 실제 Team 모듈을 함께 담는 `RegisteredTeam`이다. [실측] (`acop_basement/core/registry.py:23`)

## 등록

레지스트리는 생성자에 주입된 `TeamModule` 목록을 차례로 `register()`에 전달한다. [실측] (`acop_basement/core/registry.py:32`)

등록 과정은 다음 조건을 검사한다. [실측]

1. 레지스트리 계약 버전과 manifest 지원 버전 중 하나의 주 버전이 같아야 한다. (`acop_basement/core/registry.py:14`, `acop_basement/core/registry.py:40`)
2. 같은 `team_id`가 이미 등록되어 있으면 안 된다. (`acop_basement/core/registry.py:42`)
3. 통과한 Team은 `team_id`를 키로 하여 manifest와 모듈이 함께 저장된다. (`acop_basement/core/registry.py:44`)

기본 레지스트리 계약 버전은 `"1.0"`이다. 호환성 비교에는 점 앞의 주 버전만 사용하므로 `"1.x"`와 같은 주 버전의 지원값은 호환 후보가 된다. [실측] (`acop_basement/core/registry.py:14`, `acop_basement/core/registry.py:32`)

호환되지 않으면 `RegistryError("<team_id> does not support contract <version>")`, 중복 ID이면 `RegistryError("duplicate team_id: <team_id>")`가 발생한다. [실측] (`acop_basement/core/registry.py:40`, `acop_basement/core/registry.py:42`)

`TeamRegistry.register()` 자체에는 중복 capability 검사 코드가 없다. [실측] 지정된 통합 테스트는 별도의 조립 함수가 선언형 Team 사이의 중복 capability를 `CompositionError`로 거부해야 한다고 명시한다. [실측] 그 조립 함수 내부의 실제 중복 판정 구현은 지정된 읽기 범위에 없으므로 확인하지 않았다. [미확보] (`tests/integration/test_declarative_team_composition.py:64`)

## Team 선택

선택 순서는 다음과 같다. [실측]

1. `case_type`과 `intent`를 소문자로 정규화한다. 빈 `intent`는 `None`으로 취급한다. (`acop_basement/core/registry.py:63`)
2. 활성 상태이며 manifest의 `accepted_case_types`에 `case_type`이 대소문자 구분 없이 포함된 Team만 남긴다. (`acop_basement/core/registry.py:65`)
3. `intent`가 있으면 capability가 intent와 정확히 같거나 `intent + "."`로 시작하는 Team을 찾는다. (`acop_basement/core/registry.py:69`)
4. capability 일치 Team이 하나 이상 있을 때만 기존 후보를 그 목록으로 교체한다. (`acop_basement/core/registry.py:75`)
5. 최종 후보가 정확히 하나가 아니면 실패한다. 하나이면 그 `RegisteredTeam`을 반환한다. (`acop_basement/core/registry.py:77`)

예를 들어 intent가 `"demo"`이면 capability `"demo"`와 `"demo.investigate"`가 모두 일치 대상이다. [실측] (`acop_basement/core/registry.py:57`, `acop_basement/core/registry.py:72`)

`intent`와 일치하는 capability가 없더라도 즉시 실패하지 않는다. case type으로 만든 원래 후보를 그대로 사용한다. [실측] 따라서 그 후보가 하나이면 intent 불일치 상태에서도 해당 Team이 선택되고, 후보가 없거나 둘 이상이면 실패한다. (`acop_basement/core/registry.py:69`, `acop_basement/core/registry.py:77`)

## 선택된 capability

`capability_for(entry, intent)`는 선택된 Team에서 실제 사용할 capability 문자열을 정한다. [실측] (`acop_basement/core/registry.py:81`)

- intent와 정확히 같거나 intent namespace 아래인 첫 capability를 manifest 순서대로 반환한다. [실측]
- 일치값이 없거나 intent가 없으면 manifest의 첫 capability를 반환한다. [실측]
- `TeamManifest.capabilities`는 최소 한 항목을 요구하므로 정상 manifest에서는 첫 항목이 존재한다. [실측]

근거: `acop_basement/core/registry.py:84`, `acop_basement/core/contracts.py:310`

선언형 Team 두 개가 서로 다른 ID와 capability를 선언하면 두 manifest와 capability가 모두 레지스트리 결과에 남는다는 기대가 통합 테스트에 명시되어 있다. [실측] (`tests/integration/test_declarative_team_composition.py:49`)

## 없거나 모호할 때

case type 후보가 없거나 최종 후보가 둘 이상이면 모두 같은 `RegistryError`가 발생한다. [실측]

```text
case must resolve to exactly one active team: <정규화된 case_type>
```

근거: `acop_basement/core/registry.py:77`

이 오류 메시지만으로는 “Team 없음”과 “Team이 여러 개라 모호함”을 구별할 수 없다. [실측]

ID로 직접 조회하는 `get(team_id)`에서 ID가 없으면 별도의 오류가 발생한다. [실측]

```text
unknown team: <team_id>
```

근거: `acop_basement/core/registry.py:48`

등록된 manifest 전체가 필요하면 `manifests()`가 manifest의 튜플을 반환한다. [실측] 실제 Team 모듈은 이 반환값에 포함되지 않는다. (`acop_basement/core/registry.py:91`)

## 관계

- [Team 입출력 계약](./team-contract.md)
- [Team 경계](./team-boundary.md)