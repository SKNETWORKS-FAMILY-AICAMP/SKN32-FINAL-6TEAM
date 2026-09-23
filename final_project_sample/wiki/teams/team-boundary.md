---
type: concept
title: Team과 Core의 실행 경계
description: Team이 넘지 말아야 할 경계와 코드 및 테스트가 실제로 막는 범위를 설명한다.
status: draft
tags: [architecture, contract, testing, security]
domain: neutral
---

Team은 근거 없는 답변이나 승인 대기 없는 승인 대상 제안을 반환하면 안 된다. 선언형 Team은 읽기 작업만 수행하고 `ActionProposal`을 만들지 않는다. `[실측]` 다만 일반 `TeamModule.execute()` 내부의 직접적인 부수 효과까지 막는 검사는 지정된 코드에서 확보되지 않았다. `[미확보]`

Core 쪽 경계는 Team 구현을 주입받고 계약을 통해 다루는 구조와 정적 import 검사로 형성된다. `[실측]` (`acop_basement/core/registry.py:7`, `acop_basement/core/registry.py:32`, `acop_basement/core/contracts.py` 의 `TeamModule`(`[2026-09-10]` 320 으로 적혀 있었다 — 지금 328))

## 결과 계약이 막는 것

`TeamResult`는 다음 출력을 모델 검증 단계에서 거부한다. `[실측]`

- 답변은 있지만 evidence가 없는 결과 (`acop_basement/core/contracts.py` 의 `TeamResult._next_action_consistency`)
- 승인 대상 제안이 있으면서 `next_action`이 `WAIT_FOR_APPROVAL`이 아닌 결과 (`acop_basement/core/contracts.py` 의 `TeamResult._next_action_consistency`)
- 결과에 없는 evidence를 제안의 근거로 참조한 결과 (`acop_basement/core/contracts.py` 의 `TeamResult._next_action_consistency`)
- `RESPOND`인데 답변이 없는 결과 (`acop_basement/core/contracts.py` 의 `TeamResult._next_action_consistency`)
- `WAIT_FOR_INPUT`인데 입력 스키마나 지정된 대기 사유가 없는 결과 (`acop_basement/core/contracts.py` 의 `TeamResult._next_action_consistency`)
- `WAIT_FOR_APPROVAL`인데 제안이나 지정된 대기 사유가 없는 결과 (`acop_basement/core/contracts.py` 의 `TeamResult._next_action_consistency`)
- `HANDOFF`인데 대상 capability가 없는 결과 (`acop_basement/core/contracts.py` 의 `TeamResult._next_action_consistency`)
- `ESCALATE`인데 실패 코드와 경고가 모두 없는 결과 (`acop_basement/core/contracts.py` 의 `TeamResult._next_action_consistency`)

★`[정정 2026-09-10]` 위 여덟 줄은 **줄번호로 가리키고 있었는데 전부 2~5줄씩 밀려 있었다.** 줄번호 대신 **검증기 이름**으로 바꿨다 — 코드가 늘어도 다시 밀리지 않는다.

계약 테스트는 이 거부 조건을 `ValidationError` 기대값으로 검사한다. `[실측]` (`tests/contract/test_contracts.py:112`, `tests/contract/test_contracts.py:120`, `tests/contract/test_contracts.py:125`, `tests/contract/test_contracts.py:137`, `tests/contract/test_contracts.py:144`, `tests/contract/test_contracts.py:165`, `tests/contract/test_contracts.py:183`, `tests/contract/test_contracts.py:195`)

`ActionProposal`은 행동의 종류와 인자, 멱등성 키, 승인 필요 여부, 위험도와 근거를 담는 결과 데이터다. `[실측]` (`acop_basement/core/contracts.py:201`) 이 모델이 존재한다는 사실만으로 임의의 Team 구현이 `execute()` 안에서 외부 부수 효과를 직접 실행하지 못하게 되지는 않는다. 이를 탐지하거나 차단하는 Team 내부 검사도 지정된 소스에서는 확인되지 않았다. `[미확보]`

