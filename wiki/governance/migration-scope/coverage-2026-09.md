---
type: report
title: 반영률 실측 — 6차 이후
description: 2026-09-04~07 대조 6~19차. 19차에서 대조필요 39건을 다 훑고 격차 넷을 건졌다
status: draft
tags: [governance, documentation]
domain: commerce
---

# 반영률 실측 — 6차 이후

`[실측]` [coverage.md](coverage.md)가 300줄을 넘어 6차부터 여기로 옮겼다(2026-09-06). 링크는 같은 폴더 기준이라 그대로다. 1~5차와 방법은 [coverage.md](coverage.md).

## 6차 — DoD evidence 28건

`[실측]` 2026-09-04. `_gap_audit.md` 류 수기 대조 대신 `audit_coverage.py`로 `final_project_cs/wiki/records/evidence/DoD-02`~`29`·`DoD-EVAL-DATASETS` **28건 전체**를 기계로 훑고, 반영률이 낮은 것부터 직접 대조했다.

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

`[실측]` DoD 28건에 이어 같은 폴더의 검증 로그 5건. 이걸로 `final_project_cs/wiki/records/evidence/` 35건 전부를 직접 대조했다. 남은 `유지` 문서는 59 → 54건이고, `audit_coverage.py`로 스캔한 순위는 이 세션 로그에 있다(데이터셋 REPORT 7건·VISION 7건·handoff 04/10이 다음 후보. 일일 작업 로그·폐기된 방식의 원인 분석 기록은 "그 시점 기록"이라 이관 대상이 아닐 가능성이 커 뒤로).

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

## 10차 — acop_dojo 2건 (2026-09-06)

`[실측]` `acop_dojo/README.md`(4/9)와 `학습게임_설계검수`(8/15). `테스트_사각지대_실측.md`는 자동 생성물이라 blind-spots.md가 요약이라고 스스로 밝혀 대조 대상에서 뺐다. 남은 `유지` 문서 44 → 42건.

| 대조함 | 찾은 것 |
|---|---|
| acop_dojo/README (4/9) | **`acop_dojo/wiki/index.md`가 틀려 있었다** — "cs 카탈로그 33개·26 automated·사람 판정 7(Runtime 4)"인데 33은 dojo 원장 수이고 cs 카탈로그의 review는 TEAM-003·004·005 셋뿐. "Runtime 4"는 shared-state 오기재의 전파. `guide.md`는 "트랙 7개"라며 6개만 적었고(`front` 누락) 명령 5개(`invariants`·`patches`·`defects`·`stability`·`map`)가 빠짐. patch가 조용히 낡는다는 것(routes.py 14줄에 INV-UI-001 patch가 낡았는데 아무도 몰랐다 → `patches` 4초), 규칙은 grep으로 발견하지 않고 원장에 선언한다는 것, 사본은 `eval/reports`만 빼고 `legacy/` 포함이라는 것을 generation.md에. → [index.md](../../../acop_dojo/wiki/index.md), [guide.md](../../../acop_dojo/wiki/guide.md), [generation.md](../../../acop_dojo/wiki/generation.md) |
| 학습게임_설계검수 (8/15) | design-review.md가 7약점·5권고를 충실히 옮겼는데 **그 권고가 같은 날 완성된 도장에 이미 반영됐다는 게 없어** 검수가 설계를 멈춘 것처럼 읽혔다. 권고별 반영 표(1·3·4 반영, 2 일부, 5 [미확보] — design-principles 원칙 8은 아직 "1·3·7일")를 추가. → [design-review.md](../../../acop_dojo/wiki/design-review.md) |

## 11차 — VISION 문서군 9건 (2026-09-06)

`[실측]` VISION-01~07 · TODO_VISION · ESTIMATION_BASELINE. 대조 대상은 `product/vision-backlog.md`와 `delivery/estimation-baseline.md`. 남은 `유지` 문서 42 → 33건. VISION-08·09는 34줄이라 이관 판정이 `판정필요`로 남아 있으나 트리거·비용은 backlog에 이미 있다.

