---
type: contract
title: Case·승인·Outbox
description: 호출 주체와 책임별 REST 요청·응답 계약
status: draft
domain: travel
---

# Case·승인·Outbox



`[실측]` [rest-api.md](../rest-api.md) 에서 분리했다. **Case · outbox · 여행 · 고객 웹 · 계획 접수 · 위임 API 의 필드 단위 계약이다(날짜는 각 절의 확인 시점을 따른다).**

## `POST /v1/cases` 요청·응답 필드

`[실측]`

요청:

| 필드 | JSON 타입 | 예시 | 필수 여부 |
|---|---|---|---|
| `request_id` | string | `"req_01"` | 필수 |
| `idempotency_key` | string | `"idem_01"` | 선택 — 보내면 **그 값을 쓴다** |
| ~~`tenant_id`~~ | — | — | `[정정 2026-09-10]` **없다.** 요청 몸통에서 지웠다 — 테넌트는 인증(`principal.tenant_id`)에서만 온다. 보내면 `extra="forbid"` 라 거부된다(`app/presentation/api/cases.py:29-40`) |
| `customer_id` | string (**UUID**) | `"3f2c…"` | 필수 — `[정정 2026-09-10]` 예시가 `"cust_01"` 이었는데 UUID 가 아니라 거부된다 |
| `message` | string | `"배송완료로 떴는데 상품을 못 받았어요"` | `[미확보]` |
| `channel` | string | `"personal_ai"` | `[미확보]`; `personal_ai \| mcp \| web \| api` 중 하나 |
| `subject_ref` | object \| null | `{"kind":"trip","id":"<uuid>"}` | 선택 — `[결정 2026-09-17]` 이 Case 가 **무엇에 대한 것인지**. 아래 절 |

### `subject_ref` — Case 가 가리키는 대상 `[결정 2026-09-17]`

Case 버전만으로 여행 일정을 관리하려면 Case 가 「어느 여행의 어느 항목」인지 알아야 한다(v11 §4-B 「Case 에 `trip_id`」). 코어는 도메인 어휘를 모르므로 **이름이 중립인 칸 하나**로 받는다.

| 칸 | 타입 | 필수 | 뜻 |
|---|---|---:|---|
| `kind` | string | 예 | 대상 종류(도메인 어휘 — 여행은 `trip`) |
| `id` | UUID | 예 | 대상 id |
| `part_id` | UUID \| null | 아니오 | 대상 안의 한 부분(여행은 일정 항목 `item_id`) |
| `base_version` | int \| null | 아니오 | 고객이 **본** 대상 버전 — 그 사이 바뀌었으면 적용하지 않는다 |
| `request` | object \| null | 아니오 | 화면 버튼처럼 **구조가 정해진 요청**(여행은 `{"type":"change","choice":…}`·`{"type":"rollback","to_version":n}`). 자유 문장이면 비운다 |

- ★**서버가 확인한다.** 조립이 주입한 **대상 확인기**가 그 대상이 이 테넌트·이 고객의 것인지 본다. 아니면 `404 not_found`(있는지도 말하지 않는다). 확인기가 없는 조립에서 `subject_ref` 를 보내면 `422 subject_ref_unsupported` — **조용히 무시하지 않는다.**
- 확인기는 **라우팅 힌트**(대상 부분의 종류)를 돌려줄 수 있다. 두 종류다.
  - **확인된 힌트** — 클라이언트가 `part_id` 를 지정했고 서버가 그 항목을 확인했다. 그 종류는 사실이라 **분류보다 우선한다**(화면 버튼이 보낸 문장에 분류가 아무 접두나 붙여도).
  - **짐작한 힌트** — `part_id` 가 없어 확인기가 「가장 최근에 바뀐 항목」으로 짐작했다. 분류가 **객체 접두를 못 붙였을 때만**(`issue_code` 에 `_` 가 없을 때 — 예: `other`) 쓴다.
