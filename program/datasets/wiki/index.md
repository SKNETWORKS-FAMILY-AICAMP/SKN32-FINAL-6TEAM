---
type: guide
title: datasets 지식 지도
description: 데이터셋 목록과 재생성 방법. REPORT는 이관하지 않고 재생성한다
status: draft
---

# datasets 지식 지도

**실제 데이터 파일은 여기 두고, 조사 문서는 `program/`에 둔다.**

## 폴더 규칙

```text
datasets/<도메인>/<이름>/
├─ raw/         원시 데이터.  git에 안 올림
├─ processed/   가공 데이터.  git에 안 올림
├─ scripts/     수집·가공 스크립트
└─ REPORT.md    이 데이터가 무엇이고 어디에 쓰이는가
```

`raw/`와 `processed/`는 본인의 실제 구매 기록을 담고 있어 git에 올리지 않는다. **스크립트와 스키마와 `REPORT.md`만 올린다.**

## 데이터셋

| 데이터셋 | 무엇인가 | A-COP에서 쓰는 곳 |
|---|---|---|
| `commerce/coupang_order_history` | 쿠팡 주문·배송 기록 | Context Broker의 주문 정보 |
| `commerce/naver_order_history` | 네이버 주문 기록 | 동. 쇼핑몰 두 곳으로 구조 편향을 막는다 |
| `commerce/courier_tracking` | 택배 배송 이력 조회 도구 | 배송조회 Action 실행부 |
| `voc/*` | 고객 문의·응대 공개 데이터 | RAG 지식 재료 |
| `mt/*` | 번역 성능 비교 | 다국어 응대 검토용 |

각 폴더의 `REPORT.md`가 그 데이터가 무엇이고 어디에 쓰이는지 설명한다. **데이터 관련 작업 전에 해당 `REPORT.md`를 읽는다.**

## ★ REPORT는 이관하지 않는다

`[실측]` `datasets/` 에 md 문서가 44개 있다. **wiki로 옮기지 않는다.**

REPORT는 데이터와 함께 살아야 하고, 상당수가 스크립트로 재생성된다. **생성 명령과 입력만 wiki에 기록하고 재생성한다.**

→ [중앙 허브 이관 계획](../../wiki/governance/migration.md)

## 사업성에 쓰인 것

| 데이터셋 | 어디에 |
|---|---|
| `voc/ecmc_dispute_casebook_2024` | 오류 1건당 손실 산정 (예정) → [unit-economics](../../wiki/business/unit-economics.md) |
| `mt/olist_reviews_mt_bench` | 12GB VRAM 한계 발견 → [infrastructure-cost](../../wiki/business/infrastructure-cost.md) |

**두 번째가 재미있다.** 번역 성능을 재려던 조사가 **장비 제약**이라는 더 중요한 발견을 남겼다.

## 관계

- [../../program/wiki/business/index.md](../../wiki/business/index.md) — 데이터가 사업 논거가 되는 곳
- [../../program/wiki/evaluation/golden-set.md](../../wiki/evaluation/golden-set.md) — 평가 데이터
- [../../program/wiki/research/mt-benchmark.md](../../wiki/research/mt-benchmark.md) — 번역 조사