| 대조함 | 찾은 것 |
|---|---|
| VISION-01~07 | backlog에 트리거·비용·폐기 조건은 있었지만 **"지금 안 하는 이유"(§2)와 "선행 조건"(§5)이 통째로 없었다.** 둘 다 표로 채웠다 — 선행 조건은 이 세션에서 확인한 현재 상태와 바로 대조된다(consumer 계약 테스트 있음 / 프로세스 kill 주입·키 회전·Graph 성능 계측·검색 실패 유형 없음). **VISION-01 §1의 "현재 self-consistency N=2·규칙 기반 replan"은 `app/`에 없다**(grep 0건, v5 시절 서술). **VISION-07(검토중, 환불 룰 테이블)은 D-001(환불 계산을 쇼핑몰에)과 전제가 부딪히는데 정한 기록이 없다** `[미확보]`. D-013(선언형 Team)과의 연결도 추가. → [vision-backlog.md](../../product/vision-backlog.md) |
| TODO_VISION | backlog가 이미 정본 수준. 개정 이력의 "2026-08-13 실소요 재산정" 근거는 estimation-baseline이 담고 있어 추가 없음 |
| ESTIMATION_BASELINE (5/11) | estimation-baseline.md가 충실. 빠진 건 "검증이 병목" 증거 셋 중 둘(RAG `::vector` 100% 실패, `resuming→completed`)과 **18,390줄의 구성 — 절반이 문서(8,718줄)**라는 점. 코드 생산성으로만 읽으면 안 된다는 주의를 보탬. → [estimation-baseline.md](../../delivery/estimation-baseline.md) |

## 12차 — 계획 문서 4건 (2026-09-06)

`[실측]` `program/plan/A-COP_Composer_소유권_정정`(3/8) · `plan/diagram/_다이어그램_근거`(4/10) · cs `final_project_cs/wiki/records/plans/2026-08-16_v7_격차해소_실행계획.md`(11/18) · `2026-08-30_2100_모듈토글_실효화_설계`(2/7). 남은 `유지` 문서 33 → 29건.

| 대조함 | 찾은 것 |
|---|---|
| Composer 소유권 정정 | [D-006](../../decisions/D-006-composer-ownership.md)이 §8.1 오독·"import 금지 대상은 cs"·허용/금지 표·후속 조치 3(패키지 이름 → open-items)까지 담고 있다. **추가 없음** — 스캔 3/8은 거짓 신호 |
| 다이어그램 근거 | [architecture/diagrams.md](../../architecture/diagrams.md)가 이 문서에서 이관됐고 렌더 명령·archive 표까지 있다. **추가 없음** |
| v7 격차해소 실행계획 (11/18) | P1~P4의 내용은 DoD-24·25·13·28로 전부 wiki에 있었다. 빠진 건 **순서 논리** — v7 §9-E 제목이 "쓰기 권한을 여는 전제 조건"이라 방어(P1·P2)가 먼저고 MCP 쓰기 확장(P7)은 그 뒤에만, 그리고 "막는 코드 → 재는 수단(P4)" 순서. mcp-tools.md 쓰기 3단계에 붙였다. 실행계획의 진행 기록이 "P1 착수"에서 멈춘 낡음도. → [mcp-tools.md](../../../final_project_cs/wiki/external/mcp-tools.md) |
| 모듈토글 실효화 설계 (2/7) | 승격 사슬의 마지막 고리(`composition.py:44`)가 **의식적 설계였고 그 자리에서 "껄끄럽다"고 적혀 있었다**는 게 drift-case-voc.md에 없었다. 같은 문장(CLAUDE.md §1 "인라인 분류는 선택 기능이 아니다")이 이틀 사이 정반대 결론의 근거가 됐다 — 모순이 문서 사이가 아니라 한 문장의 두 해석 사이에 있어 점검 항목 4로도 못 잡는 종류. 작업 전 "여섯 중 셋만 코드를 갈랐다"는 이전 상태를 teams/index.md에. → [drift-case-voc.md](../drift-case-voc.md) |

## 13차 — research 색인·점검 기록·분업 규칙·산출물 양식 5건 (2026-09-06)

`[실측]` `research/index.md`(4/12) · `_정본대조_2026-08-18`(3/4) · `_정합성점검_2026-08-19`(3/8) · `handoff/05_분업_규칙`(0/7) · `산출물양식/README`(2/9). 남은 `유지` 문서 29 → 24건.

