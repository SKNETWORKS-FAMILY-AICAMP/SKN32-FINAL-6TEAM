---
type: concept
title: Team Registry
description: capability를 Team 구현으로 해석한다. Core가 app.modules를 절대 import하지 않는 장치
status: draft
tags: [architecture, agent]
owners: [human:미배정]
domain: neutral
domain_note: Registry 기제는 도메인 무관이다. 표의 예시가 커머스 Team 이다
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

## 선언이 틀렸을 때 어디서 걸리나

`[실측 2026-09-07]` handoff 계약(`wiki/records/handoff/08`)이 「빌드 시 실패시켜야 할 것」
넷을 적어 뒀다. **넷 다 걸리기는 하는데 걸리는 시점이 다르다.** 기동 때 걸리는
것과 요청이 와야 걸리는 것을 섞으면 안 된다 — 뒤엣것은 **운영 중에 터진다.**

| 규칙 | 어디서 | 언제 |
|---|---|---|
| `active: true` 인데 `implementation_ref` 를 import 못 한다 | `project_config.py:157` `importlib.import_module` | **기동 때** |
| `implementation_ref` 가 클래스가 아니거나 `manifest`·`execute` 가 없다 | 동 `:173~179` | **기동 때** |
| 중복 `team_id` | `registry.py:46` `duplicate team_id` | **기동 때**(등록 순간) |
| 선언된 모듈에 게이트가 없다 | `tests/contract/test_module_toggles.py::test_every_declared_module_has_a_gate` | **테스트** |
| 같은 case 를 두 Team 이 주장한다 | `registry.py:85` `case must resolve to exactly one active team` | ★**요청이 올 때** |

★**마지막 줄이 다르다.** capability 가 겹치는 것은 등록 때 안 잡고 **해결 때** 잡는다.
선언만 보고는 알 수 없고 실제로 그 case 가 들어와야 두 Team 이 다 잡히기 때문이다.
겹치게 선언해 두면 **기동은 멀쩡히 되고 그 종류의 문의가 처음 올 때 터진다.**

★`active: false` 는 자리를 비워 두는 방법이다. Registry 에 이름은 있지만 라우팅되지
않아 Case 가 죽지 않는다 — "자리만 만들고 세부는 나중에" 를 안전하게 하는 관용이다.
비활성 선언은 스키마의 빈 문자열 검사 말고는 들여다보지 않는다(`project_config.py:143`).

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

### ★ [2026-09-10] 지금 등록된 것은 여행 여섯이다

`[실측 2026-09-10]` `config/project.yaml` 을 직접 셌다. **위 커머스 목록은 그때의 기록이고 코드에서 나갔다.**

```
activity · booking_handoff · mobility · dining   여행 Team (판정·제안)
lodging · flight                                 등록만 (잠긴 예약)
feedback                                         인라인 분류 — 남는다. 라벨만 교체됐다
```

| | 상태 |
|---|---|
| `app/modules/customer_ops/` | **작업 트리에서 제거** (2026-09-10, **커밋 전**). `feedback.py`·`verification_policy.py` 는 삭제가 아니라 `travel_ops/` 로 **이동**했다 |
| 커머스 Team 문서 7건 | [records/legacy/teams/](../records/legacy/teams/) 로 이동 |
| `place_verification` (A2A Remote) | **원격은 있고 등록은 0건** → [index.md](index.md) |

★**`final_project_sample` 의 예시 Team 은 아키텍처 증거로만 남는다.** 그 저장소의 도메인은 구독·결제이고 이 저장소와 별개다.

## 등록된 Team 수의 변화

`[실측]` `program/research/_cs_구현현황.md`(2026-08-19 스냅샷) · 루트 `CLAUDE.md`(09-01 v8 재판정) · `config/project.yaml`(2026-09-06 디스크).

| 시점 | `project.yaml` Team | 그 밖에 |
|---|---|---|
| 08-19 | **1개** — `voc_store_manager`만 | `ResponseGenerationReviewTeam`은 소스·manifest만 있고 미등록. `order_shipping`·`return_exchange`는 legacy로 밀려났고 `__pycache__`만 남아 있었다. `case_runtime/`·`team_modules/`는 빈 디렉터리 |
| 09-01 v8 재판정 | — | Response Generation & Review **확정**, VOC & Store Manager는 **등록·계약만 유지하는 껍데기**로. 08-19의 "하나뿐이던 등록 Team"이 껍데기가 되고 "미등록이던 Team"이 주인공이 됐다 |
| 09-06 | **6개 전부 `active: true`** — voc · response_generation_review · return_refund · procurement_order_payment · fulfillment_logistics · catalog_verification | 6개가 다 `implementation_ref`로 실제 클래스를 가리킨다 |

`[실측]` 루트 `CLAUDE.md`는 Return & Refund를 **(Mock)**, Catalog & Verification을 **(A2A Remote)**라 적는데 `project.yaml`엔 둘 다 다른 넷과 같은 모양으로 등록돼 있다. 등록 형식만으로는 안 보이지만 **`return_refund.py`는 docstring부터 `Mock-only`**다 — 2026-09-06 Mock 유지로 정했다 → [return-refund.md](../records/legacy/teams/return-refund.md) · [scope-verdicts](../../../wiki/delivery/scope-verdicts.md).

## 관계

- [team-contract.md](team-contract/index.md) — `TeamManifest` 모양
- [team-boundary.md](team-boundary.md) — 등록 이후의 규칙
- [../runtime/agentic-controller.md](../runtime/agentic-controller.md) — Registry를 쓰는 쪽
- [../../../wiki/architecture/pack-model.md](../../../wiki/architecture/pack-model.md) — Pack 교체 가능성
