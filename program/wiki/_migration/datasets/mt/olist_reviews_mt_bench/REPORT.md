---
type: dataset
title: 번역 모델 15종 벤치마크 — Olist 리뷰 PT→EN / PT→KO
description: x600 (RTX 4070 SUPER 12GB)에서 Ollama + GGUF Q4_K_M 양자화로 실행.
status: draft
tags: [testing]
---

# 번역 모델 15종 벤치마크 — Olist 리뷰 PT→EN / PT→KO

## 출처·라이선스

- **원문(포르투갈어)**: [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (Kaggle). 라이선스 **CC BY-NC-SA 4.0** — 출처 표기·비상업적 이용·동일조건변경허락 조건.
- **영어 참조 번역(en-translated)**: 이 프로젝트 저장소(`team_branch/sw/`)에서 이미 준비된 상태로 발견함.
  누가 어떤 방식(수작업/API)으로 번역했는지 **문서화된 출처를 찾지 못했다** — 파일 목록,
  관련 HTML 2건 본문, git 이력(이 경로는 `.gitignore`로 추적 자체가 안 됨), Windows
  Zone.Identifier(다운로드 출처 URL, 있었으나 `HostUrl=about:internet`이라 zip 해제
  흔적만 있고 실제 URL 없음)까지 확인했다. 같은 걸 찾으려 한 다른 세션(`legacy/` 참조)도
  못 찾았다고 남겨뒀다. **sw 팀원에게 직접 확인 필요.**

## 방법론

- **정렬 검증**: 두 CSV는 공유 ID가 없어 행 순서로만 대응된다. CSV 파서로 정확히 파싱하면
  각각 40,950행 / 41,725행이며, **39,474번째 행 부근에서 번역본 쪽에 행이 하나 끼어들어
  이후 정렬이 어긋남**을 확인했다. 검증된 정렬 구간(0~39,473, 39,184쌍)에서만 사용한다.
  상세는 `preprocess_stats.json` 참조.
- **샘플**: 위 구간에서 무작위 300쌍 추출(seed=20260821, 재현 가능 — `scripts/mt_bench_prepare_sample.py`).
- **양자화**: 전부 GGUF Q4_K_M (원 리더보드는 보통 전체정밀도 또는 다른 양자화 기준이라
  점수가 그대로 비교되진 않는다 — 참고용으로만 볼 것).
- **프롬프트**: 모델별 공식 HuggingFace 카드의 권장 포맷을 그대로 사용. 일부는 raw
  completion, 일부는 단일 user 메시지 챗 포맷.

## 파일

- `raw/` — 원본 CSV 2개 (가공 안 함)
- `processed/sample.jsonl` — 검증된 정렬 구간에서 뽑은 300쌍 (PT 원문 + EN 참조)
- `processed/results/{모델명}.jsonl` — PT→EN 번역 결과 (완료, 15개 전부, GGUF 기준)
- `processed/results_ko/{모델명}.jsonl` — PT→KO 번역 결과 (완료, 15개 전부, GGUF 기준)
- `processed/results_extra_en_ko/{모델명}.jsonl` — EN→KO 신규 축 결과 (13개, TranslateGemma-27B는 전부 빈 응답)
- `processed/results_extra_pt_ko/{모델명}.jsonl` — PT→KO 신규 축 결과 (MADLAD-400-3B, NLLB-200-3.3B)
- `processed/results_broken3_pt_en/{모델명}.jsonl` — HY-MT1.5-1.8B/Seed-X-PPO/Seed-X-Instruct 공식 체크포인트 PT→EN 재검증
- `processed/results_broken3_pt_ko/{모델명}.jsonl` — 위 3개 모델 PT→KO 재검증
- `processed/leaderboard_result.json` — EN 결과 표 원본 데이터 (GGUF 기준)
- `processed/leaderboard_result_ko.json` — KO 결과 표 원본 데이터 (GGUF 기준)
- `processed/leaderboard_result_extra_en_ko.json` / `leaderboard_result_extra_pt_ko.json` — 신규 축 결과 표 원본 데이터
- `processed/leaderboard_result_broken3_pt_en.json` — 공식 체크포인트 재검증 BLEU/chrF 원본 데이터
- `scripts/` — 샘플 생성·실행·채점 스크립트 전체 (재실행 가능, 정본). `mt_bench_runner_extra.py`/`mt_bench_runner_single.py`는 x600(Windows) 확장 시도 스크립트, `gpu_runner_t5_ct2.py`/`gpu_runner_broken3.py`는 2026-08-24 별도 GPU 서버(Linux) 재검증 스크립트
- `legacy/` — 다른 세션이 만든 구버전(14종 기준, 결과 없음). 참고용, 정본 아님 — `legacy/README.md` 참조
- `preprocess_stats.json` — 정렬 검증·샘플링 통계
