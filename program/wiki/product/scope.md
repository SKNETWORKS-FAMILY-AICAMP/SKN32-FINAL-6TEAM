---
type: concept
title: 범위
description: 10주에 무엇을 만들고 무엇을 안 만드는가. Out of Scope가 In Scope보다 중요하다
status: draft
tags: [customer-operations, release]
---

# 범위

## In Scope

10주에 실제로 만드는 것.

| 영역 | 포함 |
|---|---|
| 수집·분류 | 피드백 정규화, 감성·의도·이슈 분류 |
| Case | 상태 관리, 생명주기, 이벤트 |
| Team | 업무 책임 단위 모듈, Registry 등록형 |
| 지식 | 기업 지식 RAG, Memory, Shared State |
| 승인 | Human Approval 경계 |
| 외부 연동 | REST, MCP, A2A 더미 Remote Agent 1개 |
| 운영 | 운영자 대시보드 |

**인라인 분류는 선택 기능이 아니다.** Case 생성 경로에서 감성·의도·이슈 분류가 실패하면 `classification_failed`를 남기고 `escalated`로 전환한다.

## Out of Scope

**이게 In Scope보다 중요하다.** 범위를 지키지 못하면 10주에 아무것도 못 끝낸다.

| 제외 | 왜 |
|---|---|
| OCR·영상 분석 | 입력 모달리티를 텍스트로 고정한다 |
| 다수 도메인 완전 지원 | 도메인 1개로 통제한다 |
| Production-scale 분산 시스템 | 단일 인스턴스 전제 |
| 모든 외부 AI 플랫폼별 정식 배포 | 경계와 더미 검증까지만 |
| **결제 실행** | 검증 쇼핑몰이 소유한다 → [../decisions/D-001-payment-ownership.md](../decisions/D-001-payment-ownership.md) |
| **포인트·캐시·쿠폰 잔액 변경** | 동. 읽기만 한다 |
| 음성 채널 | `[미확보]` 트래픽·STT·TTS 원가 미산정 |
| 배치 임베딩 클러스터링·토픽 모델링 | 규칙 기반 집계·급증 탐지만 |

## Pack 범위

| Pack | Team | 상태 |
|---|---|---|
| CS Pack | VOC & Store Manager, Response Generation & Review | **10주 착수 확정** |
| Commerce Ops Pack | Procurement + Order & Payment, Fulfillment & Logistics, Return & Refund(Mock), Catalog & Verification(A2A Remote) | 검증 쇼핑몰 일정에 따라 조정 |

CS Pack 2종은 부트캠프 주제 자체에 속하므로 확정이다. Commerce Ops Pack은 검증 쇼핑몰 프로젝트의 진행 범위에 따라 달라진다.

**국외 배송·해외 구매대행의 실제 Live 연동은 Mock으로 남긴다.**

구조는 [../architecture/pack-model.md](../architecture/pack-model.md).

## 지연이 만드는 범위 제약

`[실측]` 현재 p50 20~34초, p95 32~51초다. 이게 채널 범위를 좁힌다.

| 용도 | 가능한가 |
|---|---|
| 상담원 초안 보조 | 가능 |
| 이메일·게시판 문의 | 가능 |
| 야간 배치 선처리 | 가능 |
| **실시간 채팅 자동응답** | **불가** |

`[실측]` 골든셋 채널 분포가 web 23 / chat 23 / email 17 / phone 9인데, **chat 23건(32%)이 현재 지연으로는 어렵다.**

제품 형태가 "실시간 자동응답"이 아니라 **"상담원 보조"**로 좁혀진다는 뜻이다. 이걸 숨기면 안 된다.

## Vision — 지금 안 하는 것

나중에 할 수 있지만 10주에는 안 한다.

- 전면 사이트 생성·판매
- 재고·발주·배송·정산의 전면 운영 자동화
- Graph Store 도입 (채택 게이트 통과 시에만)
- 자체호스팅 실제 배포

## 범위 통제 방법

범위 과대가 이 프로젝트의 1번 리스크다. 다음 기준선으로 통제한다.

```text
도메인          1개
착수 LOCAL Team 4개
Remote A2A PoC  1개
```

**Team 수와 Remote Agent 수는 아키텍처 상한이 아니다.** Registry 등록으로 확장되는 값이고, 확장 여부는 일정과 평가 여력(골든셋·라우팅 평가 축 증가)으로 판단한다.

## 관계

- [positioning.md](positioning.md) — 무엇을 파는가
- [../architecture/pack-model.md](../architecture/pack-model.md) — Pack 구조
- [../delivery/timeline.md](../delivery/timeline.md) — 일정
- [../decisions/index.md](../decisions/index.md) — 범위를 좁힌 결정들
