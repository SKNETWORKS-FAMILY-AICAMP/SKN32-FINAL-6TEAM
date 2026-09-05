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

### 정규화 결과를 읽을 때

`[실측]` 두 쇼핑몰의 `normalize.py`가 같은 `order_schema.json`(JSON Schema draft-07) 중첩 구조로 낸다 — `payment` · `product` · `shipping` · `cs` · `_source`. 값이 추정된 자리는 **`_source.normalization_warnings`에 이름으로 남는다.**

| 경고 | 뜻 |
|---|---|
| `year_inferred:PaymentDate` | 네이버 원본 `PaymentDate`엔 연도가 없다. 입력 파일 수정 시각의 연도로 추정했다 (`OrderedAt`이 있으면 그걸 우선 쓴다) |
| `year_inferred:DeliveryCompleteDate` | 배송완료일도 연도가 없다. 주문일 연도로 만들고, **주문일보다 이르면 다음 해로 보정**했다 |
| `quantity_missing_or_invalid:defaulted_to_1` | 수량이 없거나 이상하면 1. 상품명에서 수량을 뽑지 않는다 |
| `tracking_export_missing_for_collected_order` | 쿠팡 — 배송 수집됐다고 표시된 주문인데 배송 JSON이 없다 |

**추정값을 조용히 넣지 않고 이름을 남기는 게 규칙이다.** 분석 전에 이 필드를 한 번 센다.

PII는 둘이 다르게 다룬다 — 네이버는 수령인·전화·상세주소를 `_source.pii_hashes`에 SHA-256 해시로만 남기고, 쿠팡은 확장이 애초에 수집하지 않는다(→ [scraper-notes.md](scraper-notes.md)). 지역은 둘 다 시·군·구까지만.

`--with-tracking`을 주면 네이버 정규화가 `courier_tracking/raw/tracking_*.jsonl`을 송장번호로 결합한다. 파일이 없으면 건너뛴다.

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

`sources_catalog`는 후보 소스의 **조사 기록**이다 — 목록의 대부분(AI Hub 3종·모두의말뭉치·AI Hub 102·공공데이터 7종·Kaggle 5종)은 이미 받아 각자 폴더로 독립했고, 이 폴더 자체에는 `raw/`·`processed/`가 없다. HuggingFace 감정분류 모델 후보 4종(kcbert·KoELECTRA 계열, 5~6종 감정)과 KOTE(댓글 43감정)는 **받지 않은 채 목록에만 있다** — REV 톤 사전 필터의 기준선 후보로 적혀 있고 통합은 안 됐다.

### `data_go_kr_consumer_complaints` — "완료"의 뜻과 함정

`[실측]` 2026-09-06 디스크 확인. [REPORT.md](../../../datasets/voc/data_go_kr_consumer_complaints/REPORT.md)와 어긋나는 게 둘이다.

| | |
|---|---|
| **인코딩** | 7종 전부 **EUC-KR/CP949**다. UTF-8로 열면 헤더부터 깨진다 — `encoding='cp949'` |
| 자유서술 원문 | 7종 중 **15098320(위해위험) 하나뿐**이다. 최대 규모인 15098340(온라인상거래 73만)엔 본문 필드가 없다 → [report-split.md](report-split.md) |
| 위 표의 "완료" | `processed/`에 있는 건 **15090382(품목별 피해구제 사례 XML 678건)에서 뽑은 근거 사례 2종** — `fulfillment_logistics_relevant_cases.jsonl`·`return_refund_evidence_relevant_cases.jsonl`. 7종 중 하나를 Team 근거용으로 추출한 것이지 7종 전처리가 아니다 |
| **폴더 규칙 위반** | 추출·검증 스크립트 둘(`extract_item_relief_cases.py`·`verify_item_relief_extraction.py`)이 **`scripts/`가 아니라 `processed/` 안에** 있다. `scripts/` 폴더 자체가 없다 → [index.md](index.md) 폴더 규칙 |
| REPORT.md | "아직 안 한 것 — `processed/`·`scripts/` 없음"이라 적혀 있다. **낡았다** — 위 추출이 그 뒤에 생겼다 |

`[미확보]` 15098320을 온라인 쇼핑몰 건만 골라내려면 `SALES_METHOD_CODE` 필터가 필요한데 **코드값 매핑표를 못 찾았다** — REPORT가 남긴 그대로다.

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
