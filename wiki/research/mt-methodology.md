---
type: research
title: 번역 모델 비교 검증 방법론
description: 번역 모델 순위 비교가 성립하는 조건과 검증된 표·한계를 정리한다.
status: draft
tags: [evaluation, data, documentation]
domain: neutral
---

## 결론

`[실측]` 번역 모델 비교는 언어 부분집합, 테스트셋, 지표, 평가 방향, 보고 여부가 모두 같을 때만 성립한다. 특히 표 A의 WMT24++ 결과와 표 B의 FLORES-200 결과는 테스트셋과 지표가 다르므로 섞어 순위를 만들면 안 된다.

`[실측]` 외부에서 받은 TOP 15 표 2건 중 1건에는 논문에 없는 숫자가 다수 포함돼 있었다. MiLMMT-46-12B 영→한 XCOMET-XXL을 `97.85`로 적었지만 원문 값은 `89.07`이었다. 진짜 숫자와 부풀린 숫자가 섞인 표였다.

`[외부]` 공개 근거상 한국어에서는 Hunyuan 계열이 강하며 7B와 1.8B 모델 근거가 있다. Hy-MT2는 최신이지만 한국어 단독 근거는 `[미확보]`이므로 자체 데이터 평가 없이 도입을 판단하면 안 된다.

## 검증 절차

1. `[실측]` arXiv HTML 원문 5건을 로컬에 내려받았다.
2. `[실측]` 서브에이전트가 LaTeXML 표 마크업의 셀을 직접 파싱했다.
3. `[실측]` Codex가 같은 로컬 파일에서 독립적으로 다시 추출했다.
4. `[실측]` 두 추출본을 대조하고 영→한 핵심 표는 사람이 세 번째로 확인했다.
5. `[실측]` 불일치 항목은 원문을 다시 열어 판정했다.

`[실측]` 원문 HTML은 `.tmp/mt_papers/`에 있었으나 임시 폴더이므로 영구 보관은 전제하지 않는다.

## 검증 원문

원본에는 식별자만 있고 URL은 없다.

- `[외부]` arXiv `2602.11961` — Xiaomi, MiLMMT-46, `2026-02-12`; URL `[미확보]`
- `[외부]` arXiv `2605.22064` — Tencent, Hy-MT2, `2026-05-21`; URL `[미확보]`
- `[외부]` arXiv `2506.17080` — Unbabel, Tower+, `2025-06-20`; URL `[미확보]`
- `[외부]` arXiv `2511.07003` — NiuTrans, LMT-60, v1 `2025-11-10`, v2 `2026-04-24`; URL `[미확보]`
- `[외부]` Hugging Face 모델카드 `yanolja/YanoljaNEXT-Rosetta-12B-2510`; URL `[미확보]`

## 비교가 성립하는 조건 5가지

### 1. 언어 부분집합이 같아야 한다

`[외부]` MiLMMT-46 논문은 baseline을 MiLMMT와 겹치는 언어에서만 평가한다. `21`, `26`, `28`, `31`, `46`은 컬럼이 아니라 서로 다른 평가 집단이다.

`[외부]` Tower-Plus-9B의 `86.80`은 21개 언어, MiLMMT-46-12B의 `85.09`는 46개 언어 값이므로 직접 비교할 수 없다.

`[외부]` Tower+ Table 1도 7개·15개·24개 언어 컬럼으로 나뉜다. 72B의 15개 언어 `83.29`와 9B의 24개 언어 `84.38`을 비교하면 안 된다. 같은 컬럼에서는 7개 언어에서 72B `86.68`이 9B `86.25`보다 높고, 24개 언어에서는 9B `84.38`이 72B `83.74`보다 높다.

### 2. 지표 이름을 끝까지 확인해야 한다

`[외부]` XCOMET-XXL, COMETKiwi, COMET-22는 서로 다른 평가 모델이며 값의 범위도 다르다.

- MiLMMT-46: XCOMET는 XCOMET-XXL, COMETKiwi는 `wmt23-cometkiwi-da-xxl`, FLORES+ COMET은 `wmt22-comet-da`
- LMT-60: COMET-22와 SacreBLEU
- Hy-MT2: XCOMET-XXL, CometKiwi, GEMBA

### 3. 셀 안의 슬래시를 해석해야 한다

`[외부]` Hy-MT2의 `89.45 / 78.97 / 88.89`는 세 벤치마크가 아니라 FLORES-200 ZH⇔XX 셀 안의 XCOMET-XXL, CometKiwi, GEMBA 순 점수다.

### 4. 지표끼리 다른 결과를 낼 수 있다

`[외부]` Hunyuan-MT-7B는 영→한 XCOMET `92.21`로 1위지만 FLORES+ 영→한 spBLEU는 `24.57`로 하위권이고 같은 줄의 COMET은 `90.67`로 상위권이다. 출력 문체가 레퍼런스와 달라 생긴 것으로 보이며, 하나의 지표만으로 모델을 고르면 안 된다.

