---
type: report
title: DoD evidence 재검증 — 낡은 근거와 새 결함
description: DoD-22는 인용한 테스트 소스가 사라졌다. DoD-29는 등록 전에 조립기 결함을 하나 더 찾았다
status: draft
tags: [testing]
owners: [human:미배정]
---

# DoD evidence 재검증 — 낡은 근거와 새 결함

`[실측]` [blind-spots.md](blind-spots.md)에서 분리. evidence 10건이 지금도 유효한지 확인하다 나온 것들이다.

## ★ [2026-09-06] 여기서 넘긴 것이 cs 저장소에서 전부 처리됐다

`[실측]` 이 문서가 `[미확보]`로 남긴 셋과 「일부 낡음」 일곱이 cs 에서
닫혔다. **cs 쪽 실측이 이 문서의 수치 하나를 정정했다.**

| 이 문서가 남긴 것 | cs 처리 |
|---|---|
| DoD-22 `[미확보]` "테스트를 새로 써야 한다" | `tests/contract/test_team_tool_discipline.py` **10건** 신규. 판정은 뒤집지 않았다 — 실측하니 Team 6개 인프라 직접 import 0건이고 차단도 동작한다. 없던 것은 **근거**였다 (`3186046`) |
| DoD-06 `[미확보]` "cs 저장소 작업자에게 넘길 항목" | cs 에서 재측정. 문서 25 / 청크 **306** / 임베딩 누락 0 / 1536d / rag 통합테스트 4 passed. 옛 sample 출력은 "cs 판정 근거가 아니다" 로 표시해 남김 (`0c3b475`) |
| MODULE-TOGGLES `[미확보]` "나머지는 재실행하지 않았다" | graph_store·mcp 재실행 — 2026-08-30 과 같다. **그리고 스크립트가 라벨과 정반대를 출력하고 있었다**(아래) (`991acb3`) |
| 02·14·20·24·21·13·08 「일부 낡음」 | 각각 실측 후 현행화 (`7373b67`) |

### ★이 문서의 수치 하나가 틀렸다 — DoD-02

「`transition_case()` 호출 **7회 → 14회**」로 적혀 있는데 **12회**다.
`grep` 줄 수(15)에는 정의부·주석이 섞이고 14 는 그중 일부만 뺀 값이다.
cs 에서 **AST 로 호출 노드만** 세어 12 를 얻었다
(controller 7 · api/cases 4 · classification 1).

### ★DoD-21 은 「식별자만 낡음」이 아니었다

이 문서는 21 을 "어댑터가 도메인 무관이라 판정 유효, 라벨만 옛것" 으로
분류했다. cs 에서 재현 명령을 **실제로 돌려 보니** 이랬다.

```
python -m pytest tests/unit/infrastructure/test_sql_graph_adapter.py -q
→ no tests ran in 0.00s        ← 경로가 tests/integration/graph/ 로 이동
```

**0건이 도는 명령은 통과처럼 보이지만 아무것도 증명하지 않는다** — 이
문서가 DoD-22 를 두고 "가장 나쁜 종류" 라 한 것과 같은 부류다. DoD-20 의
둘째 명령(`tests/e2e/test_project_composition.py`)도 같은 상태였다.

그래서 cs 는 **evidence 안의 pytest 명령 30개를 `--collect-only` 로 일괄
검사**했다. 지금 0건이 도는 것은 DoD-21 이 "이 명령은 0건이 돈다" 를
보여주려고 일부러 인용한 한 줄뿐이다.

### MODULE-TOGGLES — 라벨이 관측과 정반대였다

이 문서가 "evidence 가 결함을 정상으로 승인했다(다섯 번째 종류)" 로 지적한
그 자리인데, **스크립트 쪽에 그 흔적이 그대로 남아 있었다.**

```
===== VOC 끔 — 기동 자체가 거부된다   (voc: false)     ← 라벨
기동 -> 성공                                          ← 관측
```

`require_module("voc")` 는 2026-09-01 에 빠졌는데 라벨은 안 고쳐졌다.
라벨만 읽고 넘기면 아직 막히는 줄 안다. cs 에서 라벨을 고치고, 지금 계약
(기동은 된다 · 화면은 사라진다 · **분류는 계속 돈다**)을 실제로 확인하게
프로브를 바꿨다.

★**이 문서의 관찰과 분류는 대체로 정확했고 실제로 일을 끌어냈다.** 위
정정 둘은 "남이 센 숫자를 그대로 옮기지 않는다" 는 규칙이 양쪽에 다
적용된다는 뜻이다.

## ★ [2026-09-03] DoD-22 의 근거가 사라졌다

