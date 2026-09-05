---
type: report
title: 반영률 실측
description: 원본 10건 79개 절을 대조했다. 완전 반영은 11%였다
status: draft
tags: [governance, documentation]
---

# 반영률 실측

`[실측]` 2026-09-02. 전문은 `program/scripts/_gap_audit.md`.

## 왜 쟀나

wiki 166건·17,000줄을 **기존 문서에서 옮겨 담아** 만들었다. 그런데 **"이관 실행 완료"로 기록된 건 0건**이었다.

내용은 옮겼는데 **무엇이 옮겨졌는지 장부가 없었다.**

그리고 낙관할 수 없는 이유가 있었다 — **손으로 대조한 7건에서 7건 다 빠진 게 나왔다.**

## 결과

원본 10건, `##`·`###` 절 **79개**를 대조했다.

| 판정 | 절 | 비율 |
|---|---|---|
| **반영** | **9** | **11%** |
| 일부 | 35 | 44% |
| **누락** | **35** | **44%** |

**완전히 반영된 것은 아홉 절, 11% 다.**

### 문서별

| 원본 | 절 | 반영 | 일부 | 누락 |
|---|---:|---:|---:|---:|
| `_codex_추적화면_교차검증` | 14 | 0 | 0 | **14** |
| `VOC가_팀모듈로_흘러간_경위` | 14 | 1 | 5 | 8 |
| `_3차_인용검증_설계` | 13 | 3 | 7 | 3 |
| `_컴포저_설계대비_구현대조` | 8 | 0 | 6 | 2 |
| `_중앙설정저장소_검토` | 8 | 1 | 4 | 3 |
| `_평가harness_결함` | 7 | **4** | 3 | 0 |
| `_분쟁조정사례` | 6 | 0 | 4 | 2 |
| `_법령원문` | 4 | 0 | 3 | 1 |
| `dev2_브리핑_교차검증` | 4 | 0 | 3 | 1 |
| `_기술스택_공식문서` | 1 | 0 | 0 | 1 |

## 읽을 때 주의할 것

`[미확보]` **대조 중에 이관 작업이 같이 돌았다.** `VOC`·`컴포저`·`중앙설정저장소` 세 건은 이 표가 만들어진 뒤에 이관했으므로 **지금은 더 높다.**

`[실측]` **`_평가harness_결함` 이 4/7 로 가장 높은 건 우연이 아니다.** [7차 검증](../type-verification/round-7.md)에서 이 문서의 누락을 찾아 `metrics.md` 에 반영했기 때문이다. **대조하고 고친 문서가 실제로 높게 나왔다.**

## ★ "일부" 35건이 가장 위험하다

**누락은 없다는 걸 아니까 채우면 된다.** 문제는 **일부**다.

주제가 wiki 에 있으니 **읽는 사람은 반영됐다고 믿는다.** 그런데 숫자나 결론이 빠져 있다.

`[실측]` 실제 예 — `_기술스택_공식문서` 는 절이 하나뿐인데 그게 누락이다.

> 링크를 걸지 않은 5항목과 **각각의 이유**

[tech-stack.md](../../architecture/tech-stack.md) 에 기술 분류는 있지만 **왜 어떤 것에 공식 문서 링크를 안 걸었는지**가 없다.

## 이 숫자가 뜻하는 것

`[추정]` 표본 10건은 전체 196건의 5% 다. 일반화할 수 없다.

**다만 방향은 분명하다.**

```
문서가 있다  ≠  내용이 옮겨졌다
```

**wiki 에 같은 주제 문서가 있다는 것만으로 이관됐다고 세면 안 된다.**

## 2차 — 계약 문서 7건

`[실측]` 2026-09-02. 전문은 `program/scripts/_gap_audit2.md`.

| 판정 | 절 | 비율 |
|---|---|---|
| **반영** | **31** | **31%** |
| 일부 | 55 | 55% |
| 누락 | 14 | 14% |

**1차(11%)보다 세 배 높다.** 계약 문서는 필드와 숫자가 명확해서 옮길 때 덜 샜다.

