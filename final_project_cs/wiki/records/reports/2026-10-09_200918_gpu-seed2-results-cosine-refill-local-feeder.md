---
type: report
title: 두 번째 시드 비교 결과 회수와 cosine 추가 평가 및 자동 공급기
description: 완료 답안 전체 분모와 어댑터 SHA를 보존하고 유휴 GPU 서버 A를 기존 실행기로 다시 가동한 실측
status: draft
domain: travel
tags: [gpu, evaluation, finetuning]
---

# 두 번째 시드 결과와 GPU 일감 자동 보충

[실측] GPU 서버 A의 소진된 대기열에 새 학습판의 누락 평가를 보충해 계산을 재개했습니다. 완료 답안과 학습판을 보관했고, 승인된 후속 두 학습판의 자동 공급기를 이 PC에서 가동했습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 새 완료 평가 보관 | 완료 | 19,570/19,570 = 100% |
| 원격·로컬 SHA 대조 | 통과 | 72/72 = 100% |
| 새 cosine 기본 평가 | 완료 | 835/835 = 100% |
| 누락 평가 보충 | 완료 | 10/10 = 100% |
| 후속 자동 등록 통합 실측 | 학습 완료 대기 | 0/2 = 0% |

## 실제 계산과 대기열

[실측] GPU 서버 A 보충 전 2026-10-09T10:54:19.610039+00:00에는 GPU0%·실행기 생존·준비0개였습니다. 2026-10-09T11:01:23.061200+00:00에10개18,850문항을 같은 worker에 등록했습니다. 최종 2026-10-09T11:07:05.932228+00:00 (한국 시각 UTC+9)은 GPU 82 %, 3480 MiB, 16380 MiB·실행 `e4bbase_cosine_s20261013_d`·준비7개·입력 조건대기0개입니다. PID342497를 유지했으며 전체113개 중 완료103·과거실패2·실행1·미시작7개입니다. 최종 회수 snapshot은 현재 D답안 개수를 별도로 세지 않아 진행 숫자를 만들지 않았습니다.
[실측] GPU 서버 B 2026-10-09T11:05:37.579055+00:00은 GPU 12623 MiB, 94 %·B58 cosine seed20261014 270/654 = 41.28%, 다음 FINCH1개가 준비돼 있습니다. 준비1개로 목표3개 미달이며 임의의 새 시드는 추가하지 않았습니다. Saluki FT의 동일 가중치 학습 표현·역전파·16GiB 적재/공간, Spark 대응 기반 부재, StandardOne 공간/실행 호환, Jevify 과거 미수정 다운로드 실패 등 기존4개 후보군은 조건 대기입니다.
[실측] 남은 파일시스템 공간 A 4,101,066,752바이트, B 6,096,052,224바이트입니다. 계정 quota까지 보장하는 수치가 아니며 단기 관측을6시간 계속 풀가동한 증거로 확대하지 않습니다.

## FINCH 두 번째 시드 실측

아래 두 판은 모두 우리 여행 자료2613행으로 추가 학습한 동일 seed20261013 어댑터이며 기반 양자화만 다릅니다. D의 복합66개는 단일 번호 역할 진단으로 따로 보존하고 정상 요청883·요청없음1786과 섞지 않습니다.

| 역할 | Q4_K_M | QAT Q4_0 |
|---|---|---|
| D 정상 정답 | 765/883 | 766/883 |
| D3 정상 정답 | 104/120 | 105/120 |
| H 대조 정답 | 445/461 | 446/461 |
| D 요청없음 오지목 | 22/1786 | 29/1786 |
| D2 요청없음 오지목 | 6/1000 | 6/1000 |
| D3 요청없음 오지목 | 1/240 | 0/240 |
| H 함정 오지목 | 2/855 | 5/855 |
| E 혼합 정상 정답 | 915/1033 | 942/1033 |
| E 혼합 요청없음 오지목 | 3/974 | 7/974 |
| E 사전 합산 기준 | 2/4 | 2/4 |

[실측] FINCH10세트18,850/18,850, 실패·해석실패0·미완료0입니다. E는혼합2007+대조2007=4014문항이며 같은2007쌍을 독립표본4014개로 합치지 않습니다. 실패·미완료를 분모에서 빼지 않았습니다. E 사전합산2/4로 제품 채택 기준 통과가 아닙니다. 기존 개발/회귀 자료이며 사람 검수와 독립 보류 최종 검증은 별도 대기입니다.

## cosine 학습판 보관과 새 D3

[실측] cosine seed20261013 본654/654완료, 동일2613행·rank16·2에폭·accum8입니다. 학습17885.90초이며 recipe에 초기loss별도시간 필드가 없어 해당시간을0이라고 만들지 않았습니다. 기본HF NF4 단일번호 평가 B818/835·전체정확집합753/835·단일753/769·복합B65/66·복합C0/66·호출실패0입니다. 단일번호 계약의 복합C는 strict복수선택 역할 성능/학습실패로 읽지 않습니다.
[실측] [데이터 정본 HF/GGUF 폴더](../../../../datasets/travel/train_oos/oos2r_cosine_5e5_seed20261013_20261009)에6파일을 보관·재검증했습니다. GGUF69,798,944바이트 SHA256 `9832e316c7df17aa41649ab0847f98c36f4281cc403bce180e1665413641517f`. 원본 로그·기본평가를 포함한18파일도 전부SHA일치입니다.

[실측] cosine e4bbase D3도 보충 후360/360완료·정상106/120·요청없음오지목4/240·실패0으로 즉시 추가 보관했습니다.
[실측] cosine e4bqat D3도 보충 후360/360완료·정상107/120·요청없음오지목2/240·실패0으로 즉시 추가 보관했습니다.

