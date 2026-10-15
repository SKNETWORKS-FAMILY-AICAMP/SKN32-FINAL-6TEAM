---
type: contract
title: 고객 제공 SNS 맛집 링크
description: 본인 접수에 링크 후보를 보관하고 검증한 식사 변경안을 명시적으로 적용하는 웹 계약
status: draft
domain: travel
---

# SNS 맛집 링크 웹 계약

2026-10-15 사용자 승인 첫 범위. 이 계약의 추가는 운영 배포·실플랫폼 성공 확인을 의미하지 않는다. Instagram·TikTok·YouTube 공개 링크의 접근 가능한 텍스트와 고객 보완을 사용한다. 영상 분석·로그인 우회·업체 예약은 별도다.

## 인증과 상태

모든 경로는 기존 고객 웹 인증을 요구한다. 접수의 tenant와 customer가 모두 같아야 하며 남의 접수는 404다. 등록 여행은 기존 `reopen`으로 본인 수정 접수를 열어 같은 기능을 이용한다. 원래 여행 저장은 기존 `confirm`이 담당한다.

경로 접두사는 `/v1/web/trip-intakes/{intake_id}/dining-links`다. 링크 조회·접수·보완은 여행 일정을 바꾸지 않는다. 후보는 서버 DB에 보관하며, 기존 일정의 `revision`과 링크의 식별 `key`를 구분한다.

| 메서드·접미사 | 요청 | 결과 |
|---|---|---|
| GET 기본 경로 | 없음 | `{revision, links}` 및 현재 저장 제안 |
| POST 기본 경로 | `{links:[{url,note?,priority?}]}` | `{revision,links}`; 기존 후보와 합침 |
| PATCH `/{key}` | `{priority?,restaurant_index?,selected_ref?,name?,area?}` | `{revision,links}`; 저장된 후보 선택·식당명 보완 |
| POST `/preview` | `{revision,target_item_id?}` | `{revision,proposal_id,changes,unplaced,links}` |
| POST `/apply` | `{revision,proposal_id}` | 기존 intake view의 새 판; 여행 최종 저장은 기존 확정 경로 |

`priority`는 `must`(꼭 가기) 또는 `if_fits`(동선이 맞으면, 기본)다. 링크만 보내면 일정은 바뀌지 않는다. preview는 변경 후 전체 검증을 미리 실행하고 되돌려 실제 일정을 유지한다. apply는 서버에 저장한 제안만 사용하고 같은 기준 revision을 다시 검증한다. 중복 apply로 두 번 바꾸지 않는다. 낡은 revision/제안은 409다.

## 링크와 변경안

링크 항목은 `key`, `source_urls`, `platform`, `status`, `reason`, `restaurants`, `priority`, `checked_at`을 가진다. `restaurants`는 이름·지역·지점·메뉴와 실제 읽은 문구의 근거이며, 장소 검색으로 확인된 가게와 구분한다. 자동 추출된 이름은 서버 검색·고객 확인 없이 실존 장소 확정으로 표시하지 않는다.

`status`: `identified`, `needs_choice`, `needs_info`, `inaccessible`, `failed`, `unsupported`, `invalid`. 접근 실패·모델 불가·모델 실패·근거 불일치의 사유를 구분한다. 식당이 여러 곳이면 `restaurant_index`, 실존 장소가 여러 지점이면 저장한 `choices[].ref`의 `selected_ref`를 고객이 고른다. SNS 출처는 장소 제공자 `source`와 별도다.

배치 결과는 `placement_status`와 `placement_reason`으로 별도 표시한다. `changes`에는 링크 key·대상 식사 item_id·기존 `from`·새 식당 `to`·이유를, `unplaced`에는 링크 key·이름·우선순위·미반영 사유를 담는다. source_urls는 정규화로 합쳐진 원래 링크도 보존한다.

영업·식이 조건·이동을 확인할 수 없으면 해당 배치를 보류한다. 완료·고정 식사와 식사 외 활동은 자동 변경하지 않는다. 배치할 식사 자리가 없으면 후보를 보관하고 기존 일정 생성/수정 화면으로 안내한다. 링크 하나가 실패해도 기존 일정과 독립 후보는 유지한다.

## 조건·지점·검색 보존

`[2026-10-15 우선 결함 수정]` 빈 접수에 만든 초안의 `constraints`는 현재 revision의 근거 claim으로 보관하고, 확인 화면의 일정 조립과 최종 등록에도 싣는다. 초안 설문을 바탕으로 접수에 저장한 답과 최종 요청을 합치며, 일부 영역만 답해도 다른 영역의 식이 조건은 유지한다. SNS preview와 apply는 원래 여행·초안·저장 설문의 식이 조건을 읽고, 필요한 정보를 다시 확인할 수 없으면 해당 식사 배치를 보류한다.

