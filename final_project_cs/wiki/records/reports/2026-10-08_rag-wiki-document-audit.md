# RAG·모델 비교 문서 관리 점검 — 2026-10-08

최근 연구 문서는 있었지만 wiki의 정본·색인·작업 리포트 연결은 누락됐다. 지속 절차와 날짜별 상태를 분리하고 기존 진입 경로를 보존했다.

## 범위와 근거

최근 RAG 작업의 산문 문서 3개(일일 연구, 초기 GPU 운영 기록, 신모델 평가 절차)를 중앙 wiki의 구조·문서 표준·작업 루프 및 cs 프로젝트 RULE과 대조했다. 다른 과거 연구 전체나 sample·datasets·dojo wiki 전체의 정합성 완료를 뜻하지 않는다.

수정 전 live wiki와 연구 색인에서 해당 세 문서의 진입 링크를 찾지 못했다. 전체 과거 기록의 모든 연결이 없다고 주장하지 않는다. 날짜별 연구·운영 기록은 보존하고 지속 평가 절차만 정본 안내로 교체했다.

## 정본과 변경

| 소유 | 문서 |
|---|---|
| 중앙 연구 wiki | [검색·소형 모델 연구 개요](../../../../wiki/research/rag-slm-improvements.md) |
| cs 평가 wiki | [원본 비교·추가 학습 기준](../../quality/slm-model-evaluation.md) |
| cs 운영 wiki | [GPU 작업 대기열 운영법](../../operations/gpu-work-queue.md) |
| 날짜별 조사·실행 근거 | [연구 기록 색인](../../../../program/research/daily_rag_slm/index.md) |

각 영역 index를 먼저 등록하고 본문을 작성했다. 중앙 연구 색인·cs 평가/운영 색인·연구 폴더 색인·평가 실행 문서·각 wiki log를 연결했다. 후보 준비 상태를 절차 정본에 중복해서 쓰던 부분은 후보 JSON을 참조하도록 바꿨다. 과거 연구 기록과 실제 GPU 실행은 변경하지 않았다.

## 검증

검증 출력과 예약 작업 반영은 아래 후속 검증 절에 기록한다. 문서 링크 검사는 모델 성능 시험이나 실서비스 반영의 증거가 아니다.

## 수정 직전 백업

- [wiki/research/_backup/2026-10-08_1014_rag_wiki_links/index.md](../../../../wiki/research/_backup/2026-10-08_1014_rag_wiki_links/index.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_1014_rag_wiki_links/index.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_1014_rag_wiki_links/index.md)
- [final_project_cs/wiki/operations/_backup/2026-10-08_1014_rag_wiki_links/index.md](../../../../final_project_cs/wiki/operations/_backup/2026-10-08_1014_rag_wiki_links/index.md)
- [program/research/daily_rag_slm/_backup/2026-10-08_1014_rag_wiki_links/신모델_원본비교와_추가학습_절차.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_1014_rag_wiki_links/신모델_원본비교와_추가학습_절차.md)
- [program/research/_backup/2026-10-08_1014_rag_wiki_links/index.md](../../../../program/research/_backup/2026-10-08_1014_rag_wiki_links/index.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_1014_rag_wiki_links/eval-harness.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_1014_rag_wiki_links/eval-harness.md)
- [wiki/_backup/2026-10-08_1014_rag_wiki_links/log.md](../../../../wiki/_backup/2026-10-08_1014_rag_wiki_links/log.md)
- [final_project_cs/wiki/_backup/2026-10-08_1014_rag_wiki_links/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_1014_rag_wiki_links/log.md)

## 후속 검증과 예약 작업 반영

일일 연구와 GPU 대기열 확인의 두 예약 작업에 wiki 정본 우선·영역 색인 등록·작업 리포트·본문 및 log 연결 의무를 추가했다. 기존 프롬프트, 실행 주기, 활성 상태, 대상 대화, 알림 정책을 보존했는지 원본과 재대조해 2/2 통과했다. [예약 원본 백업](../../../../program/scripts/plan_qa_bench/results/rag_wiki_audit_20261008/automation_backups/) · [검증 출력](../../../../program/scripts/plan_qa_bench/results/rag_wiki_audit_20261008/automation_validation.json).

기존 wiki 검사기를 수정 전 내용을 읽게 한 검사와 수정 후 검사에 똑같이 적용했다. 이번 백업 사본은 문서 위치에 따라 깨진 상대 링크로 오탐될 수 있어 두 검사에서만 제외했다. 수정 전후 기존 지적은 각각 271건이며 새 문제는 추가하지 않았다. 전체 wiki 통과를 뜻하지 않는다. 기존 장문 로그의 줄 수 변화는 같은 지적으로 대조했다.

변경한 13개 문서의 파일 링크, 새 정본 3개 색인 등록, 수정 전 원본 8개 보관 여부를 검사했다. 정확한 최종 분자/분모와 전체 지적은 [검증 JSON](../../../../program/scripts/plan_qa_bench/results/rag_wiki_audit_20261008/validation.json) · [수정 전 출력](../../../../program/scripts/plan_qa_bench/results/rag_wiki_audit_20261008/before.txt) · [수정 후 출력](../../../../program/scripts/plan_qa_bench/results/rag_wiki_audit_20261008/after.txt)에서 확인한다.

후속 문서 조정 전 판도 보존했다: [연구 정본](../../../../wiki/research/_backup/2026-10-08_1017_rag_wiki_final/) · [cs 변경 이력](../../_backup/2026-10-08_1020_rag_wiki_log_order/) · [점검 리포트](../../records/reports/_backup/2026-10-08_1020_rag_wiki_report_completion/) · [검증 도구](../../../../program/scripts/_backup/2026-10-08_1020_rag_wiki_validation/) · [중간 검증 출력](../../../../program/scripts/plan_qa_bench/results/rag_wiki_audit_20261008/_backup/2026-10-08_1020_before_final_validation/).

기존 모델 학습·평가 프로세스와 데이터는 변경하지 않았다. 실서비스 배포·커밋·푸시는 수행하지 않았다. sample·datasets·dojo를 포함한 전체 과거 wiki 지적 해결은 이번 범위 밖이며 별도 점검이 필요하다.
