---
type: guide
title: 날짜별 RAG·소형 모델 연구 기록
description: 지속 절차의 wiki 정본과 날짜별 원본 근거를 연결한다
status: draft
domain: travel
---

# 날짜별 RAG·소형 모델 연구 기록

지속 절차는 [연구 개요](../../../wiki/research/rag-slm-improvements.md), [모델 평가 기준](../../../final_project_cs/wiki/quality/slm-model-evaluation.md), [GPU 작업 운영법](../../../final_project_cs/wiki/operations/gpu-work-queue.md)을 먼저 읽는다. 이 폴더는 날짜별 조사와 실행 상태를 보관한다.

| 기록 | 역할 |
|---|---|
| [2026-10-11.md](2026-10-11.md) · [실행 상태](2026-10-11.json) · [Oracle ARM 연결·대화 오류](oracle_llm_incident_2026-10-11.json) | 유지보수와 일일 연구 완료를 구분하며, HTTP 통과와 실제 답변 성공의 오판을 추적 |
| [2026-10-10.md](2026-10-10.md) · [단계별 상태](2026-10-10.json) · [사전 고정 계약](2026-10-10_context_prereg_v1.json) | 일일 논문4개·재검토 D3/E 전체 기준 실패·신규 모델2개·GPU 후속 작업 |
| [2026-10-09.md](2026-10-09.md) · [실행 상태](2026-10-09.json) | 일일 논문·신모델 검토·검색 실측 기준 실패·GPU 보충·ARM 회수; 독립 검증 대기 |
| [2026-10-08.md](2026-10-08.md) · [실행 상태](2026-10-08.json) | 당일 조사·구현·실측과 재개 지점 |
| [신모델 후보 목록](model_release_watchlist.json) | 동일 revision 중복 방지와 준비·평가·학습 상태 |
| [ARM 최신 서빙 상태](arm_serving_2026-10-11.json) · [초기 기록](arm_serving_2026-10-08.json) | 2코어 실제 환경의 시험·자원 관측과 재개 지점 |
| [GPU 대기열 최신 관측](gpu_backlog_2026-10-11.json) · [10-08 기록](gpu_backlog_2026-10-08.json) | 새 관측과 과거 근거, 현재 상태는 실제 프로세스와 재대조 |
| [초기 GPU 운영 기록](GPU_대기열_운영_2026-10-08.md) | 대기열을 처음 구성한 시점의 근거 |
| [wiki 문서 점검](../../../final_project_cs/wiki/records/reports/2026-10-08_rag-wiki-document-audit.md) | 문서 소유·연결·검증과 보완 내역 |

새 날의 기록은 새 파일로 추가한다. 당일 실행 상태를 갱신할 때 원본을 직전에 백업한다. 실행 중 시험을 다음 날 회수하되 날짜별 완료 표시만 보고 동일 작업을 중복 시작하지 않는다.

- [예약 실행 지침 원문](scheduled_instructions_2026-10-08.json): 긴 예약 메시지를 짧게 표시하기 위해 보존한 두 작업의 지침입니다. 실제 후보·작업 상태와 수치는 기존 상태 JSON과 원본 실행 기록에서 확인합니다.

- [독립 보류 자료 준비 초안](independent_holdout_contract_2026-10-08_v1.md): 실제 자료 작성·검수 전의 검토 대기 계약입니다. [분담·검증 근거](../../../final_project_cs/wiki/records/reports/2026-10-08_174529_qat_completion_parallel_review.md).

- [6시간 정기 설명·현황](../../../final_project_cs/wiki/records/reports/2026-10-09_0800_six-hour-gpu-arm-report.md): 완료·실패·검증 대기를 구분한다. [기존 예약 변경 검증](six_hour_reporting_2026-10-09.json), 중복 예약은 만들지 않는다.

- [Saluki와 전체 A~E 실측 비교](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/reports/2026-10-09_1116_saluki-all-abcde-comparison.md): 단일·복수 역할, E유형·손실·지연·검토자·반복과 누락범위를 한 표집에 연결했습니다.

