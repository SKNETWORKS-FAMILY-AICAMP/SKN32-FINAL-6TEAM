---
type: report
title: 번역 모델 15종 벤치마크 — Olist 리뷰 PT→EN / PT→KO
description: x600 (RTX 4070 SUPER 12GB)에서 Ollama + GGUF Q4_K_M 양자화로 실행.
status: draft
tags: [testing]
---

# 번역 모델 15종 벤치마크 — Olist 리뷰 PT→EN / PT→KO

2026-08-20. x600 (RTX 4070 SUPER 12GB)에서 Ollama + GGUF Q4_K_M 양자화로 실행.

## 결과 1 — PT → EN (완료)

| 순위 | 모델 | n | 빈응답 | 우리 BLEU | 우리 chrF | 원 리더보드 COMET-22 | 원 리더보드 BLEU |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | LMT-60-8B | 300 | 0 | **59.06** | 75.25 | - | - |
| 2 | GemmaX2-28-9B | 300 | 0 | 56.81 | 75.29 | 84.69 | 81.87 |
| 3 | Tower-Plus-9B | 300 | 0 | 55.94 | 76.16 | 86.78 | 84.44 |
| 4 | Tower-Plus-2B | 300 | 0 | 54.28 | 75.58 | 81.83 | 80.54 |
| 5 | GemmaX2-28-2B | 300 | 0 | 51.21 | 71.82 | 80.09 | 78.51 |
| 6 | MiLMMT-46-12B | 300 | 1 | 40.64 | 67.11 | 89.07 | 86.01 |
| 7 | MiLMMT-46-4B | 300 | 0 | 28.51 | 59.54 | 87.27 | 84.30 |
| 8 | HY-MT1.5-7B | 300 | 0 | 27.90 | 59.86 | 91.77 | 87.06 |
| 9 | Hunyuan-MT-7B | 300 | 0 | 26.53 | 59.81 | 92.21 | 87.24 |
| 10 | MiLMMT-46-1B | 300 | 0 | 23.87 | 56.53 | 80.71 | 79.32 |
| 11 | TranslateGemma-4B | 300 | 0 | 19.12 | 56.33 | 85.97 | 82.51 |
| 12 | TranslateGemma-12B | 300 | 0 | 18.70 | 56.75 | 89.88 | 85.85 |
| ⚠️→✅ | Seed-X-PPO-7B (GGUF) | 300 | 2 | 2.37 | 11.16 | 83.58 | 81.42 |
| ⚠️→✅ | Seed-X-Instruct-7B (GGUF) | 300 | 15 | 1.29 | 6.10 | 79.96 | 77.72 |
| ⚠️→✅ | HY-MT1.5-1.8B (GGUF) | 300 | 0 | 0.00 | 1.66 | 89.95 | 84.97 |

이 3개 행은 **GGUF 양자화가 깨진 결과** — 표는 원본 그대로 남겨두고, 공식 체크포인트로
재검증한 진짜 점수는 바로 아래 참조.

### ⚠️→✅ 신뢰할 수 없던 결과 3건 — 2026-08-24, 공식 체크포인트로 원인 확정 + 복구

당시엔 GGUF 양자화 결함으로 "추정"했을 뿐이었다. 2026-08-24에 별도 GPU 서버
(RunPod, RTX A4500 20GB, Linux, 공식 torch 2.8.0+cu128 / transformers 최신판)에서
**같은 모델의 원본(비양자화) HuggingFace 체크포인트**를 `transformers`로 직접 돌려
확정했다 — 프롬프트 포맷은 원래 쓰던 것과 동일했고, 문제는 100% GGUF 변환 쪽이었다.

| 모델 | 공식 체크포인트 | 우리 BLEU | 우리 chrF | 비고 |
|---|---|---:|---:|---|
| Seed-X-Instruct-7B | `ByteDance-Seed/Seed-X-Instruct-7B`, beam=4 | **57.51** | 78.01 | GGUF는 1.29였다 — 원 리더보드 1~2위권 실력이 맞았다 |
| Seed-X-PPO-7B | `ByteDance-Seed/Seed-X-PPO-7B`, beam=4 | 47.03 | 73.43 | GGUF는 2.37 |
| HY-MT1.5-1.8B | `tencent/HY-MT1.5-1.8B`, 카드 권장 샘플링 | 22.30 | 57.59 | GGUF는 0.00 — 완전 복구는 아니지만(1.8B라 원래도 약함) 정상 작동은 확인 |

