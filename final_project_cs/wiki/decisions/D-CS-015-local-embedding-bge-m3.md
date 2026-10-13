---
type: decision
title: 임베딩은 로컬 bge-m3 로 쓴다 — 품질 비교 없이 운영 사정으로 정했다
description: 2026-09-22 OpenAI 임베딩 크레딧이 떨어져 로컬 Ollama bge-m3(1024차원)를 임베딩 칸에 붙였다. 다른 모델과 같은 조건으로 비교한 적이 없다. 교체 여부는 여행 규정 질의 세트 비교 뒤에 정한다
status: draft
tags: [data, evaluation, cost]
owners: [human:미배정]
domain: travel
---

# D-CS-015 임베딩은 로컬 bge-m3 로 쓴다

## 현재 적용 범위 — 2026-10-12

정책(규정) 검색과 장소 임베딩은 로컬 Ollama의 `bge-m3:latest`(1024차원)로 계속 돌립니다. 이 선택은 **성능 비교로 고른 것이 아닙니다.** 운영에서 쓸 수 있는 임베딩 수단이 그때 이것뿐이었기 때문입니다. 다른 모델과의 비교는 아직 하지 않았고, 교체 여부는 그 비교 뒤에 정합니다.

## 무엇을 했나 (기록 기준)

| 날짜 | 무엇 | 근거 |
|---|---|---|
| 2026-09-22 | OpenAI 임베딩(1536칸)에만 묶여 있던 정책 검색을, 설정(`ACOP_EMBEDDING_PROVIDER`)으로 고르는 로컬 bge-m3(1024칸)를 추가 | 커밋 `f0d47b18` — 「크레딧 없이 시험이 전부 통과한다」, 청크 306개 재임베딩 |
| 2026-09-22 | 여행 코퍼스 130청크를 로컬 bge-m3로 적재. OpenAI 임베딩은 없음 | 커밋 `06d79683` · [마이그레이션 020](../../app/infrastructure/db/migrations/020_local_embedding_column.sql) |
| 2026-10-07 | 장소 임베딩(관광공사 목록)도 같은 bge-m3 로 저장 — 취향 근접성·분류 추정에 사용 | [마이그레이션 058](../../app/infrastructure/db/migrations/058_place_embeddings.sql) |
| 2026-10-11 | 로그에 「OpenAI 임베딩에만 매여 크레딧 소진 뒤 시험 3건이 계속 빨갰다」로 전환 이유를 적음 | [운영 로그 2026-10-11](../records/logs/2026-10-11_log.md) |

## 아직 없는 것 (확인 범위)

- **bge-m3 와 다른 임베딩 모델을 같은 질의·같은 조각으로 비교한 기록은 찾지 못했습니다.** 찾은 곳은 `wiki/`, `wiki/decisions/`, `wiki/records/`, `app/`의 임베딩 관련 기록과 커밋 이력(`git log -S "bge-m3"`)입니다.
- 현재 규정 검색 측정([RAG 평가 리포트 2026-10-06](../records/reports/2026-10-06_RAG_평가지표_리포트.md))은 bge-m3 한 모델의 기준선만 있습니다. 색인 글쓰기를 바꿔 얻은 개선은 측정했지만 모델은 바꾸지 않았습니다.
- 다른 프로젝트(`_unified_mall_3`, 보험 약관)에서는 bge-m3 가 비교 대상이었고 그 프로젝트 배포 모델은 `arctic-embed-l-v2.0-ko` 였습니다. **도메인이 달라 이 결과를 여행 규정에 그대로 옮기지 않습니다.**

## 그래서 무엇을 하나

1. 교체 후보: `embeddinggemma`(Google 신모델 — 2026-10-06 발표 보도 기준, 원문 미확인), `arctic-embed-l-v2.0-ko`(다른 프로젝트 배포 모델).
2. 같은 질의 세트·같은 색인 글·같은 문턱(`question.min_policy_score`)으로 재고, 결과를 이 문서에 덧붙입니다.
3. 교체가 필요하면 새 칸과 마이그레이션을 따로 두고, 기존 bge-m3 칸은 지우지 않습니다(칸 공존 원칙 — 마이그레이션 020 과 같습니다).
4. 비교 실행은 GPU 대기열 정책(한 기계, 기존 실행기 유지)을 따릅니다. 현재 대기열 상태와 등록 방법은 [GPU 작업 대기열 운영](../operations/gpu-work-queue.md)을 봅니다.

## 되돌리거나 바꿀 조건

- 같은 세트 비교에서 다른 모델의 규정 검색 Recall@3 가 bge-m3 보다 명확히 높으면(구간이 겹치지 않을 때) 교체를 검토합니다.
- 구간이 겹치면 교체하지 않습니다. 「조금 나은 것 같다」로 바꾸지 않습니다.

## 관계

- 임베딩 칸이 두 개인 구조: [마이그레이션 020](../../app/infrastructure/db/migrations/020_local_embedding_column.sql)
- 검색기가 고른 칸이 비면 예외를 내는 원칙: [검색기 `retriever.py`](../../app/infrastructure/rag/retriever.py)
- 이 문서는 [D-CS-005 ODsay 를 쓰지 않는다](D-CS-005-odsay-not-used.md)와 같은 방식으로 「사실 · 아직 없는 것 · 조건」을 나눠 적습니다.