| 대조함 | 찾은 것 |
|---|---|
| research/index.md | **루트 `CLAUDE.md`가 "정본"이라 가리키는 "현재 기준 사실" 표가 index.md에 없다** — 08-18 정본대조 땐 있었고 08-19 정리에서 사라졌다. index.md는 v8을 정본으로 가리킬 뿐이라 포인터 사슬이 한 칸 비었다. 점검 캘린더의 `migration-scope.md` 링크는 폴더 승격으로 죽은 링크. 원본 수정은 범위 밖이라 review-policy에 기록하고 open-items에 올림. → [review-policy.md](../review-policy.md) |
| _정본대조 08-18 | cs·sample `CLAUDE.md`의 §0(v8)과 §7 문서 목록(`v6` 죽은 링크)이 한 파일 안에서 다른 기준선을 말했던 사고 — drift-case-voc와 같은 종류. review-policy "같은 종류의 사고" 표에 |
| _정합성점검 08-19 | 문제 8건·권고 5건 중 **5번(B-1·C-1)만 wiki가 추적**하고 1~4(브리핑 Team 분리 카드, index.md 원본 파일명 참조, v8:407 없는 HTML, §0-2 색인 누락)의 처리 여부는 기록이 없다 `[미확보]` |
| handoff/05 분업 규칙 (0/7) | `parallel-work.md`가 Codex 샌드박스 외부망 차단(540건 APIConnectionError)·받은 뒤 검사 4종·소유 디렉터리(roles.md)까지 담고 있다. **추가 없음** — 스캔 0/7이 맞았다 |
| 산출물양식/README | 양식 18개 → 근거 문서 대응표가 wiki에 없었다. 중간발표(9/15) 직전이라 timeline.md에 wiki 페이지 기준으로 옮겼다. README의 "VOC 5종 전처리 전"은 낡았고(08-31 기준 완료 5·미착수 4), "GGUF 결과는 양자화 문제로 못 쓴다, 08-24 GPU 재검증이 정본"은 mt-benchmark.md에 없어 보완 대상. → [timeline.md](../../delivery/timeline.md) |

## 14차 — 루트 CLAUDE.md·datasets README·DISTRIBUTION·판 이력·브리핑 지시 5건 (2026-09-06)

`[실측]` 루트 `CLAUDE.md`(0/6) · `datasets/README.md`(3/9) · `datasets/commerce/DISTRIBUTION.md`(4/7) · `onboarding/versions/README.md`(5/5) · `briefing/S-BRIEFING-POLISH.md`(0/4). 남은 `유지` 문서 24 → 19건.

| 대조함 | 찾은 것 |
|---|---|
| 루트 CLAUDE.md | 기준 사실 표(v8·Team 목록·DoD 29·Phase 2·일정)·TeamFlow 6팀·데이터 폴더·도장 사각지대 전부 wiki에 있다. **추가 없음.** 13차에서 적은 "이 표의 정본은 `research/index.md`"라는 포인터가 빈 칸인 문제만 남아 있다(open-items) |
| datasets/README | **catalog.md의 VOC 현황이 하루 낡아 있었다** — "완료 5·미착수 4·924MB"(08-31)인데 정본 README는 09-01 실측으로 aihub 3종 완료, 미착수는 `kaggle_customer_support` 463MB뿐. 13차 timeline.md 주석도 같은 낡은 값을 옮겨 적었기에 둘 다 고침. data_go_kr 근거 사례 건수(53·89, 합집합 93)와 courier_tracking 제출본 5명분이 `processed/`에 안 합쳐진 것(57건 그대로)도 없었다 → [catalog.md](../../../datasets/wiki/catalog.md) |
| DISTRIBUTION (4/7) | **거짓 신호였고, 나도 속았다.** [distribution.md](../../../datasets/wiki/distribution.md)가 세 종류·5,773줄·열쇠 위치 51건·내보낼 때 지울 둘까지 이미 다 갖고 있었다. 14차에서 catalog.md에 같은 내용을 한 번 더 적었다가 15차에서 포인터로 줄였다. 진짜로 없던 건 둘 — **catalog.md와 scraper-notes.md가 distribution.md를 가리키지 않아** 데이터셋 목록에서 출발하면 PII 규칙에 못 닿았다는 것, 그리고 courier_tracking `processed/`가 제출본과 안 합쳐진 57건 그대로라는 것 |
| onboarding/versions/README (5/5) | 스캔이 맞았다. trace-review.md가 codex 지적 6개 중 5·6번을 `[미확보]`로 남겼는데 **이 README가 "확인되어 고친 것 11건 / 받아들이지 않은 것 4건"을 이미 표로 갖고 있었다** — 09-02 코드 확인과 어긋남 없음. 5·6번을 채우고 "맞다, 그런데 안 한다" 4건(`cut()` AST는 다음 판, 신선도 검사는 미착수)을 옮김. v2→v8 판 이력의 "왜 바꿨나"는 generation.md에 → [trace-review.md](../../../acop_dojo/wiki/trace-review.md) · [generation.md](../../../acop_dojo/wiki/generation.md) |
| S-BRIEFING-POLISH | 완료된 작업 지시 티켓(judgments.md가 이미 그렇게 판정). 문체·UI 기준은 그 HTML 한 파일에 대한 지시라 wiki에 옮길 규칙이 없다. **이관 없음** — TSV의 `유지`는 judgments와 어긋나므로 다음 재생성 때 `제외`로 |

