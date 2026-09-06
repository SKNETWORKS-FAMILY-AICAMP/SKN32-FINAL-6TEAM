---
type: contract
title: REST API
description: 엔드포인트 5개와 헬스체크. 쓰기는 여기로만 간다
status: draft
tags: [api, contract]
owners: [human:미배정]
---

# REST API

`app/presentation/api/cases.py`

**쓰기는 REST로만 간다.** MCP는 read-only다.

## 엔드포인트

`[실측]`

| 메서드 | 경로 | 무엇 |
|---|---|---|
| `POST` | `/v1/cases` | Case 생성 (문의 접수) |
| `GET` | `/v1/cases` | Case 목록 |
| `GET` | `/v1/cases/{case_id}` | Case 상세 |
| `POST` | `/v1/cases/{case_id}/messages` | 추가 메시지 |
| `POST` | `/v1/cases/{case_id}/actions/{action_id}/approve` | **승인** |
| `POST` | `/v1/outbox/{message_id}/resolve` | `unknown` 발행 건을 사람이 정리했다고 **기록만** 한다 (2026-08-24 추가) |

`+ /health`

`[실측]` 경로 5개 · operation 6개다. 마지막 줄이 2026-08-24에 늘어난 것이고, 그때 테스트의 계약 목록(`CONTRACT_V1_PATHS`)도 함께 갱신됐다. → [rest-endpoints.md](rest-endpoints.md)

**MVP 5개가 상한이 아니다.** 필요하면 늘리되 scope와 테스트를 함께 만든다.

### ★ [2026-09-03] 계약 문서가 반대로 적고 있다

`[실측]` `docs/handoff/03_REST_MCP_인터페이스.md` §1-0 은 이렇게 적었다.

> `/v1/` 아래에 **6번째 경로가 생기면 그것은 위반이다** — `tests/integration/api/test_openapi_surface.py` 가 검사한다.

**테스트를 열어 보니 반대다.**

```python
def test_new_paths_are_allowed_but_must_be_scoped()
def test_v1_surface_is_documented_when_it_grows()
```

**이름이 `new_paths_are_allowed` 다.** 검사하는 건 **"늘어나도 되는데 scope 가 있어야 한다"**이지 "늘면 안 된다"가 아니다.

| | 무엇을 말하나 |
|---|---|
| 계약 문서 §1-0 | 6번째는 위반 |
| **테스트 · 이 wiki · [dod.md](../../../wiki/delivery/dod.md) 13번** | **늘려도 된다. scope 와 테스트를 같이 만들면** |

**셋 중 하나만 낡았다.** → 계약 문서를 고쳐야 한다.

`[실측]` **이미 한 번 늘었다.** 2026-08-24 `/v1/outbox/{message_id}/resolve`가 추가돼 지금 `/v1/*`은 경로 5개·operation 6개다. "아직 아무도 안 걸렸다"가 아니라 **계약 목록을 같이 갱신했기 때문에** 안 걸린 것이다 — 테스트 파일 머리에 규칙이 적혀 있다.

> 계약에 적힌 경로는 **전부 있어야 한다**(누락은 여전히 결함). 새 경로는 막지 않는다. 대신 **품질 조건**을 검사한다.

`[실측]` 2026-09-06 테스트를 읽다 둘을 봤다. `test_v1_surface_is_documented_when_it_grows`는 docstring이 "실패시키지 않는다"인데 코드는 `assert extra == []`다 — **실제 동작은 "계약 목록 갱신 없이 늘리면 실패"**이고, 그게 맞는 쪽이다. 그리고 `test_new_paths_are_allowed_but_must_be_scoped`는 루프 안에서 `unscoped`에 아무것도 넣지 않아 **항상 통과한다** — scope 강제는 그 아래 `test_write_endpoints_require_a_scope_dependency`가 라우트 의존성으로 실제 검사한다. → [../quality/blind-spots.md](../quality/blind-spots.md)

## 승인은 REST 전용

**마지막 엔드포인트가 유일한 승인 경로다.** MCP에는 없다.

승인자는 `action:approve` scope가 있어야 한다. → [../actions/approval.md](../actions/approval.md)

