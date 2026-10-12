---
type: report
title: Valen 원본 실행 시작 및 복수 항목 역할 완료
description: 고정 원본 선택지 API 연결검사·실패 수정과 여행 복수 항목 답안 실측
status: draft
domain: travel
tags: [SLM, evaluation, GPU, native-choice]
---

# Valen 원본 실행 시작 및 복수 항목 역할 완료

Valen-0.8B 원본은 수정 연결검사를 통과했고 기존 GPU 서버 A worker에서 본 평가를 시작했습니다. 복수 항목 역할 6설정은 모두 보관·집계했습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 원본 파일 보관·SHA | 완료 | 17/17 = 100% |
| 전체 입력 실제 토큰 검사 | 통과 | 9425/9425 = 100% |
| 수정 GPU 연결검사 | 통과 | 12/12 = 100% |
| 연결검사 진단 정답 | 실측 | 4/12 = 33.33% |
| 복수 항목 역할 회수 | 완료 | 5010/5010 = 100% |

최종 GPU 서버 A 관측 2026-10-09T01:29:41.256128+00:00: 4876 MiB, 87 %, worker 342497 유지, 완료 80작업·별도 첫 연결 실패 1작업·계산 1작업·준비 대기 4작업·조건 대기 0작업. 현재 부분 답안 {'valen_08b_original_d3_a1': 132}이며 전체 본 비교 9425개 완료·최종 순위는 아직 아닙니다.
GPU 서버 B 관측 2026-10-09T01:23:24.649466+00:00: 12499 MiB, 100 %, FINCH seed20261013 400/654, 기존 B57/B58 생존 및 준비된 후속 학습 3개. 공간 관측은 앞선 09:58 값과 별도이며 이 새 프로세스 관측으로 다시 잰 공간이라고 쓰지 않습니다.

Valen의 고정 revision 3bf3e6d6318385884bf85e38dea1ca59afdf93f1, FP32 가중치 3417285852bytes SHA256 465714dd28702c4232d9233c2a2157d366967c541b2a27d9dadccc816304fd48을 확인했습니다. 공식 코드9개와 원본17파일 전체 해시를 고정했습니다. 최대47선택지·3934실제토큰이며 절단하지 않습니다. 일정·날짜·앞대화·질문·판단정책은 유지하고 JSON 생성 형식만 원본 선택지 API로 바꿨습니다. 정답·문항ID는 predict 입력 밖에 있습니다.

첫 a1은 모델 로드 전 실행환경 선택 오류로 0/12 저장·12개 미실행입니다. python 실행 파일 symlink의 resolved 경로가 같아 가상환경을 잘못 판별했습니다. 로그와 시작 흔적을 보존하고 sys.prefix로 고친 v2 및 별도 a2를 등록했습니다. 시스템 python→기존 rtenv 전환은 CPU에서 확인했습니다. 미시작 본5개만 새 실행기 SHA에 연결했고 worker를 중복 시작·중단하지 않았습니다.

a2는 12/12 정상 API·유한 확률·선택지ID·확률합 검사, 오류0·미완료0이며 정상 질문4/4, 요청없음/함정 오지목8/8입니다. 연결 성공을 정확도 개선으로 해석하지 않습니다. 원본 FP32 전체854305641매개변수·BF16 backbone autocast·FP32 head, shared_state·temperature1.0·local_files_only와 명시적 processor를 유지했습니다. 최대 GPU allocation4726889984bytes. causal_conv1d 최적 커널 미설치로 기존 PyTorch 기준 경로를 사용하며 패키지를 새로 설치하지 않았습니다. 이 확률은 native choice head이며 다음 토큰 확률·말로 한 확신도와 다릅니다. 다른 JSON 생성 경로와 속도를 직접 비교하지 않습니다.

| 판·양자화 | B 한 개 이상·없음 처리 | C 정확한 항목 집합 | 복합 C | 요청없음 오지목 | 오류 |
|---|---:|---:|---:|---:|---:|
| [원본 Q4_K_M](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_multi_items_bc_a1/multi_items_counts.json) | 787/835 | 666/835 | 48/66 | 19/186 | 5/835 |
| [원본 QAT Q4_0](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_original_multi_items_bc_a1/multi_items_counts.json) | 786/835 | 655/835 | 50/66 | 12/186 | 6/835 |
| [우리 학습 cosine Q4_K_M](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_cosine_s20261012_multi_items_bc_a1/multi_items_counts.json) | 819/835 | 788/835 | 55/66 | 7/186 | 0/835 |
| [우리 학습 cosine QAT Q4_0](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_cosine_s20261012_multi_items_bc_a1/multi_items_counts.json) | 819/835 | 781/835 | 56/66 | 5/186 | 0/835 |
| [우리 학습 FINCH Q4_K_M](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_finch_s20261012_multi_items_bc_a1/multi_items_counts.json) | 823/835 | 794/835 | 52/66 | 3/186 | 0/835 |
| [우리 학습 FINCH QAT Q4_0](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_finch_s20261012_multi_items_bc_a1/multi_items_counts.json) | 817/835 | 783/835 | 51/66 | 3/186 | 0/835 |

B/C 자료는 583단일·186요청없음·66복합의 기존835문항입니다. 새 strict items 배열·64출력 역할이며 옛 단일 선택 D/E 재실행이나 독립 보류 자료가 아닙니다. 기존 개발 자료의 첫 시드1회로 우열·채택을 확정하지 않습니다. FINCH Q4_K_M C전체는 cosine보다 높지만 복합 C는52/66 대55/66이고 앞선 E 정상 요청 회귀도 있어 전체 개선으로 채택하지 않습니다. D 복합66개는 Valen 단일 선택 경로에서는 별도 진단이며 복수 항목 C와 섞지 않습니다.

근거·재개:
- [수정 연결 원본·계약·부분 D3·SHA18/18](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/Valen_actual_smoke_runtime_20261009_1031/verification.json)
- [수정 연결 native 집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/valen_08b_original_smoke12_a2/native_counts.json)
- [전체 토큰길이 검사](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/Valen_actual_smoke_runtime_20261009_1031/all_input_context_preflight.json)
- [최종 GPU 상태](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_snapshot_valen_actual_20261009_1031.json)
- [최종 준비 조건](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_conditions_valen_actual_20261009_1031.json)
- [수정 등록·manifest 백업](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/Valen_registration_attempt2_20261009.json)
- [첫4설정 SHA20/20](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_multi_items_completed_20261009_1024/verification.json)
- [FINCH2설정 SHA10/10](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_multi_items_finch_completed_20261009_1029/verification.json)

본 평가는 기존 worker에서 D3→E(MX)→H→D→D2로 이어집니다. 새 완료 답안은 새 폴더로 회수·SHA 검증 후 backlog_valen_report.py로 전체 실패·미완료 분모를 유지하여 집계합니다. 본 평가가 실패하면 원문 보존 후 원인 수정·새 attempt를 사용하며 자동 재시작하지 않습니다. GPU 상태 JSON은 수정 직전 _backup/2026-10-09_103208_valen_actual_and_multi_completion에 보관했습니다. 공유 wiki·일일 기록·후보 목록은 부모 작업에서 연결합니다.
