---
type: contract
title: 도메인을 갈아 끼울 때 무엇을 바꾸고 무엇을 두나
description: 11행 체크리스트가 "무엇이 Core인가"의 정본이다. 이 목록이 sample 이 혼자 서는 근거다
status: draft
tags: [architecture, contract]
---

# 도메인을 갈아 끼울 때

`[실측]` 원본은 `final_project_cs/docs/handoff/10_도메인_교체_가이드.md`.

**이 문서가 cs 쪽에 없었다.** sample 에는 [domain-swap.md](../../final_project_sample/wiki/quality/domain-swap.md) 가 있는데 cs 에는 대응이 없었다.

## 바꾸는 것 — 순서가 있다

```
1. 도메인 테이블   2. 대조 선언   3. Agent Team
4. 코퍼스          5. 평가 데이터  6. 시연
```

**순서를 지켜야 한다.** 대조 선언 없이 Team 을 만들면 [evidence-check](actions/evidence-check.md) 가 전부 거부한다.

### 1. 도메인 테이블

```
app/infrastructure/db/migrations/002_domain_customer_ops.sql
  → 002_domain_<your>.sql
```

`[실측]` **`001_schema.sql`(Core 14 테이블)은 손대지 않는다.**

> `migrate.py` 가 `sorted(glob("*.sql"))` 로 전부 읽으므로 **파일만 두면 적용된다.**

**파일 이름의 번호가 순서다.** → [data/migrations.md](data/migrations.md)

### 2. 대조 선언

```python
CUSTOMER_OPS_POLICY = VerificationPolicy(
    references={"order_id": "orders", "shipment_id": "shipments"},
    quantities=(QuantityRule("refund_amount", "order_id", "total_cents", scale=Decimal(100)),),
    opaque=frozenset({"coupon_id"}),      # 아직 대조 수단이 없는 것
    ignored=frozenset({"reason", "memo"}),
)
```

`[실측]` **선언에 없는 필드는 자동으로 거부된다.**

**이게 [DoD-18 결함 A](quality/evidence.md) 의 원인이었다** — seed 가 표시용 `evidence` 를 넣었는데 `ignored` 에 없어서 승인이 409 로 막혔다.

## ★ 갈아 끼우지 않는 것 — 11행

**이 표가 "무엇이 Core 인가"의 정본이다.**

| 무엇 | 왜 |
|---|---|
| Case lifecycle · `transition_case()` | **상태 변경의 단일 진입점.** 도메인 무관 |
| 계약 모델 (`contracts.py`) | `extra='forbid'` · evidence 의무 |
| Team Registry · `allowed_tools` 강제 | |
| Context Broker (12,000 토큰) | |
| **대조 규칙 엔진** (`core/verification.py`) | **어휘는 선언에서 온다** |
| Controller · WAIT/RESUME · 승인 | |
| Outbox (원자성 · dedupe · `unknown`) | |
| Ports 6종 + `project.yaml` 조립 | |
| 운영 UI 4화면 · Composer GUI | **상태 색·근거 표시는 도메인 무관** |
| A2A (Card · input-required · 취소 · 인증) | |
| 방어 지표 5종 (`eval/defense_metrics.py`) | **분모 규칙은 도메인 무관** |

### 같은 목록이 Composer 에도 있다

`[실측]` `docs/handoff/09_Composer_GUI_계약.md` §2-4 — **끌 수 없는 컴포넌트 9종.**

| 컴포넌트 | 왜 선택지가 아닌가 |
|---|---|
| Case lifecycle · `transition_case()` | 상태 변경의 단일 진입점 |
| Contract models | **Team 계약 그 자체** |
| Team Registry | capability 해석과 라우팅 |
| Context Broker | 예산과 `degraded` 신호 |
| DB repository / session | **Source of Truth** |
| Outbox publisher | 트랜잭션과 이벤트 발행의 원자성 |
| Case service | run/resume 중복 실행 방지 |
| Controller | 실행 루프 |
| Settings / guardrails | 설정의 단일 출처 |

> **이것들을 끄면 A-COP 이 아니게 된다.**

**두 목록이 거의 같다.** 위 11행은 "도메인을 바꿔도 안 바뀌는 것"이고 이 9종은 "사용자가 끌 수 없는 것"이다.

`[실측]` **UI 처리 규칙도 정해져 있다.**

> 화면에 **읽기 전용으로 띄우되 "구성기에서 제거할 수 없습니다"를 함께 적어** 토글로 오해하지 않게 한다.

**숨기지 않는다.** 안 보이면 "왜 없지"가 되고, 토글로 보이면 "왜 안 눌리지"가 된다.

### 이 목록이 sample 이 혼자 서는 근거다

`[실측]` **11행 중 도메인 어휘가 필요한 것이 하나도 없다.**

**그래서 `final_project_cs` 가 릴리스로 나가도 `final_project_sample` 은 그대로 돈다.** → [D-012](../../wiki/decisions/D-012-cutover-timing.md)

**다섯 번째 줄이 그 증거다** — 대조 엔진은 어휘를 **선언에서 받는다.** `test_engine_serves_another_domain.py` 가 그걸 강제한다.

## 복사 후 첫 검증

```bash
python -m app.infrastructure.db.migrate
python -m pytest tests/architecture -q
python -m pytest -q
```

`[실측]` **아키텍처 테스트가 실패하면 그 파일을 `app/modules/` 로 옮기거나 선언으로 뺀다.** basement 에 도메인 어휘가 샌 것이다.

## 관계

- [../../final_project_sample/wiki/quality/domain-swap.md](../../final_project_sample/wiki/quality/domain-swap.md) — sample 쪽 같은 문서
- [../../wiki/architecture/core-vs-team.md](../../wiki/architecture/core-vs-team.md) — 경계 규칙
- [data/migrations.md](data/migrations.md) — 마이그레이션 순서
- [actions/evidence-check.md](actions/evidence-check.md) — 대조 선언