## 15차 — 쿠팡 확장 README 2건·폐기 계획 2건·추적 영상 리포트 (2026-09-06)

`[실측]` `scripts/extension/README.md`(6/9) · `extension_nextdata_ref/README.md`(5/8) · `docs/재작성_계획`(4/5) · `docs/클릭_구현_계획`(3/4) · `onboarding/trace/S-TRACE-VIDEO_리포트`(9/9). 남은 `유지` 문서 19 → 14건.

| 대조함 | 찾은 것 |
|---|---|
| extension README 둘 | **scraper-notes.md의 "선택자는 해시 클래스를 안 쓴다"(09-02 추가) 절이 폐기된 방식을 현행처럼 적고 있었다.** 5.4.1(08-21)부터 목록은 `__NEXT_DATA__` JSON이고 DOM 카드 수집기·클릭기·연도 탭은 삭제됐다 — REPORT가 "과거 `docs/`의 클릭 관련 문서는 폐기된 방식의 원인 분석 기록"이라 명시. 확장이 폴더 넷(현행·nextdata_ref·백업·legacy)이고 README 둘 제목이 같다는 것, `fetch`가 406으로 막혀 문서 이동으로 간 이유, 서비스 워커가 keepalive 없이 재개되는 방식, 정확성 장치 표는 wiki에 없었다. 새 페이지 → [coupang-extension.md](../../../datasets/wiki/coupang-extension.md). scraper-notes의 DOM 절은 "JSON 경로가 막혔을 때 되살릴 관측"으로 표 하나에 접음 |
| 재작성_계획 · 클릭_구현_계획 | 스캔이 "폐기 기록"이라 이관 없음으로 보려 했는데 **`docs/작업기록.md`의 근본 원인 8개가 학습 가치가 있었다** — 진짜 원인(`args: [method, undefined]`)은 5번째에 나왔고 앞 넷은 그 그림자였다. 테스트가 못 잡은 이유 셋이 전부 "대역이 실물보다 관대했다"로 모인다. Codex가 `forceWrongReturnOnce`를 끈 사고는 parallel-work.md의 "받은 뒤 검사"와 같은 종류. 같은 페이지에 |
| S-TRACE-VIDEO 리포트 (9/9) | 스캔이 맞았다. 영상 재생성 명령, 체류 시간 산식(글자 수 ÷ 7.2), PNG 17장 SHA 불변, 내용 정확성 항목, 규격이 dojo wiki에 없었다. generation.md "판 이력" 아래에. **mp4가 넷인데 리포트는 하나만 말한다** `[미확보]` → [generation.md](../../../acop_dojo/wiki/generation.md) |

## 16차 — 일일작업 3건·08-12 평가 리포트·법령사실·검수결과·밤샘요약·사각지대 초판 (2026-09-06)

`[실측]` `_일일작업_2026-08-26/27/28` · cs `eval/reports/2026-08-12_평가결과_리포트` · `_법령사실_2026-08-15` · `_검수결과_2026-08-17` · `_밤샘작업_요약_2026-08-20` · `테스트_사각지대_2026-08-30`. 남은 `유지` 문서 14 → 6건.