| 원본 | 절 | 반영 | 일부 | 누락 |
|---|---:|---:|---:|---:|
| `CLAUDE.md` | 19 | **13** | 4 | 2 |
| `release_checklist.md` | 12 | 7 | 5 | 0 |
| `01_계약_Pydantic.md` | 11 | 3 | 8 | 0 |
| `02_DB_스키마.md` | 10 | 2 | 6 | 2 |
| `03_REST_MCP_인터페이스.md` | 13 | 2 | 11 | 0 |
| `08_모듈_컴포넌트_목록.md` | 10 | 1 | 8 | 1 |
| **`RULE.md`** | **25** | **3** | 13 | **9** |

### ★ `RULE.md` 가 3/25 로 최악이었다

**프로세스 규칙이 통째로 안 옮겨져 있었다.**

```
작업 루프 9단계 · 리포트 제출 의무 · 버그 리포트 5항목
history 형식 · 파일명 규칙 · vision 등록 규칙
CLAUDE.md 와의 우선순위
```

**[work-loop.md](../work-loop.md) 로 옮겼다.**

`[실측]` 옮기며 셋을 찾았다.

| 발견 | |
|---|---|
| **두 저장소의 `RULE.md` 가 완전히 같다** | `diff` 차이 0줄. **정본이 어느 쪽인지 안 정해져 있다** |
| **파일명 체계가 이 wiki 와 다르다** | `RULE.md` 는 `YYYY-MM-DD_HHmm_`, wiki 는 kebab-case |
| **기준선 참조가 낡았다** | `RULE.md` 가 v6 를 기준선이라 부른다. 지금은 v8 |

**세 번째가 [drift-case-voc.md](../drift-case-voc.md) 와 같은 종류다** — 낡은 참조가 자주 읽히는 규칙 문서에 남아 있다.

## 3·4차

`[실측]` 전문은 `program/scripts/_gap_audit4.md`.

| 차수 | 대상 | 절 | 반영 | 일부 | 누락 |
|---|---|---:|---:|---:|---:|
| 1차 | 조사·리뷰 10건 | 79 | **11%** | 44% | 44% |
| 2차 | 계약 7건 | 100 | 31% | 55% | 14% |
| 3차 | 계약·규칙 8건 | 69 | 25% | 49% | 26% |
| **4차** | **계획·결정 8건** | **181** | **58%** | 30% | 12% |
| **5차** | **계획서 v8 등 8건** | **192** | **47%** | 36% | 16% |
| **합계** | **41건** | **621** | **43%** | 40% | 18% |

**4차가 가장 높다.** 계획·결정 문서는 **결론이 문장 하나로 떨어져서** 옮길 때 덜 샌다.

`[실측]` **5차에서 `A-COP_구현계획서_v8.md` 가 99절 중 70건 반영(71%)으로 가장 높았다.** 기준선 문서가 가장 잘 옮겨졌다 — **당연한 결과이고 확인이 필요했던 것이다.**

**1차가 가장 낮은 것과 대칭이다** — 조사·리뷰는 세부가 많고 그게 다 샜다.

### 4차에서 나온 것

`[실측]` `DoD28-FT-RAG통합_설계.md` 가 **9건 누락**으로 최악이었다.

**`stage3-v8·v9` 실험이 통째로 빠져 있었다.** 그게 가장 최신이고 **최종 기각 이유**다.

**그리고 지표 결함이 하나 더 나왔다** — `grounded` 가 mismatch 에서 무효였다. → [../../evaluation/metrics.md](../../evaluation/metrics.md)

## ★ 이 대조가 못 보는 것

`[실측]` 2026-09-02. **`_codex_추적화면_교차검증` 을 14/14 누락으로 셌는데 틀렸다.**

코드를 확인했더니 **지적 6개 중 최소 4개가 이미 고쳐져 있었다.** → [acop_dojo/wiki/trace-review.md](../../../acop_dojo/wiki/trace-review.md)

> **이 대조는 "wiki 에 있는가"만 묻고 "코드가 고쳐졌는가"는 안 묻는다.**

**리뷰 문서는 지적이 반영되면 이관 대상이 아니라 기록이 된다.** 옮기면 **이미 없는 결함을 설명하는 문서**가 남는다.

`[미확보]` **다른 리뷰 문서 몇 건이 같은 상태인지 안 세었다.** 판정형 문서를 대조할 때는 wiki 뿐 아니라 **코드도 봐야 한다.**

## 6차 — DoD evidence 28건

`[실측]` 2026-09-04. `_gap_audit.md` 류 수기 대조 대신 `audit_coverage.py`로 `final_project_cs/docs/evidence/DoD-02`~`29`·`DoD-EVAL-DATASETS` **28건 전체**를 기계로 훑고, 반영률이 낮은 것부터 직접 대조했다.

