---
type: dataset
title: 데이터셋 목록
description: 14종의 용도와 전처리 현황. 숫자는 문서가 아니라 디스크를 세어 넣는다
status: draft
tags: [data]
owners: [human:미배정]
size_exempt: true
size_exempt_reason: 데이터셋 카탈로그. 찾을 때 한 파일에서 검색하는 게 빠르다
---

# 데이터셋 목록

`[실측]` 2026-08-31 · 14종

**각 폴더의 `REPORT.md`가 정본이다.** 여기는 지도다.

## commerce — 주문·배송

| 데이터셋 | 무엇 | A-COP에서 |
|---|---|---|
| `coupang_order_history` | 쿠팡 주문·배송 기록 | Context Broker의 주문 정보 |
| `naver_order_history` | 네이버 주문 기록 | 동. **쇼핑몰 두 곳으로 구조 편향을 막는다** |
| `courier_tracking` | 택배 배송 이력 조회 도구 | 배송조회 Action 실행부 |

`raw/`와 `processed/`는 **본인의 실제 구매 기록**이라 git에 올리지 않는다. 스크립트와 스키마와 `REPORT.md`만 올린다.

## voc — 고객 문의·응대

`[실측]` 전처리 현황. **디스크를 세어 확인한 값이다.**

| 상태 | 데이터셋 | 크기 |
|---|---|---|
| **완료** | `naver_shopping_sentiment` | |
| **완료** | `aihub_30716_callcenter_qa` | K쇼핑 subset 추출·매핑 |
| **완료** | `data_go_kr_consumer_complaints` | |
| **완료** | `ecmc_dispute_casebook_2024` | |
| **완료** | `nikl_ne_2022` | |
| 미착수 | `aihub_102_smb_order_qa` | 189MB |
| 미착수 | `aihub_71603_aspect_sentiment` | 63MB |
| 미착수 | `aihub_71844_llm_instruction_tuning` | 209MB |
| 미착수 | `kaggle_customer_support` (5종 포함) | 463MB |
| | **미착수 합계** | **924MB** |

`sources_catalog`는 아직 안 받은 후보 소스 목록이다. `raw/`·`processed/`가 없다.

### ★ 계획서 숫자가 근거 없었다

`[실측]` 계획서에 오래 적혀 있던 **"VOC 5종 약 681MB"는 근거를 찾지 못했다.**

실제로는 **미착수 4종 924MB**다. `kaggle_customer_support` 하나가 안에 5종을 담고 있어서 "5종"이 거기서 왔을 가능성이 있다.

**문서에 적힌 숫자가 아니라 디스크를 센다.** 이게 이 프로젝트의 규칙이다.

## mt — 번역

| 데이터셋 | 무엇 |
|---|---|
| `olist_reviews_mt_bench` | 번역 성능 비교 |

**이 조사가 남긴 진짜 결과는 번역 성능이 아니라 장비 제약이었다.** 12GB VRAM에서 막힌 모델이 RunPod A4500 20GB에서 돌았다. → [../../wiki/research/mt-benchmark.md](../../wiki/research/mt-benchmark.md)

## 사업성·평가에 쓰이는 것

| 데이터셋 | 어디에 |
|---|---|
| `ecmc_dispute_casebook_2024` | 오류 1건당 손실 산정 **(예정)** → [unit-economics](../../wiki/business/unit-economics.md) |
| `aihub_30716_callcenter_qa` | 파인튜닝 1차 학습 데이터 (1,500건) |
| `olist_reviews_mt_bench` | 12GB 한계 발견 → [infrastructure-cost](../../wiki/business/infrastructure-cost.md) |

**`ecmc_dispute_casebook_2024`가 지금 가장 값진 미사용 자산이다.** 실제 분쟁 금액이 있어서 [사업성 문서](../../wiki/business/unit-economics.md)의 `[추정]` 3만원을 실측으로 바꿀 수 있다.

## 라이선스 주의

`[실측]` `kaggle_customer_support` 안의 **KR3**는 이전 카탈로그 기재("확인 안 됨")보다 제약이 크다. `REPORT.md`에 적혀 있다.

**쓰기 전에 해당 `REPORT.md`를 읽는다.**

## 관계

- [index.md](index.md) — 폴더 규칙
- [generation.md](generation.md) — REPORT 재생성
- [../../wiki/business/unit-economics.md](../../wiki/business/unit-economics.md) — 오류 손실 산정
- [../../wiki/evaluation/golden-set.md](../../wiki/evaluation/golden-set.md) — 평가 데이터
