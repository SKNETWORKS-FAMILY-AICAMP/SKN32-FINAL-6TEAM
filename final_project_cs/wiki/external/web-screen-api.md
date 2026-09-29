---
type: guide
title: 사용자 웹 화면과 API 연결
description: 화면의 동작·필요 데이터와 기존 API 명세를 연결하고 협의·구현·연결·검증 상태를 추적한다
status: draft
owners: [human:최연우, human:최상욱]
tags: [ui, api]
domain: travel
---

# 사용자 웹 화면과 API 연결

화면을 만드는 쪽과 API를 만드는 쪽이 함께 보는 문서다. **API의 요청·응답 계약은 [기존 명세](rest-endpoints.md)에 두고, 여기서는 화면의 요구와 사용 관계를 설명한다.** 문서 갱신 담당과 공동 연결 작업 규칙은 [RULE.md §3.5.1](../../RULE.md#351-웹-api와-화면별-연동-문서-갱신)을 따른다.

`[실측]` 2026-09-29 · 코드 기준 `develop` `fc1ac0a`. 아래 초기 상태는 Codex가 화면·호출부·서버 라우트를 정적으로 대조한 결과다. 이 문서 작성 중 실제 서버 요청이나 브라우저 검증은 하지 않았다. 기존 구현이 있다는 사실을 새 API 협의 완료나 운영 검증 완료로 해석하지 않는다.

## 읽기 순서

1. 아래 화면 표에서 작업할 화면과 기능 ID를 찾는다.
2. 기능 표의 API 명세와 코드 근거를 읽는다.
3. 없는 기능은 협의 항목에서 요구와 미정 사항을 확인한다.
4. 변경 후 해당 항목의 구현·연결·검증 상태와 근거를 갱신한다.

## 화면과 사용자 동작

API 열의 ID는 아래 연결 상태 표로 이어진다. `live`는 실제 서버 어댑터이고 `demo`는 명시적인 시연 데이터다.

| 화면·URL | 사용자가 하는 일 | 필요한 데이터·처리 | 연결 항목 |
|---|---|---|---|
| 소개 `/` | 서비스 설명 확인, 최근 여행에서 이어가기, 언어 선택 | 저장된 키가 있을 때 내 여행 목록. 언어는 현재 브라우저 설정 | W-02, Q-03 |
| 온보딩 `/start` | 약관 확인, 선택 이메일 입력, 취향 설문 | 설문 답은 메모리에 두었다가 확인·계획 생성 시 전송. 이메일은 형식 검사만 | W-05, W-06, Q-02 |
| 계획 등록 `/trips/new` | 일정 글·파일을 올리고 읽기 시작 | 접수 ID를 받아 확인 화면으로 이동. 키가 없으면 첫 API 사용 시 발급 | W-01, W-03 |
| 계획 확인 `/intakes/[intakeId]` | 읽은 내용·원문 근거 확인, 항목 수정·제외, 등록 또는 일정 생성 | 처리 단계, 원본·항목, 수정 판 번호, 등록 가능 여부와 문제 목록, 등록된 여행 ID | W-04, W-05, W-06 |
| 검증 중 `/trips/[tripId]/verification` | 검증 진행 확인 | demo는 단계 진행. live는 등록 때 서버가 판정한다는 안내와 여행 이동 링크 | 별도 검증 API 없음 |
| 검증 결과 `/trips/[tripId]/results` | 결과·확인 필요 항목 확인 | demo는 시연 결과. live는 여행 화면의 경고·알림·이력으로 안내 | W-07, W-10 |
| 여행 `/trips/[tripId]` | 일정·지도 확인, 상담, 제안 선택, 알림·변경 이력 확인 | 일정 항목·좌표·시각·경고·이력, 서버 답변, 선택 대안, 알림 | W-07~W-11 |
| 내 여행 `/trips` | 여행 목록에서 열기, 여행 삭제 | 목록의 제목·등록 시각·ID. 삭제는 demo만 지원하고 live에서는 비활성 | W-02, Q-01 |
| 마이페이지 `/mypage` | 키 보기·복사, 다른 키 가져오기, 키 재발급 | 현재 키와 발급 안내. 가져온 키는 서버 조회로 확인한 후 저장 | W-01, W-12, Q-02 |
| 프로필 수정 `/mypage/edit` | 닉네임·복구 이메일 입력 | 입력 검사만 구현. 저장·이미지 변경은 비활성 | Q-02 |

## 연결 상태

초기 표의 `구현 확인`은 서버 코드 존재, `연결 확인`은 화면에서 해당 호출부로 이어지는 코드 존재를 뜻한다. **통합 검증은 모두 별도 수행 대상**이다. 이후 검증하면 해당 행을 바꾸고 아래 갱신 근거에 실행 조건과 결과를 남긴다.

| ID·기능 | API 명세·호출 | 백엔드 구현 | 프론트 연결 | 통합 검증 | 코드 근거 |
|---|---|---|---|---|---|
| W-01 키 발급 | [웹 API](rest-endpoints.md#web-api) · `POST /v1/web/session` | 구현 확인 | 연결 확인 | 미검증 | [client.ts](../../frontend/apps/web/src/lib/live/client.ts), [키 안내](../../frontend/apps/web/src/features/account/key-notice.tsx) |
| W-02 내 여행·최근 여행 | [웹 API](rest-endpoints.md#web-api) · `GET /v1/web/trips` | 구현 확인 | 연결 확인 | 미검증 | [gateway.ts](../../frontend/apps/web/src/lib/live/gateway.ts), [여행 목록](../../frontend/apps/web/src/features/trip/trip-list.tsx) |
| W-03 계획 접수 | [계획 접수](rest-endpoints.md#intake-api) · `POST /v1/web/trip-intakes` | 구현 확인 | 연결 확인 | 미검증 | [intake.ts](../../frontend/apps/web/src/lib/live/intake.ts) |
| W-04 접수 조회·수정 | [계획 접수](rest-endpoints.md#intake-api) · `GET /v1/web/trip-intakes/{intake_id}`, `POST /v1/web/trip-intakes/{intake_id}/edits` | 구현 확인 | 연결 확인 | 미검증 | [확인 화면](../../frontend/apps/web/src/features/intake-review/intake-review.tsx) |
| W-05 확인 등록·설문 | [계획 접수](rest-endpoints.md#intake-api) · `POST /v1/web/trip-intakes/{intake_id}/confirm`, [설문 계약](rest-endpoints.md#trip-survey) | 구현 확인 | 연결 확인 | 미검증 | [intake.ts](../../frontend/apps/web/src/lib/live/intake.ts), [설문 변환](../../frontend/apps/web/src/features/onboarding/payload.ts) |
| W-06 일정 생성·설문 | [계획 접수](rest-endpoints.md#intake-api) · `POST /v1/web/trip-intakes/{intake_id}/plan` | 구현 확인 | 연결 확인 | 미검증 | [확인 화면](../../frontend/apps/web/src/features/intake-review/intake-review.tsx) |
| W-07 일정·지도·경고·이력 | [웹 API](rest-endpoints.md#web-api) · `GET /v1/web/trips/{trip_id}` | 구현 확인 | 연결 확인 | 미검증 | [gateway.ts](../../frontend/apps/web/src/lib/live/gateway.ts), [지도 표시 계약](../../frontend/apps/web/MAP_INTEGRATION.md) |
| W-08 대화 | [웹 API](rest-endpoints.md#web-api) · `POST /v1/web/trips/{trip_id}/messages` | 구현 확인 | 연결 확인 | 미검증 | [gateway.ts](../../frontend/apps/web/src/lib/live/gateway.ts), [여행 화면](../../frontend/apps/web/src/features/trip/trip-home.tsx) |
| W-09 제안 조회·선택 | [웹 API](rest-endpoints.md#web-api) · `GET /v1/web/trips/{trip_id}/proposals`, `POST /v1/web/trips/{trip_id}/proposals/{proposal_id}/choose` | 구현 확인 | 연결 확인 | 미검증 | [extras.ts](../../frontend/apps/web/src/lib/live/extras.ts), [선택 화면](../../frontend/apps/web/src/features/trip/trip-attention.tsx) |
| W-10 알림 | [웹 API](rest-endpoints.md#web-api) · `GET /v1/web/trips/{trip_id}/notices` | 구현 확인 | 연결 확인 | 미검증 | [extras.ts](../../frontend/apps/web/src/lib/live/extras.ts), [선택·알림 화면](../../frontend/apps/web/src/features/trip/trip-attention.tsx) |
| W-11 대화 모델 예열 | [예열 계약](rest-endpoints.md#web-warmup) · `POST /v1/web/warmup` | 구현 확인 | 연결 확인 | 미검증 | [extras.ts](../../frontend/apps/web/src/lib/live/extras.ts), [여행 화면](../../frontend/apps/web/src/features/trip/trip-home.tsx) |
| W-12 키 가져오기·재발급 | [웹 API](rest-endpoints.md#web-api) · 가져오기 검증은 `GET /v1/web/trips`, 재발급은 `POST /v1/web/session/rotate` | 구현 확인 | 연결 확인 | 미검증 | [client.ts](../../frontend/apps/web/src/lib/live/client.ts), [키 설정](../../frontend/apps/web/src/features/account/key-settings.tsx) |

서버 측 공통 근거는 [trip_api.py](../../app/modules/travel_ops/trip_api.py)다. `POST /v1/web/trips`도 서버에는 있지만 현재 화면은 접수→확인/생성 흐름으로 등록한다. 해당 직접 등록 API를 화면에 새로 연결해야 한다는 뜻은 아니다.

## 화면에서 주의할 현재 동작

- **키와 소유권:** 내 여행 목록은 저장된 키가 없으면 서버를 부르지 않는다. 기존 키가 거절되면 오류를 보이고 키를 지우며, 다음 요청은 새 키 발급으로 이어질 수 있다. 이전 여행을 복구한 것으로 표시하지 않는다. 다른 키 가져오기는 검증 실패 시 기존 키를 유지한다.
- **계획 확인:** 읽는 중·확인 가능·등록 완료·치명적 실패를 구분한다. 수정 판이 낡으면 서버가 거절하므로 최신 접수 상태를 확인한다. 설문은 온보딩을 마친 경우에만 확인/생성 요청에 포함한다.
- **여행·지도:** 서버 시각은 서울 날짜·시각으로 바꾸고, 이동 항목은 다음 일정의 출발 메모로 표시한다. 서버 좌표가 없으면 임의의 핀을 만들지 않는다. 지도 제공자 인증 검증은 API 연결 검증과 별도다.
- **대화:** 서버 답변을 표시하고 여행을 다시 조회한다. 현재 화면의 대화 기록은 브라우저 탭의 저장소에 남으며 서버 대화 목록을 조회하는 화면 API는 없다. [대화 처리](../../app/modules/travel_ops/trip_messages.py)는 Case를 생성·전이한다.
- **제안 선택:** 선택 성공 후 여행·제안·알림을 다시 조회한다. 이미 결정됐거나 여행 판이 달라진 오류를 성공으로 표시하지 않는다.
- **예열:** 저장된 키가 있을 때 여행 화면 진입 시 요청한다. 응답의 예열 결과를 화면에 표시하지 않으며 예열 오류도 별도 안내하지 않는다. API 호출 연결과 실패 안내 UI 구현을 구분한다.

## 협의가 필요한 항목

아래는 현재 코드에서 확인한 공백과 **협의할 질문**이다. 새 API 계약·담당자의 개발 약속으로 확정된 내용은 아니다. 확인자·합의일·채택한 계약 링크가 확보되면 해당 행을 갱신한다.

| ID·화면 요구 | 현재 상태 | 합의해야 할 내용 | 백엔드 구현 | 프론트 연결 | 통합 검증 |
|---|---|---|---|---|---|
| Q-01 내 여행 삭제 | demo만 가능, live 삭제 경로 없음 | 삭제 범위·보존/취소 정책·소유권·멱등성·선택 삭제 부분 실패 응답. CORS 허용 메서드도 함께 검토 | 미구현 | 미연결 | 미검증 |
| Q-02 프로필·이메일 복구 | [프로필 계약](../../frontend/apps/web/PROFILE_CONTRACT.md). 키 가져오기/재발급과는 별개 | 저장할 항목·조회/수정 계약·이메일 소유 확인·복구 절차. [D-021](../../../wiki/decisions/D-021-email-verified-key-recovery.md)의 결정과 실제 구현을 구분 | 미구현 | 미연결 | 미검증 |
| Q-03 선택 언어 전달 | 브라우저 문구 설정만 있고 서버 접수/생성은 `ko` 사용 | 언어를 보낼 요청·저장 위치·답변/알림 적용 범위·허용 값·기존 여행 처리 | 미구현 | 미연결 | 미검증 |
| Q-04 예열 결과 안내 | W-11 호출은 있으나 결과·실패 안내 UI 없음 | 별도 안내가 필요한지, 재시도·오류 표시를 어디에 둘지 | 예열 응답 구현 확인 | 호출 연결 확인·안내 미구현 | 미검증 |

각 항목의 **합의 상태는 모두 `협의 필요`**, 확인자·합의일·확정 계약은 `[미확보]`다. Q-01~Q-04를 채택·보류·기각할 때 이유와 양측 확인 근거를 남긴다. 구현을 요청한 것으로 간주해 에이전트가 임의로 API를 추가하지 않는다.

## 검증과 갱신 근거

정상 흐름뿐 아니라 키 거절·다른 사용자 자료·빈 목록·접수 실패·낡은 판·입력 거절·제안 중복 선택·서버/네트워크 실패를 해당 기능에 맞게 확인한다. 실제 서버 검증은 환경·대상 데이터·외부 통지 여부를 확인한 뒤 수행한다.

| 확인 수준 | 무엇을 증명하는가 | 무엇을 증명하지 못하는가 |
|---|---|---|
| 코드 대조 | 라우트·호출부·표시 경로가 존재함 | 서버 실행·DB·외부 모델·화면의 정상 동작 |
| [웹/서버 계약 검사](../../tests/contract/test_web_client_contract.py) | 프론트 호출 메서드·경로와 서버 라우트, 설문 필드·선택지의 호환 | 실제 요청·응답 전체와 브라우저 동작 |
| 웹 단위·가짜 서버 브라우저 검사 | 변환·화면 흐름·지정한 오류 처리 | 실제 백엔드·외부 서비스와의 통합 성공 |
| 실제 서버+브라우저 | 기록된 환경·데이터에서 실행한 정상/실패 흐름 | 실행하지 않은 다른 조건 |

검증 명령과 운영 조건은 [웹 개발 기준](../../frontend/apps/web/DEVELOPMENT.md)과 [실행 안내](../../frontend/apps/web/README.md)를 따른다.

| 날짜·수행자 | 대상·기준 | 결과·근거 | 남은 것 |
|---|---|---|---|
| 2026-09-29 · Codex(최상욱 작업) | 최초 화면/호출/서버 대조 · `fc1ac0a` | [작업 리포트](../records/reports/2026-09-29_1436_웹API_협업문서_정리.md) | 실제 서버·브라우저 검증, 협의 항목의 양측 확인 |

후속 행에는 `수행자 / 날짜 / 화면·기능 ID / 커밋 / 환경·명령 / 결과·근거 / 남은 문제`를 기록한다. 양측 합의나 사람 리뷰가 없으면 있다고 적지 않는다.

## 관계

- [API 명세](rest-endpoints.md) — 합의된 요청·응답과 실제 구현의 기준
- [REST 개요](rest-api.md) — 진입점과 인증·검증 범위
- [문서 갱신 규칙](../../RULE.md#351-웹-api와-화면별-연동-문서-갱신) — 이름별 책임과 공동 연결 작업
- [웹 README](../../frontend/apps/web/README.md) — 실행·환경·모드
- [취향 설문 표시 계약](../../frontend/apps/web/PREFERENCES_CONTRACT.md) — 화면 질문과 서버 설문 필드의 대응