### 5. 논문이 보고하지 않은 값은 추정하지 않아야 한다

- `[미확보]` Hy-MT2 논문에는 부록과 언어별 표가 없어 한국어 단독 성능을 확인할 수 없다. 33개 언어 평균으로 추정하면 안 된다.
- `[실측]` TranslateGemma-27B는 MiLMMT 논문에 없으며 `27B`는 0회 등장한다.

## 표 A: WMT24++ 영→한

`[실측]`[외부]` 출처는 arXiv `2602.11961` 부록 Table 21과 Table 24이며 URL은 `[미확보]`이다. 같은 벤치마크·지표·방향이므로 직접 순위를 매길 수 있는 유일한 표다.

| 모델 | XCOMET-XXL | wmt23-cometkiwi-da-xxl |
|---|---:|---:|
| Hunyuan-MT-7B | 92.21 | 87.24 |
| HY-MT1.5-7B | 91.77 | 87.06 |
| Google Translate | 90.76 | 86.91 |
| HY-MT1.5-1.8B | 89.95 | 84.97 |
| TranslateGemma-12B | 89.88 | 85.85 |
| Gemini 3 Pro | 89.34 | 85.89 |
| MiLMMT-46-12B | 89.07 | 86.01 |
| GPT-5 | 88.85 | 86.06 |
| Gemini 2.5 Pro | 88.69 | 85.01 |
| MiLMMT-46-4B | 87.27 | 84.30 |
| Tower-PLUS-9B | 86.78 | 84.44 |
| TranslateGemma-4B | 85.97 | 82.51 |
| GemmaX2-28-9B | 84.69 | 81.87 |
| Seed-X-PPO-7B | 83.58 | 81.42 |
| Tower-PLUS-2B | 81.83 | 80.54 |
| MiLMMT-46-1B | 80.71 | 79.32 |
| GemmaX2-28-2B | 80.09 | 78.51 |
| Seed-X-Instruct-7B | 79.96 | 77.72 |

`[외부]` 이 조건에서 Hunyuan 계열 2개 모델은 GPT-5와 Gemini 3 Pro보다 한국어 XCOMET가 높다. HY-MT1.5-1.8B `89.95`는 TranslateGemma-12B `89.88`과 비슷하고 Tower-PLUS-9B `86.78`보다 높으므로 모델 규모만으로 성능을 판단할 수 없다.

## 표 B: FLORES-200 devtest 영→한

`[실측]`[외부]` 출처는 arXiv `2511.07003` 부록 Table 13이며 URL은 `[미확보]`이다.

| 모델 | COMET-22 | SacreBLEU |
|---|---:|---:|
| LMT-60-8B | 90.47 | 31.36 |
| LMT-60-4B | 90.47 | 29.38 |
| LMT-60-1.7B | 89.38 | 28.17 |
| LMT-60-0.6B | 87.55 | 26.61 |

`[외부]` 표 B는 표 A와 테스트셋과 지표가 모두 다르다. 두 표의 값을 나란히 놓고 모델 순위를 비교할 수 없다.

## 표 C: Hy-MT2 FLORES-200

`[실측]`[외부]` 출처는 arXiv `2605.22064` Table 2이며 URL은 `[미확보]`이다. 값은 33개 언어 XX⇔XX 전체 방향 평균이고 한국어 단독 점수는 `[미확보]`이다.

| 모델 | XCOMET-XXL / CometKiwi / GEMBA |
|---|---|
| Hy-MT2-30B-A3B | 87.47 / 76.34 / 88.79 |
| Hy-MT2-7B | 86.89 / 76.03 / 87.23 |
| Hy-MT2-1.8B | 79.77 / 73.41 / 78.64 |

`[외부]` 같은 표에서 Tower-Plus-72B는 `70.02 / 65.53 / 67.85`다. Tower+는 24개 언어만 지원하므로 33개 언어 평가는 지원 범위를 벗어나 불리하다.

## 표 D: Tower+ WMT24++

`[실측]`[외부]` 출처는 arXiv `2506.17080` Table 1이며 URL은 `[미확보]`이다. 지표는 xCOMET-XXL이다.

| 모델 | 7개 언어 | 15개 언어 | 24개 언어 |
|---|---:|---:|---:|
| Tower+ 2B | 81.88 | 78.42 | 79.13 |
| Tower+ 9B | 86.25 | 83.57 | 84.38 |
| Tower+ 72B | 86.68 | 83.29 | 83.74 |

`[외부]` 72B의 15개 언어 값과 9B의 24개 언어 값을 비교하면 안 된다. 같은 컬럼끼리만 비교해야 한다.

## 표 E: YanoljaNEXT-Rosetta WMT24++

