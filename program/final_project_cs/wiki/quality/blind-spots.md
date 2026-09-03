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

## ★ [2026-09-03] 테스트가 제품을 잘못 끌고 간 사례

`[실측]` `docs/handoff/09_Composer_GUI_계약.md` 에서 이관.

**테스트가 없어서 못 잡는 것만 사각지대가 아니다. 있는 테스트가 틀린 것을 검사하면 더 나쁘다.**

### 무슨 일이 있었나

`test_composer_is_404_when_disabled` 가 `config/project.yaml` 을 **그대로 읽어** 404 를 단언했다.

```
테스트를 통과시키려면      저장소 기본값이 꺼짐이어야 한다
그런데 정작 쓰려는 구성기가  계속 404 였다
기본값을 켜려는 시도가      테스트 실패로 되돌려졌다
```

**테스트가 기능을 막았다.**

### 무엇이 틀렸나

| | |
|---|---|
| 검사하려던 성질 | **"선언이 false 면 라우트가 없다"** |
| 실제로 검사한 것 | **"저장소 기본값이 false 다"** |

**둘이 다르다.** 앞은 동작이고 뒤는 설정값이다.

**고친 방법** — 임시 선언을 만들어 그 성질만 검사한다. 저장소 기본값은 안 건드린다.

### 규칙

> **테스트가 검사하는 것이 의도한 성질인지 확인하라.**
>
> **아니면 테스트가 제품을 잘못된 방향으로 끌고 간다.**

`[실측]` **이건 [test-map.md](test-map.md) 가 못 잡는 종류다.** 불변식과 테스트가 연결돼 있어도, **그 테스트가 다른 것을 재고 있으면** 연결은 초록이다.

## ★ [2026-09-03] 잔존물 — 검사기가 안 보는 것

`[실측]` `program/research/_cs_구현현황.md` §9 의 지적을 오늘 다시 확인했다. **2026-08-19 기록인데 아직 그대로다.**

### 빈 패키지 넷

```
app/presentation/schemas/            .py 없음
app/core/case_runtime/               .py 없음
app/modules/customer_ops/team_modules/   .py 없음 (local_team_a·b·remote_team_demo)
```

`[실측]` **이 함정으로 wiki 문서 17건이 틀렸다.** "여기에 무엇이 있다"고 썼는데 빈 폴더였다. → [../../../wiki/governance/type-verification/round-9.md](../../../wiki/governance/type-verification/round-9.md)

**codex 프롬프트에도 "빈 패키지를 문서화하지 마라"를 명시해야 했다.**

### 고아 `.pyc` 둘

```
__pycache__/order_shipping.cpython-312.pyc     ← 대응하는 .py 없음
__pycache__/return_exchange.cpython-312.pyc    ← 없음
```

**옛 Team 두 개의 잔해다.** `legacy/` 로 옮겨졌는데 캐시만 남았다.

`[실측]` **위험하지는 않다.** Python 은 소스 없는 `.pyc` 를 기본으로 import 하지 않는다.

**다만 파일 목록만 보면 그 Team 이 아직 있는 것처럼 보인다.**

### 선언은 있는데 등록이 없는 것

| 파일 | 상태 |
|---|---|
| `response_review_policy.py` | 소스는 있고 **현행 Team 선언에 없다** |

`[미확보]` **의도적으로 남긴 것인지 잊힌 것인지 모른다.**

## 이건 검사기가 못 잡는다

`[실측]` [check_wiki.py](../../../wiki/governance/review-policy.md) 는 **문서가 가리키는 테스트 파일과 함수가 실재하는지** 본다.

**그런데 "코드에 있는데 아무도 안 쓰는 것"은 안 본다.**

```
불변식 → 테스트     검사한다
코드   → 사용처     안 한다
```

`[미확보]` **잔존물을 세는 검사가 없다.** 지금은 사람이 `_cs_구현현황.md` 같은 스냅샷을 다시 찍어야 안다.

## ★ [2026-09-03] DoD-22 의 근거가 사라졌다

`[실측]` evidence 6건이 지금도 유효한지 확인하다 나왔다. **DoD-22 만 "낡음" 판정이다.**

### 주장한 두 축이 둘 다 재현 안 된다

`DoD-22 — Team 의 직접 Tool 호출 금지`는 **정적 + 런타임 두 축**으로 통과를 주장한다.

| 축 | 인용한 근거 | 지금 |
|---|---|---|
| **정적 (AST)** | `app/modules/**` 의 import 를 파싱해 금지 대상 0건 | **`test_core_isolation.py` 는 `app/core` 만 훑는다** (`root = Path("app/core")`) |
| **런타임 (spy)** | `pytest.raises(ToolNotAllowed)` 로 실제 차단 관측 | **소스가 없다** |

### `ToolNotAllowed` 를 검사하는 테스트가 `.pyc` 에만 있다

```
tests/unit/teams/__pycache__/test_team_scenarios.cpython-312.pyc   ← 있음
tests/unit/teams/test_team_scenarios.py                            ← 없음
```

**소스가 삭제됐는데 캐시만 남았다.** → 위 "잔존물" 절의 고아 `.pyc` 와 같은 현상이다.

`[실측]` **구현은 살아 있다.**

```python
# app/tools/read_tools.py:156
raise ToolNotAllowed(f"tool '{name}' is not allowed for this task")
```

**막는 코드는 있는데 막히는지 확인하는 테스트가 없다.**

### 이게 가장 나쁜 종류다

| | |
|---|---|
| 테스트가 없다 | 알기 쉽다 |
| 테스트가 틀린 걸 검사한다 | 위 "테스트가 제품을 잘못 끌고 간 사례" |
| **evidence 가 없는 테스트를 인용한다** | **문서는 통과라고 적혀 있고 근거는 사라졌다** |

**세 번째는 evidence 를 열어 봐야만 드러난다.** 그리고 evidence 는 "한 번 통과하면 다시 안 보는" 문서다.

`[미확보]` **DoD-22 를 다시 통과시키려면 테스트를 새로 써야 한다.** 삭제된 이유를 못 찾았다.

## 다른 5건은 대체로 유효했다

`[실측]` 같이 확인한 결과.

| DoD | 판정 | 낡은 것 |
|---|---|---|
| 12 | **유효** | — |
| 02 | 일부 낡음 | `transition_case()` 호출 **7회 → 14회** |
| 14 | 일부 낡음 | scope `subscription:read`·`technical:read` **소멸** · 함수명 `six` → `ten` · allowlist 5 → **6** |
| 20 | 일부 낡음 | 테스트 경로 2건 이동 · `3 passed` → **6개** |
| 24 | 일부 낡음 | **대조 대상이 billing → commerce 로 통째로 바뀜** |

### DoD-24 가 특히 낡았다

`[실측]` 문서가 **"이 MVP 에 `orders` 테이블이 없다 → quantity 확인 불가 → 거부"**라고 적고 있다.

**지금은 `orders`·`order_items`·`shipments`·`returns` 가 다 있다.** quantity 도 실제로 대조된다.

**한계 절이 사실과 반대가 됐다.** → [../domain-swap.md](../domain-swap.md)

## 관계

- [invariants.md](invariants.md) — 불변식 카탈로그
- [test-map.md](test-map.md) — 테스트 위치
- [../../../acop_dojo/wiki/index.md](../../../acop_dojo/wiki/index.md) — 생성 프로그램
