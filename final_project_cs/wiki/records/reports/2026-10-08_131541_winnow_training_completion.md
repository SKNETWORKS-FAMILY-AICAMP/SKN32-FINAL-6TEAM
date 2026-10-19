---
type: report
title: Winnow-E4B 여행 학습 산출물 보관
description: 본 학습·변환 완료와 기본 평가 진행을 분리한 실행 근거
status: draft
domain: travel
---

# Winnow-E4B 여행 학습 산출물 보관

[실측] Jev 계열 모델 중 Winnow-E4B(우리 여행 자료로 학습)의 본 학습·변환 산출물을 보관했다. 성능 평가는 진행 중이다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 본 학습·변환 | 완료 | 1/1판 = 100% |
| HF/GGUF 보관·해시 확인 | 완료 | 2/2종 = 100% |
| 기본 평가 답안 보관 | 진행 | 323/835개 = 38.68% |
| 기본 평가 완료 파일 | 부분 완료 | 2/5개 = 40% |
| 추가 평가 등록 | 호환 확인 대기 | 0/5개 = 0% |

## 조건·원본 근거

첫 보강 여행 자료1,713개, 시드20261012·r16·2에폭·학습률0.0002·누적8의 레시피다. 본 학습193.9분이며 학습 로그의 최대 GPU 사용량10.6GB다. 기반 배포 원본은 보존했고 다른 모델이나 두 번째 보강 자료로 바꾸지 않았다. 개발사 결정 학습과 우리 여행 자료 추가 학습을 구분한다.

[HF 어댑터](../../../../datasets/core/pointing/trainset/train_oos/winnow_e4b_oos_hf_adapter_2026-10-08_1308) · [GGUF 어댑터](../../../../datasets/core/pointing/trainset/train_oos/winnow_e4b_oos_lora_f16_2026-10-08_1308.gguf) · [학습 로그](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_e4b_oos_training_1308/qlora_train_winnow_e4b_oos.log) · [원격/로컬 해시·레시피·환경·기반 설정 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_e4b_oos_training_1308/training_archive_verified.json).

HF 가중치 SHA256 `ac3e8a62890a1265d0ada4e3a2a9f45a67e63865528a94bb51fa79a733c84d59`, GGUF SHA256 `3a4f2646ed55ce3758bc0c6e66b6ee005840886c499da4189e2503b2301ef963`다. 원격 파일과 로컬 사본을 비교했고 README·설정도 일치한다. 실행 환경 버전과 학습 도구·자료 해시는 검증 JSON에 고정했다.

## 부분 평가·한계

[완료 파일 mix10](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_e4b_oos_training_1308/eval_winnow_e4b_oos_mix10.json)160개와 [완료 파일 mix11](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_e4b_oos_training_1308/eval_winnow_e4b_oos_mix11.json)163개를 보관하고 원격 해시와 개수를 확인했다. 두 파일의 호출 오류0이다. 아직 회수하지 않은512개는 완료 정답이나 전체 오류0으로 표시하지 않는다. 전체835개 완료 후 B/C를 같은 문항으로 집계한다. 이번 기록은 학습 종료를 확인한 것이며 정확도 향상의 실측을 뜻하지 않는다.

## 다음 실행·변경 범위

GPU 서버 B의 기존 평가가 끝나면 나머지 기본 답안·로그를 회수한다. GPU 서버 A의 Winnow 배포 기반과 어댑터의 출처·구조·실행 호환을 확인한 다음 기존 실행기에 새 이름의 D/D2/D3/H/MX 다섯 평가를 등록한다. 원본·기존 학습판·고정 보류 자료와 비교 전 제품 모델로 승격하지 않는다.

GPU 서버 A는 준비된 평가5개가 대기하며 GPU 서버 B는 뒤 본 학습4개(기존 기반2개·자동 다운로드 준비2개)를 유지한다. 다운로드 직전 저장공간은 다시 확인한다. 실행기 추가·중복 실행·작업 중단·새 결제·기존 모델 삭제는 하지 않았다.

변경 파일은 일일 Markdown/JSON, GPU 상태 JSON, 모델 평가 wiki와 cs wiki log다. 새 회수 파일과 이 리포트는 새 이름이며 기존 근거를 덮지 않았다. 기존 상태·문서 수정 직전 백업:

- [program/research/daily_rag_slm/_backup/2026-10-08_131541_winnow_training_completion/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_131541_winnow_training_completion/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_131541_winnow_training_completion/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_131541_winnow_training_completion/2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_131541_winnow_training_completion/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_131541_winnow_training_completion/2026-10-08.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_131541_winnow_training_completion/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_131541_winnow_training_completion/slm-model-evaluation.md)
- [final_project_cs/wiki/_backup/2026-10-08_131541_winnow_training_completion/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_131541_winnow_training_completion/log.md)