`[실측]` **승인 엔드포인트가 읽기 권한으로 열리는 결함**을 dojo가 심어 봤고 테스트 11건이 잡았다.

## Case 생성 시 인라인 분류

`POST /v1/cases`가 감성·의도·이슈 분류를 함께 한다. **선택 기능이 아니다.**

```
분류 성공 → routing
분류 실패 → classification_failed 이벤트 + escalated
```

**조용히 넘어가지 않는다.** `INV-CS-RT-017`

`[실측]` 이 경로에서 실제 결함이 있었다. `feedback.py::INTENTS`가 옛 구독 어휘(`billing`/`technical`)로 남아 있어 **쇼핑몰 Case가 전부 분류 실패로 떨어졌을 것**이다. 재발 방지로 `INTENTS ⊇ 모든 Team.accepted_case_types` 불변조건 테스트가 추가됐다.

### ★ [2026-09-06] 이 결함이 왜 운영 경로였는가, 그리고 어떻게 다시 안 나게 했는가

`[실측]` [PROD-CLASSIFIER-DOMAIN-MISMATCH](../../docs/evidence/PROD-CLASSIFIER-DOMAIN-MISMATCH_수정.md). `INTENTS`는 VOC 분석 전용 상수가 아니다.

```
create_app()  →  composition.build_classifier()  →  feedback.classify(masked(message))
                 (classifier 인자가 없으면 기본값)      ↑ 여기서 INTENTS 로 검증
```

**이게 `/v1/cases`로 들어오는 모든 신규 Case의 실제 분류 경로다.** LLM이 정직하게 `shipping`을 돌려주면 옛 집합 밖이라 `ClassificationFailed` — 안전하게 `escalated`로 가긴 하지만 정상 라우팅은 하나도 안 됐을 것이다.

`[미확보]` **얼마나 오래 있었는지는 모른다.** 이 파일을 건드린 커밋이 최초 도메인 전환 하나뿐이라 커밋 이력으로 특정이 안 된다.

`[미확보]` 재발 방지 테스트(`tests/unit/voc/test_feedback_intent_alignment.py`)는 있지만 **[invariants.md](../quality/invariants.md) 카탈로그에 ID가 없다.** "INTENTS ⊇ 모든 Team의 `accepted_case_types`"는 라우팅이 성립하는 조건이라 불변식으로 올릴 만하다.

### 실제 API 경로를 진짜로 도는 e2e 테스트

`[실측]` [LIVE-CLASSIFIER-E2E](../../docs/evidence/LIVE-CLASSIFIER-E2E_검증.md). 위 수정 직후엔 Claude가 터미널에서 한 번 수동 확인한 것뿐이었다. 그걸 재실행 가능한 테스트로 바꿨다 — `tests/live/test_feedback_classifier_live_e2e.py`(`-m live`, 실 OpenAI 호출).

**증명하는 것** — 운영 `POST /v1/cases`에 실 한국어 쇼핑몰 메시지를 보내면, 실제로 주입되는 그 classifier가 `intent="shipping"`을 돌려주고 `INTENTS` 검증을 통과해 `CLASSIFIED` 이벤트가 기록된다.

**만들다 계약의 오해가 둘 드러났다.**

| 오해 | 실제 |
|---|---|
| `create_app(controller=None)`이면 Controller가 안 돈다 | **항상 진짜 Controller가 만들어진다.** classifier를 밖에서 주입하지 않으면 기본 classifier의 `__module__`이 `app.composition`이라 `runtime_controller`가 진짜로 잡힌다 — 이 테스트는 분류뿐 아니라 **Team 실행까지 전부 탄다** |
| 최종 상태가 `escalated`가 아니어야 통과 | 합성 고객이라 주문 데이터가 없으니 Team이 정상적으로 escalate할 수 있다. **분류 성공 여부만** 보도록 좁혔다 — `case_events`의 `CLASSIFIED`를 직접 조회 |

첫 실행이 "실패"했는데 **분류 자체는 완벽했다** — 틀린 건 테스트의 단언 범위였다.

