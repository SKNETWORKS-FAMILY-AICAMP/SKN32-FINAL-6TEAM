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
domain: commerce
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

## ★ [2026-09-07] SQL 쪽 낙관적 동시성은 어느 테스트도 안 지킨다

`[실측]` 낙관적 동시성은 **두 겹**이다. `app/core/transition.py` 를 읽으면 순서가 보인다.

| 겹 | 어디 | 언제 걸리나 |
|---|---|---|
| 파이썬 | `transition.py:147` `if current.version != expected_version` | **먼저** |
| SQL | `transition.py:68` `AND version = %(expected_version)s`, 안 맞으면 rowcount 0 → `:176` | 파이썬을 통과한 뒤 |

**파이썬 검사가 먼저 걸린다.** SQL 조건까지 가려면 `SELECT` 와 `UPDATE` 사이에 다른
트랜잭션이 끼어들어야 하는데, 단일 스레드 테스트에서는 그런 일이 안 생긴다.

★**그래서 SQL 의 `AND version = ...` 을 지워도 지금 테스트는 전부 통과한다.**
`tests/integration/db/test_stale_write_conflict.py` 의 세 테스트는 모두 파이썬
검사에서 멈춘다 — SQL 조건을 검증한 적이 없다. 그런데 **진짜 동시 쓰기를 막는 것은
SQL 쪽뿐이다.** 파이썬 검사는 자기가 읽은 값과만 비교하므로 경합을 못 본다.

`[미확보]` 결함을 심어 실제로 통과하는지는 확인하지 않았다 — 코드 세션 몫이다.
위 판정은 **호출 순서를 읽어서** 낸 것이다.

**고치는 법은 설계 문서에 이미 있다.** `wiki/records/plans/2026-08-31_1154_테스트_사각지대_회귀테스트_설계.md`
§6-1 이 이 사각지대를 지목하고 **구조적 단언**(UPDATE 문에 version 조건이 있는지를
문자열로 본다)을 처방했다. 동시성 테스트는 타이밍에 따라 갈리기 때문이다
(그 문서 실측 — 단독 5회 중 1회 실패). **처방은 아직 구현되지 않았다.**
`INV-STATE-007` 을 이름으로 참조하는 테스트가 저장소에 없다.

★행동 테스트로 못 잡는 것에는 구조적 단언을 쓰되, **그게 행동 테스트가 아니라는
사실을 테스트 안에 적는다.** 안 적으면 다음 사람이 "구현을 고정하는 나쁜 테스트"
로 보고 지운다.

## 유지하는 법

원본 문서의 결론.

> 새 규칙을 만들 때 **그 규칙을 어기는 변경도 함께 만들어** 게이트에 걸어 본다. 규칙만 늘리고 세는 곳을 안 만들면 다시 벌어진다.

**불변식을 추가할 때 결함도 같이 추가한다.** 이게 카탈로그가 낡지 않게 하는 방법이다.

## ★ [2026-09-07] `degraded` 가 세 가지를 한 칸에 뭉친다

`[실측]` 평가 산출물의 `degraded` 는 이렇게 만들어진다(`eval/runners/common.py`).

```python
"degraded": bool(record.get("degraded"))
            or bool(team_result.get("failure_code"))
            or bool(team_result.get("warnings"))
```

**경고가 하나라도 있으면 degraded 다.** 그런데 Mock Team 은 부를 때마다 경고를 낸다.

| golden 216행의 `degraded` 102행 (47%) | |
|---|---|
| **Mock 경고만** — `"Mock 단계에서는 승인 제안만 생성하며 실제 처리는 수행하지 않습니다."` | **60행 (58.8%)** |
| 진짜 `failure_code` | 42행 (41.2%) |

★**degraded 로 표시된 것의 절반 넘게가 degraded 가 아니다.** Mock 이 "나는 Mock 이다"
라고 말한 것뿐이다. 골든셋의 `notes` 도 그 건들을 `normal` 이라고 적어 뒀다.