| 대조함 | 찾은 것 |
|---|---|
| DoD-29 (2/9 절만 신호 적중) | Team 조립기가 생성자 **인자 개수만** 보고 배선하다 `ReadToolbox`를 `llm` 자리에 잘못 넣을 뻔한 결함 — 등록 전에 잡음. → [blind-spots.md](../../../final_project_cs/wiki/quality/blind-spots.md) |
| DoD-24 (4/11) | 근거 대조 코드 자체가 세 번 뚫릴 뻔한 경위(순환 폴백·트랜잭션 격리·상태기계가 먼저 잡은 구멍 셋) + NaN/Infinity 500 크래시. → [evidence-check.md](../../../final_project_cs/wiki/actions/evidence-check.md) |
| DoD-07 (5/5, 신호 0건 적중) | 마스킹(전화·카드) vs 제거(API key·결제 식별자) 구분, LLM 입력 경로·demo tenant PII 잔존이 지금도 미검증. → [auth-boundary.md](../../../final_project_cs/wiki/external/auth-boundary.md) |
| DoD-17 (7/7, 신호 0건 적중) | dod.md가 "17번 부족 이유"로 적어 둔 **"파일시스템 gate 재현"이 원문에 없는 말**이었다 — 실제로는 15번과 동일 이유. → [dod.md](../../delivery/dod.md) |
| DoD-28 (10/19) | "과잉 기권율 35%"가 모델 행동이 아니라 `calculation_basis` 미선언으로 정상 제안이 기계적으로 막힌 **결함**이었음을 확인. → [dod28-rerun.md](../../evaluation/dod28-rerun.md) |
| DoD-02·DoD-09 (읽음, 추가 안 함) | 이미 `case-lifecycle.md`가 충분히 반영 중. DoD-09의 "S-API·S-VOC 계약 사이 통합 지점을 아무에게도 안 맡긴" 배선 누락 일화는 2026-08-12 당일 재측정 완료된 사소한 사례라 추가 보류 |
| DoD-10 (2/5) | 급증 공식 "통과" 판정이 실은 코드에 5·1.5·3이 직접 박혀 있어 `guardrails.yaml`을 안 읽던 것과 우연히 같은 값이었을 뿐 — 같은 날(2026-09-05) 다른 세션이 65개 잎 전수 대조로 고친 것과 정확히 맞아떨어져 확인. → [guardrails.md](../../../final_project_cs/wiki/quality/guardrails.md) |
| DoD-18 (9/15) | 브라우저 재검증에서 나온 결함 셋 중 하나(화면표시용 `evidence` 필드가 재검증 화이트리스트에 없어 막힘)가 `calculation_basis`(DoD-28)와 **완전히 같은 형태의 반복 결함**임을 확인. "UI 버그인 줄 알았는데 가드레일이 옳았다"는 사례와 승인 실패가 조용히 삼켜지던 결함도 추가. → [approval.md](../../../final_project_cs/wiki/actions/approval.md) |
| DoD-11 (5/9) | idempotency_key가 원래 v5 산식이 아니라 `task_id` 기준이었다가 승인 후 재실행에서 실제로 중복 행을 만들어야 산식이 교체된 경위, 필드 경계 충돌 결함 이력, MCP 멱등성, unknown 해소 화면. **가장 중요한 건 "이 증명은 outbox 발행까지다 — provider 실행 경로 자체가 시스템에 없다"는 경계**를 outbox.md에 명시한 것. → [idempotency.md](../../../final_project_cs/wiki/actions/idempotency.md), [outbox.md](../../../final_project_cs/wiki/actions/outbox.md) |

| DoD-15 (7/12) | 지금 무효 처리된 옛 A/B/Proposed 수치조차, 처음엔 그것도 아니었다 — mock provider·외부망 차단·judge 환각인용 채점·Team의 LLM 결과 폐기(하드코딩 대체)·next_action 어휘일치 채점(계약 준수가 벌점)까지 **결함 5건**을 순서대로 고쳐야 나온 값이었다. 그중 둘은 고쳐지지 않았다면 정반대 결론(RAG가 해롭다 등)을 냈을 것. ablation flag 4종이 실행 전엔 아무것도 안 끄고 있었다는 것도 함께. → [protocol.md](../../evaluation/protocol.md), [judge.md](../../evaluation/judge.md) |

