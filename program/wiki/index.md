---
type: guide
title: A-COP 지식 허브
description: 중앙 허브의 8개 영역과 각 영역이 답하는 질문
status: draft
---

# A-COP 지식 허브

처음이면 [quickstart.md](quickstart.md)부터 본다.

여기는 **코드 커밋과 무관하게 움직이는 지식**만 둔다. 구현 세부는 각 코드 저장소의 `wiki/`에 있다.

## 영역

### [product/](product/index.md) — 무엇을 만드는가
포지셔닝, 페인포인트, 페르소나, 범위, 용어.
"이게 왜 필요한가"에 답해야 할 때 여기부터.

### [business/](business/index.md) — 얼마짜리인가
건당 원가, 인프라 비용, 시장 규모, 가격안.
사람 1건 4,100~4,846원 · A-COP 병행 1,133원이 여기서 나온다.

### [architecture/](architecture/index.md) — 어떻게 나뉘는가
시스템 경계, 저장소 관계, Core와 Team의 분리 기준, Pack 모델.
**경계만 다룬다.** 구현은 코드 저장소 wiki에 있다.

### [delivery/](delivery/index.md) — 언제 무엇을 내는가
일정, 마일스톤, DoD 29항목, 6명의 소유 경계.

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
| 환불 계산 방식 전환 시점 | 검증 쇼핑몰과 계약 협의 | [decisions/D-001-payment-ownership.md](decisions/D-001-payment-ownership.md) |

## 최근 변경

[log.md](log.md)
