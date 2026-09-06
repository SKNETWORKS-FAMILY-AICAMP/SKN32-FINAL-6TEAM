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

### 원인이 확정된 흔들림은 따로 있다 — 시각 필드

`[실측]` [DoD-19](../../docs/evidence/DoD-19_LOCAL_A2A_정규화.md). `test_local_executor_is_identical_to_direct_team_call`이 두 실행 결과를 `model_dump()` 통째로 비교하는데, `observed_at=datetime.now(UTC)`가 두 호출에서 다르게 찍혀 **클럭 틱에 걸렸다.** 전체 실행 중 1회, 단독 실행은 통과 — 위 동시 실행 건과 겉모습이 같다.

fixture 시각을 고정해 해소했다. **위 29건과 다른 점은 원인이 잡혔다는 것이다.**

> 결과 전체를 비교할 때는 비결정 필드가 섞여 있는지 본다. 시각·UUID·순서가 대표적이다.

`[미확보]` 위 29건 중 몇이 같은 종류(비결정 필드)인지는 안 셌다. DB를 만지는 쪽에 몰려 있어 원인이 다를 가능성이 높지만, 확인은 안 됐다.

### 흔들림이 게이트 자체를 무디게 만든 경우

`[실측]` [회귀테스트 검증 로그](../../docs/evidence/2026-08-31_테스트_사각지대_회귀테스트_검증.md). 2026-08-31 배치는 결함 18건을 심어 **18건 전부 잡았다**(424 → 470 테스트). 그런데 그중 `INV-STATE-001`(동시 갱신 정확히 1건 충돌)은 **결함을 심은 채 단독 5회 돌리면 4회 통과**한다 — 잡은 테스트가 원래 비결정적이라서다. 원인은 [conflict-retry.md](../runtime/conflict-retry.md)에 있다(진 쪽이 읽는 시점에 따라 `StateConflict` 대신 `InvalidTransition`).

`[실측]` `program/research/테스트_사각지대_2026-08-30.md`(대체된 초판)가 그때는 원인을 몰라 "테스트 격리 문제일 가능성"으로 남겼던 자리다 — 위 conflict-retry 설명이 그 답이다. 같은 문서가 **흔들린 테스트를 하나 더** 적어 뒀다: `test_approval_rerun_does_not_create_action_request_again`이 결함을 고친 뒤 전체 실행에서 한 번 실패하고 재실행 2회는 통과. 이쪽은 원인 기록이 없다 `[미확보]`. 확인 수단은 도장의 안정성 검사다 — 결함마다 지정 테스트를 반복해 같은 실패 집합이 나오는지 본다.

```
python dojo.py stability --repeats 5
```

3회 기준으로는 결함 16개가 전부 안정적이었다. 반복 수를 올리면 흔들리는 자리가 더 드러날 수 있다.

**"잡았다"가 5회 중 1회면 게이트로는 못 쓴다.** 위 "현재 결과" 표의 48/48은 이 종류를 구분하지 않고 센 값이다 — 한 번이라도 실패하면 잡은 것으로 들어간다.

`[미확보]` 48건 중 같은 이유로 흔들리는 게 더 있는지는 여러 번 돌려 보지 않으면 모른다. 카탈로그에 "잡은 횟수/시도 횟수"가 없다.

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

## ★ [2026-09-06] 있는데 아무것도 검사하지 않는 테스트

`[실측]` DoD-13 재검증에서 `tests/integration/api/test_openapi_surface.py`를 읽다 봤다.

`test_new_paths_are_allowed_but_must_be_scoped`는 `/v1` 경로마다 돌면서 `unscoped` 목록을 채우게 돼 있는데, **루프 안 모든 분기가 `continue`로 끝나서 목록에 아무것도 넣지 않는다.** `assert not unscoped`는 항상 참이다.

**해가 없는 건 아니다** — 바로 아래 `test_write_endpoints_require_a_scope_dependency`가 OpenAPI 스키마 대신 **실제 라우트 의존성**을 보고 같은 성질을 제대로 검사한다. 빈 테스트가 실제 검사 옆에 나란히 있어서, 이름만 보면 두 겹 같지만 한 겹이다.

**위 "테스트가 제품을 잘못 끌고 간 사례"와 종류가 다르다.** 그건 틀린 걸 검사했고, 이건 **아무것도 검사하지 않는다.** dojo의 결함 심기로는 못 잡는다 — 어떤 결함을 심어도 이 테스트는 원래 초록이라 "잡았다/못 잡았다"를 구분할 수 없다.

`[미확보]` 같은 종류가 더 있는지 세지 않았다. "assert 대상이 빈 채로 시작해서 채워지는 경로가 없는 테스트"를 정적으로 찾는 검사가 없다.

## ★ [2026-09-06] pytest가 한 번도 import하지 않던 모듈 — 같은 결함이 두 번 났다

`[실측]` [EVAL-RUNNER-IMPORT-FIX](../../docs/evidence/EVAL-RUNNER-IMPORT-FIX.md). 2026-08-17에 `eval/runners/common.py`가 이미 삭제된 `billing.py`·`technical.py`를 import하고 있었다. **`grep -rln "eval.runners" tests/` 결과 0건** — 이 모듈을 import하는 테스트가 없어서 `pytest -m "not live"`로는 절대 안 잡혔고, `--provider openai` 라이브 경로를 사람이 CLI로 돌릴 때만 터졌다.

원문이 "import만 하는 smoke test 하나면 다음엔 pytest로 잡는다"고 제안하고 **범위 밖이라 만들지 않았다.** 그리고 **이틀 뒤 같은 파일에서 같은 종류가 다시 났다** — 2026-08-19 레거시 격리가 `order_shipping`·`return_exchange`를 옮겼는데 `common.py:253-254`의 import는 안 따라와서, 2026-08-20 DoD-28 golden 실측 72건이 전부 import 단계에서 막혔다([../../../wiki/evaluation/dod28-rerun.md](../../../wiki/evaluation/dod28-rerun.md)).

`[실측]` **지금은 닫혔다 — 의도한 게 아니라 부산물로.** 2026-09-03 `tests/unit/eval/test_team_failed_penalty.py`가 `from eval.runners.common import team_failed`를 하면서 `common.py`의 import 결함은 pytest 수집 단계에서 걸리게 됐다. `tests/unit/core/test_commit_phase_mapping.py`도 `eval.runners`를 참조한다.

**규칙 — "이 모듈을 import하는 테스트가 있는가"는 커버리지 숫자에 안 잡힌다.** 리네임·이동이 잦은 시기엔 패키지별로 import smoke를 한 줄이라도 두는 게 싸다.

## ★ [2026-09-03] DoD evidence 재검증 — 낡은 근거와 새 결함

`[실측]` evidence 6건이 지금도 유효한지 확인하다 나온 것들이 길어져서 별도 문서로 옮겼다.

**DoD-22 는 인용한 테스트 소스가 사라졌다.** 다른 5건 중 4건은 일부 낡았고 1건(12)은 유효하다. **DoD-29 재검증 중 Team 조립기가 인자 개수만 보고 배선할 뻔한 결함도 하나 더 나왔다.**

→ [dod-evidence-drift.md](dod-evidence-drift.md)

## 관계

- [invariants.md](invariants.md) — 불변식 카탈로그
- [test-map.md](test-map.md) — 테스트 위치
- [dod-evidence-drift.md](dod-evidence-drift.md) — DoD-22 근거 소실과 Team 조립기 결함
- [../../../acop_dojo/wiki/index.md](../../../acop_dojo/wiki/index.md) — 생성 프로그램