`[실측]` **DoD-22 만 "낡음" 판정이다.**

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

**소스가 삭제됐는데 캐시만 남았다.** → [blind-spots.md](blind-spots.md)의 "잔존물" 절 고아 `.pyc` 와 같은 현상이다.

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
| 테스트가 틀린 걸 검사한다 | [blind-spots.md](blind-spots.md)의 "테스트가 제품을 잘못 끌고 간 사례" |
| **evidence 가 없는 테스트를 인용한다** | **문서는 통과라고 적혀 있고 근거는 사라졌다** |

**세 번째는 evidence 를 열어 봐야만 드러난다.** 그리고 evidence 는 "한 번 통과하면 다시 안 보는" 문서다.

`[미확보]` **DoD-22 를 다시 통과시키려면 테스트를 새로 써야 한다.** 삭제된 이유를 못 찾았다.

## 다른 9건은 대체로 유효했다

`[실측]` 같이 확인한 결과.

| DoD | 판정 | 낡은 것 |
|---|---|---|
| 12 | **유효** | — |
| 02 | 일부 낡음 | `transition_case()` 호출 **7회 → 14회** |
| 14 | 일부 낡음 | scope `subscription:read`·`technical:read` **소멸** · 함수명 `six` → `ten` · allowlist 5 → **6** |
| 20 | 일부 낡음 | 테스트 경로 2건 이동 · `3 passed` → **6개** |
| 24 | 일부 낡음 | **대조 대상이 billing → commerce 로 통째로 바뀜** |
| **06** | **낡음 — 그리고 잰 곳이 cs가 아니다** | 300청크 · `billing`/`entitlement` scope → 지금 cs는 **306청크 · 쇼핑몰 scope**. 아래 |
| 21 | 일부 낡음 | evidence 출력은 `team:billing_subscription`, 지금 테스트 fixture는 `team:order_shipping`·`issue:post_cancel_charge` — 셋 다 퇴역 식별자. 어댑터가 도메인 무관이라 판정은 유효 → [../context/graph-retrieval.md](../context/graph-retrieval.md) |
| 13 | 일부 낡음 | "경로 4개 위에 operation 5개, `/v1/` 아래 6번째가 생기면 위반" — 지금 `CONTRACT_V1_PATHS`는 outbox resolve를 포함한 **경로 5개**이고 규칙 자체가 v7에서 "5는 상한이 아니다"로 바뀌었다. 판정(계약 집합 일치)은 유효 → [../external/rest-api.md](../external/rest-api.md) |
| **08** | **낡음 — 대상 자체가 없다** | 제목부터 "Billing/Technical Team"이고 판정 근거 1이 `BillingSubscriptionTeam`·`TechnicalEntitlementTeam`의 manifest다 — **둘 다 2026-08-18에 퇴역한 Team이다.** 남는 건 기제(manifest 계약 테스트·Core 격리 AST·계약 validator)뿐이고, 그 기제가 지금 여섯 Team에 대해 통과하는지는 이 evidence가 아니라 현재 테스트 실행이 말해 준다. 21·13의 "라벨만 옛것"과 달리 **evidence가 증명한 대상이 사라진** 경우 |

### DoD-06 은 cs 가 아니라 sample 을 잰 것이다

`[실측]` 2026-09-06. [DoD-06 evidence](../../docs/evidence/DoD-06_정책FAQ_25건_300청크.md)의 재현 명령이 **`cd final_project_sample`** 로 시작한다. 실측 출력도 옛 구독 도메인이다 — scope 배분 `billing 5 · entitlement 5 · incident 3 …`, 질의 "해지했는데 결제가 됐어요" → `doc_06 [refund]`.

**cs 의 지금 코퍼스는 다르다.** `final_project_cs` 에서 `python -m scripts.check_corpus` 를 직접 돌렸다.

```
문서 25 / 총 섹션 306
scope: order 5 · shipping 5 · return 4 · exchange 3 · refund 4 · support 2 · incident 2
전 항목 통과 — 인수 가능
```

**cs 의 DoD-06 "통과" 판정이 sample 의 옛 코퍼스 측정에 기대고 있다.** 루트 `CLAUDE.md` 가 명시한 규칙 — **sample 의 검증 상태를 cs 의 완료로 간주하지 않는다** — 를 evidence 문서가 어기고 있는 사례다. cs 자체 측정은 있다(2026-08-17 `RAG적재_평가데이터셋_재작성_리포트.md`, cs `CLAUDE.md` §5 "RAG corpus" 행) — evidence 가 그쪽을 가리키지 않을 뿐이다.

