---
type: concept
title: Team Registry
description: capability를 Team 구현으로 해석한다. Core가 app.modules를 절대 import하지 않는 장치
status: draft
tags: [architecture, agent]
owners: [human:미배정]
---

# Team Registry

`app/core/registry.py` (93줄)

## 책임

capability를 Team 구현으로 해석한다. **Team을 추가·교체할 때 Core 코드가 안 바뀌게 하는 장치다.**

## ★ 주입받는다, import하지 않는다

`[실측]` 클래스 docstring이 규칙을 밝히고 있다.

```python
class TeamRegistry:
    """Maps capabilities to injected Team modules; never imports app.modules."""
```

파일 첫 줄도 그렇다.

```python
"""Dependency-free registry for Team manifests and injected implementations."""
```

**Registry가 Team을 만들지 않는다.** 이미 만들어진 것을 받아 등록만 한다.

```python
def __init__(self, teams: list[TeamModule] | None = None, *, contract_version: str = "1.0"):
    for team in teams or []:
        self.register(team)
```

조립은 `config/project.yaml`이 하고 composition root가 주입한다.

**이게 `INV-CS-ARCH-003`이 성립하는 이유다.**

## 등록할 때 거부하는 것

`[실측]` `register()`가 두 가지를 막는다.

```python
if not _compatible(self.contract_version, manifest.supported_contract_versions):
    raise RegistryError(f"{manifest.team_id} does not support contract {...}")
if manifest.team_id in self._teams:
    raise RegistryError(f"duplicate team_id: {manifest.team_id}")
```

| 거부 | 왜 |
|---|---|
| 계약 버전 불일치 | 못 알아듣는 Team이 Task를 받으면 안 된다 |
| team_id 중복 | 어느 쪽이 응답할지 모르게 된다 |

**조용히 덮어쓰지 않고 예외를 던진다.**

## 계약 호환은 major 버전만 본다

```python
def _compatible(requested, supported) -> bool:
    """A contract is compatible only within the same major version."""
    major = requested.split(".", 1)[0]
    return any(version.split(".", 1)[0] == major for version in supported)
```

`1.0`과 `1.3`은 호환, `1.x`와 `2.x`는 비호환이다.

**minor 변경은 하위 호환이어야 한다는 뜻이다.** 계약에 필드를 추가할 때 이 약속을 지켜야 한다.

## ★ 해석 규칙 — 후보는 정확히 하나여야 한다

`[실측]` `TeamRegistry.resolve(case_type, intent)`

```
① accepted_case_types 로 후보를 좁힌다
② intent 가 있으면 capability 가
     intent 와 같거나  intent + "." 로 시작하는 Team 을 우선
③ 최종 후보는 정확히 하나여야 한다
```

**②의 접두사 규칙이 편하다.** `intent="refund"`면 `refund.calculate`가 걸린다.

### 따라오는 제약

**case type 을 여러 Team 이 공유하면 intent 가 반드시 있어야 한다.**

| 상황 | 해야 할 것 |
|---|---|
| 한 case type 을 여러 Team 이 받는다 | **분류 결과에 intent 를 반드시 포함** |
| intent 없는 경로가 있다 | **case type 을 분리**해 충돌을 막는다 |

**후보가 둘이면 실패한다.** 조용히 하나를 고르지 않는다.

`[실측]` 이 제약이 `feedback.py::INTENTS` 결함과 연결된다 — 분류기가 내는 intent 에 대응 Team 이 없으면 Case 가 갈 곳을 잃는다. → [../external/rest-api.md](../external/rest-api.md)

## 허용 도구 판정

Team은 `TeamManifest.allowed_tools` 밖의 도구를 호출할 수 없다. **Registry가 거부한다.**

`ToolNotAllowed` 예외가 `app/core/contracts.py`에 있다.

→ [../actions/tool-gateway.md](../actions/tool-gateway.md)

## Team을 추가하려면

```text
1. TeamModule 구현 (manifest + execute)
2. config/project.yaml 에 등록
```

**Core 파일을 하나라도 고쳐야 하면 설계가 잘못된 것이다.**

## 불변식

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-ARCH-003` | Core는 `app/modules`를 import하지 않는다 | automated | `tests/contract/test_core_isolation.py::test_core_does_not_import_modules` |
| `INV-CS-TEAM-001` | Team manifest는 프로토콜을 구현한다 | automated | `tests/contract/test_team_contract.py::test_team_manifests_implement_protocol` |
| `INV-CS-TEAM-002` | manifest의 scope는 정확히 선언된다 | automated | `tests/contract/test_team_contract.py::test_manifest_scopes_are_exact` |

## 현재 등록된 Team

`[실측]` `app/modules/customer_ops/`

```
voc_store_manager · response_review          CS Pack (착수 확정)
procurement_order_payment · fulfillment_logistics
return_refund · catalog_verification         Commerce Ops Pack
feedback                                     인라인 분류
```

`final_project_sample`의 Billing/Technical 2종은 **아키텍처 증거로만 남기고 착수 목록에 없다.**

## 등록된 Team 수의 변화

`[실측]` `program/research/_cs_구현현황.md`(2026-08-19 스냅샷) · 루트 `CLAUDE.md`(09-01 v8 재판정) · `config/project.yaml`(2026-09-06 디스크).

| 시점 | `project.yaml` Team | 그 밖에 |
|---|---|---|
| 08-19 | **1개** — `voc_store_manager`만 | `ResponseGenerationReviewTeam`은 소스·manifest만 있고 미등록. `order_shipping`·`return_exchange`는 legacy로 밀려났고 `__pycache__`만 남아 있었다. `case_runtime/`·`team_modules/`는 빈 디렉터리 |
| 09-01 v8 재판정 | — | Response Generation & Review **확정**, VOC & Store Manager는 **등록·계약만 유지하는 껍데기**로. 08-19의 "하나뿐이던 등록 Team"이 껍데기가 되고 "미등록이던 Team"이 주인공이 됐다 |
| 09-06 | **6개 전부 `active: true`** — voc · response_generation_review · return_refund · procurement_order_payment · fulfillment_logistics · catalog_verification | 6개가 다 `implementation_ref`로 실제 클래스를 가리킨다 |

`[미확보]` 루트 `CLAUDE.md`는 Return & Refund를 **(Mock)**, Catalog & Verification을 **(A2A Remote)**라 적는데 `project.yaml`엔 둘 다 다른 넷과 같은 모양으로 등록돼 있다. 등록 형식만으로는 Mock인지 실구현인지 안 보인다 → [return-refund.md](return-refund.md).

## 관계

- [team-contract.md](team-contract/index.md) — `TeamManifest` 모양
- [team-boundary.md](team-boundary.md) — 등록 이후의 규칙
- [../runtime/agentic-controller.md](../runtime/agentic-controller.md) — Registry를 쓰는 쪽
- [../../../wiki/architecture/pack-model.md](../../../wiki/architecture/pack-model.md) — Pack 교체 가능성
