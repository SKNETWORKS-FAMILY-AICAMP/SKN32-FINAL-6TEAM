---
type: contract
title: 도메인을 갈아 끼울 때 무엇을 바꾸고 무엇을 두나
description: 11행 체크리스트가 "무엇이 Core인가"의 정본이다. 이 목록이 sample 이 혼자 서는 근거다
status: draft
tags: [architecture, contract]
domain: neutral
domain_note: 무엇을 갈아 끼우나를 정하는 계약이다. 두 도메인을 대조한다
---

# 도메인을 갈아 끼울 때

`[실측]` 원본은 `final_project_cs/wiki/records/handoff/10_도메인_교체_가이드.md`.

**이 문서가 cs 쪽에 없었다.** sample 에는 [domain-swap.md](../../final_project_sample/wiki/quality/domain-swap.md) 가 있는데 cs 에는 대응이 없었다.

★**이 문서가 "도메인이 또 바뀌어도 이어서 작업할 수 있는가"의 정본이다.** 교체를 실제로 두 번 했다.

| 언제 | 무엇에서 무엇으로 | 이 문서가 잡았나 |
|---|---|---|
| 2026-08-18 | 가상 SaaS(구독·결제) → 온라인 커머스 | 11행 목록이 이때 만들어졌다 |
| **2026-09-08** | 커머스 → **여행** | **부분만.** 아래 「바꾸는 것」 3·4·5·7 이 빠져 있어 이번에 더했다 |

**교체할 때마다 이 문서를 갱신한다.** 갱신하지 않으면 다음 교체에서 같은 것을 또 빠뜨린다 — 이번이 그랬다.

## 바꾸는 것 — 순서가 있다

```
1. 도메인 테이블   2. 대조 선언   3. 분류 라벨
4. Context Broker 적재분         5. Action 목록
6. Agent Team      7. Composer 소재
8. 코퍼스          9. 평가 데이터  10. 시연
```

**순서를 지켜야 한다.** 대조 선언 없이 Team 을 만들면 [evidence-check](actions/evidence-check.md) 가 전부 거부한다.

★**[2026-09-09] 3·4·5·7이 여행 교체에서 추가됐다.** 그전 목록은 여섯 단계(테이블·대조 선언·Team·코퍼스·평가·시연)였는데, **실제로 갈아 끼운 것 넷이 빠져 있었다** — 계획서 v11 §5-A가 "코어에서 바뀌는 것"으로 넷을 따로 적었고 이 문서에는 그 항목이 없었다. `분류 라벨`·`Action` 은 이 문서에 등장 횟수 0이었다.

| 추가된 단계 | v9 (쇼핑몰) | v10 (여행) |
|---|---|---|
| 3. 분류 라벨 | 주문·배송·반품·교환·기타 | 일정 제출 / 사건 신고 / 확인 요청 / 조정 거부 / 그 외 |
| 4. Context Broker 적재분 | 주문·배송 정보 | 여행 상태(최신 일정·잠긴 예약·필수 조건·다음 확인 시점) |
| 5. Action 목록 | 주문 조회·배송 조회·환불 실행 | 장소·운영 조회 / 이동 시간 조회 / 기상 조회 |
| 7. Composer 소재 | 한국어 CS 문구 | **한국어 통지 문구를 여행 어휘로** `[결정 2026-09-10]` |

★**4번이 헷갈리는 자리다.** 아래 11행은 "Context Broker 를 안 바꾼다"고 적는데 여기서는 바꾼다고 적는다. **둘 다 맞다** — 예산·절삭 규칙·`degraded` 신호라는 **기제**는 안 바뀌고, 무엇을 싣는지라는 **적재분**이 바뀐다. 기제와 적재분을 같은 말로 부르면 다음 교체에서 한쪽을 빠뜨린다.

### 1. 도메인 테이블