| DoD-12 (5/7) | outbox 중복방지 제약이 원래 `UNIQUE(topic, dedupe_key)`뿐이라 **tenant_id가 없었다** — 다른 테넌트끼리 서로 충돌할 수 있던 보안급 결함. `final_project_sample`과 대조하다 발견됐다는 게 특히 값지다(단일 저장소 리뷰가 아니라 다른 구현체 비교로 잡음). wiki의 스키마 스니펫 자체가 옛 제약을 그대로 싣고 있던 것도 정정. → [outbox.md](../../../final_project_cs/wiki/actions/outbox.md) |

| DoD-03 (6/8) | `agent_runs` 동시 시작 유일성 제약이 왜 필요했는지의 메커니즘 — 앱 레벨 `SELECT FOR UPDATE`는 **이미 있는 행만** 잠가서, 활성 run이 0개일 때 두 요청이 동시에 insert에 성공할 수 있던 TOCTOU 레이스. 이것도 `final_project_sample`과 대조하다 발견됨(DoD-12와 같은 발견 경로). → [conflict-retry.md](../../../final_project_cs/wiki/runtime/conflict-retry.md) |

| DoD-27 (5/7) | a2a-protocol.md의 자체 표가 **틀려 있었다** — 취소를 Case 상태 `cancelled`로 기록한다고 적었지만 실제로는 `outcome=escalated`+`failure_code=cancelled_by_caller`(계약 Literal을 안 늘리려는 설계). `_call_within_deadline`이 루프 사이에서만 확인해 원격 호출 하나가 hang하면 deadline을 넘길 수 있던 갭도 확인 — DoD-03·DoD-12에 이은 **세 번째 sample 대조 발견**이라 review-policy.md에 이 방법 자체를 새 절로 기록. → [a2a-protocol.md](../../../final_project_cs/wiki/external/a2a-protocol.md), [review-policy.md](../review-policy.md) |

| DoD-06 (5/7) | evidence의 재현 명령이 `cd final_project_sample`로 시작하고 실측도 옛 구독 도메인(300청크·billing scope)이다 — cs 현재 코퍼스(306청크·쇼핑몰 scope, 직접 재실행해 전 항목 통과 확인)와 다르다. **cs의 "통과"가 sample 측정에 기대고 있는, 루트 CLAUDE.md 규칙 위반 사례**. RAG 검색이 100% 실패하던 기간에 테스트가 `4 skipped`로 초록이었던 사고("skip은 통과가 아니다")와 게이트 5회차 진화 순서도 채움. → [dod-evidence-drift.md](../../../final_project_cs/wiki/quality/dod-evidence-drift.md), [rag-retrieval.md](../../../final_project_cs/wiki/context/rag-retrieval.md), [corpus-authoring.md](../../../final_project_cs/wiki/context/corpus-authoring.md) |

| DoD-04 (4/5) | checkpoint 최소 키 5개·`graph_revision` run 내 고정·"되돌릴 경로 자체가 없다"는 정적 사실이라는 한계. 첫 측정에서 `agent_runs`가 비어 있던 원인이 **composition root 부재**(REST가 Controller를 안 탐)였고 그래서 `app/composition.py`가 생겼다는 기원. 대조 중 **`shared-state.md`가 `INV-CS-RT-001~004`에 정본과 다른 문장을 붙이고 "넷 다 강제 안 됨"이라 적은 오류**를 발견·정정(검사기가 못 잡는 종류). → [case-lifecycle.md](../../../final_project_cs/wiki/runtime/case-lifecycle.md), [shared-state.md](../../../final_project_cs/wiki/runtime/shared-state.md) |
| DoD-21 (4/5) | `SqlGraphAdapter`의 전용 페이지가 cs wiki에 아예 없었다 — 새로 썼다. 세 축 중 둘이 투영 edge가 없어 "일반 질의가 되니 특정 질의도 된다"가 추정이었던 경위, Issue→Policy는 scope 문자열 일치·Issue→Team은 실적 기준이라는 한계. fixture 라벨은 퇴역 식별자(일부 낡음). → [graph-retrieval.md](../../../final_project_cs/wiki/context/graph-retrieval.md) |