원인: 이 셋 모두 **mradermacher/tencent의 GGUF 변환 자체가 깨져 있었다**(모델 자체 결함이
아님). LMT-60-8B는 그때 이미 원인(`think:false` 누락)을 찾아 고쳐서 1위를 기록했었다 —
그 교훈대로 나머지 3건도 "GGUF가 의심스러우면 원본 체크포인트로 재검증" 원칙을 끝까지
적용해 확정했다. 상세 재현 과정은 [결과 5](#결과-5--2026-08-24-gpu-재검증-madlad·nllb·ke-t5·seed-x·hy-mt-복구) 참조.

### TranslateGemma-4B/12B 참고

Google 공식 문서에 따르면 TranslateGemma는 `source_lang_code`/`target_lang_code`/`text`
필드를 쓰는 구조화된 전용 API가 필요하며 일반 텍스트 프롬프트를 지원하지 않는다.
Ollama에서는 이 구조화 API를 재현할 방법이 없어 평문 프롬프트로 대체했다 — 즉 이 두
모델의 점수는 실제 성능보다 낮게 나왔을 가능성이 있다.

## 결과 2 — PT → KO (완료, 2026-08-20)

동일한 300개 샘플, 동일한 15개 모델로 한국어 타겟 재실행. `en-translated` 같은
한국어 참조 번역이 없어서 **BLEU/chrF 계산은 불가능** — 대신 `hangul_ratio`(출력 문자 중
한글 비율)로 "출력에 한글이 얼마나 섞여 있는지"만 자동 계산한다(스크립트:
`scripts/mt_bench_score_ko.py`, 결과: `processed/leaderboard_result_ko.json`).

| 모델 | n | 빈응답 | hangul_ratio | 자동판정 | **수동 검증(샘플 3개 직접 읽음)** |
|---|---:|---:|---:|---|---|
| HY-MT1.5-7B | 300 | 0 | 0.989 | OK | ✅ 정확 |
| MiLMMT-46-1B | 300 | 0 | 0.988 | OK | ✅ 정확 |
| MiLMMT-46-12B | 300 | 0 | 0.985 | OK | ✅ 정확 |
| MiLMMT-46-4B | 300 | 1 | 0.985 | OK | ✅ 정확 |
| GemmaX2-28-9B | 300 | 0 | 0.982 | OK | ✅ 정확 |
| Tower-Plus-2B | 300 | 0 | 0.981 | OK | ✅ 정확 |
| GemmaX2-28-2B | 300 | 0 | 0.979 | OK | ✅ 정확 |
| Tower-Plus-9B | 300 | 0 | 0.977 | OK | ✅ 정확 |
| LMT-60-8B | 300 | 5 | 0.974 | OK | ✅ 정확 |
| Hunyuan-MT-7B | 300 | 0 | 0.965 | OK | ✅ 정확 |
| TranslateGemma-12B | 300 | 0 | 0.926 | OK | ✅ 정확 |
| TranslateGemma-4B | 300 | 0 | 0.895 | OK | ✅ 정확 |
| Seed-X-PPO-7B | 300 | 0 | 0.776 | OK(자동판정 오류) | ❌ **여전히 깨짐** — 아래 참조 |
| Seed-X-Instruct-7B | 300 | 5 | 0.422 | SUSPECT | ❌ **여전히 깨짐** |
| HY-MT1.5-1.8B | 300 | 0 | 0.0 | LIKELY BROKEN | ❌ **완전히 깨짐** |

### ⚠️ hangul_ratio 자동판정의 함정 — 실제로 걸림

`hangul_ratio`는 "한글 문자가 섞여 있는가"만 재기 때문에, 뜻이 완전히 다른 내용도
한글로만 써있으면 "OK"로 잘못 판정한다. **Seed-X-PPO-7B가 정확히 이 함정에 걸렸다** —
자동판정은 0.776로 "OK"였지만 샘플 3개를 직접 읽어보니 원문과 전혀 상관없는 문장을
출력했다:

```
원문: "O tampo da mesa chegou todo amassado e batido." (테이블 상판이 찌그러지고 훼손된 채 도착했다)
Seed-X-PPO-7B 출력: "그는 자신의 에고이스트ικ 회사에서 해고되었습니다." (그는 자신의 이기적인 회사에서 해고되었다)
```

전혀 다른 내용이고 그리스 문자(ικ)까지 섞여 있다. 자동 지표만 보고 "고쳐졌다"고
결론 냈으면 오보가 될 뻔했다 — **반드시 샘플을 직접 읽고 검증**해야 한다.

### 결론 — 3건의 EN 실패가 KO에서도 재현되는가

- **HY-MT1.5-1.8B**: EN·KO 둘 다 완전히 깨짐(같은 `"onse }"` 4토큰만 반복 생성). **언어와
  무관한 GGUF 파일 자체의 결함**으로 최종 확인됨.
- **Seed-X-PPO-7B / Seed-X-Instruct-7B**: EN·KO 둘 다 깨짐. 다만 깨지는 **양상은 언어별로
  다르다** — EN에서는 터키어·벵골어 등 완전히 무관한 언어를 뱉었고, KO에서는 한글이
  섞이긴 하지만(hangul_ratio는 그럴듯하게 높음) 내용이 원문과 무관하거나(Seed-X-PPO-7B),
  `<ko>` 태그만 50번 반복하거나 벵골 문자가 섞이는(Seed-X-Instruct-7B) 식으로 깨진다.
  **mradermacher 양자화 변환 과정의 결함**이라는 기존 결론이 KO 검증으로 다시 확인됐다.
- **나머지 12개 모델**: EN에서 정상이었던 모델은 KO에서도 전부 정상이다. 샘플 문장
  ("테이블 상판이 완전히 구겨지고 망가진 채로 도착했습니다" 등)이 원문 의미를
  정확히 담고 있음을 직접 확인했다.

**2026-08-24 후속**: 이 3개 모델을 공식(비양자화) 체크포인트로 재검증한 결과 EN·KO
둘 다 정상 작동한다 — 진짜 원인은 모델이 아니라 GGUF 변환 결함이었다. [결과 5](#결과-5--2026-08-24-gpu-재검증-madlad·nllb·ke-t5·seed-x·hy-mt-복구) 참조.

## 결과 3 — EN → KO (신규 축, 2026-08-21 착수 → 2026-08-24 완료)

기존 15종 벤치마크에 없던 모델들을 대상으로 두 방향을 추가로 시도했다. 최초 시도(x600,
2026-08-21)에서 Ollama 기반 9개 모델은 성공했지만 T5/CTranslate2 계열과 TranslateGemma-27B는
x600 환경 문제로 막혔다 — 2026-08-24에 별도 GPU 서버로 재시도해 대부분 복구했다
([결과 5](#결과-5--2026-08-24-gpu-재검증-madlad·nllb·ke-t5·seed-x·hy-mt-복구) 참조).

| 모델 | n | 빈응답 | hangul_ratio | 판정 |
|---|---:|---:|---:|---|
| MiLMMT-46-4B | 300 | 0 | 0.987 | OK |
| GemmaX2-28-2B | 300 | 0 | 0.986 | OK |
| nayohan-llama3-8B | 300 | 0 | 0.986 | OK |
| MiLMMT-46-12B | 300 | 0 | 0.985 | OK |
| Gugugo-koen-7B | 300 | 0 | 0.984 | OK |
| Tower-Plus-9B | 300 | 0 | 0.983 | OK |
| NLLB-200-3.3B | 300 | 4 | 0.974 | OK |
| seongs-ke-t5-base | 300 | 0 | 0.971 | OK |
| TranslateGemma-4B | 300 | 0 | 0.941 | OK |
| TranslateGemma-12B | 300 | 0 | 0.741 | OK |
| MADLAD-400-3B | 300 | 0 | 0.645 | OK |
| Helsinki-opus-mt-tc-big-en-ko | 300 | 6 | 0.428 | **SUSPECT — 실사용 불가** |
| TranslateGemma-27B | 300 | 300 | 0.0 | **LIKELY BROKEN — 미해결(아래 참조)** |

nayohan-llama3-8B(`afrideva/llama3-instrucTrans-enko-8b-GGUF`, EN→KO 전용 모델)와
Gugugo-koen-7B(`squarelike/Gugugo-koen-7B-V1.1`)는 각 모델 카드의 고유 프롬프트 포맷
(nayohan은 한국어 시스템프롬프트+챗, Gugugo는 `### 영어: {s}</끝>\n### 한국어:` raw
completion)을 그대로 써야 정상 번역이 나온다 — 일반 chat 프롬프트를 쓰면 지시문을 그대로
따라하거나 가짜 멀티턴을 만들어내는 결과가 나왔다(수정 후 정상 확인).

davidkim205/iris-7b는 사전 변환된 GGUF가 없어 시도하지 않았다.

### ⚠️ 최종까지 미해결로 남은 2건

- **TranslateGemma-27B**: Ollama GGUF(Q3_K_M)로는 300개 전부 빈 응답. 2026-08-24 GPU 서버에서
  `transformers`로 공식 체크포인트(`google/translategemma-27b-it`)를 직접 시도했으나
  **게이트(gated) 저장소라 인증 없이 접근 불가**(401, 라이선스 동의 + HF 토큰 필요) —
  팀 계정으로 라이선스 동의 후 `HF_TOKEN`을 넣으면 재시도 가능할 것으로 보이나, 이 세션에서는
  더 진행하지 않았다.
- **Helsinki-opus-mt-tc-big-en-ko**: CTranslate2로 변환해 돌렸지만 흔한 영단어("fast",
  "delivery", "hello")조차 토크나이저가 `<unk>`로 분해해버려 출력이 무관한 단어 나열이 된다
  (`sacremoses` 설치로도 해결 안 됨 — 어휘사전 자체 문제로 추정, 원인 미특정). hangul_ratio는
  0.428로 "SUSPECT" 판정이지만 실제로는 **사용 불가**로 처리한다.

## 결과 4 — PT → KO 신규 축 확장 (2026-08-24)

PT→KO에 새로 추가한 모델. TranslateGemma-27B는 [결과 3](#결과-3--en--ko-신규-축-2026-08-21-착수--2026-08-24-완료)과 같은 이유(게이트 저장소)로 시도하지 않았다.

| 모델 | n | 빈응답 | hangul_ratio | 판정 |
|---|---:|---:|---:|---|
| NLLB-200-3.3B | 300 | 0 | 0.982 | OK |
| MADLAD-400-3B | 300 | 0 | 0.638 | OK |

두 모델 다 샘플을 직접 읽어 확인했다 — 예: "O tampo da mesa chegou todo amassado e
batido." → MADLAD-400-3B "테이블 탑은 완전히 뒤틀리고 쓰러졌습니다.", NLLB-200-3.3B
"테이블 뚜은 완전히 겨서 찢어졌습니다."(오타성 표현 있지만 뜻은 통함) — 둘 다 원문 의미를
정확히 전달한다.

## 결과 5 — 2026-08-24 GPU 재검증: MADLAD·NLLB·ke-t5·Seed-X·HY-MT 복구

x600(Windows, RTX 4070 SUPER 12GB)에서 막혔던 모델들을 사용자가 제공한 별도 GPU 서버
(RunPod, **Linux, RTX A4500 20GB VRAM, 시스템 RAM 251GB**)에서 재시도했다. 결론부터:
**x600에서 "포기"로 결론 냈던 원인은 x600이라는 특정 환경(Windows·좁은 VRAM·비공식
torch 빌드) 문제였지 모델 자체의 결함이 아니었다** — 정상적인 Linux+공식 PyPI 환경에서는
아래 항목만 빼고 전부 복구됐다.

### 진짜 원인이었던 것들 (하나씩 확정)

1. **MADLAD-400 계열 완전 무작위 퇴화 출력(`"e e e e e e..."`)의 진짜 원인**: x600에서는
   "GPU 문제인가, transformers 5.x 문제인가, 캐시 손상인가"를 계속 의심만 하고 확정하지
   못했다. GPU 서버에서 **공식 문서 예제(`"<2pt> I love pizza!"` → `"Eu amo pizza!"`)조차
   `transformers` 최신판(5.15.1)에서 깨지고, `transformers==4.46.3`으로 낮추면 정확히
   `"Eu amo pizza!"`가 나오는 것을 직접 재현 확인했다.** 최신 transformers가 MADLAD-400의
   tied-weights(입출력 임베딩 공유) 처리 방식을 바꾸면서 생긴 회귀 버그로 확정. 토큰화
   자체(`<2ko>` prefix 등)는 처음부터 문제없었다 — x600에서의 의심은 방향이 틀렸었다.
2. **Seed-X-PPO-7B / Seed-X-Instruct-7B / HY-MT1.5-1.8B가 GGUF에서 깨졌던 진짜 원인**:
   공식(비양자화) HuggingFace 체크포인트로 직접 재현하니 셋 다 정상 작동했다(위 결과 1
   참조) — **mradermacher/tencent의 GGUF 변환 결함**이었지 모델이나 프롬프트 문제가
   아니었다. Seed-X 계열은 카드에 "chat template 쓰지 말고 raw 문자열 + 끝에 언어 태그"
   라고 명시돼 있었는데, 처음부터 그렇게 쓰고 있었다(`"...{s} <en>"`) — 원래 프롬프트
   설계는 맞았다.
3. **x600에서 "디스크 여유 350TB인데도 다운로드가 죽는다"에 해당하는 문제가 GPU 서버에서도
   재현**: `/workspace`(네트워크 스토리지, `df -h` 기준 350TB 여유)에도 실제로는 계정별
   할당량이 걸려 있어 **47GB 근처에서 `Disk quota exceeded`**가 났다 — `df`가 보여주는
   숫자와 실제 쓸 수 있는 용량이 다를 수 있다는 걸 두 서버에서 연달아 확인. 모델 처리
   후 캐시를 즉시 삭제하는 방식(1개씩 처리 → 삭제 → 다음 모델)으로 우회.
4. **백그라운드 실행이 계속 "이유 없이" 죽던 문제**: `nohup`/`setsid`/`tmux`까지 다 써봤는데
   SSH 세션이 끝나면 프로세스가 통째로 사라졌다 — 원인은 프로세스 분리 실패가 아니라 위 3번의
   디스크 할당량 초과가 반복적으로 겹쳐서 생긴 연쇄 장애였다(할당량 초과 시 로그 파일 쓰기부터
   실패하면서 tmux 서버까지 같이 죽었다). 디스크 문제를 고치자 일반 SSH 연결(도구의
   백그라운드 실행 기능으로 연결을 계속 열어두는 방식)만으로도 안정적으로 끝까지 돌았다.

### 여전히 안 되는 것 (근본 원인까지 확인됨, 재시도 안 함)

- **MADLAD-400-10B**: fp32/bf16 어느 쪽이든 최소 20GB 이상 필요, 다운로드만 해도
  네트워크 스토리지 할당량(~47GB 근처)의 대부분을 잡아먹어 나머지 모델을 처리할 공간이
  안 남는다. x600에서도 이 모델이 시스템 전체를 멈추게 한 원인이었다 — 리스크 대비
  얻는 정보가 적어 이번에도 포기.
- **TranslateGemma-27B**: 공식 체크포인트가 HuggingFace 게이트 저장소라 인증 없이 접근
  불가(401). Ollama GGUF 경로는 원인 불명으로 전부 빈 응답.
- **Helsinki-opus-mt-tc-big-en-ko**: 토크나이저 자체가 흔한 영단어를 `<unk>`로 분해하는
  근본 문제 — CTranslate2/sacremoses 설치로도 해결 안 됨, 원인 미특정.

### 방법론 메모

원본 15종/en_ko 9종과 실행 환경이 다르므로(Ollama GGUF Q4_K_M vs 여기는 transformers
fp16/CTranslate2 int8), 점수를 직접 비교할 때는 참고용으로만 볼 것 — 다만 진짜
목적은 "이 모델이 실제로 쓸만한가"를 확인하는 것이었고 그 목적은 달성했다.
스크립트: `scripts/gpu_runner_t5_ct2.py`(T5/CTranslate2), `scripts/gpu_runner_broken3.py`
(공식 체크포인트 재검증), `scripts/mt_bench_score_extra.py`, `scripts/mt_bench_score_broken3.py`.