`[실측]` **teardown이 `agent_runs`·`team_tasks`·`llm_calls`를 안 지워 FK 위반으로 정리 자체가 실패했고, 첫 실행분 tenant 하나가 DB에 영구히 남았다.** Controller가 실제로 도니 그 행들이 생기는데 계약에 없었다. 손으로 같은 FK 순서로 지웠고, 정리 순서를 고쳤다. **"실행되지 않는다"는 가정이 틀리면 정리 계획도 같이 틀린다.**

## Composer API는 별개다

```
/composer/*    prefix="/composer", tags=["composer-write"]
```

**제작 단계 도구다.** 인증된 경로로만 제공한다.

★**[실측 2026-09-07] 고객 릴리즈 앱에는 이 경로가 아예 없다.** 커밋 `f2319aa`(v9 §8-D) 뒤로
`create_app()`은 라우터를 **주입받을 때만** 붙인다(`composer_write_router` · `composer_auth_router`,
기본값 `None`). 고객이 받는 `app.presentation.api.app:app`은 아무것도 주지 않으므로 `/composer/*`가
**존재하지 않는다** — 인증으로 막는 게 아니라 라우트 자체가 없다.

붙는 것은 관리용 빌드(`app/entrypoint.py`)뿐이고, 그때만 `acop_composer` 패키지의 라우터를
주입한다. 구현은 이 저장소에 없다(`app/composer_host.py`가 어댑터만 갖는다).
경계는 `tests/architecture/test_composer_stays_out_of_this_repo.py`가 지킨다.

`[실측]` `/ui/composer`는 2026-08-18에 **폐기**됐다. 인증 없이 고객 접근이 가능한 앱에 물려 있던 것을 실측으로 확인하고 삭제했다.

## 인증

모든 요청이 Agent Gateway를 거친다. **Trust Boundary다.**

| 불변식 | 무엇 |
|---|---|
| `INV-CS-SEC-001` | 유효하지 않은 토큰은 인증되지 않는다 |
| `INV-CS-SEC-002` | scope 없는 principal은 거부된다 |
| `INV-CS-SEC-003` | 다른 scope를 가진 principal도 거부된다 |

`[실측]` **인증 전 요청이 500을 내던 결함**이 있었다. `os.getenv`로 설정을 읽어서였다. 지금은 고쳐졌다.

→ [auth-boundary.md](auth-boundary.md)

## 조회 격리

목록·상세 조회는 tenant와 customer를 벗어나지 않는다.

| 불변식 | 실행 위치 |
|---|---|
| `INV-CS-SEC-005` | `tests/security/test_query_scope.py::test_case_list_does_not_leak_across_customers_in_one_tenant` |
| `INV-CS-SEC-006` | `tests/security/test_query_scope.py::test_case_list_without_customer_stays_inside_the_tenant` |

**남의 Case를 요청하면 404다.** 403이 아니다 — 존재 여부를 알려주지 않는다.

## idempotency

`POST` 계열은 전부 idempotency key를 거친다.

**동일 요청 10회 → `action_requests` 1행.** DoD 항목이다.

→ [../actions/idempotency.md](../actions/idempotency.md)

## 감사

`[실측]` **승인 감사 기록이 대기 큐에 유령 항목으로 남는 결함**이 있었다. 브라우저로 승인 버튼을 여러 번 눌러 발견했다.

```
tests/integration/api/test_approval_audit_row_excluded_from_queue.py
tests/integration/api/test_case_create_audit_row_excluded_from_queue.py
```

**테스트만으로는 안 잡혔다.** UI를 실제로 열어야 나온 결함이다.

---

# 계약 원문에서 보강 (2026-09-03)

`[실측]` `docs/handoff/` 계약 문서와 절 단위로 대조해 **빠져 있던 필드·제약·숫자**를 채웠다. 대조 결과는 [반영률 실측](../../../wiki/governance/migration-scope/coverage.md).

## `/v1/*` 표면 상한과 scope