- ★**문장 해석이 분류보다 먼저다** `[2026-09-17]`. 조립이 **대상 해석기**(`app/core/subjects.py` `SubjectInterpreter`)를 주입했으면, 대상이 정해진 고객 Case 는 분류 직전(트랜잭션 밖)에 문장을 해석한다. 해석이 담당을 내면 **확인된 힌트**로 기록해 분류 접두보다 우선한다. 해석 결과는 분류와 **같은 `CLASSIFIED` 이벤트**의 `state_patch` 로 `state_json.interpretation` 에 남고, Team 은 그것을 다시 추출하지 않고 쓴다.
  - 여행: 신고 종류로 담당을 정한다 — 늦음·휴무 → dining, 품절 → activity, 바꿔 줘·되돌려 줘 → 지정한 항목(없으면 가장 최근에 바뀐 항목)의 종류. 그 밖(`other`)은 힌트를 내지 않고 분류로 간다. 구조가 정해진 `request` 는 모델을 부르지 않는다.
  - 해석기가 예외를 내면 `interpretation.error` 로 남기고 분류 경로로 간다(삼키지 않는다).
  - 왜: 실제 gemma4:12b 로 재 보니(문장마다 3회, 같은 결과) 신고 추출은 7문장 모두 맞는데 분류 접두는 3문장이 빗나가 사람에게 넘어갔다 — [이식 검증](../../records/evidence/CASE-VERSION-ITINERARY_이식검증.md).
- 저장 자리는 `customer_cases.state_json.subject_ref` 이고, Team 은 `ContextPack.current_state.subject_ref` 로 받는다(계약 칸 추가 없음 — `current_state` 는 dict).

성공 응답 상태 코드는 `201`이다.

| 응답 필드 | JSON 타입 | 예시 |
|---|---|---|
| `case_id` | string | `"case_01"` |
| `status` | string | `"classifying"` |
| `version` | number | `1` |
| `intent` | string | `"shipping"` |
| `issue_code` | string | `"shipping_delivered_not_received"` |
| `sentiment` | string | `"negative"` |
| `links.self` | string | `"/v1/cases/case_01"` |

`[정정 2026-09-10]` **클라이언트가 `idempotency_key` 를 보내면 그 값을 쓴다.** 안 보냈을 때만 서버가 `request_id` 로 계산한다(`cases.py:106-111`). 「서버가 재계산하며 클라이언트 값은 재료일 뿐」은 2026-09-01 이전 동작이다. 같은 키로 재요청하면 새 Case를 만들지 않고 기존 결과를 그대로 반환한다.

근거: `wiki/records/handoff/03_REST_MCP_인터페이스.md:47-67`

## `GET /v1/cases` 쿼리 계약

`[실측]`

| 쿼리 필드 | 필수 | 기본값·제약 |
|---|---:|---|
| `customer_id` | 예 | 호출자의 소유 범위 검사 |
| `status` | 아니오 | `[미확보]` 허용값 |
| `limit` | 아니오 | 기본값 `20`, 최대 `100` |
| `cursor` | 아니오 | `[미확보]` 형식 |

호출자의 tenant·customer 범위 밖 Case를 반환하지 않는다.

근거: `wiki/records/handoff/03_REST_MCP_인터페이스.md:68-71`

## `GET /v1/cases/{case_id}` 응답 계약

`[실측]`

| 필드 | 형태·예시 |
|---|---|
| `case_id` | `"case_01"` |
| `status` | `"waiting_approval"` |
| `version` | `7` |
| `answer` | `"환불 요청을 준비했습니다."` |
| `pending_actions[]` | `{"action_id":"a_01","action_type":"refund.request","approval_required":true}` |
| `evidence[]` | `{"source_type":"policy","source_id":"doc_04#c12","claim":"..."}` |

`evidence`는 masked 상태로 반환한다. 원문 PII를 응답에 싣지 않으며, `answer`가 있는데 `evidence`가 비어 있으면 계약 위반이다.

근거: `wiki/records/handoff/03_REST_MCP_인터페이스.md:73-84`

