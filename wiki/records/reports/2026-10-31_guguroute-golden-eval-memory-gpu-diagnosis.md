---
type: report
title: 구구루트 골든 47행 재시도 — 적재 실패 원인(커밋 한도) 실측과 새 차단(GPU 경합·시간 초과)
description: 128GB 중 OS 30.5GiB·GPU 96GiB 분할, GPU 할당이 Windows 커밋을 소모함을 대조 실측. 적재는 성공했으나 실제 행 3/47 모두 120초 초과, 정확도 미측정
status: draft
domain: travel
---

# 구구루트 골든 47행 재시도 · 메모리/GPU 원인 실측 (2026-10-31 03:00~04:10 KST, 평가 전용)

선행: [첫 시도 보고](2026-10-31_guguroute-model-golden-eval.md) · 인계 [2026-10-31_guguroute-model-golden-eval](../../handoff/2026-10-31_guguroute-model-golden-eval.md)

**결론**
1. 128GB 장비에서 "GPU 96GB 여유"가 있는데도 적재가 실패한 원인은 **Windows 커밋 한도 92.8GiB(OS 메모리 30.5 + 페이지 파일 62.3)** 입니다. **GPU 전용 메모리에 올린 가중치도 프로세스 커밋으로 계산됩니다**(대조 실험으로 확인). Hermes Qwen 서버 하나가 커밋 36.5GiB를 잡고 있고, E4B 적재에는 커밋 **+5.96GiB**가 듭니다. 첫 시도 때 커밋 여유는 5.1~6.5GiB라 경계선 아래였습니다.
2. 이번에는 커밋 여유 7.7GiB인 시점에 적재가 **성공**했습니다(HTTP 200, 29.1초, VRAM 9.61GB 전부). 그러나 실제 행 **3/47 = 6.4%를 호출했고, 3/3이 고정 하네스의 120초 제한을 넘겼습니다.** 통과는 **0/47**이고 정확도는 「모름」입니다. 나머지 44행은 실행하지 않았습니다(중단 사유는 아래 3절).
3. 새 차단 원인은 **GPU 연산 경합**입니다. 다른 세션의 Qwen이 GPU를 93~96% 쓰고 있어서 E4B 생성 속도가 **2.29토큰/초**까지 떨어졌습니다. 따뜻한 상태에서도 한 행에 약 181초가 걸립니다(입력 처리 43초 + 생성 138초). 모델을 올려 둔 동안 커밋 여유가 0.75~1.1GiB까지 내려가서 다른 프로세스에도 위험했습니다.

## 1. 용량 실측 (추정 없음)
| 항목 | 값 | 출처 |
|---|---|---|
| 설치 메모리 | 128.0GB | `Win32_PhysicalMemory` 합 |
| OS가 쓰는 물리 메모리 | 30.5GiB | `TotalVisibleMemorySize` — 나머지 약 97.5GB는 하드웨어 예약 |
| GPU 메모리 | 98,240MiB(95.9GiB). 사용 27.8~31.7GiB, 여유 약 70GiB | `nvidia-smi` |
| 커밋 한도 | 92.8GiB(99.6e9B). 사용 85~92GiB | `GetPerformanceInfo` · `\Memory\Commit Limit` |
| 페이지 파일 | C:\pagefile.sys 63,803MB, 시스템 관리. 사용 10.9GB(최대 22.0GB). 압박 중에도 한도가 92.8에서 늘지 않음 | `Win32_PageFileUsage` · 표본 1,361개 |
| 커밋 구성 | 프로세스 private 합 63.5GiB + 비페이징 풀 13.4~14.4GiB + 페이징 풀 4.0GiB. 비페이징 풀의 소유자는 poolmon(관리자 권한 필요)이 없어 특정하지 못함 | 성능 카운터 |
| Hermes Qwen llama-server(PID 39560, 00:46 시작) | private 커밋 36.5GiB · 실제 상주(WS) 0.84GiB · GPU 전용 25.45 + 공유 2.20GiB | 프로세스·`GPU Process Memory` 카운터 |
| C: 여유 | 189~202GB | |