## 선언형 Team이 지키는 경계

선언형 구현은 manifest의 `allowed_tools`를 `max_steps`까지만 순회하고, 도구 호출 시 작업에 들어온 `task.allowed_tools`도 함께 전달한다. `[실측]` (`acop_basement/teams/declarative.py:92`)

도구 호출 실패와 빈 결과는 경고로 남긴다. 근거가 하나도 없으면 답을 생성하지 않고 `failure_code="no_evidence"`로 에스컬레이션한다. `[실측]` (`acop_basement/teams/declarative.py:93`, `acop_basement/teams/declarative.py:101`, `acop_basement/teams/declarative.py:141`)

LLM이 없거나 빈 답을 반환하면 `no_draft`, LLM 호출이 실패하면 `draft_failed`로 에스컬레이션한다. `[실측]` (`acop_basement/teams/declarative.py:115`, `acop_basement/teams/declarative.py:145`, `acop_basement/teams/declarative.py:151`)

선언형 구현은 결과를 만들 때 `action_proposals`를 지정하지 않으므로 기본 빈 목록을 사용한다. `[실측]` (`acop_basement/teams/declarative.py:128`, `acop_basement/teams/declarative.py:157`, `acop_basement/core/contracts.py:236`)

`ReadToolbox`가 허용되지 않은 도구를 실제로 판정하는 내부 로직과 선언 로드 시점의 읽기 전용 제한 구현은 지정된 읽기 범위에 포함되지 않았다. `[미확보]`

## Core 격리 테스트가 실제로 금지하는 것

`test_core_isolation.py`는 선언문을 문자열로 검색하지 않는다. `acop_basement/core` 아래의 모든 `.py` 파일을 AST로 파싱하고, 트리 전체의 `ast.Import`와 `ast.ImportFrom` 노드를 검사한다. `[실측]` 함수 내부에 작성된 일반 import도 AST 순회 대상이다. (`tests/contract/test_core_isolation.py:14`)

핵심 검사는 다음과 같다. `[실측]`

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

따라서 정확히 금지되는 것은 Core 파일의 일반 import 대상이 다음 이름과 같거나 그 하위 이름인 경우다. `[실측]`

- `app.modules`
- `acop_basement.presentation`
- `acop_basement.infrastructure`
- `acop_basement.application`
- `app.composition`

검출되면 테스트는 해당 Core 파일과 import 이름을 포함한 `Core isolation violation` 메시지로 즉시 실패한다. `[실측]` (`tests/contract/test_core_isolation.py:25`)

검사 목록에는 `acop_basement.teams`가 없다. `[실측]` 따라서 “Core가 sample의 teams 패키지를 import하지 않는다”는 규칙은 이 테스트만으로 보장되지 않는다. `[미확보]` `contracts.py`의 설명은 해당 규칙을 테스트가 강제한다고 적지만, 현재 테스트가 직접 금지하는 Team 경로는 `app.modules`다. (`acop_basement/core/contracts.py:322`, `tests/contract/test_core_isolation.py:5`)

또한 이 검사는 `ast.Import`와 `ast.ImportFrom`만 본다. 문자열로 만든 모듈 이름이나 동적 import 호출을 별도로 검사하는 코드는 없다. `[실측]` (`tests/contract/test_core_isolation.py:18`)

별도 계약 테스트는 `acop_basement`의 모든 `.py` 파일에서 줄 시작이 `from app.`, `from app import`, `import app.`인 최상위 import를 수집해 실패시킨다. `[실측]` 들여쓰기된 지연 import는 이 줄 시작 검사에 걸리지 않는다. (`tests/contract/test_module_toggles.py:119`, `tests/contract/test_module_toggles.py:131`)

## 관계

- [Team 입출력 계약](team-contract.md)
- [Team 레지스트리](team-registry.md)