## 추가 메시지 resume 제약

`[2026-10-11 수정 계약]` 추가 답변의 `message`와 `expected_version`을 재개 처리에 전달합니다.
질문·필수 입력은 `waiting_input`에 보존하며, 같은 Case에서 마스킹한 답변을 팀에 전달합니다.
웹 여행 메시지는 선택적인 `case_id`, `resume_token`, `expected_version`을 받고,
누락 시 해당 여행·고객의 단일 대기 업무만 연결합니다. 여러 대기 업무가 있으면 409입니다.
일정 변경·신고·되돌림은 등록된 Team 실행과 Controller의 제안 적용 경로를 사용합니다.
상세 계약: [웹 업무 실행과 추가 답변](../../records/reports/2026-10-11_conversation_resume_contract.md).

`[실측]`

| 항목 | 제약 |
|---|---|
| 상태 전이 | `waiting_input` → `resuming` |
| resume token 저장 | 원문이 아니라 hash만 저장 |
| TTL | `24h` |
| 사용 횟수 | 일회성 |
| 중복 처리 | 동일 `event_id` 재처리는 idempotent |
| TTL 만료 | 자동 진행 금지; `escalated` + 운영자 알림 |

`[2026-10-11 구현]` Case 메시지 본문은 `request_id`, `message`, 선택적인 `token`,
`expected_version`을 받는다. `token`이 없으면 `case:write` 권한과 같은 테넌트 Case 조회를
통과한 고객 입력 대기 업무에만 인증된 재개를 허용한다. 승인·외부 콜백 대기를 이 방식으로
재개하지 않는다. 웹 여행 메시지에서는 토큰 필드 이름이 `resume_token`이다.

근거: `wiki/records/handoff/03_REST_MCP_인터페이스.md:86-90`

## 승인 요청·감사 계약

`[실측]`

요청:

```json
{"decision":"approved","approver_id":"op_01","note":"정책 확인함"}
```

| 필드 | 제약 |
|---|---|
| `decision` | `approved \| rejected` |
| `approver_id` | `[미확보]` 필수 여부·타입 제약 |
| `note` | `[미확보]` 필수 여부·길이 제약 |

승인 event와 before/after hash를 audit에 기록한다. audit에는 API key 원문이나 결제 식별자 원문을 기록하지 않는다. 승인 후 실행은 idempotent해야 하며 동일 요청 10회에 side effect는 1회다.

근거: `wiki/records/handoff/03_REST_MCP_인터페이스.md:92-99`

## `POST /v1/outbox/{message_id}/resolve` 계약

`[실측]` `app/presentation/api/outbox.py`. 2026-08-24 추가 — 이 문서가 "다섯 경로"라고 적혀 있던 동안 빠져 있었다.

**`unknown`으로 남은 발행 건을 사람이 봤고 판단했다는 기록이다.** 재처리하지 않는다.

| 항목 | 계약 |
|---|---|
| scope | `action:approve` |
| 요청 body | `resolution`: `confirmed_delivered` \| `confirmed_not_delivered` · `note`(1자 이상) · `resolved_by`(1자 이상). `extra="forbid"` |
| 대상 행 | `status='unknown'` **이고** `resolved_at IS NULL` 인 행만. tenant 조건 포함 |
| 바뀌는 것 | `resolved_at`·`resolved_by`·`resolution_note`·`resolution` **만**. `status`는 `unknown` 그대로, provider 발행 없음 |
| `422` | `note_required` · `resolved_by_required` (공백만 있어도) |
| `409 invalid_status` | 행은 있는데 `unknown`이 아니거나 이미 해소됨 |
| `404` | 행이 없거나 다른 tenant |

**"기록만"이 설계다.** 해소했다고 시스템이 대신 재시도하면 `unknown`을 만든 이유(돈이 나갔는지 모름)가 무너진다. → [../actions/outbox.md](../../actions/outbox.md)


## 관계

- [REST 안내](index.md) — 계약 지도