## 2. 원인 분리 (대조 실험)
같은 모델(FrogNano 4B Q4_K_M, 2.60GiB)을 `llama-bench`로 바꿔 가며 프로세스 최고 private 커밋을 쟀습니다.
| 조건 | 최고 private | 판정 |
|---|---:|---|
| `-ngl 0` CPU, mmap | 1.70GiB | 기준 |
| `-ngl 99` GPU 전부, mmap | 3.87GiB(2회 같음) | **GPU에 올린 가중치만큼 +2.17GiB 커밋 → 드라이버(WDDM) 커밋 부과가 주원인** |
| `-ngl 99` GPU 전부, `-lm none` | 4.28GiB | mmap을 끈 CPU 경유(staging)의 추가분은 0.41GiB로 작음 |

- 실제 Ollama 적재: 시스템 커밋이 85.11GiB에서 91.07GiB로 **+5.96GiB** 늘었습니다. Ollama 서버 프로세스의 private 커밋은 0.19GiB 그대로였습니다. 부과분은 다른 계정이 띄운 runner 쪽에 잡히는 것으로 보이며, 카운터 권한이 없어 프로세스별 분해는 하지 못했습니다.
- 따라서 장애 사슬은 「GPU 여유 부족」이 아니라 「**커밋 한도**(30.5 + 62.3GiB)를 GPU 할당과 다른 프로세스가 나눠 쓰는데, Qwen이 36.5GiB를 잡아 여유가 6GiB 아래로 내려감」입니다. 시스템 관리 페이지 파일은 이번 압박 중에 자동으로 늘지 않았습니다.
- **원래 HTTP 500 원문은 복구하지 못했습니다.** 첫 하네스는 `HTTP Error 500`만 남기고 본문을 저장하지 않았습니다. Ollama는 다른 계정(session 0)이 실행 중이라 실행 경로와 로그에 접근할 수 없었고, 디스크에서 server.log도 찾지 못했습니다. 오늘 같은 요청은 성공해서 500이 다시 나오지 않았습니다. 원문을 남기려면 다음 실패 때 본문을 저장하는 `ollama_probe.py`를 쓰면 됩니다.

## 3. 47행 실행 기록
- 동일성: 로컬 `tripilot-pointer:e4b-ft`의 Modelfile은 `FROM sha256-4c27e0f5…`, `ADAPTER sha256-f01456d8…`로 x600 보고와 같습니다. 고정 해시 8/8 OK(run_eval·score·입력·정답·adapter).
- e4b lease를 잡고(`gugu-golden-eval-20261031`, 이후 해제) 고정 `run_eval.py --select real`을 실행했습니다. 커밋 여유가 0.6GiB 아래로 내려가면 끊는 감시를 붙였습니다.
  - 결과: `E2-user-time-now-original`·`E2-user-afternoon-original`(user_reported)·`E2-real-q01-original`(real_browser_derived) 3행 모두 `FAIL_model_call`(ReadTimeout 124.7/120.3/120.1초). 4번째 행은 진행 중에 수동으로 중단해서 기록이 없습니다. **0/47 PASS · 실패 3 · 미실행 44.**
  - 실행 중 커밋 여유는 최저 0.87GiB, 가용 물리 메모리는 최저 0.74GiB였습니다. 같은 실패가 반복될 것으로 보고, 44×120초 동안 GPU를 함께 쓰며 다른 세션을 압박하지 않으려고 중단했습니다. 중단 뒤 모델 언로드를 요청했고, `/api/ps`가 비었으며 커밋도 회복된 것을 확인했습니다.
- 시간 진단(채점 제외, 합성 smoke 1행, 클라이언트 제한 900초): HTTP 200 · stop · 입력 8,152토큰/42.96초 · 생성 316토큰/138.23초(**2.29토큰/초**) · 적재 76.24초 · 합계 258.8초. 스키마(`format`) 313,171자, 프롬프트 16,730자. 이 결과를 보면 120초 제한 실패는 모델 품질 문제가 아니라 **이 PC의 GPU 경합 환경**에서 생깁니다.