| DoD-25 (4/6) | degraded 차단의 강제 지점이 **Team의 선의**(각 Team의 `if degraded` 한 줄)에서 `Controller._reject_unverified()`로 옮겨진 경위가 wiki에 없었다. degraded를 일부러 안 보는 Team으로 검증한 점, 사람이 승인하면 진행된다(금지는 "자동"뿐)·승인자가 배너를 읽었는지 모른다는 한계. → [evidence-check.md](../../../final_project_cs/wiki/actions/evidence-check.md) |
| DoD-05 (3/5) | `context-budget.md`가 잘 덮고 있어 한계만 보탬 — 축출 4단계 중 `history_detail`·`duplicate_tool_facts`는 한 번도 관측된 적 없고(코드에만 있음), "거부한다 ≠ 올바른 순서로 자른다"로 첫 판정이 부분이었던 경위. → [context-budget.md](../../../final_project_cs/wiki/context/context-budget.md) |
| DoD-14 (4/7) | scope 6→10 낡음은 이미 반영돼 있었고, 빠진 건 2026-08-24 **Composer JWT 시크릿 fail-open(빈 문자열 서명 위조 통과) + 구현체 allowlist 부재(임의 모듈 import) 체인** — 보안 결함이고 sample 대조 발견 4·5번째. review-policy.md 표를 3→5건으로. DoD 1~29 어디에도 안 걸리는 수정(`list_cases` 정렬 비결정성)이 있다는 점도 dod.md에. → [auth-boundary.md](../../../final_project_cs/wiki/external/auth-boundary.md), [dod.md](../../delivery/dod.md) |

| DoD-13 (3/5) | **wiki가 코드보다 낡았다** — `CONTRACT_V1_PATHS`는 2026-08-24부터 `/v1/outbox/{id}/resolve`를 포함한 경로 5개(operation 6)이고 규칙은 "누락은 실패·추가는 계약 목록 갱신 필수"인데, rest-api.md 세 곳이 "정확히 5개·6번째는 위반"을 `[실측]`으로 적고 있었고 rest-endpoints.md엔 resolve 계약이 없었다. 테스트를 읽다 `test_new_paths_are_allowed_but_must_be_scoped`가 **항상 통과하는 빈 테스트**인 것도 발견 → blind-spots에 새 종류로 기록. → [rest-api.md](../../../final_project_cs/wiki/external/rest-api.md), [rest-endpoints.md](../../../final_project_cs/wiki/external/rest-endpoints.md) |
| DoD-16 (3/5) | McNemar가 카이제곱 통계량(38.025)을 p값으로 찍고 bootstrap은 KeyError로 죽어 있던 통계 모듈 결함 — DoD-15의 runner·judge 결함 5건에 이은 여섯 번째. "RAG 없는 군은 루브릭상 구조적으로 통과 불가"를 metrics.md 결함 4와 합치면 A군은 최대 15점이라 **A 0/180은 모델 성능이 아니라 루브릭이 정한 결과**. → [protocol.md](../../evaluation/protocol.md), [metrics.md](../../evaluation/metrics.md) |
| DoD-23 (3/5) | 계약 테스트 구조는 idempotency.md에 이미 있었다. 빠진 건 dod.md 자체 모순 — 위쪽은 "23은 2026-08-20 통과", 아래 표 두 곳은 "부분통과(consumer 1종뿐)·두 번째 consumer 필요"로 남아 있던 것을 정정. → [dod.md](../../delivery/dod.md) |
| DoD-26 (3/6) | `Evidence.source_type="remote_agent"`를 계약에 추가한 이유(우리가 확인한 사실 vs 남이 말한 것의 구분, 테스트가 먼저 잡음), Transport 교체 때 Executor 무변경(Port의 값 증명), **Controller 종단(`waiting_external`→resume)은 아직 미관측**이라 remote-team-a2a.md의 매핑이 설계임을 명시. → [a2a-protocol.md](../../../final_project_cs/wiki/external/a2a-protocol.md) |

