---
type: report
title: 로컬 391개 수정 읽기 전용 재분류와 고객 운영시간 구현 출처
description: 최신 팀 기준 대조, 줄바꿈 분리, 다음 격리 통합 범위 인계
status: draft
domain: travel
---

# 결론

[실측] 2026-10-24 08:44:59 UTC 팀 develop fetch 종료 0. 기준 `325ba25d88c91ce97da61f2bda635e5888fe3b40`와 같고 새 차분은 없습니다. 자동 병합하지 않았습니다.

## 확인한 범위

- 추적 수정 **391/391 = 100%**를 HEAD·로컬 바이트·지정 팀 blob과 대조했습니다. **줄바꿈만 16개, 본문 차이 375개**입니다. 본문 차이에는 문서/이름 변경도 들어가므로 기능 변경 수가 아닙니다.
- 파일별 최종 분류: **보존16 · 이미포함241 · 실제필요2 · 충돌116 · 미확인16**. 모든 원본은 분류와 무관하게 보존합니다. 충돌은 양쪽 본문 변경의 정적 위험이며 실행된 merge conflict가 아닙니다.
- 기존 후보 **1495/1495행 = 100%** 최신 blob 재확인, 불일치0. 고유1286경로이며 여러 delivery의 중복 행을 보존했습니다. 분류는 이미포함332 · 실제필요2 · 충돌4 · 미확인1157입니다. 후속 구현으로 대체된 후보는 이미포함에 들어가되 JSON에서 구분합니다. **1157행 전수 의미검토 완료가 아닙니다.**
- HEAD·index·추적 status·skip-worktree flags·391개 파일 바이트의 감사 전후 동일성을 확인했습니다. 허용 fetch 메타데이터와 이 새 보고서 외 원본 코드/기존 문서/색인을 변경하지 않았습니다. 환경파일·자격증명 본문은 출력하거나 보고서에 넣지 않았습니다.

## 다음 안전한 통합: 고객이 알려 준 운영시간

[실측] [10-13 사용자 결정과 구현 기록](../../../final_project_cs/wiki/records/reports/2026-10-13_고객_운영시간_직접입력.md)의 원본 구현을 찾았습니다. [10-19 parity의 출처 미확인 항목](2026-10-19_oracle-aws-parity.md)은 이 로컬 구현과 연결됩니다. 팀 기준의 정확한 blob을 확인한 26개 후보 경로에서 핵심 고객시간 표식은 없고, 로컬20개 경로에는 있습니다. 관련 단위/e2e/감시/웹 시험4개는 로컬에 있으나 팀 tree에는 없습니다. 키워드만으로 기능 전체를 판정하지 않고 현재 입력·타입·호출 경로와 원래 사용자 결정도 대조했습니다.

부모의 **독립 격리 통합본**에서 다음 범위로 선별 구현합니다. 기존 파일 전체 복사는 금지합니다.

1. 계약 `web-intakes.md`와 backend `intake/{pipeline,hours,review,assemble,direct_schedule}.py`, `itinerary/itinerary_checks.py`: 입력 검증, 공식 출처 우선, 장소 변경 시 제거, 등록 항목 `detail.customer_hours` 저장. 공용 장소/타 고객 자료에는 쓰지 않습니다.
2. 웹 `lib/live/{intake-review,intake-events,intake}.ts`, `features/plan-check/{model,result-parts,plan-rows,plan-check,parts}` 및 CSS, `features/intake-review/model.ts`와 회귀: 입력·저장·다시 열기·지우기·출처/미확인 안내를 한 계약으로 연결합니다. 현재 `model.ts`/시험만 수입하면 빠진 `HoursDraft`·서버 계약 때문에 완성이 아닙니다.
3. `itinerary.py`의 항목 조회/교체, `watch/dawn_check.py`, `conversation/trip_facts.py`, `places/place_info.py`: 알려 준 값의 항목별 보기, Google 등 공식 출처 우선, 다른 장소로 교체 시 제거, 출처 표시를 연결합니다.
4. 회귀: 공식값 우선, `24:00`, 역전 시간/중복요일/전일휴무 거부, 장소 교체 제거, tenant 격리, 등록 왕복, Google 모름 대체, 출처 표시. 최신 add-search·check:false·캐시·재사용·날짜 deferred 계약은 보존합니다.

[미확보] 이 감사는 **정적 누락과 출처 확인**이며 새 기능 시험은 실행하지 않았습니다. 과거 보고서의 시험 수치를 현재 통과로 사용하지 않습니다. 공유 intake 파일은 단일 통합 담당이 소유하고, 격리판 실패 회귀→최소 구현→독립 검토로 이어가야 합니다.

## 보류·이미 끝난 범위

- 날짜 위험은 `date_risk_delivery_01` / `date_risk_independent_review_01/verdict.json`의 기존 독립검증 완료 결과를 연결합니다. 재구현하지 않았으며 팀 포함 여부와 격리 delivery 완료를 구분합니다.
- ARM remote chat의 `ollama_adapter.py`/`test_adapter.py` 로컬 독자 차분은 미확인입니다. 로컬 health 경로가 원격 실패 때 로컬 모델로 통과시키므로 정책 검토 없이 수입하지 않습니다. 원격 서비스는 호출하지 않았습니다.
- launch·tsconfig·평가·과거 문서 변경은 기능 누락으로 자동 승격하지 않습니다.
- `safe_git.py`의 `rev-parse --git-dir` exit2는 옵션 필터 거부였습니다. stderr를 확인하고 허용 조회 옵션 `--absolute-git-dir`로 해결했습니다. 원본 wrapper·전역 Git 설정을 고치지 않았습니다.

## 관계·전체 파일별 산출물

프로필 scratch: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/local391_audit_01/`

- `REPORT.md` · `tracked391_classified.json`: 391개 파일별 분류·근거·지문·hunk 범위·Python AST 증거
- `tracked391.json`: 최초 기계 비교, 의미 검토로 승격하기 전 판정
- `CANDIDATES.md` · `candidate_paths.json` · `candidate_rows.json`: 후보 파일별 목록과 delivery별 원근거
- `customer_hours_scope.json`: 26개 구현/회귀 후보 경로, 원본 지문, 팀 blob, 핵심 함수/필드 위치
- `fetch.json` · `team_new_delta.json` · `source_fingerprints_before.json` · `verification.json`: 기준과 보존 증거

기존 wiki index·계약·과거 보고서는 사용자 지시에 따라 수정하지 않았습니다. 새 인계 보고서만 추가했습니다. 통합·신규 시험·서비스·운영 DB·배포·push는 실행하지 않았습니다.
