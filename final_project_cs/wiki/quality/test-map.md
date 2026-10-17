---
type: guide
title: 현재 여행 시험 지도
description: 불변식·계약과 그것을 지키는 시험의 연결 지도
status: draft
domain: travel
---

# 현재 여행 시험 지도

| 검증할 내용 | 실제 시험 경로 |
|---|---|
| Core 의존 경계·현재 정책 주입 | [구조 시험](../../tests/architecture/) |
| 입력·출력·도구·비활성 계약 | [계약 시험](../../tests/contract/) |
| 인증·scope·고객 격리·마스킹 | [보안 시험](../../tests/security/) |
| SQL 입력·신규 DB·재실행 | [입력 계획 시험](../../tests/unit/core/test_current_migration_plan.py)·[DB 통합](../../tests/integration/db/test_migrations_rerun.py) |
| 과거 결함 보고서의 현재 확인 상태 | [상태 검사](../../tests/unit/core/test_debug_report_status.py)·[현황 주석 규칙](debug-report-status.md). 제품 해결 판정과 구분 |
| 현재 여행 MCP·본인 여행·쓰기 등록 | [MCP 프로토콜](../../tests/e2e/test_mcp_server.py)·[읽기 도구](../../tests/e2e/test_mcp_read_tools.py) |
| 여행 분류 자료·재생 분모 | [현재 여행 평가 시험](../../tests/unit/eval/test_travel_classification_eval.py) |
| 여행 RAG 검색·과거 scope 차단 | [검색 통합](../../tests/integration/rag/test_travel_corpus_retrieval.py) |
| 활동 후보 세 단(같은 종류·비슷한 경험·취향)·호텔 후보·모델 이유 문장 검사·임베딩 순서·분류 채우기 | [세 단·취향](../../tests/e2e/test_intake_experience_tiers.py)·[같은 종류](../../tests/e2e/test_intake_similar_places.py)·[호텔·종류](../../tests/e2e/test_intake_candidate_kinds.py)·[이유 문장](../../tests/e2e/test_candidate_reasons.py)·[임베딩·분류 채우기](../../tests/e2e/test_place_embeddings.py). 모델·임베딩은 mock 서버(고정 답 대역)로 시험하며 실모델 확인은 별도 |
| 약관 보관 기간·회원 정리·처리 기록 파기 | [보관 기간](../../tests/e2e/test_legal_retention.py)·[삭제·게스트 정리](../../tests/e2e/test_guest_and_trip_delete.py)·[동의 기록](../../tests/e2e/test_consents.py) |

불변식 정의와 함수 연결은 [카탈로그](invariants.md)가 소유합니다. 시험 개수·과거 통과 수를 이 페이지에서 중복 관리하지 않습니다. live·DB·외부 서비스 의존 여부와 실패·건너뜀을 실제 실행 결과에 기록합니다. 사용 종료된 MCP·평가 시험은 legacy로 분리합니다.

## 공통·여행 시험을 따로 실행하기

[사용자 결정 2026-10-11] W13 C안을 반영했습니다. 공통 계약을 여행 사례로 검사하는 A와 시험 묶음을 분리하는 C는 함께 할 수 있습니다. 둘을 대안으로 제시한 설명을 정정합니다.

분류의 정본은 [시험 파일 목록](../../tests/test-suites.json)입니다. `common`은 공통 엔진·상태·계약·DB 접근·모델 처리 기반, `travel`은 여행 업무·고객 웹·API·모델 평가·제품 통합을 검사합니다. 기존 공유 설정은 유지합니다. 새 파일이 미분류이거나 양쪽에 중복되면 [분리 실행기](../../scripts/run_test_suite.py)가 중단합니다. 다른 묶음의 시험 파일은 import 전에 수집에서 제외합니다.

cs 프로젝트 폴더에서 실행합니다. `--collect-only`는 수집만 합니다. 기존 기본 조건인 `not live`를 유지하며, 실제 LLM 호출 시험은 별도 명시 실행입니다.

```powershell
python scripts/run_test_suite.py --suite common -q
python scripts/run_test_suite.py --suite travel -q
```

분리 실행 지원과 전체 시험 통과는 다릅니다. [실제 수집·실행 결과](../../../program/research/sql_review_2026-10-11/index.html#W13)를 확인합니다. 공통 묶음이 별도 제품처럼 여행 패키지 없이 설치된다는 뜻은 아닙니다. 새 시험의 검사 목적이 바뀌면 목록의 분류도 검토합니다.

## 과거 기록

[수정 전 문서](../records/commerce_2026-10-11/wiki--quality--test-map.md)는 당시 기록입니다. 현재 여행 제품의 사양·평가·시연·완료 증거로 사용하지 않습니다. 원문 바이트는 같은 폴더의 백업에도 보존했습니다.

## 관계

- [여행 사양 허브](../../../wiki/index.md) — 현재 정본을 찾는 입구


## 이전 절 링크

<a id="테스트-지도"></a>
<a id="전체-구조"></a>
<a id="무엇을-어디서-검사하는가"></a>
<a id="불변식과의-연결"></a>
<a id="코드-쪽-역방향-표식--완료"></a>
<a id="invariant-inv-cs-rt-009"></a>
<a id="테스트가-없는-곳"></a>
<a id="관계"></a>
