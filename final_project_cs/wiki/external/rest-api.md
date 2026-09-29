---
type: contract
title: REST API
description: Case・여행・고객 웹 REST 진입점과 인증 구분, API 명세 및 검증 경로를 안내한다
status: draft
owners: [human:최연우]
tags: [api, contract]
domain: travel
---

# REST API

`[실측]` 2026-09-29 · `develop` `fc1ac0a` 코드 기준. REST에는 Case뿐 아니라 여행·위임·고객 웹 API가 있다. **요청·응답 필드의 정본은 [rest-endpoints.md](rest-endpoints.md)**이며, 이 문서는 진입점과 경계를 안내한다. 화면의 요구·사용 API·연결 상태는 [화면별 연동 문서](web-screen-api.md)에 둔다.

이전 문서의 “여행 API 0개”, “전체 경로 5개”는 현재 API 전체를 설명하지 않는다. 옛 Case 검증 경위는 Git 이력과 아래 기록 링크로 확인한다.

## 진입점과 명세

| 대상 | 경로·의미 | 상세 |
|---|---|---|
| Case | `/v1/cases*` — 문의·조회·추가 메시지·제안 승인 | [필드 계약](rest-endpoints.md), [Case 라우터](../../app/presentation/api/cases.py) |
| outbox | `/v1/outbox/{message_id}/resolve` — 불명확한 배달 결과를 사람이 확인한 근거 기록 | [필드 계약](rest-endpoints.md), [outbox](../actions/outbox.md) |
| 여행·계획 | `/v1/trips*` — 등록·생성·조회·신고·상담·제안·되돌리기 | [여행 계약](rest-endpoints.md), [여행 라우터](../../app/modules/travel_ops/trip_api.py) |
| 고객 웹 | `/v1/web/*` — 사용자 키·내 여행·상담·선택·알림·모델 예열 | [웹 계약](rest-endpoints.md#web-api) |
| 계획 접수 | `/v1/web/trip-intakes*` — 자료 읽기·수정·확인·계획 생성 | [접수 계약](rest-endpoints.md#intake-api) |
| 위임 | `/v1/delegations*` — 권한 조회·부여·철회 | [필드 계약](rest-endpoints.md) |

위 표는 경로 묶음의 안내이며 엔드포인트 수나 전체 운영 API 목록이 아니다. `/health`, `/introspection`, `/admin/reload`, 토큰 링크·운영 UI의 경로도 별도로 존재한다. 관리용 Composer 라우터는 관리 빌드에서만 주입된다.

## 인증과 책임 경계

- 서버·외부 에이전트 API는 Bearer 키와 경로별 scope를 사용한다. [인증 경계](auth-boundary.md)를 확인한다.
- **고객 웹은 `X-User-Key`를 사용한다.** 키 발급 외 웹 경로는 `_web_customer`를 거치며, 여행·접수는 해당 고객의 자료만 연다. 서버용 scope 키를 브라우저에 넣지 않는다.
- 제안 승인·선택과 업무 실행의 조건은 해당 계약을 따른다. HTTP 요청 성공만으로 외부 예약 변경이나 배달 성공까지 확정하지 않는다.
- CORS의 출처·메서드·헤더는 [앱 조립](../../app/presentation/api/app.py)이 정한다. 새 API의 메서드를 추가할 때 브라우저 호출 가능 여부도 함께 확인한다.

## 계약을 추가하거나 바꿀 때

[갱신 담당과 작업 순서](../../RULE.md#351-웹-api와-화면별-연동-문서-갱신)를 따른다. 요청·응답·오류·인증·멱등성·소유권을 API 명세에 반영한 다음 구현과 계약 검사를 맞춘다. 화면 문서에는 사용 관계와 진행 상태를 갱신한다.

문서에만 있는 제안과 서버에 구현된 경로를 구분한다. 신규 요구는 화면 문서의 `협의 필요`에 남기고, 양측의 확인 근거 없이 확정 계약으로 승격하지 않는다.

## 검증 범위

| 근거 | 확인하는 것 | 한계 |
|---|---|---|
| [앱 조립](../../app/presentation/api/app.py)·[composition](../../app/composition.py) | 실제로 포함할 라우터와 경계 | 소스 존재만으로 실행 성공을 증명하지 않음 |
| [웹 계약 검사](../../tests/contract/test_web_client_contract.py) | 웹 호출 경로·메서드, 설문 판·필드·선택지와 서버의 일치 | DB·외부 모델·브라우저를 통합 실행하지 않음 |
| [OpenAPI 표면 검사](../../tests/integration/api/test_openapi_surface.py) | 계약 경로 존재, 추가 경로의 목록 반영, 쓰기 인증 의존성 | `CONTRACT_V1_PATHS`도 구현 변경과 함께 갱신해야 함 |
| [웹 API 검사](../../tests/e2e/test_web_api.py)·[접수 API 검사](../../tests/e2e/test_trip_intake_api.py) | 해당 환경의 API 동작 | 실행 조건과 실제 결과를 별도로 기록해야 함 |

`[실측]` `fc1ac0a`에는 예열 라우트가 있지만 OpenAPI 검사의 `CONTRACT_V1_PATHS`에는 `/v1/web/warmup`이 없다. [검사 목록 누락 기록](../records/reports/debugs/2026-09-29_1436_예열API_검사목록_누락.md)을 참고한다. 이 문서 변경으로 코드나 검사 목록을 수정하지 않았다.

`[미확보]` 이번 작업의 Python 계약 검사는 환경 문제로 수집·실행하지 못했다. [검증 기록](../records/evidence/2026-09-29_1436_웹API_협업문서_정리.md)에 시도한 명령과 출력을 남긴다. 코드 대조를 테스트 통과로 기록하지 않는다.

## 관계와 과거 근거

- [화면별 연동 문서](web-screen-api.md) — 화면 설명·사용 API·협의 항목·연결 상태
- [API 명세](rest-endpoints.md) — 요청·응답·제약의 정본
- [인증 경계](auth-boundary.md) — 인증·권한·격리
- [승인](../actions/approval.md) · [Case 상태](../runtime/case-lifecycle.md) — 상태 변경의 조건
- [introspection](introspection.md) — 현재 조립 정보
- [MCP](mcp-tools.md) · [A2A](a2a-protocol.md) — 별도 접점의 계약
- [옛 REST·MCP 계약](../records/handoff/03_REST_MCP_인터페이스.md) — 동결된 기록. 현재 명세로 갱신하지 않음
- [테스트 사각지대](../quality/blind-spots.md) — 옛 계약·검사 불일치의 조사 근거
