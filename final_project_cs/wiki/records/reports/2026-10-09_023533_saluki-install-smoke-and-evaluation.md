---
type: report
title: Saluki 원본 설치와 실제 평가 시작
description: 고정 가중치와 연결검사를 확인하고 동일 여행 문항의 순차 비교를 시작했다
status: draft
domain: travel
tags: [evaluation, gpu, research]
---

# Saluki 원본 설치·연결검사 및 실제 평가 시작

Saluki 원본을 받아 전체 파일 해시를 확인했고 기존 GPU 서버 A의 순차 실행기로 실제 질의 시험을 시작했습니다. 연결검사 성공과 정확도 점수를 구분합니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 고정 가중치 다운로드 | 해시 일치 | 7,898,369,152/7,898,369,152바이트 = 100% |
| 연결검사 호출·해석 | 완료 | 12/12 = 100% |
| 연결검사 정답 | 참고 실측 | 9/12 = 75.00% |
| 본 평가 답안 | 실행 중 | 184/9,425 = 1.95% |
| GPU 서버 B 디스크 사본 | 전송 중 | 1212153856/7,898,369,152바이트 = 15.35% |

관측 기준은 2026-10-09 02:32:49 KST입니다. D3 부분 답안은 184/360 = 51.11%이며 ID·정답·유형·세트·문항 번호가 고정 정답과 184/184 일치합니다. 저장된 부분의 호출 오류·해석실패는 0/184이지만 나머지 176개는 미완료이며 전체 360 및 전체 시험 9,425 분모에 남깁니다. 완료 본 세트는 0/5입니다. 연결검사 12개를 본 평가 독립 정확도 표본에 합치지 않습니다.

연결검사는 실제 모델 로드와 호출·해석 12/12, 오류 0/12로 끝났습니다. 정상 요청 정답 5/6, 요청 없음 오지목 2/6이며 전체 정답은 9/12입니다. 이 작은 연결검사로 정확도 개선·상위권·제품 채택을 판단하지 않습니다.

## 고정 모델·입력·실행 조건

모델은 개발사 학습이 있는 배포 원본 ConwayResearch/Underdog-Saluki-27B-1.0 IQ2-mix이며 우리 여행 자료로 추가 학습하지 않았습니다. 고정 revision은 1336c0b5d74dfe6ad7f793577092f5effd9f97c6, 전체 가중치 SHA256은 4a673518b11b1c4445f9b9a9d3c40356f5ba39f6a6260dcb25f3fbfd475d9efb입니다. 언어 27B로 자동 소형 모델 추가 학습 범위에 넣지 않습니다.

설치된 llama.cpp 4ebdf2c, build 0.5.0-dev의 qwen35 코드와 실제 로드를 확인했습니다. 기존 엔진은 덮지 않았습니다. 기존 비교와 같이 CPU 범위 0–5·추론 스레드 4·GPU 레이어 99·문맥 4096·동시 슬롯 1·jinja·enable_thinking=false·temperature=0·출력 최대16을 고정했습니다. 실제 질의 정보만 모델 입력에 보내며 정답은 호출 본문에 넣지 않습니다. 엔진 바이너리·실행 코드·입력 파일 SHA와 원문 응답을 보관했습니다.

문맥 길이는 연결검사 12/12·D3 360/360을 실제 설치 엔진의 같은 대화 템플릿과 토크나이저로 검사했습니다. 최대 입력은 각각 1,953·2,007토큰이며 입력+16출력 한도를 넘는 문항 0/12·0/360입니다. 임의 잘라내기나 출력 수정은 하지 않았습니다. D3·연결검사는 logprobs 비활성, 나머지 4세트는 기존 경로처럼 logprobs와 top20을 켭니다. 토큰 선택 확률과 말로 표현한 확신도는 구분하고 모델 변경 정확도를 같은 모델 엔진 속도 비교로 쓰지 않습니다.

## 순차 실행·자원·보관

기존 worker의 현재 작업이 끝난 후 연결검사→D3→E(MX)→H→D→D2 순서로 자동 이어지도록 6작업을 등록했습니다. 기존 학습·평가를 중단하거나 두 번째 GPU worker를 띄우지 않았습니다. 12개 호출·해석 성공 마커와 검증된 모델 연결 파일이 있어야 본 시험을 시작합니다. 매 작업 전에 가중치 크기·SHA·로드 전 메모리 여유를 검사합니다. 입력/가중치가 사라지면 조건 대기이며 실패 작업은 원인 수정 없이 자동 재시작하지 않습니다. 실제 D3 실행이 시작돼 설치 계획만으로 완료 표시한 상태가 아닙니다.

02:28:23 KST GPU 서버 A 관측: GPU 100%·8,142MiB, 전체 등록63개·118,442문항, 완료57개·실행1개·준비대기5개·조건대기0개입니다. GPU 서버 B는 GPU100%·12,899MiB, FINCH140/654회 갱신이며 뒤에 B57/B58 학습4개가 준비돼 있습니다. 순간 관측이며 하루 종일 사용률을 보장한 측정으로 해석하지 않습니다.

