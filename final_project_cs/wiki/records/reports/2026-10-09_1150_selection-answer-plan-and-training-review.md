---
type: report
title: 새 통합 여행 평가 계획·Saluki 학습 준비·Jev 비교
description: 최근 연구와 새 예시24개, 학습 조건 대기와 동일 문항 재계수를 구분한다
status: draft
domain: travel
---

# 새 통합 여행 평가 계획·Saluki 학습 준비·Jev 비교

D/E 이후 시험은 기존 자료를 그대로 합치는 대신 새 여행 일정에서 선택·근거·답변을 나눠 검사하는 방식으로 설계했습니다.24개는 개발 예시이며 사람 검수나 모델 성능 검증을 완료한 새 보류 자료가 아닙니다.

| 확인 | 상태 | 실측 |
|---|---|---|
| 최근 논문·이전/공식 참고 검토 | 완료 | 4/4·4/4 =100% |
| 개발 예시 형식·근거·입력/정답 분리 | 통과 | 24/24 =100% |
| 사람 검수·모델 실행 | 대기 | 각각0/24 =0% |
| 저장 학습판 원본 재계수 | 완료 | 5/5 =100% |
| Saluki CPU 실행 조건 검사 | 통과 | 8/8 =100% |
| Saluki GPU 학습 연결·본학습 | 조건 대기 | 0/2 =0% |

## 새 시험의 의미

[계획·최근 연구·대안](../../../../program/research/daily_rag_slm/selection_answer_plan_2026-10-09_v1.md), [제안 계약 정본](../../quality/selection-grounded-answer-evaluation.md), [구조화된 검토 상태](../../../../program/research/daily_rag_slm/selection_answer_review_2026-10-09_v1.json), [예시 원본·해시·검수 대기](../../../../datasets/core/answer_selection/selection_answer_bench/2026-10-09_pilot_v1/REPORT.md).

기존 항목이 없는 새 장소 요청은 잡담과 다릅니다. 선택 번호·요청 범위·근거 상태를 분리하고, 제공된 사실을 보존해 실제로 요청에 답했는지 확인합니다. 정답 대상/근거를 고정한 진단과 실제 전체 경로를 비교해 선택·검색·생성 손실을 구분합니다.

개발480개·독립720개는 제안 수량이며 아직 만들지 않았습니다. 제안 문턱은 기존 E 기준을 소급 변경하지 않으며, 본 계약 통과만으로 실서비스 배포나 상용화 완료를 선언하지 않습니다.

## Jev 관련 모델의 추가 학습 비교

[원본 재계수5판·문항별 검정·SHA](../../../../program/scripts/plan_qa_bench/results/jev_training_recount_20261009_v1/comparison.md).

과거 Winnow-E4B와 jevify-gemma4-e4b의 우리 여행 학습판은 동일 단일/요청없음769개에서756/769로 동률입니다. 최신 보강 Winnow는760/769, 독립 Jev 방식 Spark-S1-4B-v6 보강판은749/769입니다. 같은 문항의 Winnow만 정답16·Spark만 정답5, 양측 정확검정p=0.0266이지만 한 시드의 기본 개발 비교이며 여러 비교에 대한 보정과 독립 검증이 남았습니다.

Jevify 최신 보강판은 가중치 확보 오류로 학습 스모크에 실패했습니다. 이를 과거 성공판과 합치거나 정확도0으로 표시하지 않습니다. 전체 D/E와 답변 품질이 같은 범위로 완료된 Jev 비교군은 아직 확보되지 않았으므로 전 범위 최고는 미확정입니다. 단일 출력의 복합 완전선택0/66은 출력 계약의 제한도 포함합니다.

## Saluki 전담 작업

[전담 학습 계획](../../../../program/research/daily_rag_slm/saluki_finetune_plan_2026-10-09.md), [상태·레시피](../../../../program/research/daily_rag_slm/saluki_finetune_2026-10-09.json), [실측·실패·원본·백업](2026-10-09_1200_saluki-finetune-preflight.md).

사용자는 Saluki27B의 별도 학습을 승인했습니다. 정확한 고정 공식 배포의 학습 가능한 표현, 설치판 CUDA 역전파, 기존16GB GPU의 학습 메모리와 실제 저장 할당량이 미충족입니다. 다른 Underdog/Qwen을 Saluki로 대체하지 않습니다. 자료 검사와 낮은 학습률/rank8 첫 레시피, 실패 시 재시작을 막는 조건 검사기까지 준비했습니다. 조건부 항목은 실행 준비 상태가 아니어서 기존 GPU worker를 막지 않습니다.

새 학습은 정상 요청 보존과 비슷하게 말한 잡담 대조를 함께 검사합니다. 새 통합 시험의 ‘기존 대상 없음’을 모두 NONE 학습 정답으로 바꾸지 않습니다. 선택 학습과 근거 답변 학습은 별도 자료/손실로 연결합니다.

## GPU 관리의 실제 변화

[완료 회수·후속 등록·로드 전 실패 수정](2026-10-09_1150_gpu-refill-valen-d2-failure-and-winnow-role.md). GPU 서버 A11:40 관측은 계산1·준비4, GPU 서버 B11:34 관측은 계산1·후속3입니다. 잠깐0%였던 GPU 서버 A는 작업 전환 후 계산을 확인했습니다. 이 수치를 보고 시점의 새 실시간 관측이나24시간 풀가동 증거로 쓰지 않습니다.

## 백업·남은 일

공유 문서·상태 갱신 직전 백업은 각각 같은 폴더의 `_backup/2026-10-09_1152_selection-answer-integration/`에 보존했습니다. Quality색인 최초 등록 전 백업은 [이전 색인](../../quality/_backup/2026-10-09_1155_selection-answer-contract/index.md)입니다. 예시 완전일치 검사에 고객 질문 추출을 보강하기 전 [생성 도구](../../../../program/scripts/plan_qa_bench/_backup/2026-10-09_1208_question-extraction/selection_answer_pilot_20261009.py)와 [초기 manifest](../../../../datasets/core/answer_selection/selection_answer_bench/2026-10-09_pilot_v1/_backup/2026-10-09_1208_manifest/manifest.json)를 보존했습니다.

다음은 개발 답변/검색 평가 실행기·근접 중복 검사·두 사람 검수·독립 일정군 자료 작성과 해시 고정입니다. Saluki는 동일 모델 학습 경로를 먼저 확보한 후 GPU 연결 검사를 재개합니다. 외부 게시·push·결제·새 임대·기존 모델 삭제·실서비스 배포는 하지 않았습니다.
