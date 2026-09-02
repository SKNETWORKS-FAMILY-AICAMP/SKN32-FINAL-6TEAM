---
type: dataset
title: AI Hub 71603 — 속성기반 감정분석 데이터
description: AI Hub 71603 — 속성기반 감정분석 데이터
status: draft
tags: [data]
---

# AI Hub 71603 — 속성기반 감정분석 데이터

## 출처

- AI Hub (한국지능정보사회진흥원), 데이터셋 번호 147 / `dataSetSn=71603`
- `https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=71603`
- 다운로드일: 2026-08-20 (`aihubshell`로 승인 후 직접 다운로드)
- 라이선스: 영리·비영리 R&D 목적 무료. 상업 서비스 임베드는 제공기관과 별도 협의 필요(AI Hub 이용정책 기준, 페이지 직접 확인).

## 받은 것

- 상품 리뷰(SNS 포함) 원천데이터 + 라벨링데이터(속성별 감성 BIO 태깅) 둘 다 받음
  — 이 데이터셋은 콜센터 QA(30716)와 달리 원천데이터가 음성이 아니라 텍스트라
  용량 문제가 없어서 전체를 받았다.
- `raw/01-1.정식개방데이터/Training|Validation/01.원천데이터/` — 카테고리별 zip
  (패션·화장품·가전 등 SNS/리뷰 원문)
- `raw/01-1.정식개방데이터/Training|Validation/02.라벨링데이터/` — 속성-감성 태깅 라벨
- 압축 해제 안 함(받은 그대로 zip 상태로 `raw/`에 보관)
- 총 용량: 63MB

## 선택 이유

`datasets/voc/sources_catalog/PLAN.md` 참고 — 요약하면, VOC가 마주치는
실제 케이스는 "배송은 느렸지만 품질은 좋았다"처럼 한 문장에 여러 속성에
대한 감성이 섞여있는 경우가 많아, 단순 긍정/부정 이분류(`naver_shopping_sentiment/`)
로는 못 다룬다. 이 데이터셋의 스팬 단위 속성별 태깅이 그 간극을 메운다.
