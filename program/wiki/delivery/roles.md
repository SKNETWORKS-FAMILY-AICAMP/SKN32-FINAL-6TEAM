---
type: plan
title: 역할과 소유 경계
description: 6명을 코어 2·모델 3·검증&프론트 1로 배치한다. 소유가 겹치면 이중 장부가 된다
status: draft
tags: [release]
owners: [human:미배정]
---

# 역할과 소유 경계

`[실측]` v8 §16에서 이관.

## 배치

**6명을 코어 2 · 모델 3 · 검증&프론트 1로 배치한다.**

**사람의 담당 경계는 코드의 책임 경계와 같을 필요가 없다.** 한 사람이 수직 기능 하나를 끝까지 본다.

## 담당과 담당하지 않는 것

| 담당 | 인원 | 역할 | **담당하지 않는 것** |
|---|---|---|---|
| **코어 1** — Case Runtime & Coordination | 1 | Case·lifecycle·Shared State·CAS·Controller·Top-Level LangGraph·Registry·`TeamExecutorPort`·Message Broker 정책. **인라인 분류의 실행·실패 처리·상태 전이**와 Feedback Analytics 집계 배치 | 외부 인증, Tool 실행, Team 내부 로직, **분류 라벨 어휘와 프롬프트 품질** |
| **코어 2** — Access & Action Platform | 1 | Gateway·API/MCP·A2A Adapter·Tool/Action·approval·idempotency·audit | Case routing 판단, Team 내부 로직, **분류 실행** |
| **모델** — Agent Team Module | 3 | Team 내부 graph/agent·프롬프트·retrieval·rerank·memory 정책·모델 선택과 라우팅·`TeamResult` 생성 규칙. **분류 라벨 어휘와 분류 프롬프트의 구현·품질** | Core 계약 변경, side effect 실행, **분류의 호출 시점과 실패 처리** |
| **검증 & 프론트** | 1 | **평가 harness·golden/holdout 관리·지표·통계·회귀·contract test 실행**, 운영 UI, observability, 통합 데모 | 업무 로직 구현 |

**"담당하지 않는 것" 열이 실제 경계다.** 무엇을 하는지보다 무엇을 안 하는지가 충돌을 막는다.

### 분류가 셋으로 갈려 있다

`[실측]` 인라인 분류 하나가 세 담당에 걸쳐 있다. **의도된 분할이다.**

| 무엇 | 누가 |
|---|---|
| 언제 부르고 실패하면 어떻게 하나 | **코어 1** |
| 어떤 라벨을 쓰고 프롬프트를 어떻게 쓰나 | **모델** |
| 분류 실행 자체 | 코어 2 아님 |

**"실행 시점"과 "품질"을 나눈 것이다.** 분류가 틀리면 모델 담당, 분류 실패를 조용히 넘기면 코어 1 담당이다.

## ★ 검증이 앞이고 프론트가 뒤다

**이 1명의 1순위는 화면이 아니라 "좋아졌다"를 숫자로 증명하는 것이다.**

UI는 그 증명을 사람이 볼 수 있게 만드는 수단이다. **화면을 먼저 만들고 평가를 뒤로 미루지 않는다.**

## 모델 3명은 Team 수에 고정되지 않는다

Team은 Registry 등록형이라 개수가 늘 수 있다.

| 축 | 성격 |
|---|---|
| VOC & Store Manager · Response Generation & Review | **CS Pack 고정 축** |
| Procurement + Order & Payment · Fulfillment & Logistics | 검증 쇼핑몰 연계 축. 진행 범위에 따라 배치가 달라진다 |
| Catalog & Verification | A2A Remote |

**6명 팀 전체가 이 네 축에 고정되는 것은 아니다.**

**Team 하나가 무거우면 2명을 붙이고 가벼우면 한 사람이 둘을 본다.**

## ★ 소유 디렉터리 — 충돌 방지의 핵심

**두 스트림이 같은 파일을 쓰지 않는다.**

`[실측]` 이유가 명확하다.