- [새 대상 선택·근거·답변 계획](selection_answer_plan_2026-10-09_v2.md) · [검토 상태](selection_answer_review_2026-10-09_v2.json): 최근 연구8개와 사람 검수 전 개발 예시를 연결합니다.
- [Saluki 전담 학습 계획](saluki_finetune_plan_2026-10-09.md) · [준비 상태](saluki_finetune_2026-10-09.json): 사용자 승인 있음, 동일 모델 학습 표현·CUDA·공간 조건 대기입니다.
- [새 통합 평가·학습 비교 리포트](../../../final_project_cs/wiki/records/reports/2026-10-09_1150_selection-answer-plan-and-training-review.md): Jev 관련5학습판 재계수와 기존 GPU 후속 작업도 연결합니다.

- [예시 독립 검토와 현재v3](../../../final_project_cs/wiki/records/reports/2026-10-09_1158_pilot-independent-review-corrections.md): ID 정답 표시를 제거했으며 고유 일정은1개, 사람/모델 검증은 대기입니다.

- [Saluki 기존 검토 자료 첫 학습판](../../../final_project_cs/wiki/records/reports/2026-10-09_1208_saluki-reviewed-set-baseline.md): 기존2,613행·추가 AI합의900행을 비율 그대로 사용합니다. 새 자료/F/최종보류 완성을 첫 학습 조건에서 빼고 제품 채택 검증과 분리했습니다. 동일 모델·CUDA·공간 조건 대기는 유지합니다.
- [14시 6시간 현황·새 완료 회수](../../../final_project_cs/wiki/records/reports/2026-10-09_1400_six-hour-gpu-arm-report.md): GPU 준비 작업 소진의 보충, FINCH 두 번째 시드 보관, 추가 역할·Valen 결과와 ARM 캐시 비교의 중간 관측입니다. 과거 08시 보고는 보존합니다.

- [20시 6시간 현황·캐시 교대 결과](../../../final_project_cs/wiki/records/reports/2026-10-09_2000_six-hour-gpu-arm-report.md): 추가 평가·학습판 회수와 GPU 작업 소진 보충, ARM 같은 문맥 재사용의 개발 진단 통과 및 독립 검증 대기를 연결합니다.

- [Oracle ARM 메모리·디스크와 요청 지연 구분](../../../final_project_cs/wiki/records/reports/2026-10-09_2244_arm-runtime-memory-disk.md): 실제 실행 도구·자원 실사용과 모델 적재/문맥 처리/캐시 재사용을 분리해 확인했습니다.

- [Oracle ARM develop Docker 준비 상태](arm_develop_cd_2026-10-09.json) · [배포·승인 대기 근거](../../../final_project_cs/wiki/records/reports/2026-10-09_arm-docker-develop-cd.md): 모델 시험과 앱 배포 완료를 구분한다.

- [Oracle ARM 자체 6시간 공급](arm_serving_queue_2026-10-10.json) · [설치와 실제 대기 조건](../../../final_project_cs/wiki/records/reports/2026-10-10_0115_arm-server-local-six-hour-queue.md): PC 예약에 의존하지 않는 기계 내부 관리입니다.

- [승인된 Oracle ARM 자료 전송·앱 배포](../../../final_project_cs/wiki/records/reports/2026-10-10_0130_arm-approved-mobility-transfer-and-deployment.md) · [배포 상태](arm_develop_cd_2026-10-10.json): 이전 승인 대기 기록은 보존하며 현재 재개 지점은 이 기록을 따릅니다.

- [2026-10-10 02시 정기 보고](../../../final_project_cs/wiki/records/reports/2026-10-10_0200_six-hour-gpu-arm-report.md) · [해당 GPU 관측](gpu_backlog_2026-10-10.json): 새 완료 회수와 Oracle ARM 기동/질의 실패를 구분합니다.

