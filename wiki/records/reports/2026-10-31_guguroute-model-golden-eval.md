---
type: report
title: 구구루트 배포 모델 실제 질의·골든 비교 — 준비 완료, 모델 실행 차단(메모리)
description: x600 배포 모델·코드 동일성 확인, 골든 47행·채점기 고정·대조 통과. 로컬 E4B 적재 실패(커밋 메모리 부족)로 실제 답변 0/47
status: draft
domain: travel
---

# 구구루트 배포 모델 실제 질의·골든 비교 (2026-10-31 02:00~03:00 KST, 평가 전용)

**결론: 오늘 실제 모델 답변은 0/47 = 0%라서 정확도는 「모름」입니다.** 평가 입력, 정답, 채점기, 그리고 배포본과 같은 코드·가중치는 모두 고정하고 검증했습니다. 그런데 이 PC의 로컬 Ollama가 모델을 올리지 못했습니다. 원인은 시스템 커밋 메모리 부족이고, 이 상태에서 무리하게 실행하지 않았습니다.

## 평가 대상 (실측)
| 항목 | 값 |
|---|---|
| x600 배포 코드 | `fab3da50ab` (deploy.log 「반영 완료」, api `ACOP_DEPLOYMENT_VERSION`) |
| x600 해석·짚기 모델 | `ACOP_OLLAMA_MODEL`·`ACOP_OLLAMA_POINTER_MODEL` = `tripilot-pointer:e4b-ft`, `ACOP_OLLAMA_NUM_CTX=12288`, 넘김 `gpt-6-luna`(평가에서 사용 안 함) |
| 가중치 동일성 | x600와 로컬 Ollama 모두 기반 `sha256-4c27e0f5…` + 덧붙임 `f01456d8…`, renderer/parser gemma4, temperature 0·top_k 64·top_p 0.95, Ollama 0.31.1. Modelfile num_ctx만 다름(8192/12288) → 호출마다 12288 전달 |
| 코드 사본 | `git archive fab3da50a` 사본. 핵심 6파일(decision_unit·edit_intent·schedule_query·ollama_chat·feedback·guardrails.yaml)의 blob이 GitHub fab3da50a와 6/6 일치 |

## 질의 출처와 골든
| 출처 | 행 | 골든 | 이번 사용 |
|---|---:|---|---|
| E2-v2 `real_browser_derived`(x600 웹 이용 시험 질문 45개를 합성 일정에 재구성) + `user_reported` 2 | 47 | E2-v2 `gold.jsonl`(소넷 검토 기계 정답, 사람 검수 0/467) — 요청별 대상 id·사실 칸 | **주 평가 분모** |
| x600 웹 채팅 시험 2026-10-13(운영자 시험, 고객 아님) `graded.tsv` | 439행(턴 ID 고유 435 · 문장 고유 415) | 당시 정답표 `replay/labels/batch1~3`·`inputs.jsonl`·`out_*`가 **디스크에 없음**(final_workspace 전수 검색 0) | 차단 — 정답 없이 채점하지 않음 |
| x600 DB `trip_chat_turns`(읽기 전용 건수만) | 고객 214턴 · 여행 46개(10-08~10-29) | 없음 | 건수만 기록. 원문 미반출·미채점 |

참고(과거 기록, 오늘 실측 아님): 10-13 시험 당시 배포 경로 판정 정상 105 + 불가 안내 17 = 122/439 = 27.8%(유료 대체 경로 시절 코드). 10-14 재생에서 학습 E4B의 요청 해석은 할 일 107/126 = 85%, 대상 54/69 = 78%였습니다(Claude 작성 정답표, 고치기 전 코드). 10-16 일정 짚기는 86/90 = 96%였습니다. 지금 코드에는 이 수치를 적용하지 않습니다.