고객이 고른 장소 ref는 서로 다른 지점명·도로명과 건물번호·좌표가 모순되는 후보로 대체하지 않는다. 같은 건물의 본점/별관과 복합 지점 표시는 구분한다. 지점 없는 후보가 두 지점 모두와 겹치면 두 지점을 연결해 병합하지 않는다. 같은 지점임을 확인한 제공자 중복 안에서만 더 충분한 검증 결과를 재사용한다. 지점 표기가 상호 본문에 들어 있다는 이유로 요청한 지점이라고 확정하지 않는다.

SNS 장소 검색은 상호·지역·지점 힌트를 나누고, 원래 검색문은 외부 검색에 보낸다. 지역과 지점 우선순위는 DB 결과 수를 자르기 전에 반영한다. 알려진 지역은 기존 지역 좌표·반경을, 사전에 없는 지명은 주소의 명시 정보(괄호 속 동명 포함)를 근거로 확인한다. 이름을 지정한 요식 원장 검색은 서울 범위에서 찾고, 주변 대체 후보의 반경은 기존 값을 쓴다. 기존 자유 검색은 전체 상호로 먼저 찾고, 결과가 없을 때만 사전에 있는 앞/뒤 지명을 나눈다. 이 수정은 공개 API 요청·응답 모양을 바꾸지 않는다.

## 추출 프롬프트 v2

`[2026-10-15 사용자 지시]` `social_dining_extract.v2`는 지역·지점·메뉴를 각각 살펴 명시된 값을 채운다. 예시는 모든 값을 채운 형태로 제시하며, 정보가 없거나 어느 식당의 정보인지 불분명하면 해당 칸을 `null`로 둔다.

- 지역은 전체 주소 대신 원문이 그 식당에 연결한 짧은 지명 하나를 쓴다. 동네·상권·역명이 있으면 그것을, 없으면 명시된 구·도시를 쓴다. 도로명 주소에서 동네를 추정하거나 계정명·무관한 해시태그를 지역으로 쓰지 않는다.
- 지점은 이름에 붙은 명시적 지점 표시도 별도로 담는다. 메뉴는 해당 식당의 음식·음료명을 쓰며 복수면 문자열 배열을 허용한다.
- 지역·메뉴가 이름과 다른 줄에 있으면 그 근거 줄도 각각 `evidence`에 인용한다. 출처가 다르면 `metadata`와 `customer_note`를 나눠 표시한다. 모든 값과 인용은 원문의 연속 부분문자열이어야 하며, 서버의 기존 근거 대조를 거친다.

링크 응답 모양과 수집 범위는 같다. 새 추출의 근거에는 v2 버전·해시가 붙으며, 이미 보관한 v1 후보를 자동으로 다시 추출하지 않는다.

## 진행과 상한

POST 접수·preview에서 `Accept: text/event-stream`을 주면 기존 웹 진행 계약의 accepted/stage/beat/result/error를 사용한다. JSON과 SSE의 result 본문은 같다. 통신이 끊기면 GET으로 보관된 후보와 제안을 다시 읽는다. apply의 멱등 키는 서버 제안 식별자다.

플랫폼 호스트·링크 수·조회 시간·응답 크기·리디렉션 수·메타데이터 길이·모델 후보 수·배치 검색 수는 `config/guardrails.yaml`의 `travel.social_dining`이 소유한다. 허용한 공개 플랫폼 주소만 조회하고 리디렉션마다 대상과 사설 주소를 검사한다. 영상·전체 게시물 본문은 영구 저장하지 않는다. `[2026-10-15 D-025]` 공개 게시물 글 읽기는 플랫폼의 자동 수집 금지 조항에 걸리는 회색 지대라 **학업용으로만** 쓴다 — 고객이 보낸 링크 1건마다 `<head>` 의 글만 읽고, 이미지·영상은 받지 않는다. 상업 전환 전에 끄고 재확인한다([D-025](../../../wiki/decisions/D-025-study-only-social-post-text.md)).

## 관계

- [설계](../records/plans/2026-10-14_social-dining-links-design.md)
- [구현 계획](../records/plans/2026-10-15_social-dining-links-implementation.md)
- [웹 접수](rest-endpoints/web-intakes.md)
- [변경 규칙](../../../wiki/decisions/D-020-trip-survey-and-ask-first.md)
