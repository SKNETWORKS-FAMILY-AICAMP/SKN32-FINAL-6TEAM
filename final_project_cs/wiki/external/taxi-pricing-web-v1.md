---
type: contract
title: 웹 확인 화면의 택시 호출 상품 조건
status: draft
decision_status: accepted
implementation_status: partial
validation_status: partial
domain: travel
---

# 웹 확인 화면의 택시 호출 상품 조건

작성일: 2026-10-12. 현재 구현 작업의 입력 계약이며 실제 운영 반영·실사용 정확도 완료 선언이 아닙니다.

## 적용 범위

등록 전 확인 화면에서 여행 전체의 택시 즉시호출 상품 하나를 고릅니다. 상품은 `kakao_general`, `km_blue_immediate`, `turu_blue_immediate`, `capsi_immediate`, `mycap_immediate` 다섯 개만 지원합니다. 상품별 플랫폼 이용료의 공식 범위 상단을 예상 예산에 포함하며 최종 미터 운임·통행료·결제액을 보장하지 않습니다. 공식 범위를 확인하지 못한 별도 견적 상품과 예약 상품은 이번 웹 입력 범위에서 지원하지 않습니다.

마이캡은 [공식 승객 이용약관](https://www.blackpin.co.kr/?mode=policy)의 제9조에서 서울 즉시호출 플랫폼 이용료 범위가 03:00~22:00 0~3,000원, 22:00~03:00 0~5,000원임을 루트 담당자가 공식 웹의 JavaScript 모달 원문 전체로 확인했습니다. 부칙의 시행일은 2025-03-05이며 현재 관측일은 2026-10-12입니다. 이 근거는 현재 공개된 약관이며 과거 실제 이용 당시에도 같은 버전이었음을 확정하지 않습니다. 따라서 마이캡을 웹의 견적 필수 상품에서 제외하고 공식 범위 상품으로 지원합니다.

## 요청과 저장

기존 본인 접수 편집 `POST /v1/web/trip-intakes/{intake_id}/edits`의 `edits`에 다음 단일 필드를 보냅니다.

```json
{"revision": 3, "edits": [{"field": "trip.taxi_pricing", "value": {"product": "km_blue_immediate", "quotes": []}}]}
```

- 객체의 키는 정확히 `product`, `quotes`입니다. product는 위 다섯 문자열, quotes는 빈 JSON 배열만 받습니다. 잘못된 값과 비어 있지 않은 견적은 422로 거절하며 일반호출로 대체하지 않습니다.
- 이번 웹 경로는 사전 앱 견적 입력을 받지 않습니다. 기존 에이전트 API의 `constraints.taxi_call_quotes` 계약을 변경하지 않습니다. 웹 화면에서 영수증·결제수단·카드번호를 요구하지 않습니다.
- 기존 tenant/customer 확인, 편집 가능한 review 상태, revision 충돌 검사와 DB 트랜잭션을 그대로 거칩니다. 등록 후 confirmed 접수의 변경은 지원하지 않습니다.
- 값은 다른 여행 값처럼 intake_claims의 새 revision에 저장됩니다. 상품·견적 목록은 하나의 값으로 저장됩니다. 변경 직후의 재검증과 새로고침에서도 동일 값을 읽습니다.

## 응답과 실제 계산 연결

새 확인 응답의 `review.taxi_pricing`은 저장된 구조를 반환하며 미지정은 `{"product":"kakao_general","quotes":[]}`입니다. 이 필드가 없는 옛 확인 응답은 이번 웹 입력 기능을 지원한다는 신호로 읽지 않습니다. 미지정은 기존 엔진의 일반호출 기본값을 유지합니다. 구간별 택시 상품이라고 표시하지 않습니다.

저장된 product/quotes는 계산기 입력 `constraints.taxi_call_product`, `constraints.taxi_call_quotes`에 대응합니다. 전체 확인 검사와 이동수단 후보 조회·선택이 모두 같은 값을 사용합니다. 상품 변경은 이동 재사용 키를 바꾸므로 앞 revision의 요금·출발 안내를 재사용하지 않습니다.

상품이나 일정의 revision이 바뀌면 웹 화면의 기존 이동 후보 상태도 폐기합니다. 후보 조회 캐시는 동일 revision에서만 재사용하고 새 revision은 새 후보를 받습니다. 이전 revision의 진행 중 요청이 늦게 끝나도 새 revision 화면의 후보를 바꾸면 안 됩니다.

확정 등록 시 constraints에 같은 값을 보존하고 저장 이동의 departure_context 장소 key를 실제 등록 places[].key로 맞춥니다. 선택 상품·예상 운임·출발시각은 key 변환 때문에 바꾸지 않습니다. 웹 일정 생성 시에도 기존 survey/recovery 제약과 함께 보존합니다.

현재는 quotes가 비어 있으므로 등록 장소 key 변환 때문에 견적을 새로 만들거나 과거 영수증을 견적으로 승격하지 않습니다. 이후 견적 입력을 확장하면 견적 from/to와 departure_context 양쪽의 일관된 변환 및 시간·상품 일치 검증이 먼저 필요합니다.

## 켜고 끄는 스위치 — 2026-10-14 핫픽스

택시 요금 계산을 아직 믿고 내보낼 수 없다는 사용자 지시로, 이 고르기 기능을 **관리 콘솔 「운영 설정」의 스위치 `travel.mobility.taxi_call_product_enabled`** 로 끄고 켤 수 있게 했고 **기본은 꺼짐**입니다(가드레일 `travel.mobility.taxi_call_product_enabled: false`, 콘솔 값이 먼저).

- 꺼짐: 확인 응답의 `review.taxi_pricing` 이 `null` 입니다. 이 필드가 없거나 `null` 이면 이번 웹 입력 기능을 지원하지 않는 응답으로 읽고 화면은 칸을 보이지 않습니다. 앞서 저장된 `trip.taxi_pricing` 값은 요금 계산·이동수단 후보·등록 제약에 쓰지 않습니다. `trip.taxi_pricing` 고르기 요청은 `taxi_pricing_disabled` 로 거절합니다(위 「요청과 저장」의 422 규칙은 켜짐일 때의 동작입니다).
- 켜짐: 위 「요청과 저장」 · 「응답과 실제 계산 연결」 그대로입니다.
- 이미 저장된 검사 결과는 화면으로 내보낼 때 칸을 비웁니다(저장본은 그대로).
- 켜기 전에 아래 「검증 경계」의 실제 이용 · 결제 오차 근거가 필요합니다. 기록: [2026-10-14 핫픽스 보고서](../records/reports/2026-10-14_택시상품_고르기_스위치_핫픽스.md).

## 검증 경계

오프라인 단위시험은 저장 구조·계산 조건 전달·이전 후보 재사용 방지·확정 등록의 조건/키 보존을 확인합니다. DB 트랜잭션 실제 실행, 화면 조작, cs 프로젝트 서버 배포, 실제 택시 이용·결제 오차는 각각 별도의 실행 근거가 필요합니다. 단위시험 통과를 이들 완료로 확대하지 않습니다.
