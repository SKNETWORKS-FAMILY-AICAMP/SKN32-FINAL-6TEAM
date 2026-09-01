---
type: research
title: 번역 모델 비교
description: 다국어 응대 검토용 번역 성능 비교. 12GB VRAM 제약이 여기서도 드러났다
status: draft
tags: [evaluation, gpu]
owners: [human:미배정]
sources:
  - id: S1
    title: olist 리뷰 번역 벤치마크
    resource: ../../../datasets/mt/olist_reviews_mt_bench/REPORT.md
---

# 번역 모델 비교

`[실측:S1]` 2026-08-20 실행.

## 무엇을 했나

다국어 응대를 검토하려고 번역 모델들을 비교했다. x600 (RTX 4070 SUPER 12GB)에서 Ollama + GGUF Q4_K_M 양자화로 실행.

## 결과 — 장비 제약이 결론을 바꿨다

`[실측:S1]` **x600에서 "포기"로 결론 낸 모델들이 다른 환경에서는 돌았다.**

| 환경 | 사양 | 결과 |
|---|---|---|
| x600 | Windows, RTX 4070 SUPER **12GB** | 큰 모델 OOM |
| RunPod | Linux, RTX A4500 **20GB**, RAM 251GB | **통과** |

원문 결론이 이렇다.

> x600에서 "포기"로 결론 냈던 원인은 x600이라는 특정 환경(Windows·좁은 VRAM·비공식 경로) 때문이었다.

## 이 조사가 남긴 것

**번역 성능보다 장비 제약이 더 중요한 발견이었다.**

| 발견 | 어디로 이어졌나 |
|---|---|
| 12GB에서 큰 모델이 안 돈다 | [../business/infrastructure-cost.md](../business/infrastructure-cost.md) §3 |
| Windows가 문제를 악화시킨다 | 자체호스팅은 Linux 전제 |
| 임대 GPU로 우회 가능 | [D-004](../decisions/D-004-self-hosting-rationale.md) |

**MADLAD-400-10B**의 경우 FP16 가중치만 20~21GB라 12GB에 애초에 안 들어간다. 8-bit + CPU 오프로드로 겨우 돌렸고, 그것도 **다른 GPU 작업을 전부 멈춘 상태**에서만 가능했다.

## 번역 성능 결론

`[미확보]` 다국어 응대를 실제로 할지 아직 안 정했다. 성능 비교 결과는 [원본 REPORT](../../../datasets/mt/olist_reviews_mt_bench/REPORT.md)에 있다.

**범위에 들어오면 그때 다시 본다.**

## 관계

- [../business/infrastructure-cost.md](../business/infrastructure-cost.md) — 12GB 제약의 사업적 함의
- [../decisions/D-004-self-hosting-rationale.md](../decisions/D-004-self-hosting-rationale.md) — 자체호스팅 판단
- [../product/scope.md](../product/scope.md) — 다국어는 아직 범위 밖
