---
type: guide
title: 테스트 지도
description: 어떤 검사가 어디 있는가. 폴더 최상위만 보면 있는 테스트도 못 찾는다
status: draft
tags: [testing]
owners: [human:미배정]
---

# 테스트 지도

**이 문서가 필요한 이유가 있다.**

`[실측]` 불변식 카탈로그 초판에서 "Runtime 불변식은 테스트로 강제되지 않는다"고 적었는데 **틀렸다.** 테스트는 `tests/integration/db/`, `tests/unit/core/`, `tests/contract/`에 흩어져 있었다. `tests/integration/` 최상위에 `__init__.py`만 있는 걸 보고 비어 있다고 판단한 실수였다.

**지도가 없으면 있는 것도 못 찾는다.**

## 전체 구조

`[실측]` 2026-09-01 기준 70개 파일

```text
tests/
├─ architecture/   2   계층 경계
├─ contract/       7   계약·상태표·격리·idempotency
├─ security/       4   인증·스코프·PII
├─ unit/          28   core/ 하위에 상태 기계와 예산
├─ integration/   22   a2a api controller db graph llm messaging rag
├─ e2e/            4   Composer·introspection·UI
└─ live/           3   실 LLM 호출
```

**`integration/`과 `unit/`은 하위 폴더가 있다.** 최상위만 보면 안 된다.

## 무엇을 어디서 검사하는가

| 검사 대상 | 위치 | 대표 파일 |
|---|---|---|
| Core 도메인 격리 | `architecture/` | `test_basement_is_domain_free.py` |
| 다른 도메인 서빙 가능성 | `architecture/` | `test_engine_serves_another_domain.py` |
| Case 상태 기계 | `contract/` | `test_case_state_table.py` |
| 상태 축약(reducer) | `unit/core/` | `test_case_reducer.py` |
| **동시 쓰기 충돌 (CAS)** | `integration/db/` | `test_stale_write_conflict.py` |
| 실행 유일성 | `integration/controller/` | `test_active_run_uniqueness.py` |
| Context 예산 | `unit/core/` | `test_context_budget.py` |
| idempotency | `contract/` | `test_consumer_idempotency_contract.py` |
| Team 계약 | `contract/` | `test_team_contract.py` |
| Core가 modules를 import 안 함 | `contract/` | `test_core_isolation.py` |
| 인증·스코프 | `security/` | `test_auth_and_scope_guards.py` |
| PII 마스킹 | `security/` | `test_pii_redaction_runtime.py` |
| tenant·customer 격리 | `security/` | `test_query_scope.py` |
| MCP 도구 수 고정 | `security/` | `test_scope_contract.py` |
| outbox 해소 | `integration/api/` | `test_outbox_resolution.py` |
| outbox tenant 격리 | `integration/messaging/` | `test_outbox_tenant_guard.py` |
| 제공자 timeout | `integration/controller/` | `test_provider_timeout_unknown.py` |
| 실행 직전 재확인 | `integration/api/` | `test_recheck_before_execution.py` |
| 제안 차단 | `integration/controller/` | `test_proposal_guard_blocks.py` |
| A2A 왕복 | `integration/a2a/` | `test_remote_round_trip.py` |
| SQL Graph Adapter | `integration/graph/` | `test_sql_graph_adapter.py` |
| RAG | `integration/rag/` | `test_rag_integration.py` |
| LLM 호출 감사 | `integration/llm/` | `test_llm_call_audit_wiring.py` |
| Composer 쓰기채널 | `e2e/` | `test_composer_write_channel.py` |

## 불변식과의 연결

`[실측]` 불변식 51개 중 **48개가 위 테스트에 연결돼 있다.**

연결 상태는 [invariants.md](invariants.md)에 있고, **검사기가 실제로 파일과 함수 존재를 확인한다.**

```bash
python program/scripts/check_wiki.py
```

이 명령이 검사하는 것.

```text
1. 불변식이 가리키는 테스트 파일이 실재하는가
2. 그 파일에 해당 test 함수가 실재하는가
3. 코드의 invariant 표식이 카탈로그에 있는가
4. 링크·front matter·문서 크기
```

## ★ 아직 없는 것 — 코드 쪽 역방향 표식

`[실측]` **검사기가 세어 보니 0개다.**

문서는 테스트를 가리키는데 **테스트는 자기가 어떤 불변식을 지키는지 밝히지 않는다.** 단방향이다.

넣어야 할 모양.

```python
# invariant: INV-CS-RT-009
def test_two_writers_that_read_the_same_version_produce_exactly_one_conflict():
    ...
```

**왜 필요한가.** 테스트를 지우거나 이름을 바꿀 때, 그게 어떤 불변식을 깨는지 그 자리에서 보인다. 지금은 문서를 열어야 안다.

`[미확보]` 48개 테스트에 표식을 넣는 작업이 남았다. 검사기는 이미 준비돼 있다.

## 테스트가 없는 곳

| 대상 | 상태 |
|---|---|
| Team 경계 3개 (`INV-CS-TEAM-003~005`) | `review`. import 검사로 자동화 가능해 보임 |
| 그 외 | [blind-spots.md](blind-spots.md) |

## 관계

- [invariants.md](invariants.md) — 불변식 카탈로그
- [blind-spots.md](blind-spots.md) — 검사가 없는 지점
- [../../../acop_dojo/wiki/index.md](../../../acop_dojo/wiki/index.md) — 사각지대를 실행으로 찾는 프로그램