| DoD-08 (3/6) | evidence의 **증명 대상 자체가 없다** — 제목·판정 근거가 `BillingSubscriptionTeam`·`TechnicalEntitlementTeam`인데 둘 다 2026-08-18 퇴역. 21·13의 "라벨만 옛것"과 다른 종류로 drift 표에. 기제(계약 validator 3보장)는 `team-contract/index.md`의 `model_validator` 절에 이미 있어 추가 안 함. → [dod-evidence-drift.md](../../../final_project_cs/wiki/quality/dod-evidence-drift.md) |
| DoD-19 (3/5) | 원격 상태 어휘가 `TeamResult` 밖으로 안 샌다(`input_required`→`wait_for_input`)는 점을 a2a-protocol에. `observed_at` 클럭 틱으로 `model_dump()` 비교가 흔들린 **원인 확정 flake**를 blind-spots의 원인 미확정 동시실행 건과 대비해 추가. → [blind-spots.md](../../../final_project_cs/wiki/quality/blind-spots.md) |
| DoD-20 (3/5) | drift 표엔 이미 "테스트 경로 이동"으로 있었음. 빠진 건 조립 실패 조건 둘 — 미구현 port(`redis_streams`·`age`·`neo4j`) 선택은 조립 실패, `a2a`는 모듈 off면 선택 불가. "선언 교체 ≠ 원격 실행 확인" 한계는 DoD-26 종단 미완과 같은 것. → [teams/index.md](../../../final_project_cs/wiki/teams/index.md) |
| EVAL-DATASETS (3/7) | golden/holdout 인수 검사 9종(핵심은 `doc_ref`가 실제 25문서 색인과 **문자열 완전일치**해야 한다는 것 — judge 환각 인용 사고와 같은 뿌리)과 Codex 산출물을 받을 때 한 검수 4단계(독립 재실행·표본 12건 사람 확인·단위 붙은 숫자 주장 전수 추출 → 1건뿐, 코퍼스와 일치). 재작성이 낡은 테스트 단언(옛 `g-billing` 배분)을 드러낸 것도. → [golden-set.md](../../evaluation/golden-set.md) |

### 6차 결과 — 28건 전부 직접 대조 완료 (2026-09-06)

| | 건수 |
|---|---:|
| wiki에 채우거나 고친 것이 있었던 evidence | **26** |
| 읽었지만 이미 충분해 손대지 않은 것 | 2 (02·09) |
| **wiki 자체가 틀려 있던 곳** | **8** — dod.md "통과 29"·17번 "파일시스템 gate"·23번 표, shared-state의 `INV-CS-RT-001~004`, a2a-protocol 취소 상태, outbox 스키마 `UNIQUE`, rest-api "정확히 5개"×3, remote-team-a2a `waiting_external` |
| 새로 만든 페이지 | 2 — `context/graph-retrieval.md`, `quality/dod-evidence-drift.md` |
| 테스트를 읽다 찾은 것 | 빈 테스트 1(`must_be_scoped`), docstring↔코드 반대 1 |
| **evidence 쪽이 낡아 cs 저장소 작업자에게 넘길 것** | DoD-06(sample을 잰 것) · 08(대상 Team 퇴역) · 13·21(옛 라벨) · 14·22·02·20·24(일부 낡음) |

**스캔 도구가 가장 값진 데 두 번 맞았고 두 번 틀렸다.** DoD-07·17은 신호 적중 0건이 맞게 "통째로 없다"였고, DoD-29·24는 "2/9·4/11 적중"이 결함 발견으로 이어졌다. 반면 DoD-02·09는 적중이 낮아도 이미 충분히 반영돼 있었고, DoD-13은 적중 3/5인데 wiki가 코드보다 낡아 있었다 — **적중률은 읽을 순서를 정해 줄 뿐 판정을 대신하지 못한다.** 이 도구가 스스로 적어 둔 그대로다.

## 7차 — evidence 검증 로그 5건 (2026-09-06)

`[실측]` DoD 28건에 이어 같은 폴더의 검증 로그 5건. 이걸로 `final_project_cs/docs/evidence/` 35건 전부를 직접 대조했다. 남은 `유지` 문서는 59 → 54건이고, `audit_coverage.py`로 스캔한 순위는 이 세션 로그에 있다(데이터셋 REPORT 7건·VISION 7건·handoff 04/10이 다음 후보. 일일 작업 로그·폐기된 방식의 원인 분석 기록은 "그 시점 기록"이라 이관 대상이 아닐 가능성이 커 뒤로).

