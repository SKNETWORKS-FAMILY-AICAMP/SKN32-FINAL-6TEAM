---
type: report
title: Saluki 27B 파인튜닝 사전 확인과 실행 조건 검사 구현
description: 공식 고정 판·기존 GPU·자료 중복을 대조하고 파인튜닝 재개 조건을 기록한 실행 근거
status: draft
domain: travel
tags: [finetuning, evaluation, gpu]
---

# Saluki 27B 파인튜닝 사전 확인과 실행 조건 검사 구현

살루키의 잡담 오지목을 줄이되 정상 요청 인식을 유지하는 학습 계획을 작성하고, 잘못된 모델·공간·잠금 조건에서는 시작하지 않는 검사기를 구현했습니다. 동일 모델의 학습 표현과 자원 조건이 아직 검증되지 않아 학습 연결 검사와 본 학습은 실행하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 공식 배포 파일 확인 | 완료 | 4/4 = 100% |
| GPU 자원 읽기 확인 | 완료 | 2/2 = 100% |
| 학습 정답 계약 | 통과 | 1,713/1,713 = 100% |
| 본 학습 시작 조건 | 미충족 | 3/10 = 30% |
| GPU 연결·본 학습 | 조건 대기 | 0/2 = 0% |

조사·레시피·준비 상태의 단일 출처는 [Saluki 학습 계획](../../../../program/research/daily_rag_slm/saluki_finetune_plan_2026-10-09.md)과 [전용 상태 JSON](../../../../program/research/daily_rag_slm/saluki_finetune_2026-10-09.json)입니다. 연구 색인과 운영 정본에는 이 리포트 링크와 결론만 연결합니다.

## 실측·실패 기록

- [실측] [원본 사전 확인](../../../../program/scripts/plan_qa_bench/results/saluki_finetune_preflight_20261009_113242/summary.json): 공식 모델 4종과 GPU 서버 A/B 읽기 확인. 시각 2026-10-09 11:32:46~47 KST. 무게 파일 다운로드·작업 중단·모델 삭제 없음.
- [실측] [학습 환경 확인](../../../../program/scripts/plan_qa_bench/results/saluki_finetune_preflight_20261009_113242/B_runtime.json): 설치된 GGUF 로더의 qwen35·학습 지원 미확보. 최신 문서의 가능성과 현재 설치판을 구분했습니다.
- [실측] [자료 검사](../../../../program/scripts/plan_qa_bench/results/saluki_finetune_preflight_20261009_113242/data_audit.json): 학습 완성문 계약 및 개발 평가 입력과 정확 중복 검사. 의미·일정군 독립성은 미검증입니다.
- [실측] [조건 검사 결과](../../../../program/scripts/plan_qa_bench/results/saluki_finetune_preflight_20261009_113242/gate_result.json): 10조건 중 3조건 충족, 준비 대기. 이것은 정확도 통과율이 아닙니다.
- [실패] 첫 패키지 버전 검사에서 `PackageNotFoundError: gguf`로 종료했습니다. 없는 배포 패키지를 별도 표시하도록 고쳐 CPU 읽기 확인을 완료했으며 패키지 설치·GPU 할당은 하지 않았습니다. 이후 stdin 연결 검사는 닫힌 stdin으로 실패했고 파일 입력 전달로 수정했습니다.

## 구현·백업

- [자료 검사기](../../../../program/scripts/plan_qa_bench/saluki_data_audit_20261009.py): 원본 자료를 변경하지 않고 정답·중복·해시를 기록합니다.
- [실행 조건 검사기](../../../../program/scripts/plan_qa_bench/server/queues/saluki_train_gate_20261009.py): 준비 상태만 출력하며 학습 프로세스를 띄우지 않습니다.
- [학습 환경 읽기 검사기](../../../../program/scripts/plan_qa_bench/server/queues/saluki_runtime_readonly_20261009.py): 모델을 적재하지 않습니다.
- [사전 확인 스크립트 백업](../../../../program/scripts/plan_qa_bench/results/saluki_finetune_preflight_20261009_113242/_backup/2026-10-09_1200_saluki_private_alias_cleanup/): 수정 직전 원본 보관 후 개인 근거 폴더로 이동했습니다. 새 판은 개인 접속 별칭을 환경 변수로 받아 공용 코드에 쓰지 않습니다. 이 백업과 원격 자원 원문은 개인 접속값이 포함될 수 있어 폴더의 git 제외 규칙으로 공유하지 않습니다.

[실측] [검사기 계약 확인](../../../../program/scripts/plan_qa_bench/results/saluki_finetune_preflight_20261009_113242/gate_contract_checks.json) **8/8 = 100%**: 동일 모델·revision 불일치, 역전파/보류 검증 부재, 활성 잠금, 수정 없는 실패 재시도, 공간 경계 1바이트 미달을 차단합니다. 이는 CPU 조건 검사이며 GPU 학습 성공이나 정확도 개선 시험이 아닙니다.

## 다음 작업

동일 Saluki의 학습 가능한 표현·CUDA 역전파·실제 할당량을 확보하고 사람 검수 및 독립 보류 자료를 고정하면, 기존 GPU 작업 뒤 16문항 연결 검사부터 이어갑니다. 현재는 조건부 준비 항목이며 실GPU 예약 등록·학습 완료·제품 채택·실서비스 배포를 뜻하지 않습니다.

## 관계

- [모델 평가 정본](../../quality/slm-model-evaluation.md)
- [GPU 운영 정본](../../operations/gpu-work-queue.md)