GPU 서버 A의 기존 /dev/shm RAM에 약7.9GB 파일을 보관했으므로 휘발성입니다. 실제 cgroup 메모리 한도는 약31GB이며 D3 로드 전 여유7,821,004,800바이트를 확인했습니다. 연결검사 후 로드 상태의 여유는3,819,016,192바이트였습니다. 다운로드는 GPU를 쓰지 않고 속도와 메모리 보호 조건을 두었습니다. 기존 저장공간을 확장하거나 모델을 삭제하지 않았습니다. 로컬 C의 여유4,993,708,032바이트는 파일 전체보다 작아 로컬 영구 가중치 사본은 아직 없습니다.

검증된 GPU 서버 A RAM 파일을 기존 GPU 서버 B 디스크로 GPU 연산 없이 옮기는 중입니다. 02:32:45 KST 수신 상태는 receiving, 1212153856/7,898,369,152바이트이며 전체 SHA 검증·최종 이름 교체 전이므로 완료로 쓰지 않습니다. GPU 서버 B의 디스크 사본도 기계 삭제 후 유지되는 외부 영구 백업은 아닙니다. 로컬 제어 프로세스와 수신 상태를 확인해 살아 있으면 기존 전송을 기다립니다. 전송이 끊기면 .part와 GPU 서버 A 원본을 보존한 뒤 수신 바이트·기존 부분 해시를 확인하는 별도 재개 절차를 준비하며 지금 실행을 중복하지 않습니다.

cosine의 새 완료7개·14,116답안은 회수 대기입니다: Q4_K_M/QAT 각 D 2,735·D2 1,000·H 1,316, Q4_K_M E(MX) 4,014. 이전에 회수한 cosine D3 두 세트720개와 섞지 않았습니다. 다음 확인에서 완료 답안을 새 폴더에 회수하고 실패를 분모에 유지하는 기존 도구로 집계합니다. E는 backlog_mx_report.py를 사용합니다. 독립 보류 검증·반복·서비스 채택 및 상용화 판정은 아직 하지 않았습니다.

## 실행 증거·백업

- [전체 가중치 다운로드·SHA 검증](../../../../program/scripts/plan_qa_bench/results/saluki_preflight_20261009/download_verified_A_20261009.json)
- [6작업 등록·기존 worker 및 원자 교체 백업](../../../../program/scripts/plan_qa_bench/results/saluki_preflight_20261009/queue_registered_A_20261009.json)
- [회수 원문 및 부분 답안](../../../../program/scripts/plan_qa_bench/results/saluki_preflight_20261009/runtime_20261009_0232)
- [원격·로컬 파일 SHA 14/14](../../../../program/scripts/plan_qa_bench/results/saluki_preflight_20261009/runtime_20261009_0232/capture_manifest.json)
- [고정 정답·유형·실행 조건 독립 검증](../../../../program/scripts/plan_qa_bench/results/saluki_preflight_20261009/runtime_20261009_0232/runtime_verification.json)
- [연결검사 원문 summary](../../../../program/scripts/plan_qa_bench/results/saluki_preflight_20261009/runtime_20261009_0232/saluki_original_smoke12_a1/saluki_summary.json)
- [D3 실행 조건](../../../../program/scripts/plan_qa_bench/results/saluki_preflight_20261009/runtime_20261009_0232/saluki_original_d3_a1/saluki_contract.json)
- [D3 360개 문맥 길이](../../../../program/scripts/plan_qa_bench/results/saluki_preflight_20261009/runtime_20261009_0232/saluki_original_d3_a1/context_lengths.json)
- [GPU 서버 B 수신 진행](../../../../program/scripts/plan_qa_bench/results/saluki_preflight_20261009/runtime_20261009_0232/B_preservation_capture.json)
- [최신 GPU 상태 JSON](../../../../program/research/daily_rag_slm/gpu_backlog_2026-10-09.json)
- [상태 변경 직전 백업](../../../../program/research/daily_rag_slm/_backup/2026-10-09_023533_saluki_actual_running/gpu_backlog_2026-10-09.json)
- [Saluki 실행 코드](../../../../program/scripts/plan_qa_bench/server/queues/saluki_eval_20261009.py)
- [실행 코드의 계측 보강 전 백업](../../../../program/scripts/plan_qa_bench/server/queues/_backup/2026-10-09_0220_saluki_resource_samples/saluki_eval_20261009.py)

공통 날짜 기록·색인·후보 목록·wiki 본문은 부모 에이전트가 소유하며 이 작업에서 수정하지 않았습니다. 기존 산출물을 수정한 GPU 상태 JSON과 실행 코드·원격 manifest는 수정 직전에 백업했고 신규 보고서·회수 파일은 새 이름으로 보관했습니다.