```
app/infrastructure/db/migrations/002_domain_commerce.sql   ← [정정 2026-09-10] customer_ops 로 적혀 있었다
app/infrastructure/db/migrations/010_domain_travel.sql     ← 여행 (작업 트리)
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

`[실측]` `wiki/records/handoff/09_Composer_GUI_계약.md` §2-4 — **끌 수 없는 컴포넌트 9종.**

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

### ★ [2026-09-09] 가드가 여행 어휘를 모른다

`[실측]` `tests/architecture/test_basement_is_domain_free.py` 의 `DOMAIN_WORDS`.

```python
DOMAIN_WORDS = (
    # 구독·결제 (현재 sample 도메인)
    "payment", "subscription", "entitlement", "refund", "invoice",
    # 커머스 (복사본이 쓸 도메인)
    "order_id", "line_item", "shipment", "sku", "cart",
)
```

**여행 어휘가 하나도 없다.** `[정정 2026-09-10 작업 트리]` **지금은 다섯이 들어갔다** — `booking`·`itinerary`·`lodging`·`supplier_booking`·`traveller`(`tests/architecture/test_basement_is_domain_free.py:47`). `[실측 git]` git 에는 아직 없다. `trip`·`itinerary`·`booking`·`reservation`·`activity` 가 `app/core/` 에 들어가도 이 가드는 통과한다. 여행 Team 구현이 시작되면 그때가 가장 새기 쉬운 시점이다.

★**이 목록은 "지금 도메인"이 아니라 "새면 안 되는 어휘 전부"다.** 도메인을 바꿀 때 옛 어휘를 지우지 않고 **더한다** — 그래야 되돌아갔을 때도 잡힌다. 목록 추가는 코드 담당 몫으로 [../../wiki/delivery/open-items.md](../../wiki/delivery/open-items.md) 에 올렸다.

`[실측]` `test_engine_serves_another_domain.py` 는 **쇼핑몰 선언으로** 엔진을 돌려 도메인 무관을 증명한다. 여행으로 갈아탄 지금 이 테스트는 **오히려 강해졌다** — 우리가 만들고 있지 않은 도메인으로 검증하기 때문이다. 여행으로 바꾸지 않는다.

## 이 문서가 생긴 이유

`[실측]` 원본 §4. 2026-08-16에 `app/core/verification.py`가 **구독·결제 어휘를 Core에 박고 있었다.** 그 상태로 쇼핑몰에 복사했다면 `order_id`가 "확인 불가 → 자동 거부"에 걸렸을 것이다 — 그 도메인의 가장 중요한 식별자가 basement의 거부 목록에 있는 정반대 상황이다.

원인은 계획서 v7 §9-E 표가 `payment_id`·`amount`를 **예시로** 든 것을 스펙으로 읽은 것이었다.

> 계획서의 예시는 그 계획서의 도메인일 뿐이다. **basement에는 메커니즘만 올라가고, 어휘는 선언으로 내려간다.**

## 원본 가이드(`handoff/10`)에서 낡은 것

`[실측]` 2026-09-06 대조. 원칙과 11행 표는 맞고, **구체 값이 옛 도메인이다.**

| 원본 | 지금 |
|---|---|
| §1-1 "현재 도메인 테이블 4개 = `subscriptions`·`payments`·`entitlements`·`incidents`" | **두 판 낡았다.** 그다음이 `orders`·`order_items`·`shipments`·`returns`(쇼핑몰)였고, 2026-09-08 여행 교체로 그것도 옛 도메인이 됐다. 여행 테이블은 아직 안 만들었다 `[미확보]` — 새 집합체는 **Trip** 하나다(v11 §4-B) |
| §1-3 Team 파일 `{billing,technical,feedback}.py` | 퇴역. 쇼핑몰 여섯 Team도 MVP 경로에서 빠졌고, 여행 Team 넷은 명세만 있다(`[정정 2026-09-10]` 지금 작업 트리에는 코드가 있고 여섯이 등록됐다 — git 에는 없다) → [teams/index.md](teams/index.md) |
| §1-4 "25문서 / 300청크" | **306청크** ([context/rag-retrieval.md](context/rag-retrieval.md)) |
| §1-5 `attack_fixtures.jsonl` 15건 | **17건** (atk-16·17 추가) — `[2026-09-10]` 지금은 **23건**(작업 트리·git 같다) |
| §0 "예외 목록은 3개를 넘을 수 없다" | 지금도 맞다 — `INV-CS-ARCH-004`가 크기를 검사한다 |

**"무엇을 갈아 끼우나"의 목록은 살아 있고 "지금 뭐가 들어 있나"는 낡았다.** 이 문서는 후자를 옮기지 않는다 — 현재 값은 각 영역 문서가 정본이다.

## 어느 문서를 다시 쓰나

`[실측 2026-09-09]` 이 문서는 **무엇을 갈아 끼우나**를 정하고, 그게 **어느 문서에 걸리나**는 문서마다 front matter 의 `domain:` 이 말한다. 규칙은 [../../wiki/governance/domain-axis.md](../../wiki/governance/domain-axis.md).

```bash
python program/scripts/check_wiki.py --domain travel
```

★**2026-09-08 교체 때는 이 표시가 없어서 grep 으로 훑었고, 낱말이 안 든 문서를 놓쳤다** — `wiki/architecture/pack-model.md` 의 구조 표가 `Commerce Ops Pack` 인 채로 하루 넘게 남아 있었다. 다음 교체 때는 목록으로 나온다.

`[실측 2026-09-09]` 지금 값 — 비-기록 문서 252개 중 `travel` 19 · `neutral` 169 · `commerce` 64(그중 **이유 없는 30개가 판올림을 못 따라간 것**).

## 관계

- [../../wiki/governance/domain-axis.md](../../wiki/governance/domain-axis.md) — **문서 단위 교체 대상 목록**
- [../../final_project_sample/wiki/quality/domain-swap.md](../../final_project_sample/wiki/quality/domain-swap.md) — sample 쪽 같은 문서
- [../../wiki/architecture/core-vs-team.md](../../wiki/architecture/core-vs-team.md) — 경계 규칙
- [data/migrations.md](data/migrations.md) — 마이그레이션 순서
- [actions/evidence-check.md](actions/evidence-check.md) — 대조 선언