## 4. 해석 한계
- 골든은 **기계 생성 + Sonnet 검토, 사람 검수 0/467**입니다. 47행은 x600 웹 시험 질문을 합성 일정에 다시 구성한 개발 노출 자료로, 독립 홀드아웃이 아닙니다.
- 경로 차이: 로컬은 비스트리밍 `structured`에 하네스 제한 120초를 씁니다. x600 제품은 스트리밍과 첫 조각 15초 감시를 씁니다. 로컬 Modelfile의 num_ctx는 8192이고 호출마다 12288을 넘깁니다. 로컬 GPU는 다른 모델과 함께 쓰고, x600은 하드웨어가 다릅니다. 따라서 이 PC의 지연은 x600 지연이 아닙니다.
- 605 에피소드(`chat_replay_20261019`, `episodes_v*.jsonl`/`targets_v*.jsonl`): `C:/_proj`·`C:/Users/kcxsz`(AppData 제외)·`sshuser`·`Public`·Hermes scratch에서 **파일 이름만** 찾았고 **0건**입니다. 각 경로 검색은 900초 상한 안에서 돌렸지만 경로별 완료 여부는 따로 확인하지 않았습니다. `eval/conversation_replay/` 코드(README, examples 합성 3행)만 여러 사본에 있습니다. 원문은 열지 않았습니다. 여전히 **차단** 상태입니다.

## 5. 다음에 안전하게 실행할 조건
1. 적재 전에 **커밋 여유 ≥ 8GiB**가 필요합니다(적재 +6GiB에 다른 프로세스 몫 2GiB 이상). 실측 시점의 여유는 12.09GiB였으므로 이 조건은 시점에 따라 충족됩니다.
2. **GPU 사용률(다른 세션) ≤ 약 20%**여야 합니다. 그렇지 않으면 120초 고정 하네스로는 측정할 수 없습니다. 대안은 제한시간을 600초로 늘린 변형을 **실행 전에 별도로 고정해 선언**하는 것입니다. 이 변형은 x600 15초 스트리밍과 다른 지표로 보고해야 합니다. 현재 경합에서는 47행에 약 2.5~3.5시간이 걸립니다.
3. 근본 해결은 모두 사용자 결정 사항입니다(이번에는 실행 안 함, 설정 변경 금지 지시). ① 고정 크기 페이지 파일을 늘려 커밋 한도를 올리기(관리자 권한·재부팅 가능성) ② Hermes Qwen의 ctx 147456 축소나 언로드 ③ x600 한산 시간대 실행 승인.
4. 실행 명령은 그대로입니다: `python _coord/e4b_lease.py acquire …` → `python gugu-memdiag-20261031/run_guarded.py real_e4b.jsonl 0.6`(이어받기는 지원하지만, 기존 3개 실패 행은 고정 규칙상 그대로 남음) → 해제 → `score_real.py`.

## 남긴 것 · 건드리지 않은 것
- 증거: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/gugu-memdiag-20261031/`(memsample·ollama_probe·run_guarded·diag_timing, 표본 jsonl, `probe1.json`, `diag_timing_metrics.json`, 수 MB). 실행 결과 `gugu-golden-eval-20261031/out/real_e4b.jsonl`(3행), `out/diag_timing_synthetic.jsonl`(1행).
- 모델 호출 장부: Ollama 적재·1토큰 1회, 실제 행 3회(실패), 합성 시간 진단 1회, 언로드 요청 2회. llama-bench 4회(소형 모델). 유료 API 0, 외부 전송 0(소켓 차단 기록 0), x600 접속 0, 서비스 재시작·설정 변경·다른 세션 모델 언로드 0.
- 고객 원문·키·프로세스 명령행은 기록하지 않았습니다.