| 대조함 | 찾은 것 |
|---|---|
| 일일작업 08-26 | 본문이 비어 있는 게 내용이다 — "없는 것을 추측으로 채우면 지어낸 것". review-policy에 규칙으로 → [review-policy.md](../review-policy.md) |
| 일일작업 08-27 | sample `docs/vision/` VISION-10~12가 wiki 어디에도 없었다. vision-backlog는 cs 01~09만 다룬다(impl_scope cs). 목록만 올리고 트리거는 `[미확보]` → [vision-backlog.md](../../product/vision-backlog.md) |
| 일일작업 08-28 | 선언형 Team(D-013)·스프린트 4/에픽 13(ticket-structure)·주말 요약(midterm)은 있었다. 없던 셋 — **Composer 화면 결함 3건**(사유 누락으로 적용이 항상 422 · 계약 버전 `v1`≠`1.0` · 토글 상태 세 모양)은 sample ui-boundary.md에, **송장 58→57의 이유**(08-21 재조회 중복 1건)는 catalog.md에, 기획서를 제출표 기준으로 다시 쓴 사건과 "산출물은 생성기로" 방식이 자리 잡은 날이라는 건 midterm에 이미 같은 취지가 있어 생략 |
| eval/reports 08-12 | protocol.md 측정 결함 1번(provider=mock)이 이 파일이다. **파일이 지표 전부 1.00인 채로 `eval/reports/`에 남아 있다**는 것만 없었다 — 인용 금지 한 줄 → [protocol.md](../../evaluation/protocol.md) |
| 법령사실 08-15 | legal-basis.md가 "웹 검색 요약이라 원문을 우선"으로 이미 자리매김했고 청약철회·국외이전·통신판매업 50회 면제·Bitext·LoRA 500건 미만이 다 있다. **추가 없음** |
| 검수결과 08-17 | 제출 엑셀 10지적(과장 2·근거 없음 2·틀림 3·불일치 3). Fin 근거를 Sierra·Decagon으로 확장 금지, 자체호스팅은 방향이지 구현 완료 아님, 9W 기간 표기 없음은 positioning·timeline에 있다. ERD `prompts` UNIQUE 둘·`sha256` 불변이 DDL 제약이 아니라는 지적은 sample 스키마 이야기라 sample wiki에 없지만 **그 엑셀 산출물 자체가 낡아** 옮길 값이 없다. 그 시점 기록 |
| 밤샘작업 요약 08-20 | 보고서 9건의 색인이고 각각은 design-gap·D-011·dod.md·정합성점검(13차)으로 이미 대조됐다. "결정이 필요한 것" 9건 중 Composer v3 넷은 D-011, DoD 순서는 dod.md, 정합성 A묶음은 완료. **DoD-01 원본 v4 hash 판정 불가·예제 Team 2개 활성 등록**은 그 뒤 어떻게 됐는지 기록이 없다 `[미확보]` |
| 테스트_사각지대 08-30 (대체됨) | 초판이 "원인 모름, 격리 문제일 가능성"으로 남긴 INV-STATE-001 흔들림은 conflict-retry.md가 답했다. **둘째 흔들림**(`test_approval_rerun…` 전체 실행 1회 실패)과 `dojo.py stability --repeats 5`가 없어 blind-spots.md에 → [blind-spots.md](../../../final_project_cs/wiki/quality/blind-spots.md) |

## 17차 — cs 구현현황 스냅샷·VOC 완결성 점검·dev2 교차검증 (2026-09-06)

`[실측]` `_cs_구현현황`(08-19) · `sources_catalog/_완결성점검_codex_2026-08-20` · `dev2_브리핑_교차검증_2026-08-28`. 남은 `유지` 문서 6 → 3건 — 남은 셋은 1~5차 표에서 "누락 1·2·3"으로 센 `_법령원문`·`_분쟁조정사례`·`_중앙설정저장소_검토`의 잔여분이라 스캔으로 자리를 찾아 마무리한다.