| 대조함 | 찾은 것 |
|---|---|
| LIVE-CLASSIFIER-E2E (7/7) | 실 API 경로 e2e 테스트가 wiki에 없었다. 만들며 드러난 계약 오해 둘 — `create_app(controller=None)`이 Controller를 막지 않는다(기본 classifier의 `__module__`이 `app.composition`이면 항상 진짜 Controller), 합성 고객이라 escalate가 정상이므로 단언을 "분류 성공"으로 좁힘. teardown이 `agent_runs` 계열을 안 지워 tenant 하나가 DB에 영구히 남았던 것도. → [rest-api.md](../../../final_project_cs/wiki/external/rest-api.md) |
| PROD-CLASSIFIER-DOMAIN-MISMATCH (4/7) | 결함 자체는 이미 있었다. 빠진 건 `INTENTS`가 왜 운영 경로인지(`create_app → build_classifier → feedback.classify`), "얼마나 오래 있었는지 모른다", 재발 방지 테스트가 **invariants 카탈로그에 ID가 없다**는 점. → [rest-api.md](../../../final_project_cs/wiki/external/rest-api.md) |
| EVAL-RUNNER-IMPORT-FIX (4/6) | pytest가 `eval/runners`를 한 번도 import하지 않아 리네임 결함이 안 잡혔고, 제안된 smoke test를 안 만들어 **이틀 뒤 같은 파일에서 같은 결함이 재발**(DoD-28 08-20). 지금은 `test_team_failed_penalty.py`가 `eval.runners.common`을 import해 부산물로 닫힘. → [blind-spots.md](../../../final_project_cs/wiki/quality/blind-spots.md) |
| 2026-08-31 회귀테스트_검증 (5/6) | 결함 18건 전부 잡힘(424→470)은 좋은데, `INV-STATE-001`은 **결함을 심어도 단독 5회 중 4회 통과** — 진 쪽이 읽는 시점에 따라 `StateConflict` 대신 `InvalidTransition`. 게이트 48/48이 이 종류를 구분 안 하고 센 값이라는 점을 blind-spots에, 예외 종류가 타이밍에 달렸다는 성질을 conflict-retry에. 고쳐졌는지는 `[미확보]`. → [conflict-retry.md](../../../final_project_cs/wiki/runtime/conflict-retry.md) |
| MODULE-TOGGLES (3/8) | **evidence가 결함을 정상으로 승인한 다섯 번째 종류** — `voc: false` → 기동 거부를 "통과"로 판정했는데 이틀 뒤 v8 재판정이 그 결합을 결함 1번으로 뒤집었다. 로그가 틀린 건 아니다("선언대로 동작하는가"엔 맞았다) — 선언이 틀렸다는 건 로그가 물을 수 없는 질문이었다. "모듈 꺼짐" 표기(빈칸은 껐다/고장을 구별 못 함)와 `--reload` 함정(조립은 기동 때 한 번, reload 자식이 옛 코드를 서빙)도 채움. → [dod-evidence-drift.md](../../../final_project_cs/wiki/quality/dod-evidence-drift.md), [run.md](../../../final_project_cs/wiki/operations/run.md) |

## 8차 — 데이터셋 문서 5건 (2026-09-06)

`[실측]` 루트 `CLAUDE.md`가 "각 데이터셋의 정본"으로 지정한 REPORT/README 중 5건. `catalog.md`는 일부러 얇은 지도라 본문이 안 옮겨진 건 설계이고, **함정·결론·규칙 위반**만 골라 채웠다. 남은 `유지` 문서 54 → 49건.

| 대조함 | 찾은 것 |
|---|---|
| data_go_kr REPORT (4/5) | EUC-KR 인코딩 함정이 wiki에 없었다. 디스크를 보니 REPORT의 "processed/·scripts/ 없음"이 **낡았고**(15090382 XML에서 Team 근거 사례 2종을 뽑아 둠), 그 추출 스크립트 둘이 **`scripts/`가 아니라 `processed/` 안에** 있어 폴더 규칙 위반. "원문은 15098320뿐"은 report-split.md에 이미 있었음. → [catalog.md](../../../datasets/wiki/catalog.md) |
| kaggle REPORT (4/6) | KR3 라이선스·"학습 본체 아님" 방침은 이미 반영. 죽은 링크 1건·두 CSV 동일 여부 미확인은 REPORT에 두는 게 맞아 안 옮김 |
| sources_catalog REPORT (2/6) | catalog.md의 "아직 안 받은 후보 목록"이 낡았다(대부분 받아 독립함). HuggingFace 감정분류 모델 4종·KOTE가 wiki에 없었고, **"감정 축 검증 못 한다"로 닫은 항목의 후보**라 golden-set.md에 [미확보] 단서로 연결 — 댓글 감정이지 상담 감정은 아니라 축 판단은 사람 몫. → [golden-set.md](../../evaluation/golden-set.md) |
| naver README (4/6) | 두 쇼핑몰이 같은 `order_schema.json`으로 낸다는 점, `_source.normalization_warnings` 4종(연도 추정·수량 기본값·배송 JSON 누락)의 뜻, PII 처리가 둘이 다르다는 점(네이버 해시·쿠팡 미수집). → [catalog.md](../../../datasets/wiki/catalog.md) |
| courier_tracking README (4/7) | 네이버 내부 API(`passportKey` JSONP 주입, `fetch` 금지)라 바깥 관측이라는 점, 오류 6종 중 `no_history`는 보관기간 만료일 수 있어 실패로 세면 안 된다는 점, 저장 제외 PII 목록. → [scraper-notes.md](../../../datasets/wiki/scraper-notes.md) |