- [2026-10-10 08시 정기 보고](../../../final_project_cs/wiki/records/reports/2026-10-10_0800_six-hour-gpu-arm-report.md) · [실측과 재개 지점](six_hour_report_2026-10-10_0800.json): GPU 소진 후 누락 역할 보충, E 반복 결과와 Oracle ARM 실제 지연을 구분합니다.

- [14시 6시간 현황](../../../final_project_cs/wiki/records/reports/2026-10-10_1400_six-hour-gpu-arm-report.md) · [구조화 상태](six_hour_report_2026-10-10_1400.json): 재검토 완료 실패, 후보 표시 순서 진단, 누락 HF 비교, Oracle ARM 준비 시간 계산 수정과 실패 보존입니다.

- [20시 6시간 현황](../../../final_project_cs/wiki/records/reports/2026-10-10_2000_six-hour-gpu-arm-report.md) · [상태](six_hour_report_2026-10-10_2000.json) · [추가 순서 진단 계약](2026-10-10_candidate_order_extension_v1.json): 같은 문항 순서 취약점, HF 후속 비교, ARM 자체 공급과 로컬 보관 공간 제한을 연결합니다.

- [2026-10-11 일일 기록](2026-10-11.md) · [02시 정기 보고](../../../final_project_cs/wiki/records/reports/2026-10-11_0200_six-hour-gpu-arm-report.md) · [상태](six_hour_report_2026-10-11_0200.json) · [표현 방식 진단 계약](2026-10-11_candidate_order_representation_prereg_v1.json): 완료 회수·GPU 보충과 사람/독립 검증 대기를 구분합니다.

- [2026-10-11 08시 정기 보고](../../../final_project_cs/wiki/records/reports/2026-10-11_0800_six-hour-gpu-arm-report.md) · [상태](six_hour_report_2026-10-11_0800.json) · [앱 출력 계약 진단](2026-10-11_app_schema_diagnostic_prereg_v1.json) · [QAT 진단 추가](2026-10-11_app_schema_diagnostic_prereg_v2_qat.json) · [6시간 안정성 시험](2026-10-11_app_schema_soak_prereg_v2.json): 완료 표식의 미실행 누락과 실제 답변 실패를 분리하고 기존 실행기에 다음 일을 보충했습니다.

- [2026-10-11 일일 논문·응답 완성 검증](../../../final_project_cs/wiki/records/reports/2026-10-11_1030_daily-response-completion-research.md): [선정 논문5개 적용 조건](2026-10-11_sources_and_review_v1.json), [연결기 고정 조건](2026-10-11_response_guard_prereg_v1.json), [원본800토큰 안정성 조건](2026-10-11_app_schema_soak_originals_prereg_v3.json). 로컬 구현·기존 답안 재생과 독립 검증·운영 반영을 구분합니다. 최신 자원 관측은 [GPU](gpu_backlog_2026-10-11.json)·[Oracle ARM](arm_serving_2026-10-11.json)입니다.

- [2026-10-11 14시 정기 보고](../../../final_project_cs/wiki/records/reports/2026-10-11_1400_six-hour-gpu-arm-report.md) · [상태](six_hour_report_2026-10-11_1400.json) · [HF 완전한 답변 진단](2026-10-11_hf_app_completion_prereg_v1.json) · [백업 목록](six_hour_report_2026-10-11_1400_backups.json): 완료 E 대비, 일반 생성 형식 실패, 순차 후속 작업과 Oracle 앱 차단을 구분합니다.

- [Oracle ARM 답변 복구](../../../final_project_cs/wiki/records/reports/2026-10-11_oracle_answer_repair.md) · [복구 실행 상태](oracle_answer_repair_2026-10-11_v1.json): 기본 답변 복구와 반복 계정 수정의 적용·실측을 기록하며 대화 중복·추천 전체·독립 검증을 일일 연구 완료와 구분한다.

- [2026-10-11 22시 정기 보고](../../../final_project_cs/wiki/records/reports/2026-10-11_2240_six-hour-gpu-arm-report.md) · [상태](six_hour_report_2026-10-11_2240.json) · [백업](six_hour_report_2026-10-11_2240_backups.json): 완료 회수·안정성·미측정 비교와 Oracle 답변 복구 뒤 한계를 구분합니다.


