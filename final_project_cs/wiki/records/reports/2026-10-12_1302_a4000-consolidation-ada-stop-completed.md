---
type: report
title: A4000 작업 통합과 ADA2000 Pod 정지 완료
description: 승인된 원본 보존 후 Pod stop 응답과 실제 접근 종료를 대조한 후속 기록
status: draft
domain: travel
---

# A4000 작업 통합과 ADA2000 Pod 정지 완료

기존 작업과 Valen 원본을 보존한 뒤 ADA2000 Pod를 정지했습니다. A4000의 기존 계산은 그대로 유지하고 누락 비교와 고정 제품 결정 회귀를 후속 대기열에 연결했습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 기존 종료 평가 이력 | 보존 | 196/196 = 100% |
| A4000 이전 파일 | SHA 검증 | 1,397/1,397 = 100% |
| Valen 비공개 원본 보존 | SHA 검증 | 54/54 = 100% |
| ADA2000 Pod stop | 응답·접근 종료 확인 | 1/1 = 100% |
| ADA 새 작업 금지 | 재검증 | 5/5 = 100% |
| 새 고정 결정 회귀 | 등록·선행 대기 | 0/1,448 = 0% 실측 |

## 실제 정지와 보존

[실측] 2026-10-12 12:57:20 KST에 Valen 원본·토크나이저·설정 54개를 기존 Oracle ARM 비공개 보관소로 직접 스트리밍했고 모든 파일의 SHA-256·크기를 대조했습니다. tar는 3,437,455,360바이트, 모델 가중치 SHA-256은 `465714dd28702c4232d9233c2a2157d366967c541b2a27d9dadccc816304fd48`, tar SHA-256은 `b602e2063a4ae43731ebfee98c37ddb5e9e0230f9a7c105deef50a39ec661bdd`입니다. 완료 후 여유는 23,436,042,240바이트였습니다. 모델을 기동하지 않고 CPU nice 19·idle IO·폴더0700/파일0600으로 보관했습니다. 로컬과 A4000에는 대용량 사본을 쓰지 않았습니다.

[실측] 13:00:31 KST에 정확한 RTX 2000 Ada 기계, 기존196개 종료 상태, 유휴 실행기 종료, GPU 메모리100MiB 미만을 확인한 뒤 공식 GraphQL `podStop`을 Authorization 헤더 인증으로 한 번 요청했습니다. 반환 Pod id가 대상과 같고 `desiredStatus=EXITED`, 오류0개였습니다. 13:01:36 KST에 실제 SSH 연결도 `connection_refused`로 종료 상태와 일치했습니다. terminate·볼륨 삭제는 실행하지 않았습니다. 청구 명세 자체는 조회하지 않았습니다.

[앞선 차단 기록](2026-10-12_a4000-consolidation-and-ada-stop-blocker.md)은 당시 상태 그대로 보존합니다. Oracle ARM 전송에 대한 자동심사 거절 뒤 사용자가 목적지와 원본 전송을 직접 승인해 보존을 진행했습니다. URL에 관리 키를 싣는 거절 방식은 반복하거나 우회하지 않았으며 안전한 헤더 방식의 stop 요청이 성공했습니다. 이전 조회 인증 실패를 모든 관리 동작이 불가능하다는 결론으로 일반화하지 않습니다.

## A4000 현재 실행과 후속 평가

[실측] 13:01:40 KST에 기존 HF 작업은2/4 완료, FINCH seed20261013 실행, cosine seed20261013 대기였습니다. 기존 worker와 후속 dispatcher가 살아 있고 GPU 메모리는10,469MiB, 순간 이용률은25%, 디스크 여유는3,772,653,568바이트였습니다. 이 순간 표본을 지속 이용률로 쓰지 않습니다. 선행 작업 종료와 프로세스 종료 뒤에만 후속4개가 한 번씩 실행됩니다.

우리 자료로 학습한 cosine seed20261014·oos2r·oos3의 누락 QAT 표현 비교 각48문항과 개발사 Gemma E4B QAT Q4_0 원본(우리 어댑터 없음)의 현재 제품 결정 회귀1,448문항을 등록했습니다. [고정 회귀의 입력·코드·프롬프트·엔진 해시와 범위](2026-10-12_fixed1448-current-decision-preregistration.md)를 따릅니다. 현재 새 실측은0/1,592이며 실패·미완료를 분모에서 빼지 않습니다. 과거196개는 재실행하지 않습니다.

현재 결정 회귀는 일상·구어체1,300문장과 규정148문장의 분류·대상 지목을 평가하며 규정 검색·최종 답변·일정 실행·웹 사용 흐름까지 포함하지 않습니다. 과거 gemma4:12b와 모델·코드가 달라 결과 차이를 파인튜닝 효과 하나로 단정할 수 없습니다. 반복 안정성 문항을 독립 정확도에 합치지 않습니다. E 사람 검수·독립 보류 검증·제품 채택은 별도 미완료입니다.

## 근거와 다음 회수

- [Valen 보존·해시](../../../../program/scripts/plan_qa_bench/results/gpu_consolidation_20261012/valen_oracle_archive_verification.json)
- [Pod stop 원본 응답](../../../../program/scripts/plan_qa_bench/results/gpu_consolidation_20261012/ada_stop_header_mutation_20261012.json)
- [정지 후 ADA 접근·A4000 실제 상태](../../../../program/scripts/plan_qa_bench/results/gpu_consolidation_20261012/post_stop_runtime.json)
- [공급 차단5/5 재검증](../../../../program/scripts/plan_qa_bench/results/gpu_consolidation_20261012/policy_guard_reverification.json)
- [현재 구조화 운영 상태](../../../../program/research/daily_rag_slm/gpu_consolidation_2026-10-12.json)

개인 설정·공유 rag/rag-strata 지침·기존 feeder에서 ADA 재보충 금지가 유지됩니다. 새 예약을 중복 생성하지 않았습니다. 기존 산출물 변경 전 각 폴더의 `_backup/2026-10-12_130319_ada_stop_completed/`에 복사했습니다. [운영 본문 백업](../../operations/_backup/2026-10-12_130319_ada_stop_completed/) · [상태·날짜 색인 백업](../../../../program/research/daily_rag_slm/_backup/2026-10-12_130319_ada_stop_completed/) · [log 백업](../../_backup/2026-10-12_130319_ada_stop_completed/).

다음에는 A4000 선행 완료 결과와 새 비교를 회수해 같은 세트의 분자·전체 분모로 비교합니다. 디스크3GiB 미만, 원인 미수정 실패, 중복 작업은 새 실행으로 넘기지 않습니다.
