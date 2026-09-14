---
type: contract
title: Response Review 내부 설계
description: GEN→REV 흐름과 검증 4항목. 결정론 검사를 LLM 검사보다 먼저 돌린다
status: draft
tags: [agent, contract, evaluation]
owners: [human:미배정]
domain: commerce
domain_note: v10 §0-2 가 MVP 경로에서 제외한 커머스 Team 이다. 2026-09-09 에 config/project.yaml 등록에서 빠졌고 소스만 app/modules/customer_ops/ 에 남아 있다
---

# Response Review 내부 설계

`[실측]` v8 §8-B에서 이관. **DoD-29의 검증 대상이다.**

## 하나의 Team이다

**GEN과 REV를 별도 Team으로 분리하지 않는다.** 새 컴포넌트를 추가하는 것도 아니다.

**재시도 루프가 모듈 내부에서 돈다.** Controller가 관여하지 않는다.

## 슬롯 자격

| 축 | |
|---|---|
| capability | 응답 생성·검증 |
| 지식 | 톤 프로파일·금칙 표현·검증 규칙 |
| 입력 | `TeamTask` |
| side effect | **없다** |

## 내부 흐름

```
톤 결정 (규칙)  →  GEN 초안  →  REV 검증  →  완료
                       ↑            │
                       └────────────┘  최대 3회 재시도
```

## ★ REV 4항목 — 셋은 결정론이다

| # | 검사 | 방법 |
|---|---|---|
| 1 | **과잉약속** | 금칙어 사전 — **결정론** |
| 2 | **근거 인용** | `refund_amount`·`policy_ref` 값 대조 — **결정론** |
| 3 | **개인정보** | 정규식 — **결정론** |
| 4 | 톤 | LLM 판정 |

**LLM은 넷 중 하나에만 쓴다.**

### 결정론 검사를 먼저 돌린다

`[실측]` v7.1 개정 사항이다.

> 결정론 검사를 LLM 검사보다 **먼저** 실행한다. **자기채점 방지 논거는 LLM 판단에만 해당하고 결정론 검사에는 해당하지 않는다.**

**같은 모델이 쓰고 같은 모델이 채점하면 안 된다**는 원칙이 있지만, 정규식과 값 대조는 모델이 아니다. 그래서 먼저 돌려도 된다.

**싸고 확실한 것부터 거른다.**

### 톤은 재시도 사유가 아니다

**톤은 사람 라벨이 필요하므로 재시도 사유에서 제외하고 경고로만 남긴다.**

톤 판정이 LLM이라 틀릴 수 있는데, 그걸로 재시도를 돌리면 **틀린 판정 때문에 3회를 소모한다.**

## 지표

| 지표 | 목표 |
|---|---|
| 1차 통과율 | — |
| 에스컬레이션 비율 | **5% 이하** |
| 반려 사유 분포 | — |
| **개인정보 노출율** | **0%** |

**개인정보 0%가 유일한 절대 목표다.**

## ★ Human Approval과 대상이 다르다

**둘을 헷갈리면 안 된다.**

| | 무엇을 묻나 | 언제 |
|---|---|---|
| **Human Approval** | 이 **조치를 실행**해도 되는가 | 고위험 Case |
| **응답 검증 (REV)** | 이 **문장을 보내**도 되는가 | **모든 Case** |

**REV는 전건이다.** 승인은 고위험만이다.

→ [../actions/approval.md](../../../actions/approval.md)

## 계약을 바꾸지 않는다

`[실측]` `TeamResult`는 `ConfigDict(extra='forbid')`라 필드를 임의로 못 늘린다. **매핑으로 해결했다.**

| 설계 표기 | 계약 필드 |
|---|---|
| `final_response_text` | `answer` |
| `status` | `outcome` |
| `retry_count` | `decisions[]` |
| `review_history` | `decisions[]` |
| 반려 사유 | `warnings[]` |
| `escalation` | `outcome='escalated'` + `next_action` |

**계약을 바꾸면 `contract_version` 상향과 회귀 테스트가 함께 필요하다.** 그래서 안 바꿨다.

→ [team-contract.md](../../../teams/team-contract/index.md)

## 불변식

`[실측]` **DoD-29가 2026-09-01 평가 완료됐다**
(`final_project_cs/wiki/records/evidence/DoD-29_ResponseGenerationReview.md`).

검증한 것 셋.

```
GEN→REV 두 호출 흐름이 실제로 실행되는가 — 신규 테스트로 채움(기존 테스트는
  전부 tone_ok를 미리 박아 두 번째 호출을 건너뛰고 있었다)
REV 반려 시 재시도 상한이 적용되는가 — 기존 테스트로 이미 확인됨
개인정보가 섞인 응답을 REV 자체 검증이 차단하는가 — 기존 테스트로 이미 확인됨
```

→ [../../../wiki/delivery/dod.md](../../../../../wiki/delivery/dod.md)

## 관계

- [response-review.md](response-review.md) — manifest와 운영 이력
- [team-contract.md](../../../teams/team-contract/index.md) — `TeamResult` 매핑
- [../actions/approval.md](../../../actions/approval.md) — 승인과의 차이
- [../external/auth-boundary.md](../../../external/auth-boundary.md) — PII 마스킹