`[미확보]` **evidence 문서의 재현 명령과 실측 출력을 cs 기준으로 바꾸는 것은 `final_project_cs/docs/` 수정이라 이 wiki 작업 범위 밖이다.** 해당 저장소 작업자에게 넘길 항목이다.

**이건 이 문서의 "가장 나쁜 종류" 셋과도 다른 네 번째다** — 근거가 사라진 것(22)도, 낡은 것(02·14·20·24)도 아니고, **처음부터 다른 프로젝트를 잰 근거**다.

### 검증 로그 MODULE-TOGGLES — "통과"라고 판정한 동작이 다음 날 결함이 됐다

`[실측]` 2026-09-06. [MODULE-TOGGLES 검증 로그](../../docs/evidence/MODULE-TOGGLES_실효화_검증.md)(2026-08-30)의 실측 출력 둘째 줄.

```
===== VOC 끔 — 기동 자체가 거부된다   (voc: false)
기동 -> ProjectConfigError | module 'voc' is disabled; cannot assemble inline classifier
```

판정은 **"통과. 여섯 모듈 전부가 선언에 따라 실제로 코드를 가른다."** — 그런데 이틀 뒤 v8 재판정(2026-09-01)은 **바로 이 동작을 결함 1번(높음)으로 뒤집었다.** 인라인 분류는 필수 기능이라 선택 플래그 `voc`에 매달리면 안 되고, "끌 수 있는 모듈"이라 선언해 놓고 끄면 제품이 안 뜨는 건 결함이다. → [../../../wiki/governance/drift-case-voc.md](../../../wiki/governance/drift-case-voc.md)

**다섯 번째 종류다.** 근거가 사라지거나 낡거나 다른 곳을 잰 게 아니라, **evidence가 결함을 정상으로 승인했다.** 검증 로그는 "선언대로 동작하는가"를 물었고 그 답은 맞았다 — 선언 자체가 틀렸다는 건 검증 로그가 물을 수 있는 질문이 아니었다. 그래서 이 로그는 지금도 "통과"이고, 그게 틀린 것도 아니다. **다만 이 로그를 근거로 "voc 토글은 검증됐다"고 읽으면 안 된다.**

`[미확보]` 로그 나머지(graph_store·mcp 토글, 브라우저 확인)는 지금도 유효한지 재실행하지 않았다.

### DoD-24 가 특히 낡았다

`[실측]` 문서가 **"이 MVP 에 `orders` 테이블이 없다 → quantity 확인 불가 → 거부"**라고 적고 있다.

**지금은 `orders`·`order_items`·`shipments`·`returns` 가 다 있다.** quantity 도 실제로 대조된다.

**한계 절이 사실과 반대가 됐다.** → [../domain-swap.md](../domain-swap.md)

## ★ [2026-09-04] Team 조립이 인자 개수만 보고 배선할 뻔했다

`[실측]` [DoD-29](../../docs/evidence/DoD-29_ResponseGenerationReview.md)에서 발견. `composition.py::_instantiate_team()`이 생성자의 **위치 인자 개수**만 보고 `(tools, llm)`을 채워 넣는 방식이었다.

`ResponseGenerationReviewTeam(llm=None)`처럼 단일 인자 생성자라면 이름을 안 보고는 그 인자가 `tools`인지 `llm`인지 알 수 없다 — 개수만 보면 `ReadToolbox`가 `llm` 자리로 잘못 들어간다. **DoD-29 등록 전에 발견해 실제로 터지기 전에 막았다.**

### 고친 방법도 완전히 안전하진 않다

`[실측]` `final_project_cs/app/composition.py:137-144`

```python
if len(required) <= 1 and len(positional) <= 1:
    if positional[0].name == "llm":
        return implementation(llm)
    return implementation(tools)
```

**여전히 이름 하나만 본다.** 단일 인자 이름이 `llm`이 아닌 다른 이름(`toolbox`·`client` 등)이면 다시 `tools`로 채워진다 — 이름이 우연히 `llm`인 경우만 잡는 패치이지, 타입을 보는 검사로 바뀐 게 아니다.

`[미확보]` **타입 기반 검사로 안 바꾼 이유는 확인 안 됨.** 지금 Team이 둘 다 `tools`·`llm` 이름 관례를 지켜서 드러나지 않을 뿐이다.

## 관계

- [blind-spots.md](blind-spots.md) — 테스트 사각지대 본문
- [invariants.md](invariants.md) — 불변식 카탈로그
- [../../../../final_project_cs/docs/evidence/DoD-29_ResponseGenerationReview.md](../../docs/evidence/DoD-29_ResponseGenerationReview.md) — 원본 evidence
