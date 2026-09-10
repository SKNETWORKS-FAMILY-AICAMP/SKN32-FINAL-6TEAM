---
type: guide
title: A-COP 지식 허브
description: 중앙 허브의 8개 영역과 각 영역이 답하는 질문. 2026-09-08 도메인이 여행으로 바뀌었다
status: draft
domain: travel
domain_note: 판올림 이력을 싣는다. 두 도메인이 대조로 나온다
---

# A-COP 지식 허브

처음이면 [quickstart.md](quickstart.md)부터 본다.

여기는 **코드 커밋과 무관하게 움직이는 지식**만 둔다. 구현 세부는 각 코드 저장소의 `wiki/`에 있다.

## ★ [2026-09-08] 여행 판올림 — 이 wiki의 절반이 아직 쇼핑몰이다

도메인이 **커머스 CS → 여행 CS**로 바뀌었다(계획서 v10). 기준선은 `program/plan/A-COP_구현계획서_v11.md`다 — `[2026-09-10]` v11 이 여행 전환 결정(라우팅 두 축 · 멱등 키 대상 · 루프 둘 · DB 5표 교체)을 흡수했다. 무엇이 달라졌는지는 v11 §0-2A.

`[실측 2026-09-10]` 기록(`records/`)과 이관 스테이징(`_migration/`)을 뺀 허브 + cs **176문서 중 85개(48%)에 커머스 낱말이 남아 있다**(2026-09-09 에는 198 중 104 = 53% 였다). ★**남은 것 중 상당수는 남는 게 맞다** — 도메인 교체 가능성을 증명하는 대조군과 그때의 기록이다. 문서별 판정은 front matter 의 `domain` 축이 갖고 있다 → [governance/domain-axis.md](governance/domain-axis.md). 그중 37개는 1~2회 스치는 언급이고 67개는 구조가 쇼핑몰이다. 여행 낱말이 든 문서는 3개뿐이었다. 낱말로 센 값이라 **하한이다** — 그 말을 안 쓰면서 예시가 전부 주문인 문서는 안 잡혔다.

| 영역 | 여행에서 |
|---|---|
| `governance/` · `architecture/`의 경계 규칙 | **그대로 쓴다.** 도메인을 모르는 규칙이다 |
| `decisions/` | 코어 결정은 유효. D-001(결제 소유)처럼 쇼핑몰 전제인 것은 재판정 대상 |
| `product/` · `business/` · `evaluation/` 골든셋 | **교체 대상.** v11 §1·§8 |
| `delivery/` DoD | **29 → 22 → 24 → 25 → 26** 으로 움직였다(v11 §12 = **26항목**). 옛 29항목은 쇼핑몰 대상. ★**나흘 만에 네 번 바뀌었다** — `DoD-8` 같은 참조를 읽을 때 어느 판인지 본다 |

읽을 때 규칙 하나 — **도메인 사실이 기준선과 다르면 기준선이 맞다.** 기준선은 지금 **v11** 이다(2026-09-10 판올림). 「v10 이 맞다」고 적어 뒀던 것을 고쳤다 — **판이 올라가면 이 문장도 같이 낡는다.** 낡은 서술은 지우지 않고 그 시점 사실로 남긴다.

## 영역

### [product/](product/index.md) — 무엇을 만드는가
포지셔닝, 페인포인트, 페르소나, 범위, 용어.
"이게 왜 필요한가"에 답해야 할 때 여기부터. `[실측 2026-09-10]` **product/ 넷 다 여행으로 다시 썼다** — [scope](product/scope.md)·[positioning](product/positioning.md)·[problem](product/problem.md)·[personas](product/personas.md). ★**구매 결정자가 바뀐 것이 가장 큰 변화다** — 기업 CS 조직(B2B)에서 **여행팀 본인**(이용권)으로.

### [business/](business/index.md) — 얼마짜리인가
건당 원가, 인프라 비용, 시장 규모, 가격안.
`[실측]` 여기 적힌 사람 1건 4,100~4,846원 · A-COP 병행 **1,132원**은 **쇼핑몰 CS 상담 원가**다(`business/unit-economics.md` 와 맞췄다 — 1,133 으로 적혀 있었다). 여행은 팀당 이용권(7일·4인·서울 1도시, 가격은 v11 §11-A)이라 산식이 다르다 — v11 §1. 인바운드 손익 재계산은 `[미확보]`.

### [architecture/](architecture/index.md) — 어떻게 나뉘는가
시스템 경계, 저장소 관계, Core와 Team의 분리 기준, Pack 모델.
**경계만 다룬다.** 구현은 코드 저장소 wiki에 있다.