cosine 본5역할 전체는 진행 중입니다. 같은 시드/양자화의 모든 비교가 완료되기 전 FINCH와 cosine의 최종 우열을 정하지 않습니다. 같은 엔진 속도·모델 정확도·생성 토큰 확률·말로 한 확신도를 구분하며 이 회차는 속도 비교를 수행하지 않았습니다.

## 숨김 로컬 자동 공급기

기존 queues/관련 watcher 파일 범위의 검색에서 완료 어댑터 자동 공급 경로를 찾지 못했습니다. 다른 경로나 외부 스케줄은 이 검색만으로 부재라고 단정하지 않습니다. 새 공급기는 기존 개인 SSH config를 이 PC에서만 사용하며 키를 원격으로 복사하거나 새 App 예약을 만들지 않습니다. 임의 명령을 설정으로 받아 실행하는 경로·새 GPU worker·학습 명령은 추가하지 않았습니다. 승인된 B58 cosine/FINCH seed20261014 두 레시피만10분마다 읽습니다.
[실측] 숨김PID24556·시작2026-10-09T11:04:16.3725952Z·확인2026-10-09T11:06:42.1551066Z·stderr0바이트입니다. 두 번째 실행은 파일잠금으로 거절됐습니다. 기존 완료 레시피2개36/36SHA 읽기검사·등록소스2/2컴파일·기존 입력/실행기계약10/10·대기/중복분기2/2를 확인했습니다. 준비 스모크에서 옛 base manifest에 prompt_sha256필드가 빠진 것을 확인해 오류원문을 보존하고 고정QAT원본과 실제입력SHA를 대조하는 새 시도로 고쳤습니다.
완료마커·recipe·654단계·학습자료/소스SHA·rank/epoch/accum·기본평가완료를 확인하고 전체HF/GGUF/로그를 새 폴더와 datasets에SHA보관합니다. 기존 같은 어댑터10역할이 등록돼 있으면 다운로드/등록을 하지 않습니다. 부분/동등역할 충돌은 수동 검토로 보존합니다. A공간3GiB와 전송여유, 전체모델/어댑터SHA·텐서구조·고정입력/실행기SHA·기존worker잠금을 통과해야 manifest백업→원자교체합니다. 실패 원인을 고치기 전 자동 재시도하지 않습니다.
[한계] B58 두 판은 아직 완료되지 않아 자동 공급의 전체 보관→전송→등록 경로를 실제 완료 어댑터로 통합 실행한 수는0/2입니다. 구성요소의 읽기검사와 대기 가동을 통합 성공이라고 쓰지 않습니다. 이 PC와 프로세스가 계속 살아 있어야 하며 재부팅 자동시작은 설정하지 않았습니다. 두 판이 완료되면 유효한 누락20평가만 공급하도록 구성했으며 아직 준비 작업으로 세지 않습니다.

## 근거·백업·다음 확인

- [FINCH·cosine 새12세트 전체집계](../../../../program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/completion_counts.json)
- [새 FINCH 답안SHA42/42](../../../../program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/A_verification.json)
- [cosine 학습 산출물SHA18/18](../../../../program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/B_verification.json)
- [추가 cosine D3 SHA6/6](../../../../program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/cosine_D3_completed/A_verification.json)
- [추가 cosine QAT D3 SHA6/6](../../../../program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/cosine_QAT_D3_completed/A_verification.json)
- [cosine 기본역할집계](../../../../program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/cosine_seed13_basic_counts.json)
- [데이터 정본SHA검증](../../../../program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/dataset_verification.json)
- [GPU 서버 A 실제계산/대기](../../../../program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/cosine_QAT_D3_completed/A_completed/snapshot.json)
- [GPU 서버 B 실제학습/진행](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/B_snapshot_hb2008final_20261009.json)
- [기존worker10평가등록·원격백업](../../../../program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/A_seed13_registration.json)
- [공급기 소스](../../../../program/scripts/plan_qa_bench/server/queues/completed_adapter_feeder.py)
- [공급기 완료레시피읽기·중복분기검사](../../../../program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/feeder_smoke_completed.json)
- [공급기PID/잠금확인](../../../../program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/feeder/process_proof.json)
- [공급기 상태·재개로그](../../../../program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/feeder/state.json)
- [공급기 준비오류보존](../../../../program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/feeder_prepare_a2_stderr.txt)
- [GPU 상태 수정 직전 백업](../../../../program/research/daily_rag_slm/_backup/2026-10-09_200918_gpu_hb1953_completion_feeder/gpu_backlog_2026-10-09.json)

다음 확인에서는 현재cosine D/D2/H/E완료분을 새 이름으로 회수·전체분모집계하고, B58 완료판 자동 공급 상태/실패원문을 먼저 확인합니다. 원인 미수정실패·완료MAI/Saluki/oos3/oos2r·Strata는 재실행하지 않았습니다.

- [고정 원본 ID집합·정답·유형·SHA 전체12세트 대조](../../../../program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/source_identity_verification.json) — 19,570/19,570 = 100%; H/E에도 연속 번호 가정을 쓰지 않았습니다.

## 개인 설정 보관 보완

개인 접속 설정은 기존 git 제외 영역의 [비공개 설정 파일](../../../../datasets/travel/gpu_feeder_private_20261009/private_config.json)로 옮겼고 이전 원본도 같은 영역의 백업으로 보존했습니다. 실행 중인 숨김 공급기는 설정을 이미 메모리에 읽었으므로 중단하지 않았습니다. 현재 프로세스 명령에는 구 경로가 남아 있으며, 재개할 때는 새 비공개 설정 경로를 사용합니다. 구 파일은 접속값 없는 위치 안내로 교체했습니다. 이번 회수 폴더의 원본·개인 실행 보조 스크립트도 폴더별 git 제외 규칙으로 보호했습니다.