> 쓰면 **마지막에 끝난 쪽이 이겨서 조용히 덮어쓴다.**

담당을 역할이 아니라 **디렉터리로 긋는다.** 사람 이름으로 나누면 경계가 흐려진다.

| 스트림 | 소유 디렉터리 — 여기만 쓴다 |
|---|---|
| **Core** | `app/core/**` `app/domain/**` `app/application/{case_service,controller}.py` `app/infrastructure/messaging/**` `tests/contract/**` `docs/handoff/**` `config/guardrails.yaml` |
| **DB** | `app/infrastructure/db/**` `scripts/seed.py` |
| **API** | `app/presentation/api/**` `app/presentation/security.py` `tests/security/**` |
| **Team** | `app/modules/customer_ops/**` `app/tools/**` `prompts/**` |
| **RAG** | `knowledge/**` `app/infrastructure/rag/**` |
| **VOC** | `app/modules/customer_ops/feedback.py` `app/application/feedback_job.py` |
| **Eval** | `eval/**` `prompts/judge/**` |
| **UI** | `app/presentation/ui/**` |

`[실측]` 이 원칙이 `acop_dojo`의 트랙 경계에도 그대로 쓰인다 — **"경계는 사람이 아니라 디렉터리로 긋는다."**

### 왜 Core를 계약 테스트와 함께 묶는가

`[실측]` 원문의 근거가 날카롭다.

> `transition_case()`·낙관적 동시성·outbox 원자성·ContextPack 예산 절삭은 **틀려도 테스트가 초록으로 나오는 종류의 코드**다 (경합·부분 실패·토큰 경계).

**그래서 계약 테스트를 만든 쪽과 통과시킨 쪽을 분리한다.** Core와 `tests/contract/`를 같은 사람이 쥔다.

## DB 소유

`[실측]` 테이블 단위로 소유가 갈린다.

| 소유 | 테이블 |
|---|---|
| **코어 1** | `customer_cases` `case_events` `shared_state` `agent_runs` `team_tasks` `outbox` |
| **코어 2** | `action_requests` `action_approvals` `audit_logs` external client/auth |
| **공통** | `tenants` `customers` knowledge/prompt/LLM 기록 |

SQLAlchemy 설정과 Alembic revision은 **공동 합의**다.

## ★ Alembic은 단일 브랜치다

**마이그레이션이 갈리면 병합이 지옥이 된다.**

```
revision 생성 전 main 을 rebase 한다
CI 에서 upgrade head → downgrade -1 → upgrade head 를 검증한다
```

**되돌릴 수 있는지까지 검사한다.** 앞으로만 가는 마이그레이션은 사고 때 못 쓴다.

## 경계를 넘는 작업

혼자 못 정하는 것들.

| 작업 | 누가 함께 |
|---|---|
| Team 계약 변경 | 코어 1 + 모델 3명 |
| 스키마 변경 | 소유 담당 + 영향받는 쪽 |
| 승인 경계 조정 | 코어 2 + 기획 |
| 지표 정의 변경 | 검증 + 기획 |
| 저장소 간 계약 | 양쪽 저장소 소유자 |
| **Alembic revision** | **공동 합의** |

계약 변경은 `contract_version` 상향과 회귀 테스트를 함께 한다.

## 고정점

**1W 금요일은 Contract Freeze Day다.** → [timeline.md](timeline.md)

## 검증 쇼핑몰과의 경계

`[미확보]` 협의 창구가 정해지지 않았다.

| 우리가 주는 것 | 받아야 하는 것 |
|---|---|
| Action 실행 요청 | 결제 구성 스냅샷 |
| 근거 대조 결과 | 쇼핑몰이 계산한 환불 예정액 |

→ [../decisions/D-001-payment-ownership.md](../decisions/D-001-payment-ownership.md)

## 관계

- [timeline.md](timeline.md) — 주차별 배분
- [dod.md](dod.md) — 완료 기준
- [../governance/review-policy.md](../governance/review-policy.md) — 문서 소유
- [../architecture/repository-map.md](../architecture/repository-map.md) — 저장소별 소유