| 대조함 | 찾은 것 |
|---|---|
| _cs_구현현황 (08-19) | 빈 패키지·`ALLOWED_PROMPT_KEYS` 빈 집합·테이블 18 vs 14는 이미 wiki에 있었다. 없던 건 **등록 Team 수의 궤적** — 08-19엔 `voc_store_manager` 하나였고 RGR은 미등록, 09-01 v8이 그 둘의 지위를 맞바꿨고, 09-06엔 여섯이 전부 active. 그리고 **teams/index.md의 VOC 행이 "10주 착수 확정"으로 낡아 있었다**(v8 09-01은 껍데기) — 고침. `return_refund`가 Mock인지 실구현인지 등록만으론 안 보임 `[미확보]` → [team-registry.md](../../../final_project_cs/wiki/teams/team-registry.md) |
| _완결성점검_codex | source-selection.md가 후보 A~E·잔여 갭 결론을 갖고 있었다. 없던 건 §2.1의 **5단계 절차와 "매핑표 전엔 확정 데이터셋으로 세지 않는다"**, 그리고 08-28 REPORT가 그중 무엇을 했는지 — 파일명 파티션으로 도메인 분리는 됐고 intent 매핑은 300건 샘플·90% `*_other`·검수 미완. catalog의 "완료"가 뜻하는 범위를 좁힘. §2.2 3단계 필터도 미착수 → [source-selection.md](../../../datasets/wiki/source-selection.md) |
| dev2_브리핑_교차검증 | scope-verdicts.md가 안건 7건·분모 질문을 담고 있었다. 없던 건 **Return & Refund LOCAL 승격 조건**(사유 코드·상태 전이 확인 → golden 배분, 당시 0)과 그 뒤 판단 기록이 없다는 것, `verdict`≠`outcome` 매핑 규칙 → [scope-verdicts.md](../../delivery/scope-verdicts.md) |
| (부산물) | **`final_project_sample/wiki/`가 통째로 git 무시 대상**이다 — 16차의 ui-boundary.md 편집이 커밋되지 않아 알았다. 루트 `.gitignore`의 `final_project_sample/`이 `program/` 아래 사본에도 걸린다. open-items에 올림 |

## 18차 — 1~5차 잔여분 셋: 법령원문·분쟁조정사례·중앙설정저장소 검토 (2026-09-06)

`[실측]` 스캔 `_법령원문`(2/4) · `_분쟁조정사례`(2/6) · `_중앙설정저장소_검토`(5/8). 남은 `유지` 문서 3 → **0건.** 목록의 유지 문서를 전부 한 번씩 사람이 대조했다.

| 대조함 | 찾은 것 |
|---|---|
| _법령원문 | 스캔이 "신호 없음"으로 올린 두 절(조회 방법·남은 것)은 코드 블록과 목록이라 지문이 안 잡힌 것이고, legal-basis.md의 "조회 방법"·"미확보·후속 범위"가 문장 단위로 다 갖고 있다. **추가 없음** |
| _분쟁조정사례 | 같다 — dispute-cases.md "수집과 재현"·"조사 한계"에 336건 중 4건 선별, 재배포 정책 미확인, `searchCnd=3` 추가 검색까지 있다. **추가 없음.** 1~5차 표의 "누락 2"는 그 뒤 이관된 것으로 보인다 |
| _중앙설정저장소_검토 | D-007에 자체호스팅 충돌·제안(두 배포 형태)·구현 상태는 있었다. 없던 건 **§6 더 물어야 할 것 넷**(감사 로그 위치 · `deployment_id` 발급자 · 중앙 유출 = 고객사 3,000곳 · 이번 기간에 하나/에픽 없음)과 §1 "산출물 세 문서가 '아직 연결 안 됨'이라 적었다"는 것 → [D-007](../../decisions/D-007-central-config-store.md) |

### 6~18차를 마치며

`[실측]` 스캔 판정후보의 적중률 — "신호 없음·누락 후보"가 실제 누락이었던 건 대략 절반이다(14차 DISTRIBUTION·12차 Composer 정정·18차 둘은 거짓 신호, 15차 확장 README·11차 VISION·17차 완결성 점검은 진짜). **거짓 신호의 원인은 둘** — 코드 블록·표·목록은 지문이 안 잡히고, 같은 내용이 다른 wiki 페이지에 있으면 스캔이 못 찾는다(14차에 나도 같은 이유로 중복을 적었다). 스캔은 읽는 순서를 정하는 도구지 판정 도구가 아니라는 [coverage.md](coverage.md)의 결론이 그대로다.

