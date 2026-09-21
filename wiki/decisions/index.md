---
type: guide
title: Decisions
description: 되돌리려면 근거가 필요한 선택들. 기각한 대안도 함께 기록한다
status: draft
domain: neutral
domain_note: 결정 목록이다. 개별 결정의 도메인은 각 문서가 말한다
---

# Decisions

**왜 그렇게 했는가**를 남기는 곳이다.

문서가 없으면 나중에 누군가 코드만 보고 "왜 이렇게 했지, 고쳐야겠다" 하면서 되돌린다. 특히 에이전트가 그런다. 그래서 **기각한 대안을 함께 적는다.**

## 무엇이 여기 오는가

| 온다 | 안 온다 |
|---|---|
| 되돌리려면 근거가 필요한 선택 | 명백한 구현 선택 |
| 대안이 실제로 있었던 것 | 대안이 없던 것 |
| 여러 저장소에 영향 | 한 파일 안에서 끝나는 것 |
| 나중에 "왜 안 했지"가 나올 것 | 조사 자료 (→ `research/`) |

**조사와 결정을 구분한다.** 알아본 것은 `research/`, 정한 것은 여기다. 결정 문서가 조사 문서를 `sources`로 참조한다.

## 목록

| ID | 결정 | 상태 | 영향 |
|---|---|---|---|
| [D-001](D-001-payment-ownership.md) | 결제 실행은 검증 쇼핑몰이 소유한다 | draft | cs, 검증 쇼핑몰 |
| [D-002](D-002-graph-store-gate.md) | Graph Store는 채택 게이트 통과 시에만 | draft | cs |
| [D-003](D-003-message-broker.md) | Message Broker는 in-process queue | draft | cs |
| [D-004](D-004-self-hosting-rationale.md) | 자체호스팅은 원가가 아니라 규제 논거 | draft | 사업·제품 |
| [D-005](D-005-write-gate.md) | **쓰기 권한을 여는 전제 조건 — 방어 7층** | draft | cs 전체 |
| [D-006](D-006-composer-ownership.md) | Composer 는 sample 이 만들고 UI 가 가져다 쓴다 | draft | sample·UI |
| [D-007](D-007-central-config-store.md) | 중앙 설정 저장소 (direct/central 2모드) | draft | Composer·배포 |
| [D-008](D-008-review-spam-out-of-scope.md) | 가짜 리뷰 분류는 제품 기능으로 안 낸다 | draft | VOC·데이터 |
| [D-009](D-009-recommendation-scope.md) | 추천 기능은 vision 으로 미룬다 | draft | 제품 범위 |

## 결정 문서 골격

```markdown
## 맥락           어떤 상황에서 이 판단이 필요했는가
## 결정           한 문장
## 선택지와 이유   표. 채택 여부와 이유
## 결과           무엇이 바뀌는가. 무엇을 못 하게 되는가
## 근거           [실측] 코드 위치 · [외부] 출처
```

**"결과"에 "무엇을 못 하게 되는가"를 반드시 쓴다.** 결정은 항상 무언가를 포기하는 것이고, 그걸 안 적으면 나중에 왜 막혔는지 모른다.

## 번호

`D-<3자리>-<주제>.md`. 번호는 재사용하지 않는다. 폐기된 결정도 번호를 유지하고 `status: deprecated`로 바꾼다.

## 미결정

아직 답이 없는 것. 정해지면 여기로 온다.

| 항목 | 무엇이 필요한가 | 어디 |
|---|---|---|
| 가격 정책 | 오류 1건당 손실 실측 | [../business/pricing.md](../business/pricing.md) |
| 자체호스팅 채택 | 3B 추론 처리량·정확도 실측 | [../business/infrastructure-cost.md](../business/infrastructure-cost.md) |
| ~~환불 계산 전환 시점~~ | **대상이 사라졌다** — 도메인이 여행으로 바뀌어 쇼핑몰 조치안이 실행될 일이 없다. 여행 쪽 대응(위약금 규정을 어디까지 신뢰하나)은 미정 | [D-001](D-001-payment-ownership.md) |
| 음성 채널 | 별도 원가 산정 | [../product/scope.md](../product/scope.md) |

## 인접 영역

- [../research/index.md](../research/index.md) — 결정의 재료가 된 조사
- [../product/index.md](../product/index.md) — 제품 결정이 여기서 나온다
- [../log.md](../log.md) — 결정이 추가된 시점
## [2026-09-03 추가]

| ID | 무엇 | 상태 |
|---|---|---|
| [D-010](D-010-deferral-scoring.md) | **승인 대기를 실패로 셀 것인가** | **미결.** 코드에 규칙만 넣고 껐다 |
| [D-011](D-011-composer-v3-gap.md) | Composer v3 설계와 구현 중 무엇을 맞추나 | **결정 (2026-09-06).** `[정정 2026-09-10]` 「미결·질문 6개」로 적혀 있었다 |
| [D-012](D-012-cutover-timing.md) | **전환은 중간발표 후에 한다** | **완료 — 앞당겨 실행됐다.** 2026-09-15 이후로 잡았으나 사용자 호출로 **2026-09-07** 에 243개 이동(`d976932`) |
| [D-013](D-013-declarative-team.md) | **Team 을 코드가 아니라 선언으로 만든다** | **결정.** 네 방식 중 셋을 기각 |

## [2026-09-06 추가]

| ID | 무엇 | 상태 |
|---|---|---|
| [D-014](D-014-judge-rebaseline.md) | **judge 를 v1 에서 v3 로 바꾼다** | **결정·시행.** v1 의 `policy_grounding` 이 분산 0 인 상수였다 |

## [2026-09-09 추가] — 도메인 교체가 드러낸 것 둘

| ID | 무엇 | 상태 |
|---|---|---|
| [D-015](D-015-implementation-catalog.md) | **구현 카탈로그를 손으로 유지하지 않는다** | **미결.** 사용자가 "UI 에서 관리 가능하게" 방향 지시(09-09). 갈래 넷 중 ④(배포된 `app/modules/` 스캔) 권고 + UI 화면 셋 |
| [D-016](D-016-scope-narrowing-reasons.md) | **도시와 언어는 좁히는 이유가 다르다** | **결정 (09-09).** 도시는 검증 주장의 범위, 언어는 책임 경계 — 번역은 고객 에이전트 몫 |