### [delivery/](delivery/index.md) — 언제 무엇을 내는가
일정, 마일스톤, DoD, 6명의 소유 경계.
`[실측]` DoD는 **v11 §12의 26항목**(자동 20 · 아키텍처 테스트 4 · 측정 2)이다. 이 영역의 29항목 서술은 쇼핑몰 기준이라 낡았다.

### [evaluation/](evaluation/index.md) — 무엇으로 증명하는가
지표와 산식, A/B/Proposed 프로토콜, 골든셋, Judge 루브릭.

### [research/](research/index.md) — 무엇을 알아봤는가
외부 조사와 비교 분석. **결정이 끝난 것은 여기 없고 `decisions/`에 있다.**

### [decisions/](decisions/index.md) — 왜 그렇게 했는가
되돌리려면 근거가 필요한 선택들. 기각한 대안도 함께 적는다.

### [governance/](governance/index.md) — 어떻게 쓰는가
문서 표준, front matter 규격, 근거 등급, 리뷰 정책.

## 코드 저장소

| 저장소 | 무엇이 있나 |
|---|---|
| [final_project_cs](../final_project_cs/wiki/index.md) | Core·Team 구현, 계약, 불변식, 평가 하네스 |
| [final_project_sample](../final_project_sample/wiki/index.md) | cs로 이식 확정된 계약만 |
| [datasets](../datasets/wiki/index.md) | 데이터셋 의미와 재생성 방법 |
| [acop_dojo](../acop_dojo/wiki/index.md) | 학습 도장 사용법 |

## 미결정

지금 답이 없는 것들. 정해지면 `decisions/`로 옮긴다.

| 항목 | 무엇이 필요한가 | 어디 |
|---|---|---|
| 가격 정책 | 오류 1건당 손실 실측 | [business/pricing.md](business/pricing.md) |
| 자체호스팅 채택 | 3B 모델 추론 처리량·정확도·지연 실측 | [business/infrastructure-cost.md](business/infrastructure-cost.md) |
| 검토·승인 1건 소요시간 | 내부 실험 | [business/unit-economics.md](business/unit-economics.md) |
| 음성 채널 | 별도 원가 산정 | [business/infrastructure-cost.md](business/infrastructure-cost.md) |
| ~~환불 계산 방식 전환 시점~~ | 쇼핑몰 전제라 여행에서는 해당 없음. D-001 재판정 대상 | [decisions/D-001-payment-ownership.md](decisions/D-001-payment-ownership.md) |
| ~~MVP 대상 도시~~ | **닫힘 — 서울** (2026-09-10). 기술 제약이 아니라 검증 주장의 분모다 | [decisions/D-016-scope-narrowing-reasons.md](decisions/D-016-scope-narrowing-reasons.md) |
| ~~지원 언어 범위~~ | **닫힘 — 세 번 바뀌었다** (2026-09-10, v11 §0-4 결정 2 → 11 → 14). 원본 한국어, **링크·알림은 보낼 때 고객 언어로 생성한다**(언어 목록 없음), 에이전트 경로는 에이전트가 | 동 |
| **액티비티 운영 변경 정보를 어디서 받나** | 서울권 표본 조사 — 2주차. **도시가 정해져 시작 가능** | v11 §0-3 |
| **구현 카탈로그를 어떻게 관리하나** | 손으로 유지하는 목록 둘을 없애는 안. UI 화면 셋 | [decisions/D-015-implementation-catalog.md](decisions/D-015-implementation-catalog.md) |
| **49,000원 수용 여부** `[정정 2026-09-10]` 59,000원(2도시)에서 **팀당 49,000원 · 서울 · 최대 7일 · 4인**으로 내렸다 — v11 §0-4 결정 13, [business/pricing-travel.md](business/pricing-travel.md) | 유료 파일럿 20~30팀 | 동 |
| **`MCP`·`Docker`·`AWS`를 v11이 말하지 않는다** | `A2A` 는 「계약을 바꾸면 걸리는 것」으로 2회 나온다. 나머지 셋은 0회 — 빠진 것인지 뺀 것인지 안 정해졌다 | `program/plan/A-COP_여행Team모듈_구성안.md` §0 |

## 최근 변경

[log.md](log.md)

## 작업 기록은 각 저장소의 `wiki/records/`에 있다 (2026-09-08)

옛 `docs/`(evidence·리포트·handoff 등)는 `final_project_cs/wiki/records/`·`final_project_sample/wiki/records/`로 합쳐졌다. 허브 wiki는 현재 지식만 담고 기록은 인용한다. 규칙은 [governance/work-loop.md](governance/work-loop.md) 2026-09-08 절.
