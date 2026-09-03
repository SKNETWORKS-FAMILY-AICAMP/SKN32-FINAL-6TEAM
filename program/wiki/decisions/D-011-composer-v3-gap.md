---
type: decision
title: Composer v3 설계와 구현 중 무엇을 맞출 것인가
description: 설계는 토글 전용인데 구현은 전체 교체다. 세 안을 비교했고 결정에 질문 6개가 남아 있다
status: draft
impl_scope: sample — Composer 는 sample 이 원본이고 cs 로 이식한다. D-006 참조
tags: [architecture, api, contract]
---

# D-011 Composer v3 설계와 구현 중 무엇을 맞출 것인가

`[미확보]` **아직 안 정했다.** 결정에 답이 필요한 질문이 여섯 개 남아 있다.

## 문제

**설계와 구현이 서로 다른 계약을 가리킨다.**

| | 계약 |
|---|---|
| **v3 설계** | `POST /composer/toggle` **하나로** — 등록 ID 확인 · flag 변경 · revision 충돌 · 감사 |
| **sample 구현** | `ProjectConfig` **전체**를 받아 검증·교체하는 v2 형 — `current` · `validate` · `apply` |

**항목 11개를 대조했더니 일치가 1건이었다.** → [sample/composer/design-gap.md](../../final_project_sample/wiki/composer/design-gap.md)

## 세 안

| | 무엇 |
|---|---|
| **안 A** | **구현을 설계에 맞춘다** — toggle 전용으로 좁힌다 |
| **안 B** | **설계를 구현에 맞춘다** — v2 형을 정본으로 |
| **안 C** | **병행한다** — 종료일을 정하고 |

### 기준별 비교

`[실측]` 설계 문서와 대조 보고서에서 확인된 기준.

| 기준 | A | B | C |
|---|---|---|---|
| UI 가 Core 모델을 import 안 함 | **가장 직접적으로 충족** | 직접 import 는 피하나 **schema 복제 위험** | 새 UI 만 충족 |
| Composer 를 고객 빌드에서 배제 | 구조상 가능 | 현재 구조로 가능 | 결합 검증 필요 |
| **좁은 v3 책임** | **충족** | **포기** | 새 경로만 |
| **v2 소비자 연속성** | **깨질 가능성 큼** | **가장 잘 보존** | 단기 보존 |
| 되돌리기 단순성 | 전환 중 큼 | 단순 | 장기에 복잡 |

**A 와 B 가 정확히 반대다.** 좁은 책임을 얻으면 연속성을 잃는다.

## ★ 답해야 결정할 수 있는 질문 여섯

`[미확보]` **하나도 안 정해졌다.**

1. **고객용 빌드에서 `acop_composer` 와 `/composer/*` 를 완전히 배제하는 것이 양보할 수 없는 목표인가?**
2. **기존 `/composer/validate`·`/composer/apply` 를 부르는 외부 소비자나 운영 절차가 실제로 있는가?**
3. 전체 `ProjectConfig` 교체가 필요한 운영 요구가 남아 있는가, 아니면 flag toggle 로 충분한가?
4. UI 의 비포크 원칙은 **직접 import 만** 금지하는가, **동등한 schema 복제도** 금지하는가?
5. 병행한다면 두 경로가 같은 `project.yaml` 을 공유해야 하는가?
6. deprecation 기간·종료일·제거 책임 주체를 정할 수 있는가?

### 1번과 2번이 갈림길이다

`[실측]` 원문의 권고가 이 둘로 갈린다.

```
1번이 필수 AND 2번이 없다   →  안 A
2번이 있거나 3번이 필수      →  안 B 또는 (종료일 있는) 안 C
```

**그러니 2번을 먼저 세면 된다.** 외부 소비자가 실제로 있는지는 셀 수 있는 사실이다.

`[미확보]` **안 세었다.**

## 지금 상태

`[실측]` 2026-09-02 확인. **`/composer/toggle` 경로 자체는 존재한다.**

```
POST /composer/toggle   POST /composer/validate
POST /composer/apply    GET  /composer/current
```

**둘 다 있다.** 사실상 안 C(병행) 상태인데 **종료일이 없다.**

> **종료일 없는 병행은 안 C 가 아니라 그냥 미결이다.**

## ★ [2026-09-03] introspection 계약도 갈라져 있다

`[실측]` `A-COP_Composer_v3_설계_토글전용_UI이관.md` §2 를 오늘 구현과 대조했다.

| | 값 |
|---|---|
| **설계가 요구한 것** | `contract_version: "introspection.v3"` |
| **실제 구현** | `CONTRACT_VERSION = "1.1"` (`introspection/contract.py:27`) |

**이름 체계 자체가 다르다.** `introspection.vN` 이 아니라 `N.N` 이다.

### 설계에만 있는 필드

`[실측]` 설계는 **`registered_ids`** 를 요구한다 — "제품이 등록해 둔 항목의 ID 목록".

```json
"registered_ids": {
  "modules": ["vector_rag", "graph_store", …],
  "teams": ["order_shipping", "return_exchange"],
  "ports": ["team_executor", "message_broker", "graph_store"]
}
```

**구현에 이 필드가 없다.** 대신 `modules`·`teams`·`ports` 를 직접 낸다.

### 구현에만 있는 필드

`[실측]` **구현이 설계보다 더 낸다.**

```python
"active_revision":  active_revision,      # 실행 중인 것
"desired_revision": desired_revision,     # 선언된 것
"reload_state":     reload_state,
"reload_error":     …,
"team_manifests":   manifests,
"port_implementations": …,
```

**주석이 이유를 적어 뒀다.**

> ★**선언과 조립을 함께 낸다.** 선언만 보면 **"켰다고 적혀 있는데 실제로는 안 올라간" 경우를 못 본다.**

> ★옛 소비자를 위해 `config_revision` 을 남긴다. 이제 **실행 중인** revision 을 가리킨다.

**구현이 설계보다 낫다.** 설계는 "무엇이 등록됐나"만 물었는데 구현은 **"등록된 것이 실제로 올라왔나"**까지 답한다.

### 그래서 D-011 의 질문이 하나 늘어난다

| 질문 | |
|---|---|
| **`registered_ids` 를 추가할 것인가** | 설계에만 있다. **UI 가 그걸 필요로 하는지 확인 안 됨** |
| **버전 이름을 맞출 것인가** | `1.1` vs `introspection.v3` |

`[미확보]` **UI 가 실제로 무엇을 읽는지 확인하지 않았다.** `packages/acop_composer_ui/` 를 봐야 안다.

## 관계

- [D-006](D-006-composer-ownership.md) — Composer 소유는 sample
- [D-007](D-007-central-config-store.md) — 중앙 설정 저장소
- [sample/composer/design-gap.md](../../final_project_sample/wiki/composer/design-gap.md) — 항목 11개 대조
- 원본: `program/plan/A-COP_Composer_v3_불일치_해소안.md`
