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

## 관계

- [D-006](D-006-composer-ownership.md) — Composer 소유는 sample
- [D-007](D-007-central-config-store.md) — 중앙 설정 저장소
- [sample/composer/design-gap.md](../../final_project_sample/wiki/composer/design-gap.md) — 항목 11개 대조
- 원본: `program/plan/A-COP_Composer_v3_불일치_해소안.md`