## 9차 — cs 계약·매뉴얼 4건 + WBS 원본 (2026-09-06)

`[실측]` handoff 04·06·10(2차에서 01·02·03·08만 봤다), 환경 기동절차 매뉴얼, 루트 `CLAUDE.md`가 일정 정본으로 지정한 `_WBS원본`. 남은 `유지` 문서 49 → 44건.

| 대조함 | 찾은 것 |
|---|---|
| handoff/04 Team 모듈 계약 (2/7) | 규칙은 team-contract에 다 있었다. 낡은 건 **예시 Team 둘이 퇴역**했고 §3 "프롬프트 등록 미구현"이 세 번 뒤집혔다는 것 — team-contract/index.md에 "원본에서 낡은 것" 표로. → [team-contract/index.md](../../../final_project_cs/wiki/teams/team-contract/index.md) |
| handoff/06 가드레일 수치 (3/11) | **§4-A sweeper(2026-09-03 추가)가 wiki에 전혀 없었다** — 멈춘 Case 되잡기, 임계값(안전) vs 주기(복구 지연) 구분, `errored`≠`failed`. 스크립트·마이그레이션 009·yaml 키 실재 확인 후 guardrails.md·run.md에. §5 scope 6종도 handoff/03과 같이 낡아 auth-boundary 표에 행 추가. → [guardrails.md](../../../final_project_cs/wiki/quality/guardrails.md) |
| handoff/10 도메인 교체 가이드 (4/11) | domain-swap.md에 "이 문서가 생긴 이유"(08-16 Core에 구독 어휘, 계획서 예시를 스펙으로 읽음)가 없었다. 구체 값 4개(도메인 테이블·Team 파일·청크 수·fixture 수)가 옛 도메인인 것도 표로. → [domain-swap.md](../../../final_project_cs/wiki/domain-swap.md) |
| manuals/환경 기동절차 (4/8) | 3차에서 함정 셋을 옮겼는데 **정작 PG를 어떻게 띄우는지가 없었다** — `pg_ctl` + `-o "-p 5433"`(빠뜨리면 5432), 데이터 디렉터리가 저장소 밖이고 옆 프로젝트 DB와 같은 서버, 복구 40초, extension은 마이그레이션만. → [local-setup.md](../../../final_project_cs/wiki/operations/local-setup.md) |
| _WBS원본 (4/6) | 날짜·주차·산출물 21건은 timeline.md에 있었다. 빠진 건 wiki 곳곳의 "10주"가 선행 포함 총 기간이라는 뜻풀이(공식은 8.5주), 그리고 원문이 "판단 필요"로 남긴 미결 둘 — **sLLM 파인튜닝이 6팀 필수인가**(시트 문구 "3, 4번 팀"), **3W 산출물 "학습한 모델"에 무엇을 내나**(파인튜닝 미채택). open-items "아직 안 정한 것"에도 올림. → [timeline.md](../../delivery/timeline.md) |

## 다음

| # | 할 일 |
|---|---|
| 1 | **`_codex_추적화면_교차검증` 14/14 누락** — 통째로 안 됐다 |
| 2 | "일부" 35건의 빠진 부분 채우기 |
| 3 | ~~DoD evidence 28건 직접 대조~~ **완료 (6차, 2026-09-06)** |
| 4 | 나머지 186건도 같은 방식으로 대조 |

## 관계

- [index.md](index.md) — 이관 범위
- [judgments.md](judgments.md) — 판정 내역
- [../type-verification/round-7.md](../type-verification/round-7.md) — 대조 7번에 누락 7건