## 고정한 평가 기준 (모델 실행 전)
- 경로: 배포 코드 `decision_unit.decide`(시스템 문장·생성 스키마·서버 검증 그대로)에 로컬 `tripilot-pointer:e4b-ft`를 연결하고, `num_ctx` 12288·`num_predict` 1200(guardrails)을 씁니다. DB·외부 소켓은 차단하고 127.0.0.1:11434만 허용했습니다. 비스트리밍 호출이며, x600의 스트리밍 상한 15초는 지연 기록으로만 대조합니다.
- 행 판정 PASS 조건: ①호출·검증 성공, ②정답에 쓰기 요청이 없으면 쓰기 할 일을 내지 않음, ③정답 요청마다 대상 id와 사실 칸이 대응표에 맞음. 실패는 `FAIL_model_call / unsafe_write / partial / miss`로 나눕니다. 오류·누락도 분모에 남깁니다.
- 채점기 대조: 정답으로 만든 양성 기록 47/47 = 100% PASS, 호출 실패 음성 기록 0/47 PASS. 실제 입력 47/47 = 100%가 배포 `decide()`의 프롬프트·스키마로 만들어졌습니다(모델 0회, 최대 system 15,629자 · 스키마 327,897자).

## 막힌 곳 (구체)
| 시도 | 결과 |
|---|---|
| 로컬 Ollama `decide` 1회(합성 smoke, 실제 행 아님) | 120초 ReadTimeout. `/api/ps` 적재 0 |
| e4b lease 아래 예열 1회(num_predict 1, 600초 한도) | 105초 뒤 **HTTP 500**. 시작 시 여유 물리 메모리 0.9GB |
| 같은 가중치를 llama.cpp CUDA(`C:/Users/kcxsz/llama.cpp`, f3fb2fcdb)로 적재 | `wrong number of tensors; expected 2131, got 720`. Ollama 전용 gemma4 blob이라 llama.cpp가 읽지 못함. 추론 0회 |
| 메모리 상태 | 커밋 여유 5.1~6.5GB / 92.8GB. Hermes 로컬 Qwen llama-server(PID 39560)가 private 35.9GB를 쓰고, GPU 사용률은 81~96%(다른 세션 사용) |

다른 세션의 모델·프로세스는 멈추지 않았습니다. x600은 이용자 규칙(시험 부하 금지)과 운영 모델 서버라는 이유로 추론에 쓰지 않았습니다.

## 다시 돌리는 조건과 명령
1. 다음 중 하나가 필요합니다. 이 PC의 커밋 여유가 약 12GB 이상 생기거나(Hermes Qwen을 내린 시점 등, 사용자 결정), x600 한산 시간대 실행을 사용자가 명시적으로 승인하는 것입니다.
2. `python _coord/e4b_lease.py acquire gugu-golden-eval-20261031` 뒤 `date_risk_env_312` python으로 `run_eval.py --select real --out real_e4b.jsonl`를 실행하고(47회, 이어받기 지원), lease를 해제한 다음 `python score_real.py out/real_e4b.jsonl`로 채점합니다.
3. 선택: `--select synthetic_original`(합성 원문체 가족)은 실제 행 결과를 본 뒤 별도 분모로 실행합니다.

## 남긴 것 · 건드리지 않은 것
- 증거: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/gugu-golden-eval-20261031/`(95MB). 하네스·채점기·대조·`frozen_hashes.txt`, x600에서 읽어 sha를 확인한 덧붙임 70MB, 배포 코드 사본 28MB.
- x600은 읽기만 했습니다(deploy.log 꼬리·모델 이름 env 키·채팅 턴 건수 SQL(read-only 트랜잭션)·`/api/show`·덧붙임 파일 복사). 쓰기·재시작·추론은 0입니다.
- 유료 API 0, 외부 전송 0, 운영 DB 쓰기 0, 원본 데이터셋 수정 0입니다. 고객 원문·키는 기록하지 않았습니다.
- 모델 호출 장부: Ollama 2회(답 0), llama.cpp 적재 1회(추론 0). 실제 47행 호출은 0회입니다.