`[실측]`[외부]` 출처는 Hugging Face 모델카드 `yanolja/YanoljaNEXT-Rosetta-12B-2510`이며 URL은 `[미확보]`이다. 베이스는 `google/gemma-3-12b-pt`, 규모는 12B이고 지표는 CHrF++ 하나뿐이다.

| 모델 | CHrF++ |
|---|---:|
| yanolja/YanoljaNEXT-Rosetta-12B-2510 | 37.36 |
| openai/gpt-4o | 36.08 |
| google/gemini-2.5-flash | 35.25 |
| yanolja/YanoljaNEXT-Rosetta-12B | 34.75 |
| yanolja/YanoljaNEXT-Rosetta-20B | 33.87 |
| google/gemini-2.0-flash-001 | 33.81 |
| openai/gpt-oss-120b | 31.51 |
| google/gemma-3-27b-it | 30.05 |
| google/gemma-3-12b-pt | 29.31 |

`[외부]` 모델카드에서는 Rosetta-12B-2510이 GPT-4o보다 높다. CHrF++는 문자 n-gram 겹침 기반이며 의미 정확도를 직접 측정하는 지표는 아니다.

## WMT25 자기 보고와 공식 사람 평가

- `[외부]` Tencent 논문 arXiv `2509.05209` 초록은 Hunyuan-MT가 WMT25의 31개 중 30개 카테고리에서 1위라고 자체 보고한다. URL `[미확보]`.
- `[외부]` WMT25 공식 findings `ACL Anthology 2025.wmt-1.22`는 30개 언어쌍과 60개 시스템을 다뤘다. 공식 ESA 사람 평가는 15개 언어쌍에서 수행됐다. URL `[미확보]`.
- `[외부]` 전체 최고인 Google Gemini 2.5 Pro는 15개 중 14개에서 승자군에 들었다.
- `[외부]` Tencent 출전작 Shy-hunyuan-MT는 constrained 부문 최고였고 15개 중 11개에서 승자군이었다.
- 자기 보고와 제3자 평가를 구분해야 한다.

## Tencent 모델 계보

`[외부]` `Hunyuan-MT(2025-09, WMT25 출전) → HY-MT1.5(2025-12-30) → Hy-MT2(2026-05-21)` 순이다. 이름이 비슷해도 서로 다른 세대다. 출처 URL은 `[미확보]`이다.

## 로컬 벤치마크 라벨 오류

- `[실측]` 대상은 `datasets/mt/olist_reviews_mt_bench/REPORT.md`이며 작성 당시 경로는 `program/research/archive/2026-08-20/mt_bench_results/`였다.
- `[실측]` Olist 리뷰 300쌍, PT→EN, GGUF Q4_K_M 모델 15개를 대상으로 sacrebleu BLEU와 chrF2를 측정했다.
- `[실측]` 이후 추가된 PT→KO 결과는 `hangul_ratio` 기반이므로 이 지적의 대상이 아니다.
- `[실측]` 마지막 두 열의 `원 리더보드 COMET-22`는 XCOMET-XXL, `원 리더보드 BLEU`는 COMETKiwi로 고쳐 읽어야 한다.
- `[실측]` 두 열은 영→한 값인데 나머지는 PT→EN 값이다. `92.21 / 87.24`, `86.78 / 84.44`, `89.07 / 86.01`이 표 A와 각각 일치한다.
- `[실측]` 잘못된 라벨은 Hunyuan-MT-7B가 리더보드 BLEU `87.24`에서 로컬 BLEU `26.53`으로 폭락한 것처럼 보이게 한다.
- `[외부]` 실제 FLORES+ 영→한 spBLEU는 `24.57`이다. 영→한 `24.57`과 PT→EN `26.53`은 직접 비교할 수 없다.
- `[실측]` REPORT는 깨진 출력 3건의 원인을 확인했고 LMT-60-8B의 thinking 문제를 `think:false`로 해결했다.
- `[실측]` 양자화 방식과 언어쌍이 달라 논문·리더보드와 직접 비교할 수 없다는 한계를 REPORT도 명시한다.
- `[실측]` 원본 REPORT는 수정하지 않았다.

## 한계

- `[미확보]` TranslateGemma 기술보고서 arXiv `2601.09012`에는 HTML 판이 없어 표를 추출하지 못했다. 이 문서의 TranslateGemma 값은 Xiaomi 논문의 재평가 값이다.
- `[실측]` LMT-60의 0.6B와 1.7B는 본문 집계표가 아니라 부록 언어별 표에서 확인했다.
- `[실측]` 수치 기준일은 `2026-08-19`다.

## 실무 결론

- `[외부]` 현재 공개된 한국어 근거에서는 Hunyuan 계열이 가장 강하며 7B와 1.8B 근거가 있다.
- `[미확보]` 최신 Hy-MT2의 한국어 단독 성능은 공개되지 않았다.
- 도입 전 자체 데이터로 다시 평가해야 하며 논문 수치는 해당 논문의 테스트셋 안에서만 해석해야 한다.

## 관계

- 원본: program/research/_번역모델_조사.md