**무엇이 오염되나.**

- `degraded` 로 나눠 보는 모든 분석. 분모의 절반이 가짜다
- 기권 지표 — 과잉 기권으로 잡힌 12건이 전부 이 칸에 걸려 있었다
  → [../../../wiki/evaluation/metrics.md](../../../wiki/evaluation/metrics.md)
- DoD-25(degraded 차단)의 근거로 이 필드를 쓴다면 그것도

**고치는 방향은 칸을 나누는 것이다** — `context_degraded` · `team_failed` ·
`has_warnings` 를 따로 싣고, 합친 값이 필요하면 읽는 쪽에서 합친다. 지금은
합쳐 놓아서 **되돌릴 수가 없다.**

`[미확보]` Mock 을 진짜 Return & Refund Team 으로 바꾸면 이 60행이 어떻게 되는지는
바꿔 봐야 안다.

## ★ [2026-09-07] rescore 는 judge 의 `total` 이 축의 합과 같은지 안 본다

`[실측]` 러너는 본다. `eval/runners/common.py:547~551` 이 다섯 축의 합과 `total` 이
다르면 `ValueError("judge rubric is empty or malformed")` 를 던진다.
**`eval/rescore.py:100~103` 은 키가 있는지만 본다.** 그리고 `row["score"]` 를 검증
안 된 `judge["total"]` 에서 그대로 가져온다.

그래서 채점자가 산수를 틀리면 그대로 파일에 들어간다. 실제로 들어가 있다.

| 산출물 | `total ≠ 축의 합` |
|---|---|
| `2026-09-06_rebaseline_Proposed_judgev3.jsonl` | **11/216 (5.1%)** |
| `2026-09-06_golden_proposed_judge_v3.jsonl` | **6/72 (8.3%)** |
| `2026-09-06_rebaseline_holdout_judgev3.jsonl` | 1/72 (1.4%) |
| `..._A_judgev3.jsonl` · `..._B_judgev3.jsonl` | 0 |

한 예 — 다섯 축이 `0·4·0·0·0` 이라 합이 **4** 인데 `total` 과 `score` 가 **8** 이다
(`g-order-04`, `degraded: true`). A·B 에 없고 Proposed 계열에만 있는 것으로 보아
기록이 클수록 채점자가 더 자주 틀린다.

★**오늘의 결론은 안 바뀐다.** 축의 합으로 다시 계산하면 Proposed 평균 총점이
10.15 → 10.06 (−0.09) 이고 **pass 건수는 25 로 그대로다**(`pass` 는 세 파일 모두
규칙과 어긋나는 행이 0이다). 그래서 지금 실린 수치는 그대로 쓴다.

★**그래도 고쳐야 한다.** `score` 가 검증 안 된 값에서 오므로 **`score` 로 집계하는
모든 것이 노출돼 있다.** 이번에 −0.09 였던 것은 운이지 설계가 아니다. 러너에 있는
검사를 rescore 에도 넣으면 된다 — 같은 자리에 같은 규칙이 둘로 갈라져 있는 것이
원인이다.

## 테스트 자체를 못 믿게 된 사례는 따로 뒀다

흔들리는 테스트와 테스트가 제품을 잘못 끌고 간 사례는
[test-reliability.md](test-reliability.md) 로 옮겼다(2026-09-07, 300줄 규정).

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

`[실측]` [EVAL-RUNNER-IMPORT-FIX](../records/evidence/EVAL-RUNNER-IMPORT-FIX.md). 2026-08-17에 `eval/runners/common.py`가 이미 삭제된 `billing.py`·`technical.py`를 import하고 있었다. **`grep -rln "eval.runners" tests/` 결과 0건** — 이 모듈을 import하는 테스트가 없어서 `pytest -m "not live"`로는 절대 안 잡혔고, `--provider openai` 라이브 경로를 사람이 CLI로 돌릴 때만 터졌다.

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