- [오후 일정 변경 조건 질문 보완](../../../final_project_cs/wiki/records/reports/2026-10-11_2320_afternoon-scope-query.md) · [실행 상태](scoped_query_repair_2026-10-11_v1.json): 실제 오해·시간 초과, 로컬 조회 구현과 실제 모델 미달·미배포 상태를 구분합니다.


- [2026-10-12 Oracle ARM 질문·지연 원인과 최소 수정](../../../final_project_cs/wiki/records/reports/2026-10-12_0038_arm-latency-root-cause.md) · [구조화 실행 상태](arm_response_root_cause_2026-10-12_v1.json): 실제 원본 모델·조회 계약, 축약 실험 실패, CPU 조정과 실제 HTTP 반영 상태입니다. 일일 논문 조사 완료와 구분합니다.

- [2026-10-12 운영 보완](2026-10-12.md) · [검색·모델 상태](arm_search_model_repair_2026-10-12_v1.json) · [실측 보고](../../../final_project_cs/wiki/records/reports/2026-10-12_0454_arm-search-model-repair.md): 식사 오연결·검색 적재·실제 질의와 지연·검증 대기를 구분합니다.

- [A4000 단일 GPU 통합 상태](gpu_consolidation_2026-10-12.json) · [누락 QAT 비교 고정 조건](2026-10-12_single_gpu_missing_qat_prereg_v1.json) · [실측·ADA Pod 정지 차단](../../../final_project_cs/wiki/records/reports/2026-10-12_a4000-consolidation-and-ada-stop-blocker.md): 이전·현재 계산과 실제 Pod stop 미완료를 구분합니다.

- [2026-10-12 하루 요약 지연 수정](../../../final_project_cs/wiki/records/reports/2026-10-12_day-summary-timeout-repair.md): 같은 시험 여행의 수정 전후 응답, 실제 반영과 자유 질의·GPU 정지의 남은 범위를 구분합니다.


- [현재 결정 구성의 고정 1,448문장 회귀](../../../final_project_cs/wiki/records/reports/2026-10-12_fixed1448-current-decision-preregistration.md) · [입력·모델·엔진·코드 해시](2026-10-12_current_product_frozen1448_prereg_v1.json): 같은 원문으로 현재 결정만 재측정하며 규정 검색·제품 끝단 검증과 구분합니다.

- [2026-10-12 13시 GPU 통합·ADA 정지 완료](../../../final_project_cs/wiki/records/reports/2026-10-12_1302_a4000-consolidation-ada-stop-completed.md) — 원본 보존·실제 정지·A4000 후속 작업 관측.

- [E2 복수 일정 CRUD 초안 제작·검증](../../../final_project_cs/wiki/records/reports/2026-10-12_e2-crud-pilot-and-real-dialogue.md) · [평가 계약](../../../final_project_cs/wiki/quality/itinerary-crud-e2-evaluation.md): 기존 E 보존, 실제 대화 재구성과 사람 검수·실측 대기를 구분합니다.

- [E2 정답 검토·A4000 비교 등록](../../../final_project_cs/wiki/records/reports/2026-10-12_e2-gold-review-and-a4000-registration.md) · [사전 조건](2026-10-12_e2_reviewed_request_plan_prereg_v1.json) · [Saluki 동일 가중치 학습 재점검](../../../final_project_cs/wiki/records/reports/2026-10-12_saluki-training-runtime-recheck.md).


`[등록·검증 대기 2026-10-12]` Winnow를 우선 후보로 보강 학습하고 Saluki는 원본 보존 학습 경로를 추가했습니다. 학습·정확도·전체 앱 로직 완료와 구분하며 기존 A4000 실행 뒤 단일 큐로 이어갑니다. [2026-10-12 모델 작업큐 Claude 인계](2026-10-12_model_queue_claude_handoff.md)。