`[실측]` 계약 문서(`docs/handoff/03` §1-0)는 "외부 AI용 `/v1/*` endpoint는 정확히 5개, 여섯 번째 경로가 생기면 계약 위반"이라고 적는다. **이 문장은 낡았다** — 위 [2026-09-03 절](#-2026-09-03-계약-문서가-반대로-적고-있다)이 밝힌 대로 v7에서 "5는 상한이 아니다"로 바뀌었고, 실제로 2026-08-24에 여섯 번째 operation이 추가됐다. 아래 표가 지금 코드의 계약 집합이다.

| 메서드 | 경로 | 필수 scope |
|---|---|---|
| `POST` | `/v1/cases` | `case:write` |
| `GET` | `/v1/cases` | `case:read` |
| `GET` | `/v1/cases/{case_id}` | `case:read` |
| `POST` | `/v1/cases/{case_id}/messages` | `case:write` |
| `POST` | `/v1/cases/{case_id}/actions/{action_id}/approve` | `action:approve` |
| `POST` | `/v1/outbox/{message_id}/resolve` | `action:approve` |

다음 경로는 5개를 셀 때 제외한다.

| 경로 | 성격 |
|---|---|
| `/health` | 상태 확인 |
| `/ui/*` | 운영 화면 |
| `/openapi.json`, `/docs`, `/redoc` | FastAPI 기본 제공 |

`/ui/*`는 쓰기를 직접 수행하지 않는다. 승인은 `/v1/cases/{case_id}/actions/{action_id}/approve`를 호출한다.

근거: `docs/handoff/03_REST_MCP_인터페이스.md:18-45`

## 엔드포인트별 상세 계약

**필드·제약·상태 전이는 [rest-endpoints.md](rest-endpoints.md) 에 있다.** operation 여섯(경로 다섯)을 각각 다룬다.

## 오류 응답 계약

`[실측]`

| HTTP | 조건 | `error.code` |
|---:|---|---|
| `400` | 스키마 위반 | `contract_violation` |
| `401` | API key 없음 또는 무효 | `unauthenticated` |
| `403` | scope 부족 또는 ownership 불일치 | `scope_denied` |
| `404` | 존재하지 않거나 볼 권한이 없는 리소스 | `not_found` |
| `409` | optimistic concurrency 충돌 | `state_conflict` |
| `422` | 허용되지 않은 상태 전이 | `invalid_transition` |
| `429` | 일일 비용 또는 호출 상한 | `guardrail_exceeded` |

오류 body에 stack trace·SQL·내부 경로를 넣지 않는다.

근거: `docs/handoff/03_REST_MCP_인터페이스.md:101-114`

## 인증 형식

`[실측]`

| 항목 | 계약 |
|---|---|
| MVP 인증 | hashed API key + scope |
| Header | `Authorization: Bearer <api_key>` |
| OAuth2/OIDC | Phase 2; MVP에서 구현하지 않음 |
| scope 검증 | scope × endpoint 전체 unauthorized matrix 테스트 |

근거: `docs/handoff/03_REST_MCP_인터페이스.md:116-121`

## OpenAPI 일치 조건

`[실측]` `/openapi.json`의 `/v1/*` 경로 집합은 테스트의 `CONTRACT_V1_PATHS`(경로 5개, outbox resolve 포함)와 **정확히 일치해야 한다** — 계약에 있는데 없으면 실패, 계약 목록에 없는 게 있어도 실패. 늘릴 땐 계약 문서·이 목록·scope 의존성을 같이 만든다.

근거: `docs/handoff/03_REST_MCP_인터페이스.md:150-153`

## `GET /introspection`

`ops:introspect` scope 로 보호되는 read-only API 다. **무엇이 조립돼 있나를 보여주고 얼마나 돌고 있나는 안 보여준다.**

→ [introspection.md](introspection.md)

## 관계

- [mcp-tools.md](mcp-tools.md) — 읽기 전용 경로
- [a2a-protocol.md](a2a-protocol.md) — 업무 위임 경로
- [auth-boundary.md](auth-boundary.md) — 인증·scope·PII
- [../actions/approval.md](../actions/approval.md) — 승인
- [../runtime/case-lifecycle.md](../runtime/case-lifecycle.md) — Case 상태
