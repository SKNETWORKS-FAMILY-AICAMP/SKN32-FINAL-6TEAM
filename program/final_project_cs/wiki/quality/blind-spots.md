---
type: report
title: 테스트 사각지대
description: 불변식을 어겼는데 테스트가 울지 않는 지점. acop_dojo가 실행으로 찾아낸다
status: draft
tags: [testing]
owners: [process:dojo-report]
automation:
  command: acop-dojo report
  owner: process:dojo-report
  manual_edit: false
---

# 테스트 사각지대

**이 문서는 요약이다.** 정본은 자동 생성물이다.

```bash
acop-dojo report
```

원본: `program/research/테스트_사각지대_실측.md` · 카탈로그: `acop_dojo/acop_dojo/defects/catalog.json`

**손으로 고치지 않는다.**

## 어떻게 찾는가

```text
원본 저장소
   ↓ 임시 사본 (원본 불변)
불변식을 어기는 최소 변경을 심는다
   ↓ 전체 테스트 실행
테스트가 우는가?
   ├─ 운다   → 정상. 그 규칙은 지켜지고 있다
   └─ 안 운다 → ★ 사각지대
```

**사람이 찾기 어려운 종류의 정보다.** 테스트가 있다는 것과 테스트가 잡는다는 것은 다르다.

## 현재 결과

`[실측]` revision `git:04f6634` · 기준선 486 passed

| | |
|---|---|
| 심어 본 변경 | 49건 |
| 분모에 센 것 | 48건 |
| **테스트가 잡은 것** | **48건** |
| **생존한 것 (사각지대)** | **0건** |

**등록된 활성 결함 중 생존한 것이 없다.**

## ★ 이 0이 무엇에 대한 0인가

원본 문서가 스스로 못박고 있다.

> 이 숫자는 저장소의 **테스트 커버리지가 아니다.** 사람이 고른 48개 가설에 대한 검출률이다. **카탈로그에 없는 규칙은 여전히 보이지 않는다.**

**이 문장이 이 도구의 정직함이다.** 0건이라고 안전한 게 아니라, **우리가 물어본 48가지에 대해서만 0건**이다.

## 분모에서 뺀 것

`[실측]` 1건을 뺐다. 이유를 밝히는 게 규칙이다.

> 뺀 것을 밝히지 않으면 0이라는 수치가 무엇에 대한 0인지 알 수 없다.

**`INV-CLASS-002`** — 잡을 수 없다. API 쪽 검사를 지워도 `domain/case.py`의 `validate_payload`가 같은 필드를 다시 검사해 `InvalidTransition`을 던진다. **관찰 가능한 동작이 안 바뀌는 중복 방어 제거**다.

이런 걸 subsumed mutant라고 한다. 진짜 결함은 값 검증 쪽에 따로 있고 별도 리포트로 남았다.

## 잡힌 것 — 대조군 일부

`[실측]` 어떤 변경이 어떤 테스트에 걸리는지.

| 심은 결함 | 깨지는 테스트 |
|---|---|
| 승인 대기인데 제안이 없어도 통과 | `test_wait_for_approval_needs_at_least_one_proposal` |
| Bearer 형식 검사 제거 | `test_any_seven_character_prefix_must_not_authenticate` |
| 승인 엔드포인트가 읽기 권한으로 열림 | `test_approval_uses_rest_endpoint` 외 10건 |
| ContextPack 예산 상한 두 배 | `test_context_pack_rejects_over_budget` |
| 분류 실패의 사유를 잃음 | `test_create_escalates_when_injected_classifier_fails` |
| 제안이 근거 id를 안 담음 | `test_proposal_carries_the_evidence_it_was_built_from` |
| 배송 상태를 모르는데 아는 척 답함 | `test_unknown_shipment_status_escalates_instead_of_answering` 외 2건 |
| 조회 건수를 세지 않고 0으로 답함 | `test_tracking_answer_counts_the_shipments_it_read` |

**"모르는데 아는 척"과 "안 세고 0으로 답함"이 특히 이 프로젝트다운 결함이다.**

## 지금 보이는 사각지대

카탈로그가 아직 안 다루는 영역. [invariants.md](invariants.md) 기준.

| 불변식 | 판정 | 왜 카탈로그에 없나 |
|---|---|---|
| `INV-CS-TEAM-003` | review | side effect 실행을 정적으로 잡는 테스트가 없다 |
| `INV-CS-TEAM-004` | review | read 도구 직접 호출을 잡는 테스트가 없다 |
| `INV-CS-TEAM-005` | review | Team 간 직접 호출을 잡는 테스트가 없다 |

**셋 다 심을 결함은 만들 수 있는데 잡을 테스트가 없다.** 그래서 카탈로그에 올리면 생존한다.

`[추정]` `tests/architecture/test_basement_is_domain_free.py`가 이미 import 검사를 하므로 같은 방식으로 셋 다 자동화 가능해 보인다.

## 유지하는 법

원본 문서의 결론.

> 새 규칙을 만들 때 **그 규칙을 어기는 변경도 함께 만들어** 게이트에 걸어 본다. 규칙만 늘리고 세는 곳을 안 만들면 다시 벌어진다.

**불변식을 추가할 때 결함도 같이 추가한다.** 이게 카탈로그가 낡지 않게 하는 방법이다.

## ★ [2026-09-03] 테스트가 동시 실행에 약하다

`[실측]` 같은 코드로 두 번 돌렸는데 결과가 달랐다.

| 언제 | 결과 |
|---|---|
| 다른 작업 3개가 동시에 돌 때 | **29 failed, 560 passed** |
| 단독 | **591 passed** (두 번 확인) |

실패한 것이 전부 DB 를 만지는 쪽이었다.

```
integration/api/test_openapi_surface.py       5
integration/api/test_api_runtime.py           4
security/test_pii_redaction_runtime.py        1
integration/api/test_case_create_audit_row…   1
```

`[미확보]` **원인을 확정하지 못했다.** 재현이 안 된다. 후보는 셋이다.

```
같은 Postgres 를 여러 프로세스가 만진다
tenant 이름이 겹친다
앞선 테스트의 teardown 이 안 끝난 채 다음이 시작된다
```

**이게 위험한 이유는 실패가 아니라 "가끔 통과"다.** CI 가 초록인데 실제로는 불안정할 수 있다.

`[미확보]` **CI 가 이 상황을 재현하는지 확인 안 했다.** 병렬 실행(`-n auto`)을 쓰면 상시로 겪는다.

## 관계

- [invariants.md](invariants.md) — 불변식 카탈로그
- [test-map.md](test-map.md) — 테스트 위치
- [../../../acop_dojo/wiki/index.md](../../../acop_dojo/wiki/index.md) — 생성 프로그램
