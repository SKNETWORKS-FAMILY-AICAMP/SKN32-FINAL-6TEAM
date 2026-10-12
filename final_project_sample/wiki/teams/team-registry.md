---
type: concept
title: capability 기반 Team 탐색
description: 레지스트리가 case type과 capability 의도로 Team을 선택하고 실패를 표현하는 방식을 설명한다.
status: draft
tags: [architecture, contract, api]
domain: neutral
---

`TeamRegistry.resolve()`는 capability만으로 Team을 직접 조회하지 않는다. 필수 `case_type`으로 활성 Team 후보를 만든 뒤 선택적인 `intent`를 manifest의 capability와 대조하고, 최종 후보가 정확히 하나일 때만 반환한다. `[실측]` (`acop_basement/core/registry.py:54`)

반환값은 manifest와 실제 Team 모듈을 함께 담는 `RegisteredTeam`이다. `[실측]` (`acop_basement/core/registry.py:23`)

## 등록

레지스트리는 생성자에 주입된 `TeamModule` 목록을 차례로 `register()`에 전달한다. `[실측]` (`acop_basement/core/registry.py:32`)

등록 과정은 다음 조건을 검사한다. `[실측]`

1. 레지스트리 계약 버전과 manifest 지원 버전 중 하나의 주 버전이 같아야 한다. (`acop_basement/core/registry.py:14`, `acop_basement/core/registry.py:40`)
2. 같은 `team_id`가 이미 등록되어 있으면 안 된다. (`acop_basement/core/registry.py:42`)
3. 통과한 Team은 `team_id`를 키로 하여 manifest와 모듈이 함께 저장된다. (`acop_basement/core/registry.py:44`)

기본 레지스트리 계약 버전은 `"1.0"`이다. 호환성 비교에는 점 앞의 주 버전만 사용하므로 `"1.x"`와 같은 주 버전의 지원값은 호환 후보가 된다. `[실측]` (`acop_basement/core/registry.py:14`, `acop_basement/core/registry.py:32`)

호환되지 않으면 `RegistryError("<team_id> does not support contract <version>")`, 중복 ID이면 `RegistryError("duplicate team_id: <team_id>")`가 발생한다. `[실측]` (`acop_basement/core/registry.py:40`, `acop_basement/core/registry.py:42`)

`TeamRegistry.register()` 자체에는 중복 capability 검사 코드가 없다. `[실측]` 지정된 통합 테스트는 별도의 조립 함수가 선언형 Team 사이의 중복 capability를 `CompositionError`로 거부해야 한다고 명시한다. `[실측]` 그 조립 함수 내부의 실제 중복 판정 구현은 지정된 읽기 범위에 없으므로 확인하지 않았다. `[미확보]` (`tests/integration/test_declarative_team_composition.py:64`)

## Team 선택

선택 순서는 다음과 같다. `[실측]`

1. `case_type`과 `intent`를 소문자로 정규화한다. 빈 `intent`는 `None`으로 취급한다. (`acop_basement/core/registry.py:63`)
2. 활성 상태이며 manifest의 `accepted_case_types`에 `case_type`이 대소문자 구분 없이 포함된 Team만 남긴다. (`acop_basement/core/registry.py:65`)
3. `intent`가 있으면 capability가 intent와 정확히 같거나 `intent + "."`로 시작하는 Team을 찾는다. (`acop_basement/core/registry.py:69`)
4. capability 일치 Team이 하나 이상 있을 때만 기존 후보를 그 목록으로 교체한다. (`acop_basement/core/registry.py:75`)
5. 최종 후보가 정확히 하나가 아니면 실패한다. 하나이면 그 `RegisteredTeam`을 반환한다. (`acop_basement/core/registry.py:77`)

예를 들어 intent가 `"demo"`이면 capability `"demo"`와 `"demo.investigate"`가 모두 일치 대상이다. `[실측]` (`acop_basement/core/registry.py:57`, `acop_basement/core/registry.py:72`)

`intent`와 일치하는 capability가 없더라도 즉시 실패하지 않는다. case type으로 만든 원래 후보를 그대로 사용한다. `[실측]` 따라서 그 후보가 하나이면 intent 불일치 상태에서도 해당 Team이 선택되고, 후보가 없거나 둘 이상이면 실패한다. (`acop_basement/core/registry.py:69`, `acop_basement/core/registry.py:77`)

## 선택된 capability

`capability_for(entry, intent)`는 선택된 Team에서 실제 사용할 capability 문자열을 정한다. `[실측]` (`acop_basement/core/registry.py:81`)

- intent와 정확히 같거나 intent namespace 아래인 첫 capability를 manifest 순서대로 반환한다. `[실측]`
- 일치값이 없거나 intent가 없으면 **`default_capability` 가 있으면 그것을, 없으면** manifest의 첫 capability를 반환한다(`acop_basement/core/registry.py:91`). `[정정 2026-09-10]` `default_capability` 단계가 빠져 있었다
- `TeamManifest.capabilities`는 최소 한 항목을 요구하므로 정상 manifest에서는 첫 항목이 존재한다. `[실측]`

근거: `acop_basement/core/registry.py:84`, `acop_basement/core/contracts.py:310`

선언형 Team 두 개가 서로 다른 ID와 capability를 선언하면 두 manifest와 capability가 모두 레지스트리 결과에 남는다는 기대가 통합 테스트에 명시되어 있다. `[실측]` (`tests/integration/test_declarative_team_composition.py:49`)

## 없거나 모호할 때

case type 후보가 없거나 최종 후보가 둘 이상이면 모두 같은 `RegistryError`가 발생한다. `[실측]`

```text
case must resolve to exactly one active team: <정규화된 case_type>
```

근거: `acop_basement/core/registry.py:77`

이 오류 메시지만으로는 “Team 없음”과 “Team이 여러 개라 모호함”을 구별할 수 없다. `[실측]`

ID로 직접 조회하는 `get(team_id)`에서 ID가 없으면 별도의 오류가 발생한다. `[실측]`

```text
unknown team: <team_id>
```

근거: `acop_basement/core/registry.py:48`

등록된 manifest 전체가 필요하면 `manifests()`가 manifest의 튜플을 반환한다. `[실측]` 실제 Team 모듈은 이 반환값에 포함되지 않는다. (`acop_basement/core/registry.py:91`)

## 관계

- [Team 입출력 계약](team-contract.md)
- [Team 경계](team-boundary.md)
