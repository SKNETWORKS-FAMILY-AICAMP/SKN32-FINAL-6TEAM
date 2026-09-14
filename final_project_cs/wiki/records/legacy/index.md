# 레거시 — 지난 도메인의 문서

`[실측 2026-09-10]` **여기 있는 문서는 고치지 않는다.** `wiki/records/` 아래이므로 형식·크기·링크 규칙이 면제되고, 깨진 링크는 집계만 된다.

## 왜 옮겼나

2026-09-08 에 도메인이 **커머스(쇼핑몰) CS → 여행 CS** 로 교체됐고, 2026-09-10 에 **커머스 코드가 작업 트리에서 제거됐다.**

`[실측 2026-09-10]` **「삭제」의 범위** — `app/modules/customer_ops/` 의 파일들이 작업 트리에 없고 **git 에는 아직 있다**(커밋 전, 다른 세션의 진행 중 작업). `feedback.py`·`verification_policy.py` 는 삭제가 아니라 `app/modules/travel_ops/` 로 **이동**했다.

그 결과 커머스 Team 문서 일곱이 **없는 코드를 현재형으로 설명하는 상태**가 됐다. 살아 있는 `wiki/teams/` 에 두면 읽는 사람이 지금 동작으로 읽는다.

★**지우지 않는 이유는 둘이다.**

| | |
|---|---|
| **판정의 이유가 도메인 무관이다** | 승인 경계·Mock 취급·근거 대조 같은 결정이 이 문서들에 적혀 있고, 여행 Team 이 같은 문제를 다시 만난다 |
| **도메인이 되돌아갈 수 있다** | 되돌아가면 이 판정을 다시 하게 되고, **그걸 다시 논의하지 않으려고** 기록을 남긴다 |

## 무엇이 있나

### `teams/` — 커머스 Team 문서 일곱

| 문서 | 무엇이었나 | 코드 |
|---|---|---|
| `voc-store-manager.md` | 집계·급증 탐지. **v8 재판정으로 이미 껍데기였다** | 제거됨 |
| `response-review.md` · `response-review-design.md` | 응답 생성과 검토를 다른 주체가 한다 | 제거됨. **원칙은 여행 Team 내부 규칙으로 흡수**(v11 §5) |
| `return-refund.md` | 취소 기한·위약금율 판정. **Mock 유지로 결정됐다**(2026-09-06) | 제거됨. 뼈대를 [activity](../../teams/activity.md) 가 물려받았다 |
| `fulfillment-logistics.md` | 구간·경로 판정. **`business_subject` 를 옳게 쓰는 유일한 Team 이었다** | 제거됨. 뼈대를 [mobility](../../teams/mobility.md) 가 물려받았다 |
| `procurement-order.md` | 주문·금액·승인 검증 | 제거됨 |
| `catalog-verification.md` | 외부 원장과 대조. **A2A Remote** | 제거됨. 자리를 **Place Verification** 이 물려받았다 |

★**뼈대를 물려받았다는 말은 구조를 베꼈다는 뜻이다.** 판정 규칙과 도메인 데이터는 전량 신규다(v11 §0-2).

## 이 문서를 읽을 때

| | |
|---|---|
| **현재형 문장을 지금 사실로 읽지 않는다** | "등록돼 있다"·"돌고 있다"는 **그때** 그랬다는 뜻이다 |
| 인용된 코드 경로는 대개 없다 | `app/modules/customer_ops/*` 는 2026-09-10 에 작업 트리에서 제거됐다 |
| 판정의 **이유**는 아직 유효할 수 있다 | 그 이유를 여행으로 옮긴 것은 [scope-verdicts.md](../../../../wiki/delivery/scope-verdicts.md) 가 표로 적었다 |

## 관계

- [../../teams/index.md](../../teams/index.md) — 지금 Team 목록
- [../../domain-swap.md](../../domain-swap.md) — 무엇을 갈아 끼우고 무엇을 안 끼우나
- [../../../../wiki/governance/domain-axis.md](../../../../wiki/governance/domain-axis.md) — 어느 문서가 도메인에 묶여 있나