남은 것은 이관이 아니라 **판정**이다 — open-items의 `[미확보]`(Return & Refund 승격, DoD-01 v4 hash, mp4 넷, sample wiki git 무시 등)와 cs 저장소 쪽 수정(DoD evidence 9건, `research/index.md` 둘)은 사람 몫이다.

## 19차 — 대조필요 39건 일괄 (2026-09-07)

`[실측]` `_verify*.tsv` 에서 `대조필요` 로 남아 있던 **39건 전부**를 절 단위로 훑었다.
`audit_coverage.py` 는 파일 하나마다 wiki 를 다시 읽어서, wiki 를 한 번만 적재하고
39건을 도는 방식으로 바꿔 돌렸다.

```
절 334개  ·  누락후보 29  ·  일부후보 34  ·  반영후보 181  ·  신호없음 90
```

**63개 후보를 읽어 진짜 격차 넷을 건졌다.** 적중률은 6~18차와 비슷하게 낮다.

| 찾은 것 | 어디로 |
|---|---|
| **outbox 제약에 `tenant_id` 가 빠진 채였다** — 살아 있는 DB 는 `UNIQUE (tenant_id, topic, dedupe_key)` 인데 wiki 세 곳이 옛 제약을 실었다. `idempotency.md` 는 스니펫 주석이 `003_outbox_tenant_scoped_dedupe.sql` 을 가리키면서 **그 마이그레이션 전 값**을 싣고 있었다 | [idempotency.md](../../../final_project_cs/wiki/actions/idempotency.md) |
| **말 네 개 구분(컴포넌트·모듈·Port·인스턴스)이 wiki 에 없었다** — handoff/08 §0 에만 있었다. 소유 판단의 기준이고, 실제로 인라인 분류를 `voc` 모듈 아래 묶은 사고의 원인이다 | [cs wiki 첫 화면](../../../final_project_cs/wiki/index.md) |
| **Team 선언 검증 규칙 넷**이 없었다. 옮기면서 코드로 확인하니 **걸리는 시점이 다르다** — 셋은 기동 때, capability 겹침은 **요청이 올 때** | [team-registry.md](../../../final_project_cs/wiki/teams/team-registry.md) |
| **SQL 쪽 낙관적 동시성을 지키는 테스트가 없다** — 파이썬 검사가 먼저 걸려서 `AND version = ...` 을 지워도 테스트가 다 통과한다 | [blind-spots.md](../../../final_project_cs/wiki/quality/blind-spots.md) |

### 거짓 신호의 새 원인 — 도메인 교체

`[실측]` `handoff/04` 가 `return.accept`·`return_exchange.py` 를 적어 뒀는데 wiki 에
없다고 떴다. **옮겨야 할 것이 아니라 없어진 이름이다** — 지금은 `return_refund.py` 이고
capability 는 `return.check_eligibility`·`return.request`·`refund.calculate` 다.
2026-08-17 도메인 교체 전 문서를 대조하면 이런 신호가 계속 나온다.

`handoff/06` §5 의 "MCP 에 `mcp:read` 외 어떤 scope 도 부여하지 않는다" 도 같다 —
v7·v8 이 **쓰기 3단계**로 바꾼 것을 wiki 가 이미 담고 있다. 옛 규칙이 더 엄한 경우라
"없다" 가 아니라 "바뀌었다" 로 읽어야 한다.

### 분류가 틀린 것도 있었다

일일·주말·밤샘 작업 로그(`_일일작업_*` 등)가 `대조필요` 로 잡혀 있는데, 빠진 것으로
뜬 신호가 **토큰 수와 서술문**이다. 이건 옮길 지식이 아니라 그날의 기록이라
`제외` 가 맞다. 다음에 판정표를 손볼 때 함께 고친다.

## 관계

- [coverage.md](coverage.md) — 1~5차와 대조 방법
- [index.md](index.md) — 이관 범위
- [../review-policy.md](../review-policy.md) — 다른 구현체와 대조하면 결함이 찾아진다
