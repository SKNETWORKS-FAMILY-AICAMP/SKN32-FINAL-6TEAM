# 오라클 ARM 서버 안 쓰는 공개 모델 7개 정리 기록 (Claude, 2026-10-14)

사용자 지시(2026-10-14): 「공개 모델 7개(30.7GB)를 지울지 — 지워」. 지우기 전에 받은 곳과 원본 해시를 남긴다.

## 지운 파일 — 다시 받는 법

모두 공개 모델이다. 오라클 서버 `~/bench/models/` 에서 지웠다. 원본이 같은 크기로 남아 있는 것을 2026-10-14 에 확인했다(접근 제한 없음).

| 파일 | 크기(바이트) | 원본 | 원본 해시(sha256) | 받은 날 | 원본 저장소 마지막 수정 |
|---|---|---|---|---|---|
| `g12b_q4km.gguf` | 7,121,861,440 | `unsloth/gemma-4-12b-it-GGUF` 의 `gemma-4-12b-it-Q4_K_M.gguf` | `0a270ec9fe6b34f4a0d33992b6135117b484ebc4766ab76b51d4ae8c457e4c42` | 2026-10-07 | 2026-07-17 |
| `e2b_q8.gguf` | 5,048,352,864 | `unsloth/gemma-4-E2B-it-GGUF` 의 `gemma-4-E2B-it-Q8_0.gguf` | `605d3c2647d7c58c1e4b5375ccb5702acf94c2611b4c8d4877812f8fdd32d053` | 2026-10-07 | 2026-07-17 |
| `frog4b_q8.gguf` | 4,622,130,976 | `bartowski/FrogNano-4B-2609-GGUF` 의 `FrogNano-4B-2609-Q8_0.gguf` | `ea42d264c21d88b9bf6ce583bb3fd4dfddb22eb5b30efba9e305c56f75974c86` | 2026-10-07 | 2026-10-02 |
| `kanana2_3b_q8.gguf` | 3,734,222,720 | `mradermacher/kanana-2-3b-instruct-GGUF` 의 `kanana-2-3b-instruct.Q8_0.gguf` | `259fcfee0daf4557b9c054bc1095f26ec103017f49987ad6e80c46a3136e38fb` | 2026-10-07 | 2026-07-29 |
| `e2b_qat_q40.gguf` | 3,349,516,256 | `google/gemma-4-E2B-it-qat-q4_0-gguf` 의 `gemma-4-E2B_q4_0-it.gguf` | `fa401b55b07ee70a54c6dae3903c783a6e65064312529ea57175cb5f8dec6634` | 2026-10-07 | 2026-07-17 |
| `exaone40_12b_q8.gguf` | 1,363,939,616 | `LGAI-EXAONE/EXAONE-4.0-1.2B-GGUF` 의 `EXAONE-4.0-1.2B-Q8_0.gguf` | `cc0b2a3f447e134cafd2853104d06227122cc280f4c9fee8c90172066174ef04` | 2026-10-07 | 2025-08-01 |
| `e4b_original_q4km.gguf` | 5,493,439,296 | Ollama 저장소 `library/gemma4` 의 조각(blob) | `370c2879f17648d337b0ab4e208fdce348e24d1060064e93d7645daafd56d39c` | 2026-10-12 | — |

- 받는 주소: 허깅페이스는 `https://huggingface.co/<저장소>/resolve/main/<파일>`, Ollama 는 `https://registry.ollama.ai/v2/library/gemma4/blobs/sha256:<해시>`.
- 원본 저장소의 마지막 수정일이 모두 받은 날 이전이라 지금 받아도 같은 파일이다. 서버에 있던 파일의 해시는 직접 재지 않았고 크기(바이트)가 원본과 같은 것으로 확인했다(`e4b_original` 은 받을 때 해시를 검증했다).
- 이 파일들을 쓰던 시험: 2026-10-07 속도 시험(`~/bench/results/<이름>_np1.jsonl`, 지우지 않음). 시험 대기열에서 보류(`deferred_for_app_serving`)된 4개(`e2b_qat` · `kanana` · `exaone` · `frog`)는 다시 돌릴 때 위 주소에서 받아야 한다.

## 확인한 것

- 지우기 전에 `/proc/*/fd` 를 전부 훑어(프로세스 208개) 이 7개 파일을 열어 둔 프로세스가 없는 것을 확인했고, 실행 중인 `llama-server` 는 `bge_m3_q8` · `e4b_qat_q40` 둘뿐이었다. 지금 서비스 중인 두 모델은 지우지 않았다. (처음 쓴 `fuser` 확인은 서버에 그 명령이 없어 빈 결과였으므로 근거로 쓰지 않는다.)
- 지운 뒤 오라클 서버 남은 공간 16GB → 44GB(`df`), 앱 `/health` 200, 앱 모델 · 임베딩 · 시험 대기열 서비스 `active`.
- 가르친 모델 `e4bt-Q8_0` · `e4bt-Q4_K_M` 은 지우지 않았다(허깅페이스 비공개 저장소 업로드는 별도 기록).
